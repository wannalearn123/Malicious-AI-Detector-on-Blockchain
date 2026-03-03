import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
import torch
import numpy as np

from src.detection.engine import MaliciousAgentDetector
from src.models.gnn_model import MaliciousAgentGNN

@pytest.fixture
def mock_db():
    session = Mock()
    return session

@pytest.fixture
def detector(mock_db):
    return MaliciousAgentDetector(mock_db, device='cpu')

@pytest.mark.asyncio
async def test_analyze_transaction(detector):
    # Mock collector
    collector = AsyncMock()
    collector.async_w3.eth.get_transaction.return_value = {
        'hash': b'0x123',
        'from': '0xabc',
        'to': '0xdef',
        'value': 1000,
        'gas': 21000,
        'input': '0x',
        'blockNumber': 1000000
    }
    collector.async_w3.eth.get_transaction_receipt.return_value = {
        'gasUsed': 21000,
        'status': 1,
        'logs': []
    }
    collector.async_w3.eth.get_block.return_value = {
        'timestamp': 1234567890
    }
    collector.get_transaction_trace.return_value = []
    collector.get_opcode_trace.return_value = {'opcodes': []}
    
    result = await detector.analyze_transaction('0x123', collector)
    
    assert 'risk_score' in result
    assert 'risk_level' in result
    assert 0 <= result['risk_score'] <= 1

def test_opcode_analyzer():
    from src.features.opcode_parser import OpcodeAnalyzer
    
    analyzer = OpcodeAnalyzer()
    bytecode = "0x608060405234801561001057600080fd5b50"  # Simple contract bytecode
    
    opcodes = analyzer.parse_bytecode(bytecode)
    assert len(opcodes) > 0
    
    features = analyzer.extract_features(opcodes)
    assert 'entropy' in features
    assert 'total_opcodes' in features

def test_gnn_forward():
    from torch_geometric.data import Data
    
    model = MaliciousAgentGNN(in_channels=10)
    
    # Create dummy data
    x = torch.randn(5, 10)
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
    data = Data(x=x, edge_index=edge_index)
    
    out, anomaly = model(data)
    
    assert out.shape == (1, 2)  # Binary classification
    assert anomaly.shape == (5, 1)  # Node-level anomaly scores

if __name__ == "__main__":
    pytest.main([__file__])import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
import torch
import numpy as np

from src.detection.engine import MaliciousAgentDetector
from src.models.gnn_model import MaliciousAgentGNN

@pytest.fixture
def mock_db():
    session = Mock()
    return session

@pytest.fixture
def detector(mock_db):
    return MaliciousAgentDetector(mock_db, device='cpu')

@pytest.mark.asyncio
async def test_analyze_transaction(detector):
    # Mock collector
    collector = AsyncMock()
    collector.async_w3.eth.get_transaction.return_value = {
        'hash': b'0x123',
        'from': '0xabc',
        'to': '0xdef',
        'value': 1000,
        'gas': 21000,
        'input': '0x',
        'blockNumber': 1000000
    }
    collector.async_w3.eth.get_transaction_receipt.return_value = {
        'gasUsed': 21000,
        'status': 1,
        'logs': []
    }
    collector.async_w3.eth.get_block.return_value = {
        'timestamp': 1234567890
    }
    collector.get_transaction_trace.return_value = []
    collector.get_opcode_trace.return_value = {'opcodes': []}
    
    result = await detector.analyze_transaction('0x123', collector)
    
    assert 'risk_score' in result
    assert 'risk_level' in result
    assert 0 <= result['risk_score'] <= 1

def test_opcode_analyzer():
    from src.features.opcode_parser import OpcodeAnalyzer
    
    analyzer = OpcodeAnalyzer()
    bytecode = "0x608060405234801561001057600080fd5b50"  # Simple contract bytecode
    
    opcodes = analyzer.parse_bytecode(bytecode)
    assert len(opcodes) > 0
    
    features = analyzer.extract_features(opcodes)
    assert 'entropy' in features
    assert 'total_opcodes' in features

def test_gnn_forward():
    from torch_geometric.data import Data
    
    model = MaliciousAgentGNN(in_channels=10)
    
    # Create dummy data
    x = torch.randn(5, 10)
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
    data = Data(x=x, edge_index=edge_index)
    
    out, anomaly = model(data)
    
    assert out.shape == (1, 2)  # Binary classification
    assert anomaly.shape == (5, 1)  # Node-level anomaly scores

if __name__ == "__main__":
    pytest.main([__file__])