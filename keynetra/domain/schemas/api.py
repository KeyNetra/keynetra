"""Shared API envelope schemas for core."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

PayloadT = TypeVar("PayloadT")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class MetaBody(BaseModel):
    request_id: str | None = None
    limit: int | None = None
    next_cursor: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SuccessResponse(BaseModel, Generic[PayloadT]):
    data: PayloadT
    meta: MetaBody = Field(default_factory=MetaBody)
    error: None = None


class ErrorResponse(BaseModel):
    data: None = None
    error: ErrorBody
