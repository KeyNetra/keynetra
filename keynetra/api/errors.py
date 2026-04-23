"""Core API error codes and exception helpers."""

from __future__ import annotations

from typing import Any

from keynetra.domain.errors import ApiErrorCode


class ApiError(Exception):
    """Structured application error rendered by the global error handler."""

    def __init__(
        self, *, status_code: int, code: ApiErrorCode, message: str, details: Any | None = None
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)
