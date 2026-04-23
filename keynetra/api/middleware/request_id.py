from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from keynetra.infrastructure.logging import (
    reset_correlation_id,
    reset_request_id,
    set_correlation_id,
    set_request_id,
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a request id (for tracing/log correlation).
    - Accepts inbound `X-Request-Id` if present
    - Otherwise generates a short, URL-safe id
    - Echoes it back on responses as `X-Request-Id`
    """

    header_name = "X-Request-Id"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(self.header_name) or secrets.token_urlsafe(10)
        request.state.request_id = request_id
        correlation_token = set_correlation_id(request_id)
        request_token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers[self.header_name] = request_id
            return response
        finally:
            reset_request_id(request_token)
            reset_correlation_id(correlation_token)
