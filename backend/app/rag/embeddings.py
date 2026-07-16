import asyncio
from typing import Any, Protocol

from app.llm.registry import EmbeddingsConfig, load_models_config

# The one supported model: 384-dim, symmetric (no query prefix), multilingual —
# Arabic (and 50+ other language) queries retrieve the English clause corpus
# cross-lingually. The pgvector column is vector(384); a different model needs
# a migration and a corpus re-ingest (make seed).
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingBackend(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbeddings:
    """Semantic embeddings from a Hugging Face sentence-transformer, executed
    locally via ONNX Runtime (Qdrant's open-source `fastembed` — no torch, no
    GPU, no API key).

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


def build_embedding_backend(config: EmbeddingsConfig | None = None) -> EmbeddingBackend:
    cfg = config or load_models_config().embeddings
    return FastEmbedEmbeddings(model=cfg.model or DEFAULT_MODEL, dim=cfg.dim)
