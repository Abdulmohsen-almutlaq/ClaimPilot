import asyncio
import hashlib
import math
import re
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.llm.registry import EmbeddingsConfig, load_models_config

DEFAULT_FASTEMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingBackend(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbeddings:
    """Deterministic, dependency-free signed feature hashing over word unigrams and
    character trigrams, L2-normalized.

    This is lexical, not semantic: it scores texts by shared words/spellings.
    It stays as the test/CI backend because it is free, offline, and bit-for-bit
    reproducible; the app default is the `fastembed` transformer backend below.
    """

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _features(self, text: str) -> list[str]:
        words = _TOKEN_RE.findall(text.lower())
        features = list(words)
        for word in words:
            padded = f"#{word}#"
            features.extend(padded[i : i + 3] for i in range(len(padded) - 2))
        return features

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature in self._features(text):
            digest = hashlib.md5(feature.encode()).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


class FastEmbedEmbeddings:
    """Semantic embeddings from a Hugging Face sentence-transformer, executed
    locally via ONNX Runtime (Qdrant's open-source `fastembed` — no torch, no GPU,
    no API key). The default model, all-MiniLM-L6-v2, emits 384-dim vectors that
    fit the existing pgvector column.

    The model is loaded lazily on first use so that constructing the backend
    (e.g. in config-wiring tests) never touches the network or disk cache."""

    def __init__(self, *, model: str, dim: int) -> None:
        self._model_name = model
        self._model: Any = None
        self.dim = dim

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
        return [[float(x) for x in vec] for vec in self._model.embed(texts)]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # ONNX inference is CPU-bound and synchronous; keep the event loop free.
        return await asyncio.to_thread(self._encode, texts)


class OpenAICompatibleEmbeddings:
    """Dense embeddings from any OpenAI-compatible /embeddings endpoint
    (OpenAI itself, Ollama, vLLM, LM Studio...)."""

    def __init__(
        self, *, base_url: str, model: str, api_key: str | None, dim: int, timeout: float = 30.0
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self._api_key or 'not-needed'}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/embeddings",
                headers=headers,
                json={"model": self._model, "input": texts},
            )
        resp.raise_for_status()
        payload: dict[str, Any] = resp.json()
        # /embeddings responses preserve input order via the index field.
        items = sorted(payload["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in items]


def build_embedding_backend(config: EmbeddingsConfig | None = None) -> EmbeddingBackend:
    cfg = config or load_models_config().embeddings
    if cfg.provider == "hashing":
        return HashingEmbeddings(dim=cfg.dim)
    if cfg.provider == "fastembed":
        return FastEmbedEmbeddings(model=cfg.model or DEFAULT_FASTEMBED_MODEL, dim=cfg.dim)
    if not cfg.base_url or not cfg.model:
        raise ValueError(
            f"embeddings provider '{cfg.provider}' requires base_url and model in models.yaml"
        )
    settings = get_settings()
    api_key = settings.openai_api_key if cfg.provider == "openai" else settings.local_llm_api_key
    return OpenAICompatibleEmbeddings(
        base_url=cfg.base_url, model=cfg.model, api_key=api_key, dim=cfg.dim
    )
