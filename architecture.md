┌─────────────────────────────────────────────────────────────────┐
│                    GOOGLE COLAB (TRAINING)                      │
│  GPU: Tesla T4/P100 | RAM: 12-25GB | Storage: 100GB            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📂 notebooks/                                                  │
│     └─ train_on_colab.ipynb ⭐ MAIN TRAINING NOTEBOOK          │
│                                                                 │
│  📂 scripts/                                                    │
│     ├─ train_model.py        ⭐ Training orchestrator          │
│     └─ pre_data.py           ⭐ Dataset preparation            │
│                                                                 │
│  📂 src/data/                                                   │
│     └─ synthetic_agents.py   ⭐ Data generation                │
│                                                                 │
│  📂 src/models/                                                 │
│     ├─ light_gnn.py          ⭐ Model architecture             │
│     └─ anomaly_detection.py  ⭐ Anomaly models                 │
│                                                                 │
│  📂 src/features/                                               │
│     ├─ opcode_parser.py      ⭐ Feature extraction             │
│     └─ graph_builder.py      ⭐ Graph construction             │
│                                                                 │
│  OUTPUT: models/checkpoints/ → Upload ke Drive/HuggingFace     │
│     ├─ gnn_model.pt          (5-20 MB)                         │
│     ├─ anomaly_detector.joblib (2-5 MB)                        │
│     └─ xgb_model.json        (1-3 MB)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓ Download Models
┌─────────────────────────────────────────────────────────────────┐
│              LOCAL LAPTOP (INFERENCE & DEPLOYMENT)              │
│  CPU: Intel Core | RAM: 8GB | GPU: Intel Iris                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📂 scripts/                                                    │
│     └─ download_models.py    ⭐ Download dari cloud            │
│                                                                 │
│  📂 src/inference/           ⭐ NEW FOLDER                      │
│     └─ predictor.py          ⭐ Lightweight inference engine   │
│                                                                 │
│  📂 src/api/                                                    │
│     └─ main.py               ⭐ FastAPI deployment             │
│                                                                 │
│  📂 src/detection/                                              │
│     └─ engine.py             ⭐ Detection logic (inference)    │
│                                                                 │
│  📂 src/blockchain/                                             │
│     └─ collector.py          ⭐ Real-time data collection      │
│                                                                 │
│  📂 src/utils/                                                  │
│     └─ monitoring.py         ⭐ Prometheus metrics             │
│                                                                 │
│  📂 models/checkpoints/      ⭐ Downloaded pre-trained models  │
│     ├─ gnn_model.pt                                            │
│     ├─ anomaly_detector.joblib                                 │
│     └─ xgb_model.json                                          │
│                                                                 │
│  📂 data/                    ⭐ Minimal data (cache only)      │
│     └─ cache/                                                  │
│                                                                 │
│  🐳 docker-compose.yaml      ⭐ Local deployment               │
│  🔧 .env                     ⭐ Local config                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
