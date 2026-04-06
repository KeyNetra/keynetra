from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260404_000004"
down_revision = "20260404_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("relation", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.String(length=128), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "subject_type",
            "subject_id",
            "relation",
            "object_type",
            "object_id",
            name="uq_relationships_tuple",
        ),
    )
    op.create_index(
        "ix_relationships_lookup",
        "relationships",
        ["tenant_id", "subject_type", "subject_id", "relation"],
        unique=False,
    )
    op.create_index("ix_relationships_tenant_id", "relationships", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_relationships_tenant_id", table_name="relationships")
    op.drop_index("ix_relationships_lookup", table_name="relationships")
    op.drop_table("relationships")
