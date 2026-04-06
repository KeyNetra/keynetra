"""add resource acl table

Revision ID: 20260405_000007
Revises: 20260405_000006
Create Date: 2026-04-05 00:07:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260405_000007"
down_revision = "20260405_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_acl",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_resource_acl_lookup",
        "resource_acl",
        ["tenant_id", "resource_type", "resource_id", "action"],
    )
    op.create_index(
        "ix_resource_acl_subject", "resource_acl", ["tenant_id", "subject_type", "subject_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_resource_acl_subject", table_name="resource_acl")
    op.drop_index("ix_resource_acl_lookup", table_name="resource_acl")
    op.drop_table("resource_acl")
