# src/detection/engine.py
"""
Malicious AI Agent Detection Engine - Inference Mode.
Optimized untuk laptop 8GB RAM dengan Intel Iris GPU.
"""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np
import torch
import networkx as nx
from sqlalchemy.orm import Session

from src.blockchain.collector import EVMDataCollector
from src.features.opcode_parser import OpcodeAnalyzer
from src.features.graph_builder import TransactionGraphBuilder
from src.models.light_gnn import LightweightGNN
from src.models.anomaly_detection import MultiModalAnomalyDetector, XGBoostEnsemble
from src.data.models import Transaction, Wallet, DetectionAlert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MaliciousAgentDetector:
    """
    Lightweight detection engine untuk inference.
    Memory footprint: ~500MB (vs ~2GB full version).
    """
    
    def __init__(
        self,
        db_session: Session,
        model_path: Optional[str] = 'models/checkpoints',
        device: str = 'cpu'
    ):
        self.db = db_session
        self.device = device
        self.model_path = model_path
        
        # Feature extractors (lightweight)
        self.opcode_analyzer = OpcodeAnalyzer()
        self.graph_builder = TransactionGraphBuilder(db_session)
        
        # Models (lazy loading)
        self.gnn = None
        self.anomaly_detector = None
        self.meta_classifier = None
        
        # Cache untuk performance
        self._graph_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
    def load_models(self):
        """Lazy load models saat dibutuhkan."""
        if self.gnn is None:
            try:
                self.gnn = LightweightGNN(in_channels=10, num_classes=2)
                self.gnn.load_state_dict(
                    torch.load(f"{self.model_path}/gnn_model.pt", map_location=self.device)
                )
                self.gnn.eval()
                logger.info("✅ GNN loaded")
            except Exception as e:
                logger.warning(f"GNN not available: {e}")
        
        if self.anomaly_detector is None:
            try:
                self.anomaly_detector = MultiModalAnomalyDetector()
                self.anomaly_detector.load(f"{self.model_path}/anomaly_detector.joblib")
                logger.info("✅ Anomaly Detector loaded")
            except Exception as e:
                logger.warning(f"Anomaly detector not available: {e}")
        
        if self.meta_classifier is None:
            try:
                import xgboost as xgb
                self.meta_classifier = xgb.XGBClassifier()
                self.meta_classifier.load_model(f"{self.model_path}/xgb_model.json")
                logger.info("✅ XGBoost loaded")
            except Exception as e:
                logger.warning(f"XGBoost not available: {e}")
    
    async def analyze_transaction(self, tx_hash: str, collector: EVMDataCollector) -> Dict:
        """
        Main analysis function - optimized untuk low latency.
        Target: <100ms per transaction.
        """
        start_time = datetime.utcnow()
        
        # Fetch transaction data
        tx_data = await self._get_transaction_data(tx_hash, collector)
        
        # Parallel analysis (async)
        opcode_task = asyncio.create_task(self._analyze_opcodes_async(tx_data))
        graph_task = asyncio.create_task(self._analyze_graph_context_async(tx_data))
        temporal_task = asyncio.create_task(self._analyze_temporal_patterns_async(tx_data))
        
        # Wait for all
        opcode_data, graph_data, temporal_data = await asyncio.gather(
            opcode_task, graph_task, temporal_task
        )
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(opcode_data, graph_data, temporal_data)
        
        # Generate alert if high risk
        if risk_score['final_score'] > 0.7:
            await self._create_alert(tx_data, risk_score)
        
        analysis_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            'tx_hash': tx_hash,
            'risk_score': risk_score['final_score'],
            'risk_level': self._score_to_level(risk_score['final_score']),
            'indicators': risk_score['indicators'],
            'component_scores': risk_score['component_scores'],
            'recommendation': self._get_recommendation(risk_score['final_score']),
            'analysis_time_ms': analysis_time * 1000
        }
    
    async def _get_transaction_data(self, tx_hash: str, collector: EVMDataCollector) -> Dict:
        """Fetch minimal transaction data."""
        tx = await collector.async_w3.eth.get_transaction(tx_hash)
        receipt = await collector.async_w3.eth.get_transaction_receipt(tx_hash)
        
        # Opcode trace (optional, fallback jika tidak ada)
        try:
            opcode_trace = await collector.get_opcode_trace(tx_hash)
        except:
            opcode_trace = {'opcodes': []}
        
        block = await collector.async_w3.eth.get_block(tx.blockNumber)
        
        return {
            'transaction': dict(tx),
            'receipt': dict(receipt),
            'opcode_trace': opcode_trace,
            'timestamp': datetime.fromtimestamp(block.timestamp)
        }
    
    async def _analyze_opcodes_async(self, tx_data: Dict) -> Dict:
        """Analyze opcode patterns."""
        opcodes = []
        
        # Extract opcodes
        if tx_data['opcode_trace'].get('opcodes'):
            opcodes = [op['op'] for op in tx_data['opcode_trace']['opcodes']]
        elif tx_data['transaction'].get('input'):
            opcodes = self.opcode_analyzer.parse_bytecode(tx_data['transaction']['input'])
        
        features = self.opcode_analyzer.extract_features(opcodes)
        indicators = []
        
        # Rule-based detection
        if features.get('reentrancy_risk', 0) > 0:
            indicators.append({
                'type': 'REENTRANCY_PATTERN',
                'severity': 'HIGH' if features['reentrancy_risk'] > 2 else 'MEDIUM',
                'confidence': min(features['reentrancy_risk'] / 5, 1.0),
                'details': f"Detected {features['reentrancy_risk']} reentrancy patterns"
            })
        
        if features.get('timestamp_dependency', 0):
            indicators.append({
                'type': 'TIMESTAMP_DEPENDENCY',
                'severity': 'MEDIUM',
                'confidence': 0.8,
                'details': "Uses block.timestamp in critical logic"
            })
        
        if features.get('tx_origin_usage', 0) > 0:
            indicators.append({
                'type': 'TX_ORIGIN_USAGE',
                'severity': 'HIGH',
                'confidence': 0.9,
                'details': "tx.origin usage detected (phishing risk)"
            })
        
        # AI Agent signature
        if features.get('entropy', 0) > 4.5 and features.get('external_call_ratio', 0) > 0.3:
            indicators.append({
                'type': 'AI_AGENT_BEHAVIOR',
                'severity': 'MEDIUM',
                'confidence': 0.7,
                'details': "High complexity + extensive external calls (automated)"
            })
        
        return {'features': features, 'indicators': indicators}
    
    async def _analyze_graph_context_async(self, tx_data: Dict) -> Dict:
        """Analyze graph context dengan caching."""
        from_address = tx_data['transaction']['from']
        to_address = tx_data['transaction'].get('to')
        
        # Check cache
        cache_key = f"graph_{datetime.utcnow().strftime('%Y%m%d%H')}"
        if cache_key in self._graph_cache:
            G = self._graph_cache[cache_key]
        else:
            # Build graph (last 1 hour untuk memory efficiency)
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            G = self.graph_builder.build_transaction_graph(start_time, end_time)
            self._graph_cache = {cache_key: G}  # Replace old cache
        
        features = {}
        indicators = []
        
        # Analyze sender
        if from_address in G:
            sender_feat = self.graph_builder.extract_graph_features(from_address)
            features['sender'] = sender_feat
            
            # Sybil detection
            if sender_feat.get('out_degree', 0) > 50 and sender_feat.get('in_degree', 0) < 5:
                indicators.append({
                    'type': 'SYBIL_BEHAVIOR',
                    'severity': 'HIGH',
                    'confidence': 0.85,
                    'details': f"High out-degree ({sender_feat['out_degree']}) suggests coordination"
                })
            
            # Mixing pattern
            if sender_feat.get('cycle_count', 0) > 3:
                indicators.append({
                    'type': 'MIXING_PATTERN',
                    'severity': 'HIGH',
                    'confidence': 0.8,
                    'details': f"Detected {sender_feat['cycle_count']} cycles (tumbling)"
                })
        
        # Analyze receiver
        if to_address and to_address in G and G.nodes[to_address].get('is_contract'):
            in_edges = list(G.in_edges(to_address, data=True))
            out_edges = list(G.out_edges(to_address, data=True))
            
            if in_edges and out_edges:
                total_in = sum(d['total_value'] for _, _, d in in_edges)
                total_out = sum(d['total_value'] for _, _, d in out_edges)
                
                if total_in > 0 and (total_out / total_in) < 0.1:
                    indicators.append({
                        'type': 'HONEYPOT_INDICATOR',
                        'severity': 'CRITICAL',
                        'confidence': 0.9,
                        'details': "Contract receives but rarely sends funds"
                    })
        
        # GNN prediction
        gnn_score = 0.0
        if self.gnn and len(G) > 0:
            try:
                self.load_models()
                data = self.graph_builder.to_pytorch_geometric()
                with torch.no_grad():
                    out, _ = self.gnn(data)
                    gnn_score = torch.softmax(out, dim=1)[0][1].item()
                    features['gnn_prediction'] = gnn_score
                    
                    if gnn_score > 0.8:
                        indicators.append({
                            'type': 'GNN_ANOMALY',
                            'severity': 'HIGH',
                            'confidence': gnn_score,
                            'details': "Graph structure matches malicious patterns"
                        })
            except Exception as e:
                logger.warning(f"GNN prediction failed: {e}")
        
        return {
            'features': features,
            'indicators': indicators,
            'graph_stats': {
                'nodes': len(G),
                'edges': G.size(),
                'density': nx.density(G) if len(G) > 0 else 0
            }
        }
    
    async def _analyze_temporal_patterns_async(self, tx_data: Dict) -> Dict:
        """Analyze temporal behavior."""
        from_address = tx_data['transaction']['from']
        
        # Query recent transactions (limit untuk memory)
        recent_txs = self.db.query(Transaction).filter(
            Transaction.from_address == from_address,
            Transaction.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).order_by(Transaction.timestamp).limit(100).all()
        
        features = {}
        indicators = []
        
        if len(recent_txs) > 1:
            timestamps = [tx.timestamp for tx in recent_txs]
            time_deltas = [(timestamps[i] - timestamps[i-1]).total_seconds() 
                          for i in range(1, len(timestamps))]
            
            if time_deltas:
                features['avg_time_delta'] = np.mean(time_deltas)
                features['std_time_delta'] = np.std(time_deltas)
                features['min_time_delta'] = np.min(time_deltas)
                
                # Bot detection: regular intervals
                if features['std_time_delta'] < 1.0 and len(recent_txs) > 10:
                    indicators.append({
                        'type': 'AUTOMATED_TIMING',
                        'severity': 'MEDIUM',
                        'confidence': 0.75,
                        'details': f"Regular timing (std: {features['std_time_delta']:.2f}s)"
                    })
                
                # High frequency
                if features['min_time_delta'] < 1.0:
                    indicators.append({
                        'type': 'HIGH_FREQUENCY',
                        'severity': 'LOW',
                        'confidence': 0.6,
                        'details': "Sub-second intervals detected"
                    })
        
        features['tx_count_24h'] = len(recent_txs)
        
        return {'features': features, 'indicators': indicators}
    
    def _calculate_risk_score(self, opcode_data: Dict, graph_data: Dict, temporal_data: Dict) -> Dict:
        """Ensemble risk scoring."""
        indicators = []
        indicators.extend(opcode_data.get('indicators', []))
        indicators.extend(graph_data.get('indicators', []))
        indicators.extend(temporal_data.get('indicators', []))
        
        # Component scores
        opcode_score = min(
            len([i for i in opcode_data.get('indicators', []) 
                 if i['severity'] in ['HIGH', 'CRITICAL']]) / 3, 1.0
        )
        
        graph_score = 0.0
        if graph_data.get('features', {}).get('gnn_prediction'):
            graph_score = graph_data['features']['gnn_prediction']
        elif graph_data.get('features', {}).get('sender', {}).get('pagerank'):
            graph_score = graph_data['features']['sender']['pagerank']
        
        temporal_score = 0.5 if any(
            i['type'] == 'AUTOMATED_TIMING' for i in temporal_data.get('indicators', [])
        ) else 0.0
        
        # Weighted ensemble
        final_score = 0.4 * opcode_score + 0.4 * graph_score + 0.2 * temporal_score
        
        # Boost if multiple high-confidence indicators
        high_conf = sum(1 for i in indicators if i.get('confidence', 0) > 0.8)
        if high_conf >= 2:
            final_score = min(final_score * 1.2, 1.0)
        
        # ML ensemble (if available)
        if self.meta_classifier:
            try:
                self.load_models()
                meta_features = np.array([[
                    opcode_score, graph_score, temporal_score,
                    opcode_data.get('features', {}).get('entropy', 0),
                    opcode_data.get('features', {}).get('external_call_ratio', 0)
                ]])
                ml_score = self.meta_classifier.predict_proba(meta_features)[0][1]
                final_score = 0.6 * final_score + 0.4 * ml_score
            except Exception as e:
                logger.warning(f"ML ensemble failed: {e}")
        
        return {
            'final_score': float(final_score),
            'component_scores': {
                'opcode': float(opcode_score),
                'graph': float(graph_score),
                'temporal': float(temporal_score)
            },
            'indicators': indicators,
            'indicator_count': len(indicators)
        }
    
    def _score_to_level(self, score: float) -> str:
        """Convert score to risk level."""
        if score >= 0.9: return "CRITICAL"
        elif score >= 0.7: return "HIGH"
        elif score >= 0.4: return "MEDIUM"
        elif score >= 0.2: return "LOW"
        return "MINIMAL"
    
    def _get_recommendation(self, score: float) -> str:
        """Get action recommendation."""
        if score >= 0.9:
            return "BLOCK_IMMEDIATELY: Quarantine addresses and alert security team"
        elif score >= 0.7:
            return "REVIEW_REQUIRED: Manual investigation needed"
        elif score >= 0.4:
            return "MONITOR_CLOSELY: Enhanced monitoring for 24 hours"
        elif score >= 0.2:
            return "STANDARD_MONITORING: Normal risk protocols"
        return "NO_ACTION: Standard processing"
    
    async def _create_alert(self, tx_data: Dict, risk_score: Dict):
        """Create alert in database."""
        alert = DetectionAlert(
            alert_type='MALICIOUS_AI_AGENT' if any(
                i['type'] == 'AI_AGENT_BEHAVIOR' for i in risk_score['indicators']
            ) else 'SUSPICIOUS_TRANSACTION',
            severity=self._score_to_level(risk_score['final_score']),
            confidence=max((i.get('confidence', 0) for i in risk_score['indicators']), default=0.5),
            description=f"Risk: {risk_score['final_score']:.2f}. Indicators: {len(risk_score['indicators'])}",
            involved_addresses=[
                tx_data['transaction']['from'],
                tx_data['transaction'].get('to')
            ],
            evidence={
                'indicators': risk_score['indicators'],
                'component_scores': risk_score['component_scores']
            }
        )
        
        self.db.add(alert)
        self.db.commit()
        logger.warning(f"⚠️ Alert created: {alert.alert_type} - Score {risk_score['final_score']:.2f}")
    
    def batch_analyze(self, tx_hashes: List[str], collector: EVMDataCollector) -> List[Dict]:
        """
        Batch analysis untuk multiple transactions.
        Memory-efficient dengan streaming.
        """
        results = []
        for tx_hash in tx_hashes:
            try:
                result = asyncio.run(self.analyze_transaction(tx_hash, collector))
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze {tx_hash}: {e}")
                results.append({'tx_hash': tx_hash, 'error': str(e)})
        
        return results
    
    def clear_cache(self):
        """Clear graph cache untuk free memory."""
        self._graph_cache = {}
        logger.info("🧹 Cache cleared")

class FastInferenceDetector:
    """
    Ultra-lightweight detector untuk high-throughput inference.
    Memory: ~100MB, Latency: <20ms.
    Trade-off: Hanya rule-based, no ML models.
    """
    
    def __init__(self):
        self.opcode_analyzer = OpcodeAnalyzer()
        self.rule_weights = {
            'REENTRANCY_PATTERN': 0.9,
            'TX_ORIGIN_USAGE': 0.85,
            'TIMESTAMP_DEPENDENCY': 0.6,
            'HIGH_FREQUENCY': 0.5,
            'AUTOMATED_TIMING': 0.7
        }
    
    def quick_analyze(self, tx_data: Dict) -> Dict:
        """
        Fast rule-based analysis tanpa ML.
        Use case: Pre-filtering sebelum full analysis.
        """
        opcodes = self.opcode_analyzer.parse_bytecode(
            tx_data.get('input', '0x')
        )
        features = self.opcode_analyzer.extract_features(opcodes)
        
        risk_score = 0.0
        indicators = []
        
        # Rule-based scoring
        if features.get('reentrancy_risk', 0) > 0:
            risk_score += self.rule_weights['REENTRANCY_PATTERN']
            indicators.append('REENTRANCY_PATTERN')
        
        if features.get('tx_origin_usage', 0) > 0:
            risk_score += self.rule_weights['TX_ORIGIN_USAGE']
            indicators.append('TX_ORIGIN_USAGE')
        
        if features.get('timestamp_dependency', 0):
            risk_score += self.rule_weights['TIMESTAMP_DEPENDENCY']
            indicators.append('TIMESTAMP_DEPENDENCY')
        
        # Normalize
        risk_score = min(risk_score, 1.0)
        
        return {
            'risk_score': risk_score,
            'risk_level': 'HIGH' if risk_score > 0.7 else 'MEDIUM' if risk_score > 0.4 else 'LOW',
            'indicators': indicators,
            'fast_mode': True
        }

class HybridDetector:
    """
    Hybrid: Fast pre-filter + Full analysis untuk high-risk.
    Optimal untuk production dengan traffic tinggi.
    """
    
    def __init__(self, db_session: Session, model_path: str = 'models/checkpoints'):
        self.fast_detector = FastInferenceDetector()
        self.full_detector = MaliciousAgentDetector(db_session, model_path)
    
    async def analyze(self, tx_hash: str, collector: EVMDataCollector) -> Dict:
        """
        Two-stage detection:
        1. Fast pre-filter (rule-based, <20ms)
        2. Full analysis jika suspicious (ML-based, <100ms)
        """
        # Stage 1: Quick check
        tx = await collector.async_w3.eth.get_transaction(tx_hash)
        quick_result = self.fast_detector.quick_analyze({'input': tx.get('input', '0x')})
        
        # Stage 2: Full analysis jika suspicious
        if quick_result['risk_score'] > 0.3:
            return await self.full_detector.analyze_transaction(tx_hash, collector)
        
        # Low risk: return quick result
        return {
            'tx_hash': tx_hash,
            'risk_score': quick_result['risk_score'],
            'risk_level': quick_result['risk_level'],
            'indicators': quick_result['indicators'],
            'fast_mode': True,
            'recommendation': 'NO_ACTION: Low risk detected'
        }
