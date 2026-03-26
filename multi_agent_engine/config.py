"""Configuration settings for Multi-Agent Engine."""

from functools import lru_cache
from typing import Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Multi-Agent Engine"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8010

    # Redis
    redis_url: str = "redis://localhost:6379/2"
    queue_entry_ttl_seconds: int = 86400  # 24 hours

    # Orchestrator callback
    orchestrator_url: str = "http://localhost:8001"

    # Memory Layer
    memory_layer_url: str = "http://localhost:8011"

    # LLM Configuration
    llm_provider: str = "vertex-ai"  # mock, openai, anthropic, vertex-ai
    llm_api_key: Optional[str] = Field(default=None, description="LLM API key (from secret manager)")
    llm_default_model: str = "gemini-1.5-pro"
    llm_timeout_seconds: int = 90
    llm_max_retries: int = 3
    llm_retry_backoff_seconds: list = [10, 30, 90]

    # Google Cloud / Vertex AI Configuration
    gcp_project_id: Optional[str] = Field(default=None, description="GCP Project ID for Vertex AI")
    gcp_location: str = "us-central1"  # Vertex AI location
    google_application_credentials: str = "/app/application_default_credentials.json"

    # Task Configuration
    default_task_timeout_seconds: int = 300
    max_task_timeout_seconds: int = 600
    min_task_timeout_seconds: int = 30
    max_retry_attempts: int = 3
    max_context_size_bytes: int = 32768  # 32 KB

    # Queue Configuration
    max_queue_depth_per_type: int = 1000
    scheduler_poll_interval_ms: int = 500

    # Agent Configuration
    agent_heartbeat_interval_seconds: int = 10
    agent_offline_threshold_seconds: int = 30
    min_agents_per_type: int = 2
    max_agents_per_type: int = 20
    scale_out_queue_depth_threshold: int = 50
    scale_out_duration_seconds: int = 120

    # Output Configuration
    max_generated_tests: int = 200

    # Agent type specific timeouts
    agent_timeouts: Dict[str, int] = Field(
        default={
            "PARSE_STORY": 60,
            "CLASSIFY_DOMAIN": 60,
            "FETCH_CONTEXT": 120,
            "GENERATE_TESTS": 180,
            "VALIDATE_TESTS": 120,
            "ANALYSE_COVERAGE": 90,
        },
        description="Timeout in seconds per agent type",
    )

    model_config = {
        "env_prefix": "AGENT_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
