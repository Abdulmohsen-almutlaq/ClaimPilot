"""cases.human_decision + override tracking for the M7 approval workflow

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("human_decision", sa.String(16), nullable=True))
    op.add_column("cases", sa.Column("decision_notes", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("decided_by", sa.String(255), nullable=True))
    op.add_column("cases", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    # NULL = no human decision yet; True/False only ever set together with
    # human_decision, so override_rate can use COUNT(overridden) as its denominator.
    op.add_column("cases", sa.Column("overridden", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("cases", "overridden")
    op.drop_column("cases", "decided_at")
    op.drop_column("cases", "decided_by")
    op.drop_column("cases", "decision_notes")
    op.drop_column("cases", "human_decision")
