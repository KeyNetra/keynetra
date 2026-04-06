"""Compiled permission graph for schema-first authorization models."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from keynetra.modeling.permission_compiler import CompiledAuthorizationModel


@dataclass(frozen=True)
class AuthorizationGraphDecision:
    outcome: str
    reason: str | None
    policy_id: str | None


@dataclass(frozen=True)
class CompiledPermissionGraph:
    tenant_key: str
    model: CompiledAuthorizationModel

    def evaluate(self, authorization_input: Any) -> AuthorizationGraphDecision:
        resource_type, _resource_id = self._resource_identity(authorization_input)
        action = getattr(authorization_input, "action", None)
        if not resource_type or not action:
            return AuthorizationGraphDecision(outcome="abstain", reason=None, policy_id=None)
        if action not in self.model.permissions:
            return AuthorizationGraphDecision(outcome="abstain", reason=None, policy_id=None)
        evaluator = _PermissionEvaluator(
            authorization_input=authorization_input, model=self.model, resource_type=resource_type
        )
        matched = evaluator.evaluate(self.model.permissions[action].expression)
        if matched:
            return AuthorizationGraphDecision(
                outcome="allow",
                reason=f"matched authorization model permission {action}",
                policy_id=f"auth-model:{action}",
            )
        return AuthorizationGraphDecision(
            outcome="deny",
            reason=f"authorization model denied {action}",
            policy_id=f"auth-model:{action}",
        )

    def _resource_identity(self, authorization_input: Any) -> tuple[str, str]:
        resource = getattr(authorization_input, "resource", {}) or {}
        resource_type = str(
            resource.get("resource_type") or resource.get("type") or resource.get("kind") or ""
        )
        resource_id = str(resource.get("resource_id") or resource.get("id") or "")
        return resource_type, resource_id


class _PermissionEvaluator:
    def __init__(
        self, *, authorization_input: Any, model: CompiledAuthorizationModel, resource_type: str
    ) -> None:
        self._authorization_input = authorization_input
        self._model = model
        self._resource_type = resource_type

    def evaluate(self, expr: Any) -> bool:
        from keynetra.modeling.schema_parser import AndExpr, IdentifierExpr, NotExpr, OrExpr

        if isinstance(expr, IdentifierExpr):
            return self._has_relation(expr.name)
        if isinstance(expr, NotExpr):
            return not self.evaluate(expr.value)
        if isinstance(expr, AndExpr):
            return self.evaluate(expr.left) and self.evaluate(expr.right)
        if isinstance(expr, OrExpr):
            return self.evaluate(expr.left) or self.evaluate(expr.right)
        return False

    def _has_relation(self, name: str) -> bool:
        relations = getattr(self._authorization_input, "user", {}).get("relations", [])
        if not isinstance(relations, list):
            return False
        resource = getattr(self._authorization_input, "resource", {}) or {}
        resource_id = str(resource.get("resource_id") or resource.get("id") or "")
        for edge in relations:
            if not isinstance(edge, dict):
                continue
            if str(edge.get("relation")) != name:
                continue
            if str(edge.get("object_type")) != self._resource_type:
                continue
            if str(edge.get("object_id")) != resource_id:
                continue
            return True
        return False


class PermissionGraphStore:
    """In-memory compiled permission graph cache keyed by tenant."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._graphs: dict[str, CompiledPermissionGraph] = {}

    def get(self, tenant_key: str) -> CompiledPermissionGraph | None:
        with self._lock:
            return self._graphs.get(tenant_key)

    def set(self, tenant_key: str, graph: CompiledPermissionGraph) -> None:
        with self._lock:
            self._graphs[tenant_key] = graph

    def invalidate(self, tenant_key: str) -> None:
        with self._lock:
            self._graphs.pop(tenant_key, None)


MODEL_GRAPH_STORE = PermissionGraphStore()
