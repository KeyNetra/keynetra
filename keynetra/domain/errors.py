from __future__ import annotations

from enum import StrEnum


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
