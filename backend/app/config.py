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

    # LLM secrets only. Provider choice, model names, endpoints, temperature, and
    # token budgets live in configs/models.yaml — never duplicate them here.
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    local_llm_api_key: str | None = None  # some local OpenAI-compatible servers require one

    models_config_path: str = "../configs/models.yaml"

    # External services (wired in later milestones)
    crm_base_url: str = "http://localhost:8001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
