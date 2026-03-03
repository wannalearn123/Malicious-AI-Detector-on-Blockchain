from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, BigInteger, Boolean, Text, ForeignKey, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Wallet(Base):
    __tablename__ = 'wallets'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    address = Column(String(42), unique=True, nullable=False, index=True)
    chain = Column(String(20), nullable=False, default='ethereum')
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime)
    total_transactions = Column(BigInteger, default=0)
    risk_score = Column(Float, default=0.0)
    is_contract = Column(Boolean, default=False)
    is_malicious = Column(Boolean, default=False)
    labels = Column(JSON, default=list)  # ["sybil", "bot", "ai_agent"]
    
    # Relationships
    transactions_from = relationship("Transaction", foreign_keys="Transaction.from_address", back_populates="sender")
    transactions_to = relationship("Transaction", foreign_keys="Transaction.to_address", back_populates="receiver")
    opcode_patterns = relationship("OpcodePattern", back_populates="wallet")
    
    __table_args__ = (
        Index('idx_wallet_risk', 'risk_score', 'last_active'),
        Index('idx_wallet_labels', 'labels', postgresql_using='gin'),
    )

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(String(66), primary_key=True)  # tx_hash
    block_number = Column(BigInteger, nullable=False, index=True)
    block_hash = Column(String(66))
    timestamp = Column(DateTime, nullable=False, index=True)
    from_address = Column(String(42), ForeignKey('wallets.address'), nullable=False, index=True)
    to_address = Column(String(42), ForeignKey('wallets.address'), nullable=False, index=True)
    value = Column(String(50))  # Wei as string to handle big numbers
    gas = Column(BigInteger)
    gas_price = Column(BigInteger)
    gas_used = Column(BigInteger)
    nonce = Column(Integer)
    input_data = Column(Text)
    status = Column(Integer)  # 1 success, 0 fail
    
    # Analysis fields
    anomaly_score = Column(Float)
    risk_flags = Column(JSON, default=list)
    ai_agent_probability = Column(Float, default=0.0)
    
    # Relationships
    sender = relationship("Wallet", foreign_keys=[from_address], back_populates="transactions_from")
    receiver = relationship("Wallet", foreign_keys=[to_address], back_populates="transactions_to")
    traces = relationship("TransactionTrace", back_populates="transaction")
    
    __table_args__ = (
        Index('idx_tx_time', 'timestamp'),
        Index('idx_tx_anomaly', 'anomaly_score'),
    )

class TransactionTrace(Base):
    __tablename__ = 'transaction_traces'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_hash = Column(String(66), ForeignKey('transactions.id'), nullable=False, index=True)
    trace_address = Column(JSON)  # Path in call tree
    subtraces = Column(Integer)
    trace_type = Column(String(20))  # call, create, suicide, reward
    call_type = Column(String(20))   # call, callcode, delegatecall, staticcall
    from_address = Column(String(42))
    to_address = Column(String(42))
    value = Column(String(50))
    gas = Column(BigInteger)
    gas_used = Column(BigInteger)
    input = Column(Text)
    output = Column(Text)
    error = Column(Text)
    
    # Opcode analysis
    opcode_sequence = Column(JSON)  # List of executed opcodes
    opcode_frequencies = Column(JSON)  # Dict of opcode counts
    entropy_score = Column(Float)
    
    transaction = relationship("Transaction", back_populates="traces")

class OpcodePattern(Base):
    __tablename__ = 'opcode_patterns'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_address = Column(String(42), ForeignKey('wallets.address'), nullable=False, index=True)
    pattern_type = Column(String(50))  # reentrancy, flash_loan, etc.
    confidence = Column(Float)
    evidence = Column(JSON)  # Supporting data
    detected_at = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship("Wallet", back_populates="opcode_patterns")

class GraphEdge(Base):
    __tablename__ = 'graph_edges'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(42), nullable=False, index=True)
    target = Column(String(42), nullable=False, index=True)
    edge_type = Column(String(20))  # transaction, call, token_transfer
    weight = Column(Float, default=1.0)
    timestamp = Column(DateTime, nullable=False)
    tx_hash = Column(String(66))
    value_eth = Column(Float)
    
    __table_args__ = (
        Index('idx_edge_nodes', 'source', 'target'),
        Index('idx_edge_time', 'timestamp'),
    )

class DetectionAlert(Base):
    __tablename__ = 'detection_alerts'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_type = Column(String(50))  # sybil, reentrancy, wash_trading, etc.
    severity = Column(String(20))  # low, medium, high, critical
    confidence = Column(Float)
    description = Column(Text)
    involved_addresses = Column(JSON)
    evidence = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)

# Database initialization
def init_database(database_url: str):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

def get_session(database_url: str):
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()