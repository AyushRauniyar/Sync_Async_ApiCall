import os
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
from models import RequestMode, RequestStatus

# Database setup with environment-aware connection pooling
environment = os.getenv('ENVIRONMENT', 'development')

if environment == 'production':
    # Production: File-based SQLite
    SQLALCHEMY_DATABASE_URL = "sqlite:///./api_requests.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
else:
    # Development/demo: In-memory SQLite for better concurrency
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=False  # Disable SQL logging for performance
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class RequestRecord(Base):
    __tablename__ = "requests"
    
    request_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    mode = Column(Enum(RequestMode), nullable=False)
    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.PENDING)
    input_data = Column(Text, nullable=False)  # JSON string
    result = Column(Text, nullable=True)  # JSON string
    processing_time_ms = Column(Float, nullable=True)
    callback_url = Column(String, nullable=True)
    callback_attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()