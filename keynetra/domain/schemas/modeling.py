from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from keynetra.domain.schemas.api import StrictSchemaModel


class AuthModelCreate(StrictSchemaModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_text: str = Field(alias="schema")


class AuthModelOut(StrictSchemaModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: int
    tenant_id: int
    schema_text: str = Field(alias="schema")
    parsed: dict[str, Any]
    compiled: dict[str, Any]


class PolicySimulationInput(StrictSchemaModel):
    policy_change: str | None = None
    relationship_change: dict[str, Any] | None = None
    role_change: dict[str, Any] | None = None


class PolicySimulationRequest(StrictSchemaModel):
    simulate: PolicySimulationInput = Field(default_factory=PolicySimulationInput)
    request: dict[str, Any] = Field(default_factory=dict)


class PolicySimulationResponse(StrictSchemaModel):
    decision_before: dict[str, Any]
    decision_after: dict[str, Any]


class ImpactAnalysisRequest(StrictSchemaModel):
    policy_change: str


class ImpactAnalysisResponse(StrictSchemaModel):
    gained_access: list[int] = Field(default_factory=list)
    lost_access: list[int] = Field(default_factory=list)
