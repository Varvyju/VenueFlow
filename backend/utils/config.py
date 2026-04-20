"""
VenueFlow – Centralised configuration.
All secrets come from environment variables; never hard-coded.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "VenueFlow"
    app_version: str = "1.0.0"
    debug: bool = False

    # Google Cloud
    gcp_project_id: str = "your-gcp-project-id"
    gcp_location: str = "us-central1"
    gemini_model: str = "gemini-2.0-flash-001"

    # Maps
    google_maps_api_key: str = ""

    # Firebase
    firebase_database_url: str = ""
    firebase_credentials_path: str = "serviceAccountKey.json"

    # Translation
    translation_cache_ttl: int = 3600  # seconds

    # Image processing
    max_image_size_px: int = 1024  # LANCZOS downscale target
    max_image_bytes: int = 5 * 1024 * 1024  # 5 MB

    # Rate limiting (requests per minute per IP)
    rate_limit_fan: int = 30
    rate_limit_staff: int = 60

    # JWT (for staff auth)
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    """Cached settings – instantiated once per process."""
    return Settings()
