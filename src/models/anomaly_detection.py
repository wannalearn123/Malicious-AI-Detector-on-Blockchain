import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import xgboost as xgb
from typing import List, Dict, Tuple, Optional
import joblib

class MultiModalAnomalyDetector:
    """
    Ensemble anomaly detection combining multiple algorithms.
    """
    
    def __init__(self):
        self.isolation_forest = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
            n_jobs=-1
        )
        self.dbscan = DBSCAN(eps=0.5, min_samples=5)
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=0.95)  # Keep 95% variance
        
    def fit(self, X: np.ndarray, fit_pca: bool = True):
        """Fit models on training data (should be mostly normal)."""
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Optional dimensionality reduction
        if fit_pca:
            X_scaled = self.pca.fit_transform(X_scaled)
            
        # Fit isolation forest
        self.isolation_forest.fit(X_scaled)
        
        return self
        
    def predict(self, X: np.ndarray) -> Dict:
        """
        Predict anomaly scores using multiple methods.
        Returns ensemble score.
        """
        X_scaled = self.scaler.transform(X)
        if hasattr(self.pca, 'components_'):
            X_scaled = self.pca.transform(X_scaled)
            
        # Isolation Forest score (negative = anomaly)
        iso_scores = self.isolation_forest.decision_function(X_scaled)
        iso_anomaly = self.isolation_forest.predict(X_scaled)  # -1 for anomaly
        
        # DBSCAN clustering (noise points = anomalies)
        dbscan_labels = self.dbscan.fit_predict(X_scaled)
        dbscan_anomaly = (dbscan_labels == -1).astype(int)
        
        # Combine scores (weighted average)
        # Normalize scores to [0, 1] range
        iso_norm = 1 - (iso_scores + 0.5)  # Transform to anomaly probability
        
        ensemble_score = 0.7 * iso_norm + 0.3 * dbscan_anomaly
        
        return {
            'ensemble_score': ensemble_score,
            'isolation_forest_score': iso_norm,
            'dbscan_label': dbscan_labels,
            'is_anomaly': (ensemble_score > 0.6).astype(int),
            'confidence': np.abs(ensemble_score - 0.5) * 2  # Distance from decision boundary
        }
        
    def save(self, path: str):
        joblib.dump({
            'isolation_forest': self.isolation_forest,
            'scaler': self.scaler,
            'pca': self.pca
        }, path)
        
    def load(self, path: str):
        data = joblib.load(path)
        self.isolation_forest = data['isolation_forest']
        self.scaler = data['scaler']
        self.pca = data['pca']

class XGBoostEnsemble:
    """
    XGBoost ensemble for combining GNN and anomaly detector outputs.
    """
    
    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {
            'objective': 'binary:logistic',
            'eval_metric': ['auc', 'logloss'],
            'max_depth': 6,
            'learning_rate': 0.1,
            'n_estimators': 200,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42
        }
        self.model = xgb.XGBClassifier(**self.params)
        self.feature_importance = None
        
    def fit(self, X: np.ndarray, y: np.ndarray, eval_set: Optional[Tuple] = None):
        """Train XGBoost on meta-features."""
        self.model.fit(
            X, y,
            eval_set=eval_set,
            early_stopping_rounds=20,
            verbose=True
        )
        self.feature_importance = self.model.feature_importances_
        return self
        
    def predict(self, X: np.ndarray) -> Dict:
        """Predict with probability and confidence."""
        proba = self.model.predict_proba(X)[:, 1]
        pred = (proba > 0.5).astype(int)
        
        return {
            'prediction': pred,
            'probability': proba,
            'confidence': np.maximum(proba, 1 - proba),
            'is_malicious': pred
        }
        
    def get_feature_importance(self) -> Dict:
        """Return feature importance scores."""
        if self.feature_importance is None:
            return {}
        return dict(enumerate(self.feature_importance))