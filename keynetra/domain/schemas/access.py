from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AccessRequest(BaseModel):
    """Explicit authorization request passed through the API boundary."""

    user: dict[str, Any] = Field(default_factory=dict)
    action: str
    resource: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    consistency: str = "eventual"
    revision: int | None = None


class AccessResponse(BaseModel):
    allowed: bool


class AccessDecisionResponse(BaseModel):
    allowed: bool
    decision: str
    matched_policies: list[str] = Field(default_factory=list)
    reason: str | None = None
    policy_id: str | None = None
    explain_trace: list[dict[str, Any]] = Field(default_factory=list)
    revision: int | None = None


class SimulationResponse(BaseModel):
    decision: str
    matched_policies: list[str]
    reason: str | None = None
    policy_id: str | None = None
    explain_trace: list[dict[str, Any]] = Field(default_factory=list)
    failed_conditions: list[str] = Field(default_factory=list)
    revision: int | None = None


class BatchAccessItem(BaseModel):
    action: str
    resource: dict[str, Any] = Field(default_factory=dict)


class BatchAccessRequest(BaseModel):
    user: dict[str, Any] = Field(default_factory=dict)
    items: list[BatchAccessItem]
    consistency: str = "eventual"
    revision: int | None = None


class BatchAccessResult(BaseModel):
    action: str
    allowed: bool
    revision: int | None = None


class BatchAccessResponse(BaseModel):
    results: list[BatchAccessResult]
    revision: int | None = None
