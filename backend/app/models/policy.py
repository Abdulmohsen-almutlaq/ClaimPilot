import uuid
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Policy(Base, TimestampMixin):
    """CRM policy record. Formerly served by a separate mock-CRM service with
    its own Postgres; consolidated so the whole stack runs one database."""

    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    policy_number: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    coverage_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_date: Mapped[str] = mapped_column(String(10), nullable=False)
    expiry_date: Mapped[str] = mapped_column(String(10), nullable=False)
