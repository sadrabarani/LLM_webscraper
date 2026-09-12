from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from webtester.domain.models import ScopePolicy


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    webtester_authorized: bool = False
    webtester_data_dir: Path = Path("./data")
    webtester_headless: bool = True
    webtester_llm_provider: str = "groq"

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/auto:free"

    database_url: str = Field(
        default="postgresql+psycopg://webtester:webtester@localhost:5432/webtester"
    )
    persist_postgres: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


def scope_from_url(
    url: str,
    *,
    max_actions: int,
    max_runtime_seconds: int,
    max_llm_calls: int,
    authorized: bool,
) -> ScopePolicy:
    host = urlparse(url).hostname or ""
    return ScopePolicy(
        allowed_domains=[host] if host else [],
        max_actions=max_actions,
        max_runtime_seconds=max_runtime_seconds,
        max_llm_calls=max_llm_calls,
        authorized=authorized,
        require_explicit_authorization=True,
    )
