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


@dataclass(frozen=True)
class EmbeddingsConfig:
    provider: str  # hashing | openai | local
    base_url: str | None
    model: str | None
    dim: int


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int
    min_similarity: float


@dataclass(frozen=True)
class GuardrailsConfig:
    pii_redaction: bool


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
    embeddings: EmbeddingsConfig
    retrieval: RetrievalConfig
    guardrails: GuardrailsConfig

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


def resolve_config_path(path: str) -> Path:
    """Resolve a configs/ path the same way regardless of caller: absolute paths
    pass through; relative ones anchor to the backend/ directory (matches
    Settings' env_file lookup), which is /app inside the containers."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    backend_dir = Path(__file__).resolve().parents[2]
    return (backend_dir / candidate).resolve()


@lru_cache
def load_models_config(path: str | None = None) -> ModelsConfig:
    config_path = resolve_config_path(path or get_settings().models_config_path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    providers = {
        name: ProviderConfig(
            base_url=cfg["base_url"], model=cfg["model"], fallback_model=cfg["fallback_model"]
        )
        for name, cfg in raw["providers"].items()
    }
    raw_embeddings = raw.get("embeddings") or {}
    raw_retrieval = raw.get("retrieval") or {}
    raw_guardrails = raw.get("guardrails") or {}
    return ModelsConfig(
        default_provider=raw["provider"],
        providers=providers,
        defaults=raw["defaults"],
        node_overrides=raw.get("nodes", {}),
        prompt_versions=raw.get("prompts", {}),
        embeddings=EmbeddingsConfig(
            provider=str(raw_embeddings.get("provider", "hashing")),
            base_url=raw_embeddings.get("base_url"),
            model=raw_embeddings.get("model"),
            dim=int(raw_embeddings.get("dim", 384)),
        ),
        retrieval=RetrievalConfig(
            top_k=int(raw_retrieval.get("top_k", 5)),
            min_similarity=float(raw_retrieval.get("min_similarity", 0.05)),
        ),
        guardrails=GuardrailsConfig(
            pii_redaction=bool(raw_guardrails.get("pii_redaction", True)),
        ),
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
