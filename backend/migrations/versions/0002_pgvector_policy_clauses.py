"""pgvector extension + policy_clauses table for RAG evidence retrieval

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match app.models.policy_clause.EMBEDDING_DIM.
EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "policy_clauses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clause_id", sa.String(32), nullable=False, unique=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_policy_clauses_clause_id", "policy_clauses", ["clause_id"])
    op.create_index("ix_policy_clauses_category", "policy_clauses", ["category"])
    # Corpus is clause-granular and small (dozens of rows); exact scan beats an
    # ivfflat/hnsw index at this scale, so no ANN index on purpose.


def downgrade() -> None:
    op.drop_table("policy_clauses")
    op.execute("DROP EXTENSION IF EXISTS vector")
