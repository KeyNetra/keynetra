"""initial_schema_v0

Revision ID: 20260407_000001
Revises:
Create Date: 2026-04-07
"""

from __future__ import annotations

from alembic import op

# Ensure all models are registered on Base metadata.
from keynetra.domain.models import acl as _acl  # noqa: F401
from keynetra.domain.models import audit as _audit  # noqa: F401
from keynetra.domain.models import auth_model as _auth_model  # noqa: F401
from keynetra.domain.models import idempotency as _idempotency  # noqa: F401
from keynetra.domain.models import policy_versioning as _policy_versioning  # noqa: F401
from keynetra.domain.models import rbac as _rbac  # noqa: F401
from keynetra.domain.models import relationship as _relationship  # noqa: F401
from keynetra.domain.models import tenant as _tenant  # noqa: F401
from keynetra.domain.models.base import Base

revision = "20260407_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
