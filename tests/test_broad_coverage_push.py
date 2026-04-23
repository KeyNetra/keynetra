from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typer import BadParameter, Exit

from keynetra.api.errors import ApiError
from keynetra.api.openapi import (
    _apply_route_metadata,
    _document_non_json_exceptions,
    _ensure_common_error_responses,
    _ensure_parameter_ref,
    _ensure_response_examples,
    _extract_nullable_variant,
    _normalize_for_sdk_codegen,
    build_openapi_schema,
)
from keynetra.api.routes import admin_tools
from keynetra.cli import (
    _coerce_scalar,
    _effective_config_path,
    _percentile,
    _resolve_url,
    benchmark,
    check_openapi,
    compile_policies,
    config_doctor,
    doctor,
    generate_openapi,
    migrate,
)
from keynetra.config.settings import Settings, reset_settings_cache
from keynetra.domain.models.auth_model import AuthorizationModel
from keynetra.domain.models.base import Base
from keynetra.domain.models.rbac import Permission, Role, User
from keynetra.domain.models.relationship import Relationship
from keynetra.domain.models.tenant import Tenant
from keynetra.engine.keynetra_engine import (
    AuthorizationInput,
    ConditionEvaluator,
    ExplainTraceStep,
    KeyNetraEngine,
    PolicyDefinition,
)
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app
from keynetra.modeling.model_validator import validate_authorization_schema
from keynetra.modeling.schema_parser import (
    AuthorizationSchema,
    IdentifierExpr,
    parse_authorization_schema,
)


def _db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_settings_cover_validators_and_parsing() -> None:
    with pytest.raises(ValueError):
        Settings(environment="qa", api_keys="key")
    with pytest.raises(ValueError):
        Settings(environment="prod", database_url="sqlite+pysqlite:///./db.sqlite", api_keys="key")
    with pytest.raises(ValueError):
        Settings(environment="prod", api_keys="key")
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", service_timeout_seconds=0.01)
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", critical_retry_attempts=0)
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", rate_limit_per_minute=0)
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", rate_limit_window_seconds=0)
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", rate_limit_burst=0)
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", resilience_executor_workers=0)
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", rate_limit_redis_unavailable_mode="bad")
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", jwks_cache_ttl_seconds=1)
    with pytest.raises(ValueError):
        Settings(environment="development", api_keys="key", jwks_backoff_max_seconds=0)

    settings = Settings(
        environment="development",
        api_keys="alpha,beta",
        api_key_scopes_json=json.dumps(
            {
                "alpha": {"tenant": "acme", "role": "admin", "permissions": ["read"]},
                "beta": {"tenant": "acme", "permissions": []},
            }
        ),
        policy_paths="a.yaml,b.yaml",
        model_paths="model.yaml",
        cors_allow_origins="http://a,http://b",
        cors_allow_methods="GET,POST",
        cors_allow_headers="X-Test,Content-Type",
    )

    assert len(settings.parsed_api_key_hashes()) == 2
    assert len(settings.parsed_api_key_scopes()) == 2
    assert settings.parsed_policy_paths() == ["a.yaml", "b.yaml"]
    assert settings.parsed_model_paths() == ["model.yaml"]
    assert settings.parsed_cors_allow_origins() == ["http://a", "http://b"]
    assert settings.parsed_cors_allow_methods() == ["GET", "POST"]
    assert settings.parsed_cors_allow_headers() == ["X-Test", "Content-Type"]
    assert settings.resolved_resilience_executor_workers() >= 4


def test_keynetra_engine_covers_conditions_and_helpers() -> None:
    evaluator = ConditionEvaluator()
    auth_input = AuthorizationInput(
        user={
            "id": "u1",
            "roles": ["manager"],
            "permissions": ["direct"],
            "direct_permissions": ["write"],
            "relations": [{"relation": "viewer", "object_type": "document", "object_id": "doc-1"}],
            "country": "US",
        },
        action="read",
        resource={"id": "doc-1", "resource_type": "document", "country": "US"},
        context={"current_time": "23:30"},
    )
    assert evaluator.evaluate({"unknown": True}, auth_input) == (
        False,
        "unknown condition: unknown",
    )
    assert (
        evaluator.evaluate(
            {"max_amount": 10},
            AuthorizationInput(user={}, action="read", resource={"amount": "bad"}),
        )[1]
        == "invalid amount"
    )
    assert evaluator.evaluate({"owner_only": False}, auth_input) == (True, None)
    assert evaluator.evaluate({"time_range": {"start": "22:00", "end": "02:00"}}, auth_input) == (
        True,
        None,
    )
    assert evaluator.evaluate(
        {"geo_match": {"user_field": "country", "resource_field": "country"}}, auth_input
    ) == (True, None)
    assert evaluator.evaluate(
        {
            "has_relation": {
                "relation": "viewer",
                "object_type": "document",
                "object_id_from_resource": "id",
            }
        },
        auth_input,
    ) == (True, None)
    assert (
        evaluator.evaluate({"has_relation": {"relation": "viewer"}}, auth_input)[1]
        == "invalid has_relation"
    )

    engine = KeyNetraEngine(
        [{"action": "read", "effect": "allow", "conditions": {"role": "manager"}}]
    )
    decision = engine.check_access(
        subject={"id": "u1", "role": "manager"},
        action="read",
        resource="document:doc-1",
    )
    assert decision.allowed is True
    assert engine._parse_descriptor("document:doc-1") == ("document", "doc-1")  # noqa: SLF001
    assert engine._parse_descriptor("doc-1") == ("doc-1", "doc-1")  # noqa: SLF001
    assert engine._normalize_subject({"id": "u2"}) == {"id": "u2"}  # noqa: SLF001
    assert (
        engine._normalize_resource("document:doc-2")["resource_type"] == "document"
    )  # noqa: SLF001
    assert "relationship:viewer:document:doc-1" in engine._subject_descriptors(
        auth_input
    )  # noqa: SLF001
    assert (
        engine._acl_subject_matches(
            "relationship", "viewer:document:doc-1", engine._subject_descriptors(auth_input)
        )
        is True
    )  # noqa: SLF001
    assert (
        engine._best_reason([(PolicyDefinition(action="read"), False, "because")]) == "because"
    )  # noqa: SLF001
    policy_decision = engine._decision_from_policy(  # noqa: SLF001
        PolicyDefinition(action="read", effect="deny", policy_id="deny-1"),
        trace=[ExplainTraceStep(step="policy", outcome="deny", detail="matched")],
        failed_conditions=["role mismatch"],
    )
    assert policy_decision.decision == "deny"
    with pytest.raises(TypeError):
        engine.decide({"id": "u1"})


def test_admin_tools_internal_helpers_cover_export_import_and_lookup() -> None:
    db = _db_session()
    tenant = Tenant(tenant_key="acme", policy_version=1, authorization_revision=1)
    permission = Permission(action="read")
    role = Role(name="admin", permissions=[permission])
    user = User(external_id="u-1", roles=[role])
    relationship = Relationship(
        tenant_id=1,
        subject_type="user",
        subject_id="u-1",
        relation="viewer",
        object_type="document",
        object_id="doc-1",
    )
    db.add_all([tenant, permission, role, user])
    db.commit()
    tenant = db.query(Tenant).filter_by(tenant_key="acme").one()
    relationship.tenant_id = tenant.id
    db.add(relationship)
    db.commit()

    policy_calls: list[dict[str, Any]] = []
    auth_models: dict[int, AuthorizationModel] = {}
    acl_entries: list[dict[str, Any]] = []
    relationships_created: list[dict[str, Any]] = []
    revisions: list[str] = []

    class _PolicyRepo:
        def list_current_policy_views(self, *, tenant_id: int) -> list[dict[str, Any]]:
            return [{"policy_key": "read-doc"}]

    class _TenantRepo:
        def get_or_create(self, tenant_key: str) -> Tenant:
            return tenant

        def bump_revision(self, tenant_obj: Tenant) -> Tenant:
            revisions.append(tenant_obj.tenant_key)
            return tenant_obj

    class _PolicyService:
        def create_policy(self, **kwargs: Any) -> None:
            policy_calls.append(kwargs)

    class _AuthModelRepo:
        def get_model(self, *, tenant_id: int) -> AuthorizationModel | None:
            return auth_models.get(tenant_id)

        def upsert_model(
            self,
            *,
            tenant_id: int,
            schema_text: str,
            schema_json: dict[str, Any],
            compiled_json: dict[str, Any],
        ) -> None:
            auth_models[tenant_id] = AuthorizationModel(
                tenant_id=tenant_id,
                schema_text=schema_text,
                schema_json=schema_json,
                compiled_json=compiled_json,
            )

    class _AclRepo:
        def create_acl_entry(self, **kwargs: Any) -> int:
            acl_entries.append(kwargs)
            return len(acl_entries)

    class _RelationshipRepo:
        def create(self, **kwargs: Any) -> None:
            relationships_created.append(kwargs)

    services = SimpleNamespace(
        db=db,
        policy_repo=_PolicyRepo(),
        policy_service=_PolicyService(),
        auth_model_repo=_AuthModelRepo(),
        tenant_repo=_TenantRepo(),
        acl_repo=_AclRepo(),
        relationship_repo=_RelationshipRepo(),
        decision_cache=SimpleNamespace(
            bump_namespace=lambda tenant_key: revisions.append(tenant_key)
        ),
        access_index_cache=SimpleNamespace(
            invalidate_global=lambda: revisions.append("invalidate")
        ),
    )

    assert admin_tools._normalize_resource(" roles ") == "roles"  # noqa: SLF001
    with pytest.raises(ApiError):
        admin_tools._normalize_resource("unknown")  # noqa: SLF001
    assert admin_tools._generate_api_key()  # noqa: SLF001
    assert admin_tools._get_or_create_user(services, "u-1").external_id == "u-1"  # noqa: SLF001
    assert admin_tools._get_or_create_user(services, "u-2").external_id == "u-2"  # noqa: SLF001
    assert admin_tools._get_user_or_404(services, "u-1").external_id == "u-1"  # noqa: SLF001
    with pytest.raises(ApiError):
        admin_tools._get_user_or_404(services, "missing")  # noqa: SLF001

    assert admin_tools._export_resource(services, tenant.id, "policies") == [
        {"policy_key": "read-doc"}
    ]  # noqa: SLF001
    assert admin_tools._export_resource(services, tenant.id, "auth-model") is None  # noqa: SLF001
    assert (
        admin_tools._export_resource(services, tenant.id, "roles")[0]["name"] == "admin"
    )  # noqa: SLF001
    assert (
        admin_tools._export_resource(services, tenant.id, "permissions")[0]["action"] == "read"
    )  # noqa: SLF001
    assert (
        admin_tools._export_resource(services, tenant.id, "relationships")[0]["relation"]
        == "viewer"
    )  # noqa: SLF001

    assert (
        admin_tools._import_resource(  # noqa: SLF001
            services,
            "acme",
            "policies",
            [{"action": "read", "effect": "allow", "priority": 1, "conditions": {}}],
        )
        == 1
    )
    assert policy_calls[0]["policy_key"] == "read"
    assert (
        admin_tools._import_resource(  # noqa: SLF001
            services,
            "acme",
            "auth-model",
            {"schema_text": "type user", "schema_json": {}, "compiled_json": {}},
        )
        == 1
    )
    assert (
        admin_tools._import_resource(services, "acme", "roles", ["developer"]) == 1
    )  # noqa: SLF001
    assert (
        admin_tools._import_resource(services, "acme", "permissions", ["write"]) == 1
    )  # noqa: SLF001
    assert (
        admin_tools._import_resource(  # noqa: SLF001
            services,
            "acme",
            "acl",
            [
                {
                    "subject_type": "user",
                    "subject_id": "u-1",
                    "resource_type": "document",
                    "resource_id": "doc-1",
                    "action": "read",
                    "effect": "allow",
                }
            ],
        )
        == 1
    )
    assert (
        admin_tools._import_resource(  # noqa: SLF001
            services,
            "acme",
            "relationships",
            [
                {
                    "subject_type": "user",
                    "subject_id": "u-1",
                    "relation": "editor",
                    "object_type": "document",
                    "object_id": "doc-1",
                }
            ],
        )
        == 1
    )
    assert acl_entries and relationships_created and revisions
    admin_tools._sync_role_permissions(db, role, ["read", {"action": "write"}])  # noqa: SLF001
    assert sorted(permission.action for permission in role.permissions) == ["read", "write"]


def test_cli_helpers_and_commands_cover_branchy_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reset_settings_cache()
    ctx = SimpleNamespace(obj={})
    ctx.obj = {"config": "settings.yaml"}
    assert _effective_config_path(ctx, None) == "settings.yaml"
    assert _effective_config_path(ctx, "explicit.yaml") == "explicit.yaml"

    monkeypatch.setattr(
        "keynetra.cli.get_settings",
        lambda: SimpleNamespace(server_host="0.0.0.0", server_port=9000),
    )
    assert _resolve_url(None, "/health", use_settings=True) == "http://127.0.0.1:9000/health"
    assert (
        _resolve_url("http://localhost:8000", "/health", use_settings=False)
        == "http://localhost:8000/health"
    )
    assert _percentile([], 50) == 0.0
    assert _percentile([1.0, 2.0, 3.0], 50) == 2.0
    assert _coerce_scalar("42") == 42
    assert _coerce_scalar("u1") == "u1"

    monkeypatch.setattr("keynetra.cli._maybe_load_config", lambda ctx, config: None)
    monkeypatch.setattr("keynetra.cli.create_engine_for_url", lambda url: object())
    monkeypatch.setattr("keynetra.cli._read_applied_revisions", lambda engine: {"a"})
    monkeypatch.setattr(
        "keynetra.cli.find_destructive_revisions", lambda versions_dir, applied: ["drop-users"]
    )
    monkeypatch.setattr(
        "keynetra.cli.get_settings", lambda: SimpleNamespace(database_url="sqlite:///db.sqlite")
    )
    with pytest.raises(Exit):
        migrate(SimpleNamespace(obj={}), revision="head", confirm_destructive=False, config=None)

    policy_file = tmp_path / "policy.json"
    policy_file.write_text(
        json.dumps([{"action": "read", "effect": "allow", "priority": 1, "conditions": {}}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "keynetra.cli.get_settings",
        lambda: SimpleNamespace(parsed_policy_paths=lambda: [str(policy_file)]),
    )
    compile_policies(SimpleNamespace(obj={}), path=None, config=None)

    contract = {"openapi": "3.1.0", "info": {"title": "KeyNetra", "version": "1.0.0"}, "paths": {}}
    monkeypatch.setattr(
        "keynetra.cli.create_app",
        lambda: SimpleNamespace(openapi=lambda: contract),
        raising=False,
    )
    output_path = tmp_path / "openapi.json"
    yaml_path = tmp_path / "openapi.yaml"
    generate_openapi(output=str(output_path), yaml_output=str(yaml_path))
    check_openapi(contract=str(output_path))
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps({"openapi": "3.0.0"}), encoding="utf-8")
    with pytest.raises(Exit):
        check_openapi(contract=str(drift_path))

    monkeypatch.setattr(
        "keynetra.cli.run_core_doctor", lambda settings: {"ok": False, "checks": []}
    )
    monkeypatch.setattr(
        "keynetra.cli.get_settings", lambda: SimpleNamespace(environment="development")
    )
    with pytest.raises(Exit):
        doctor(SimpleNamespace(obj={}), service="core", config=None)
    with pytest.raises(BadParameter):
        doctor(SimpleNamespace(obj={}), service="saas", config=None)

    monkeypatch.setattr(
        "keynetra.cli.run_core_doctor",
        lambda settings: {
            "ok": False,
            "checks": [
                {
                    "ok": False,
                    "name": "db",
                    "message": "broken",
                    "details": {"remediation": ["fix"]},
                }
            ],
        },
    )
    with pytest.raises(Exit):
        config_doctor(SimpleNamespace(obj={}), config=None)

    def _empty_benchmark(coro: Any) -> list[float]:
        coro.close()
        return []

    monkeypatch.setattr("keynetra.cli.asyncio.run", _empty_benchmark)
    with pytest.raises(Exit):
        benchmark(url="http://localhost", requests=1, concurrency=1, api_key="devkey", timeout=1.0)


def test_openapi_and_modeling_helpers_cover_normalization_and_validation() -> None:
    app = FastAPI(title="KeyNetra", version="1.0.0", description="desc")

    @app.get("/items", tags=["items", "items"])
    def list_items() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/dev/internal")
    def dev_only() -> dict[str, str]:
        return {"ok": "dev"}

    schema = build_openapi_schema(app)
    assert "/metrics" in schema["paths"]
    assert "/dev/internal" not in schema["paths"]

    route = next(
        route for route in app.routes if isinstance(route, APIRoute) and route.path == "/items"
    )
    metadata_schema = {"paths": {"/items": {"get": {"tags": ["items", "items"]}}}}
    _apply_route_metadata(app, metadata_schema)
    assert metadata_schema["paths"]["/items"]["get"]["operationId"] == route.name
    assert metadata_schema["paths"]["/items"]["get"]["tags"] == ["items"]

    document = {"type": ["string", "null"], "properties": {"error": {"type": "null"}}}
    _normalize_for_sdk_codegen(document)
    assert document["openapi"] == "3.0.3"

    responses = {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}}
    _ensure_common_error_responses(responses)
    _ensure_response_examples(responses)
    _ensure_parameter_ref([], "#/components/parameters/ApiVersionHeader")
    _document_non_json_exceptions(schema)
    assert _extract_nullable_variant({"anyOf": [{"type": "null"}, {"type": "string"}]}) == {
        "type": "string"
    }

    parsed = parse_authorization_schema(
        """
        model schema 1
        type user
        type document
        relations
        owner: [user]
        permissions
        read = owner
        """
    )
    validate_authorization_schema(parsed)
    with pytest.raises(ValueError):
        parse_authorization_schema("model schema 1\nrelations\nowner: user")
    with pytest.raises(ValueError):
        validate_authorization_schema(
            AuthorizationSchema(
                version=1,
                types=("user",),
                relations={},
                permissions={"read": IdentifierExpr("missing")},
            )
        )


def test_admin_tools_routes_cover_management_endpoints(tmp_path: Path) -> None:
    import os

    database_url = f"sqlite+pysqlite:///{tmp_path / 'admin-tools.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
    )
    reset_settings_cache()
    initialize_database(database_url)
    client = TestClient(create_app())
    headers = {"X-API-Key": "testkey"}

    created_tenant = client.post("/tenants", json={"tenant_key": "acme"}, headers=headers)
    assert created_tenant.status_code == 201
    assert client.get("/tenants", headers=headers).status_code == 200
    assert client.get("/tenants/acme", headers=headers).status_code == 200

    mismatch = client.post(
        "/tenants/acme/api-keys",
        json={"name": "bad", "scopes": {"tenant": "other", "role": "viewer", "permissions": []}},
        headers=headers,
    )
    assert mismatch.status_code == 422
    created_key = client.post(
        "/tenants/acme/api-keys",
        json={"name": "good", "scopes": {"role": "developer", "permissions": ["read"]}},
        headers=headers,
    )
    assert created_key.status_code == 201
    assert client.get("/tenants/acme/api-keys", headers=headers).status_code == 200

    created_role = client.post("/roles", json={"name": "auditor"}, headers=headers)
    role_id = created_role.json()["data"]["id"]
    assert client.post(f"/users/u-1/roles/{role_id}", headers=headers).status_code == 200
    assert client.get("/users/u-1/roles", headers=headers).status_code == 200
    assert client.delete(f"/users/u-1/roles/{role_id}", headers=headers).status_code == 200

    created_policy = client.post(
        "/policies",
        json={
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin", "policy_key": "audit-policy"},
        },
        headers=headers,
    )
    assert created_policy.status_code == 201
    assert (
        client.put(
            "/policies/audit-policy",
            json={"action": "read", "effect": "deny", "priority": 5, "conditions": {}},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get("/policies/audit-policy/versions", headers=headers).status_code == 200
    assert client.get("/policies/audit-policy/versions/1", headers=headers).status_code == 200
    assert (
        client.get("/policies/audit-policy/versions/1/diff/2", headers=headers).status_code == 200
    )
    assert (
        client.post("/policies/audit-policy/versions/1/restore", headers=headers).status_code == 200
    )
    assert (
        client.post("/policy-tests/run", json={"document": "invalid"}, headers=headers).status_code
        == 422
    )
