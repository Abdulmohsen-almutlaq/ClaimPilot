"""policies table: CRM data folded into the app database (single-DB stack)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_number", sa.String(64), nullable=False),
        sa.Column("customer_id", sa.String(64), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("coverage_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_date", sa.String(10), nullable=False),
        sa.Column("expiry_date", sa.String(10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_policies_policy_number", "policies", ["policy_number"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_policies_policy_number", table_name="policies")
    op.drop_table("policies")
