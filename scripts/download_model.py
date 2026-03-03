# scripts/download_models.py
"""
Download pre-trained models dari Google Drive atau HuggingFace.
Jalankan ini di local sebelum deployment.
"""
import os
import gdown
import requests
from tqdm import tqdm

def download_from_drive(file_id: str, output_path: str):
    """Download dari Google Drive."""
    url = f'https://drive.google.com/uc?id={file_id}'
    gdown.download(url, output_path, quiet=False)

def download_models(source: str = 'drive'):
    """
    Download all models.
    
    Args:
        source: 'drive' atau 'huggingface'
    """
    os.makedirs('models/checkpoints', exist_ok=True)
    
    if source == 'drive':
        # ✅ Ganti dengan file_id Anda setelah upload
        models = {
            'gnn_model.pt': 'YOUR_DRIVE_FILE_ID_1',
            'anomaly_detector.joblib': 'YOUR_DRIVE_FILE_ID_2',
            'xgb_model.json': 'YOUR_DRIVE_FILE_ID_3'
        }
        
        for filename, file_id in models.items():
            print(f"📥 Downloading {filename}...")
            download_from_drive(file_id, f'models/checkpoints/{filename}')
    
    elif source == 'huggingface':
        # Alternative: HuggingFace Hub
        from huggingface_hub import hf_hub_download
        repo_id = "YOUR_USERNAME/malicious-ai-detector"
        
        for filename in ['gnn_model.pt', 'anomaly_detector.joblib', 'xgb_model.json']:
            print(f"📥 Downloading {filename}...")
            hf_hub_download(repo_id=repo_id, filename=filename, local_dir='models/checkpoints')
    
    print("✅ All models downloaded!")

if __name__ == "__main__":
    # Download models sebelum deployment
    download_models(source='drive')
