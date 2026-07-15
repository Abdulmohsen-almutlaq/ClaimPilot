import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.db.session import session_factory
from app.llm.registry import resolve_config_path
from app.models.policy_clause import PolicyClause
from app.rag.embeddings import EmbeddingBackend, build_embedding_backend

# Chunking is clause-granular on purpose: each "## CLAUSE-ID: title" block becomes
# one embedded row, so retrieval results carry citable clause ids end-to-end.
_CLAUSE_RE = re.compile(r"^##\s*(?P<id>[A-Z]+-\d+):\s*(?P<title>.+)$", re.MULTILINE)

DEFAULT_CORPUS_DIR = "../configs/policies"


@dataclass(frozen=True)
class ParsedClause:
    clause_id: str
    category: str
    title: str
    text: str


def parse_clauses(markdown: str, *, category: str) -> list[ParsedClause]:
    matches = list(_CLAUSE_RE.finditer(markdown))
    clauses: list[ParsedClause] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[match.end() : end].strip()
        title = match.group("title").strip()
        clauses.append(
            ParsedClause(
                clause_id=match.group("id"),
                category=category,
                title=title,
                text=f"{title}. {body}",
            )
        )
    return clauses


def load_corpus(corpus_dir: str = DEFAULT_CORPUS_DIR) -> list[ParsedClause]:
    root = resolve_config_path(corpus_dir)
    clauses: list[ParsedClause] = []
    for path in sorted(root.glob("*.md")):
        category = Path(path).stem
        clauses.extend(parse_clauses(path.read_text(encoding="utf-8"), category=category))
    return clauses


async def ingest_corpus(
    corpus_dir: str = DEFAULT_CORPUS_DIR, *, embedder: EmbeddingBackend | None = None
) -> int:
    """Embed every policy clause and upsert by clause_id (idempotent re-runs)."""
    embedder = embedder or build_embedding_backend()
    clauses = load_corpus(corpus_dir)
    if not clauses:
        return 0

    vectors = await embedder.embed([clause.text for clause in clauses])

    async with session_factory() as session:
        for clause, vector in zip(clauses, vectors, strict=True):
            stmt = (
                insert(PolicyClause)
                .values(
                    clause_id=clause.clause_id,
                    category=clause.category,
                    title=clause.title,
                    text=clause.text,
                    embedding=vector,
                )
                .on_conflict_do_update(
                    index_elements=["clause_id"],
                    set_={
                        "category": clause.category,
                        "title": clause.title,
                        "text": clause.text,
                        "embedding": vector,
                    },
                )
            )
            await session.execute(stmt)
        await session.commit()
    return len(clauses)


def main() -> None:
    count = asyncio.run(ingest_corpus())
    print(f"ingested {count} policy clauses")


if __name__ == "__main__":
    main()
