from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.config.security import get_principal
from keynetra.config.settings import Settings, get_settings
from keynetra.config.tenancy import DEFAULT_TENANT_KEY, normalize_tenant_key, tenant_from_principal
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.storage.session import get_db

_ROLE_ORDER = {"viewer": 1, "developer": 2, "admin": 3}


@dataclass(frozen=True)
class AdminAccess:
    tenant_key: str
    role: str
    principal: dict[str, Any]


def require_management_role(minimum_role: str):
    if minimum_role not in _ROLE_ORDER:
        raise ValueError(f"unsupported management role: {minimum_role}")

    def dependency(
        request: Request,
        principal: dict[str, Any] = Depends(get_principal),
        settings: Any = Depends(get_settings),
        db: Session = Depends(get_db),
    ) -> AdminAccess:
        if not isinstance(settings, Settings):
            settings = get_settings()
        tenant_key = _resolve_request_tenant_key(
            request=request, principal=principal, settings=settings
        )
        if getattr(request.state, "is_management_api", False):
            tenants = SqlTenantRepository(db)
            explicit_tenant = normalize_tenant_key(request.headers.get("X-Tenant-Id"))
            tenant = tenants.get_by_key(tenant_key)
            if tenant is None:
                if settings.strict_tenancy or explicit_tenant is not None:
                    raise ApiError(
                        status_code=HTTPStatus.NOT_FOUND,
                        code=ApiErrorCode.NOT_FOUND,
                        message="tenant not found",
                        details={"tenant_key": tenant_key},
                    )
                tenant = tenants.get_or_create(tenant_key)
        role = _resolve_tenant_role(principal, tenant_key=tenant_key)
        if role is None:
            raise ApiError(
                status_code=HTTPStatus.FORBIDDEN,
                code=ApiErrorCode.FORBIDDEN,
                message="tenant access denied",
                details={"tenant_key": tenant_key},
            )
        if _ROLE_ORDER[role] < _ROLE_ORDER[minimum_role]:
            raise ApiError(
                status_code=HTTPStatus.FORBIDDEN,
                code=ApiErrorCode.FORBIDDEN,
                message="insufficient management role",
                details={
                    "required_role": minimum_role,
                    "actual_role": role,
                    "tenant_key": tenant_key,
                },
            )
        request.state.admin_role = role
        request.state.admin_tenant_key = tenant_key
        request.state.requested_tenant_key = tenant_key
        return AdminAccess(tenant_key=tenant_key, role=role, principal=principal)

    return dependency


def _resolve_tenant_role(principal: dict[str, Any], tenant_key: str | None = None) -> str | None:
    if principal.get("type") == "api_key":
        scopes = principal.get("scopes")
        if isinstance(scopes, dict):
            role = scopes.get("role")
            if isinstance(role, str) and role in _ROLE_ORDER:
                scoped_tenant = normalize_tenant_key(str(scopes.get("tenant") or ""))
                if tenant_key and scoped_tenant and scoped_tenant != tenant_key:
                    return None
                return role
        return None

    claims = principal.get("claims")
    if not isinstance(claims, dict):
        return None

    tenant_roles = claims.get("tenant_roles")
    if isinstance(tenant_roles, dict):
        if tenant_key:
            role = tenant_roles.get(tenant_key)
            if isinstance(role, str) and role in _ROLE_ORDER:
                return role
        for role in sorted(
            tenant_roles.values(), key=lambda item: _ROLE_ORDER.get(item, 0), reverse=True
        ):
            if isinstance(role, str) and role in _ROLE_ORDER:
                return role
    elif isinstance(tenant_roles, list):
        for item in tenant_roles:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            role_tenant = normalize_tenant_key(
                str(item.get("tenant") or item.get("tenant_key") or "")
            )
            if tenant_key and role_tenant and role_tenant != tenant_key:
                continue
            if isinstance(role, str) and role in _ROLE_ORDER:
                return role

    role = claims.get("admin_role") or claims.get("role")
    if isinstance(role, str) and role in _ROLE_ORDER:
        return role

    roles = claims.get("admin_roles") or claims.get("roles")
    if isinstance(roles, list):
        for item in roles:
            if isinstance(item, str) and item in _ROLE_ORDER:
                return item

    return None


def _resolve_request_tenant_key(
    *, request: Request, principal: dict[str, Any], settings: Settings
) -> str:
    headers = getattr(request, "headers", {})
    header_tenant = normalize_tenant_key(
        headers.get("X-Tenant-Id") or getattr(request.state, "requested_tenant_key", None)
    )
    if header_tenant:
        return header_tenant

    principal_tenant = tenant_from_principal(principal)
    if principal_tenant:
        return principal_tenant

    if settings.strict_tenancy:
        raise ApiError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="tenant is required",
            details={"header": "X-Tenant-Id"},
        )

    if settings.is_development():
        return DEFAULT_TENANT_KEY

    raise ApiError(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        code=ApiErrorCode.VALIDATION_ERROR,
        message="tenant is required",
        details={"header": "X-Tenant-Id"},
    )
