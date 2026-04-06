from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260404_000003"
down_revision = "20260404_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants", sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1")
    )


def downgrade() -> None:
    op.drop_column("tenants", "policy_version")
