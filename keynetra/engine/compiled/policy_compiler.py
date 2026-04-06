"""Policy compilation from DSL-shaped policy objects into executable graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from keynetra.engine.compiled.decision_graph import CompiledPolicyNode, DecisionGraph
from keynetra.observability.metrics import record_policy_compilation


@dataclass(frozen=True)
class PolicyAST:
    action: str
    effect: str
    priority: int
    policy_id: str | None
    conditions: dict[str, Any]


def compile_policy_ast(ast: PolicyAST, evaluator: Any) -> CompiledPolicyNode:
    # Metadata like policy_key travels through the DSL layer but is not a
    # decision condition. Ignore it at compile time so it does not block
    # otherwise valid policies.
    checks: list[tuple[str, Any]] = [
        (key, value) for key, value in ast.conditions.items() if key not in {"policy_key"}
    ]
    policy_id = ast.policy_id or f"{ast.action}:{ast.priority}:{ast.effect}"

    def evaluate(authorization_input: Any) -> tuple[bool, str | None]:
        for key, value in checks:
            handler = getattr(evaluator, f"handle_{key}", None)
            if handler is None:
                return False, f"unknown condition: {key}"
            matched, reason = handler(value, authorization_input)
            if not matched:
                return False, reason or f"{key} mismatch"
        return True, None

    return CompiledPolicyNode(
        policy_id=policy_id,
        action=ast.action,
        effect=ast.effect,
        priority=ast.priority,
        evaluate=evaluate,
    )


def compile_policy_graph(
    policies: list[dict[str, Any]], evaluator: Any, *, tenant_key: str | None = None
) -> DecisionGraph:
    ast_nodes = [
        PolicyAST(
            action=str(policy.get("action", "")),
            effect="allow" if str(policy.get("effect", "deny")) == "allow" else "deny",
            priority=int(policy.get("priority", 100)),
            policy_id=str(policy.get("policy_id")) if policy.get("policy_id") is not None else None,
            conditions=dict(policy.get("conditions") or {}),
        )
        for policy in policies
    ]
    compiled = [
        compile_policy_ast(ast, evaluator)
        for ast in sorted(ast_nodes, key=lambda node: node.priority)
    ]
    record_policy_compilation(tenant=tenant_key)
    return DecisionGraph(nodes=tuple(compiled))
