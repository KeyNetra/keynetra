"""API version negotiation middleware."""

from __future__ import annotations

import logging
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from keynetra.api.errors import ApiErrorCode
from keynetra.api.responses import ensure_request_id, error_json_response
from keynetra.config.tenancy import TENANT_HEADER_NAME, normalize_tenant_key, tenant_for_logs
from keynetra.infrastructure.logging import log_event


class ApiVersionMiddleware(BaseHTTPMiddleware):
    """Resolves request API version from `X-API-Version`."""

    header_name = "X-API-Version"
    latest_version = "v1"
    supported_versions = {"v1"}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        request_id = ensure_request_id(request)
        requested_version = (
            request.headers.get(self.header_name, self.latest_version).strip()
            or self.latest_version
        )
        if requested_version not in self.supported_versions:
            return error_json_response(
                status_code=400,
                code=ApiErrorCode.BAD_REQUEST,
                message="unsupported api version",
                details={
                    "requested_version": requested_version,
                    "supported_versions": sorted(self.supported_versions),
                },
                request_id=request_id,
                headers={self.header_name: self.latest_version},
            )

        request.state.api_version = requested_version
        if getattr(request.state, "requested_tenant_key", None) is None:
            header_tenant = normalize_tenant_key(request.headers.get(TENANT_HEADER_NAME))
            if header_tenant:
                request.state.requested_tenant_key = header_tenant
        log_event(
            logging.getLogger("keynetra.api_version"),
            event="api_version_used",
            api_version=requested_version,
            path=request.url.path,
            method=request.method,
            request_id=getattr(request.state, "request_id", None),
            tenant_id=tenant_for_logs(request),
        )
        response = await call_next(request)
        response.headers[self.header_name] = requested_version
        return response
