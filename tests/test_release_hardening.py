from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from keynetra.api.errors import ApiError
from keynetra.api.routes.access import (
    AccessRequest,
    BatchAccessRequest,
    check_access,
    check_access_batch,
)
from keynetra.api.routes.access import simulate as access_simulate
from keynetra.api.routes.dev import _require_local_dev, get_sample_data, seed_sample_data
from keynetra.api.routes.simulation import (
    ImpactAnalysisRequest,
    PolicySimulationRequest,
    _normalize_request,
    impact_analysis,
    simulate_policy,
)
from keynetra.cli import app
from keynetra.config.admin_auth import AdminAccess, _resolve_tenant_role, require_management_role
from keynetra.config.security import _matches_api_key, get_principal
from keynetra.config.settings import Settings, reset_settings_cache
from keynetra.domain.models.base import Base
from keynetra.domain.models.rbac import Permission, Role
from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.infrastructure.cache.backends import (
    InMemoryCacheBackend,
    RedisCacheBackend,
    build_cache_backend,
)
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app
from keynetra.services import resilience
from keynetra.services.interfaces import (
    PolicyListItem,
    PolicyMutationResult,
    PolicyRecord,
    RelationshipRecord,
    TenantRecord,
)
from keynetra.services.policies import PolicyService
from keynetra.services.relationships import RelationshipService


class DummyRequest:
    def __init__(self) -> None:
        self.state = SimpleNamespace(request_id="req-1")
        self.url = SimpleNamespace(path="/check-access")
        self.method = "POST"
        self.client = SimpleNamespace(host="127.0.0.1")


class FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str) -> None:
        self.store[key] = value

    def setex(self, key: str, ttl: int, value: str) -> None:  # noqa: ARG002
        self.store[key] = value

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def incr(self, key: str) -> int:
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])


def test_in_memory_cache_backend_supports_ttl_delete_and_incr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = InMemoryCacheBackend()
    monkeypatch.setattr("keynetra.infrastructure.cache.backends.time.time", lambda: 100.0)

    backend.set("foo", "bar", ttl_seconds=1)
    assert backend.get("foo") == "bar"
    assert backend.incr("counter") == 1
    assert backend.incr("counter") == 2
    backend.delete("foo")
    assert backend.get("foo") is None

    monkeypatch.setattr("keynetra.infrastructure.cache.backends.time.time", lambda: 102.0)
    backend.set("short", "value", ttl_seconds=1)
    monkeypatch.setattr("keynetra.infrastructure.cache.backends.time.time", lambda: 104.0)
    assert backend.get("short") is None


def test_redis_cache_backend_survives_client_errors() -> None:
    class ExplodingClient:
        def get(self, key: str) -> None:  # noqa: ARG002
            raise RuntimeError("boom")

        def set(self, key: str, value: str) -> None:  # noqa: ARG002
            raise RuntimeError("boom")

        def setex(self, key: str, ttl: int, value: str) -> None:  # noqa: ARG002
            raise RuntimeError("boom")

        def delete(self, key: str) -> None:  # noqa: ARG002
            raise RuntimeError("boom")

        def incr(self, key: str) -> None:  # noqa: ARG002
            raise RuntimeError("boom")

    backend = RedisCacheBackend(ExplodingClient())
    assert backend.get("foo") is None
    backend.set("foo", "bar", ttl_seconds=10)
    backend.delete("foo")
    assert backend.incr("counter") == 0


def test_build_cache_backend_uses_shared_memory_fallback() -> None:
    backend = build_cache_backend(None)
    assert isinstance(backend, InMemoryCacheBackend)
    assert build_cache_backend(FakeRedisClient()).__class__ is RedisCacheBackend


def test_matches_api_key_uses_constant_time_hash_comparison() -> None:
    secret = "super-secret"
    hashes = {hashlib.sha256(secret.encode("utf-8")).hexdigest()}
    assert _matches_api_key(secret, hashes) is True
    assert _matches_api_key("wrong", hashes) is False


def test_get_principal_supports_api_key_and_bearer_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = DummyRequest()
    monkeypatch.setattr("keynetra.config.security._matches_api_key", lambda *_: True)
    api_key_settings = Settings(
        api_key_scopes_json='{"test-key":{"tenant":"default","role":"developer","permissions":["*"]}}'
    )

    api_key_principal = get_principal(
        request,
        settings=api_key_settings,
        authorization=None,
        x_api_key="test-key",
    )
    assert api_key_principal["type"] == "api_key"
    assert len(api_key_principal["id"]) == 12

    token = jwt.encode(
        {"sub": "alice", "role": "admin"},
        "jwt-secret",
        algorithm="HS256",
    )
    jwt_principal = get_principal(
        request,
        settings=Settings(jwt_secret="jwt-secret", jwt_algorithm="HS256"),
        authorization=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        x_api_key=None,
    )
    assert jwt_principal["type"] == "jwt"
    assert jwt_principal["id"] == "alice"
    assert jwt_principal["claims"]["role"] == "admin"


def test_get_principal_rejects_invalid_and_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = DummyRequest()
    monkeypatch.setenv("KEYNETRA_API_KEYS", "test-key")
    settings = Settings()

    with pytest.raises(HTTPException):
        get_principal(
            request,
            settings=settings,
            authorization=None,
            x_api_key="wrong",
        )

    with pytest.raises(HTTPException):
        get_principal(request, settings=settings, authorization=None, x_api_key=None)


def test_get_principal_rejects_invalid_jwt() -> None:
    request = DummyRequest()
    token = jwt.encode({"sub": "alice"}, "wrong-secret", algorithm="HS256")
    with pytest.raises(HTTPException):
        get_principal(
            request,
            settings=Settings(jwt_secret="jwt-secret", jwt_algorithm="HS256"),
            authorization=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            x_api_key=None,
        )


def test_resolve_tenant_role_covers_list_and_dict_claims() -> None:
    assert _resolve_tenant_role({"type": "api_key"}) is None
    assert _resolve_tenant_role({"type": "api_key", "scopes": {"role": "admin"}}) == "admin"
    assert _resolve_tenant_role({"claims": {"tenant_roles": {"acme": "developer"}}}) == "developer"
    assert _resolve_tenant_role({"claims": {"tenant_roles": [{"role": "viewer"}]}}) == "viewer"
    assert _resolve_tenant_role({"claims": {"roles": ["developer", "viewer"]}}) == "developer"


def test_require_management_role_resolves_and_enforces_roles() -> None:
    request = DummyRequest()
    dependency = require_management_role("developer")

    access = dependency(
        request,
        principal={"type": "api_key", "id": "test", "scopes": {"role": "admin"}},
    )
    assert access.role == "admin"
    assert request.state.admin_role == "admin"

    denied = require_management_role("admin")
    with pytest.raises(ApiError):
        denied(request, principal={"type": "jwt", "claims": {"role": "viewer"}})

    with pytest.raises(ValueError):
        require_management_role("owner")


def test_resilience_helpers_cover_timeout_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resilience.time, "sleep", lambda *_: None)

    class FakeFuture:
        def result(self, timeout: float):  # noqa: ARG002
            raise TimeoutError

        def cancel(self) -> None:
            return None

    monkeypatch.setattr(resilience._EXECUTOR, "submit", lambda func: FakeFuture())

    with pytest.raises(TimeoutError):
        resilience.with_timeout(lambda: "ok", timeout_seconds=0.0)

    attempts: list[int] = []

    def flaky() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("try again")
        return "ok"

    assert resilience.retry(flaky, attempts=3, base_delay_seconds=0.0) == "ok"
    assert len(attempts) == 3

    with pytest.raises(RuntimeError):
        resilience.retry(lambda: (_ for _ in ()).throw(RuntimeError("fail")), attempts=1)


def test_cli_surface_commands_cover_release_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout

    recorded: dict[str, object] = {}

    def fake_run(app_path: str, *, host: str, port: int, reload: bool) -> None:
        recorded["app_path"] = app_path
        recorded["host"] = host
        recorded["port"] = port
        recorded["reload"] = reload

    monkeypatch.setattr("uvicorn.run", fake_run)
    result = runner.invoke(app, ["start", "--host", "127.0.0.1", "--port", "9001", "--reload"])
    assert result.exit_code == 0
    assert recorded == {
        "app_path": "keynetra.api.main:app",
        "host": "127.0.0.1",
        "port": 9001,
        "reload": True,
    }

    posted: list[tuple[str, dict[str, object], dict[str, str]]] = []
    got: list[tuple[str, dict[str, str]]] = []

    class FakeResponse:
        def __init__(self, text: str = "ok") -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, *, json: dict[str, object], headers: dict[str, str], timeout: float):
        posted.append((url, json, headers))
        return FakeResponse(text='{"ok": true}')

    def fake_get(url: str, *, headers: dict[str, str], timeout: float):
        got.append((url, headers))
        return FakeResponse(text='{"status": "ok"}')

    monkeypatch.setattr("keynetra.cli.httpx.post", fake_post)
    monkeypatch.setattr("keynetra.cli.httpx.get", fake_get)

    result = runner.invoke(
        app,
        [
            "check",
            "--api-key",
            "testkey",
            "--action",
            "read",
            "--user",
            '{"id": 1}',
            "--resource",
            '{"id": "doc-1"}',
            "--context",
            '{"scope": "demo"}',
        ],
    )
    assert result.exit_code == 0
    assert posted[-1][0] == "http://localhost:8000/check-access"
    assert posted[-1][2] == {"X-API-Key": "testkey"}

    result = runner.invoke(
        app,
        [
            "simulate",
            "--api-key",
            "testkey",
            "--action",
            "read",
            "--policy-change",
            "allow read",
        ],
    )
    assert result.exit_code == 0
    assert posted[-1][0] == "http://localhost:8000/simulate-policy"

    result = runner.invoke(
        app,
        [
            "impact",
            "--api-key",
            "testkey",
            "--policy-change",
            "allow read",
        ],
    )
    assert result.exit_code == 0
    assert posted[-1][0] == "http://localhost:8000/impact-analysis"

    schema_file = tmp_path / "schema.dsl"
    schema_file.write_text("model schema 1", encoding="utf-8")
    result = runner.invoke(app, ["model", "apply", str(schema_file), "--api-key", "testkey"])
    assert result.exit_code == 0
    assert posted[-1][0] == "http://localhost:8000/auth-model"

    result = runner.invoke(app, ["model", "show", "--api-key", "testkey"])
    assert result.exit_code == 0
    assert got[-1][0] == "http://localhost:8000/auth-model"


def test_cli_migrate_invokes_alembic_upgrade(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migrate.db'}"
    monkeypatch.setenv("KEYNETRA_DATABASE_URL", database_url)
    reset_settings_cache()

    called: dict[str, object] = {}

    def fake_upgrade(config, revision: str) -> None:  # noqa: ANN001
        called["revision"] = revision
        called["url"] = config.get_main_option("sqlalchemy.url")

    monkeypatch.setattr("alembic.command.upgrade", fake_upgrade)
    monkeypatch.setattr("keynetra.cli.find_destructive_revisions", lambda *args, **kwargs: [])

    runner = CliRunner()
    result = runner.invoke(app, ["migrate", "--confirm-destructive"])

    assert result.exit_code == 0
    assert called["revision"] == "head"
    assert called["url"] == database_url


def test_access_route_helpers_cover_transport_paths() -> None:
    class FakeAccessService:
        def authorize(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(
                decision=SimpleNamespace(
                    allowed=True,
                    decision="allow",
                    matched_policies=["p1"],
                    reason="granted",
                    policy_id="p1",
                    explain_trace=[SimpleNamespace(to_dict=lambda: {"step": "done"})],
                ),
                revision=9,
                cached=False,
            )

        def simulate(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(
                decision="deny",
                matched_policies=[],
                reason="missing",
                policy_id=None,
                explain_trace=[SimpleNamespace(to_dict=lambda: {"step": "deny"})],
                failed_conditions=["role"],
            )

        def authorize_batch(self, **_: object) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    decision=SimpleNamespace(allowed=True),
                    revision=1,
                ),
                SimpleNamespace(
                    decision=SimpleNamespace(allowed=False),
                    revision=2,
                ),
            ]

        def get_revision(self, *, tenant_key: str) -> int:  # noqa: ARG002
            return 9

    request = DummyRequest()
    service = FakeAccessService()
    services = SimpleNamespace(settings=SimpleNamespace(async_authorization_enabled=False))

    check = asyncio.run(
        check_access(
            payload=AccessRequest(
                user={"id": 1}, action="read", resource={}, context={}, consistency="eventual"
            ),
            request=request,
            service=service,
            services=services,
            principal={"type": "api_key"},
        )
    )
    assert check["data"]["decision"] == "allow"
    assert check["data"]["revision"] == 9

    simulated = asyncio.run(
        access_simulate(
            payload=AccessRequest(
                user={"id": 1}, action="read", resource={}, context={}, consistency="eventual"
            ),
            request=request,
            service=service,
            services=services,
            principal={"type": "api_key"},
        )
    )
    assert simulated["data"]["decision"] == "deny"

    batch = asyncio.run(
        check_access_batch(
            payload=BatchAccessRequest(
                user={"id": 1},
                items=[{"action": "read"}, {"action": "write"}],
                consistency="eventual",
            ),
            request=request,
            service=service,
            services=services,
            principal={"type": "api_key"},
        )
    )
    assert batch["data"]["results"] == [
        {"action": "read", "allowed": True, "revision": 1},
        {"action": "write", "allowed": False, "revision": 2},
    ]


def test_simulation_and_dev_routes_cover_local_and_normalization_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSimulator:
        def simulate_policy_change(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(
                decision_before=SimpleNamespace(
                    allowed=False, decision="deny", reason="before", policy_id="p0"
                ),
                decision_after=SimpleNamespace(
                    allowed=True, decision="allow", reason="after", policy_id="p1"
                ),
            )

    class FakeImpact:
        def analyze_policy_change(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(gained_access=[1, 2], lost_access=[3])

    monkeypatch.setattr(
        "keynetra.api.routes.dev.sample_bootstrap_document",
        lambda: {"sample": True},
    )
    monkeypatch.setattr(
        "keynetra.api.routes.dev.seed_demo_data",
        lambda db, reset=False: SimpleNamespace(
            tenant_key="default",
            created_tenant=True,
            created_user=True,
            created_role=False,
            created_permissions=1,
            created_relationships=2,
            created_policies=3,
        ),
    )

    _require_local_dev(Settings(environment="development"))
    with pytest.raises(ApiError):
        _require_local_dev(
            Settings(
                environment="production",
                api_keys="prod-key",
                api_key_scopes_json='{"prod-key":{"tenant":"default","role":"viewer","permissions":["*"]}}',
                jwt_secret="strong-prod-secret",
            )
        )

    request = DummyRequest()
    sample = get_sample_data(request=request, settings=Settings(environment="development"))
    assert sample["data"] == {"sample": True}

    seeded = seed_sample_data(
        request=request,
        services=SimpleNamespace(db=object()),
        settings=Settings(environment="development"),
        reset=True,
    )
    assert seeded["data"]["created_permissions"] == 1

    normalized = _normalize_request(
        {"user": "alice", "resource": "document:42", "action": 123, "context": "bad"}
    )
    assert normalized == {
        "user": {"id": "alice"},
        "resource": {"resource_type": "document", "resource_id": "42"},
        "action": "",
        "context": {},
    }

    simulation = simulate_policy(
        payload=PolicySimulationRequest(
            simulate={"policy_change": "allow read"},
            request=normalized,
        ),
        request=request,
        services=SimpleNamespace(policy_simulator=FakeSimulator(), impact_analyzer=FakeImpact()),
        access=AdminAccess(tenant_key="default", role="viewer", principal={"type": "api_key"}),
    )
    assert simulation["data"]["decision_before"]["decision"] == "deny"
    assert simulation["data"]["decision_after"]["decision"] == "allow"

    impact = impact_analysis(
        payload=ImpactAnalysisRequest(policy_change="allow read"),
        request=request,
        services=SimpleNamespace(policy_simulator=FakeSimulator(), impact_analyzer=FakeImpact()),
        access=AdminAccess(tenant_key="default", role="viewer", principal={"type": "api_key"}),
    )
    assert impact["data"]["gained_access"] == [1, 2]
    assert impact["data"]["lost_access"] == [3]


def test_policy_service_release_paths() -> None:
    class FakeTenantRepo:
        def __init__(self) -> None:
            self.tenant = TenantRecord(id=1, tenant_key="default", policy_version=1, revision=1)

        def get_or_create(self, tenant_key: str) -> TenantRecord:
            return self.tenant

        def get_by_id(self, tenant_id: int) -> TenantRecord | None:  # noqa: ARG002
            return self.tenant

        def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
            self.tenant = TenantRecord(
                id=tenant.id,
                tenant_key=tenant.tenant_key,
                policy_version=tenant.policy_version + 1,
                revision=tenant.revision + 1,
            )
            return self.tenant

        def bump_revision(self, tenant: TenantRecord) -> TenantRecord:
            self.tenant = TenantRecord(
                id=tenant.id,
                tenant_key=tenant.tenant_key,
                policy_version=tenant.policy_version,
                revision=tenant.revision + 1,
            )
            return self.tenant

    class FakePolicyRepo:
        def __init__(self) -> None:
            self.policy = PolicyRecord(
                id=1,
                definition=PolicyDefinition(
                    action="read",
                    effect="allow",
                    priority=10,
                    policy_id="p1",
                    conditions={"role": "admin"},
                ),
            )
            self.deleted: list[str] = []

        def list_current_policies(self, *, tenant_id: int) -> list[PolicyRecord]:  # noqa: ARG002
            return [self.policy]

        def list_current_policy_views(
            self, *, tenant_id: int
        ) -> list[PolicyListItem]:  # noqa: ARG002
            return [PolicyListItem(id=1, action="read", effect="allow", priority=10, conditions={})]

        def list_current_policy_page(
            self,
            *,
            tenant_id: int,
            limit: int,
            cursor: dict[str, object] | None,
        ) -> tuple[list[PolicyListItem], str | None]:  # noqa: ARG002
            return (
                [PolicyListItem(id=1, action="read", effect="allow", priority=10, conditions={})],
                "cursor-1",
            )

        def create_policy_version(
            self,
            *,
            tenant_id: int,
            policy_key: str,
            action: str,
            effect: str,
            priority: int,
            conditions: dict[str, object],
            created_by: str | None,
        ) -> PolicyMutationResult:  # noqa: ARG002
            return PolicyMutationResult(
                id=2, action=action, effect=effect, priority=priority, conditions=conditions
            )

        def rollback_policy(
            self, *, tenant_id: int, policy_key: str, version: int
        ) -> tuple[str, int]:  # noqa: ARG002
            return policy_key, version

        def delete_policy(self, *, tenant_id: int, policy_key: str) -> None:  # noqa: ARG002
            self.deleted.append(policy_key)

    class FakePolicyCache:
        def __init__(self) -> None:
            self.invalidated: list[str] = []

        def invalidate(self, tenant_key: str) -> None:
            self.invalidated.append(tenant_key)

    class FakeDecisionCache:
        def __init__(self) -> None:
            self.namespaces: list[str] = []

        def bump_namespace(self, tenant_key: str) -> int:
            self.namespaces.append(tenant_key)
            return len(self.namespaces)

    class FakePublisher:
        def __init__(self) -> None:
            self.events: list[tuple[str, int]] = []

        def publish_policy_update(self, *, tenant_key: str, policy_version: int) -> None:
            self.events.append((tenant_key, policy_version))

    tenants = FakeTenantRepo()
    policies = FakePolicyRepo()
    policy_cache = FakePolicyCache()
    decision_cache = FakeDecisionCache()
    publisher = FakePublisher()
    service = PolicyService(
        tenants=tenants,
        policies=policies,
        policy_cache=policy_cache,
        decision_cache=decision_cache,
        publisher=publisher,
    )

    assert service.list_policies(tenant_key="default") == [
        {"id": 1, "action": "read", "effect": "allow", "priority": 10, "conditions": {}}
    ]

    page, cursor = service.list_policies_page(tenant_key="default", limit=10, cursor=None)
    assert page[0]["action"] == "read"
    assert cursor == "cursor-1"

    created = service.create_policy(
        tenant_key="default",
        policy_key="p2",
        action="write",
        effect="allow",
        priority=20,
        conditions={"role": "writer"},
        created_by="tester",
    )
    assert created.action == "write"
    assert policy_cache.invalidated[-1] == "default"
    assert decision_cache.namespaces[-1] == "default"
    assert publisher.events[-1] == ("default", 2)

    rolled_back = service.rollback_policy(tenant_key="default", policy_key="p1", version=3)
    assert rolled_back == ("p1", 3)

    service.delete_policy(tenant_key="default", policy_key="p1")
    assert policies.deleted == ["p1"]


def test_relationship_service_release_paths() -> None:
    class FakeTenantRepo:
        def __init__(self) -> None:
            self.tenant = TenantRecord(id=1, tenant_key="default", policy_version=1, revision=1)

        def get_or_create(self, tenant_key: str) -> TenantRecord:
            return self.tenant

        def get_by_id(self, tenant_id: int) -> TenantRecord | None:  # noqa: ARG002
            return self.tenant

        def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
            self.tenant = TenantRecord(
                id=tenant.id,
                tenant_key=tenant.tenant_key,
                policy_version=tenant.policy_version + 1,
                revision=tenant.revision + 1,
            )
            return self.tenant

        def bump_revision(self, tenant: TenantRecord) -> TenantRecord:
            self.tenant = TenantRecord(
                id=tenant.id,
                tenant_key=tenant.tenant_key,
                policy_version=tenant.policy_version,
                revision=tenant.revision + 1,
            )
            return self.tenant

    class FakeRelationshipRepo:
        def __init__(self) -> None:
            self.calls = 0

        def list_for_subject(
            self, *, tenant_id: int, subject_type: str, subject_id: str
        ) -> list[RelationshipRecord]:  # noqa: ARG002
            self.calls += 1
            return [
                RelationshipRecord(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    relation="member_of",
                    object_type="team",
                    object_id="red",
                )
            ]

        def list_for_subject_page(
            self,
            *,
            tenant_id: int,
            subject_type: str,
            subject_id: str,
            limit: int,
            cursor: dict[str, object] | None,
        ) -> tuple[list[RelationshipRecord], str | None]:  # noqa: ARG002
            return (
                [
                    RelationshipRecord(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        relation="member_of",
                        object_type="team",
                        object_id="red",
                    )
                ],
                "next",
            )

        def create(
            self,
            *,
            tenant_id: int,
            subject_type: str,
            subject_id: str,
            relation: str,
            object_type: str,
            object_id: str,
        ) -> int:  # noqa: ARG002
            return 99

    class FakeRelationshipCache:
        def __init__(self) -> None:
            self.data: dict[tuple[int, str, str], list[RelationshipRecord]] = {}

        def get(
            self, *, tenant_id: int, subject_type: str, subject_id: str
        ) -> list[RelationshipRecord] | None:
            return self.data.get((tenant_id, subject_type, subject_id))

        def set(
            self,
            *,
            tenant_id: int,
            subject_type: str,
            subject_id: str,
            relationships: list[RelationshipRecord],
        ) -> None:
            self.data[(tenant_id, subject_type, subject_id)] = relationships

        def invalidate(self, *, tenant_id: int, subject_type: str, subject_id: str) -> None:
            self.data.pop((tenant_id, subject_type, subject_id), None)

    class FakeDecisionCache:
        def __init__(self) -> None:
            self.namespaces: list[str] = []

        def bump_namespace(self, tenant_key: str) -> int:
            self.namespaces.append(tenant_key)
            return len(self.namespaces)

    class FakeAccessIndexCache:
        def __init__(self) -> None:
            self.invalidated: list[int] = []

        def invalidate_tenant(self, tenant_id: int) -> None:
            self.invalidated.append(tenant_id)

    tenants = FakeTenantRepo()
    relationships = FakeRelationshipRepo()
    relationship_cache = FakeRelationshipCache()
    decision_cache = FakeDecisionCache()
    access_index_cache = FakeAccessIndexCache()
    service = RelationshipService(
        tenants=tenants,
        relationships=relationships,
        relationship_cache=relationship_cache,
        decision_cache=decision_cache,
        access_index_cache=access_index_cache,
    )

    first = service.list_relationships(tenant_key="default", subject_type="user", subject_id="7")
    second = service.list_relationships(tenant_key="default", subject_type="user", subject_id="7")
    assert first == second
    assert relationships.calls == 1

    page, cursor = service.list_relationships_page(
        tenant_key="default",
        subject_type="user",
        subject_id="7",
        limit=5,
        cursor=None,
    )
    assert page[0]["relation"] == "member_of"
    assert cursor == "next"

    created = service.create_relationship(
        tenant_key="default",
        subject_type="user",
        subject_id="7",
        relation="member_of",
        object_type="team",
        object_id="blue",
    )
    assert created == 99
    assert decision_cache.namespaces[-1] == "default"
    assert access_index_cache.invalidated == [1]


def test_management_routes_cover_permissions_roles_and_acl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'management.db'}"
    monkeypatch.setenv("KEYNETRA_DATABASE_URL", database_url)
    monkeypatch.setenv("KEYNETRA_API_KEYS", "testkey")
    monkeypatch.setenv(
        "KEYNETRA_API_KEY_SCOPES_JSON",
        '{"testkey":{"tenant":"default","role":"admin","permissions":["*"]}}',
    )
    monkeypatch.setenv("KEYNETRA_RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("KEYNETRA_RATE_LIMIT_BURST", "1000")
    reset_settings_cache()
    initialize_database(database_url)
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        role = Role(name="seed-role")
        permission = Permission(action="seed-action")
        role.permissions.append(permission)
        session.add_all([role, permission])
        session.commit()
        permission_id = permission.id

    client = TestClient(create_app())
    headers = {"X-API-Key": "testkey"}

    listed_permissions = client.get("/permissions", headers=headers)
    assert listed_permissions.status_code == 200

    created_permission = client.post(
        "/permissions",
        json={"action": "export_data"},
        headers=headers,
    )
    assert created_permission.status_code == 201
    created_permission_id = created_permission.json()["id"]

    updated_permission = client.put(
        f"/permissions/{created_permission_id}",
        json={"action": "export_data_v2"},
        headers=headers,
    )
    assert updated_permission.status_code == 200

    permission_roles = client.get(
        f"/permissions/{permission_id}/roles",
        headers=headers,
    )
    assert permission_roles.status_code == 200

    created_role = client.post(
        "/roles",
        json={"name": "auditor"},
        headers=headers,
    )
    assert created_role.status_code == 201
    created_role_id = created_role.json()["id"]

    updated_role = client.put(
        f"/roles/{created_role_id}",
        json={"name": "auditor-v2"},
        headers=headers,
    )
    assert updated_role.status_code == 200

    add_permission = client.post(
        f"/roles/{created_role_id}/permissions/{created_permission_id}",
        headers=headers,
    )
    assert add_permission.status_code == 201

    role_permissions = client.get(
        f"/roles/{created_role_id}/permissions",
        headers=headers,
    )
    assert role_permissions.status_code == 200

    remove_permission = client.delete(
        f"/roles/{created_role_id}/permissions/{created_permission_id}",
        headers=headers,
    )
    assert remove_permission.status_code == 200

    delete_role = client.delete(f"/roles/{created_role_id}", headers=headers)
    assert delete_role.status_code == 200

    created_acl = client.post(
        "/acl",
        json={
            "subject_type": "user",
            "subject_id": "u1",
            "resource_type": "document",
            "resource_id": "doc-1",
            "action": "read",
            "effect": "allow",
        },
        headers=headers,
    )
    assert created_acl.status_code == 201
    acl_id = created_acl.json()["data"]["id"]

    listed_acl = client.get("/acl/document/doc-1", headers=headers)
    assert listed_acl.status_code == 200

    deleted_acl = client.delete(f"/acl/{acl_id}", headers=headers)
    assert deleted_acl.status_code == 200
