import pytest

from app.rag.embeddings import HashingEmbeddings
from app.rag.ingest import ingest_corpus, load_corpus, parse_clauses
from app.rag.retrieve import PgVectorRetriever


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
async def _ingested_corpus() -> int:
    return await ingest_corpus(embedder=HashingEmbeddings(dim=384))


async def test_ingest_is_idempotent(_ingested_corpus: int) -> None:
    count_again = await ingest_corpus(embedder=HashingEmbeddings(dim=384))
    assert count_again == _ingested_corpus


async def test_retrieval_ranks_matching_category_clauses_first(_ingested_corpus: int) -> None:
    retriever = PgVectorRetriever(
        embedder=HashingEmbeddings(dim=384), top_k=5, min_similarity=0.05
    )
    evidence = await retriever.retrieve(
        "auto insurance claim rear-end collision vehicle damage repair"
    )
    assert evidence, "expected at least one clause above the similarity floor"
    assert evidence[0].clause_id.startswith("AUTO-")
    # results ordered by similarity descending
    similarities = [e.similarity for e in evidence]
    assert similarities == sorted(similarities, reverse=True)


async def test_retrieval_filters_below_similarity_floor(_ingested_corpus: int) -> None:
    retriever = PgVectorRetriever(
        embedder=HashingEmbeddings(dim=384), top_k=5, min_similarity=0.99
    )
    evidence = await retriever.retrieve("zzzz qqqq xyzzy plugh unrelated gibberish")
    assert evidence == []
