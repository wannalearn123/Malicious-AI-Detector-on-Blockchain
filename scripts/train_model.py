# scripts/train_model.py
import torch
import torch.nn.functional as F
from torch_geometric.data import DataLoader
import pandas as pd
import xgboost as xgb
import os
import yaml
from sklearn.metrics import roc_auc_score

from src.models.light_gnn import LightweightGNN
from src.models.anomaly_detection import MultiModalAnomalyDetector, XGBoostEnsemble

def get_device():
    return 'cuda' if torch.cuda.is_available() else 'cpu'

def train_gnn_colab(config, device='cuda'):
    """Train GNN."""
    from scripts.pre_data import BlockchainGraphDataset
    
    dataset = BlockchainGraphDataset(root='data/processed')
    train_size = int(0.8 * len(dataset))
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, len(dataset) - train_size])
    
    train_loader = DataLoader(train_ds, batch_size=config.get('batch_size', 32), shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=config.get('batch_size', 32))
    
    model = LightweightGNN(in_channels=dataset.num_features).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.get('learning_rate', 0.001))
    
    best_acc = 0
    for epoch in range(config.get('epochs', 50)):
        # Train
        model.train()
        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            out, _ = model(batch)
            F.cross_entropy(out, batch.y).backward()
            optimizer.step()
        
        # Validate
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = batch.to(device)
                pred = model(batch)[0].argmax(dim=1)
                correct += (pred == batch.y).sum().item()
                total += batch.y.size(0)
        
        acc = correct / total
        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), 'models/checkpoints/gnn_model.pt')
        
        if epoch % 10 == 0:
            print(f"Epoch {epoch}: Acc={acc:.4f}")
    
    print(f"✅ Best Accuracy: {best_acc:.4f}")
    return model

def train_anomaly_detector_colab():
    """Train anomaly detector."""
    df = pd.read_csv('data/processed/train_features.csv')
    X = df[df['label'] == 0].drop('label', axis=1).values
    
    detector = MultiModalAnomalyDetector()
    detector.fit(X, fit_pca=True)
    detector.save('models/checkpoints/anomaly_detector.joblib')
    
    print(f"✅ Trained on {len(X)} samples")
    return detector

def train_xgboost_colab():
    """Train XGBoost."""
    train = pd.read_csv('data/processed/train_features.csv')
    val = pd.read_csv('data/processed/val_features.csv')
    
    X_train, y_train = train.drop('label', axis=1).values, train['label'].values
    X_val, y_val = val.drop('label', axis=1).values, val['label'].values
    
    model = xgb.XGBClassifier(max_depth=4, learning_rate=0.1, n_estimators=100, tree_method='hist')
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], early_stopping_rounds=10, verbose=False)
    
    auc = roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])
    model.save_model('models/checkpoints/xgb_model.json')
    
    print(f"✅ AUC: {auc:.4f}")
    return model

if __name__ == "__main__":
    device = get_device()
    
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)
    
    from scripts.pre_data import prepare_training_data, extract_features_batch
    
    print("📊 Generating data...")
    tx_df = prepare_training_data()
    
    print("🔧 Extracting features...")
    extract_features_batch(tx_df)
    
    print(f"🧠 Training GNN on {device}...")
    train_gnn_colab(config['models']['gnn'], device)
    
    print("🔍 Training Anomaly Detector...")
    train_anomaly_detector_colab()
    
    print("🌲 Training XGBoost...")
    train_xgboost_colab()
    
    print("✅ Training complete!")
