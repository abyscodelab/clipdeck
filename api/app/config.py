"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./clipdeck.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Security
    CLIPDECK_MASTER_KEY: str = ""  # Fernet key for encrypting provider keys
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Media storage
    MEDIA_STORAGE_PATH: str = "./media"

    # Supabase (Backend & Storage)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_STORAGE_BUCKET_CLIPS: str = "clips"
    SUPABASE_STORAGE_BUCKET_THUMBNAILS: str = "thumbnails"
    USE_SUPABASE_STORAGE: bool = False

    # App
    APP_NAME: str = "ClipDeck"
    DEBUG: bool = False
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "changeme"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
