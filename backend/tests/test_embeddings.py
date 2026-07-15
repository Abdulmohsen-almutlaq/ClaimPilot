import math

import pytest

from app.llm.registry import EmbeddingsConfig
from app.rag.embeddings import FastEmbedEmbeddings, HashingEmbeddings, build_embedding_backend


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_hashing_embeddings_are_deterministic() -> None:
    embedder = HashingEmbeddings(dim=384)
    first = await embedder.embed(["rear-end collision damage"])
    second = await embedder.embed(["rear-end collision damage"])
    assert first == second


async def test_hashing_embeddings_are_normalized() -> None:
    embedder = HashingEmbeddings(dim=384)
    [vec] = await embedder.embed(["auto collision claim"])
    assert len(vec) == 384
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-9)


async def test_related_texts_score_higher_than_unrelated() -> None:
    embedder = HashingEmbeddings(dim=384)
    query, related, unrelated = await embedder.embed(
        [
            "vehicle collision accident damage claim",
            "Collision damage to the insured vehicle including rear-end collision",
            "Prescription medications on the policy formulary have tiered copayments",
        ]
    )
    assert _cosine(query, related) > _cosine(query, unrelated)


async def test_empty_text_embeds_to_zero_vector_without_error() -> None:
    embedder = HashingEmbeddings(dim=384)
    [vec] = await embedder.embed([""])
    assert all(v == 0.0 for v in vec)


def test_build_backend_default_is_fastembed_transformer() -> None:
    backend = build_embedding_backend()
    assert isinstance(backend, FastEmbedEmbeddings)
    assert backend.dim == 384
    # lazy: wiring the backend must not download/load the model (keeps CI offline)
    assert backend._model is None


def test_build_backend_hashing() -> None:
    config = EmbeddingsConfig(provider="hashing", base_url=None, model=None, dim=384)
    backend = build_embedding_backend(config)
    assert isinstance(backend, HashingEmbeddings)
    assert backend.dim == 384


def test_build_backend_openai_requires_endpoint() -> None:
    config = EmbeddingsConfig(provider="openai", base_url=None, model=None, dim=384)
    with pytest.raises(ValueError, match="requires base_url and model"):
        build_embedding_backend(config)
