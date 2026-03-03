# src/api/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os

from src.detection.engine import MaliciousAgentDetector
from src.blockchain.collector import EVMDataCollector
from src.data.models import get_session, DetectionAlert

app = FastAPI(title="Malicious AI Detector API")

detector = None
collector = None

@app.on_event("startup")
async def startup():
    global detector, collector
    session = get_session(os.getenv('DATABASE_URL', 'sqlite:///./test.db'))
    detector = MaliciousAgentDetector(session, model_path='models/checkpoints')
    collector = EVMDataCollector(rpc_url=os.getenv('ETH_RPC_URL'), chain='ethereum')

class AnalyzeRequest(BaseModel):
    tx_hash: str

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        async with collector:
            result = await detector.analyze_transaction(req.tx_hash, collector)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts(limit: int = 100, db: Session = Depends(get_session)):
    alerts = db.query(DetectionAlert).order_by(DetectionAlert.created_at.desc()).limit(limit).all()
    return [{'id': a.id, 'type': a.alert_type, 'severity': a.severity, 'created_at': a.created_at} for a in alerts]

@app.get("/health")
async def health():
    return {'status': 'healthy', 'detector': detector is not None}
