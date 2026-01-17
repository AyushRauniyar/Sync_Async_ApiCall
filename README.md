# 🚀 Sync vs Async API

A comprehensive demonstration of **synchronous vs asynchronous API patterns** under load, built with enterprise-grade security, reliability, and monitoring features.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg?style=flat&logo=FastAPI)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/SQLite-3.x-blue.svg)](https://www.sqlite.org/)
[![Security](https://img.shields.io/badge/security-production--ready-green.svg)](./PRODUCTION_SECURITY.md)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🌟 Project Overview

This project demonstrates the **fundamental differences between synchronous and asynchronous API patterns** while implementing production-grade features that address real-world deployment challenges including security, reliability, monitoring, and operational excellence.

### 🎯 **Core Purpose**
- **Performance Comparison**: Clear demonstration of sync vs async performance characteristics
- **Production Readiness**: Enterprise-grade security, monitoring, and reliability features
- **Educational Value**: Comprehensive examples of modern API design patterns
- **Load Testing**: Dual-mode testing for both demonstration and production validation

### 🏗️ **Architecture**

- **FastAPI** backend with production security enhancements
- **SQLAlchemy + SQLite** for zero-config persistence with production migration path
- **Background tasks** with circuit breaker patterns for resilient async processing
- **aiohttp** for reliable callback delivery with retry logic and SSRF protection
- **Dual-mode load generator** with security awareness and comprehensive metrics
- **Enterprise security** features including rate limiting, input validation, and monitoring

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+**
- **Git** 
- **curl** or **Postman** (for API testing)

### Option 1: Quick Launch (Windows)
```bash
# Clone the repository
git clone https://github.com/your-username/sync-async-api.git
cd sync-async-api

# Run the automated setup and server start script
start_server.bat
```

### Option 2: Manual Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-username/sync-async-api.git
cd sync-async-api
```

### 2. Setup Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the API Server
```bash
# Start the FastAPI server
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# API will be available at:
# - API: http://localhost:8000
# - Interactive docs: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
```

### 4. Test the APIs
```bash

# Make sure to Activate virtual environment
# Test Sync endpoint
curl -X POST http://localhost:8000/sync \
  -H "Content-Type: application/json" \
  -d '{"data": {"user_id": "test123", "operation": "compute"}, "complexity": 2}'

# Test Async endpoint  
curl -X POST http://localhost:8000/async \
  -H "Content-Type: application/json" \
  -d '{
    "data": {"user_id": "test456", "operation": "process"}, 
    "complexity": 2,
    "callback_url": "https://httpbin.org/post"
  }'

# Get all requests (shows processing history)
curl http://localhost:8000/requests

# Get requests with pagination
curl "http://localhost:8000/requests?limit=5&offset=0"

# Get specific request details (use request_id from above responses)
curl http://localhost:8000/requests/{request_id}

# Check system statistics
curl http://localhost:8000/stats

# Health check
curl http://localhost:8000/healthz
```

---

## 🧪 Load Testing

### Demo Mode (Performance Comparison)
```bash
# Show clear sync vs async differences
python load_generator/load_test.py --demo-mode --requests 200 --concurrency 15

# High-performance demonstration  
python load_generator/load_test.py --demo-mode --requests 2000 --concurrency 20 --complexity 3
```

### Production Mode (Security-Aware Testing)
```bash
# Safe production testing
python load_generator/load_test.py --production-mode --requests 30 --concurrency 3

# With external API
python load_generator/load_test.py \
    --production-mode \
    --url https://your-api.com \
    --requests 25 \
    --concurrency 2
```

### Load Test Features
- **🎭 Demo Mode**: Optimized to show sync vs async performance differences
  - In-memory database for maximum I/O performance
  - No rate limiting to show pure async vs sync behavior
  - External callback URLs (httpbin.org) for reliable testing
- **🔒 Production Mode**: Security-aware testing with rate limiting respect
  - File-based SQLite with connection pooling
  - Rate limiting simulation (50 requests/60 seconds)
  - SSRF protection for callback URL security
- **📊 Comprehensive Metrics**: Latency percentiles, throughput, callback analysis
- **🛡️ Security Testing**: Built-in security test suite with SSRF protection validation

For detailed load testing guide, see [LOAD_TESTING_GUIDE.md](./LOAD_TESTING_GUIDE.md).

---

## 📊 API Endpoints

### **Core Endpoints**

| Method | Endpoint | Description | Response Time |
|--------|----------|-------------|---------------|
| `POST` | `/sync` | Synchronous processing | ~100-200ms |
| `POST` | `/async` | Asynchronous processing | ~5-15ms |
| `GET` | `/requests` | List request history | ~10-50ms |
| `GET` | `/requests/{id}` | Get request details | ~5-20ms |
| `GET` | `/stats` | System statistics | ~20-100ms |
| `GET` | `/healthz` | Health check | ~1-5ms |

### **Request/Response Examples**

#### Synchronous Request
```bash
POST /sync
{
  "data": {"user_id": "user789", "operation": "calculate"},
  "complexity": 2
}

# Response (after ~150ms)
{
  "request_id": "req_abc123",
  "result": {
    "sum": 8.5,
    "product": 16.305,
    "operations": 6
  },
  "processing_time_ms": 152.3,
  "timestamp": "2026-01-16T10:30:00.152Z"
}

```

#### Asynchronous Request
```bash
POST /async  
{
  "data": {"user_id": "user789", "operation": "analyze"},
  "complexity": 2,
  "callback_url": "https://httpbin.org/post"
}

# Immediate Response (~8ms)
{
  "request_id": "req_def456",
  "status": "accepted", 
  "message": "Request accepted for processing. Callback will be sent when complete."
}

# Later: Callback sent to httpbin.org/post (~150ms later)
{
  "request_id": "req_def456",
  "result": {"sum": 8.5, "product": 16.305, "operations": 6},
  "processing_time_ms": 152.3,
  "timestamp": "2026-01-16T10:30:00.160Z"
}
```

---

## 🏗️ Architecture & Design Decisions

### 🎯 **Core Design Philosophy**
This project prioritizes **production readiness** over simplicity, implementing real-world considerations often overlooked in demonstrations.

### 🔧 **Technology Stack**

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Web Framework** | FastAPI | Modern async support, automatic OpenAPI docs, high performance |
| **Database** | SQLite + SQLAlchemy | Zero-config setup, production-scalable ORM patterns |
| **Async Processing** | FastAPI BackgroundTasks + asyncio | Native async support, no external queue dependencies |
| **HTTP Client** | aiohttp | Async HTTP client for callbacks, robust error handling |
| **Validation** | Pydantic | Type safety, automatic validation, security-aware parsing |
| **Load Testing** | asyncio + aiohttp | Custom solution for precise control and security awareness |

### 🔀 **Key Design Decisions**

#### 1. **Shared Business Logic Pattern**
```python
# Both sync and async use the same work processor
class WorkProcessor:
    @staticmethod
    def process_work(data: List[float], complexity: int) -> Dict[str, Any]:
        # Shared CPU-intensive work simulation
        # Used by both sync and async endpoints
```

**Rationale**: Ensures identical processing logic, making performance comparisons fair and meaningful.

#### 2. **Database-Driven Request Tracking**
```python
class RequestRecord:
    id: str
    mode: RequestMode  # SYNC or ASYNC
    status: RequestStatus  # PROCESSING, COMPLETED, FAILED, etc.
    processing_time_ms: Optional[float]
    callback_url: Optional[str]
```

**Rationale**: Provides comprehensive audit trail, enables monitoring, supports async callback correlation.

#### 3. **Security-First Callback Handling**
```python
# SSRF Protection
if parsed.hostname in blocked_hosts and environment == 'production':
    raise HTTPException(400, "Callback to localhost not allowed in production")

# Circuit Breaker Pattern  
if self._is_circuit_open(domain):
    return False  # Skip callback to failing domain
```

**Rationale**: Prevents security vulnerabilities (SSRF attacks) and provides resilience against failing callback endpoints. Load testing uses external URLs (httpbin.org) to avoid localhost restrictions and ensure realistic callback behavior.

#### 4. **Dual-Mode Load Testing**
- **Demo Mode**: 
  - No rate limits for maximum performance demonstration
  - In-memory SQLite database for faster I/O
  - External callback URLs (httpbin.org) for reliable testing
  - High concurrency support (20+ concurrent requests)
- **Production Mode**: 
  - Security-aware with rate limiting (50 requests/60 seconds)
  - File-based SQLite with connection pooling
  - SSRF protection for callback URLs
  - Operational validation focus

**Rationale**: Balances demonstration needs with production safety requirements.

### ⚖️ **Key Tradeoffs**

#### 📊 **Performance vs Security**
- **Decision**: Implement comprehensive security validation
- **Tradeoff**: ~1ms additional latency per request
- **Rationale**: Production deployment requires security over micro-optimizations

#### 🔄 **Sync vs Async Processing**
- **Sync Benefits**: Simpler error handling, immediate results, predictable resource usage
- **Async Benefits**: Better user experience, higher throughput, non-blocking operations
- **Tradeoff**: Async adds complexity (callback handling, circuit breakers, monitoring)

#### 💾 **Database Choice: Environment-Aware Configuration**
- **Demo/Development Mode**: In-memory SQLite for maximum performance and zero setup
- **Production Mode**: File-based SQLite with proper connection pooling
- **PostgreSQL Migration**: Easy upgrade path when scaling requirements demand it
- **Decision**: Environment-specific SQLite configuration with production migration path documented
- **Rationale**: Ease of setup for evaluation, with clear upgrade path

#### 🧪 **Custom Load Testing vs Artillery/k6**
- **Custom Advantages**: Security feature awareness, precise control, mode-specific analysis
- **Existing Tools Advantages**: Battle-tested, feature-rich, community support  
- **Decision**: Custom solution with production compatibility
- **Rationale**: Needed security-aware testing and sync vs async specific metrics

#### 🔐 **Security Depth vs Simplicity**
- **Simple Approach**: Basic validation, minimal security checks
- ---

## 📈 Performance Characteristics

### **Sync vs Async Performance Comparison**

| Metric | Sync Pattern | Async Pattern | Advantage |
|--------|-------------|---------------|-----------|
| **Response Time** | 100-200ms (complete) | 5-15ms (acceptance) | **12-20x faster** async acceptance |
| **Throughput** | 8-15 req/s | 30-60 req/s | **3-4x higher** async throughput |
| **Resource Usage** | High (blocking) | Low (non-blocking) | **Better** resource utilization |
| **User Experience** | Wait for completion | Immediate feedback | **Significantly better** UX |
| **Error Handling** | Simple (immediate) | Complex (callback-based) | **Simpler** sync debugging |
| **Monitoring** | Basic | Advanced | **More complex** async observability |

### **Load Testing Results Example**

#### Demo Mode Results:
```
🎭 SYNC vs ASYNC PERFORMANCE COMPARISON:
   📊 IMMEDIATE RESPONSE TIMES:
      Sync (full processing):    156.2ms
      Async (acceptance only):   12.4ms  
      📈 Speed improvement:       12.6x faster acceptance

   📊 THROUGHPUT COMPARISON:
      Sync requests/sec:        8.2
      Async requests/sec:       42.1
      📈 Throughput advantage:    5.1x higher (async)

   🎯 KEY INSIGHTS:
      ✅ Async provides faster user feedback
      ✅ Async handles higher request volumes  
      ✅ Reliable async completion (95.2% success rate)
```

---

## 🔧 Development

### **Project Structure**
```
sync-async-api/
├── src/                          # Main application code
│   ├── main.py                   # FastAPI app with dual-mode features
│   ├── models.py                 # Pydantic models for requests/responses  
│   ├── database.py               # SQLAlchemy setup and models
│   ├── services.py               # Business logic and callback handling
│   └── work_processor.py         # Shared CPU-intensive work simulation
├── load_generator/               # Load testing framework
│   └── load_test.py             # Dual-mode load testing tool
├── tests/                        # Test suites
│   ├── test_api.py              # API endpoint tests
│   └── security_test_suite.py   # Security validation tests
├── docs/                         # Documentation
│   ├── PRODUCTION_SECURITY.md   # Security implementation guide
│   ├── LOAD_TESTING_GUIDE.md    # Load testing documentation
│   └── API_ENDPOINTS.md         # API documentation
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

### **Running Tests**
```bash
# API functionality tests
python test_api.py

# Comprehensive security tests  
python security_test_suite.py

# Load testing
python load_generator/load_test.py --demo-mode --requests 100 --concurrency 10
```

### **Database Management**
```bash
# Database is created automatically on first run
# Location: ./requests.db

# To reset database:
rm requests.db

# Database will be recreated on next API start
```

---
## 🤝 Contributing

### **Development Setup**
```bash
# Clone and setup
git clone https://github.com/your-username/sync-async-api.git
cd sync-async-api
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run tests
python test_api.py
python security_test_suite.py

# Start development server
python -m uvicorn src.main:app --reload
```

### **Testing Guidelines**
- Add tests for new features
- Run security test suite for security-related changes
- Test both demo and production modes for load testing changes
- Update documentation for new features

---


**Built with ❤️ for demonstrating difference between async/sync API patterns**

## Load Generator Usage

```bash
# Basic load test
python load_generator/load_test.py

# Advanced options
python load_generator/load_test.py \
  --requests 1000 \          # Total requests to send
  --concurrency 50 \         # Concurrent requests
  --sync-ratio 0.6 \         # 60% sync, 40% async
  --complexity 5 \           # Work complexity (1-10)
  --callback-port 8080 \     # Callback server port
  --output results.json      # Save results to file
```

## Design Decisions & Tradeoffs

### 1. **FastAPI Choice**
- **Pros**: Native async support, automatic OpenAPI docs, excellent performance
- **Tradeoffs**: Slightly more complex than Flask but better for this use case

### 2. **SQLite for Persistence**
- **Demo Mode**: In-memory SQLite (sqlite:///:memory:) for maximum performance
- **Production Mode**: File-based SQLite with connection pooling
- **Pros**: Zero-configuration, sufficient for demo, ACID compliance
- **Tradeoffs**: Single-writer limitation (would use PostgreSQL in production)

### 3. **Background Tasks vs Message Queue**
- **Current**: FastAPI background tasks for simplicity
- **Production Alternative**: Celery + Redis for distributed processing
- **Tradeoff**: In-memory task queue vs external dependency

### 4. **Callback Retry Strategy**
- **Strategy**: 3 attempts with exponential backoff
- **Reasoning**: Balance between reliability and resource usage
- **Timeout**: 10-second HTTP timeout to prevent hanging
- **External URLs**: Uses httpbin.org for load testing (no localhost dependencies)
- **Security**: SSRF protection blocks localhost callbacks in production mode

### 5. **Work Simulation**
- **Approach**: Mathematical computations with deterministic results
- **Benefits**: Reproducible testing, CPU-bound workload simulation
- **Complexity Scaling**: Linear increase in processing time

### 6. **Error Handling**
- **Callback Failures**: Graceful degradation with status tracking
- **Malicious URLs**: Basic validation (production would need more)
- **Resource Limits**: Input size limits to prevent abuse

## Monitoring & Observability

### Request States
- **Pending**: Request received, not yet processed
- **Processing**: Currently being worked on
- **Completed**: Successfully processed
- **Failed**: Processing failed
- **Callback Sent**: Callback delivered successfully
- **Callback Failed**: Callback delivery failed after retries

### Performance Metrics
- **Request throughput** (requests/second)
- **Success rates** for both sync and async
- **Latency percentiles** (p50, p95, p99)
- **Callback delivery rates** and timing
- **Error categorization** and frequency
