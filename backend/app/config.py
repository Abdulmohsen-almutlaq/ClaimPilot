from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["dev", "test", "prod"] = "dev"

    # Auth
    secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Datastores
    database_url: str = "postgresql+asyncpg://claimpilot:claimpilot@localhost:5432/claimpilot"
    redis_url: str = "redis://localhost:6379/0"

    # LLM — provider-agnostic. Switch providers (including a local server) via env only.
    llm_provider: Literal["anthropic", "openai", "local"] = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_fallback_model: str = "claude-haiku-4-5-20251001"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Any OpenAI-compatible local server (Ollama, vLLM, LM Studio, etc.)
    local_llm_base_url: str | None = None
    local_llm_model: str | None = None
    local_llm_api_key: str | None = None

    # External services (wired in later milestones)
    crm_base_url: str = "http://localhost:8001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
