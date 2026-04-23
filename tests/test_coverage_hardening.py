from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.main import (
    _bootstrap_file_backed_model,
    _ensure_bootstrap_tenant,
    _run_startup,
    _start_policy_subscriber,
    _stop_policy_subscriber,
)
from keynetra.api.routes.access import (
    AccessRequest,
    BatchAccessRequest,
    check_access,
    check_access_batch,
    simulate,
)
from keynetra.config.security import _get_jwks, _load_persistent_api_key_scopes, get_principal
from keynetra.engine.keynetra_engine import (
    AuthorizationDecision,
    AuthorizationInput,
    ExplainTraceStep,
)
from keynetra.infrastructure.errors import BootstrapError
from keynetra.services.access_indexer import AccessIndexer, relationship_descriptor
from keynetra.services.authorization import AuthorizationResult, AuthorizationService
from keynetra.services.errors import TenantNotFoundError
from keynetra.services.interfaces import (
    AccessIndexEntry,
    ACLRecord,
    AuthModelRecord,
    CachedDecision,
    PolicyRecord,
    RelationshipRecord,
    TenantRecord,
)


class DummyRequest(SimpleNamespace):
    def __init__(
        self, *, headers: dict[str, str] | None = None, path: str = "/check-access"
    ) -> None:
        super().__init__(
            headers=headers or {},
            method="POST",
            url=SimpleNamespace(path=path),
            client=SimpleNamespace(host="127.0.0.1"),
            state=SimpleNamespace(request_id="req-1"),
        )


class DummySettings:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)
        self._api_key_hashes = kwargs.get("_api_key_hashes", set[str]())
        self._api_key_scopes = kwargs.get("_api_key_scopes", {})
        self.database_url = kwargs.get("database_url", "sqlite+pysqlite:///./test.db")
        self.jwt_secret = kwargs.get("jwt_secret", "secret")
        self.jwt_algorithm = kwargs.get("jwt_algorithm", "HS256")
        self.oidc_jwks_url = kwargs.get("oidc_jwks_url")
        self.oidc_audience = kwargs.get("oidc_audience")
        self.oidc_issuer = kwargs.get("oidc_issuer")
        self.jwks_cache_ttl_seconds = kwargs.get("jwks_cache_ttl_seconds", 30)
        self.jwks_backoff_max_seconds = kwargs.get("jwks_backoff_max_seconds", 8)
        self.service_timeout_seconds = kwargs.get("service_timeout_seconds", 1.0)
        self.critical_retry_attempts = kwargs.get("critical_retry_attempts", 1)
        self.decision_cache_ttl_seconds = kwargs.get("decision_cache_ttl_seconds", 5)
        self.resilience_mode = kwargs.get("resilience_mode", "fail_closed")
        self.resilience_fallback_behavior = kwargs.get("resilience_fallback_behavior", "static")
        self.async_authorization_enabled = kwargs.get("async_authorization_enabled", False)
        self.strict_tenancy = kwargs.get("strict_tenancy", False)
        self.environment = kwargs.get("environment", "development")
        self.run_migrations = kwargs.get("run_migrations", False)
        self.auto_seed_sample_data = kwargs.get("auto_seed_sample_data", False)
        self.service_mode = kwargs.get("service_mode", "all")
        self.policy_events_channel = kwargs.get("policy_events_channel", "policy-events")

    def parsed_api_key_hashes(self) -> set[str]:
        return set(self._api_key_hashes)

    def parsed_api_key_scopes(self) -> dict[str, dict[str, Any]]:
        return dict(self._api_key_scopes)

    def is_development(self) -> bool:
        return self.environment in {"development", "dev", "local"}

    def load_policies(self) -> list[dict[str, Any]]:
        return [{"action": "read", "effect": "allow", "priority": 1, "conditions": {}}]

    def parsed_model_paths(self) -> list[str]:
        return []

    def resolved_resilience_executor_workers(self) -> int:
        return 1


class FakeTenantRepo:
    def __init__(self) -> None:
        self.record = TenantRecord(id=1, tenant_key="acme", policy_version=7, revision=3)
        self.created: list[str] = []

    def get_by_key(self, tenant_key: str) -> TenantRecord | None:
        return self.record if tenant_key == self.record.tenant_key else None

    def create(self, tenant_key: str) -> TenantRecord:
        self.created.append(tenant_key)
        return self.record

    def get_or_create(self, tenant_key: str) -> TenantRecord:
        self.created.append(tenant_key)
        return self.record

    def get_by_id(self, tenant_id: int) -> TenantRecord | None:
        return self.record if tenant_id == self.record.id else None

    def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
        return TenantRecord(
            id=tenant.id,
            tenant_key=tenant.tenant_key,
            policy_version=tenant.policy_version + 1,
            revision=tenant.revision,
        )

    def bump_revision(self, tenant: TenantRecord) -> TenantRecord:
        return TenantRecord(
            id=tenant.id,
            tenant_key=tenant.tenant_key,
            policy_version=tenant.policy_version,
            revision=tenant.revision + 1,
        )


class FakePolicyRepo:
    def __init__(self, policies: list[PolicyRecord] | None = None) -> None:
        self.policies = policies or []

    def list_current_policies(
        self, *, tenant_id: int, policy_set: str = "active"
    ) -> list[PolicyRecord]:
        return list(self.policies)


class FakeUserRepo:
    def get_user_context(self, user_id: int) -> dict[str, Any] | None:
        return (
            {"role": "admin", "roles": ["admin"], "permissions": ["write"]}
            if user_id == 7
            else None
        )


class FakeRelationshipRepo:
    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]:
        return [
            RelationshipRecord(
                subject_type=subject_type,
                subject_id=subject_id,
                relation="member_of",
                object_type="team",
                object_id="red",
            )
        ]

    def list_for_object(
        self, *, tenant_id: int, object_type: str, object_id: str
    ) -> list[RelationshipRecord]:
        return [
            RelationshipRecord(
                subject_type="user",
                subject_id="7",
                relation="viewer",
                object_type=object_type,
                object_id=object_id,
            )
        ]


class FakeAuditRepo:
    def __init__(self) -> None:
        self.calls = 0

    def write(self, **kwargs: Any) -> None:
        self.calls += 1


class FakeDecisionCache:
    def __init__(self, cached: CachedDecision | None = None) -> None:
        self.cached = cached
        self.set_calls = 0

    def get(self, key: str) -> CachedDecision | None:
        return self.cached

    def set(self, key: str, value: CachedDecision, ttl_seconds: int) -> None:
        self.set_calls += 1
        self.cached = value

    def make_key(
        self,
        *,
        tenant_key: str,
        policy_version: int,
        authorization_input: AuthorizationInput,
        revision: int | None = None,
    ) -> str:
        return f"{tenant_key}:{policy_version}:{authorization_input.action}:{revision}"

    def bump_namespace(self, tenant_key: str) -> int:
        return 1


class FakePolicyCache:
    def __init__(self, cached: list[PolicyRecord] | None = None) -> None:
        self.cached = cached
        self.set_calls = 0

    def get(self, tenant_key: str, policy_version: int) -> list[PolicyRecord] | None:
        return self.cached

    def set(self, tenant_key: str, policy_version: int, policies: list[PolicyRecord]) -> None:
        self.set_calls += 1
        self.cached = policies

    def invalidate(self, tenant_key: str) -> None:
        return None


class FakeRelationshipCache:
    def __init__(self, cached: list[RelationshipRecord] | None = None) -> None:
        self.cached = cached
        self.set_calls = 0

    def get(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord] | None:
        return self.cached

    def set(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        relationships: list[RelationshipRecord],
    ) -> None:
        self.set_calls += 1
        self.cached = relationships

    def invalidate(self, *, tenant_id: int, subject_type: str, subject_id: str) -> None:
        return None


class FakeACLRepo:
    def find_matching_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[ACLRecord]:
        return [
            ACLRecord(
                id=11,
                tenant_id=tenant_id,
                subject_type="user",
                subject_id="7",
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                effect="allow",
            )
        ]

    def create_acl_entry(self, **kwargs: Any) -> int:
        return 1

    def list_resource_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str
    ) -> list[ACLRecord]:
        return []

    def get_acl_entry(self, *, tenant_id: int, acl_id: int) -> ACLRecord | None:
        return None

    def delete_acl_entry(self, *, tenant_id: int, acl_id: int) -> None:
        return None


class FakeACLCache:
    def __init__(self) -> None:
        self.cached: list[ACLRecord] | None = None
        self.invalidated = False

    def get(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[ACLRecord] | None:
        return self.cached

    def set(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        acl_entries: list[ACLRecord],
    ) -> None:
        self.cached = acl_entries

    def invalidate(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None:
        self.invalidated = True


class FakeAccessIndexCache:
    def __init__(self, cached: list[AccessIndexEntry] | None = None) -> None:
        self.cached = cached
        self.set_payload: list[AccessIndexEntry] | None = None
        self.invalidated = False
        self.tenant_invalidated = False

    def get(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[AccessIndexEntry] | None:
        return self.cached

    def set(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        entries: list[AccessIndexEntry],
    ) -> None:
        self.cached = entries
        self.set_payload = entries

    def invalidate(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None:
        self.invalidated = True

    def invalidate_tenant(self, *, tenant_id: int) -> None:
        self.tenant_invalidated = True

    def invalidate_global(self) -> None:
        self.cached = None


class FakeAuthModelRepo:
    def get_model(self, *, tenant_id: int) -> AuthModelRecord | None:
        return AuthModelRecord(
            id=1,
            tenant_id=tenant_id,
            schema_text="model schema 1\ntype user\ntype document\nrelations\nowner: [user]\npermissions\nread = owner",
            schema_json={},
            compiled_json={},
        )


def build_service(
    *,
    settings: DummySettings | None = None,
    decision_cache: FakeDecisionCache | None = None,
    policy_cache: FakePolicyCache | None = None,
    relationship_cache: FakeRelationshipCache | None = None,
    auth_model_repo: FakeAuthModelRepo | None = None,
) -> AuthorizationService:
    return AuthorizationService(
        settings=settings or DummySettings(),
        tenants=FakeTenantRepo(),
        policies=FakePolicyRepo(
            [
                PolicyRecord(
                    id=1,
                    definition=SimpleNamespace(
                        action="read",
                        effect="allow",
                        priority=1,
                        conditions={},
                        policy_id="read:v1",
                    ),
                )
            ]
        ),
        users=FakeUserRepo(),
        relationships=FakeRelationshipRepo(),
        audit=FakeAuditRepo(),
        policy_cache=policy_cache or FakePolicyCache(),
        relationship_cache=relationship_cache or FakeRelationshipCache(),
        decision_cache=decision_cache or FakeDecisionCache(),
        acl_repository=FakeACLRepo(),
        acl_cache=FakeACLCache(),
        access_index_cache=FakeAccessIndexCache(),
        auth_model_repository=auth_model_repo,
    )


def _decision(*, allowed: bool, action: str = "read") -> AuthorizationDecision:
    return AuthorizationDecision(
        allowed=allowed,
        decision="allow" if allowed else "deny",
        reason="ok" if allowed else "no",
        policy_id=f"{action}:v1" if allowed else None,
        explain_trace=(
            ExplainTraceStep(step="final", outcome="allow" if allowed else "deny", detail="done"),
        ),
        matched_policies=((f"{action}:v1",) if allowed else ()),
        failed_conditions=(),
    )


def test_load_persistent_api_key_scopes_returns_record(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Repo:
        def __init__(self, db: object) -> None:
            self._db = db

        def get_by_hash(self, *, key_hash: str) -> SimpleNamespace:
            return SimpleNamespace(scopes={"role": "admin"}, revoked_at=None)

    class _Db:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "keynetra.config.security.create_session_factory", lambda _url: lambda: _Db()
    )
    monkeypatch.setattr("keynetra.config.security.SqlApiKeyRepository", _Repo)
    scopes = _load_persistent_api_key_scopes(DummySettings(), "hash")
    assert scopes == {"role": "admin"}


def test_get_jwks_covers_success_cache_and_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = DummySettings(oidc_jwks_url="https://issuer/jwks")
    payload = {"keys": [{"kid": "1"}]}
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: payload,
    )
    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: response)
    monkeypatch.setattr("keynetra.config.security.time.time", lambda: 10.0)

    first = _get_jwks(settings)
    second = _get_jwks(settings)
    assert first == payload
    assert second == payload

    monkeypatch.setattr(
        "httpx.get", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr("keynetra.config.security.time.time", lambda: 100.0)
    with pytest.raises(JWTError):
        _get_jwks(settings)
    with pytest.raises(JWTError):
        _get_jwks(settings)


def test_get_principal_supports_persistent_and_development_api_key_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "dev-key"
    key_hash = __import__("hashlib").sha256(key.encode("utf-8")).hexdigest()
    request = DummyRequest(headers={"X-API-Key": key})

    persistent_settings = DummySettings(
        _api_key_hashes={key_hash},
        _api_key_scopes={},
        development=False,
    )
    monkeypatch.setattr(
        "keynetra.config.security._load_persistent_api_key_scopes",
        lambda settings, key_hash: {"tenant": "acme", "role": "admin"},
    )
    principal = get_principal(
        request, settings=persistent_settings, authorization=None, x_api_key=key
    )
    assert principal["scopes"]["role"] == "admin"

    dev_settings = DummySettings(
        _api_key_hashes={key_hash}, _api_key_scopes={}, environment="development"
    )
    monkeypatch.setattr(
        "keynetra.config.security._load_persistent_api_key_scopes", lambda *args: None
    )
    principal = get_principal(request, settings=dev_settings, authorization=None, x_api_key=key)
    assert principal["scopes"]["tenant"] == "default"


def test_get_principal_uses_jwks_when_oidc_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "keynetra.config.security._get_jwks", lambda settings: {"keys": [{"kid": "1"}]}
    )
    monkeypatch.setattr(
        "keynetra.config.security._decode_with_jwks",
        lambda token, jwks, audience, issuer: {"sub": "svc-1"},
    )
    principal = get_principal(
        DummyRequest(path="/health"),
        settings=DummySettings(oidc_jwks_url="https://issuer/jwks"),
        authorization=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
        x_api_key=None,
    )
    assert principal["id"] == "svc-1"


def test_authorization_service_returns_cached_decision() -> None:
    cached = CachedDecision.from_decision(_decision(allowed=True))
    service = build_service(decision_cache=FakeDecisionCache(cached=cached))
    result = service.authorize(
        tenant_key="acme",
        principal={"type": "api_key", "id": "p1"},
        user={"id": 7},
        action="read",
        resource={"resource_type": "document", "resource_id": "doc-1"},
        context={},
    )
    assert result.cached is True
    assert result.decision.allowed is True


def test_authorization_service_builds_input_with_model_and_access_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(auth_model_repo=FakeAuthModelRepo())
    monkeypatch.setattr(
        "keynetra.services.authorization.compile_authorization_schema",
        lambda schema_text: {"compiled": schema_text},
        raising=False,
    )
    built = service._build_authorization_input(  # noqa: SLF001
        tenant_id=1,
        tenant_key="acme",
        user={"id": 7},
        action="read",
        resource={"resource_type": "document", "resource_id": "doc-1"},
        context={},
    )
    assert built.permission_graph is not None
    assert built.acl_entries
    assert built.access_index_entries


def test_authorization_service_hydrates_user_and_relationships() -> None:
    relationship_cache = FakeRelationshipCache(cached=None)
    service = build_service(relationship_cache=relationship_cache)
    hydrated = service._hydrate_user(
        tenant_id=1, user={"id": 7, "permissions": ["read"]}
    )  # noqa: SLF001
    assert hydrated["roles"] == ["admin"]
    assert hydrated["role_permissions"] == ["write"]
    assert hydrated["direct_permissions"] == ["read"]
    assert relationship_cache.set_calls == 1


def test_authorization_service_authorize_batch_memoizes_same_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service()
    decisions: list[str] = []

    class _Engine:
        def decide(self, authorization_input: AuthorizationInput) -> AuthorizationDecision:
            decisions.append(authorization_input.action)
            return _decision(allowed=True, action=authorization_input.action)

    monkeypatch.setattr(service, "_build_engine", lambda **kwargs: _Engine())
    results = service.authorize_batch(
        tenant_key="acme",
        principal={"type": "api_key", "id": "p1"},
        user={"id": 7},
        items=[
            {"action": "read", "resource": {"resource_type": "document", "resource_id": "doc-1"}},
            {"action": "read", "resource": {"resource_type": "document", "resource_id": "doc-1"}},
        ],
    )
    assert len(results) == 2
    assert decisions == ["read"]


def test_authorization_service_safe_cache_helpers_handle_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service()
    monkeypatch.setattr(
        "keynetra.services.authorization.with_timeout",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()),
    )
    assert service._safe_cache_get("k") is None  # noqa: SLF001
    assert service._safe_policy_cache_get("acme", 1) is None  # noqa: SLF001
    assert (
        service._safe_relationship_cache_get(tenant_id=1, subject_type="user", subject_id="7")
        is None
    )  # noqa: SLF001


def test_access_indexer_covers_cache_memo_relationships_and_invalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acl_cache = FakeACLCache()
    access_cache = FakeAccessIndexCache()
    indexer = AccessIndexer(
        acl_repository=FakeACLRepo(),
        acl_cache=acl_cache,
        access_index_cache=access_cache,
        relationships=FakeRelationshipRepo(),
    )
    entries = indexer.build_resource_index(
        tenant_id=1,
        resource_type="document",
        resource_id="doc-1",
        action="read",
    )
    assert entries[0].source == "acl"
    assert entries[1].source == "relationship"
    assert (
        relationship_descriptor(
            FakeRelationshipRepo().list_for_object(
                tenant_id=1, object_type="document", object_id="doc-1"
            )[0]
        )
        == "relationship:viewer:document:doc-1"
    )

    monkeypatch.setattr(indexer, "_schedule_background_refresh", lambda **kwargs: None)
    indexer._memo_set((1, "document", "doc-1", "read"), entries)  # noqa: SLF001
    assert indexer.build_resource_index(
        tenant_id=1, resource_type="document", resource_id="doc-1", action="read"
    )
    indexer.invalidate_resource(tenant_id=1, resource_type="document", resource_id="doc-1")
    indexer.invalidate_tenant(tenant_id=1)
    assert access_cache.invalidated is True
    assert access_cache.tenant_invalidated is True
    assert "relationship:viewer:document:doc-1" in indexer.subject_descriptors(
        {
            "id": 7,
            "roles": ["admin"],
            "permissions": ["read"],
            "relations": [{"relation": "viewer", "object_type": "document", "object_id": "doc-1"}],
        }
    )


@pytest.mark.anyio
async def test_access_routes_cover_invalid_policy_set_and_batch_flow() -> None:
    request = DummyRequest(headers={"X-Tenant-Id": "acme"})
    decision = _decision(allowed=True)
    result = AuthorizationResult(decision=decision, cached=False, revision=9)

    class _Service:
        async def authorize_async(self, **kwargs: Any) -> AuthorizationResult:
            return result

        async def authorize_batch_async(self, **kwargs: Any) -> list[AuthorizationResult]:
            return [result, result]

        def get_revision(self, *, tenant_key: str) -> int:
            return 9

    services = SimpleNamespace(
        authorization_service=_Service(),
        settings=SimpleNamespace(
            async_authorization_enabled=True, strict_tenancy=False, is_development=lambda: False
        ),
        tenant_repo=SimpleNamespace(get_by_key=lambda tenant_key: object()),
    )

    payload = AccessRequest(user={"id": "u1"}, action="read", resource={"id": "doc-1"})
    with pytest.raises(ApiError) as exc:
        await check_access(
            payload, request, service=None, services=services, principal={}, policy_set="bad"
        )
    assert exc.value.code == ApiErrorCode.VALIDATION_ERROR

    batch = await check_access_batch(
        BatchAccessRequest(
            user={"id": "u1"},
            items=[{"action": "read", "resource": {}}, {"action": "read", "resource": {}}],
        ),
        request,
        service=None,
        services=services,
        principal={},
        policy_set="active",
    )
    assert len(batch["data"]["results"]) == 2

    simulated = await simulate(payload, request, service=None, services=services, principal={})
    assert simulated["data"]["decision"] == "allow"


@pytest.mark.anyio
async def test_access_route_maps_tenant_not_found_to_api_error() -> None:
    request = DummyRequest(headers={"X-Tenant-Id": "acme"})

    class _Service:
        def authorize(self, **kwargs: Any) -> AuthorizationResult:
            raise TenantNotFoundError("acme")

    services = SimpleNamespace(
        authorization_service=_Service(),
        settings=SimpleNamespace(
            async_authorization_enabled=False, strict_tenancy=False, is_development=lambda: False
        ),
        tenant_repo=SimpleNamespace(get_by_key=lambda tenant_key: object()),
    )

    with pytest.raises(ApiError) as exc:
        await check_access(
            AccessRequest(user={}, action="read", resource={}),
            request,
            service=None,
            services=services,
            principal={},
            policy_set="active",
        )
    assert exc.value.code == ApiErrorCode.NOT_FOUND


@pytest.mark.anyio
async def test_access_batch_route_maps_tenant_not_found_to_api_error() -> None:
    request = DummyRequest(headers={"X-Tenant-Id": "acme"})

    class _Service:
        async def authorize_batch_async(self, **kwargs: Any) -> list[AuthorizationResult]:
            raise TenantNotFoundError("acme")

    services = SimpleNamespace(
        authorization_service=_Service(),
        settings=SimpleNamespace(
            async_authorization_enabled=True, strict_tenancy=False, is_development=lambda: False
        ),
        tenant_repo=SimpleNamespace(get_by_key=lambda tenant_key: object()),
    )

    with pytest.raises(ApiError) as exc:
        await check_access_batch(
            BatchAccessRequest(user={}, items=[{"action": "read", "resource": {}}]),
            request,
            service=None,
            services=services,
            principal={},
            policy_set="active",
        )
    assert exc.value.code == ApiErrorCode.NOT_FOUND


def test_run_startup_and_bootstrap_helpers_cover_success_and_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    settings = DummySettings(auto_seed_sample_data=True, service_mode="policy-store")
    monkeypatch.setattr("keynetra.api.main.initialize_database", lambda url: calls.append("init"))
    monkeypatch.setattr("keynetra.api.main.run_migrations", lambda url: calls.append("migrate"))
    monkeypatch.setattr(
        "keynetra.api.main._ensure_bootstrap_tenant", lambda settings: calls.append("tenant")
    )
    monkeypatch.setattr(
        "keynetra.api.main._bootstrap_file_backed_policies",
        lambda settings: calls.append("policies"),
    )
    monkeypatch.setattr(
        "keynetra.api.main._bootstrap_file_backed_model", lambda settings: calls.append("model")
    )
    monkeypatch.setattr(
        "keynetra.api.main.create_session_factory",
        lambda url: lambda: SimpleNamespace(close=lambda: calls.append("close")),
    )
    monkeypatch.setattr("keynetra.api.main.seed_demo_data", lambda db: calls.append("seed"))
    _run_startup(settings)
    assert {"init", "tenant", "policies", "model", "seed", "close"} <= set(calls)

    monkeypatch.setattr(
        "keynetra.api.main.initialize_database",
        lambda url: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(BootstrapError):
        _run_startup(settings)


def test_bootstrap_tenant_model_subscriber_and_stop_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[str] = []
    monkeypatch.setattr(
        "keynetra.api.main.create_session_factory",
        lambda url: lambda: SimpleNamespace(close=lambda: None),
    )
    monkeypatch.setattr(
        "keynetra.api.main.SqlTenantRepository",
        lambda db: SimpleNamespace(
            get_by_key=lambda tenant_key: None, create=lambda tenant_key: created.append(tenant_key)
        ),
    )
    _ensure_bootstrap_tenant(DummySettings(environment="development"))
    assert created == ["default"]

    monkeypatch.setattr(
        "keynetra.config.file_loaders.load_authorization_model_from_paths",
        lambda paths: (_ for _ in ()).throw(ValueError("bad")),
    )
    with pytest.raises(BootstrapError):
        _bootstrap_file_backed_model(
            SimpleNamespace(parsed_model_paths=lambda: ["model"], environment="production")
        )

    class _PubSub:
        def subscribe(self, channel: str) -> None:
            return None

        def listen(self):
            yield {"type": "message", "data": json.dumps({"tenant_key": "acme"})}

        def close(self) -> None:
            raise RuntimeError("close failed")

    class _Redis:
        def pubsub(self) -> _PubSub:
            return _PubSub()

    cache = SimpleNamespace(invalidate=lambda tenant_key: created.append(tenant_key))
    monkeypatch.setattr("keynetra.api.main.build_policy_cache", lambda redis: cache)
    monkeypatch.setattr("keynetra.api.main.get_redis", lambda: _Redis())
    app = FastAPI()
    _start_policy_subscriber(app, settings=DummySettings())
    app.state.policy_subscriber.join(timeout=1)
    _stop_policy_subscriber(app)
    assert "acme" in created
