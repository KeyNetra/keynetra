"""Shared API envelope schemas for core."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_serializers import PlainSerializer
from typing_extensions import Annotated

from keynetra.api.errors import ApiErrorCode
from keynetra.utils.datetime import isoformat_z

PayloadT = TypeVar("PayloadT")
UtcDateTime = Annotated[datetime, PlainSerializer(isoformat_z, return_type=str)]


class StrictSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(StrictSchemaModel):
    code: ApiErrorCode
    message: str
    details: Any | None = None


class MetaBody(StrictSchemaModel):
    request_id: str | None = None
    limit: int | None = None
    next_cursor: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SuccessResponse(StrictSchemaModel, Generic[PayloadT]):
    data: PayloadT
    meta: MetaBody = Field(default_factory=MetaBody)
    error: None = None


class ErrorResponse(StrictSchemaModel):
    data: None = None
    meta: MetaBody = Field(default_factory=MetaBody)
    error: ErrorBody
