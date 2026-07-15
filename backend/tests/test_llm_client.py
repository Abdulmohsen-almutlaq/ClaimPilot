from decimal import Decimal

import pytest
from pydantic import BaseModel

from app.llm.adapters import StructuredOutputError, TokenUsage
from app.llm.client import LLMCallFailed, LLMClient
from app.llm.registry import (
    EmbeddingsConfig,
    GuardrailsConfig,
    ModelsConfig,
    NodeConfig,
    ProviderConfig,
    RetrievalConfig,
)


class _Fields(BaseModel):
    value: str


def _make_models_config(*, max_retries: int = 3, use_fallback_model: bool = False) -> ModelsConfig:
    return ModelsConfig(
        default_provider="anthropic",
        providers={
            "anthropic": ProviderConfig(
                base_url="http://primary.example",
                model="primary-model",
                fallback_model="fallback-model",
            ),
        },
        defaults={"temperature": 0.0, "timeout_seconds": 5, "max_retries": max_retries},
        node_overrides={"intake": {"use_fallback_model": use_fallback_model}},
        prompt_versions={"intake_extract": "v1"},
        embeddings=EmbeddingsConfig(provider="hashing", base_url=None, model=None, dim=384),
        retrieval=RetrievalConfig(top_k=5, min_similarity=0.05),
        guardrails=GuardrailsConfig(pii_redaction=True),
    )


class _FakeAdapter:
    def __init__(self, **kwargs: object) -> None:
        self.model = kwargs["model"]

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        return _Fields(value="ok"), TokenUsage(input_tokens=100, output_tokens=50)


class _AlwaysFailsAdapter:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        raise StructuredOutputError("nope")


class _FailsOnceAdapter:
    calls: list[str] = []

    def __init__(self, **kwargs: object) -> None:
        self.model = str(kwargs["model"])

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        _FailsOnceAdapter.calls.append(self.model)
        if len(_FailsOnceAdapter.calls) == 1:
            raise StructuredOutputError("transient")
        return _Fields(value="ok"), TokenUsage(input_tokens=10, output_tokens=5)


async def test_generate_structured_success() -> None:
    client = LLMClient(models_config=_make_models_config(), adapter_factory=_FakeAdapter)
    result = await client.generate_structured(
        node="intake",
        prompt_version="v1",
        system_prompt="sys",
        user_prompt="usr",
        schema=_Fields,
    )
    assert result.data.value == "ok"
    assert result.model_used == "primary-model"
    assert result.attempts == 1
    assert result.cost_usd >= Decimal("0")


async def test_generate_structured_exhausts_retries_and_raises() -> None:
    client = LLMClient(
        models_config=_make_models_config(max_retries=2), adapter_factory=_AlwaysFailsAdapter
    )
    with pytest.raises(LLMCallFailed):
        await client.generate_structured(
            node="intake",
            prompt_version="v1",
            system_prompt="sys",
            user_prompt="usr",
            schema=_Fields,
        )


async def test_generate_structured_falls_back_on_last_attempt() -> None:
    _FailsOnceAdapter.calls = []
    client = LLMClient(
        models_config=_make_models_config(max_retries=2), adapter_factory=_FailsOnceAdapter
    )
    result = await client.generate_structured(
        node="intake",
        prompt_version="v1",
        system_prompt="sys",
        user_prompt="usr",
        schema=_Fields,
    )
    assert result.attempts == 2
    assert result.model_used == "fallback-model"
    assert _FailsOnceAdapter.calls == ["primary-model", "fallback-model"]


async def test_node_use_fallback_model_forces_cheap_model() -> None:
    client = LLMClient(
        models_config=_make_models_config(use_fallback_model=True), adapter_factory=_FakeAdapter
    )
    result = await client.generate_structured(
        node="intake",
        prompt_version="v1",
        system_prompt="sys",
        user_prompt="usr",
        schema=_Fields,
    )
    assert result.model_used == "fallback-model"


def test_resolve_node_unknown_provider_raises() -> None:
    config = _make_models_config()
    config.node_overrides["intake"]["provider"] = "does-not-exist"
    node_cfg = config.resolve_node("intake")
    assert isinstance(node_cfg, NodeConfig)
    with pytest.raises(Exception, match="unknown LLM provider"):
        config.provider(node_cfg.provider)
