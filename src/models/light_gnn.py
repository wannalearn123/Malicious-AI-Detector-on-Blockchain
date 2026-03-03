"""
Lightweight GNN untuk CPU/low-RAM environment.
Menggantikan MaliciousAgentGNN yang berat.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, global_mean_pool

class LightweightGNN(nn.Module):
    """
    Versi ringan: 32 hidden channels, 1 layer, tanpa attention.
    RAM usage: ~500MB vs ~4GB untuk versi full.
    """
    
    def __init__(self, in_channels: int, num_classes: int = 2):
        super().__init__()
        
        # Hanya 1 layer GNN (vs 2-3 di versi full)
        self.conv1 = SAGEConv(in_channels, 32)
        
        # Batch norm untuk stabilisasi
        self.bn1 = nn.BatchNorm1d(32)
        
        # Classifier sederhana
        self.classifier = nn.Sequential(
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(16, num_classes)
        )
        
        # Anomaly detection head
        self.anomaly = nn.Sequential(
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch
        
        # Single convolution
        x = self.conv1(x, edge_index)
        x = self.bn1(x)
        x = F.relu(x)
        
        # Global pooling (mean only, tanpa max concatenation)
        x = global_mean_pool(x, batch)
        
        # Predictions
        out = self.classifier(x)
        anomaly_score = self.anomaly(x)
        
        return out, anomaly_score

class CPUOptimizedTrainer:
    """Trainer yang dioptimalkan untuk CPU (tanpa CUDA)."""
    
    def __init__(self, model, learning_rate=0.001):
        self.model = model
        self.optimizer = torch.optim.Adam(
            model.parameters(), 
            lr=learning_rate,
            weight_decay=1e-5
        )
        
        # Gradient accumulation untuk simulasi batch besar
        self.accumulation_steps = 4
        
    def train_epoch(self, loader):
        self.model.train()
        total_loss = 0
        self.optimizer.zero_grad()
        
        for i, batch in enumerate(loader):
            # Forward
            out, _ = self.model(batch)
            loss = F.cross_entropy(out, batch.y)
            
            # Scale untuk gradient accumulation
            loss = loss / self.accumulation_steps
            loss.backward()
            
            # Update setiap accumulation_steps
            if (i + 1) % self.accumulation_steps == 0:
                self.optimizer.step()
                self.optimizer.zero_grad()
                
            total_loss += loss.item() * self.accumulation_steps
            
        return total_loss / len(loader)