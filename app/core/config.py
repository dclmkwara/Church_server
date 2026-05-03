"""
Application configuration settings.
"""
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "DCLM Server"
    VERSION: str = "1.3.0"
    DEBUG: bool = False  # NEVER True in production
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str
    SYNC_DATABASE_URL: Optional[str] = None
    PG_VERSION: str = "16.0"

    # Connection pool, tune per environment / DB plan.
    # Small hosted Postgres plans often cap at about 20-25 total connections.
    # pool_size=5 + max_overflow=10 = max 15 connections per worker process.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 3600

    # Email (Optional - for password reset)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None

    # CORS
    BACKEND_CORS_ORIGINS: Optional[str] = None  # JSON array or comma-separated

    # Edit Window Settings (in days)
    MAX_EDIT_WINDOW_DAYS: int = 7
    EDIT_WARNING_THRESHOLD_HOURS: int = 48

    # Idempotency
    IDEMPOTENCY_KEY_TTL_DAYS: int = 7

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: list[str] = Field(default_factory=lambda: ["image/jpeg", "image/png", "image/webp"])
    ALLOWED_VIDEO_TYPES: list[str] = Field(default_factory=lambda: ["video/mp4", "video/webm"])

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long. "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return v

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        value = str(v).strip().lower()
        if value in {"true", "1", "yes", "y", "debug"}:
            return True
        if value in {"false", "0", "no", "n", "release", "prod", "production"}:
            return False
        return bool(value)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def sync_database_url(self) -> str:
        source_url = self.SYNC_DATABASE_URL or self.DATABASE_URL
        if source_url.startswith("postgresql+psycopg2://"):
            return source_url
        if source_url.startswith("postgresql+asyncpg://"):
            return source_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        if source_url.startswith("postgresql+psycopg://"):
            return source_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        if source_url.startswith("postgres://"):
            return source_url.replace("postgres://", "postgresql+psycopg2://", 1)
        if source_url.startswith("postgresql://"):
            return source_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return source_url


settings = Settings()
