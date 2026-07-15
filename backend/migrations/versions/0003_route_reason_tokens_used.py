"""cases.route_reason + cases.tokens_used for routing and token budgets

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("route_reason", sa.String(64), nullable=True))
    op.add_column(
        "cases", sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("cases", "tokens_used")
    op.drop_column("cases", "route_reason")
