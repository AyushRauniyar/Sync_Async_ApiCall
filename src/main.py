import asyncio
import time
import uuid
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import (
    WorkRequest, AsyncWorkRequest, WorkResponse, AsyncAckResponse,
    RequestDetails, HealthResponse, RequestMode, RequestStatus
)
from services import RequestService, CallbackService
from work_processor import WorkProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting configuration
class RateLimiter:
    """Production-grade rate limiter with sliding window"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)  # IP -> deque of timestamps
        
    async def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed based on rate limits"""
        now = time.time()
        client_requests = self.requests[client_ip]
        
        # Remove old requests outside the window
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) >= self.max_requests:
            return False
        
        # Add current request
        client_requests.append(now)
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """Get rate limiting statistics"""
        now = time.time()
        active_ips = 0
        total_recent_requests = 0
        
        for ip, requests in self.requests.items():
            # Clean old requests
            while requests and requests[0] <= now - self.window_seconds:
                requests.popleft()
            
            if requests:
                active_ips += 1
                total_recent_requests += len(requests)
        
        return {
            "active_ips": active_ips,
            "total_recent_requests": total_recent_requests,
            "max_requests_per_window": self.max_requests,
            "window_seconds": self.window_seconds
        }

# Environment-aware rate limiter configuration
environment = os.getenv('ENVIRONMENT', 'development')
if environment == 'production':
    rate_limiter = RateLimiter(max_requests=50, window_seconds=60)  # Production limits
else:
    rate_limiter = RateLimiter(max_requests=1000, window_seconds=60)  # Development/demo limits

async def check_rate_limit(request: Request) -> None:
    """Dependency to check rate limits"""
    # Skip rate limiting in development/demo mode
    if environment != 'production':
        return
        
    client_ip = request.client.host if request.client else "unknown"
    
    if not await rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": rate_limiter.window_seconds
            }
        )

# Enhanced error handler
async def validation_exception_handler(request: Request, exc: HTTPException):
    """Custom error handler for better error responses"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url),
            "method": request.method
        }
    )

# App initialization
app = FastAPI(
    title="Sync vs Async API Demo - Production Ready",
    description="""
    Production-ready demonstration of synchronous and asynchronous API patterns under load.
    
    Features:
    - Rate limiting to prevent abuse
    - Enhanced input validation with security checks
    - Circuit breaker pattern for external callbacks
    - Comprehensive error handling and monitoring
    - Security measures against SSRF and injection attacks
    """,
    version="2.0.0"
)

# Add custom error handlers
app.add_exception_handler(HTTPException, validation_exception_handler)

# CORS middleware with more restrictive settings for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["Content-Type", "Authorization"],  # Specific headers
)

# Services
request_service = RequestService()
callback_service = CallbackService()

# App startup time for health check
app_start_time = time.time()


@app.post("/sync", response_model=WorkResponse)
async def sync_endpoint(
    request: WorkRequest,
    db: Session = Depends(get_db),
    _: None = Depends(check_rate_limit)
):
    """
    Synchronous endpoint that processes work and returns result immediately.
    
    Security Features:
    - Rate limiting per IP
    - Enhanced input validation
    - Request sanitization
    - Error logging and monitoring
    """
    # Enhanced input validation
    if not WorkProcessor.validate_input(request.data):
        logger.warning(f"Invalid input data received: {request.data}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Invalid input data",
                "message": "Input data failed validation checks",
                "code": "INVALID_INPUT"
            }
        )
    
    try:
        # Process request synchronously with enhanced logging
        start_time = time.time()
        logger.info(f"Processing sync request with complexity {request.complexity}")
        
        result = request_service.process_sync_request(
            db, request.data, request.complexity
        )
        
        processing_time = (time.time() - start_time) * 1000
        logger.info(f"Sync request completed in {processing_time:.2f}ms")
        
        return WorkResponse(**result)
        
    except ValueError as e:
        logger.error(f"Validation error in sync processing: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Invalid request parameters",
                "message": str(e),
                "code": "VALIDATION_ERROR"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in sync processing: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Internal processing error",
                "message": "An unexpected error occurred during processing",
                "code": "PROCESSING_ERROR"
            }
        )


@app.post("/async", response_model=AsyncAckResponse)
async def async_endpoint(
    request: AsyncWorkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(check_rate_limit)
):
    """
    Asynchronous endpoint that accepts request, returns quickly, 
    and later sends result to callback URL.
    
    Security Features:
    - Rate limiting per IP
    - SSRF protection for callback URLs
    - Enhanced input validation
    - Callback URL security checks
    - Request tracking and monitoring
    """
    # Enhanced input validation
    if not WorkProcessor.validate_input(request.data):
        logger.warning(f"Invalid input data received: {request.data}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Invalid input data",
                "message": "Input data failed validation checks",
                "code": "INVALID_INPUT"
            }
        )
    
    # Comprehensive callback URL validation for security
    callback_url_str = str(request.callback_url)
    
    # Basic URL format validation
    if not (callback_url_str.startswith('http://') or callback_url_str.startswith('https://')):
        logger.warning(f"Invalid callback URL scheme: {callback_url_str}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Invalid callback URL",
                "message": "Callback URL must use http or https scheme",
                "code": "INVALID_CALLBACK_URL"
            }
        )
    
    # Advanced security checks against SSRF attacks
    from urllib.parse import urlparse
    import ipaddress
    
    try:
        parsed = urlparse(callback_url_str)
        
        # Block dangerous schemes and protocols
        if parsed.scheme not in ['http', 'https']:
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "Invalid URL scheme",
                    "message": "Only HTTP and HTTPS schemes are allowed",
                    "code": "INVALID_SCHEME"
                }
            )
        
        # Environment-based security checks
        environment = os.getenv('ENVIRONMENT', 'development')
        
        if parsed.hostname:
            # Block internal/localhost addresses in production
            blocked_hosts = ['localhost', '127.0.0.1', '0.0.0.0', '::1', 'metadata.google.internal']
            
            if parsed.hostname.lower() in blocked_hosts and environment == 'production':
                logger.warning(f"Blocked callback to internal host: {parsed.hostname}")
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Callback URL not allowed",
                        "message": "Callbacks to localhost/internal hosts not allowed in production",
                        "code": "BLOCKED_HOST"
                    }
                )
            
            # Block private IP ranges
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                if (ip.is_private or ip.is_loopback) and environment == 'production':
                    logger.warning(f"Blocked callback to private IP: {ip}")
                    raise HTTPException(
                        status_code=400, 
                        detail={
                            "error": "Private IP not allowed",
                            "message": "Callbacks to private IP addresses not allowed in production",
                            "code": "PRIVATE_IP_BLOCKED"
                        }
                    )
            except ValueError:
                pass  # Not an IP address, hostname is OK
            
            # Block cloud metadata endpoints
            metadata_domains = [
                'metadata.google.internal',
                '169.254.169.254',  # AWS/GCP metadata
                'metadata.azure.com'
            ]
            
            if parsed.hostname.lower() in metadata_domains:
                logger.warning(f"Blocked callback to metadata endpoint: {parsed.hostname}")
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Metadata endpoint blocked",
                        "message": "Callbacks to cloud metadata endpoints are not allowed",
                        "code": "METADATA_BLOCKED"
                    }
                )
    
    except ValueError as e:
        logger.warning(f"URL parsing error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Malformed URL",
                "message": "The provided callback URL is malformed",
                "code": "MALFORMED_URL"
            }
        )
    
    try:
        # Create request record with enhanced tracking
        start_time = time.time()
        logger.info(f"Accepting async request with complexity {request.complexity}")
        
        request_id = request_service.create_request_record(
            db, RequestMode.ASYNC, request.data, callback_url_str
        )
        
        # Schedule background processing
        background_tasks.add_task(
            callback_service.process_async_callback,
            SessionLocal,  # Pass session factory
            request_id
        )
        
        accept_time = (time.time() - start_time) * 1000
        logger.info(f"Async request {request_id} accepted in {accept_time:.2f}ms")
        
        return AsyncAckResponse(
            request_id=request_id,
            status="accepted",
            message="Request accepted for processing. Callback will be sent when complete."
        )
        
    except ValueError as e:
        logger.error(f"Validation error in async processing: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Invalid request parameters",
                "message": str(e),
                "code": "VALIDATION_ERROR"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in async processing: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Request acceptance failed",
                "message": "An unexpected error occurred while accepting the request",
                "code": "ACCEPTANCE_ERROR"
            }
        )


@app.get("/requests", response_model=List[RequestDetails])
async def list_requests(
    mode: Optional[RequestMode] = Query(None, description="Filter by request mode"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of requests to return"),
    db: Session = Depends(get_db)
):
    """
    List recent requests with optional filtering by mode.
    """
    try:
        requests = request_service.list_requests(db, mode, limit)
        return requests
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve requests: {str(e)}")


@app.get("/requests/{request_id}", response_model=RequestDetails)
async def get_request_details(
    request_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific request.
    """
    try:
        request_details = request_service.get_request_details(db, request_id)
        
        if not request_details:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return request_details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve request: {str(e)}")


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    uptime = time.time() - app_start_time
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime_seconds=uptime
    )


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    Get comprehensive statistics about requests and system health.
    
    Includes:
    - Request counts and processing times
    - Success/failure rates
    - Rate limiting statistics
    - Circuit breaker status
    """
    try:
        # Get basic counts
        from database import RequestRecord
        
        total_requests = db.query(RequestRecord).count()
        sync_requests = db.query(RequestRecord).filter(RequestRecord.mode == RequestMode.SYNC).count()
        async_requests = db.query(RequestRecord).filter(RequestRecord.mode == RequestMode.ASYNC).count()
        
        completed_requests = db.query(RequestRecord).filter(
            RequestRecord.status == RequestStatus.COMPLETED
        ).count()
        
        failed_requests = db.query(RequestRecord).filter(
            RequestRecord.status == RequestStatus.FAILED
        ).count()
        
        # Get average processing times
        sync_avg_time = db.query(RequestRecord).filter(
            RequestRecord.mode == RequestMode.SYNC,
            RequestRecord.processing_time_ms.isnot(None)
        ).with_entities(RequestRecord.processing_time_ms).all()
        
        async_avg_time = db.query(RequestRecord).filter(
            RequestRecord.mode == RequestMode.ASYNC,
            RequestRecord.processing_time_ms.isnot(None)
        ).with_entities(RequestRecord.processing_time_ms).all()
        
        sync_avg = sum([t[0] for t in sync_avg_time]) / len(sync_avg_time) if sync_avg_time else 0
        async_avg = sum([t[0] for t in async_avg_time]) / len(async_avg_time) if async_avg_time else 0
        
        # Get rate limiting statistics
        rate_limit_stats = rate_limiter.get_stats()
        
        # Get callback service statistics (if available)
        callback_stats = {}
        try:
            callback_stats = callback_service.get_circuit_breaker_stats()
        except AttributeError:
            callback_stats = {"circuit_breaker": "not_available"}
        
        return {
            "request_statistics": {
                "total_requests": total_requests,
                "sync_requests": sync_requests,
                "async_requests": async_requests,
                "completed_requests": completed_requests,
                "failed_requests": failed_requests,
                "sync_avg_processing_time_ms": round(sync_avg, 2),
                "async_avg_processing_time_ms": round(async_avg, 2),
                "success_rate": round(completed_requests / total_requests * 100, 2) if total_requests > 0 else 0
            },
            "rate_limiting": rate_limit_stats,
            "callback_service": callback_stats,
            "system": {
                "uptime_seconds": time.time() - app_start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Statistics unavailable",
                "message": "Unable to retrieve system statistics",
                "code": "STATS_ERROR"
            }
        )


# Simple callback test endpoint for development
@app.post("/test-callback")
async def test_callback(payload: dict):
    """
    Test endpoint to receive callbacks during development.
    """
    print(f"Received callback: {payload}")
    return {"status": "callback_received", "payload": payload}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)