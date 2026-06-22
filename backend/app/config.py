"""
Brieflyy — Application Configuration
All environment variables and settings managed via Pydantic BaseSettings.
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

# Placeholder values from .env.example — treat as "not configured"
_GCP_PLACEHOLDERS = frozenset({
    "",
    "your-gcp-project-id",
    "your-project-id",
    "change-me",
})


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # FastAPI
    SECRET_KEY: str = "change-me-in-production-this-is-min-32-chars!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BACKEND_CORS_ORIGINS: str = "http://localhost:4200"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://brieflyy:password@localhost:5432/brieflyy_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GCS_BUCKET_NAME: str = "brieflyy-uploads"

    # Vertex AI / Gemini
    VERTEX_AI_LOCATION: str = "us-central1"
    GEMINI_MODEL: str = "gemini-1.5-pro"
    EMBEDDING_MODEL: str = "text-embedding-004"

    # Adzuna Job API
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ADZUNA_COUNTRY: str = "gb"

    # Additional job platform API keys (optional)
    FINDWORK_API_KEY: str = ""
    JOOBLE_API_KEY: str = ""
    WELLFOUND_API_TOKEN: str = ""
    INDEED_PUBLISHER_ID: str = ""
    INDEED_API_KEY: str = ""
    LINKEDIN_ACCESS_TOKEN: str = ""
    INTERNSHALA_API_KEY: str = ""

    # JSearch / RapidAPI
    JSEARCH_API_KEY: str = ""

    # Job aggregator (real APIs only)
    JOB_CACHE_TTL_SECONDS: int = 7200
    # Increase defaults to be more resilient to slow job APIs
    JOB_SEARCH_TIMEOUT_SECONDS: int = 20
    JOB_API_TIMEOUT_PER_SOURCE: int = 10
    JOB_SEARCH_MIN_RESULTS: int = 15
    ENABLED_JOB_SOURCES: str = "remoteok,remotive,arbeitnow"
    SKIP_SEMANTIC_RANKING: bool = True

    # Application
    MAX_JOBS_PER_SEARCH: int = 80
    CV_MAX_SIZE_MB: int = 5
    CV_PARSE_TIMEOUT_SECONDS: int = 10
    CV_PARSE_GEMINI_WARN_SECONDS: float = 5.0
    CV_CACHE_TTL_SECONDS: int = 86400
    SKIP_CV_EMBEDDINGS_ON_UPLOAD: bool = True
    CV_GEMINI_MAX_CHARS: int = 4000
    PIPELINE_TIMEOUT_SECONDS: int = 120
    PIPELINE_MAX_JOBS: int = 15
    PIPELINE_FAST_MODE: bool = True  # Default to fast mode (no Gemini required)
    UPLOAD_DIR: str = ""

    @property
    def enabled_job_sources_list(self) -> List[str]:
        if not self.ENABLED_JOB_SOURCES.strip():
            return []
        return [s.strip().lower() for s in self.ENABLED_JOB_SOURCES.split(",") if s.strip()]

    @property
    def enabled_job_sources_set(self) -> frozenset:
        return frozenset(self.enabled_job_sources_list)

    @property
    def gcp_enabled(self) -> bool:
        """True only when a real GCP project ID is configured."""
        return self.GOOGLE_CLOUD_PROJECT.strip() not in _GCP_PLACEHOLDERS

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]

    @property
    def upload_dir(self) -> str:
        """Writable directory for local file uploads (CVs, FAISS indexes)."""
        if self.UPLOAD_DIR:
            return self.UPLOAD_DIR
        if os.path.exists("/app/uploads"):
            return "/app/uploads"
        return str(_BACKEND_ROOT / "uploads")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
