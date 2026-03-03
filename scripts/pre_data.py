# scripts/pre_data.py
import os
import sys
import torch
import pandas as pd
from torch_geometric.data import Data, Dataset
from tqdm import tqdm

sys.path.insert(0, '.')

class BlockchainGraphDataset(Dataset):
    """PyG dataset for blockchain graphs."""
    
    def __init__(self, root: str, transform=None, pre_transform=None):
        super().__init__(root, transform, pre_transform)
        self._num_features = 10
    
    @property
    def raw_file_names(self):
        return ['transactions.csv']
    
    @property
    def processed_file_names(self):
        path = os.path.join(self.processed_dir, 'graphs')
        return [f for f in os.listdir(path) if f.endswith('.pt')] if os.path.exists(path) else []
    
    def process(self):
        df = pd.read_csv(os.path.join(self.raw_dir, 'transactions.csv'))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.floor('H')
        
        os.makedirs(os.path.join(self.processed_dir, 'graphs'), exist_ok=True)
        
        for idx, (_, group) in enumerate(tqdm(df.groupby('hour'))):
            if len(group) < 2:
                continue
            graph = self._create_graph(group)
            if graph:
                torch.save(graph, os.path.join(self.processed_dir, 'graphs', f'graph_{idx}.pt'))
    
    def _create_graph(self, df):
        addrs = pd.concat([df['from_address'], df['to_address']]).unique()
        addr_map = {a: i for i, a in enumerate(addrs)}
        
        edges = [[addr_map[r['from_address']], addr_map[r['to_address']]] 
                 for _, r in df.iterrows() if r['to_address'] in addr_map]
        
        if not edges:
            return None
        
        x = torch.zeros((len(addrs), 10))
        for i, addr in enumerate(addrs):
            txs = df[(df['from_address'] == addr) | (df['to_address'] == addr)]
            x[i] = torch.tensor([
                len(txs), txs['value'].sum(), txs['gas_used'].mean(),
                (df['from_address'] == addr).sum(), (df['to_address'] == addr).sum(),
                txs['value'].std() if len(txs) > 1 else 0,
                1.0 if txs['is_malicious'].any() else 0.0, 0, 0, 0
            ])
        
        return Data(
            x=x,
            edge_index=torch.tensor(edges, dtype=torch.long).t(),
            y=torch.tensor([1 if df['is_malicious'].any() else 0], dtype=torch.long)
        )
    
    def len(self):
        return len(self.processed_file_names)
    
    def get(self, idx):
        return torch.load(os.path.join(self.processed_dir, 'graphs', f'graph_{idx}.pt'))
    
    @property
    def num_features(self):
        return self._num_features

def prepare_training_data(output_dir='data/processed'):
    """Generate synthetic data."""
    from src.data.synthetic_agents import MaliciousAIAgentSimulator, BenignAgentSimulator
    
    raw_dir = os.path.join(output_dir, 'raw')
    os.makedirs(raw_dir, exist_ok=True)
    
    mal_sim = MaliciousAIAgentSimulator()
    ben_sim = BenignAgentSimulator()
    
    txs = []
    for agent_type in mal_sim.AGENT_TYPES.keys():
        txs.extend(mal_sim.generate_transaction_sequence(agent_type, 200))
    txs.extend(ben_sim.generate_normal_transactions(1000))
    
    df = pd.DataFrame(txs).sort_values('timestamp').reset_index(drop=True)
    df.to_csv(os.path.join(raw_dir, 'transactions.csv'), index=False)
    
    print(f"✅ Generated {len(df)} transactions ({df['is_malicious'].sum()} malicious)")
    return df

def extract_features_batch(df, output_dir='data/processed'):
    """Extract features for XGBoost."""
    from src.features.opcode_parser import OpcodeAnalyzer
    
    analyzer = OpcodeAnalyzer()
    features = []
    
    for _, tx in tqdm(df.iterrows(), total=len(df)):
        feat = analyzer.extract_features(analyzer.parse_bytecode(tx.get('input_data', '0x')))
        feat.update({'value_eth': tx['value'], 'gas_used': tx['gas_used'], 'label': int(tx['is_malicious'])})
        features.append(feat)
    
    feat_df = pd.DataFrame(features)
    train = feat_df.sample(frac=0.8, random_state=42)
    val = feat_df.drop(train.index)
    
    train.to_csv(os.path.join(output_dir, 'train_features.csv'), index=False)
    val.to_csv(os.path.join(output_dir, 'val_features.csv'), index=False)
    
    print(f"✅ Features: {len(train)} train, {len(val)} val")
    return train, val
