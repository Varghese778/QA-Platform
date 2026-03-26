# QA Platform

> **Enterprise-Grade Intelligent Test Generation & Execution Platform**

A comprehensive, microservices-based QA platform that leverages multi-agent AI systems to automatically generate, execute, and analyze test cases from user stories. Built with modern technologies and designed for scalability, observability, and developer experience.

---

## 🏗️ Architecture Overview

The QA Platform consists of **10 modules** organized into 3 tiers:

### **Infrastructure Layer**
- **PostgreSQL** (15-alpine) - Primary data store with async support
- **Redis** (7-alpine) - Caching, rate limiting, distributed coordination, and message queuing

### **Backend Microservices** (Python 3.11 + FastAPI)

1. **Auth & Access Control Service** (Port 8000)
   - OIDC/OAuth2 integration with JWT token management
   - Role-Based Access Control (RBAC) with project-level permissions
   - API key management and audit logging
   - Token denylist and brute-force protection

2. **API Gateway** (Port 8080) ⭐ **PUBLIC**
   - Single ingress point for all client traffic
   - JWT validation and rate limiting (Redis-backed sliding window)
   - Request routing and WebSocket proxying
   - CORS, security headers, and circuit breaking

3. **Orchestrator Service** (Port 8001)
   - Job lifecycle management and task graph execution
   - Finite state machine (FSM) for workflow coordination
   - Dependent task scheduling and retry logic
   - Watchdog for timeout detection and recovery

4. **Multi-Agent Engine** (Port 8010)
   - Multi-agent task distribution with work-stealing scheduler
   - LLM integration (mock for MVP, real LLM ready)
   - Task queue prioritization and agent pool management
   - Specialized agents: Parser, Classifier, Tester, Validator

5. **Memory Layer** (Port 8011)
   - Semantic search with vector embeddings (mock for MVP)
   - Knowledge graph for entity/relationship mapping
   - Context storage with TTL and retention policies
   - Constraint and validation rule management

6. **Artifact Storage** (Port 8012)
   - Binary artifact persistence (local filesystem or S3-compatible)
   - Virus scanning queue (async with Redis)
   - Pre-signed URL generation for secure downloads
   - Project-level access control and duplicate detection

7. **Execution Engine** (Port 8013)
   - Test case execution with dynamic runner provisioning
   - Flaky test detection with automatic retry
   - Coverage calculation and detailed failure reporting
   - Script translation from JSON test definitions

8. **Async Processing** (Port 8014)
   - Event ingestion and Redis Streams processing
   - Real-time WebSocket gateway for job status updates
   - Dead Letter Queue (DLQ) with replay capability
   - WebSocket connection registry and heartbeat management

9. **Observability & Logging** (Port 8015)
   - Structured log collection and full-text search
   - Metrics aggregation with time-series queries
   - Distributed tracing with span reconstruction
   - Alert rule engine with threshold-based triggers

### **Frontend** (React 18 + TypeScript + Vite)

10. **Frontend Dashboard** (Port 80/5173) ⭐ **PUBLIC**
    - Story submission form with validation
    - Real-time pipeline status via WebSocket
    - Test suite viewer with filtering
    - Execution report with pass/fail charts and PDF/CSV export
    - Responsive design with Tailwind CSS

---

## 🚀 Quick Start

### Prerequisites

- **Docker** 24.0+ and **Docker Compose** 2.20+
- **Git**
- At least **4GB RAM** available for Docker
- **Ports** 80, 5432, 6379, and 8080 must be available

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/qa-platform.git
   cd qa-platform
   ```

2. **Set up environment variables:**

   ```bash
   cp .env.example .env
   ```

   > ⚠️ **IMPORTANT**: For production, update `.env` with:
   > - Strong PostgreSQL passwords
   > - Actual domain names (replace `localhost`)
   > - JWT private/public key paths
   > - External secrets management

3. **Build and start all services:**

   ```bash
   docker-compose up --build -d
   ```

   This command will:
   - Build Docker images for all 9 backend services and the frontend
   - Start PostgreSQL and Redis
   - Initialize databases with schemas
   - Start all microservices
   - Serve the frontend dashboard

4. **Verify services are running:**

   ```bash
   docker-compose ps
   ```

   All services should show status `Up` or `Up (healthy)`.

5. **Access the platform:**

   - **Frontend Dashboard**: http://localhost
   - **API Gateway (Swagger Docs)**: http://localhost:8080/docs
   - **API Gateway (ReDoc)**: http://localhost:8080/redoc

6. **Quick Test:**

   Open the frontend dashboard and use the **"Quick Demo Login"** button to bypass authentication and start submitting user stories.

---

## 📦 Service Ports Reference

| Service | Internal Port | Externally Exposed | Description |
|---------|---------------|-------------------|-------------|
| **Frontend Dashboard** | 80 | ✅ Yes (`:80`) | React SPA served via Nginx |
| **API Gateway** | 8080 | ✅ Yes (`:8080`) | Single public ingress point |
| **Auth Service** | 8000 | ❌ No | Internal authentication |
| **Orchestrator** | 8001 | ❌ No | Job coordination |
| **Multi-Agent Engine** | 8010 | ❌ No | AI agent pool |
| **Memory Layer** | 8011 | ❌ No | Context & embeddings |
| **Artifact Storage** | 8012 | ❌ No | Binary artifacts |
| **Execution Engine** | 8013 | ❌ No | Test execution |
| **Async Processing** | 8014 | ❌ No | Event streams & WebSockets |
| **Observability** | 8015 | ❌ No | Logs, metrics, traces |
| **PostgreSQL** | 5432 | 🔧 Dev only | Primary database |
| **Redis** | 6379 | 🔧 Dev only | Cache & message broker |

> **Security Note**: Only the API Gateway and Frontend are exposed. All internal services communicate via the `qa-network` Docker bridge network.

---

## 🔧 Configuration

### Environment Variables

All services are configured via environment variables with the `[SERVICE]_` prefix. See `.env.example` for the complete reference.

**Key Configuration Points:**

- **Database URLs**: Must use `postgresql+asyncpg://` for async SQLAlchemy
- **Service URLs**: Use Docker service names (e.g., `http://auth-service:8000`)
- **Redis URLs**: Use `redis://redis:6379/[db_number]` for namespace isolation
- **CORS**: Update `GATEWAY_CORS_ALLOWED_ORIGINS` for production domains

### Docker Compose Overrides

For local development customizations, create `docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  api-gateway:
    environment:
      GATEWAY_DEBUG: "true"
    ports:
      - "8080:8080"
```

---

## 🛠️ Development Workflow

### Running Individual Services Locally

To develop a single service without Docker:

```bash
cd auth_service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Update .env to use localhost instead of Docker service names
AUTH_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/qa_platform
AUTH_REDIS_URL=redis://localhost:6379/0

uvicorn main:app --reload --port 8000
```

### Rebuilding After Code Changes

```bash
# Rebuild specific service
docker-compose up --build -d auth-service

# Rebuild all services
docker-compose up --build -d

# Force rebuild without cache
docker-compose build --no-cache
docker-compose up -d
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api-gateway

# Last 100 lines
docker-compose logs --tail=100 orchestrator-service
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

---

## 📊 System Health Checks

### Health Check Endpoints

All backend services expose two health endpoints:

- **Liveness**: `GET /health/live` - Returns 200 if the process is running
- **Readiness**: `GET /health/ready` - Returns 200 if dependencies (DB, Redis) are accessible

### Checking Service Health

```bash
# API Gateway
curl http://localhost:8080/health/ready

# Via Docker
docker-compose exec api-gateway curl -f http://localhost:8080/health/live
```

### Database Migrations

Each service with a database manages its own schema. On first startup, tables are auto-created via SQLAlchemy.

For production, use Alembic migrations:

```bash
# Inside a service container
docker-compose exec auth-service alembic upgrade head
```

---

## 🧪 Testing

### Manual Integration Test Flow

1. **Login**: Access http://localhost and use "Quick Demo Login"
2. **Submit Story**: Fill out the user story form and submit
3. **Monitor Pipeline**: Navigate to job detail page and watch real-time updates
4. **View Tests**: Switch to "Test Suite" tab to see generated test cases
5. **Check Report**: Once execution completes, view the "Execution Report" tab

### API Testing with Swagger

Access http://localhost:8080/docs to explore and test all API endpoints interactively.

---

## 📁 Project Structure

```
qa-platform/
├── auth_service/               # Authentication & RBAC
├── api_gateway/                # Public API + WebSocket gateway
├── orchestrator_service/       # Job & task orchestration
├── multi_agent_engine/         # Multi-agent AI task execution
├── memory_layer/               # Semantic search & knowledge graph
├── artifact_storage/           # Binary artifact management
├── execution_engine/           # Test execution & reporting
├── async_processing/           # Event streams & real-time updates
├── observability/              # Logs, metrics, traces, alerts
├── frontend/                   # React dashboard
├── docker-compose.yml          # Orchestration configuration
├── .env.example                # Environment variable template
├── .gitignore                  # Git ignore rules
├── Dockerfile.python           # Python service template
└── README.md                   # This file
```

Each backend service follows a consistent structure:

```
service_name/
├── main.py                     # FastAPI app entry point
├── config.py                   # Environment-based settings
├── database.py                 # Async SQLAlchemy setup
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Multi-stage Docker build
├── models/                     # SQLAlchemy ORM models
├── routes/                     # FastAPI route handlers
├── schemas/                    # Pydantic request/response models
├── services/                   # Business logic layer
└── core/                       # Shared utilities
```

---

## 🔐 Security Considerations

### Authentication Flow

1. User authenticates via Auth Service (OIDC/OAuth2 integration planned)
2. Auth Service issues JWT with RS256 signature
3. Frontend stores JWT in localStorage
4. API Gateway validates JWT on every request using JWKS from Auth Service
5. Backend services trust requests forwarded by API Gateway (internal network)

### Production Checklist

- [ ] Use strong, randomly generated PostgreSQL passwords
- [ ] Configure actual JWT RS256 private/public key pair (not mock)
- [ ] Enable HTTPS/TLS for all external endpoints
- [ ] Set up external secrets management (AWS Secrets Manager, Vault)
- [ ] Configure proper CORS origins (remove `localhost`)
- [ ] Enable rate limiting with appropriate thresholds
- [ ] Set up log aggregation (ELK, Datadog, CloudWatch)
- [ ] Configure backup strategies for PostgreSQL
- [ ] Implement network policies for Kubernetes deployments
- [ ] Set up vulnerability scanning for Docker images

---

## 🐛 Troubleshooting

### Common Issues

**Issue: Services fail to start with "connection refused"**

**Solution**: Ensure `depends_on` health checks pass. Check logs:

```bash
docker-compose logs postgres redis
```

---

**Issue: Frontend shows "Network Error"**

**Solution**: Verify API Gateway is running and CORS is configured:

```bash
docker-compose logs api-gateway | grep CORS
```

Check `.env` has correct `GATEWAY_CORS_ALLOWED_ORIGINS`.

---

**Issue: "Database connection failed" errors**

**Solution**: Ensure database URL uses `postgresql+asyncpg://` and points to `postgres` service:

```bash
docker-compose exec auth-service env | grep DATABASE_URL
```

---

**Issue: WebSocket connection fails**

**Solution**: WebSocket URLs must use `ws://` protocol (not `http://`). Check frontend `.env`:

```bash
VITE_WS_BASE_URL=ws://localhost:8080/ws/v1
```

---

**Issue: Port conflicts (address already in use)**

**Solution**: Change exposed ports in `docker-compose.yml` or stop conflicting services.

---

## 🎯 Roadmap

### ✅ MVP (Current)
- [x] All 10 modules implemented
- [x] Docker orchestration
- [x] Basic authentication and RBAC
- [x] Real-time job status updates
- [x] Mock LLM integration

### 🔜 Phase 2 (Q2 2026)
- [ ] Real LLM integration (OpenAI, Anthropic, or self-hosted)
- [ ] Advanced vector embeddings with Pinecone/Weaviate
- [ ] Kubernetes Helm charts
- [ ] CI/CD pipelines with GitHub Actions
- [ ] Comprehensive test suite (unit + integration)

### 🚀 Phase 3 (Q3 2026)
- [ ] Multi-tenancy with workspace isolation
- [ ] Advanced analytics dashboard
- [ ] Scheduled test execution
- [ ] Mobile-responsive UI
- [ ] Plugin system for custom test frameworks

---

Built for Atos - Srijan 2026
