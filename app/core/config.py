"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "DCLM Server"
    VERSION: str = "1.3.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days (optional, for future use)
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour (optional, for future use)
    
    # Database
    DATABASE_URL: str
    PG_VERSION: str = "16.0"  # Optional, for documentation
    
    # Email (Optional - for password reset)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    
    # CORS
    BACKEND_CORS_ORIGINS: Optional[str] = None  # JSON string of origins
    
    # Edit Window Settings (in days)
    MAX_EDIT_WINDOW_DAYS: int = 7
    EDIT_WARNING_THRESHOLD_HOURS: int = 48
    
    # Idempotency
    IDEMPOTENCY_KEY_TTL_DAYS: int = 7
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100
    
    # File Upload (Supabase Storage)
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]
    ALLOWED_VIDEO_TYPES: list[str] = ["video/mp4", "video/webm"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()