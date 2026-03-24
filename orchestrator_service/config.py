"""Configuration settings for Orchestrator Service."""

from functools import lru_cache
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Orchestrator Service"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/orchestrator",
        description="PostgreSQL connection URL",
    )

    # Redis (for distributed coordination)
    redis_url: str = "redis://localhost:6379/1"

    # Downstream Services
    multi_agent_engine_url: str = "http://localhost:8010"
    memory_layer_url: str = "http://localhost:8011"
    artifact_storage_url: str = "http://localhost:8002"
    execution_engine_url: str = "http://localhost:8012"
    async_processing_url: str = "http://localhost:8003"

    # Timeouts (seconds)
    default_job_timeout_seconds: int = 1800  # 30 minutes
    default_task_timeout_seconds: int = 300  # 5 minutes
    http_client_timeout_seconds: float = 30.0

    # Task-specific timeouts
    task_timeouts: Dict[str, int] = Field(
        default={
            "PARSE_STORY": 60,
            "CLASSIFY_DOMAIN": 60,
            "FETCH_CONTEXT": 120,
            "GENERATE_TESTS": 300,
            "VALIDATE_TESTS": 180,
            "EXECUTE_TESTS": 600,
        },
        description="Timeout in seconds per task type",
    )

    # Retry configuration
    max_task_retries: int = 3
    retry_backoff_base_seconds: int = 5  # Exponential: 5s, 15s, 45s

    # Scheduler configuration
    scheduler_poll_interval_seconds: int = 10
    watchdog_check_interval_seconds: int = 30
    queue_retry_interval_seconds: int = 30

    # Estimation configuration
    default_estimated_completion_seconds: int = 300  # 5 minutes fallback

    model_config = {
        "env_prefix": "ORCHESTRATOR_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
