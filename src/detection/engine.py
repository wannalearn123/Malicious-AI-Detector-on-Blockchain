# src/detection/engine.py
import logging
from typing import Dict
from datetime import datetime, timedelta
import numpy as np
import torch
import networkx as nx
from sqlalchemy.orm import Session

from src.blockchain.collector import EVMDataCollector
from src.features.opcode_parser import OpcodeAnalyzer
from src.features.graph_builder import TransactionGraphBuilder
from src.models.light_gnn import LightweightGNN
from src.models.anomaly_detection import MultiModalAnomalyDetector
from src.data.models import Transaction, DetectionAlert

logger = logging.getLogger(__name__)

class MaliciousAgentDetector:
    """Lightweight detection engine for inference."""
    
    def __init__(self, db_session: Session, model_path='models/checkpoints', device='cpu'):
        self.db = db_session
        self.device = device
        self.model_path = model_path
        
        self.opcode_analyzer = OpcodeAnalyzer()
        self.graph_builder = TransactionGraphBuilder(db_session)
        
        self.gnn = None
        self.anomaly_detector = None
        self._graph_cache = {}
    
    def load_models(self):
        """Lazy load models."""
        if self.gnn is None:
            self.gnn = LightweightGNN(in_channels=10)
            self.gnn.load_state_dict(torch.load(f"{self.model_path}/gnn_model.pt", map_location=self.device))
            self.gnn.eval()
        
        if self.anomaly_detector is None:
            self.anomaly_detector = MultiModalAnomalyDetector()
            self.anomaly_detector.load(f"{self.model_path}/anomaly_detector.joblib")
    
    async def analyze_transaction(self, tx_hash: str, collector: EVMDataCollector) -> Dict:
        """Analyze transaction."""
        tx_data = await self._get_tx_data(tx_hash, collector)
        
        opcode_result = self._analyze_opcodes(tx_data)
        graph_result = await self._analyze_graph(tx_data)
        temporal_result = self._analyze_temporal(tx_data)
        
        risk_score = self._calculate_risk(opcode_result, graph_result, temporal_result)
        
        if risk_score['score'] > 0.7:
            await self._create_alert(tx_data, risk_score)
        
        return {
            'tx_hash': tx_hash,
            'risk_score': risk_score['score'],
            'risk_level': self._score_to_level(risk_score['score']),
            'indicators': risk_score['indicators']
        }
    
    async def _get_tx_data(self, tx_hash: str, collector: EVMDataCollector) -> Dict:
        tx = await collector.async_w3.eth.get_transaction(tx_hash)
        receipt = await collector.async_w3.eth.get_transaction_receipt(tx_hash)
        block = await collector.async_w3.eth.get_block(tx.blockNumber)
        
        return {
            'transaction': dict(tx),
            'receipt': dict(receipt),
            'timestamp': datetime.fromtimestamp(block.timestamp)
        }
    
    def _analyze_opcodes(self, tx_data: Dict) -> Dict:
        opcodes = self.opcode_analyzer.parse_bytecode(tx_data['transaction'].get('input', '0x'))
        features = self.opcode_analyzer.extract_features(opcodes)
        
        indicators = []
        if features.get('reentrancy_risk', 0) > 0:
            indicators.append({'type': 'REENTRANCY', 'severity': 'HIGH', 'confidence': 0.8})
        if features.get('tx_origin_usage', 0) > 0:
            indicators.append({'type': 'TX_ORIGIN', 'severity': 'HIGH', 'confidence': 0.9})
        
        return {'features': features, 'indicators': indicators}
    
    async def _analyze_graph(self, tx_data: Dict) -> Dict:
        from_addr = tx_data['transaction']['from']
        
        cache_key = datetime.utcnow().strftime('%Y%m%d%H')
        if cache_key not in self._graph_cache:
            G = self.graph_builder.build_transaction_graph(
                datetime.utcnow() - timedelta(hours=1),
                datetime.utcnow()
            )
            self._graph_cache = {cache_key: G}
        else:
            G = self._graph_cache[cache_key]
        
        indicators = []
        if from_addr in G:
            feat = self.graph_builder.extract_graph_features(from_addr)
            if feat.get('out_degree', 0) > 50:
                indicators.append({'type': 'SYBIL', 'severity': 'HIGH', 'confidence': 0.85})
        
        return {'indicators': indicators}
    
    def _analyze_temporal(self, tx_data: Dict) -> Dict:
        from_addr = tx_data['transaction']['from']
        recent = self.db.query(Transaction).filter(
            Transaction.from_address == from_addr,
            Transaction.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).limit(100).all()
        
        indicators = []
        if len(recent) > 10:
            deltas = [(recent[i].timestamp - recent[i-1].timestamp).total_seconds() 
                     for i in range(1, len(recent))]
            if np.std(deltas) < 1.0:
                indicators.append({'type': 'BOT_TIMING', 'severity': 'MEDIUM', 'confidence': 0.75})
        
        return {'indicators': indicators}
    
    def _calculate_risk(self, opcode, graph, temporal) -> Dict:
        indicators = opcode['indicators'] + graph['indicators'] + temporal['indicators']
        
        score = min(len([i for i in indicators if i['severity'] in ['HIGH', 'CRITICAL']]) / 3, 1.0)
        
        return {'score': float(score), 'indicators': indicators}
    
    def _score_to_level(self, score: float) -> str:
        if score >= 0.9: return "CRITICAL"
        if score >= 0.7: return "HIGH"
        if score >= 0.4: return "MEDIUM"
        if score >= 0.2: return "LOW"
        return "MINIMAL"
    
    async def _create_alert(self, tx_data: Dict, risk_score: Dict):
        alert = DetectionAlert(
            alert_type='SUSPICIOUS_TRANSACTION',
            severity=self._score_to_level(risk_score['score']),
            confidence=max((i.get('confidence', 0) for i in risk_score['indicators']), default=0.5),
            description=f"Risk: {risk_score['score']:.2f}",
            involved_addresses=[tx_data['transaction']['from'], tx_data['transaction'].get('to')],
            evidence={'indicators': risk_score['indicators']}
        )
        self.db.add(alert)
        self.db.commit()
