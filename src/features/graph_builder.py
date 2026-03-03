import networkx as nx
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from sqlalchemy.orm import Session

class TransactionGraphBuilder:
    """Build interaction graphs from blockchain transactions."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.G = nx.DiGraph()
        
    def build_transaction_graph(
        self, 
        start_time: datetime, 
        end_time: datetime,
        min_value_eth: float = 0.0,
        include_contracts: bool = True
    ) -> nx.DiGraph:
        """
        Build directed graph of transactions within time window.
        Nodes: Wallets/Contracts
        Edges: Transactions with weights based on value and frequency
        """
        from src.data.models import Transaction, Wallet
        
        # Query transactions in time window
        transactions = self.db.query(Transaction).filter(
            Transaction.timestamp >= start_time,
            Transaction.timestamp <= end_time
        ).all()
        
        G = nx.DiGraph()
        
        for tx in transactions:
            # Skip if below minimum value
            value_eth = float(tx.value) / 1e18 if tx.value else 0
            if value_eth < min_value_eth:
                continue
                
            from_addr = tx.from_address
            to_addr = tx.to_address
            
            if not to_addr:  # Contract creation
                continue
                
            # Add nodes with attributes
            if from_addr not in G:
                wallet = self.db.query(Wallet).filter_by(address=from_addr).first()
                G.add_node(from_addr, 
                          is_contract=wallet.is_contract if wallet else False,
                          risk_score=wallet.risk_score if wallet else 0.0)
                          
            if to_addr not in G:
                wallet = self.db.query(Wallet).filter_by(address=to_addr).first()
                G.add_node(to_addr,
                          is_contract=wallet.is_contract if wallet else False,
                          risk_score=wallet.risk_score if wallet else 0.0)
            
            # Add or update edge
            if G.has_edge(from_addr, to_addr):
                G[from_addr][to_addr]['weight'] += 1
                G[from_addr][to_addr]['total_value'] += value_eth
                G[from_addr][to_addr]['transactions'].append(tx.id)
            else:
                G.add_edge(from_addr, to_addr,
                          weight=1,
                          total_value=value_eth,
                          first_tx=tx.timestamp,
                          last_tx=tx.timestamp,
                          transactions=[tx.id])
                          
        self.G = G
        return G
        
    def build_temporal_graph(self, time_windows: int = 24) -> List[nx.DiGraph]:
        """
        Build sequence of graphs for temporal analysis.
        Each graph represents 1 hour window.
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_windows)
        
        graphs = []
        for i in range(time_windows):
            window_start = start_time + timedelta(hours=i)
            window_end = window_start + timedelta(hours=1)
            
            G = self.build_transaction_graph(window_start, window_end)
            graphs.append(G)
            
        return graphs
        
    def extract_graph_features(self, node: str, depth: int = 2) -> Dict:
        """Extract structural features for a node in the graph."""
        if node not in self.G:
            return {}
            
        features = {}
        
        # Basic centrality measures
        features['degree_centrality'] = self.G.degree(node)
        features['in_degree'] = self.G.in_degree(node)
        features['out_degree'] = self.G.out_degree(node)
        features['clustering_coefficient'] = nx.clustering(self.G.to_undirected(), node)
        
        # PageRank (importance in network)
        try:
            pr = nx.pagerank(self.G)
            features['pagerank'] = pr.get(node, 0)
        except:
            features['pagerank'] = 0
            
        # Betweenness centrality (bridging role)
        try:
            bc = nx.betweenness_centrality(self.G)
            features['betweenness'] = bc.get(node, 0)
        except:
            features['betweenness'] = 0
            
        # Ego network features (neighborhood)
        ego_net = nx.ego_graph(self.G, node, radius=depth)
        features['ego_size'] = len(ego_net)
        features['ego_density'] = nx.density(ego_net)
        
        # Transaction pattern features
        if self.G.in_degree(node) > 0:
            in_edges = self.G.in_edges(node, data=True)
            features['avg_in_value'] = np.mean([d['total_value'] for _, _, d in in_edges])
            features['max_in_value'] = np.max([d['total_value'] for _, _, d in in_edges])
        else:
            features['avg_in_value'] = 0
            features['max_in_value'] = 0
            
        if self.G.out_degree(node) > 0:
            out_edges = self.G.out_edges(node, data=True)
            features['avg_out_value'] = np.mean([d['total_value'] for _, _, d in out_edges])
            features['max_out_value'] = np.max([d['total_value'] for _, _, d in out_edges])
        else:
            features['avg_out_value'] = 0
            features['max_out_value'] = 0
            
        # Flow balance
        features['flow_balance'] = features['avg_in_value'] - features['avg_out_value']
        
        # Cycle detection (wash trading indicator)
        try:
            cycles = list(nx.simple_cycles(self.G.subgraph(list(ego_net.nodes()))))
            features['cycle_count'] = len(cycles)
            features['min_cycle_length'] = min(len(c) for c in cycles) if cycles else 0
        except:
            features['cycle_count'] = 0
            features['min_cycle_length'] = 0
            
        return features
        
    def detect_sybil_clusters(self, eps: float = 0.5, min_samples: int = 5) -> List[List[str]]:
        """
        Detect Sybil clusters using graph clustering.
        Returns list of address clusters likely controlled by same entity.
        """
        from sklearn.cluster import DBSCAN
        
        # Extract features for all nodes
        nodes = list(self.G.nodes())
        feature_matrix = []
        
        for node in nodes:
            feat = self.extract_graph_features(node, depth=1)
            vec = [
                feat.get('in_degree', 0),
                feat.get('out_degree', 0),
                feat.get('clustering_coefficient', 0),
                feat.get('flow_balance', 0),
                feat.get('cycle_count', 0)
            ]
            feature_matrix.append(vec)
            
        X = np.array(feature_matrix)
        
        # Normalize
        from sklearn.preprocessing import StandardScaler
        X_scaled = StandardScaler().fit_transform(X)
        
        # Cluster
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(X_scaled)
        labels = clustering.labels_
        
        # Group by cluster
        clusters = defaultdict(list)
        for node, label in zip(nodes, labels):
            if label != -1:  # Exclude noise
                clusters[label].append(node)
                
        return list(clusters.values())
        
    def find_mixing_patterns(self, target_node: str, min_hops: int = 2) -> List[Dict]:
        """
        Detect mixing/tumbling patterns (indicator of money laundering).
        Looks for long chains of transactions with similar amounts.
        """
        patterns = []
        
        # BFS to find paths
        for length in range(min_hops, 6):
            paths = self._find_paths_of_length(target_node, length)
            
            for path in paths:
                # Check if amounts are similar (peel chain pattern)
                amounts = []
                for i in range(len(path) - 1):
                    if self.G.has_edge(path[i], path[i+1]):
                        amounts.append(self.G[path[i]][path[i+1]]['total_value'])
                        
                if len(amounts) > 1:
                    cv = np.std(amounts) / np.mean(amounts) if np.mean(amounts) > 0 else 0
                    if cv < 0.1:  # Coefficient of variation < 10%
                        patterns.append({
                            'path': path,
                            'length': length,
                            'amounts': amounts,
                            'cv': cv,
                            'pattern_type': 'peel_chain' if length > 3 else 'simple_mix'
                        })
                        
        return patterns
        
    def _find_paths_of_length(self, start: str, length: int) -> List[List[str]]:
        """Find all simple paths of exact length from start node."""
        paths = []
        self._dfs_paths(start, [start], length, paths)
        return paths
        
    def _dfs_paths(self, current: str, path: List[str], target_length: int, results: List):
        """DFS helper for path finding."""
        if len(path) == target_length + 1:
            results.append(path.copy())
            return
            
        if current not in self.G:
            return
            
        for neighbor in self.G.successors(current):
            if neighbor not in path:  # Simple path (no cycles)
                path.append(neighbor)
                self._dfs_paths(neighbor, path, target_length, results)
                path.pop()
                
    def to_pytorch_geometric(self) -> 'torch_geometric.data.Data':
        """Convert NetworkX graph to PyTorch Geometric Data object."""
        import torch
        from torch_geometric.data import Data
        
        # Node mapping
        node_list = list(self.G.nodes())
        node_to_idx = {node: i for i, node in enumerate(node_list)}
        
        # Edge index
        edge_index = []
        edge_attr = []
        
        for u, v, data in self.G.edges(data=True):
            edge_index.append([node_to_idx[u], node_to_idx[v]])
            edge_attr.append([
                data.get('weight', 1),
                data.get('total_value', 0),
                (data.get('last_tx') - data.get('first_tx')).total_seconds() if data.get('last_tx') and data.get('first_tx') else 0
            ])
            
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_attr, dtype=torch.float)
        
        # Node features
        x = []
        for node in node_list:
            feat = self.extract_graph_features(node, depth=1)
            vec = [
                feat.get('degree_centrality', 0),
                feat.get('pagerank', 0),
                feat.get('betweenness', 0),
                feat.get('clustering_coefficient', 0),
                1 if self.G.nodes[node].get('is_contract') else 0,
                self.G.nodes[node].get('risk_score', 0)
            ]
            x.append(vec)
            
        x = torch.tensor(x, dtype=torch.float)
        
        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr, num_nodes=len(node_list))