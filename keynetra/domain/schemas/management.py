from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str


class RoleUpdate(BaseModel):
    name: str


class RoleOut(BaseModel):
    id: int
    name: str


class PermissionCreate(BaseModel):
    action: str


class PermissionUpdate(BaseModel):
    action: str


class PermissionOut(BaseModel):
    id: int
    action: str


class RolePermissionOut(BaseModel):
    id: int
    action: str


class PolicyCreate(BaseModel):
    action: str
    effect: str = "allow"
    priority: int = 100
    conditions: dict[str, Any] = Field(default_factory=dict)


class PolicyOut(BaseModel):
    id: int
    action: str
    effect: str
    priority: int
    conditions: dict[str, Any]


class ACLCreate(BaseModel):
    subject_type: str
    subject_id: str
    resource_type: str
    resource_id: str
    action: str
    effect: str


class ACLOut(ACLCreate):
    id: int
    tenant_id: int
    created_at: datetime | None = None


class AuditRecordOut(BaseModel):
    id: int
    principal_type: str
    principal_id: str
    user: dict[str, Any]
    action: str
    resource: dict[str, Any]
    decision: str
    matched_policies: list[Any]
    reason: str | None = None
    evaluated_rules: list[Any]
    failed_conditions: list[Any]
    created_at: datetime


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str = "admin"
    tenant_key: str
