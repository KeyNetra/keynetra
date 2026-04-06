from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260404_000002"
down_revision = "20260404_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_key", sa.String(length=64), nullable=False, unique=True),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("principal_type", sa.String(length=32), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("user", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column("matched_policies", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"], unique=False)

    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("policy_key", sa.String(length=64), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "policy_key", name="uq_policies_tenant_key"),
    )
    op.create_index("ix_policies_tenant_id", "policies", ["tenant_id"], unique=False)

    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            sa.Integer(),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False, server_default="deny"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("conditions", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.UniqueConstraint("policy_id", "version", name="uq_policy_versions_policy_version"),
    )
    op.create_index(
        "ix_policy_versions_tenant_action_priority",
        "policy_versions",
        ["tenant_id", "action", "priority"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_policy_versions_tenant_action_priority", table_name="policy_versions")
    op.drop_table("policy_versions")
    op.drop_index("ix_policies_tenant_id", table_name="policies")
    op.drop_table("policies")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("tenants")
