import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# Fixed by migration 0002; changing embedding dimension requires a new migration.
EMBEDDING_DIM = 384


class PolicyClause(Base, TimestampMixin):
    __tablename__ = "policy_clauses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clause_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
