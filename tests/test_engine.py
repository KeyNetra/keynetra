from __future__ import annotations

from keynetra.engine.keynetra_engine import AuthorizationInput, KeyNetraEngine


def test_engine_is_deterministic_for_same_structured_input() -> None:
    engine = KeyNetraEngine(
        [
            {
                "action": "approve_payment",
                "effect": "allow",
                "priority": 10,
                "policy_id": "approve:v1",
                "conditions": {"role": "manager", "max_amount": 1000},
            }
        ]
    )
    authorization_input = AuthorizationInput(
        user={"id": 7, "role": "manager", "permissions": []},
        action="approve_payment",
        resource={"amount": 100},
        context={"current_time": "09:30"},
    )

    first = engine.decide(authorization_input)
    second = engine.decide(authorization_input)

    assert first == second
    assert first.allowed is True
    assert first.policy_id == "approve:v1"
    assert first.explain_trace[-1].outcome == "allow"


def test_engine_time_range_requires_explicit_context() -> None:
    engine = KeyNetraEngine(
        [
            {
                "action": "deploy",
                "effect": "allow",
                "priority": 10,
                "policy_id": "deploy:v1",
                "conditions": {"time_range": {"start": "09:00", "end": "17:00"}},
            }
        ]
    )

    decision = engine.decide(
        AuthorizationInput(
            user={"id": 1, "role": "ops"},
            action="deploy",
            resource={},
            context={},
        )
    )

    assert decision.allowed is False
    assert decision.reason == "missing context.current_time"
    assert decision.policy_id is None


def test_engine_has_relation_uses_explicit_input_only() -> None:
    engine = KeyNetraEngine(
        [
            {
                "action": "view_team",
                "effect": "allow",
                "priority": 10,
                "policy_id": "team-member:v1",
                "conditions": {
                    "has_relation": {
                        "relation": "member_of",
                        "object_type": "team",
                        "object_id_from_resource": "team_id",
                    }
                },
            }
        ]
    )

    decision = engine.decide(
        AuthorizationInput(
            user={
                "id": 4,
                "relations": [
                    {
                        "subject_type": "user",
                        "subject_id": "4",
                        "relation": "member_of",
                        "object_type": "team",
                        "object_id": "red",
                    }
                ],
            },
            action="view_team",
            resource={"team_id": "red"},
        )
    )

    assert decision.allowed is True
    assert decision.policy_id == "team-member:v1"


def test_engine_trace_alias_remains_available() -> None:
    engine = KeyNetraEngine([{"action": "read", "effect": "deny", "priority": 1, "conditions": {}}])

    decision = engine.decide(AuthorizationInput(user={}, action="read", resource={}))

    assert decision.decision == "deny"
    assert isinstance(decision.evaluated_rules, list)
    assert decision.evaluated_rules[-1]["outcome"] == "deny"
