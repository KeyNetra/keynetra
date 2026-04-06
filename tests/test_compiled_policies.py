from __future__ import annotations

from keynetra.engine.compiled.decision_graph import COMPILED_POLICY_STORE
from keynetra.engine.keynetra_engine import AuthorizationInput, KeyNetraEngine


def test_compiled_policy_execution_uses_graph() -> None:
    engine = KeyNetraEngine(
        [
            {
                "action": "approve_payment",
                "effect": "allow",
                "priority": 10,
                "policy_id": "pay:v1",
                "conditions": {"role": "manager", "max_amount": 1000},
            }
        ]
    )

    decision = engine.decide(
        AuthorizationInput(
            user={"id": 1, "roles": ["manager"]},
            action="approve_payment",
            resource={"amount": 100},
        )
    )

    assert decision.allowed is True
    assert decision.policy_id == "pay:v1"
    assert any(step.step == "policy_graph" for step in decision.explain_trace)
    assert (
        engine._compiled_graph.evaluate(
            AuthorizationInput(
                user={"roles": ["manager"]}, action="approve_payment", resource={"amount": 100}
            )
        ).outcome
        == "allow"
    )


def test_compiled_graph_store_keeps_tenant_graphs() -> None:
    COMPILED_POLICY_STORE.invalidate("default")
    engine = KeyNetraEngine(
        [
            {
                "action": "read",
                "effect": "allow",
                "priority": 1,
                "conditions": {},
                "policy_id": "read:v1",
            }
        ]
    )
    COMPILED_POLICY_STORE.set("default", 1, engine._compiled_graph)

    stored = COMPILED_POLICY_STORE.get("default", 1)
    assert stored is not None
    assert (
        stored.evaluate(AuthorizationInput(user={}, action="read", resource={})).outcome == "allow"
    )
