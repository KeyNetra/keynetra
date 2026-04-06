from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from keynetra.domain.models.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    authorization_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
