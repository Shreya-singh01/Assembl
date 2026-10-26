"""Application settings, read from environment variables (see ../.env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # MongoDB. "memory://" uses an in-process mock (tests / zero-install demo; data is lost on restart).
    mongodb_url: str = "memory://"
    mongodb_db: str = "assembl"

    # Optional Redis for rate limiting / multi-instance Socket.IO. Empty = in-process fallback.
    redis_url: str = ""

    # Sessions & cookies
    session_cookie_name: str = "assembl_session"
    session_ttl_hours: int = 24 * 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = "http://localhost:5173"

    # Accounts whose e-mail is listed here get the "admin" role (research dashboard).
    admin_emails: str = ""

    # Embeddings
    embedding_backend: Literal["sbert", "hashing"] = "sbert"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Limits
    login_rate_limit: int = Field(10, description="login attempts per window per IP+email")
    login_rate_window_s: int = 300
    message_rate_limit: int = 30
    message_rate_window_s: int = 60
    max_message_chars: int = 4000
    recommendation_timeout_s: float = 30.0

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    def check_production(self) -> list[str]:
        problems = []
        if self.environment == "production":
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true in production")
            if self.mongodb_url.startswith("memory://"):
                problems.append("MONGODB_URL must point at a real MongoDB deployment in production")
            if self.cookie_samesite == "none" and not self.cookie_secure:
                problems.append("SameSite=None cookies require Secure")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
