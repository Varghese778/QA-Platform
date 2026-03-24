"""Configuration settings for Execution Engine."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Execution Engine"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8013

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/execution",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = "redis://localhost:6379/5"
    execution_queue_name: str = "execution_queue"
    runner_registry_key: str = "runner_registry"

    # Execution
    test_execution_timeout_seconds: float = 300.0  # 5 minutes
    execution_poll_interval_seconds: float = 5.0
    max_retries: int = 3
    retry_backoff_seconds: float = 5.0

    # Test Execution
    execution_per_test_timeout_seconds: float = 30.0
    flaky_retry_count: int = 1
    min_pass_rate_for_coverage: float = 0.8

    # Runner
    runner_startup_timeout_seconds: float = 30.0
    runner_shutdown_timeout_seconds: float = 10.0
    max_concurrent_runners: int = 5

    # Artifact Storage
    artifact_storage_url: str = "http://localhost:8012"
    artifact_storage_timeout_seconds: float = 30.0

    # Memory Layer
    memory_layer_url: str = "http://localhost:8011"
    memory_layer_timeout_seconds: float = 30.0

    # Secret Manager (mock)
    secret_manager_url: str = "http://localhost:9000"
    secret_manager_timeout_seconds: float = 10.0

    # Allowed Services (for access control)
    allowed_services: list = Field(
        default=["orchestrator", "api_gateway"],
        description="Service accounts allowed to access execution engine",
    )

    # Query Limits
    max_list_limit: int = 1000

    model_config = {
        "env_prefix": "EXECUTION_ENGINE_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
