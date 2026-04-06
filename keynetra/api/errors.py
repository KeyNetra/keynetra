"""Core API error codes and exception helpers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ApiErrorCode(StrEnum):
    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    TOO_MANY_REQUESTS = "too_many_requests"
    VALIDATION_ERROR = "validation_error"
    DATABASE_ERROR = "database_error"
    INTERNAL_ERROR = "internal_error"


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
