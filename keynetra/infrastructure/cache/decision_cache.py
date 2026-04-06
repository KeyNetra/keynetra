"""Decision cache adapter.

The cache lives outside the pure engine. Keys are derived from the fully
hydrated authorization input so cache hits never hide changes to explicit
inputs such as relationships or request context.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from keynetra.engine.keynetra_engine import AuthorizationInput
from keynetra.infrastructure.cache.backends import CacheBackend, build_cache_backend
from keynetra.services.interfaces import CachedDecision


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class RedisBackedDecisionCache:
    """Decision cache with namespace bump invalidation."""

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend

    def get(self, key: str) -> CachedDecision | None:
        raw = self._backend.get(key)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return CachedDecision(
            allowed=bool(payload.get("allowed")),
            decision=str(payload.get("decision", "deny")),
            reason=(
                payload.get("reason")
                if payload.get("reason") is None
                else str(payload.get("reason"))
            ),
            policy_id=(
                payload.get("policy_id")
                if payload.get("policy_id") is None
                else str(payload.get("policy_id"))
            ),
            matched_policies=[
                str(item) for item in payload.get("matched_policies", []) if isinstance(item, str)
            ],
            explain_trace=[
                step for step in payload.get("explain_trace", []) if isinstance(step, dict)
            ],
            failed_conditions=[
                str(item) for item in payload.get("failed_conditions", []) if isinstance(item, str)
            ],
        )

    def set(self, key: str, value: CachedDecision, ttl_seconds: int) -> None:
        payload = {
            "allowed": value.allowed,
            "decision": value.decision,
            "reason": value.reason,
            "policy_id": value.policy_id,
            "matched_policies": value.matched_policies,
            "explain_trace": value.explain_trace,
            "failed_conditions": value.failed_conditions,
        }
        self._backend.set(key, json.dumps(payload, separators=(",", ":")), ttl_seconds)

    def make_key(
        self,
        *,
        tenant_key: str,
        policy_version: int,
        authorization_input: AuthorizationInput,
        revision: int | None = None,
    ) -> str:
        namespace = self._tenant_namespace(tenant_key)
        payload = {
            "tenant_key": tenant_key,
            "policy_version": policy_version,
            "revision": revision,
            "action": authorization_input.action,
            "user": authorization_input.user,
            "resource": authorization_input.resource,
            "context": authorization_input.context,
        }
        digest = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
        return f"dec:{tenant_key}:{namespace}:{policy_version}:{digest}"

    def bump_namespace(self, tenant_key: str) -> int:
        return self._backend.incr(self._namespace_key(tenant_key))

    def _tenant_namespace(self, tenant_key: str) -> int:
        raw = self._backend.get(self._namespace_key(tenant_key))
        return int(raw) if raw is not None else 0

    def _namespace_key(self, tenant_key: str) -> str:
        return f"decns:{tenant_key}"


def build_decision_cache(redis_client: Any | None) -> RedisBackedDecisionCache:
    """Build the default decision cache."""

    return RedisBackedDecisionCache(build_cache_backend(redis_client))
