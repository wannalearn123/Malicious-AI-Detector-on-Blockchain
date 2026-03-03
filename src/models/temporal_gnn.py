# src/models/temporal_gnn.py - Pembaruan State-of-the-Art

import torch
import torch.nn as nn
from torch_geometric.nn import GATConv, TransformerConv
from torch_geometric_temporal import DCRNN, A3TGCN  # Temporal GNN layers

class TemporalMaliciousAgentDetector(nn.Module):
    """
    Temporal Graph Neural Network untuk deteksi AI agents yang adaptif.
    Kontribusi: Belum ada di literatur existing [^28^][^33^]
    """
    
    def __init__(
        self,
        node_features: int,
        hidden_dim: int = 128,
        num_layers: int = 3,
        num_timesteps: int = 24,  # 24 jam sliding window
        attention_heads: int = 8
    ):
        super().__init__()
        
        # Temporal encoding menggunakan DCRNN (Diffusion Convolutional RNN)
        # Paper: "Diffusion Convolutional Recurrent Neural Network" (Li et al., 2018)
        self.temporal_encoder = DCRNN(
            in_channels=node_features,
            out_channels=hidden_dim,
            K=3,  # Chebyshev polynomial order
            num_layers=num_layers
        )
        
        # Attention mechanism untuk agent coordination detection
        # Referensi: Multi-agent reinforcement learning detection [^35^]
        self.coordination_attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=attention_heads,
            batch_first=True
        )
        
        # Temporal pattern detection untuk "agentic signatures" [^34^]
        self.pattern_lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim // 2,
            num_layers=2,
            batch_first=True,
            bidirectional=True
        )
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, 2)  # Binary: benign vs malicious AI agent
        )
        
        # Anomaly head untuk deteksi behavioral drift
        self.anomaly_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()
        )
        
    def forward(
        self, 
        x_sequence: torch.Tensor,  # [batch, timesteps, nodes, features]
        edge_index_sequence: list,  # List of edge_index for each timestep
        edge_attr_sequence: list   # Edge attributes (transaction values, etc.)
    ):
        """
        Args:
            x_sequence: Node features over time (sliding window)
            edge_index_sequence: Graph structure for each timestep
        """
        batch_size, timesteps, num_nodes, node_features = x_sequence.shape
        
        # Encode temporal dynamics
        temporal_embeddings = []
        for t in range(timesteps):
            # DCRNN forward
            h = self.temporal_encoder(
                x_sequence[:, t], 
                edge_index_sequence[t]
            )
            temporal_embeddings.append(h)
            
        # Stack: [batch, timesteps, nodes, hidden_dim]
        temporal_stack = torch.stack(temporal_embeddings, dim=1)
        
        # Detect coordination patterns (multi-agent interaction)
        # Reshape untuk attention: [batch * nodes, timesteps, hidden_dim]
        attn_input = temporal_stack.permute(0, 2, 1, 3).reshape(
            -1, timesteps, temporal_stack.size(-1)
        )
        
        attn_output, _ = self.coordination_attention(
            attn_input, attn_input, attn_input
        )
        
        # LSTM untuk temporal pattern detection
        lstm_out, _ = self.pattern_lstm(attn_output)
        
        # Global pooling
        # Mean pooling across time and nodes
        global_mean = lstm_out.mean(dim=(1, 2))  # [batch, hidden_dim]
        global_max = lstm_out.max(dim=1)[0].max(dim=1)[0]  # [batch, hidden_dim]
        
        global_repr = torch.cat([global_mean, global_max], dim=-1)
        
        # Predictions
        class_logits = self.classifier(global_repr)
        anomaly_scores = self.anomaly_head(
            lstm_out[:, -1, :]  # Last timestep
        ).mean(dim=1)  # Average across nodes
        
        return class_logits, anomaly_scores, temporal_stack

class AgenticSignatureExtractor:
    """
    Ekstraksi "agentic signatures" yang diusulkan di [^34^] tapi belum diimplementasikan.
    """
    
    def __init__(self):
        self.signatures = {
            'temporal_regularity': self._temporal_regularity,
            'coordination_pattern': self._coordination_pattern,
            'complexity_burst': self._complexity_burst,
            'memory_access_pattern': self._memory_access_pattern
        }
        
    def extract(self, transaction_sequence: list) -> dict:
        """
        Extract signatures yang indicate AI agent behavior vs human behavior.
        """
        features = {}
        
        # 1. Temporal Regularity: AI agents cenderung memiliki interval teratur
        timestamps = [tx['timestamp'] for tx in transaction_sequence]
        intervals = np.diff(timestamps)
        features['interval_cv'] = np.std(intervals) / np.mean(intervals) if len(intervals) > 0 else 0
        features['is_regular'] = features['interval_cv'] < 0.1  # Threshold untuk bot detection
        
        # 2. Complexity Burst: AI agents sering melakukan kompleksitas tinggi dalam waktu singkat
        gas_used = [tx['gas_used'] for tx in transaction_sequence]
        features['gas_entropy'] = self._calculate_entropy(gas_used)
        features['complexity_burst'] = self._detect_burst(gas_used)
        
        # 3. Coordination Pattern: Deteksi apakah transaksi terkoordinasi dengan alamat lain
        features['coordination_score'] = self._analyze_coordination(transaction_sequence)
        
        # 4. Memory Access: Pola akses storage yang sistematis (indikasi AI planning)
        features['memory_pattern'] = self._analyze_storage_access(transaction_sequence)
        
        return features
        
    def _calculate_entropy(self, values: list) -> float:
        """Shannon entropy untuk mengukur kompleksitas."""
        if not values:
            return 0.0
        hist, _ = np.histogram(values, bins=10)
        probs = hist / len(values)
        return -np.sum(probs * np.log2(probs + 1e-10))
        
    def _detect_burst(self, values: list, threshold: float = 2.0) -> bool:
        """Deteksi burst activity (banyak aktivitas dalam waktu singkat)."""
        if len(values) < 3:
            return False
        rolling_mean = np.convolve(values, np.ones(3)/3, mode='valid')
        return np.max(rolling_mean) > threshold * np.mean(values)
        
    def _analyze_coordination(self, tx_sequence: list) -> float:
        """
        Analisis koordinasi dengan alamat lain.
        High coordination = indikasi multi-agent system.
        """
        # Implementasi: analisis similarity dengan transaksi lain secara temporal
        # Jika banyak transaksi serupa dalam waktu singkat = coordinated
        return 0.0  # Placeholder
        
    def _analyze_storage_access(self, tx_sequence: list) -> dict:
        """
        Analisis pola akses storage (SLOAD/SSTORE).
        AI agents cenderung memiliki pola akses yang lebih sistematis/predictable.
        """
        patterns = {
            'read_write_ratio': 0.0,
            'access_entropy': 0.0,
            'sequential_access': False
        }
        return patterns