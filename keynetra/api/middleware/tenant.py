"""Tenant resolution middleware."""

from __future__ import annotations
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from keynetra.api.errors import ApiErrorCode
from keynetra.api.responses import ensure_request_id, error_json_response
from keynetra.config.tenancy import TENANT_HEADER_NAME, normalize_tenant_key


class TenantResolverMiddleware(BaseHTTPMiddleware):
    """Resolves and validates tenant header into request state."""

    _PREFIXES = ("/policies", "/roles", "/permissions", "/relationships", "/playground", "/audit")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        request_id = ensure_request_id(request)
        request.state.is_management_api = any(
            request.url.path.startswith(prefix) for prefix in self._PREFIXES
        )
        requested = request.headers.get(TENANT_HEADER_NAME)
        if requested is None:
            request.state.requested_tenant_key = None
            return await call_next(request)

        tenant_key = normalize_tenant_key(requested)
        if tenant_key is None:
            return error_json_response(
                status_code=422,
                code=ApiErrorCode.VALIDATION_ERROR,
                message="invalid tenant header",
                details={"header": TENANT_HEADER_NAME},
                request_id=request_id,
            )

        request.state.requested_tenant_key = tenant_key
        return await call_next(request)
