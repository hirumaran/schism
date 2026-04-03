from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("SCHISM_APP_NAME", "schism"))
    api_prefix: str = field(default_factory=lambda: os.getenv("SCHISM_API_PREFIX", "/api"))
    database_url: str = field(default_factory=lambda: os.getenv("SCHISM_DATABASE_URL", "sqlite:///./data/schism.db"))
    qdrant_url: str = field(default_factory=lambda: os.getenv("SCHISM_QDRANT_URL", "http://localhost:6333"))
    qdrant_collection: str = field(default_factory=lambda: os.getenv("SCHISM_QDRANT_COLLECTION", "schism_claims"))
    enable_qdrant: bool = field(default_factory=lambda: _bool_env("SCHISM_ENABLE_QDRANT", False))
    allowed_origins: list[str] = field(default_factory=lambda: _csv_env("SCHISM_ALLOWED_ORIGINS", "*"))
    default_max_results: int = field(default_factory=lambda: int(os.getenv("SCHISM_DEFAULT_MAX_RESULTS", "25")))
    contradiction_threshold: float = field(default_factory=lambda: float(os.getenv("SCHISM_CONTRADICTION_THRESHOLD", "0.6")))
    min_keyword_overlap: int = field(default_factory=lambda: int(os.getenv("SCHISM_MIN_KEYWORD_OVERLAP", "1")))
    local_embedding_model: str = field(
        default_factory=lambda: os.getenv("SCHISM_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    )
    user_agent: str = field(default_factory=lambda: os.getenv("SCHISM_USER_AGENT", "schism/0.1"))
    contact_email: str | None = field(default_factory=lambda: os.getenv("SCHISM_CONTACT_EMAIL") or None)
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("SCHISM_LLM_TIMEOUT_SECONDS", "45")))
    claim_concurrency: int = field(default_factory=lambda: int(os.getenv("SCHISM_CLAIM_CONCURRENCY", "4")))
    scoring_concurrency: int = field(default_factory=lambda: int(os.getenv("SCHISM_SCORING_CONCURRENCY", "4")))
    openai_claim_concurrency: int = field(default_factory=lambda: int(os.getenv("SCHISM_OPENAI_CLAIM_CONCURRENCY", "15")))
    anthropic_claim_concurrency: int = field(
        default_factory=lambda: int(os.getenv("SCHISM_ANTHROPIC_CLAIM_CONCURRENCY", "8"))
    )
    query_cache_hours: int = field(default_factory=lambda: int(os.getenv("SCHISM_QUERY_CACHE_HOURS", "6")))
    analysis_cache_hours: int = field(default_factory=lambda: int(os.getenv("SCHISM_ANALYSIS_CACHE_HOURS", "24")))
    job_timeout_minutes: int = field(default_factory=lambda: int(os.getenv("SCHISM_JOB_TIMEOUT_MINUTES", "15")))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", os.getenv("SCHISM_LOG_LEVEL", "INFO")))
    log_format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "human"))

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// URLs are supported in the local repository.")
        return Path(self.database_url.removeprefix(prefix))


@lru_cache
def get_settings() -> Settings:
    return Settings()
