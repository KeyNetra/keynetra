from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from keynetra.domain.schemas.api import StrictSchemaModel, UtcDateTime


class RoleCreate(StrictSchemaModel):
    name: str


class RoleUpdate(StrictSchemaModel):
    name: str


class RoleOut(StrictSchemaModel):
    id: int
    name: str


class PermissionCreate(StrictSchemaModel):
    action: str


class PermissionUpdate(StrictSchemaModel):
    action: str


class PermissionOut(StrictSchemaModel):
    id: int
    action: str


class RolePermissionOut(StrictSchemaModel):
    id: int
    action: str


class PolicyCreate(StrictSchemaModel):
    action: str
    effect: str = "allow"
    priority: int = 100
    state: str = "active"
    conditions: dict[str, Any] = Field(default_factory=dict)


class PolicyOut(StrictSchemaModel):
    id: int
    action: str
    effect: str
    priority: int
    state: str = "active"
    conditions: dict[str, Any]


class PolicyDslCreate(StrictSchemaModel):
    dsl: str


class ACLCreate(StrictSchemaModel):
    subject_type: str
    subject_id: str
    resource_type: str
    resource_id: str
    action: str
    effect: str


class ACLOut(ACLCreate):
    id: int
    tenant_id: int
    created_at: UtcDateTime | None = None


class AuditRecordOut(StrictSchemaModel):
    id: int
    principal_type: str
    principal_id: str
    correlation_id: str | None = None
    user: dict[str, Any]
    action: str
    resource: dict[str, Any]
    decision: str
    matched_policies: list[Any]
    reason: str | None = None
    evaluated_rules: list[Any]
    failed_conditions: list[Any]
    created_at: UtcDateTime


class AdminLoginRequest(StrictSchemaModel):
    username: str
    password: str


class AdminLoginResponse(StrictSchemaModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str = "admin"
    tenant_key: str
