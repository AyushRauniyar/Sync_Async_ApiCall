from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field
import uuid


class RequestMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"


class RequestStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CALLBACK_SENT = "callback_sent"
    CALLBACK_FAILED = "callback_failed"


class WorkRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="Input data for processing")
    complexity: int = Field(default=1, ge=1, le=10, description="Work complexity level (1-10)")


class AsyncWorkRequest(WorkRequest):
    callback_url: HttpUrl = Field(..., description="URL to send results to")


class WorkResponse(BaseModel):
    request_id: str
    result: Dict[str, Any]
    processing_time_ms: float
    timestamp: datetime


class AsyncAckResponse(BaseModel):
    request_id: str
    status: str = "accepted"
    message: str = "Request accepted for processing"


class RequestDetails(BaseModel):
    request_id: str
    mode: RequestMode
    status: RequestStatus
    input_data: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[float] = None
    callback_url: Optional[str] = None
    callback_attempts: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    version: str = "1.0.0"
    uptime_seconds: float