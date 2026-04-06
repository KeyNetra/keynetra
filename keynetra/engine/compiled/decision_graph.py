"""Executable decision graph for compiled policy evaluation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class GraphDecision:
    outcome: str
    reason: str | None
    policy_id: str | None


@dataclass(frozen=True)
class CompiledPolicyNode:
    policy_id: str | None
    action: str
    effect: str
    priority: int
    evaluate: Callable[[Any], tuple[bool, str | None]]


@dataclass
class DecisionGraph:
    nodes: tuple[CompiledPolicyNode, ...] = field(default_factory=tuple)

    def evaluate(self, authorization_input: Any) -> GraphDecision:
        first_reason: str | None = None
        for node in self.nodes:
            if node.action != getattr(authorization_input, "action", None):
                continue
            matched, reason = node.evaluate(authorization_input)
            if matched:
                return GraphDecision(
                    outcome=node.effect,
                    reason=reason or f"matched policy {node.policy_id or node.action}",
                    policy_id=node.policy_id,
                )
            if first_reason is None and reason is not None:
                first_reason = reason
        if first_reason is not None:
            return GraphDecision(outcome="deny", reason=first_reason, policy_id=None)
        return GraphDecision(outcome="abstain", reason=None, policy_id=None)


class CompiledPolicyStore:
    """In-memory compiled graph cache keyed by tenant and policy version."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._graphs: dict[tuple[str, int], DecisionGraph] = {}

    def get(self, tenant_key: str, policy_version: int) -> DecisionGraph | None:
        with self._lock:
            return self._graphs.get((tenant_key, policy_version))

    def set(self, tenant_key: str, policy_version: int, graph: DecisionGraph) -> None:
        with self._lock:
            self._graphs[(tenant_key, policy_version)] = graph

    def invalidate(self, tenant_key: str) -> None:
        with self._lock:
            keys = [key for key in self._graphs if key[0] == tenant_key]
            for key in keys:
                self._graphs.pop(key, None)


COMPILED_POLICY_STORE = CompiledPolicyStore()
