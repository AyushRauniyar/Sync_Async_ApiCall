import json
import uuid
import random
import time
import aiohttp
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database import RequestRecord, get_db
from models import RequestMode, RequestStatus, RequestDetails
from work_processor import WorkProcessor


class RequestService:
    """Service layer for handling requests and database operations"""
    
    def __init__(self):
        self.work_processor = WorkProcessor()
    
    def create_request_record(self, db: Session, mode: RequestMode, input_data: Dict[str, Any], 
                            callback_url: Optional[str] = None) -> str:
        """Create a new request record in database"""
        request_id = str(uuid.uuid4())
        
        record = RequestRecord(
            request_id=request_id,
            mode=mode,
            status=RequestStatus.PENDING,
            input_data=json.dumps(input_data),
            callback_url=callback_url
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return request_id
    
    def update_request_status(self, db: Session, request_id: str, 
                            status: RequestStatus, result: Optional[Dict[str, Any]] = None,
                            processing_time_ms: Optional[float] = None,
                            error_message: Optional[str] = None):
        """Update request status and results"""
        record = db.query(RequestRecord).filter(RequestRecord.request_id == request_id).first()
        
        if record:
            record.status = status
            if result:
                record.result = json.dumps(result)
            if processing_time_ms:
                record.processing_time_ms = processing_time_ms
            if status in [RequestStatus.COMPLETED, RequestStatus.FAILED, RequestStatus.CALLBACK_SENT]:
                record.completed_at = datetime.utcnow()
            if error_message:
                record.error_message = error_message
            
            db.commit()
    
    def get_request_details(self, db: Session, request_id: str) -> Optional[RequestDetails]:
        """Get details for a specific request"""
        record = db.query(RequestRecord).filter(RequestRecord.request_id == request_id).first()
        
        if not record:
            return None
        
        return RequestDetails(
            request_id=record.request_id,
            mode=record.mode,
            status=record.status,
            input_data=json.loads(record.input_data),
            result=json.loads(record.result) if record.result else None,
            processing_time_ms=record.processing_time_ms,
            callback_url=record.callback_url,
            callback_attempts=record.callback_attempts,
            created_at=record.created_at,
            completed_at=record.completed_at,
            error_message=record.error_message
        )
    
    def list_requests(self, db: Session, mode: Optional[RequestMode] = None, 
                     limit: int = 100) -> List[RequestDetails]:
        """List recent requests with optional filtering"""
        query = db.query(RequestRecord).order_by(RequestRecord.created_at.desc())
        
        if mode:
            query = query.filter(RequestRecord.mode == mode)
        
        records = query.limit(limit).all()
        
        return [
            RequestDetails(
                request_id=record.request_id,
                mode=record.mode,
                status=record.status,
                input_data=json.loads(record.input_data),
                result=json.loads(record.result) if record.result else None,
                processing_time_ms=record.processing_time_ms,
                callback_url=record.callback_url,
                callback_attempts=record.callback_attempts,
                created_at=record.created_at,
                completed_at=record.completed_at,
                error_message=record.error_message
            )
            for record in records
        ]
    
    def process_sync_request(self, db: Session, input_data: Dict[str, Any], 
                           complexity: int = 1) -> Dict[str, Any]:
        """Process a synchronous request"""
        # Create request record
        request_id = self.create_request_record(db, RequestMode.SYNC, input_data)
        
        try:
            # Update status to processing
            self.update_request_status(db, request_id, RequestStatus.PROCESSING)
            
            # Perform the work
            work_result = self.work_processor.process_work(input_data, complexity)
            
            # Update with results
            self.update_request_status(
                db, request_id, RequestStatus.COMPLETED,
                result=work_result["result"],
                processing_time_ms=work_result["processing_time_ms"]
            )
            
            return {
                "request_id": request_id,
                "result": work_result["result"],
                "processing_time_ms": work_result["processing_time_ms"],
                "timestamp": datetime.utcnow()
            }
            
        except Exception as e:
            # Update with error
            self.update_request_status(
                db, request_id, RequestStatus.FAILED,
                error_message=str(e)
            )
            raise e


class CallbackService:
    """Enhanced service for handling async callbacks with circuit breaker pattern"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.circuit_breaker_threshold = 5  # failures before opening circuit
        self.circuit_breaker_reset_timeout = 60  # seconds
        self.failed_callbacks: Dict[str, int] = {}  # domain -> failure count
        self.circuit_breaker_state: Dict[str, float] = {}  # domain -> last_failure_time
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for circuit breaker tracking"""
        from urllib.parse import urlparse
        return urlparse(url).netloc
    
    def _is_circuit_open(self, domain: str) -> bool:
        """Check if circuit breaker is open for this domain"""
        if domain not in self.circuit_breaker_state:
            return False
        
        failure_count = self.failed_callbacks.get(domain, 0)
        if failure_count < self.circuit_breaker_threshold:
            return False
        
        # Check if enough time has passed to reset circuit
        last_failure = self.circuit_breaker_state[domain]
        if time.time() - last_failure > self.circuit_breaker_reset_timeout:
            self.failed_callbacks[domain] = 0
            del self.circuit_breaker_state[domain]
            return False
        
        return True
    
    def _record_callback_failure(self, domain: str):
        """Record a callback failure for circuit breaker"""
        self.failed_callbacks[domain] = self.failed_callbacks.get(domain, 0) + 1
        self.circuit_breaker_state[domain] = time.time()
    
    def _record_callback_success(self, domain: str):
        """Record a callback success for circuit breaker"""
        if domain in self.failed_callbacks:
            del self.failed_callbacks[domain]
        if domain in self.circuit_breaker_state:
            del self.circuit_breaker_state[domain]
    
    async def send_callback(self, callback_url: str, payload: Dict[str, Any], 
                          request_id: str) -> bool:
        """Send callback to the provided URL with retry logic and circuit breaker"""
        
        domain = self._get_domain(callback_url)
        
        # Check circuit breaker
        if self._is_circuit_open(domain):
            print(f"Circuit breaker open for {domain}, skipping callback for request {request_id}")
            return False
        
        for attempt in range(self.max_retries):
            try:
                # Enhanced timeout and connection limits
                connector = aiohttp.TCPConnector(
                    limit_per_host=10,  # Max 10 connections per host
                    ttl_dns_cache=300,  # DNS cache for 5 minutes
                    use_dns_cache=True
                )
                
                timeout = aiohttp.ClientTimeout(
                    total=10,      # Total timeout
                    connect=3,     # Connection timeout
                    sock_read=5    # Socket read timeout
                )
                
                async with aiohttp.ClientSession(
                    connector=connector, 
                    timeout=timeout,
                    headers={'User-Agent': 'SyncAsyncAPI/1.0'}
                ) as session:
                    # Add request ID to payload for tracking
                    enhanced_payload = {
                        **payload,
                        'callback_metadata': {
                            'attempt': attempt + 1,
                            'max_attempts': self.max_retries,
                            'sent_at': datetime.utcnow().isoformat()
                        }
                    }
                    
                    async with session.post(
                        callback_url,
                        json=enhanced_payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            self._record_callback_success(domain)
                            print(f"Callback successful for request {request_id} on attempt {attempt + 1}")
                            return True
                        else:
                            print(f"Callback failed with status {response.status} for request {request_id} on attempt {attempt + 1}")
                            
            except asyncio.TimeoutError:
                print(f"Callback timeout for request {request_id} on attempt {attempt + 1}")
            except aiohttp.ClientError as e:
                print(f"Callback client error for request {request_id} on attempt {attempt + 1}: {str(e)}")
            except Exception as e:
                print(f"Callback unexpected error for request {request_id} on attempt {attempt + 1}: {str(e)}")
                
            # Exponential backoff with jitter
            if attempt < self.max_retries - 1:
                jitter = random.uniform(0.1, 0.3)  # Add randomness to prevent thundering herd
                delay = self.retry_delay * (2 ** attempt) + jitter
                await asyncio.sleep(delay)
        
        # All attempts failed
        self._record_callback_failure(domain)
        print(f"All callback attempts failed for request {request_id}")
        return False
    
    async def process_async_callback(self, db_session_factory, request_id: str):
        """Process async request and send callback"""
        db = db_session_factory()
        
        try:
            # Get request record
            record = db.query(RequestRecord).filter(RequestRecord.request_id == request_id).first()
            
            if not record:
                print(f"Request {request_id} not found")
                return
            
            # Update status to processing
            record.status = RequestStatus.PROCESSING
            db.flush()  # Flush without full commit for better performance
            
            # Perform the work asynchronously
            input_data = json.loads(record.input_data)
            work_result = await WorkProcessor.process_work_async(input_data, 1)  # Default complexity
            
            # Update with results in single transaction
            record.status = RequestStatus.COMPLETED
            record.result = json.dumps(work_result["result"])
            record.processing_time_ms = work_result["processing_time_ms"]
            record.completed_at = datetime.utcnow()
            
            # Send callback
            callback_payload = {
                "request_id": request_id,
                "result": work_result["result"],
                "processing_time_ms": work_result["processing_time_ms"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            callback_success = await self.send_callback(
                record.callback_url, callback_payload, request_id
            )
            
            if callback_success:
                record.status = RequestStatus.CALLBACK_SENT
                record.callback_attempts = self.max_retries  # Track successful attempt
            else:
                record.status = RequestStatus.CALLBACK_FAILED
                record.error_message = f"Callback failed after {self.max_retries} attempts"
            
            db.commit()
            
        except Exception as e:
            # Update with error
            record.status = RequestStatus.FAILED
            record.error_message = str(e)
            record.completed_at = datetime.utcnow()
            db.commit()
            print(f"Error processing async request {request_id}: {str(e)}")
        
        finally:
            db.close()
    
    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring"""
        stats = {}
        
        for domain in set(list(self.failed_callbacks.keys()) + list(self.circuit_breaker_state.keys())):
            failure_count = self.failed_callbacks.get(domain, 0)
            last_failure = self.circuit_breaker_state.get(domain, 0)
            is_open = self._is_circuit_open(domain)
            
            stats[domain] = {
                "state": "open" if is_open else "closed",
                "failure_count": failure_count,
                "last_failure_time": last_failure,
                "circuit_open": is_open
            }
        
        return {
            "domains": stats,
            "global_stats": {
                "total_domains_tracked": len(stats),
                "open_circuits": len([d for d in stats.values() if d["state"] == "open"]),
                "circuit_threshold": self.circuit_breaker_threshold,
                "reset_timeout": self.circuit_breaker_reset_timeout
            }
        }