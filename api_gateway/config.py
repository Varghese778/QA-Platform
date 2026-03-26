"""Configuration settings for API Gateway."""

from functools import lru_cache
from typing import Optional, Set

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "API Gateway"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # JWT/Auth
    jwks_url: str = Field(
        default="http://localhost:8000/auth/v1/.well-known/jwks.json",
        description="URL to fetch JWKS from Auth service",
    )
    jwks_cache_ttl_seconds: int = Field(
        default=900,  # 15 minutes
        description="JWKS cache TTL in seconds",
    )
    jwt_issuer: str = "https://auth.qaplatform.internal"
    jwt_audience: str = "qaplatform-api"
    jwt_clock_skew_seconds: int = 5

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate Limiting
    rate_limit_user_per_minute: int = 100
    rate_limit_project_per_minute: int = 500
    rate_limit_window_seconds: int = 60
    rate_limit_fail_open: bool = True  # Allow requests if Redis is down

    # Downstream Services
    auth_service_url: str = "http://localhost:8000"
    orchestrator_service_url: str = "http://localhost:8001"
    artifact_service_url: str = "http://localhost:8002"
    async_service_url: str = "http://localhost:8003"

    # Timeouts
    downstream_timeout_seconds: float = 30.0
    websocket_ping_interval_seconds: int = 60

    # Request Limits
    max_request_body_bytes: int = 1_048_576  # 1 MB for non-upload routes
    max_upload_file_bytes: int = 10_485_760  # 10 MB per file
    max_upload_files_count: int = 5
    max_query_string_length: int = 2048

    # CORS
    cors_allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://localhost",
        description="Comma-separated list of allowed origins",
    )
    cors_allow_credentials: bool = True

    # Circuit Breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_window_seconds: int = 10
    circuit_breaker_recovery_timeout_seconds: int = 30

    @property
    def allowed_origins_set(self) -> Set[str]:
        """Parse CORS origins into a set."""
        return set(origin.strip() for origin in self.cors_allowed_origins.split(","))

    model_config = {
        "env_prefix": "GATEWAY_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
