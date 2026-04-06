from __future__ import annotations

import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a request id (for tracing/log correlation).
    - Accepts inbound `X-Request-Id` if present
    - Otherwise generates a short, URL-safe id
    - Echoes it back on responses as `X-Request-Id`
    """

    header_name = "X-Request-Id"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        request_id = request.headers.get(self.header_name) or secrets.token_urlsafe(10)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[self.header_name] = request_id
        return response
