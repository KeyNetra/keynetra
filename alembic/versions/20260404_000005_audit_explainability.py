from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260404_000005"
down_revision = "20260404_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("evaluated_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "audit_logs",
        sa.Column("failed_conditions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "failed_conditions")
    op.drop_column("audit_logs", "evaluated_rules")
