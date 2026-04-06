"""add policy states and audit correlation id

Revision ID: 20260406_000009
Revises: 20260405_000008
Create Date: 2026-04-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260406_000009"
down_revision = "20260405_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy_versions",
        sa.Column("state", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.add_column(
        "audit_logs",
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "correlation_id")
    op.drop_column("policy_versions", "state")
