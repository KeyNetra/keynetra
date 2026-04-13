"""Interactive evaluation surface for inline policies."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.security import get_principal
from keynetra.domain.schemas.api import StrictSchemaModel, SuccessResponse
from keynetra.engine.keynetra_engine import AuthorizationInput, KeyNetraEngine


class PlaygroundPolicy(StrictSchemaModel):
    action: str
    effect: str = "allow"
    priority: int = 100
    policy_id: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)


class PlaygroundInput(StrictSchemaModel):
    user: dict[str, Any] = Field(default_factory=dict)
    resource: dict[str, Any] = Field(default_factory=dict)
    action: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class PlaygroundEvaluateRequest(StrictSchemaModel):
    policies: list[PlaygroundPolicy]
    input: PlaygroundInput


router = APIRouter(prefix="/playground", dependencies=[Depends(get_principal)])


@router.post("/evaluate", response_model=SuccessResponse[dict[str, Any]])
def evaluate(
    payload: PlaygroundEvaluateRequest,
    request: Request,
    _: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, Any]:
    engine = KeyNetraEngine([policy.model_dump() for policy in payload.policies])
    authorization_input = AuthorizationInput(
        user=payload.input.user,
        resource=payload.input.resource,
        action=payload.input.action,
        context=payload.input.context,
    )
    decision = engine.decide(authorization_input)
    return success_response(
        data={
            "allowed": decision.allowed,
            "decision": decision.decision,
            "reason": decision.reason,
            "policy_id": decision.policy_id,
            "explain_trace": [step.to_dict() for step in decision.explain_trace],
        },
        request_id=request_id_from_state(request.state),
    )
