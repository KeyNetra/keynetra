"""Authorization orchestration service.

This layer coordinates validation, repository access, caching, and audit
writing. The decision engine remains pure and receives only explicit input.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from keynetra.config.settings import Settings
from keynetra.engine.compiled.decision_graph import COMPILED_POLICY_STORE
from keynetra.engine.keynetra_engine import (
    AuthorizationDecision,
    AuthorizationInput,
    ExplainTraceStep,
    KeyNetraEngine,
)
from keynetra.engine.model_graph.permission_graph import MODEL_GRAPH_STORE, CompiledPermissionGraph
from keynetra.infrastructure.logging import log_event
from keynetra.infrastructure.metrics import (
    observe_decision_latency,
    record_auth_fail_closed,
    record_auth_fail_open,
    record_backend_timeout,
    record_cache_event,
)
from keynetra.services.access_indexer import AccessIndexer
from keynetra.services.attribute_validation import validate_resource, validate_user
from keynetra.services.errors import TenantNotFoundError
from keynetra.services.interfaces import (
    AccessIndexCache,
    ACLCache,
    ACLRepository,
    AuditRepository,
    AuthModelRepository,
    CachedDecision,
    DecisionCache,
    PolicyCache,
    PolicyRepository,
    RelationshipCache,
    RelationshipRepository,
    TenantRepository,
    UserRepository,
)
from keynetra.services.resilience import retry, with_timeout
from keynetra.services.revisions import RevisionService


@dataclass(frozen=True)
class AuthorizationResult:
    """Service-level authorization result used by API and tests."""

    decision: AuthorizationDecision
    cached: bool
    revision: int


class AuthorizationService:
    """Compose persistence, caches, and the pure engine into one flow."""

    def __init__(
        self,
        *,
        settings: Settings,
        tenants: TenantRepository,
        policies: PolicyRepository,
        users: UserRepository,
        relationships: RelationshipRepository,
        audit: AuditRepository,
        policy_cache: PolicyCache,
        relationship_cache: RelationshipCache,
        decision_cache: DecisionCache,
        acl_repository: ACLRepository | None = None,
        acl_cache: ACLCache | None = None,
        access_index_cache: AccessIndexCache | None = None,
        auth_model_repository: AuthModelRepository | None = None,
        request_id: str | None = None,
    ) -> None:
        self._settings = settings
        self._tenants = tenants
        self._policies = policies
        self._users = users
        self._relationships = relationships
        self._audit = audit
        self._policy_cache = policy_cache
        self._relationship_cache = relationship_cache
        self._decision_cache = decision_cache
        self._acl_repository = acl_repository
        self._acl_cache = acl_cache
        self._access_index_cache = access_index_cache
        self._auth_model_repository = auth_model_repository
        self._request_id = request_id
        self._revisions = RevisionService(tenants)
        self._access_indexer = (
            AccessIndexer(
                acl_repository=acl_repository,
                acl_cache=acl_cache,
                access_index_cache=access_index_cache,
                relationships=relationships,
            )
            if acl_repository is not None
            and acl_cache is not None
            and access_index_cache is not None
            else None
        )
        self._logger = logging.getLogger("keynetra.authorization")

    def authorize(
        self,
        *,
        tenant_key: str,
        principal: dict[str, Any],
        user: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any] | None = None,
        consistency: str = "eventual",
        revision: int | None = None,
        audit: bool = True,
        policy_set: str = "active",
    ) -> AuthorizationResult:
        started_at = time.perf_counter()
        normalized_policy_set = policy_set.strip().lower() or "active"
        consistency_mode = consistency.strip().lower()
        fallback_input = AuthorizationInput(
            user=dict(user),
            action=action,
            resource=dict(resource),
            context=dict(context or {}),
            tenant_key=tenant_key,
        )
        try:
            authorization_input, tenant = self._build_input(
                tenant_key=tenant_key,
                user=user,
                action=action,
                resource=resource,
                context=context or {},
            )
        except TenantNotFoundError:
            raise
        except Exception as exc:
            decision = self._fallback_decision(
                fallback_input, reason=f"authorization input unavailable: {exc}"
            )
            observe_decision_latency(tenant_key=tenant_key, value=time.perf_counter() - started_at)
            return AuthorizationResult(decision=decision, cached=False, revision=1)

        try:
            cache_key = None
            cache_namespace = (
                tenant.tenant_key
                if normalized_policy_set == "active"
                else f"{tenant.tenant_key}:{normalized_policy_set}"
            )
            if consistency_mode != "fully_consistent":
                cache_key = self._decision_cache.make_key(
                    tenant_key=cache_namespace,
                    policy_version=tenant.policy_version,
                    authorization_input=authorization_input,
                    revision=tenant.revision if revision is None else revision,
                )
                cached = self._safe_cache_get(cache_key)
                if cached is not None:
                    observe_decision_latency(
                        tenant_key=tenant.tenant_key, value=time.perf_counter() - started_at
                    )
                    return AuthorizationResult(
                        decision=self._decision_from_cache(cached),
                        cached=True,
                        revision=tenant.revision,
                    )

            engine = self._build_engine(
                tenant_key=tenant.tenant_key,
                tenant_id=tenant.id,
                policy_version=tenant.policy_version,
                policy_set=normalized_policy_set,
            )
            decision = engine.decide(authorization_input)
            if cache_key is not None:
                self._safe_cache_set(cache_key, CachedDecision.from_decision(decision))
            if audit:
                self._safe_audit_write(
                    tenant_id=tenant.id,
                    principal_type=str(principal.get("type")),
                    principal_id=str(principal.get("id")),
                    authorization_input=authorization_input,
                    decision=decision,
                    correlation_id=self._request_id,
                )
            return AuthorizationResult(decision=decision, cached=False, revision=tenant.revision)
        except TenantNotFoundError:
            raise
        except Exception as exc:
            log_event(
                self._logger,
                event="authorization_fallback",
                tenant_id=tenant.tenant_key,
                principal_type=str(principal.get("type")),
                correlation_id=self._request_id,
                resilience_mode=self._settings.resilience_mode,
                fallback_behavior=self._settings.resilience_fallback_behavior,
                reason=repr(exc),
            )
            return AuthorizationResult(
                decision=self._fallback_decision(
                    authorization_input, reason="authorization backend unavailable"
                ),
                cached=False,
                revision=tenant.revision,
            )
        finally:
            observe_decision_latency(tenant_key=tenant_key, value=time.perf_counter() - started_at)

    async def authorize_async(
        self,
        *,
        tenant_key: str,
        principal: dict[str, Any],
        user: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any] | None = None,
        consistency: str = "eventual",
        revision: int | None = None,
        audit: bool = True,
        policy_set: str = "active",
    ) -> AuthorizationResult:
        return await asyncio.to_thread(
            self.authorize,
            tenant_key=tenant_key,
            principal=principal,
            user=user,
            action=action,
            resource=resource,
            context=context,
            consistency=consistency,
            revision=revision,
            audit=audit,
            policy_set=policy_set,
        )

    def authorize_batch(
        self,
        *,
        tenant_key: str,
        principal: dict[str, Any],
        user: dict[str, Any],
        items: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        consistency: str = "eventual",
        revision: int | None = None,
        policy_set: str = "active",
    ) -> list[AuthorizationResult]:
        validate_user(user)
        fallback_context = dict(context or {})
        normalized_policy_set = policy_set.strip().lower() or "active"
        consistency_mode = consistency.strip().lower()
        try:
            tenant = self._require_tenant(tenant_key)
            enriched_user = self._hydrate_user(tenant_id=tenant.id, user=user)
            engine = self._build_engine(
                tenant_key=tenant.tenant_key,
                tenant_id=tenant.id,
                policy_version=tenant.policy_version,
                policy_set=normalized_policy_set,
            )
        except TenantNotFoundError:
            raise
        except (RuntimeError, TimeoutError, ValueError) as exc:
            log_event(
                self._logger,
                event="authorization_batch_fallback",
                reason=repr(exc),
                correlation_id=self._request_id,
            )
            return [
                AuthorizationResult(
                    decision=self._fallback_decision(
                        AuthorizationInput(
                            user=dict(user),
                            action=str(item.get("action", "")),
                            resource=dict(item.get("resource") or {}),
                            context=fallback_context,
                            tenant_key=tenant_key,
                        ),
                        reason="authorization backend unavailable",
                    ),
                    cached=False,
                    revision=1,
                )
                for item in items
            ]

        item_results: list[AuthorizationResult] = []
        memoized_results: dict[
            tuple[str, str, str], tuple[AuthorizationInput, AuthorizationDecision, bool]
        ] = {}
        for item in items:
            resource = dict(item.get("resource") or {})
            validate_resource(resource)
            action = str(item["action"])
            context_payload = dict(context or {})
            memo_key = (
                action,
                json.dumps(resource, sort_keys=True, separators=(",", ":"), default=str),
                json.dumps(context_payload, sort_keys=True, separators=(",", ":"), default=str),
            )
            if memo_key in memoized_results:
                authorization_input, decision, cached = memoized_results[memo_key]
            else:
                authorization_input = self._build_authorization_input(
                    tenant_id=tenant.id,
                    tenant_key=tenant.tenant_key,
                    user=enriched_user,
                    action=action,
                    resource=resource,
                    context=context_payload,
                )
                cache_namespace = (
                    tenant.tenant_key
                    if normalized_policy_set == "active"
                    else f"{tenant.tenant_key}:{normalized_policy_set}"
                )
                cached = False
                if consistency_mode != "fully_consistent":
                    cache_key = self._decision_cache.make_key(
                        tenant_key=cache_namespace,
                        policy_version=tenant.policy_version,
                        authorization_input=authorization_input,
                        revision=tenant.revision if revision is None else revision,
                    )
                    cached_decision = self._safe_cache_get(cache_key)
                    if cached_decision is not None:
                        decision = self._decision_from_cache(cached_decision)
                        cached = True
                    else:
                        decision = engine.decide(authorization_input)
                        self._safe_cache_set(cache_key, CachedDecision.from_decision(decision))
                else:
                    decision = engine.decide(authorization_input)
                memoized_results[memo_key] = (authorization_input, decision, cached)

            self._safe_audit_write(
                tenant_id=tenant.id,
                principal_type=str(principal.get("type")),
                principal_id=str(principal.get("id")),
                authorization_input=authorization_input,
                decision=decision,
                correlation_id=self._request_id,
            )
            item_results.append(
                AuthorizationResult(decision=decision, cached=cached, revision=tenant.revision)
            )

        return item_results

    async def authorize_batch_async(
        self,
        *,
        tenant_key: str,
        principal: dict[str, Any],
        user: dict[str, Any],
        items: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        consistency: str = "eventual",
        revision: int | None = None,
        policy_set: str = "active",
    ) -> list[AuthorizationResult]:
        return await asyncio.to_thread(
            self.authorize_batch,
            tenant_key=tenant_key,
            principal=principal,
            user=user,
            items=items,
            context=context,
            consistency=consistency,
            revision=revision,
            policy_set=policy_set,
        )

    def simulate(
        self,
        *,
        tenant_key: str,
        principal: dict[str, Any],
        user: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AuthorizationDecision:
        result = self.authorize(
            tenant_key=tenant_key,
            principal=principal,
            user=user,
            action=action,
            resource=resource,
            context=context,
            audit=True,
        )
        return result.decision

    def get_revision(self, *, tenant_key: str) -> int:
        return self._revisions.get_revision(tenant_key=tenant_key)

    def build_input(
        self,
        *,
        tenant_key: str,
        user: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AuthorizationInput:
        authorization_input, _ = self._build_input(
            tenant_key=tenant_key,
            user=user,
            action=action,
            resource=resource,
            context=dict(context or {}),
        )
        return authorization_input

    def _build_input(
        self,
        *,
        tenant_key: str,
        user: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[AuthorizationInput, Any]:
        validate_user(user)
        validate_resource(resource)
        tenant = self._require_tenant(tenant_key)
        enriched_user = self._hydrate_user(tenant_id=tenant.id, user=user)
        return (
            self._build_authorization_input(
                tenant_id=tenant.id,
                tenant_key=tenant_key,
                user=enriched_user,
                action=action,
                resource=resource,
                context=context,
            ),
            tenant,
        )

    def _build_authorization_input(
        self,
        *,
        tenant_id: int,
        tenant_key: str,
        user: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
    ) -> AuthorizationInput:
        acl_entries: tuple[dict[str, Any], ...] = ()
        access_entries: tuple[dict[str, Any], ...] = ()
        permission_graph: CompiledPermissionGraph | None = MODEL_GRAPH_STORE.get(tenant_key)
        if permission_graph is None and self._auth_model_repository is not None:
            model_record = self._auth_model_repository.get_model(tenant_id=tenant_id)
            if model_record is not None:
                from keynetra.modeling.permission_compiler import compile_authorization_schema

                compiled = compile_authorization_schema(model_record.schema_text)
                permission_graph = CompiledPermissionGraph(tenant_key=tenant_key, model=compiled)
                MODEL_GRAPH_STORE.set(tenant_key, permission_graph)
        if self._access_indexer is not None:
            resource_type, resource_id = self._resource_identity(resource)
            if resource_type and resource_id:
                entries = self._access_indexer.build_resource_index(
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                )
                access_entries = tuple(entry.__dict__ for entry in entries)
                acl_entries = tuple(
                    {
                        **dict(entry.__dict__),
                        "id": entry.acl_id,
                    }
                    for entry in entries
                    if entry.source == "acl"
                )
        return AuthorizationInput(
            user=user,
            action=action,
            resource=dict(resource),
            context=dict(context),
            tenant_key=tenant_key,
            acl_entries=acl_entries,
            access_index_entries=access_entries,
            permission_graph=permission_graph,
        )

    def _hydrate_user(self, *, tenant_id: int, user: dict[str, Any]) -> dict[str, Any]:
        enriched_user = dict(user)
        direct_permissions = enriched_user.get("permissions", [])
        if isinstance(direct_permissions, list):
            enriched_user["direct_permissions"] = list(direct_permissions)
        user_id = enriched_user.get("id")
        if isinstance(user_id, int):
            persisted_user = with_timeout(
                lambda: self._users.get_user_context(user_id),
                timeout_seconds=self._settings.service_timeout_seconds,
                settings=self._settings,
            )
            if persisted_user is not None:
                enriched_user["roles"] = list(persisted_user.get("roles", []))
                enriched_user["role_permissions"] = list(persisted_user.get("permissions", []))
                enriched_user.setdefault("role", persisted_user.get("role"))
            relationships = self._safe_relationship_cache_get(
                tenant_id=tenant_id, subject_type="user", subject_id=str(user_id)
            )
            if relationships is None:
                relationships = with_timeout(
                    lambda: self._relationships.list_for_subject(
                        tenant_id=tenant_id,
                        subject_type="user",
                        subject_id=str(user_id),
                    ),
                    timeout_seconds=self._settings.service_timeout_seconds,
                    settings=self._settings,
                )
                self._safe_relationship_cache_set(
                    tenant_id=tenant_id,
                    subject_type="user",
                    subject_id=str(user_id),
                    relationships=relationships,
                )
            enriched_user["relations"] = [relationship.to_dict() for relationship in relationships]
        return enriched_user

    def _build_engine(
        self, *, tenant_key: str, tenant_id: int, policy_version: int, policy_set: str = "active"
    ) -> KeyNetraEngine:
        policy_set_key = policy_set.strip().lower() or "active"
        graph_tenant_key = (
            tenant_key if policy_set_key == "active" else f"{tenant_key}:{policy_set_key}"
        )
        cached = (
            self._safe_policy_cache_get(tenant_key, policy_version)
            if policy_set_key == "active"
            else None
        )
        if cached is None:

            def _load_current_policies() -> list[Any]:
                try:
                    return self._policies.list_current_policies(
                        tenant_id=tenant_id, policy_set=policy_set_key
                    )
                except TypeError:
                    # Backward compatibility for repositories that only accept tenant_id.
                    return self._policies.list_current_policies(tenant_id=tenant_id)

            cached = with_timeout(
                _load_current_policies,
                timeout_seconds=self._settings.service_timeout_seconds,
                settings=self._settings,
            )
            if not cached:
                policies = self._settings.load_policies()
                engine = KeyNetraEngine(policies, strategy="first_match")
                COMPILED_POLICY_STORE.set(graph_tenant_key, policy_version, engine._compiled_graph)
                return engine
            if policy_set_key == "active":
                self._safe_policy_cache_set(tenant_key, policy_version, cached)
        policies = [policy.definition for policy in cached]
        engine = KeyNetraEngine(policies, strategy="first_match")
        COMPILED_POLICY_STORE.set(graph_tenant_key, policy_version, engine._compiled_graph)
        return engine

    def _decision_from_cache(self, cached: CachedDecision) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=cached.allowed,
            decision=(
                "allow"
                if cached.allowed
                else (
                    "deny"
                    if cached.decision not in {"allow", "deny"}
                    else "allow" if cached.decision == "allow" else "deny"
                )
            ),
            reason=cached.reason,
            policy_id=cached.policy_id,
            explain_trace=tuple(
                ExplainTraceStep(
                    step=str(item.get("step", "cache")),
                    outcome=str(item.get("outcome", "cached")),
                    detail=str(item.get("detail", "served from decision cache")),
                    policy_id=(
                        item.get("policy_id")
                        if item.get("policy_id") is None
                        else str(item.get("policy_id"))
                    ),
                )
                for item in cached.explain_trace
            ),
            matched_policies=tuple(cached.matched_policies),
            failed_conditions=tuple(cached.failed_conditions),
        )

    def _safe_deny(self, *, reason: str) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=False,
            decision="deny",
            reason=reason,
            policy_id=None,
            explain_trace=(ExplainTraceStep(step="final", outcome="deny", detail=reason),),
            matched_policies=(),
            failed_conditions=(reason,),
        )

    def _safe_allow(self, *, reason: str) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=True,
            decision="allow",
            reason=reason,
            policy_id=None,
            explain_trace=(ExplainTraceStep(step="final", outcome="allow", detail=reason),),
            matched_policies=(),
            failed_conditions=(),
        )

    def _fallback_decision(
        self, authorization_input: AuthorizationInput, *, reason: str
    ) -> AuthorizationDecision:
        behavior = (self._settings.resilience_fallback_behavior or "static").strip().lower()
        if behavior == "default_policy_eval":
            try:
                decision = KeyNetraEngine(
                    self._settings.load_policies(), strategy="first_match"
                ).decide(authorization_input)
                return AuthorizationDecision(
                    allowed=decision.allowed,
                    decision=decision.decision,
                    reason=decision.reason,
                    policy_id=decision.policy_id,
                    explain_trace=tuple(
                        list(decision.explain_trace)
                        + [
                            ExplainTraceStep(
                                step="resilience_fallback",
                                outcome="fallback",
                                detail=reason,
                                policy_id=decision.policy_id,
                            )
                        ]
                    ),
                    matched_policies=decision.matched_policies,
                    failed_conditions=decision.failed_conditions,
                )
            except Exception as exc:
                log_event(
                    self._logger, event="resilience_default_policy_eval_failed", reason=repr(exc)
                )

        if (self._settings.resilience_mode or "fail_closed").strip().lower() == "fail_open":
            record_auth_fail_open()
            return self._safe_allow(reason=reason)
        record_auth_fail_closed()
        return self._safe_deny(reason=reason)

    def _safe_cache_get(self, key: str) -> CachedDecision | None:
        try:
            cached = with_timeout(
                lambda: self._decision_cache.get(key),
                timeout_seconds=self._settings.service_timeout_seconds,
                settings=self._settings,
            )
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                record_backend_timeout(operation="decision_cache_get")
            record_cache_event(cache_name="decision", outcome="fallback")
            log_event(
                self._logger,
                event="cache_get_failed",
                cache_name="decision",
                reason=repr(exc),
                correlation_id=self._request_id,
            )
            return None
        record_cache_event(cache_name="decision", outcome="hit" if cached is not None else "miss")
        return cached

    def _safe_cache_set(self, key: str, value: CachedDecision) -> None:
        try:
            retry(
                lambda: with_timeout(
                    lambda: self._decision_cache.set(
                        key, value, self._settings.decision_cache_ttl_seconds
                    ),
                    timeout_seconds=self._settings.service_timeout_seconds,
                    settings=self._settings,
                ),
                attempts=self._settings.critical_retry_attempts,
            )
        except Exception as exc:
            log_event(
                self._logger,
                event="cache_set_failed",
                cache_name="decision",
                reason=repr(exc),
                correlation_id=self._request_id,
            )

    def _safe_policy_cache_get(self, tenant_key: str, policy_version: int):
        try:
            cached = with_timeout(
                lambda: self._policy_cache.get(tenant_key, policy_version),
                timeout_seconds=self._settings.service_timeout_seconds,
                settings=self._settings,
            )
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                record_backend_timeout(operation="policy_cache_get")
            record_cache_event(cache_name="policy", outcome="fallback")
            log_event(
                self._logger,
                event="cache_get_failed",
                cache_name="policy",
                reason=repr(exc),
                correlation_id=self._request_id,
            )
            return None
        record_cache_event(cache_name="policy", outcome="hit" if cached is not None else "miss")
        return cached

    def _safe_policy_cache_set(
        self, tenant_key: str, policy_version: int, cached: list[Any]
    ) -> None:
        try:
            retry(
                lambda: with_timeout(
                    lambda: self._policy_cache.set(tenant_key, policy_version, cached),
                    timeout_seconds=self._settings.service_timeout_seconds,
                    settings=self._settings,
                ),
                attempts=self._settings.critical_retry_attempts,
            )
        except Exception as exc:
            log_event(
                self._logger,
                event="cache_set_failed",
                cache_name="policy",
                reason=repr(exc),
                correlation_id=self._request_id,
            )

    def _safe_relationship_cache_get(self, *, tenant_id: int, subject_type: str, subject_id: str):
        try:
            cached = with_timeout(
                lambda: self._relationship_cache.get(
                    tenant_id=tenant_id, subject_type=subject_type, subject_id=subject_id
                ),
                timeout_seconds=self._settings.service_timeout_seconds,
                settings=self._settings,
            )
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                record_backend_timeout(operation="relationship_cache_get")
            record_cache_event(cache_name="relationship", outcome="fallback")
            log_event(
                self._logger,
                event="cache_get_failed",
                cache_name="relationship",
                reason=repr(exc),
                correlation_id=self._request_id,
            )
            return None
        record_cache_event(
            cache_name="relationship", outcome="hit" if cached is not None else "miss"
        )
        return cached

    def _safe_relationship_cache_set(
        self, *, tenant_id: int, subject_type: str, subject_id: str, relationships: list[Any]
    ) -> None:
        try:
            retry(
                lambda: with_timeout(
                    lambda: self._relationship_cache.set(
                        tenant_id=tenant_id,
                        subject_type=subject_type,
                        subject_id=subject_id,
                        relationships=relationships,
                    ),
                    timeout_seconds=self._settings.service_timeout_seconds,
                    settings=self._settings,
                ),
                attempts=self._settings.critical_retry_attempts,
            )
        except Exception as exc:
            log_event(
                self._logger,
                event="cache_set_failed",
                cache_name="relationship",
                reason=repr(exc),
                correlation_id=self._request_id,
            )

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

    def _safe_audit_write(self, **kwargs: Any) -> None:
        try:
            retry(
                lambda: with_timeout(
                    lambda: self._audit.write(**kwargs),
                    timeout_seconds=self._settings.service_timeout_seconds,
                    settings=self._settings,
                ),
                attempts=self._settings.critical_retry_attempts,
            )
        except Exception as exc:
            log_event(
                self._logger,
                event="audit_write_failed",
                reason=repr(exc),
                correlation_id=self._request_id,
            )

    def _require_tenant(self, tenant_key: str):
        tenant = with_timeout(
            lambda: self._tenants.get_by_key(tenant_key),
            timeout_seconds=self._settings.service_timeout_seconds,
            settings=self._settings,
        )
        if tenant is None:
            raise TenantNotFoundError(tenant_key)
        return tenant
