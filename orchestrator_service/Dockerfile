# Multi-stage Dockerfile for Python/FastAPI microservices
# Optimized for production with minimal image size

# Stage 1: Build stage
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /build

# Configure apt to use stable repositories and fix connectivity issues
RUN echo 'APT::Acquire::Retries "3";' > /etc/apt/apt.conf.d/80retries && \
    echo 'APT::Acquire::http::Timeout "60";' > /etc/apt/apt.conf.d/80timeout && \
    echo 'Acquire::http::Pipeline-Depth "0";' > /etc/apt/apt.conf.d/90pipeline

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies in a virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt --timeout=120 --retries=5

# Stage 2: Runtime stage
FROM python:3.11-slim AS runtime

# Set working directory for the package
WORKDIR /app

# Configure apt to use stable repositories and fix connectivity issues
RUN echo 'APT::Acquire::Retries "3";' > /etc/apt/apt.conf.d/80retries && \
    echo 'APT::Acquire::http::Timeout "60";' > /etc/apt/apt.conf.d/80timeout && \
    echo 'Acquire::http::Pipeline-Depth "0";' > /etc/apt/apt.conf.d/90pipeline

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PYTHONPATH=/app

# Copy application code to the package directory
COPY . /app/orchestrator_service/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "orchestrator_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
