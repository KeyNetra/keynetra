from __future__ import annotations

import logging
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from keynetra.config.tenancy import tenant_for_logs
from keynetra.infrastructure.logging import log_event
from keynetra.observability.http_metrics import record_http_request


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured log line per request."""

    def __init__(self, app) -> None:  # type: ignore[override]
        super().__init__(app)
        self._logger = logging.getLogger("keynetra.request")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_seconds = time.perf_counter() - start
        tenant_id = tenant_for_logs(request)
        log_event(
            self._logger,
            event="request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_seconds * 1000, 3),
            request_id=getattr(request.state, "request_id", None),
            tenant_id=tenant_id,
        )
        record_http_request(
            tenant=tenant_id,
            endpoint=request.url.path,
            method=request.method,
            status=response.status_code,
            duration_seconds=duration_seconds,
        )
        return response
