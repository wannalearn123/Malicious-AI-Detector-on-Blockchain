# scripts/pre_data.py
"""
Data preparation untuk training.
Bisa dijalankan di Colab atau local.
"""
import os
import torch
import pandas as pd
import numpy as np
from torch_geometric.data import Data, Dataset
from typing import List, Dict
from tqdm import tqdm
import gc

class BlockchainGraphDataset(Dataset):
    """Memory-efficient PyG dataset."""
    
    def __init__(self, root: str, transform=None, pre_transform=None):
        super().__init__(root, transform, pre_transform)
        self._num_features = 10
    
    @property
    def raw_file_names(self):
        return ['transactions.csv']
    
    @property
    def processed_file_names(self):
        processed_dir = os.path.join(self.processed_dir, 'graphs')
        if os.path.exists(processed_dir):
            return [f for f in os.listdir(processed_dir) if f.endswith('.pt')]
        return []
    
    def process(self):
        """Process raw transactions ke graphs."""
        print("🔄 Processing transactions to graphs...")
        tx_df = pd.read_csv(os.path.join(self.raw_dir, 'transactions.csv'))
        tx_df['timestamp'] = pd.to_datetime(tx_df['timestamp'])
        tx_df['hour'] = tx_df['timestamp'].dt.floor('H')
        
        os.makedirs(os.path.join(self.processed_dir, 'graphs'), exist_ok=True)
        
        for idx, (hour, group) in enumerate(tqdm(tx_df.groupby('hour'))):
            if len(group) < 2:
                continue
            
            graph = self._create_graph(group)
            if graph:
                torch.save(graph, os.path.join(self.processed_dir, 'graphs', f'graph_{idx}.pt'))
            
            if idx % 100 == 0:
                gc.collect()
    
    def _create_graph(self, tx_group: pd.DataFrame) -> Data:
        """Create PyG graph from transactions."""
        addresses = pd.concat([tx_group['from_address'], tx_group['to_address']]).unique()
        addr_map = {addr: i for i, addr in enumerate(addresses)}
        
        edge_index = []
        for _, tx in tx_group.iterrows():
            if tx['to_address'] in addr_map:
                edge_index.append([addr_map[tx['from_address']], addr_map[tx['to_address']]])
        
        if not edge_index:
            return None
        
        edge_index = torch.tensor(edge_index, dtype=torch.long).t()
        
        # Node features
        x = torch.zeros((len(addresses), 10))
        for i, addr in enumerate(addresses):
            addr_txs = tx_group[(tx_group['from_address'] == addr) | (tx_group['to_address'] == addr)]
            x[i] = torch.tensor([
                len(addr_txs),
                addr_txs['value'].sum(),
                addr_txs['gas_used'].mean(),
                (tx_group['from_address'] == addr).sum(),
                (tx_group['to_address'] == addr).sum(),
                addr_txs['value'].std(),
                1.0 if addr_txs['is_malicious'].any() else 0.0,
                0, 0, 0
            ])
        
        y = torch.tensor([1 if tx_group['is_malicious'].any() else 0], dtype=torch.long)
        return Data(x=x, edge_index=edge_index, y=y)
    
    def len(self):
        return len(self.processed_file_names)
    
    def get(self, idx):
        return torch.load(os.path.join(self.processed_dir, 'graphs', f'graph_{idx}.pt'))
    
    @property
    def num_features(self):
        return self._num_features

def prepare_training_data(output_dir: str = 'data/processed'):
    """Generate synthetic data."""
    from src.data.synthetic_agents import MaliciousAIAgentSimulator, BenignAgentSimulator
    
    print("📊 Generating synthetic data...")
    os.makedirs(output_dir, exist_ok=True)
    
    mal_sim = MaliciousAIAgentSimulator()
    ben_sim = BenignAgentSimulator()
    
    all_txs = []
    for agent_type in mal_sim.AGENT_TYPES.keys():
        all_txs.extend(mal_sim.generate_transaction_sequence(agent_type, 200))
    
    all_txs.extend(ben_sim.generate_normal_transactions(1000))
    
    df = pd.DataFrame(all_txs).sort_values('timestamp').reset_index(drop=True)
    df.to_csv(os.path.join(output_dir, 'transactions.csv'), index=False)
    
    print(f"✅ Generated {len(df)} transactions")
    return df

def extract_features_batch(df: pd.DataFrame, output_dir: str = 'data/processed'):
    """Extract features untuk XGBoost."""
    from src.features.opcode_parser import OpcodeAnalyzer
    
    print("🔧 Extracting features...")
    analyzer = OpcodeAnalyzer()
    features_list = []
    
    for _, tx in tqdm(df.iterrows(), total=len(df)):
        opcodes = analyzer.parse_bytecode(tx.get('input_data', '0x'))
        feat = analyzer.extract_features(opcodes)
        feat['value_eth'] = tx.get('value', 0)
        feat['gas_used'] = tx.get('gas_used', 0)
        feat['label'] = 1 if tx.get('is_malicious') else 0
        features_list.append(feat)
    
    feat_df = pd.DataFrame(features_list)
    train_df = feat_df.sample(frac=0.8, random_state=42)
    val_df = feat_df.drop(train_df.index)
    
    train_df.to_csv(os.path.join(output_dir, 'train_features.csv'), index=False)
    val_df.to_csv(os.path.join(output_dir, 'val_features.csv'), index=False)
    
    print(f"✅ Features: {len(train_df)} train, {len(val_df)} val")
    return train_df, val_df
