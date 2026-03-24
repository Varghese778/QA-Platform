"""Configuration settings for Auth & Access Control module."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Auth & Access Control Service"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/qa_platform",
        description="PostgreSQL connection string (async)",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for token denylist",
    )

    # JWT Configuration
    jwt_issuer: str = "https://auth.qaplatform.internal"
    jwt_audience: str = "qaplatform-api"
    jwt_access_token_ttl_seconds: int = 900  # 15 minutes
    jwt_refresh_token_ttl_days: int = 7
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: Optional[str] = None  # Path to RS256 private key PEM
    jwt_public_key_path: Optional[str] = None  # Path to RS256 public key PEM
    jwt_clock_skew_seconds: int = 5  # ±5 seconds tolerance

    # OIDC Configuration (mock for MVP)
    oidc_issuer: str = "https://idp.example.com"
    oidc_audience: str = "qa-platform-client"

    # Security
    api_key_length: int = 64  # 64-character hex string
    invitation_token_ttl_days: int = 7
    brute_force_max_attempts: int = 10
    brute_force_window_minutes: int = 10
    brute_force_lockout_minutes: int = 30

    class Config:
        env_prefix = "AUTH_"
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
