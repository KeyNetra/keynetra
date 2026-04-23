from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from keynetra.domain.models.base import Base
from keynetra.utils.datetime import utc_now


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    principal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    user: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    decision: Mapped[str] = mapped_column(String(8), nullable=False)  # ALLOW/DENY
    matched_policies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    evaluated_rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    failed_conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        Index("ix_audit_logs_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_audit_logs_tenant_actor", "tenant_id", "principal_type", "principal_id"),
        Index("ix_audit_logs_tenant_decision", "tenant_id", "decision"),
    )
