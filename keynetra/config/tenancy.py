from __future__ import annotations

import re
from typing import Any

DEFAULT_TENANT_KEY = "default"
TENANT_HEADER_NAME = "X-Tenant-Id"
_TENANT_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def get_tenant_key() -> str:
    return DEFAULT_TENANT_KEY


def normalize_tenant_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if not _TENANT_PATTERN.fullmatch(normalized):
        return None
    return normalized


def tenant_from_principal(principal: dict[str, Any]) -> str | None:
    if principal.get("type") == "api_key":
        scopes = principal.get("scopes")
        if isinstance(scopes, dict):
            tenant = normalize_tenant_key(str(scopes.get("tenant") or ""))
            if tenant:
                return tenant
        return None

    claims = principal.get("claims")
    if not isinstance(claims, dict):
        return None

    for key in ("tenant", "tenant_id", "tenant_key"):
        tenant = claims.get(key)
        if isinstance(tenant, str):
            normalized = normalize_tenant_key(tenant)
            if normalized:
                return normalized

    tenant_roles = claims.get("tenant_roles")
    if isinstance(tenant_roles, dict):
        candidates = [normalize_tenant_key(str(item)) for item in tenant_roles]
        normalized = [item for item in candidates if item]
        if len(normalized) == 1:
            return normalized[0]

    return None


def tenant_for_logs(request: Any) -> str | None:
    state = getattr(request, "state", None)
    return normalize_tenant_key(getattr(state, "requested_tenant_key", None)) or "unknown"
