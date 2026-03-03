# scripts/train_model.py
"""
Training script untuk Google Colab.
Setelah training, upload models ke Google Drive atau HuggingFace.
"""
import torch
import torch.nn as nn
from torch_geometric.data import DataLoader
import numpy as np
import pandas as pd
import xgboost as xgb
import os
import yaml
from tqdm import tqdm
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

from src.models.light_gnn import LightweightGNN, CPUOptimizedTrainer
from src.models.anomaly_detection import MultiModalAnomalyDetector, XGBoostEnsemble

def get_device():
    """Auto-detect best device."""
    if torch.cuda.is_available():
        print(f"✅ CUDA available: {torch.cuda.get_device_name(0)}")
        return 'cuda'
    return 'cpu'

def train_gnn_colab(config: dict, device: str = 'cuda'):
    """Train GNN di Colab dengan GPU."""
    from scripts.pre_data import BlockchainGraphDataset
    
    print(f"🚀 Training GNN on {device}...")
    dataset = BlockchainGraphDataset(root='data/processed')
    
    # Batch size besar untuk GPU
    batch_size = config.get('batch_size', 64) if device == 'cuda' else 16
    
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)
    
    model = LightweightGNN(in_channels=dataset.num_features).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.get('learning_rate', 0.001))
    
    best_val_acc = 0
    history = {'train_loss': [], 'val_loss': [], 'val_acc': []}
    
    for epoch in range(config.get('epochs', 100)):
        # Train
        model.train()
        total_loss = 0
        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            out, _ = model(batch)
            loss = F.cross_entropy(out, batch.y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        # Validate
        model.eval()
        correct = total = 0
        val_loss = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = batch.to(device)
                out, _ = model(batch)
                val_loss += F.cross_entropy(out, batch.y).item()
                pred = out.argmax(dim=1)
                correct += (pred == batch.y).sum().item()
                total += batch.y.size(0)
        
        train_loss = total_loss / len(train_loader)
        val_loss = val_loss / len(val_loader)
        val_acc = correct / total
        
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        
        if epoch % 5 == 0:
            print(f"Epoch {epoch}: Loss={train_loss:.4f}, Val Acc={val_acc:.4f}")
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), 'models/checkpoints/gnn_model.pt')
    
    print(f"✅ Best Val Accuracy: {best_val_acc:.4f}")
    return history, model

def train_anomaly_detector_colab():
    """Train anomaly detector."""
    print("🔍 Training Anomaly Detector...")
    df = pd.read_csv('data/processed/train_features.csv')
    X = df[df['label'] == 0].drop('label', axis=1).values
    
    detector = MultiModalAnomalyDetector()
    detector.fit(X, fit_pca=True)
    detector.save('models/checkpoints/anomaly_detector.joblib')
    print(f"✅ Trained on {len(X)} samples")
    return detector

def train_xgboost_colab():
    """Train XGBoost."""
    print("🌲 Training XGBoost...")
    train = pd.read_csv('data/processed/train_features.csv')
    val = pd.read_csv('data/processed/val_features.csv')
    
    X_train, y_train = train.drop('label', axis=1).values, train['label'].values
    X_val, y_val = val.drop('label', axis=1).values, val['label'].values
    
    ensemble = XGBoostEnsemble()
    ensemble.fit(X_train, y_train, eval_set=[(X_val, y_val)])
    
    result = ensemble.predict(X_val)
    auc = roc_auc_score(y_val, result['probability'])
    print(f"✅ Validation AUC: {auc:.4f}")
    
    ensemble.model.save_model('models/checkpoints/xgb_model.json')
    return ensemble

def upload_to_drive():
    """Upload models ke Google Drive."""
    try:
        from google.colab import drive
        drive.mount('/content/drive')
        
        import shutil
        shutil.copytree(
            'models/checkpoints',
            '/content/drive/MyDrive/malicious_ai_models',
            dirs_exist_ok=True
        )
        print("✅ Models uploaded to Google Drive")
    except:
        print("⚠️ Not in Colab, skipping Drive upload")

if __name__ == "__main__":
    device = get_device()
    
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)
    
    print("="*60)
    print("🎓 TRAINING ON GOOGLE COLAB")
    print("="*60)
    
    # Generate data
    from scripts.pre_data import prepare_training_data, extract_features_batch
    print("\n📊 Step 1: Generate Data")
    tx_df = prepare_training_data()
    
    print("\n🔧 Step 2: Extract Features")
    extract_features_batch(tx_df)
    
    print("\n🧠 Step 3: Train GNN")
    gnn_history, gnn_model = train_gnn_colab(config['models']['gnn'], device)
    
    print("\n🔍 Step 4: Train Anomaly Detector")
    anomaly_detector = train_anomaly_detector_colab()
    
    print("\n🌲 Step 5: Train XGBoost")
    xgb_model = train_xgboost_colab()
    
    print("\n☁️ Step 6: Upload to Drive")
    upload_to_drive()
    
    print("\n" + "="*60)
    print("✅ TRAINING COMPLETE!")
    print("📁 Download models from: /content/drive/MyDrive/malicious_ai_models")
    print("="*60)
