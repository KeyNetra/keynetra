"""Pure, deterministic authorization engine.

This module is intentionally isolated from HTTP, databases, caches, and other
external systems. Every input needed to evaluate a decision must be supplied
explicitly through ``AuthorizationInput``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from keynetra.engine.compiled.decision_graph import DecisionGraph
from keynetra.engine.compiled.policy_compiler import compile_policy_graph
from keynetra.engine.model_graph.permission_graph import CompiledPermissionGraph
from keynetra.observability.metrics import (
    observe_access_check_latency,
    record_access_check,
    record_acl_match,
    record_policy_evaluation,
    record_relationship_traversal,
)

DecisionValue = Literal["allow", "deny"]
StageOutcome = Literal["allow", "deny", "abstain"]


@dataclass(frozen=True)
class AuthorizationInput:
    """Explicit request supplied to the pure decision engine."""

    user: dict[str, Any]
    resource: dict[str, Any]
    action: str
    context: dict[str, Any] = field(default_factory=dict)
    acl_entries: tuple[dict[str, Any], ...] = ()
    access_index_entries: tuple[dict[str, Any], ...] = ()
    permission_graph: CompiledPermissionGraph | None = None
    compiled_graph: DecisionGraph | None = None
    tenant_key: str | None = None


@dataclass(frozen=True)
class PolicyDefinition:
    """Policy definition evaluated by the engine."""

    action: str
    effect: DecisionValue = "deny"
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    policy_id: str | None = None

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> PolicyDefinition:
        return PolicyDefinition(
            action=str(raw.get("action", "")),
            effect="allow" if str(raw.get("effect", "deny")) == "allow" else "deny",
            conditions=raw.get("conditions") if isinstance(raw.get("conditions"), dict) else {},
            priority=int(raw.get("priority", 100)),
            policy_id=str(raw.get("policy_id")) if raw.get("policy_id") is not None else None,
        )


@dataclass(frozen=True)
class ExplainTraceStep:
    """One deterministic step in the evaluation trace."""

    step: str
    outcome: str
    detail: str
    policy_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "step": self.step,
            "outcome": self.outcome,
            "detail": self.detail,
            "policy_id": self.policy_id,
        }


@dataclass(frozen=True)
class AuthorizationDecision:
    """Pure engine output.

    ``policy_id`` points to the winning policy when one exists. The
    ``explain_trace`` documents every relevant evaluation step.
    """

    allowed: bool
    decision: DecisionValue
    reason: str | None
    policy_id: str | None
    explain_trace: tuple[ExplainTraceStep, ...]
    matched_policies: tuple[str, ...] = ()
    failed_conditions: tuple[str, ...] = ()

    @property
    def evaluated_rules(self) -> list[dict[str, str | None]]:
        """Backward-compatible trace alias for existing callers."""

        return [step.to_dict() for step in self.explain_trace]


ConditionHandler = Callable[[Any, AuthorizationInput], tuple[bool, str | None]]


class ConditionEvaluator:
    """Evaluates policy conditions using only explicit request data."""

    def evaluate(
        self, conditions: dict[str, Any], authorization_input: AuthorizationInput
    ) -> tuple[bool, str | None]:
        for key, value in conditions.items():
            handler = getattr(self, f"handle_{key}", None)
            if handler is None:
                return False, f"unknown condition: {key}"
            ok, reason = handler(value, authorization_input)
            if not ok:
                return False, reason or f"{key} mismatch"
        return True, None

    def handle_role(
        self, value: str, authorization_input: AuthorizationInput
    ) -> tuple[bool, str | None]:
        user = authorization_input.user
        if user.get("role") == value:
            return True, None
        roles = user.get("roles", [])
        ok = isinstance(roles, list) and value in roles
        return ok, None if ok else "role mismatch"

    def handle_max_amount(
        self, value: int | float, authorization_input: AuthorizationInput
    ) -> tuple[bool, str | None]:
        amount = authorization_input.resource.get("amount", 0)
        try:
            ok = float(amount) <= float(value)
        except (TypeError, ValueError):
            return False, "invalid amount"
        return ok, None if ok else "max_amount exceeded"

    def handle_owner_only(
        self, value: bool, authorization_input: AuthorizationInput
    ) -> tuple[bool, str | None]:
        if not value:
            return True, None
        resource = authorization_input.resource
        user = authorization_input.user
        ok = resource.get("owner_id") == user.get("id")
        return ok, None if ok else "owner mismatch"

    def handle_time_range(
        self, value: dict[str, Any], authorization_input: AuthorizationInput
    ) -> tuple[bool, str | None]:
        if not isinstance(value, dict):
            return False, "invalid time_range"
        start = value.get("start")
        end = value.get("end")
        current_time = authorization_input.context.get("current_time")
        if not isinstance(start, str) or not isinstance(end, str):
            return False, "invalid time_range"
        if not isinstance(current_time, str):
            return False, "missing context.current_time"
        try:
            start_value = datetime.strptime(start, "%H:%M").time()
            end_value = datetime.strptime(end, "%H:%M").time()
            current_value = datetime.strptime(current_time, "%H:%M").time()
        except ValueError:
            return False, "invalid time_range"
        if start_value <= end_value:
            ok = start_value <= current_value <= end_value
        else:
            ok = current_value >= start_value or current_value <= end_value
        return ok, None if ok else "time_range mismatch"

    def handle_geo_match(
        self, value: dict[str, Any], authorization_input: AuthorizationInput
    ) -> tuple[bool, str | None]:

        if not isinstance(value, dict):
            return False, "invalid geo_match"
        user_field = value.get("user_field", "country")
        resource_field = value.get("resource_field", "country")
        user = authorization_input.user
        resource = authorization_input.resource
        ok = user.get(user_field) is not None and user.get(user_field) == resource.get(
            resource_field
        )
        return ok, None if ok else "geo mismatch"

    def handle_has_relation(
        self, value: dict[str, Any], authorization_input: AuthorizationInput
    ) -> tuple[bool, str | None]:
        if not isinstance(value, dict):
            return False, "invalid has_relation"
        relation = value.get("relation")
        object_type = value.get("object_type")
        object_id = value.get("object_id")
        object_id_from_resource = value.get("object_id_from_resource")
        if object_id is None and isinstance(object_id_from_resource, str):
            object_id = authorization_input.resource.get(object_id_from_resource)

        if not isinstance(relation, str) or not isinstance(object_type, str) or object_id is None:
            return False, "invalid has_relation"

        relations = authorization_input.user.get("relations", [])
        if not isinstance(relations, list):
            return False, "no relations"

        object_id_str = str(object_id)
        for edge in relations:
            if not isinstance(edge, dict):
                continue
            if (
                edge.get("relation") == relation
                and edge.get("object_type") == object_type
                and str(edge.get("object_id")) == object_id_str
            ):
                return True, None
        return False, "relation mismatch"


class KeyNetraEngine:
    """Deterministic evaluator over explicit input and policy definitions."""

    def __init__(
        self,
        policies: list[PolicyDefinition | dict[str, Any]],
        strategy: str = "first_match",
        compiled_graph: DecisionGraph | None = None,
    ) -> None:
        parsed = [
            p if isinstance(p, PolicyDefinition) else PolicyDefinition.from_dict(p)
            for p in policies
        ]
        self._policies: tuple[PolicyDefinition, ...] = tuple(
            sorted(parsed, key=lambda policy: policy.priority)
        )
        self._evaluator = ConditionEvaluator()
        self._compiled_graph = compiled_graph or compile_policy_graph(
            [
                {
                    "action": policy.action,
                    "effect": policy.effect,
                    "priority": policy.priority,
                    "conditions": policy.conditions,
                    "policy_id": policy.policy_id,
                }
                for policy in self._policies
            ],
            self._evaluator,
        )
        self._strategy = strategy

    def decide(
        self,
        authorization_input: AuthorizationInput | dict[str, Any],
        action: str | None = None,
        resource: dict[str, Any] | None = None,
    ) -> AuthorizationDecision:
        """Evaluate access.

        The legacy ``decide(user, action, resource)`` call shape remains
        supported for compatibility, but all new code should pass a single
        ``AuthorizationInput`` instance.
        """

        normalized_input = self._normalize_input(
            authorization_input, action=action, resource=resource
        )
        return self._decide_structured(normalized_input)

    def check_access(
        self,
        *,
        subject: str | dict[str, Any],
        action: str,
        resource: str | dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AuthorizationDecision:
        """Headless convenience API for direct engine embedding.

        This method intentionally performs lightweight subject/resource parsing
        only, then delegates to the deterministic ``decide`` pipeline.
        """

        user_payload = self._normalize_subject(subject)
        resource_payload = self._normalize_resource(resource)
        return self.decide(
            AuthorizationInput(
                user=user_payload,
                action=action,
                resource=resource_payload,
                context=dict(context or {}),
            )
        )

    def _normalize_input(
        self,
        authorization_input: AuthorizationInput | dict[str, Any],
        *,
        action: str | None,
        resource: dict[str, Any] | None,
    ) -> AuthorizationInput:
        if isinstance(authorization_input, AuthorizationInput):
            return authorization_input
        if action is None or resource is None:
            raise TypeError(
                "authorization_input, action, and resource are required for legacy decide() calls"
            )
        return AuthorizationInput(
            user=dict(authorization_input), action=action, resource=dict(resource), context={}
        )

    def _normalize_subject(self, subject: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(subject, dict):
            return dict(subject)
        subject_type, subject_id = self._parse_descriptor(subject)
        if subject_type == "user":
            return {"id": subject_id}
        return {"id": subject_id, "subject_type": subject_type}

    def _normalize_resource(self, resource: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(resource, dict):
            return dict(resource)
        resource_type, resource_id = self._parse_descriptor(resource)
        return {
            "id": resource_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "type": resource_type,
        }

    def _parse_descriptor(self, value: str) -> tuple[str, str]:
        normalized = str(value).strip()
        if ":" not in normalized:
            return normalized or "unknown", normalized or ""
        prefix, suffix = normalized.split(":", 1)
        return prefix.strip() or "unknown", suffix.strip()

    def _decide_structured(self, authorization_input: AuthorizationInput) -> AuthorizationDecision:
        total_started = time.perf_counter()
        trace: list[ExplainTraceStep] = [
            ExplainTraceStep(
                step="start",
                outcome="continue",
                detail=f"evaluate action={authorization_input.action}",
            )
        ]
        user_subjects = self._subject_descriptors(authorization_input)

        stage_started = time.perf_counter()
        stage = self._evaluate_direct_permissions(authorization_input, trace=trace)
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="rbac",
            value=time.perf_counter() - stage_started,
        )
        if stage[0] != "abstain":
            return self._decision_from_stage(
                stage,
                trace=trace,
                policy_id="rbac:permissions",
                matched=("rbac:permissions",),
                authorization_input=authorization_input,
                total_started=total_started,
            )

        stage_started = time.perf_counter()
        stage = self._evaluate_acl(authorization_input, trace=trace, user_subjects=user_subjects)
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="acl",
            value=time.perf_counter() - stage_started,
        )
        if stage[0] != "abstain":
            return self._decision_from_stage(
                stage,
                trace=trace,
                policy_id=stage[2],
                matched=(stage[2],) if stage[2] else (),
                authorization_input=authorization_input,
                total_started=total_started,
            )

        stage_started = time.perf_counter()
        stage = self._evaluate_role_permissions(authorization_input, trace=trace)
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="rbac",
            value=time.perf_counter() - stage_started,
        )
        if stage[0] != "abstain":
            return self._decision_from_stage(
                stage,
                trace=trace,
                policy_id="rbac:role",
                matched=("rbac:role",),
                authorization_input=authorization_input,
                total_started=total_started,
            )

        stage_started = time.perf_counter()
        stage = self._evaluate_relationship_index(
            authorization_input, trace=trace, user_subjects=user_subjects
        )
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="relationship",
            value=time.perf_counter() - stage_started,
        )
        if stage[0] != "abstain":
            return self._decision_from_stage(
                stage,
                trace=trace,
                policy_id="relationship:index",
                matched=("relationship:index",),
                authorization_input=authorization_input,
                total_started=total_started,
            )

        stage_started = time.perf_counter()
        stage = self._evaluate_permission_graph(authorization_input, trace=trace)
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="schema",
            value=time.perf_counter() - stage_started,
        )
        if stage[0] != "abstain":
            return self._decision_from_stage(
                stage,
                trace=trace,
                policy_id=stage[2],
                matched=(stage[2],) if stage[2] else (),
                authorization_input=authorization_input,
                total_started=total_started,
            )

        stage_started = time.perf_counter()
        stage = self._evaluate_compiled_policies(authorization_input, trace=trace)
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="policy",
            value=time.perf_counter() - stage_started,
        )
        if stage[0] != "abstain":
            return self._decision_from_stage(
                stage,
                trace=trace,
                policy_id=stage[2],
                matched=(stage[2],) if stage[2] else (),
                authorization_input=authorization_input,
                total_started=total_started,
            )

        trace.append(ExplainTraceStep(step="final", outcome="deny", detail="no matching policy"))
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="total",
            value=time.perf_counter() - total_started,
        )
        record_access_check(tenant=authorization_input.tenant_key, decision="deny")
        return AuthorizationDecision(
            allowed=False,
            decision="deny",
            reason="no matching policy",
            policy_id=None,
            explain_trace=tuple(trace),
            matched_policies=(),
            failed_conditions=(),
        )

    def _decision_from_stage(
        self,
        stage: tuple[StageOutcome, str | None, str | None],
        *,
        trace: list[ExplainTraceStep],
        policy_id: str | None,
        matched: tuple[str, ...],
        authorization_input: AuthorizationInput,
        total_started: float,
    ) -> AuthorizationDecision:
        outcome, reason, stage_policy_id = stage
        final_policy_id = stage_policy_id or policy_id
        final_detail = reason or f"decision {outcome}"
        if final_policy_id == "rbac:permissions" and outcome == "allow":
            final_detail = "granted by explicit permission"
        trace.append(
            ExplainTraceStep(
                step="final",
                outcome=outcome,
                detail=final_detail,
                policy_id=final_policy_id,
            )
        )
        observe_access_check_latency(
            tenant=authorization_input.tenant_key,
            stage="total",
            value=time.perf_counter() - total_started,
        )
        record_access_check(
            tenant=authorization_input.tenant_key,
            decision="allow" if outcome == "allow" else "deny",
        )
        return AuthorizationDecision(
            allowed=outcome == "allow",
            decision="allow" if outcome == "allow" else "deny",
            reason=reason,
            policy_id=final_policy_id,
            explain_trace=tuple(trace),
            matched_policies=matched if outcome == "allow" else (),
            failed_conditions=(),
        )

    def _evaluate_direct_permissions(
        self, authorization_input: AuthorizationInput, *, trace: list[ExplainTraceStep]
    ) -> tuple[StageOutcome, str | None, str | None]:
        permissions = authorization_input.user.get(
            "direct_permissions", authorization_input.user.get("permissions", [])
        )
        if isinstance(permissions, list) and authorization_input.action in permissions:
            trace.append(
                ExplainTraceStep(
                    step="rbac_permissions",
                    outcome="matched",
                    detail="explicit permission grant matched input action",
                    policy_id="rbac:permissions",
                )
            )
            return "allow", "explicit permission grant", "rbac:permissions"
        trace.append(
            ExplainTraceStep(
                step="rbac_permissions", outcome="abstain", detail="no direct permission match"
            )
        )
        return "abstain", None, None

    def _evaluate_acl(
        self,
        authorization_input: AuthorizationInput,
        *,
        trace: list[ExplainTraceStep],
        user_subjects: set[str],
    ) -> tuple[StageOutcome, str | None, str | None]:
        resource_type, resource_id = self._resource_identity(authorization_input.resource)
        if not resource_type or not resource_id:
            trace.append(
                ExplainTraceStep(
                    step="acl", outcome="abstain", detail="resource identity unavailable"
                )
            )
            return "abstain", None, None
        acl_entries = authorization_input.acl_entries
        if not acl_entries and authorization_input.access_index_entries:
            acl_entries = tuple(
                entry
                for entry in authorization_input.access_index_entries
                if str(entry.get("source")) == "acl"
            )
        matched = False
        for entry in acl_entries:
            if self._acl_matches(
                entry, resource_type, resource_id, authorization_input.action, user_subjects
            ):
                matched = True
                record_acl_match(tenant=authorization_input.tenant_key)
                effect = str(entry.get("effect", "deny")).lower()
                subject = f"{entry.get('subject_type')}:{entry.get('subject_id')}"
                trace.append(
                    ExplainTraceStep(
                        step="acl",
                        outcome=effect if effect in {"allow", "deny"} else "abstain",
                        detail=f"matched ACL entry {subject} {authorization_input.action} {resource_type}:{resource_id}",
                        policy_id=f"acl:{entry.get('id')}",
                    )
                )
                if effect in {"allow", "deny"}:
                    return (
                        effect,
                        f"matched ACL entry {subject} {authorization_input.action} {resource_type}:{resource_id}",
                        f"acl:{entry.get('id')}",
                    )
        if not matched:
            trace.append(ExplainTraceStep(step="acl", outcome="abstain", detail="no ACL match"))
        return "abstain", None, None

    def _evaluate_role_permissions(
        self, authorization_input: AuthorizationInput, *, trace: list[ExplainTraceStep]
    ) -> tuple[StageOutcome, str | None, str | None]:
        permissions = authorization_input.user.get("role_permissions", [])
        if isinstance(permissions, list) and authorization_input.action in permissions:
            trace.append(
                ExplainTraceStep(
                    step="rbac_role",
                    outcome="allow",
                    detail="role permission grant",
                    policy_id="rbac:role",
                )
            )
            return "allow", "role permission grant", "rbac:role"
        trace.append(
            ExplainTraceStep(step="rbac_role", outcome="abstain", detail="no role permission match")
        )
        return "abstain", None, None

    def _evaluate_relationship_index(
        self,
        authorization_input: AuthorizationInput,
        *,
        trace: list[ExplainTraceStep],
        user_subjects: set[str],
    ) -> tuple[StageOutcome, str | None, str | None]:
        record_relationship_traversal(tenant=authorization_input.tenant_key)
        resource_type, resource_id = self._resource_identity(authorization_input.resource)
        if not resource_type or not resource_id:
            trace.append(
                ExplainTraceStep(
                    step="relationship", outcome="abstain", detail="resource identity unavailable"
                )
            )
            return "abstain", None, None
        for entry in authorization_input.access_index_entries:
            if str(entry.get("source")) != "relationship":
                continue
            if (
                str(entry.get("resource_type")) != resource_type
                or str(entry.get("resource_id")) != resource_id
            ):
                continue
            if str(entry.get("action")) not in {authorization_input.action, "*"}:
                continue
            allowed = entry.get("allowed_subjects", [])
            if not isinstance(allowed, (list, tuple, set)):
                continue
            if any(str(subject) in user_subjects for subject in allowed):
                trace.append(
                    ExplainTraceStep(
                        step="relationship",
                        outcome="allow",
                        detail=f"relationship index match for {resource_type}:{resource_id}",
                        policy_id="relationship:index",
                    )
                )
                return (
                    "allow",
                    f"relationship index match for {resource_type}:{resource_id}",
                    "relationship:index",
                )
        trace.append(
            ExplainTraceStep(
                step="relationship", outcome="abstain", detail="no relationship index match"
            )
        )
        return "abstain", None, None

    def _evaluate_compiled_policies(
        self, authorization_input: AuthorizationInput, *, trace: list[ExplainTraceStep]
    ) -> tuple[StageOutcome, str | None, str | None]:
        record_policy_evaluation(tenant=authorization_input.tenant_key)
        graph = authorization_input.compiled_graph or self._compiled_graph
        graph_decision = graph.evaluate(authorization_input)
        if graph_decision.outcome == "abstain":
            trace.append(
                ExplainTraceStep(
                    step="policy_graph", outcome="abstain", detail="no matching policy node"
                )
            )
            return "abstain", None, None
        trace.append(
            ExplainTraceStep(
                step="policy_graph",
                outcome=graph_decision.outcome,
                detail=graph_decision.reason or f"decision {graph_decision.outcome}",
                policy_id=graph_decision.policy_id,
            )
        )
        return graph_decision.outcome, graph_decision.reason, graph_decision.policy_id

    def _evaluate_permission_graph(
        self, authorization_input: AuthorizationInput, *, trace: list[ExplainTraceStep]
    ) -> tuple[StageOutcome, str | None, str | None]:
        graph = authorization_input.permission_graph
        if graph is None:
            trace.append(
                ExplainTraceStep(
                    step="permission_graph", outcome="abstain", detail="no authorization model"
                )
            )
            return "abstain", None, None
        graph_decision = graph.evaluate(authorization_input)
        if graph_decision.outcome == "abstain":
            trace.append(
                ExplainTraceStep(
                    step="permission_graph",
                    outcome="abstain",
                    detail="permission graph did not apply",
                )
            )
            return "abstain", None, None
        trace.append(
            ExplainTraceStep(
                step="permission_graph",
                outcome=graph_decision.outcome,
                detail=graph_decision.reason or f"decision {graph_decision.outcome}",
                policy_id=graph_decision.policy_id,
            )
        )
        return graph_decision.outcome, graph_decision.reason, graph_decision.policy_id

    def _subject_descriptors(self, authorization_input: AuthorizationInput) -> set[str]:
        descriptors: set[str] = set()
        user = authorization_input.user
        user_id = user.get("id")
        if user_id is not None:
            descriptors.add(f"user:{user_id}")
        roles = user.get("roles", [])
        if isinstance(roles, list):
            descriptors.update(f"role:{role}" for role in roles if role is not None)
        permissions = user.get("permissions", [])
        if isinstance(permissions, list):
            descriptors.update(
                f"permission:{permission}" for permission in permissions if permission is not None
            )
        direct_permissions = user.get("direct_permissions", [])
        if isinstance(direct_permissions, list):
            descriptors.update(
                f"permission:{permission}"
                for permission in direct_permissions
                if permission is not None
            )
        relations = user.get("relations", [])
        if isinstance(relations, list):
            for relation in relations:
                if not isinstance(relation, dict):
                    continue
                relation_type = str(relation.get("relation", ""))
                object_type = str(relation.get("object_type", ""))
                object_id = str(relation.get("object_id", ""))
                if relation_type and object_type and object_id:
                    descriptors.add(f"relationship:{relation_type}:{object_type}:{object_id}")
        return descriptors

    def _resource_identity(self, resource: dict[str, Any]) -> tuple[str, str]:
        resource_type = str(
            resource.get("resource_type")
            or resource.get("type")
            or resource.get("kind")
            or resource.get("entity_type")
            or ""
        )
        resource_id = str(resource.get("resource_id") or resource.get("id") or "")
        return resource_type, resource_id

    def _acl_matches(
        self,
        entry: dict[str, Any],
        resource_type: str,
        resource_id: str,
        action: str,
        user_subjects: set[str],
    ) -> bool:
        if (
            str(entry.get("resource_type")) != resource_type
            or str(entry.get("resource_id")) != resource_id
        ):
            return False
        if str(entry.get("action")) != action:
            return False
        subject_type = str(entry.get("subject_type", ""))
        subject_id = str(entry.get("subject_id", ""))
        return self._acl_subject_matches(subject_type, subject_id, user_subjects)

    def _acl_subject_matches(
        self, subject_type: str, subject_id: str, user_subjects: set[str]
    ) -> bool:
        if not subject_type or not subject_id:
            return False
        if subject_type == "relationship":
            normalized_subject_id = (
                subject_id[12:] if subject_id.startswith("relationship:") else subject_id
            )
            candidates = {
                subject_id,
                normalized_subject_id,
                f"relationship:{normalized_subject_id}",
            }
            return any(candidate in user_subjects for candidate in candidates)
        return f"{subject_type}:{subject_id}" in user_subjects

    def _decision_from_policy(
        self,
        policy: PolicyDefinition,
        *,
        trace: list[ExplainTraceStep],
        failed_conditions: list[str],
    ) -> AuthorizationDecision:
        policy_id = self._policy_id(policy)
        trace.append(
            ExplainTraceStep(
                step="final",
                outcome=policy.effect,
                detail=f"selected policy effect={policy.effect}",
                policy_id=policy_id,
            )
        )
        return AuthorizationDecision(
            allowed=policy.effect == "allow",
            decision=policy.effect,
            reason=f"matched policy {policy_id}" if policy_id else "matched policy",
            policy_id=policy_id,
            explain_trace=tuple(trace),
            matched_policies=(policy_id,) if policy_id is not None else (),
            failed_conditions=tuple(failed_conditions),
        )

    def _best_reason(
        self, evaluated: list[tuple[PolicyDefinition, bool, str | None]]
    ) -> str | None:
        for _policy, matched, reason in evaluated:
            if not matched and reason:
                return reason
        return None

    def _policy_id(self, policy: PolicyDefinition) -> str | None:
        return policy.policy_id or f"{policy.action}:{policy.priority}:{policy.effect}"
