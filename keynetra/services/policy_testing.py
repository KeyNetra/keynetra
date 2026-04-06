"""Policy test parsing and execution.

This module provides a deployment-time validation workflow similar to unit
tests. It stays outside the API and engine boundaries: the engine only
evaluates explicit inputs, while this service parses policy test fixtures and
reports pass/fail results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from keynetra.engine.keynetra_engine import AuthorizationInput, KeyNetraEngine
from keynetra.services.policy_dsl import dsl_to_policy

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional parser dependency
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class PolicyTestCase:
    """One expected authorization outcome."""

    name: str
    authorization_input: AuthorizationInput
    expect: str


@dataclass(frozen=True)
class PolicyTestSuite:
    """Structured policies plus test cases."""

    policies: list[dict[str, Any]]
    tests: list[PolicyTestCase]


@dataclass(frozen=True)
class PolicyTestResult:
    """Outcome for one executed policy test."""

    name: str
    passed: bool
    expected: str
    actual: str
    reason: str | None
    policy_id: str | None
    explain_trace: list[dict[str, Any]] = field(default_factory=list)


def parse_policy_test_suite(document: str) -> PolicyTestSuite:
    """Parse a YAML or JSON policy test document."""

    raw = _load_document(document)
    if not isinstance(raw, dict):
        raise ValueError("policy test file must be an object")

    raw_policies = raw.get("policies")
    raw_tests = raw.get("tests")
    if not isinstance(raw_policies, list) or not raw_policies:
        raise ValueError("policies must be a non-empty list")
    if not isinstance(raw_tests, list) or not raw_tests:
        raise ValueError("tests must be a non-empty list")

    policies = [
        _parse_policy_entry(entry, index=index) for index, entry in enumerate(raw_policies, start=1)
    ]
    tests = [_parse_test_case(entry, index=index) for index, entry in enumerate(raw_tests, start=1)]
    return PolicyTestSuite(policies=policies, tests=tests)


def run_policy_test_suite(suite: PolicyTestSuite) -> list[PolicyTestResult]:
    """Execute all policy tests against the pure engine."""

    engine = KeyNetraEngine(suite.policies, strategy="first_match")
    results: list[PolicyTestResult] = []
    for case in suite.tests:
        decision = engine.decide(case.authorization_input)
        results.append(
            PolicyTestResult(
                name=case.name,
                passed=decision.decision == case.expect,
                expected=case.expect,
                actual=decision.decision,
                reason=decision.reason,
                policy_id=decision.policy_id,
                explain_trace=[step.to_dict() for step in decision.explain_trace],
            )
        )
    return results


def validate_policy_test_suite(document: str) -> list[PolicyTestResult]:
    """Parse and execute a suite, raising on malformed policies or tests."""

    suite = parse_policy_test_suite(document)
    return run_policy_test_suite(suite)


def _load_document(document: str) -> Any:
    if yaml is not None:
        return yaml.safe_load(document)
    return json.loads(document)


def _parse_policy_entry(entry: Any, *, index: int) -> dict[str, Any]:
    if isinstance(entry, dict) and ("allow" in entry or "deny" in entry):
        parsed = dsl_to_policy(_dump_document(entry))
        conditions = dict(parsed.get("conditions") or {})
        policy_key = conditions.get("policy_key")
        conditions.pop("policy_key", None)
        parsed["policy_id"] = str(policy_key) if isinstance(policy_key, str) else f"policy-{index}"
        parsed["conditions"] = conditions
        return parsed
    if not isinstance(entry, dict):
        raise ValueError(f"policy #{index} must be an object")
    action = entry.get("action")
    effect = entry.get("effect")
    if not isinstance(action, str) or not action:
        raise ValueError(f"policy #{index} is missing action")
    if effect not in {"allow", "deny"}:
        raise ValueError(f"policy #{index} effect must be allow or deny")
    priority = int(entry.get("priority", 100))
    conditions = entry.get("conditions") or {}
    if not isinstance(conditions, dict):
        raise ValueError(f"policy #{index} conditions must be an object")
    policy_id = entry.get("policy_id")
    if policy_id is not None and not isinstance(policy_id, str):
        raise ValueError(f"policy #{index} policy_id must be a string")
    return {
        "action": action,
        "effect": effect,
        "priority": priority,
        "conditions": dict(conditions),
        "policy_id": policy_id or f"policy-{index}",
    }


def _parse_test_case(entry: Any, *, index: int) -> PolicyTestCase:
    if not isinstance(entry, dict):
        raise ValueError(f"test #{index} must be an object")
    name = entry.get("name")
    expect = entry.get("expect")
    raw_input = entry.get("input")
    if not isinstance(name, str) or not name:
        raise ValueError(f"test #{index} is missing name")
    if expect not in {"allow", "deny"}:
        raise ValueError(f"test '{name}' expect must be allow or deny")
    if not isinstance(raw_input, dict):
        raise ValueError(f"test '{name}' input must be an object")

    user = raw_input.get("user") or {}
    resource = raw_input.get("resource") or {}
    action = raw_input.get("action")
    context = raw_input.get("context") or {}
    if not isinstance(user, dict):
        raise ValueError(f"test '{name}' user must be an object")
    if not isinstance(resource, dict):
        raise ValueError(f"test '{name}' resource must be an object")
    if not isinstance(context, dict):
        raise ValueError(f"test '{name}' context must be an object")
    if not isinstance(action, str) or not action:
        raise ValueError(f"test '{name}' is missing action")

    return PolicyTestCase(
        name=name,
        authorization_input=AuthorizationInput(
            user=dict(user),
            resource=dict(resource),
            action=action,
            context=dict(context),
        ),
        expect=expect,
    )


def _dump_document(value: dict[str, Any]) -> str:
    if yaml is not None:
        return yaml.safe_dump(value, sort_keys=False)
    return json.dumps(value)
