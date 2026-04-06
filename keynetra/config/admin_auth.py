from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Request, status

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.config.security import get_principal
from keynetra.config.tenancy import DEFAULT_TENANT_KEY

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
    ) -> AdminAccess:
        role = _resolve_tenant_role(principal)
        if role is None:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code=ApiErrorCode.FORBIDDEN,
                message="tenant access denied",
                details={"tenant_key": DEFAULT_TENANT_KEY},
            )
        if _ROLE_ORDER[role] < _ROLE_ORDER[minimum_role]:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code=ApiErrorCode.FORBIDDEN,
                message="insufficient management role",
                details={
                    "required_role": minimum_role,
                    "actual_role": role,
                    "tenant_key": DEFAULT_TENANT_KEY,
                },
            )
        request.state.admin_role = role
        request.state.admin_tenant_key = DEFAULT_TENANT_KEY
        return AdminAccess(tenant_key=DEFAULT_TENANT_KEY, role=role, principal=principal)

    return dependency


def _resolve_tenant_role(principal: dict[str, Any]) -> str | None:
    if principal.get("type") == "api_key":
        return "admin"

    claims = principal.get("claims")
    if not isinstance(claims, dict):
        return None

    tenant_roles = claims.get("tenant_roles")
    if isinstance(tenant_roles, dict):
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
