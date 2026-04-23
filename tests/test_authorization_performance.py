from __future__ import annotations

import time
from typing import Any

from keynetra.config.settings import Settings
from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.infrastructure.cache.backends import InMemoryCacheBackend
from keynetra.infrastructure.cache.decision_cache import RedisBackedDecisionCache
from keynetra.infrastructure.cache.local_ttl import ThreadSafeTTLCache
from keynetra.infrastructure.cache.policy_cache import RedisBackedPolicyCache
from keynetra.infrastructure.cache.relationship_cache import RedisBackedRelationshipCache
from keynetra.services.authorization import AuthorizationService
from keynetra.services.interfaces import PolicyRecord, RelationshipRecord, TenantRecord


class _TenantRepo:
    def __init__(self) -> None:
        self._tenant = TenantRecord(id=1, tenant_key="default", policy_version=1)

    def get_by_key(self, tenant_key: str) -> TenantRecord | None:
        return self._tenant if tenant_key == "default" else None


class _PolicyRepo:
    def __init__(self) -> None:
        self.list_calls = 0

    def list_current_policies(
        self, *, tenant_id: int, policy_set: str = "active"
    ) -> list[PolicyRecord]:
        self.list_calls += 1
        return [
            PolicyRecord(
                id=1,
                definition=PolicyDefinition(
                    action="read",
                    effect="allow",
                    priority=1,
                    policy_id="read:v1",
                    conditions={"role": "admin"},
                ),
            )
        ]


class _UserRepo:
    def get_user_context(self, user_id: int) -> dict[str, Any] | None:
        return {"id": user_id, "role": "admin", "roles": ["admin"], "permissions": []}


class _RelationshipRepo:
    def __init__(self) -> None:
        self.list_calls = 0

    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]:
        self.list_calls += 1
        return [
            RelationshipRecord(
                subject_type=subject_type,
                subject_id=subject_id,
                relation="viewer",
                object_type="document",
                object_id="doc-1",
            )
        ]


class _AuditRepo:
    def write(self, **_: Any) -> None:
        return


def test_authorization_cached_path_stays_fast() -> None:
    backend = InMemoryCacheBackend()
    policy_repo = _PolicyRepo()
    relationship_repo = _RelationshipRepo()
    service = AuthorizationService(
        settings=Settings(api_keys="testkey"),
        tenants=_TenantRepo(),
        policies=policy_repo,
        users=_UserRepo(),
        relationships=relationship_repo,
        audit=_AuditRepo(),
        policy_cache=RedisBackedPolicyCache(backend),
        relationship_cache=RedisBackedRelationshipCache(backend),
        decision_cache=RedisBackedDecisionCache(backend),
    )

    for _ in range(5):
        result = service.authorize(
            tenant_key="default",
            principal={"type": "api_key", "id": "testkey"},
            user={"id": 7},
            action="read",
            resource={"id": "doc-1", "resource_id": "doc-1", "resource_type": "document"},
        )
        assert result.decision.allowed is True

    started = time.perf_counter()
    for _ in range(1000):
        result = service.authorize(
            tenant_key="default",
            principal={"type": "api_key", "id": "testkey"},
            user={"id": 7},
            action="read",
            resource={"id": "doc-1", "resource_id": "doc-1", "resource_type": "document"},
        )
        assert result.decision.allowed is True
    duration = time.perf_counter() - started

    assert duration < 0.5
    assert policy_repo.list_calls == 1
    assert relationship_repo.list_calls == 1


def test_thread_safe_ttl_cache_is_bounded_and_expires() -> None:
    cache = ThreadSafeTTLCache[str, str](max_entries=2)
    cache.set("a", "1", ttl_seconds=0.01)
    cache.set("b", "2", ttl_seconds=10)
    cache.set("c", "3", ttl_seconds=10)

    assert cache.get("a") is None
    assert cache.get("b") == "2"
    assert cache.get("c") == "3"

    time.sleep(0.02)

    assert cache.get("b") == "2"
    assert cache.get("c") == "3"


def test_thread_safe_ttl_cache_supports_default_ttl_and_mutation_helpers() -> None:
    now = [0.0]
    cache = ThreadSafeTTLCache[str, str](
        max_entries=4,
        default_ttl_seconds=1.0,
        clock=lambda: now[0],
    )

    cache.set("token", "value")
    assert cache.get_with_expiry("token") is not None
    assert cache.get("token") == "value"
    now[0] = 1.5
    assert cache.get("token") is None

    cache.set("persist", "forever", ttl_seconds=None)
    assert cache.get("persist") == "forever"
    cache.delete("persist")
    assert cache.get("persist") is None

    cache.set("a", "1", ttl_seconds=5.0)
    cache.set("b", "2", ttl_seconds=5.0)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
