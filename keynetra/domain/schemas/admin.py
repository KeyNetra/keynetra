from __future__ import annotations

from typing import Any

from pydantic import Field

from keynetra.domain.schemas.api import StrictSchemaModel, UtcDateTime


class TenantCreate(StrictSchemaModel):
    tenant_key: str


class TenantOut(StrictSchemaModel):
    id: int
    tenant_key: str
    policy_version: int
    revision: int


class ApiKeyScope(StrictSchemaModel):
    tenant: str | None = None
    role: str | None = None
    permissions: list[str] = Field(default_factory=list)


class ApiKeyCreate(StrictSchemaModel):
    name: str
    scopes: ApiKeyScope = Field(default_factory=ApiKeyScope)


class ApiKeyOut(StrictSchemaModel):
    id: int
    tenant_id: int
    name: str
    key_prefix: str
    scopes: dict[str, Any]
    created_at: UtcDateTime
    revoked_at: UtcDateTime | None = None


class ApiKeyCreatedOut(ApiKeyOut):
    secret: str


class UserRoleAssignmentOut(StrictSchemaModel):
    user_id: int
    external_id: str | None = None
    roles: list[str] = Field(default_factory=list)


class PolicyVersionOut(StrictSchemaModel):
    id: int
    version: int
    action: str
    effect: str
    priority: int
    state: str
    conditions: dict[str, Any]
    created_at: UtcDateTime
    created_by: str | None = None


class PolicyVersionDiffOut(StrictSchemaModel):
    policy_key: str
    from_version: int
    to_version: int
    changes: dict[str, Any]


class PolicyTestSuiteRequest(StrictSchemaModel):
    document: str


class PolicyTestResultOut(StrictSchemaModel):
    name: str
    passed: bool
    expected: str
    actual: str
    reason: str | None = None
    policy_id: str | None = None
    explain_trace: list[dict[str, Any]] = Field(default_factory=list)


class BulkImportRequest(StrictSchemaModel):
    resource: str
    payload: Any


class BulkImportOut(StrictSchemaModel):
    resource: str
    imported: int


class BulkExportOut(StrictSchemaModel):
    resource: str
    data: Any
