"""Configuration settings for Async Processing."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Async Processing"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8014

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/async_processing",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = "redis://localhost:6379/6"
    event_stream_name: str = "events"
    consumer_group_name: str = "async_processors"
    consumer_name: str = "processor_1"
    stream_block_timeout_ms: int = 1000  # 1 second
    stream_read_count: int = 10  # Read up to 10 events at a time

    # WebSocket
    websocket_timeout_seconds: float = 300.0  # 5 minutes
    max_connections_per_job: int = 100
    connection_heartbeat_interval_seconds: float = 30.0

    # Event Processing
    event_retention_days: int = 30
    batch_size: int = 100
    process_timeout_seconds: float = 60.0

    # Dead Letter Queue
    dead_letter_stream_name: str = "dead_letter_events"
    dead_letter_max_retries: int = 3
    dead_letter_retention_days: int = 90

    # External Services
    orchestrator_url: str = "http://localhost:8008"
    execution_engine_url: str = "http://localhost:8013"
    memory_layer_url: str = "http://localhost:8011"

    # Allowed Services (for access control)
    allowed_services: list = Field(
        default=["orchestrator", "execution_engine", "api_gateway"],
        description="Service accounts allowed to send events",
    )

    model_config = {
        "env_prefix": "ASYNC_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
