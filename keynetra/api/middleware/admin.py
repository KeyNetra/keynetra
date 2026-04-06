"""Administrative request context middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware


class AdminAuthorizationContextMiddleware(BaseHTTPMiddleware):
    _PREFIXES = ("/policies", "/roles", "/permissions", "/relationships", "/playground", "/audit")

    async def dispatch(self, request, call_next):  # type: ignore[override]
        request.state.requested_tenant_key = "default"
        request.state.is_management_api = any(
            request.url.path.startswith(prefix) for prefix in self._PREFIXES
        )
        return await call_next(request)
