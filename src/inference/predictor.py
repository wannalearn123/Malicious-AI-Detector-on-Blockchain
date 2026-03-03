# src/inference/predictor.py
"""
Lightweight inference engine untuk local deployment.
Optimized untuk RAM 8GB, hanya load models saat dibutuhkan.
"""
import torch
import joblib
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class LightweightPredictor:
    """
    Inference-only predictor untuk local laptop.
    Memory footprint: ~200MB (vs ~2GB untuk full system).
    """
    
    def __init__(self, model_dir: str = 'models/checkpoints'):
        self.model_dir = model_dir
        self.gnn = None
        self.anomaly_detector = None
        self.xgb_model = None
        self.device = 'cpu'  # Force CPU untuk stability
        
    def load_models_lazy(self):
        """Lazy loading: load hanya saat dibutuhkan."""
        if self.gnn is None:
            from src.models.light_gnn import LightweightGNN
            self.gnn = LightweightGNN(in_channels=10)
            self.gnn.load_state_dict(torch.load(f'{self.model_dir}/gnn_model.pt', map_location='cpu'))
            self.gnn.eval()
            logger.info("✅ GNN loaded")
        
        if self.anomaly_detector is None:
            from src.models.anomaly_detection import MultiModalAnomalyDetector
            self.anomaly_detector = MultiModalAnomalyDetector()
            self.anomaly_detector.load(f'{self.model_dir}/anomaly_detector.joblib')
            logger.info("✅ Anomaly Detector loaded")
        
        if self.xgb_model is None:
            import xgboost as xgb
            self.xgb_model = xgb.XGBClassifier()
            self.xgb_model.load_model(f'{self.model_dir}/xgb_model.json')
            logger.info("✅ XGBoost loaded")
    
    @torch.no_grad()
    def predict_transaction(self, features: Dict) -> Dict:
        """
        Fast inference untuk single transaction.
        Input: feature dict dari opcode/graph analysis
        Output: risk score + indicators
        """
        self.load_models_lazy()
        
        # GNN prediction (jika ada graph data)
        gnn_score = 0.0
        if 'graph_data' in features:
            graph = features['graph_data']
            out, anomaly = self.gnn(graph)
            gnn_score = torch.softmax(out, dim=1)[0][1].item()
        
        # Anomaly detection
        feature_vec = self._extract_feature_vector(features)
        anomaly_result = self.anomaly_detector.predict(feature_vec.reshape(1, -1))
        anomaly_score = anomaly_result['ensemble_score'][0]
        
        # XGBoost meta-prediction
        meta_features = np.array([[gnn_score, anomaly_score] + feature_vec.tolist()[0]])
        xgb_result = self.xgb_model.predict_proba(meta_features)[0][1]
        
        # Final score (weighted)
        final_score = 0.4 * gnn_score + 0.3 * anomaly_score + 0.3 * xgb_result
        
        return {
            'risk_score': float(final_score),
            'risk_level': self._score_to_level(final_score),
            'component_scores': {'gnn': gnn_score, 'anomaly': anomaly_score, 'xgb': xgb_result}
        }
    
    def _extract_feature_vector(self, features: Dict) -> np.ndarray:
        """Extract minimal feature vector."""
        return np.array([[
            features.get('entropy', 0),
            features.get('external_call_ratio', 0),
            features.get('reentrancy_risk', 0),
            features.get('gas_used', 0) / 1e6
        ]])
    
    def _score_to_level(self, score: float) -> str:
        if score >= 0.9: return "CRITICAL"
        elif score >= 0.7: return "HIGH"
        elif score >= 0.4: return "MEDIUM"
        elif score >= 0.2: return "LOW"
        return "MINIMAL"
