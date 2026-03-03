from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
import os
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from src.detection.engine import MaliciousAgentDetector
from src.blockchain.collector import EVMDataCollector
from src.data.models import init_database, get_session, DetectionAlert, Transaction
from src.utils.monitoring import PrometheusMetrics

# Global instances
detector = None
collector = None
metrics = PrometheusMetrics()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global detector, collector
    
    # Startup
    db_url = os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/db')
    init_database(db_url)
    
    # Initialize detector
    session = get_session(db_url)
    detector = MaliciousAgentDetector(
        session,
        model_path='models/checkpoints',
        device='cpu'
    )
    
    # Initialize blockchain collector
    collector = EVMDataCollector(
        rpc_url=os.getenv('ETH_RPC_URL'),
        chain='ethereum'
    )
    
    # Start background monitoring
    asyncio.create_task(monitor_new_blocks())
    
    yield
    
    # Shutdown
    session.close()

app = FastAPI(
    title="Malicious AI Agent Detection API",
    description="Real-time detection of malicious AI agents on blockchain",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class TransactionAnalysisRequest(BaseModel):
    tx_hash: str
    chain: str = "ethereum"
    include_traces: bool = True

class RiskAssessmentResponse(BaseModel):
    tx_hash: str
    risk_score: float
    risk_level: str
    indicators: List[Dict]
    recommendation: str
    analysis_time_ms: float

class AlertQuery(BaseModel):
    severity: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 100

# Dependency
def get_db():
    db_url = os.getenv('DATABASE_URL')
    session = get_session(db_url)
    try:
        yield session
    finally:
        session.close()

@app.post("/analyze", response_model=RiskAssessmentResponse)
async def analyze_transaction(
    request: TransactionAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Analyze a specific transaction for malicious AI agent activity.
    """
    import time
    start_time = time.time()
    
    metrics.increment_counter('analysis_requests_total')
    
    try:
        # Update detector with new session
        detector.db = db
        
        async with collector:
            result = await detector.analyze_transaction(request.tx_hash, collector)
            
        analysis_time = (time.time() - start_time) * 1000
        
        metrics.observe_histogram('analysis_duration_seconds', analysis_time / 1000)
        
        return RiskAssessmentResponse(
            tx_hash=result['tx_hash'],
            risk_score=result['risk_score'],
            risk_level=result['risk_level'],
            indicators=result['indicators'],
            recommendation=result['recommendation'],
            analysis_time_ms=analysis_time
        )
        
    except Exception as e:
        metrics.increment_counter('analysis_errors_total')
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve detection alerts with optional filtering.
    """
    query = db.query(DetectionAlert)
    
    if severity:
        query = query.filter(DetectionAlert.severity == severity)
        
    alerts = query.order_by(DetectionAlert.created_at.desc()).limit(limit).all()
    
    return [{
        'id': alert.id,
        'type': alert.alert_type,
        'severity': alert.severity,
        'confidence': alert.confidence,
        'description': alert.description,
        'involved_addresses': alert.involved_addresses,
        'created_at': alert.created_at.isoformat(),
        'resolved': alert.resolved
    } for alert in alerts]

@app.get("/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get detection system statistics.
    """
    total_alerts = db.query(DetectionAlert).count()
    unresolved_critical = db.query(DetectionAlert).filter(
        DetectionAlert.severity == 'CRITICAL',
        DetectionAlert.resolved == False
    ).count()
    
    recent_detections = db.query(DetectionAlert).filter(
        DetectionAlert.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).count()
    
    return {
        'total_alerts': total_alerts,
        'unresolved_critical': unresolved_critical,
        'detections_24h': recent_detections,
        'system_status': 'operational',
        'model_version': '1.0.0'
    }

@app.post("/webhook/block")
async def receive_block_webhook(block_data: Dict, background_tasks: BackgroundTasks):
    """
    Receive webhook from blockchain node for new blocks.
    """
    block_number = block_data.get('block_number')
    tx_count = len(block_data.get('transactions', []))
    
    logger.info(f"Received block {block_number} with {tx_count} transactions")
    
    # Queue for analysis
    for tx in block_data.get('transactions', []):
        background_tasks.add_task(analyze_async, tx['hash'])
        
    return {'status': 'queued', 'transactions': tx_count}

async def analyze_async(tx_hash: str):
    """Background task for transaction analysis."""
    try:
        async with collector:
            await detector.analyze_transaction(tx_hash, collector)
    except Exception as e:
        logger.error(f"Background analysis failed for {tx_hash}: {e}")

async def monitor_new_blocks():
    """Background task to monitor new blocks."""
    while True:
        try:
            # This would connect to WebSocket or poll for new blocks
            await asyncio.sleep(12)  # ~Ethereum block time
        except Exception as e:
            logger.error(f"Block monitoring error: {e}")
            await asyncio.sleep(5)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'detector_loaded': detector is not None,
        'collector_loaded': collector is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)