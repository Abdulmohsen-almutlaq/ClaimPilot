from typing import NamedTuple, Protocol

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr


class TokenUsage(NamedTuple):
    input_tokens: int
    output_tokens: int


class ChatAdapter(Protocol):
    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]: ...


class StructuredOutputError(Exception):
    pass


class LangChainAdapter:
    """Thin wrapper around LangChain chat models. Anthropic uses its native SDK
    integration; OpenAI and any local server both speak the OpenAI protocol, so
    "local" reuses ChatOpenAI pointed at a self-hosted base_url (Ollama, vLLM, ...).
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key: str | None,
        temperature: float,
        timeout: float,
    ) -> None:
        secret_key = SecretStr(api_key) if api_key else SecretStr("not-needed")
        self._provider = provider
        if provider == "anthropic":
            self._model: ChatAnthropic | ChatOpenAI = ChatAnthropic(
                model_name=model,
                api_key=secret_key,
                base_url=base_url,
                temperature=temperature,
                timeout=timeout,
                stop=None,
            )
        else:
            self._model = ChatOpenAI(
                model=model,
                api_key=secret_key,
                base_url=base_url,
                temperature=temperature,
                timeout=timeout,
            )

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        if self._provider == "anthropic":
            structured = self._model.with_structured_output(schema, include_raw=True)
        else:
            # Pin function-calling for OpenAI-compatible providers (DeepSeek, Ollama,
            # vLLM...): LangChain picks a structured-output method by sniffing the
            # model name, and non-OpenAI models can get routed to OpenAI-only
            # json_schema response_format, which those APIs reject.
            structured = self._model.with_structured_output(
                schema, include_raw=True, method="function_calling"
            )
        result = await structured.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        if not isinstance(result, dict) or result.get("parsed") is None:
            raise StructuredOutputError("model output failed schema validation")

        parsed = result["parsed"]
        raw = result.get("raw")
        usage_meta = getattr(raw, "usage_metadata", None) or {}
        usage = TokenUsage(
            input_tokens=int(usage_meta.get("input_tokens", 0)),
            output_tokens=int(usage_meta.get("output_tokens", 0)),
        )
        return parsed, usage
