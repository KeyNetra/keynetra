from __future__ import annotations

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from keynetra.infrastructure.logging import log_event


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
        log_event(
            self._logger,
            event="request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 3),
            request_id=getattr(request.state, "request_id", None),
            tenant_id="default",
        )
        return response
