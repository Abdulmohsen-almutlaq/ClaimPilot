from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    model: str
    fallback_model: str


@dataclass(frozen=True)
class NodeConfig:
    provider: str
    temperature: float
    timeout_seconds: float
    max_retries: int
    use_fallback_model: bool


class UnknownProviderError(Exception):
    pass


class UnknownPromptError(Exception):
    pass


@dataclass(frozen=True)
class ModelsConfig:
    default_provider: str
    providers: dict[str, ProviderConfig]
    defaults: dict[str, Any]
    node_overrides: dict[str, dict[str, Any]]
    prompt_versions: dict[str, str]

    def provider(self, name: str) -> ProviderConfig:
        try:
            return self.providers[name]
        except KeyError as exc:
            raise UnknownProviderError(f"unknown LLM provider: {name}") from exc

    def resolve_node(self, node: str) -> NodeConfig:
        overrides = self.node_overrides.get(node, {})
        return NodeConfig(
            provider=str(overrides.get("provider", self.default_provider)),
            temperature=float(overrides.get("temperature", self.defaults["temperature"])),
            timeout_seconds=float(
                overrides.get("timeout_seconds", self.defaults["timeout_seconds"])
            ),
            max_retries=int(overrides.get("max_retries", self.defaults["max_retries"])),
            use_fallback_model=bool(overrides.get("use_fallback_model", False)),
        )

    def prompt_version(self, name: str) -> str:
        try:
            return self.prompt_versions[name]
        except KeyError as exc:
            raise UnknownPromptError(f"no active prompt version configured for: {name}") from exc


def _resolve_config_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    # app/llm/registry.py -> app/llm -> app -> backend; models_config_path is
    # relative to the backend/ working directory (matches Settings' env_file lookup).
    backend_dir = Path(__file__).resolve().parents[2]
    return (backend_dir / candidate).resolve()


@lru_cache
def load_models_config(path: str | None = None) -> ModelsConfig:
    config_path = _resolve_config_path(path or get_settings().models_config_path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    providers = {
        name: ProviderConfig(
            base_url=cfg["base_url"], model=cfg["model"], fallback_model=cfg["fallback_model"]
        )
        for name, cfg in raw["providers"].items()
    }
    return ModelsConfig(
        default_provider=raw["provider"],
        providers=providers,
        defaults=raw["defaults"],
        node_overrides=raw.get("nodes", {}),
        prompt_versions=raw.get("prompts", {}),
    )


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class PromptNotFoundError(Exception):
    pass


@lru_cache
def load_prompt(name: str, version: str) -> str:
    path = _PROMPTS_DIR / f"{name}.{version}.md"
    if not path.exists():
        raise PromptNotFoundError(f"no prompt file for {name} {version}")
    return path.read_text(encoding="utf-8").strip()
