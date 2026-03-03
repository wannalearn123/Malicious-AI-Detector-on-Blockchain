┌────────────────────────────────────────────────────────────────┐
│                    ☁️ GOOGLE COLAB (TRAINING)                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ 📓 notebooks/train_on_colab.ipynb                             │
│    ├─ Cell 1: Install dependencies                            │
│    ├─ Cell 2: Mount Drive & load project                      │
│    ├─ Cell 3: Generate synthetic data                         │
│    ├─ Cell 4: Train models (GPU)                              │
│    ├─ Cell 5: Evaluate & save                                 │
│    └─ Cell 6: Upload to Drive                                 │
│                                                                │
│ 📜 scripts/train_model.py                                     │
│    ├─ train_gnn_colab() → GPU training                        │
│    ├─ train_anomaly_detector_colab()                          │
│    ├─ train_xgboost_colab()                                   │
│    └─ upload_to_drive()                                       │
│                                                                │
│ 📜 scripts/pre_data.py                                        │
│    ├─ BlockchainGraphDataset → PyG graphs                     │
│    ├─ prepare_training_data() → Generate data                 │
│    └─ extract_features_batch() → Feature engineering          │
│                                                                │
│ 📜 src/data/synthetic_agents.py                               │
│    ├─ MaliciousAIAgentSimulator → Malicious data             │
│    └─ BenignAgentSimulator → Normal data                      │
│                                                                │
│ 📜 src/models/light_gnn.py                                    │
│    ├─ LightweightGNN → Model architecture                     │
│    └─ CPUOptimizedTrainer → Training logic                    │
│                                                                │
│ 📜 src/models/anomaly_detection.py                            │
│    ├─ MultiModalAnomalyDetector                               │
│    └─ XGBoostEnsemble                                         │
│                                                                │
│ 📜 src/features/opcode_parser.py                              │
│    └─ OpcodeAnalyzer → Extract opcode features                │
│                                                                │
│ 📜 src/features/graph_builder.py                              │
│    └─ TransactionGraphBuilder → Build NetworkX graphs         │
│                                                                │
│ 📂 data/ (Generated)                                          │
│    ├─ raw/transactions.csv (~500MB)                           │
│    └─ processed/                                              │
│       ├─ train_features.csv (~200MB)                          │
│       ├─ val_features.csv (~50MB)                             │
│       └─ graphs/ (~1GB, 1000+ .pt files)                      │
│                                                                │
│ 📂 models/checkpoints/ (Output)                               │
│    ├─ gnn_model.pt (~10MB)                                    │
│    ├─ anomaly_detector.joblib (~3MB)                          │
│    └─ xgb_model.json (~2MB)                                   │
│                                                                │
│ ⏱️ Training Time: 45-60 minutes                               │
│ 💾 RAM Usage: 10-15GB                                         │
│ 🎮 GPU: Tesla T4/P100 (required)                              │
│ 💰 Cost: FREE (Colab)                                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                            ↓
                    📥 DOWNLOAD MODELS
                    (Google Drive / HuggingFace)
                            ↓
┌────────────────────────────────────────────────────────────────┐
│              💻 LOCAL LAPTOP (INFERENCE & DEPLOYMENT)          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ 📜 scripts/download_models.py                                 │
│    └─ Download pre-trained models dari Drive                  │
│                                                                │
│ 📜 src/inference/predictor.py ⭐ NEW                          │
│    ├─ LightweightPredictor → Fast inference                   │
│    ├─ Lazy model loading                                      │
│    └─ Memory: ~200MB                                          │
│                                                                │
│ 📜 src/detection/engine.py ⭐ UPDATED                         │
│    ├─ MaliciousAgentDetector → Full analysis                  │
│    ├─ FastInferenceDetector → Rule-based only                 │
│    ├─ HybridDetector → Two-stage detection                    │
│    └─ Memory: ~500MB                                          │
│                                                                │
│ 📜 src/api/main.py                                            │
│    ├─ POST /analyze → Single transaction                      │
│    ├─ POST /batch-analyze → Multiple transactions             │
│    ├─ GET /alerts → Detection alerts                          │
│    ├─ GET /stats → System stats                               │
│    └─ Memory: ~300MB                                          │
│                                                                │
│ 📜 src/blockchain/collector.py                                │
│    ├─ EVMDataCollector → Fetch blockchain data                │
│    ├─ Async support                                           │
│    └─ Memory: ~200MB                                          │
│                                                                │
│ 📜 src/utils/monitoring.py                                    │
│    └─ PrometheusMetrics → Monitoring                          │
│                                                                │
│ 📂 models/checkpoints/ (Downloaded)                           │
│    ├─ gnn_model.pt                                            │
│    ├─ anomaly_detector.joblib                                 │
│    └─ xgb_model.json                                          │
│                                                                │
│ 📂 data/cache/ (Minimal)                                      │
│    └─ graph_cache.pkl (~50MB)                                 │
│                                                                │
│ 🐳 docker-compose.yaml                                        │
│    ├─ PostgreSQL (database)                                   │
│    ├─ Redis (cache)                                           │
│    ├─ Prometheus (metrics)                                    │
│    └─ Grafana (dashboard)                                     │
│                                                                │
│ ⚡ Inference Time: 50-100ms per transaction                   │
│ 💾 RAM Usage: 1-2GB (stable)                                  │
│ 🎮 GPU: Intel Iris (optional, minimal benefit)                │
│ 🔄 Uptime: 24/7                                               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
