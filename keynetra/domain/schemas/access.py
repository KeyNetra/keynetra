from __future__ import annotations

from typing import Any

from pydantic import Field

from keynetra.domain.schemas.api import StrictSchemaModel


class AccessRequest(StrictSchemaModel):
    """Explicit authorization request passed through the API boundary."""

    user: dict[str, Any] = Field(default_factory=dict)
    action: str
    resource: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    consistency: str = "eventual"
    revision: int | None = None


class AccessResponse(StrictSchemaModel):
    allowed: bool


class AccessDecisionResponse(StrictSchemaModel):
    allowed: bool
    decision: str
    matched_policies: list[str] = Field(default_factory=list)
    reason: str | None = None
    policy_id: str | None = None
    explain_trace: list[dict[str, Any]] = Field(default_factory=list)
    revision: int | None = None


class SimulationResponse(StrictSchemaModel):
    decision: str
    matched_policies: list[str]
    reason: str | None = None
    policy_id: str | None = None
    explain_trace: list[dict[str, Any]] = Field(default_factory=list)
    failed_conditions: list[str] = Field(default_factory=list)
    revision: int | None = None


class BatchAccessItem(StrictSchemaModel):
    action: str
    resource: dict[str, Any] = Field(default_factory=dict)


class BatchAccessRequest(StrictSchemaModel):
    user: dict[str, Any] = Field(default_factory=dict)
    items: list[BatchAccessItem]
    consistency: str = "eventual"
    revision: int | None = None


class BatchAccessResult(StrictSchemaModel):
    action: str
    allowed: bool
    revision: int | None = None


class BatchAccessResponse(StrictSchemaModel):
    results: list[BatchAccessResult]
    revision: int | None = None
