"""add auth model storage and authorization revision

Revision ID: 20260405_000008
Revises: 20260405_000007
Create Date: 2026-04-05 00:08:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260405_000008"
down_revision = "20260405_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("authorization_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "auth_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_text", sa.Text(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("compiled_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_auth_models_tenant"),
    )


def downgrade() -> None:
    op.drop_table("auth_models")
    op.drop_column("tenants", "authorization_revision")
