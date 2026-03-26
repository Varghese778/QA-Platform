"""Configuration settings for Artifact Storage."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Artifact Storage"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8012

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/artifacts",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = "redis://localhost:6379/4"

    # Storage
    storage_type: str = Field(
        default="local", description="Storage backend: local or s3"
    )
    local_storage_path: str = Field(
        default="./artifact_data", description="Local filesystem storage directory"
    )
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = "us-east-1"
    s3_endpoint_url: Optional[str] = None

    # Upload
    max_upload_size_bytes: int = 536870912  # 512 MB
    chunk_size_bytes: int = 1048576  # 1 MB
    upload_timeout_seconds: float = 3600.0  # 1 hour

    # Virus scanning
    enable_virus_scan: bool = True
    virus_scan_timeout_seconds: float = 300.0  # 5 minutes
    scan_queue_name: str = "virus_scans"

    # Pre-signed URLs
    presigned_url_ttl_seconds: int = 3600  # 1 hour
    token_secret: str = Field(
        default="dev-secret-change-in-production",
        description="Secret for signing pre-signed URL tokens",
    )

    # Retention
    artifact_retention_days: int = 90
    cleanup_interval_hours: int = 24

    # Allowed Services (for access control)
    allowed_services: list = Field(
        default=["orchestrator", "multi_agent_engine", "execution_engine"],
        description="Service accounts allowed to access artifacts",
    )

    # Query Limits
    max_list_limit: int = 1000

    model_config = {
        "env_prefix": "ARTIFACT_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
