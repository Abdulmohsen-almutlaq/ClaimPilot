import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="intake")
    document_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    qa_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    route_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    errors: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    token_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_versions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    prompt_versions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
