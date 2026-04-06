from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import APIRouter

from keynetra.api.router import api_router
from keynetra.infrastructure.cache import user_cache
from keynetra.services import audit, policy_store, relationship_store, tenant_store, user_store
from keynetra.services.policy_admin import PolicyAdmin


def test_api_router_alias_is_built() -> None:
    assert isinstance(api_router, APIRouter)
    assert any(route.path == "/health" for route in api_router.routes)


def test_deprecated_store_alias_exports() -> None:
    assert audit.AuditWriter.__name__ == "SqlAuditRepository"
    assert policy_store.PolicyStore.__name__ == "SqlPolicyRepository"
    assert relationship_store.RelationshipStore.__name__ == "SqlRelationshipRepository"
    assert tenant_store.TenantStore.__name__ == "SqlTenantRepository"
    assert user_store.UserStore.__name__ == "SqlUserRepository"


def test_get_cached_user_context_none_when_redis_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_cache, "get_redis", lambda: None)
    assert user_cache.get_cached_user_context("user:1") is None


def test_get_cached_user_context_none_when_get_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenRedis:
        def get(self, _key: str) -> str:
            raise RuntimeError("boom")

    monkeypatch.setattr(user_cache, "get_redis", lambda: BrokenRedis())
    assert user_cache.get_cached_user_context("user:1") is None


def test_get_cached_user_context_none_for_empty_invalid_or_non_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedis:
        def __init__(self, value: str | None) -> None:
            self._value = value

        def get(self, _key: str) -> str | None:
            return self._value

    monkeypatch.setattr(user_cache, "get_redis", lambda: FakeRedis(None))
    assert user_cache.get_cached_user_context("user:1") is None

    monkeypatch.setattr(user_cache, "get_redis", lambda: FakeRedis("not-json"))
    assert user_cache.get_cached_user_context("user:1") is None

    monkeypatch.setattr(user_cache, "get_redis", lambda: FakeRedis(json.dumps(["not", "dict"])))
    assert user_cache.get_cached_user_context("user:1") is None


def test_get_cached_user_context_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"id": 1, "role": "admin"}

    class FakeRedis:
        def get(self, _key: str) -> str:
            return json.dumps(payload)

    monkeypatch.setattr(user_cache, "get_redis", lambda: FakeRedis())
    assert user_cache.get_cached_user_context("user:1") == payload


def test_set_cached_user_context_handles_none_and_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(user_cache, "get_redis", lambda: None)
    user_cache.set_cached_user_context("user:1", {"id": 1}, ttl_seconds=5)

    class BrokenRedis:
        def setex(self, _key: str, _ttl: int, _value: str) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(user_cache, "get_redis", lambda: BrokenRedis())
    user_cache.set_cached_user_context("user:1", {"id": 1}, ttl_seconds=5)


def test_set_cached_user_context_calls_setex_with_min_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeRedis:
        def setex(self, key: str, ttl: int, value: str) -> None:
            captured["key"] = key
            captured["ttl"] = ttl
            captured["value"] = value

    monkeypatch.setattr(user_cache, "get_redis", lambda: FakeRedis())
    user_cache.set_cached_user_context("user:1", {"id": 1, "role": "admin"}, ttl_seconds=0)

    assert captured["key"] == "user:1"
    assert captured["ttl"] == 1
    assert captured["value"] == '{"id":1,"role":"admin"}'


def test_policy_admin_create_policy_version_success(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = PolicyAdmin()
    fake_db = object()
    created: dict[str, object] = {}

    class FakeTenantRepo:
        def __init__(self, _db: object) -> None:
            pass

        def get_by_id(self, tenant_id: int) -> SimpleNamespace | None:
            assert tenant_id == 7
            return SimpleNamespace(id=7, tenant_key="default")

    class FakePolicyService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def create_policy(self, **kwargs: object) -> dict[str, object]:
            created.update(kwargs)
            return {"ok": True}

    monkeypatch.setattr("keynetra.services.policy_admin.get_settings", lambda: object())
    monkeypatch.setattr("keynetra.services.policy_admin.SqlTenantRepository", FakeTenantRepo)
    monkeypatch.setattr("keynetra.services.policy_admin.SqlPolicyRepository", lambda _db: object())
    monkeypatch.setattr("keynetra.services.policy_admin.build_policy_cache", lambda _r: object())
    monkeypatch.setattr("keynetra.services.policy_admin.build_decision_cache", lambda _r: object())
    monkeypatch.setattr(
        "keynetra.services.policy_admin.RedisPolicyEventPublisher",
        lambda _settings: object(),
    )
    monkeypatch.setattr("keynetra.services.policy_admin.PolicyService", FakePolicyService)

    result = admin.create_policy_version(
        fake_db,
        tenant_id=7,
        policy_key="doc-read",
        action="read",
        effect="allow",
        priority=10,
        conditions={"role": "admin"},
        created_by="u1",
    )
    assert result == {"ok": True}
    assert created["tenant_key"] == "default"
    assert created["policy_key"] == "doc-read"


def test_policy_admin_create_policy_version_raises_when_tenant_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = PolicyAdmin()

    class FakeTenantRepo:
        def __init__(self, _db: object) -> None:
            pass

        def get_by_id(self, _tenant_id: int) -> None:
            return None

    monkeypatch.setattr("keynetra.services.policy_admin.get_settings", lambda: object())
    monkeypatch.setattr("keynetra.services.policy_admin.SqlTenantRepository", FakeTenantRepo)

    with pytest.raises(ValueError, match="tenant not found"):
        admin.create_policy_version(
            object(),
            tenant_id=1,
            policy_key="x",
            action="read",
            effect="allow",
            priority=1,
            conditions={},
            created_by=None,
        )


def test_policy_admin_rollback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = PolicyAdmin()
    rolled_back: dict[str, object] = {}

    class FakeTenantRepo:
        def __init__(self, _db: object) -> None:
            pass

        def get_by_id(self, tenant_id: int) -> SimpleNamespace | None:
            assert tenant_id == 8
            return SimpleNamespace(id=8, tenant_key="default")

    class FakePolicyService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def rollback_policy(self, **kwargs: object) -> tuple[str, int]:
            rolled_back.update(kwargs)
            return ("doc-read", 3)

    monkeypatch.setattr("keynetra.services.policy_admin.get_settings", lambda: object())
    monkeypatch.setattr("keynetra.services.policy_admin.SqlTenantRepository", FakeTenantRepo)
    monkeypatch.setattr("keynetra.services.policy_admin.SqlPolicyRepository", lambda _db: object())
    monkeypatch.setattr("keynetra.services.policy_admin.build_policy_cache", lambda _r: object())
    monkeypatch.setattr("keynetra.services.policy_admin.build_decision_cache", lambda _r: object())
    monkeypatch.setattr(
        "keynetra.services.policy_admin.RedisPolicyEventPublisher",
        lambda _settings: object(),
    )
    monkeypatch.setattr("keynetra.services.policy_admin.PolicyService", FakePolicyService)

    result = admin.rollback_policy(object(), tenant_id=8, policy_key="doc-read", version=2)
    assert result.policy_key == "doc-read"
    assert result.current_version == 3
    assert rolled_back["tenant_key"] == "default"


def test_policy_admin_rollback_raises_when_tenant_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = PolicyAdmin()

    class FakeTenantRepo:
        def __init__(self, _db: object) -> None:
            pass

        def get_by_id(self, _tenant_id: int) -> None:
            return None

    monkeypatch.setattr("keynetra.services.policy_admin.get_settings", lambda: object())
    monkeypatch.setattr("keynetra.services.policy_admin.SqlTenantRepository", FakeTenantRepo)

    with pytest.raises(ValueError, match="tenant not found"):
        admin.rollback_policy(object(), tenant_id=1, policy_key="x", version=1)
