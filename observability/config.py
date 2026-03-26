"""Configuration settings for Observability & Logging."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Observability & Logging"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8015

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/observability",
        description="PostgreSQL connection URL",
    )

    # Logging
    log_retention_days: int = 30
    log_pagination_limit: int = 1000
    log_level: str = "INFO"

    # Metrics
    metrics_retention_days: int = 90
    metrics_aggregation_interval_seconds: int = 60
    default_metrics_lookback_seconds: int = 3600  # 1 hour

    # Tracing
    trace_retention_days: int = 7
    trace_sampling_ratio: float = 0.1  # 10% by default
    max_span_batch_size: int = 100

    # Alerts
    alert_check_interval_seconds: int = 60
    alert_max_history_days: int = 30
    alert_deduplicate_minutes: int = 15

    # Service endpoints
    orchestrator_url: str = "http://localhost:8008"
    execution_engine_url: str = "http://localhost:8013"
    async_processing_url: str = "http://localhost:8014"

    model_config = {
        "env_prefix": "OBSERVABILITY_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
