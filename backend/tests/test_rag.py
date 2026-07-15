from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.db.session import session_factory
from app.models.policy_clause import PolicyClause
from app.rag.embeddings import HashingEmbeddings
from app.rag.ingest import ingest_corpus, load_corpus, parse_clauses
from app.rag.retrieve import PgVectorRetriever

# Ingestion/retrieval tests run against a SYNTHETIC corpus in a namespaced
# category ("autotest"), never the live configs/policies corpus: ingest upserts
# by clause_id, so re-embedding the real clauses with the test embedder would
# silently corrupt the vector store the running app (and the eval harness)
# retrieves from. Found live: a green pytest run zeroed out eval retrieval.
_TEST_CORPUS = """# Test Auto Policy

## TAUTO-001: Collision coverage
Collision damage to the insured vehicle is covered when the vehicle collides
with another vehicle or object, including rear-end collision.

## TAUTO-002: Deductible
A deductible of $500 applies to each collision claim payout.

## TAUTO-003: Theft
Theft of the insured vehicle is covered when a police report is filed.
"""


def test_parse_clauses_extracts_ids_and_bodies() -> None:
    markdown = (
        "# Title\n\n"
        "## AUTO-001: Collision coverage\n"
        "Collision damage is covered.\n\n"
        "## AUTO-002: Deductible\n"
        "A deductible applies.\n"
    )
    clauses = parse_clauses(markdown, category="auto")
    assert [c.clause_id for c in clauses] == ["AUTO-001", "AUTO-002"]
    assert clauses[0].category == "auto"
    assert "Collision damage is covered." in clauses[0].text
    assert clauses[0].text.startswith("Collision coverage.")


def test_load_corpus_reads_all_policy_files() -> None:
    clauses = load_corpus()
    categories = {c.category for c in clauses}
    assert categories == {"auto", "home", "health"}
    assert len(clauses) >= 20
    assert len({c.clause_id for c in clauses}) == len(clauses)  # ids unique


@pytest.fixture
async def _ingested_corpus(tmp_path: Path) -> AsyncIterator[int]:
    (tmp_path / "autotest.md").write_text(_TEST_CORPUS, encoding="utf-8")
    count = await ingest_corpus(str(tmp_path), embedder=HashingEmbeddings(dim=384))
    yield count
    async with session_factory() as session:
        await session.execute(delete(PolicyClause).where(PolicyClause.category == "autotest"))
        await session.commit()


async def test_ingest_is_idempotent(_ingested_corpus: int, tmp_path: Path) -> None:
    count_again = await ingest_corpus(str(tmp_path), embedder=HashingEmbeddings(dim=384))
    assert count_again == _ingested_corpus == 3


async def test_retrieval_ranks_matching_clauses_first(_ingested_corpus: int) -> None:
    retriever = PgVectorRetriever(
        embedder=HashingEmbeddings(dim=384), top_k=5, min_similarity=0.05
    )
    evidence = await retriever.retrieve(
        "auto insurance claim rear-end collision vehicle damage repair",
        category="autotest",
    )
    assert evidence, "expected at least one clause above the similarity floor"
    assert evidence[0].clause_id == "TAUTO-001"
    # results ordered by similarity descending
    similarities = [e.similarity for e in evidence]
    assert similarities == sorted(similarities, reverse=True)


async def test_retrieval_filters_below_similarity_floor(_ingested_corpus: int) -> None:
    retriever = PgVectorRetriever(
        embedder=HashingEmbeddings(dim=384), top_k=5, min_similarity=0.99
    )
    evidence = await retriever.retrieve(
        "zzzz qqqq xyzzy plugh unrelated gibberish", category="autotest"
    )
    assert evidence == []


async def test_category_scoping_recovers_paraphrased_claims(_ingested_corpus: int) -> None:
    retriever = PgVectorRetriever(
        embedder=HashingEmbeddings(dim=384), top_k=5, min_similarity=0.05
    )
    # Regression for a live failure: an LLM paraphrase of a collision claim
    # ("rear-ended ... bumper and trunk", never the word "collision") pulled
    # cross-domain and adjacent clauses ahead of the collision clause without
    # scoping.
    query = (
        "auto insurance claim Claimant was rear-ended while stopped at a red light, "
        "causing damage to the rear bumper and trunk. claimed amount 3450.00"
    )
    scoped = await retriever.retrieve(query, category="autotest")
    assert scoped, "expected test clauses above the similarity floor"
    assert all(e.clause_id.startswith("TAUTO-") for e in scoped)
    assert "TAUTO-001" in [e.clause_id for e in scoped]
