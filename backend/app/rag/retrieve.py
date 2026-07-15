from typing import Protocol

from sqlalchemy import select

from app.db.session import session_factory
from app.llm.registry import load_models_config
from app.models.policy_clause import PolicyClause
from app.pipeline.schemas import Evidence
from app.rag.embeddings import EmbeddingBackend, build_embedding_backend


class Retriever(Protocol):
    async def retrieve(self, query: str, *, category: str | None = None) -> list[Evidence]: ...


class PgVectorRetriever:
    def __init__(
        self, *, embedder: EmbeddingBackend, top_k: int, min_similarity: float
    ) -> None:
        self._embedder = embedder
        self._top_k = top_k
        self._min_similarity = min_similarity

    async def retrieve(self, query: str, *, category: str | None = None) -> list[Evidence]:
        query_vec = (await self._embedder.embed([query]))[0]
        distance = PolicyClause.embedding.cosine_distance(query_vec).label("distance")
        stmt = (
            select(PolicyClause, distance)
            .order_by(distance)
            .limit(self._top_k)
        )
        if category is not None:
            # The claim's category is validated structured data by the time we get
            # here — scoping the search to that category's clauses removes cross-
            # domain noise that similarity alone can't (found live: an auto claim
            # phrased as "rear-ended... bumper" pulled theft/rental clauses ahead
            # of the collision clause and forced a needless needs_info draft).
            stmt = stmt.where(PolicyClause.category == category)
        async with session_factory() as session:
            rows = (await session.execute(stmt)).all()

        evidence: list[Evidence] = []
        for clause, dist in rows:
            similarity = 1.0 - float(dist)
            if similarity < self._min_similarity:
                continue
            evidence.append(
                Evidence(clause_id=clause.clause_id, text=clause.text, similarity=similarity)
            )
        return evidence


def build_default_retriever() -> PgVectorRetriever:
    config = load_models_config()
    return PgVectorRetriever(
        embedder=build_embedding_backend(config.embeddings),
        top_k=config.retrieval.top_k,
        min_similarity=config.retrieval.min_similarity,
    )
