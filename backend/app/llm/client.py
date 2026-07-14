import asyncio
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.llm.adapters import ChatAdapter, LangChainAdapter
from app.llm.pricing import estimate_cost_usd
from app.llm.registry import ModelsConfig, load_models_config

ChatAdapterFactory = Callable[..., ChatAdapter]


class LLMCallFailed(Exception):
    pass


@dataclass(frozen=True)
class LLMResult[SchemaT: BaseModel]:
    data: SchemaT
    model_used: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int
    attempts: int


def _backoff_delay(attempt: int) -> float:
    base: int = min(2 ** (attempt - 1), 8)
    return base + random.uniform(0, 0.5)


class LLMClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        models_config: ModelsConfig | None = None,
        adapter_factory: ChatAdapterFactory = LangChainAdapter,
    ) -> None:
        self._settings = settings or get_settings()
        self.models_config = models_config or load_models_config()
        self._adapter_factory = adapter_factory

    def _api_key_for(self, provider: str) -> str | None:
        if provider == "anthropic":
            return self._settings.anthropic_api_key
        if provider == "openai":
            return self._settings.openai_api_key
        return self._settings.local_llm_api_key

    def _build_adapter(self, node: str, *, use_fallback: bool) -> tuple[ChatAdapter, str]:
        node_cfg = self.models_config.resolve_node(node)
        provider_cfg = self.models_config.provider(node_cfg.provider)
        # A node's own cost-control choice (e.g. QA always uses the cheap model) and a
        # reliability fallback (repeated primary failure) both resolve to fallback_model.
        effective_use_fallback = use_fallback or node_cfg.use_fallback_model
        model_name = provider_cfg.fallback_model if effective_use_fallback else provider_cfg.model
        adapter = self._adapter_factory(
            provider=node_cfg.provider,
            model=model_name,
            base_url=provider_cfg.base_url,
            api_key=self._api_key_for(node_cfg.provider),
            temperature=node_cfg.temperature,
            timeout=node_cfg.timeout_seconds,
        )
        return adapter, model_name

    async def generate_structured[SchemaT: BaseModel](
        self,
        *,
        node: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
    ) -> LLMResult[SchemaT]:
        node_cfg = self.models_config.resolve_node(node)
        last_exc: Exception | None = None

        for attempt in range(1, node_cfg.max_retries + 1):
            use_fallback = attempt == node_cfg.max_retries and node_cfg.max_retries > 1
            adapter, model_name = self._build_adapter(node, use_fallback=use_fallback)

            start = time.monotonic()
            try:
                parsed, usage = await asyncio.wait_for(
                    adapter.generate(
                        system_prompt=system_prompt, user_prompt=user_prompt, schema=schema
                    ),
                    timeout=node_cfg.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 — provider errors, timeouts, and
                # schema-validation failures are all retried the same way on purpose.
                last_exc = exc
                if attempt < node_cfg.max_retries:
                    await asyncio.sleep(_backoff_delay(attempt))
                continue

            latency_ms = int((time.monotonic() - start) * 1000)
            cost = estimate_cost_usd(model_name, usage.input_tokens, usage.output_tokens)
            return LLMResult(
                data=cast(SchemaT, parsed),
                model_used=model_name,
                prompt_version=prompt_version,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                attempts=attempt,
            )

        raise LLMCallFailed(
            f"node={node} exhausted {node_cfg.max_retries} attempts"
        ) from last_exc
