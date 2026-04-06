"""API version negotiation middleware."""

from __future__ import annotations

import logging
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from keynetra.infrastructure.logging import log_event


class ApiVersionMiddleware(BaseHTTPMiddleware):
    """Resolves request API version from `X-API-Version`."""

    header_name = "X-API-Version"
    latest_version = "v1"
    supported_versions = {"v1"}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        requested_version = (
            request.headers.get(self.header_name, self.latest_version).strip()
            or self.latest_version
        )
        if requested_version not in self.supported_versions:
            return JSONResponse(
                status_code=400,
                content={
                    "data": None,
                    "error": {
                        "code": "bad_request",
                        "message": "unsupported api version",
                        "details": {
                            "requested_version": requested_version,
                            "supported_versions": sorted(self.supported_versions),
                        },
                    },
                },
            )

        request.state.api_version = requested_version
        log_event(
            logging.getLogger("keynetra.api_version"),
            event="api_version_used",
            api_version=requested_version,
            path=request.url.path,
            method=request.method,
            request_id=getattr(request.state, "request_id", None),
            tenant_id="default",
        )
        response = await call_next(request)
        response.headers[self.header_name] = requested_version
        return response
