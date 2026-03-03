"""
Streaming dataset yang tidak load semua data ke RAM.
Menggunakan generator pattern untuk 8GB RAM.
"""

import sqlite3
import torch
from torch_geometric.data import Data
from typing import Generator
import numpy as np

class StreamingGraphDataset:
    """
    Dataset yang stream dari database, tidak load semua ke memory.
    Cocok untuk laptop 8GB RAM.
    """
    
    def __init__(self, db_path: str, batch_size: int = 32):
        self.db_path = db_path
        self.batch_size = batch_size
        self.conn = sqlite3.connect(db_path)
        
    def __del__(self):
        self.conn.close()
        
    def stream_batches(self, query_filter: str = "") -> Generator:
        """
        Yield batch demi batch, tidak load semua data.
        """
        cursor = self.conn.cursor()
        
        # Query dengan pagination
        offset = 0
        while True:
            query = f"""
            SELECT * FROM transactions 
            {query_filter}
            LIMIT {self.batch_size} OFFSET {offset}
            """
            
            rows = cursor.execute(query).fetchall()
            if not rows:
                break
                
            # Convert ke PyG Data objects
            batch_data = self._rows_to_data(rows)
            yield batch_data
            
            offset += self.batch_size
            
            # Force garbage collection setiap batch
            import gc
            gc.collect()
            
    def _rows_to_data(self, rows) -> list:
        """Convert SQL rows ke PyG Data."""
        data_list = []
        
        for row in rows:
            # Extract features dari row
            # ... feature extraction logic ...
            
            x = torch.tensor(features, dtype=torch.float)
            edge_index = torch.tensor(edges, dtype=torch.long)
            y = torch.tensor([label], dtype=torch.long)
            
            data_list.append(Data(x=x, edge_index=edge_index, y=y))
            
        return data_list

class IncrementalGraphBuilder:
    """
    Build graph secara incremental, tidak menyimpan seluruh graph di memory.
    """
    
    def __init__(self, max_nodes_in_memory: int = 500):
        self.max_nodes = max_nodes_in_memory
        self.node_cache = {}
        self.edge_buffer = []
        
    def add_transaction(self, tx: dict):
        """Add transaction dengan eviction policy."""
        # Tambah node dengan LRU eviction
        for addr in [tx['from'], tx['to']]:
            if addr not in self.node_cache:
                if len(self.node_cache) >= self.max_nodes:
                    # Remove oldest
                    oldest = min(self.node_cache, key=self.node_cache.get)
                    del self.node_cache[oldest]
                self.node_cache[addr] = tx['timestamp']
                
        # Buffer edges
        self.edge_buffer.append((tx['from'], tx['to'], tx['value']))
        
        # Flush ke disk jika buffer penuh
        if len(self.edge_buffer) > 1000:
            self._flush_edges()
            
    def _flush_edges(self):
        """Simpan edges ke SQLite, kosongkan buffer."""
        # ... implementasi flush ke database ...
        self.edge_buffer = []