"""Configuration settings for Memory Layer."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Memory Layer"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8011

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/memory",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = "redis://localhost:6379/3"
    embedding_cache_ttl_seconds: int = 86400  # 24 hours

    # Embedding Configuration
    embedding_dimension: int = 1536
    embedding_model: str = "text-embedding-3-small"
    embedding_cache_enabled: bool = True

    # Search Configuration
    default_top_k: int = 10
    max_top_k: int = 50
    agg_multiplier: int = 3  # Get top_k * 3 candidates, then filter
    semantic_search_timeout_seconds: float = 10.0

    # Retention Configuration
    default_retention_days: int = 365
    min_retention_days: int = 30
    hard_delete_days: int = 90

    # Rate Limiting
    max_payload_size_bytes: int = 65536  # 64 KB

    # Query Limits
    max_query_text_length: int = 2000
    max_filter_tags: int = 10
    max_filter_domains: int = 6

    # Timeouts
    http_client_timeout_seconds: float = 30.0

    # Allowed Services (for access control)
    allowed_services: list = Field(
        default=["orchestrator", "multi_agent_engine", "execution_engine"],
        description="Service accounts allowed to access memory",
    )

    model_config = {
        "env_prefix": "MEMORY_LAYER_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
