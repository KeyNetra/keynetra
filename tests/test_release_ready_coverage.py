from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from typer import Exit

from keynetra.api.errors import ApiError
from keynetra.api.openapi import (
    _apply_standard_contract_metadata,
    _error_code_for_status,
    _extract_nullable_variant,
    _normalize_node,
    _unique_operation_id,
    build_openapi_schema,
)
from keynetra.api.routes import admin_tools
from keynetra.config.policies import DEFAULT_POLICIES
from keynetra.config.settings import Settings, reset_settings_cache
from keynetra.domain.models.acl import ResourceACL
from keynetra.domain.models.auth_model import AuthorizationModel
from keynetra.domain.models.base import Base
from keynetra.domain.models.rbac import Role, User
from keynetra.domain.models.tenant import Tenant
from keynetra.engine.keynetra_engine import (
    AuthorizationInput,
    ConditionEvaluator,
    KeyNetraEngine,
)
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app
from keynetra.modeling.model_validator import validate_authorization_schema
from keynetra.modeling.schema_parser import (
    AndExpr,
    AuthorizationSchema,
    IdentifierExpr,
    NotExpr,
    OrExpr,
    parse_authorization_schema,
)
from keynetra.services.access_indexer import AccessIndexer, AccessSubject, relationship_descriptor
from keynetra.services.attribute_validation import (
    AttributeValidationError,
    validate_resource,
    validate_user,
)
from keynetra.services.interfaces import AccessIndexEntry, ACLRecord, RelationshipRecord
from keynetra.services.seeding import _clear_sample_data, _ensure_policy, seed_demo_data


def _memory_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _app_client(tmp_path: Path, *, scopes: str | None = None) -> TestClient:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+pysqlite:///{tmp_path / 'release-ready.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = scopes or json.dumps(
        {"testkey": {"tenant": "default", "role": "admin", "permissions": ["*"]}}
    )
    os.environ.pop("KEYNETRA_REDIS_URL", None)
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def test_settings_cover_security_profile_and_policy_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KEYNETRA_POLICIES_JSON", raising=False)
    monkeypatch.delenv("KEYNETRA_POLICY_PATHS", raising=False)
    monkeypatch.delenv("KEYNETRA_MODEL_PATHS", raising=False)
    with pytest.raises(ValueError, match="admin_password is not allowed"):
        Settings(
            environment="ci",
            api_keys="key",
            admin_password="plaintext",
        )
    with pytest.raises(ValueError, match="default admin username"):
        Settings(
            environment="ci",
            api_keys="key",
            admin_username="admin",
        )
    with pytest.raises(ValueError, match="redis_url cannot be blank"):
        Settings(
            environment="ci",
            api_keys="key",
            redis_url="   ",
        )

    policy_file = tmp_path / "policies.json"
    policy_file.write_text(
        json.dumps([{"action": "read", "effect": "allow", "priority": 1, "conditions": {}}]),
        encoding="utf-8",
    )
    from_paths = Settings(environment="development", policy_paths=str(policy_file))
    assert from_paths.load_policies() == [
        {
            "action": "read",
            "effect": "allow",
            "priority": 1,
            "conditions": {},
            "policy_id": None,
        }
    ]

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    empty_paths = Settings(environment="development", policy_paths=str(empty_dir))
    assert empty_paths.load_policies() == DEFAULT_POLICIES

    invalid_json = Settings(environment="development", policies_json="{")
    assert invalid_json.load_policies() == DEFAULT_POLICIES

    wrong_root = Settings(environment="development", policies_json=json.dumps({"x": 1}))
    assert wrong_root.load_policies() == DEFAULT_POLICIES

    mixed_list = Settings(
        environment="development",
        policies_json=json.dumps([{"action": "read"}, "skip", {"action": "write"}]),
        api_key_scopes_json="not-json",
    )
    assert mixed_list.load_policies() == [{"action": "read"}, {"action": "write"}]
    assert mixed_list.parsed_api_key_scopes() == {}

    non_dict_scopes = Settings(
        environment="development",
        api_key_hashes="f" * 64,
        api_key_scopes_json=json.dumps(
            {
                "raw-key": {"tenant": "acme", "permissions": "bad"},
                "f" * 64: {"tenant": "acme", "role": "viewer", "permissions": ["read"]},
                "skip": "nope",
            }
        ),
        cors_allow_origins=None,
        cors_allow_methods="",
        cors_allow_headers="",
    )
    parsed_scopes = non_dict_scopes.parsed_api_key_scopes()
    assert len(parsed_scopes) == 2
    assert parsed_scopes["f" * 64]["permissions"] == ["read"]
    assert all(isinstance(value, dict) for value in parsed_scopes.values())
    assert non_dict_scopes.parsed_cors_allow_origins() == []
    assert non_dict_scopes.parsed_cors_allow_methods() == ["*"]
    assert non_dict_scopes.parsed_cors_allow_headers() == ["*"]
    assert non_dict_scopes.is_development() is True


def test_openapi_helpers_cover_nullable_and_metadata_paths() -> None:
    schema = {
        "paths": {
            "/policies": {
                "get": {
                    "parameters": [{"$ref": "#/components/parameters/ApiVersionHeader"}],
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"type": "object"}}}},
                        "400": {"description": "bad"},
                    },
                }
            },
            "/metrics": {"get": {"responses": {"200": {"description": "ok"}}}},
        }
    }
    _apply_standard_contract_metadata(schema)
    policy_parameters = schema["paths"]["/policies"]["get"]["parameters"]
    assert {"$ref": "#/components/parameters/TenantHeader"} in policy_parameters
    assert policy_parameters.count({"$ref": "#/components/parameters/ApiVersionHeader"}) == 1
    assert "401" in schema["paths"]["/policies"]["get"]["responses"]
    assert "400" in schema["paths"]["/policies"]["get"]["responses"]
    assert "401" not in schema["paths"]["/metrics"]["get"]["responses"]

    nullable_variant = _extract_nullable_variant(
        {"anyOf": [{"type": "null"}, {"type": "string", "title": "Example"}]}
    )
    assert nullable_variant == {"type": "string", "title": "Example"}

    nullable_node = {"type": "null", "description": "desc"}
    _normalize_node(nullable_node)
    assert nullable_node == {"nullable": True, "description": "desc"}

    error_node = {"type": "null", "title": "Error", "description": "nullable"}
    _normalize_node(error_node, parent_key="error")
    assert error_node["allOf"] == [{"$ref": "#/components/schemas/ErrorBody"}]
    assert error_node["nullable"] is True

    empty_type_node = {"type": ["null"]}
    _normalize_node(empty_type_node)
    assert empty_type_node == {"nullable": True}

    assert _extract_nullable_variant({"anyOf": [{"type": "string"}, {"type": "integer"}]}) is None
    assert _unique_operation_id("listItems", {"listItems"}) == "listItems_2"
    assert _error_code_for_status("418") == "bad_request"

    app = FastAPI(title="KeyNetra", version="1.0.0")

    @app.get("/items")
    def list_items() -> dict[str, str]:
        return {"ok": "yes"}

    first = build_openapi_schema(app)
    second = build_openapi_schema(app)
    assert first is second


def test_schema_parser_and_model_validator_cover_error_paths() -> None:
    parsed = parse_authorization_schema(
        """
        model schema 2
        type user
        type document
        relations
        owner: [user]
        editor: [user]
        permissions
        read = owner or (editor and not banned)
        banned = editor and not owner
        """
    )
    assert isinstance(parsed.permissions["read"], OrExpr)
    assert isinstance(parsed.permissions["banned"], AndExpr)

    with pytest.raises(ValueError, match="schema is empty"):
        parse_authorization_schema("   \n# comment only")
    with pytest.raises(ValueError, match="unexpected schema line"):
        parse_authorization_schema("model schema 1\nbogus")
    with pytest.raises(ValueError, match="invalid relation subjects"):
        parse_authorization_schema("model schema 1\ntype user\nrelations\nowner: user")
    with pytest.raises(ValueError, match="invalid relation subjects"):
        parse_authorization_schema("model schema 1\ntype user\nrelations\nowner: []")
    with pytest.raises(ValueError, match="invalid permission"):
        parse_authorization_schema("model schema 1\ntype user\npermissions\nread owner")
    with pytest.raises(ValueError, match="invalid permission"):
        parse_authorization_schema("model schema 1\ntype user\npermissions\nread = ")
    with pytest.raises(ValueError, match="invalid permission expression"):
        parse_authorization_schema("model schema 1\ntype user\npermissions\nread = owner + editor")
    with pytest.raises(ValueError, match="unexpected end of expression"):
        parse_authorization_schema("model schema 1\ntype user\npermissions\nread = not")
    with pytest.raises(ValueError, match="missing closing parenthesis"):
        parse_authorization_schema("model schema 1\ntype user\npermissions\nread = (owner")
    with pytest.raises(ValueError, match="invalid expression"):
        parse_authorization_schema("model schema 1\ntype user\npermissions\nread = and owner")
    with pytest.raises(ValueError, match="invalid permission expression"):
        parse_authorization_schema("model schema 1\ntype user\npermissions\nread = owner editor")

    with pytest.raises(ValueError, match="schema version must be >= 1"):
        validate_authorization_schema(AuthorizationSchema(version=0))
    with pytest.raises(ValueError, match="at least one type"):
        validate_authorization_schema(
            AuthorizationSchema(version=1, permissions={"read": IdentifierExpr("x")})
        )
    with pytest.raises(ValueError, match="define type user"):
        validate_authorization_schema(
            AuthorizationSchema(
                version=1, types=("document",), permissions={"read": IdentifierExpr("x")}
            )
        )
    with pytest.raises(ValueError, match="define permissions"):
        validate_authorization_schema(AuthorizationSchema(version=1, types=("user",)))
    with pytest.raises(ValueError, match="unknown type"):
        validate_authorization_schema(
            AuthorizationSchema(
                version=1,
                types=("user",),
                relations={"owner": ("group",)},
                permissions={"read": IdentifierExpr("owner")},
            )
        )
    with pytest.raises(ValueError, match="non-empty"):
        validate_authorization_schema(
            AuthorizationSchema(
                version=1,
                types=("user",),
                relations={"": ("user",)},
                permissions={"read": IdentifierExpr("read")},
            )
        )
    with pytest.raises(ValueError, match="permission names must be non-empty"):
        validate_authorization_schema(
            AuthorizationSchema(
                version=1, types=("user",), permissions={"": IdentifierExpr("read")}
            )
        )
    with pytest.raises(ValueError, match="unknown relation or permission"):
        validate_authorization_schema(
            AuthorizationSchema(
                version=1, types=("user",), permissions={"read": IdentifierExpr("missing")}
            )
        )
    with pytest.raises(ValueError, match="invalid expression node"):
        validate_authorization_schema(
            AuthorizationSchema(
                version=1, types=("user",), permissions={"read": cast(Any, object())}
            )
        )

    validate_authorization_schema(
        AuthorizationSchema(
            version=1,
            types=("user", "document"),
            relations={"owner": ("user",)},
            permissions={
                "owner_permission": IdentifierExpr("owner"),
                "read": NotExpr(
                    OrExpr(
                        IdentifierExpr("owner"),
                        AndExpr(IdentifierExpr("owner_permission"), IdentifierExpr("owner")),
                    )
                ),
            },
        )
    )


def test_keynetra_engine_covers_acl_relationship_and_policy_graph_branches() -> None:
    evaluator = ConditionEvaluator()
    auth_input = AuthorizationInput(
        user={"relations": "bad"}, action="read", resource={"amount": 5}
    )
    assert evaluator.handle_time_range("bad", auth_input) == (False, "invalid time_range")
    assert evaluator.handle_time_range({"start": 1, "end": "09:00"}, auth_input) == (
        False,
        "invalid time_range",
    )
    assert evaluator.handle_geo_match("bad", auth_input) == (False, "invalid geo_match")
    assert evaluator.handle_has_relation({}, auth_input) == (False, "invalid has_relation")
    assert evaluator.handle_has_relation(
        {"relation": "viewer", "object_type": "doc", "object_id": "1"},
        auth_input,
    ) == (False, "no relations")

    engine = KeyNetraEngine(
        [{"action": "read", "effect": "allow", "priority": 1, "conditions": {}}]
    )
    trace: list[Any] = []
    assert engine._evaluate_acl(  # noqa: SLF001
        AuthorizationInput(user={}, action="read", resource={}),
        trace=trace,
        user_subjects=set(),
    ) == ("abstain", None, None)
    assert trace[-1].detail == "resource identity unavailable"

    acl_from_index = AuthorizationInput(
        user={"id": "u1"},
        action="read",
        resource={"resource_type": "document", "resource_id": "doc-1"},
        access_index_entries=(
            {
                "source": "acl",
                "id": 7,
                "subject_type": "user",
                "subject_id": "u1",
                "resource_type": "document",
                "resource_id": "doc-1",
                "action": "read",
                "effect": "weird",
            },
        ),
    )
    assert engine._evaluate_acl(
        acl_from_index, trace=[], user_subjects={"user:u1"}
    ) == (  # noqa: SLF001
        "abstain",
        None,
        None,
    )

    assert (
        engine._evaluate_role_permissions(  # noqa: SLF001
            AuthorizationInput(user={"role_permissions": ["read"]}, action="read", resource={}),
            trace=[],
        )[0]
        == "allow"
    )

    assert engine._evaluate_relationship_index(  # noqa: SLF001
        AuthorizationInput(user={}, action="read", resource={}),
        trace=[],
        user_subjects=set(),
    ) == ("abstain", None, None)

    relationship_input = AuthorizationInput(
        user={"id": "u1"},
        action="read",
        resource={"resource_type": "document", "resource_id": "doc-1"},
        access_index_entries=(
            {"source": "relationship"},
            {
                "source": "relationship",
                "resource_type": "document",
                "resource_id": "doc-1",
                "action": "read",
                "allowed_subjects": "bad",
            },
            {
                "source": "relationship",
                "resource_type": "document",
                "resource_id": "doc-2",
                "action": "read",
                "allowed_subjects": ["user:u1"],
            },
            {
                "source": "relationship",
                "resource_type": "document",
                "resource_id": "doc-1",
                "action": "*",
                "allowed_subjects": ["user:u1"],
            },
        ),
    )
    assert (
        engine._evaluate_relationship_index(  # noqa: SLF001
            relationship_input,
            trace=[],
            user_subjects={"user:u1"},
        )[0]
        == "allow"
    )

    compiled_allow = SimpleNamespace(
        evaluate=lambda authorization_input: SimpleNamespace(
            outcome="allow", reason=None, policy_id="policy:1"
        )
    )
    assert engine._evaluate_compiled_policies(  # noqa: SLF001
        AuthorizationInput(user={}, action="read", resource={}, compiled_graph=compiled_allow),
        trace=[],
    ) == ("allow", None, "policy:1")

    compiled_abstain = SimpleNamespace(
        evaluate=lambda authorization_input: SimpleNamespace(
            outcome="abstain", reason=None, policy_id=None
        )
    )
    assert engine._evaluate_compiled_policies(  # noqa: SLF001
        AuthorizationInput(user={}, action="read", resource={}, compiled_graph=compiled_abstain),
        trace=[],
    ) == ("abstain", None, None)

    permission_allow = SimpleNamespace(
        evaluate=lambda authorization_input: SimpleNamespace(
            outcome="deny", reason="schema deny", policy_id="schema:1"
        )
    )
    assert engine._evaluate_permission_graph(  # noqa: SLF001
        AuthorizationInput(user={}, action="read", resource={}, permission_graph=permission_allow),
        trace=[],
    ) == ("deny", "schema deny", "schema:1")

    assert engine._subject_descriptors(  # noqa: SLF001
        AuthorizationInput(
            user={
                "id": "u1",
                "roles": "bad",
                "permissions": "bad",
                "direct_permissions": "bad",
                "relations": ["bad"],
            },
            action="read",
            resource={},
        )
    ) == {"user:u1"}
    assert engine._resource_identity({"kind": "document", "id": "doc-1"}) == (  # noqa: SLF001
        "document",
        "doc-1",
    )
    assert (
        engine._acl_matches({}, "document", "doc-1", "read", {"user:u1"}) is False
    )  # noqa: SLF001
    assert engine._acl_subject_matches("user", "", {"user:u1"}) is False  # noqa: SLF001
    assert (
        engine._acl_subject_matches(  # noqa: SLF001
            "relationship",
            "viewer:document:doc-1",
            {"relationship:viewer:document:doc-1"},
        )
        is True
    )
    assert engine._best_reason([(SimpleNamespace(), True, "x")]) is None  # noqa: SLF001


def test_seeding_covers_reset_and_existing_policy_paths() -> None:
    db = _memory_db()

    first = seed_demo_data(db)
    assert first.created_tenant is True
    assert first.created_user is True
    assert first.created_role is True
    assert first.created_permissions >= 1
    assert first.created_relationships == 1
    assert first.created_policies >= 1

    second = seed_demo_data(db)
    assert second.created_tenant is False
    assert second.created_user is False
    assert second.created_role is False
    assert second.created_permissions == 0
    assert second.created_relationships == 0
    assert second.created_policies == 0

    tenant = db.query(Tenant).filter_by(tenant_key=first.tenant_key).one()
    assert (
        _ensure_policy(  # noqa: SLF001
            db,
            tenant_id=tenant.id,
            policy_key="existing",
            action="read",
            effect="allow",
            priority=1,
            conditions={},
        )
        == 1
    )
    db.commit()
    assert (
        _ensure_policy(  # noqa: SLF001
            db,
            tenant_id=tenant.id,
            policy_key="existing",
            action="read",
            effect="allow",
            priority=1,
            conditions={},
        )
        == 0
    )

    reset_summary = seed_demo_data(db, reset=True)
    assert reset_summary.created_tenant is True
    assert db.query(Tenant).filter_by(tenant_key=first.tenant_key).count() == 1

    _clear_sample_data(db, tenant_key="missing")  # noqa: SLF001


def test_admin_tools_helper_branches_cover_acl_export_and_invalid_payloads() -> None:
    db = _memory_db()
    tenant = Tenant(tenant_key="acme", policy_version=1, authorization_revision=1)
    db.add(tenant)
    db.commit()
    tenant = db.query(Tenant).filter_by(tenant_key="acme").one()

    db.add(
        ResourceACL(
            tenant_id=tenant.id,
            subject_type="user",
            subject_id="u-1",
            resource_type="document",
            resource_id="doc-1",
            action="read",
            effect="allow",
        )
    )
    db.commit()

    policy_calls: list[dict[str, Any]] = []
    revisions: list[str] = []
    relationship_payloads: list[dict[str, Any]] = []

    class TenantRepo:
        def get_or_create(self, tenant_key: str) -> Tenant:
            return tenant

        def bump_revision(self, tenant_key: str) -> None:
            revisions.append(tenant_key)

    class PolicyService:
        def create_policy(self, **kwargs: Any) -> None:
            policy_calls.append(kwargs)

    class AuthModelRepo:
        def get_model(self, *, tenant_id: int) -> AuthorizationModel | None:
            return None

        def upsert_model(
            self,
            *,
            tenant_id: int,
            schema_text: str,
            schema_json: dict[str, Any],
            compiled_json: dict[str, Any],
        ) -> None:
            revisions.append(schema_text)

    class AclRepo:
        def create_acl_entry(self, **kwargs: Any) -> int:
            revisions.append("acl")
            return 1

    class RelationshipRepo:
        def create(self, **kwargs: Any) -> None:
            relationship_payloads.append(kwargs)
            if kwargs["object_id"] == "dup":
                raise IntegrityError("dup", {}, None)

    services = SimpleNamespace(
        db=db,
        tenant_repo=TenantRepo(),
        policy_service=PolicyService(),
        auth_model_repo=AuthModelRepo(),
        acl_repo=AclRepo(),
        relationship_repo=RelationshipRepo(),
        policy_repo=SimpleNamespace(list_current_policy_views=lambda tenant_id: []),
        decision_cache=SimpleNamespace(
            bump_namespace=lambda tenant_key: revisions.append(f"cache:{tenant_key}")
        ),
        access_index_cache=SimpleNamespace(
            invalidate_global=lambda: revisions.append("invalidate")
        ),
    )

    exported_acl = admin_tools._export_resource(services, tenant.id, "acl")  # noqa: SLF001
    assert exported_acl[0]["action"] == "read"
    assert (
        admin_tools._get_tenant_for_request(services, "acme").tenant_key == "acme"
    )  # noqa: SLF001
    with pytest.raises(ApiError, match="tenant not found"):
        admin_tools._get_tenant_or_404(services, "missing")  # noqa: SLF001

    with pytest.raises(ApiError, match="payload must be a list"):
        admin_tools._import_resource(services, "acme", "policies", {})  # noqa: SLF001
    with pytest.raises(ApiError, match="auth-model payload requires schema_text"):
        admin_tools._import_resource(services, "acme", "auth-model", {})  # noqa: SLF001
    with pytest.raises(ApiError, match="payload must be a list"):
        admin_tools._import_resource(services, "acme", "roles", {})  # noqa: SLF001
    with pytest.raises(ApiError, match="payload must be a list"):
        admin_tools._import_resource(services, "acme", "permissions", {})  # noqa: SLF001
    with pytest.raises(ApiError, match="payload must be a list"):
        admin_tools._import_resource(services, "acme", "acl", {})  # noqa: SLF001
    with pytest.raises(ApiError, match="payload must be a list"):
        admin_tools._import_resource(services, "acme", "relationships", {})  # noqa: SLF001

    assert (
        admin_tools._import_resource(  # noqa: SLF001
            services,
            "acme",
            "policies",
            [None, {"action": "read", "effect": "allow", "priority": 1, "conditions": {}}],
        )
        == 1
    )
    assert policy_calls[0]["policy_key"] == "read"

    assert (
        admin_tools._import_resource(  # noqa: SLF001
            services,
            "acme",
            "roles",
            [None, {"permissions": []}, {"name": "developer", "permissions": ["read"]}],
        )
        == 1
    )
    assert (
        admin_tools._import_resource(
            services, "acme", "permissions", [None, {}, {"action": "deploy"}]
        )  # noqa: SLF001
        == 1
    )
    assert (
        admin_tools._import_resource(  # noqa: SLF001
            services,
            "acme",
            "acl",
            [
                None,
                {
                    "subject_type": "user",
                    "subject_id": "u-1",
                    "resource_type": "doc",
                    "resource_id": "1",
                    "action": "read",
                },
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
                None,
                {
                    "subject_type": "user",
                    "subject_id": "u-1",
                    "relation": "viewer",
                    "object_type": "doc",
                    "object_id": "dup",
                },
                {
                    "subject_type": "user",
                    "subject_id": "u-1",
                    "relation": "viewer",
                    "object_type": "doc",
                    "object_id": "ok",
                },
            ],
        )
        == 1
    )
    assert relationship_payloads[-1]["object_id"] == "ok"


def test_admin_tools_routes_cover_error_and_pagination_branches(tmp_path: Path) -> None:
    client = _app_client(tmp_path)
    headers = {"X-API-Key": "testkey"}

    assert client.get("/tenants?limit=101", headers=headers).status_code == 422
    assert client.get("/tenants/missing", headers=headers).status_code == 404

    first = client.post("/tenants", json={"tenant_key": "acme"}, headers=headers)
    assert first.status_code == 201
    assert client.post("/tenants", json={"tenant_key": "acme"}, headers=headers).status_code == 409
    client.post("/tenants", json={"tenant_key": "beta"}, headers=headers)

    paged = client.get("/tenants?limit=1", headers=headers)
    assert paged.status_code == 200
    next_cursor = paged.json()["meta"]["next_cursor"]
    assert next_cursor
    second_page = client.get(f"/tenants?limit=1&cursor={next_cursor}", headers=headers)
    assert second_page.status_code == 200
    assert len(second_page.json()["data"]) == 1

    created_role = client.post("/roles", json={"name": "auditor"}, headers=headers)
    role_id = created_role.json()["data"]["id"]
    assert client.post(f"/users/u-1/roles/{role_id}", headers=headers).status_code == 200
    assert client.post("/users/u-1/roles/9999", headers=headers).status_code == 404
    assert client.delete("/users/u-404/roles/9999", headers=headers).status_code == 404
    assert client.delete("/users/u-1/roles/9999", headers=headers).status_code == 404
    assert client.delete(f"/users/u-1/roles/{role_id}", headers=headers).status_code == 200

    create_key = client.post(
        "/tenants/acme/api-keys",
        json={"name": "automation", "scopes": {"permissions": ["*"]}},
        headers=headers,
    )
    assert create_key.status_code == 201
    key_id = create_key.json()["data"]["id"]
    assert client.delete(f"/tenants/acme/api-keys/{key_id}", headers=headers).status_code == 200
    assert client.get("/tenants/missing/api-keys", headers=headers).status_code == 404

    policy = client.post(
        "/policies",
        json={
            "action": "read_doc",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin", "policy_key": "versioned"},
        },
        headers=headers,
    )
    assert policy.status_code == 201
    assert client.get("/policies/versioned/versions/999", headers=headers).status_code == 404
    assert client.get("/policies/versioned/versions/1/diff/999", headers=headers).status_code == 404
    assert client.get("/audit/export?limit=0", headers=headers).status_code == 422

    scopes = json.dumps({"testkey": {"tenant": "default", "role": "viewer", "permissions": []}})
    viewer_client = _app_client(tmp_path / "viewer", scopes=scopes)
    assert (
        viewer_client.post("/tenants", json={"tenant_key": "blocked"}, headers=headers).status_code
        == 403
    )
    assert (
        viewer_client.post(
            "/bulk/import",
            json={"resource": "permissions", "payload": [{"action": "read"}]},
            headers=headers,
        ).status_code
        == 403
    )


def test_admin_tools_direct_database_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    def request() -> SimpleNamespace:
        return SimpleNamespace(state=SimpleNamespace(admin_tenant_key="acme", request_id="req-1"))

    create_tenant_db = _memory_db()
    rollback_calls: list[str] = []
    original_tenant_rollback = create_tenant_db.rollback
    monkeypatch.setattr(create_tenant_db, "rollback", lambda: rollback_calls.append("tenant"))
    monkeypatch.setattr(
        create_tenant_db,
        "commit",
        lambda: (_ for _ in ()).throw(SQLAlchemyError("boom")),
    )
    with pytest.raises(ApiError, match="db error"):
        admin_tools.create_tenant(
            payload=SimpleNamespace(tenant_key="acme"),
            request=request(),
            services=SimpleNamespace(db=create_tenant_db),
            _=SimpleNamespace(),
        )
    assert rollback_calls == ["tenant"]
    monkeypatch.setattr(create_tenant_db, "rollback", original_tenant_rollback)

    api_key_db = _memory_db()
    tenant = Tenant(tenant_key="acme", policy_version=1, authorization_revision=1)
    api_key_db.add(tenant)
    api_key_db.commit()
    api_key_rollbacks: list[str] = []
    monkeypatch.setattr(api_key_db, "rollback", lambda: api_key_rollbacks.append("api-key"))
    monkeypatch.setattr(
        admin_tools.SqlApiKeyRepository,
        "create_key",
        lambda self, **kwargs: (_ for _ in ()).throw(SQLAlchemyError("boom")),
    )
    with pytest.raises(ApiError, match="db error"):
        admin_tools.create_api_key(
            tenant_key="acme",
            payload=SimpleNamespace(name="broken", scopes=SimpleNamespace(model_dump=lambda: {})),
            request=request(),
            services=SimpleNamespace(db=api_key_db),
            access=SimpleNamespace(role="developer"),
        )
    assert api_key_rollbacks == ["api-key"]

    assign_db = _memory_db()
    role = Role(name="developer")
    user = User(external_id="u-1")
    assign_db.add_all([role, user])
    assign_db.commit()
    assign_rollbacks: list[str] = []
    monkeypatch.setattr(assign_db, "rollback", lambda: assign_rollbacks.append("assign"))
    monkeypatch.setattr(
        assign_db,
        "commit",
        lambda: (_ for _ in ()).throw(SQLAlchemyError("boom")),
    )
    with pytest.raises(ApiError, match="db error"):
        admin_tools.assign_user_role(
            external_id="u-1",
            role_id=role.id,
            request=request(),
            services=SimpleNamespace(db=assign_db),
            access=SimpleNamespace(tenant_key="acme"),
        )
    assert assign_rollbacks == ["assign"]

    remove_db = _memory_db()
    remove_role = Role(name="developer")
    remove_user = User(external_id="u-1", roles=[remove_role])
    remove_db.add_all([remove_role, remove_user])
    remove_db.commit()
    remove_rollbacks: list[str] = []
    monkeypatch.setattr(remove_db, "rollback", lambda: remove_rollbacks.append("remove"))
    monkeypatch.setattr(
        remove_db,
        "commit",
        lambda: (_ for _ in ()).throw(SQLAlchemyError("boom")),
    )
    with pytest.raises(ApiError, match="db error"):
        admin_tools.remove_user_role(
            external_id="u-1",
            role_id=remove_role.id,
            request=request(),
            services=SimpleNamespace(db=remove_db),
            access=SimpleNamespace(tenant_key="acme"),
        )
    assert remove_rollbacks == ["remove"]


def test_cli_check_openapi_still_rejects_invalid_contract(tmp_path: Path) -> None:
    contract_path = tmp_path / "invalid.json"
    contract_path.write_text(json.dumps({"openapi": "3.1.0"}), encoding="utf-8")
    from keynetra.cli import check_openapi

    with pytest.raises(Exit):
        check_openapi(contract=str(contract_path))


def test_user_cache_attribute_validation_and_audit_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    from keynetra.infrastructure.cache import user_cache
    from keynetra.services.audit import AuditWriter

    cache_events: list[tuple[str, str]] = []
    log_events: list[str] = []

    monkeypatch.setattr(
        "keynetra.infrastructure.cache.user_cache.record_cache_event",
        lambda cache_name, outcome: cache_events.append((cache_name, outcome)),
    )
    monkeypatch.setattr(
        "keynetra.infrastructure.cache.user_cache.log_event",
        lambda logger, event, **kwargs: log_events.append(event),
    )

    monkeypatch.setattr("keynetra.infrastructure.cache.user_cache.get_redis", lambda: None)
    assert user_cache.get_cached_user_context("u:1") is None
    user_cache.set_cached_user_context("u:1", {"id": 1}, 5)

    class BrokenRedis:
        def get(self, key: str) -> str:
            raise ConnectionError("down")

        def setex(self, key: str, ttl: int, value: str) -> None:
            raise RuntimeError("down")

    monkeypatch.setattr("keynetra.infrastructure.cache.user_cache.get_redis", lambda: BrokenRedis())
    assert user_cache.get_cached_user_context("u:2") is None
    user_cache.set_cached_user_context("u:2", {"id": 2}, 0)
    assert ("relationship", "fallback") in cache_events
    assert "user_cache_fetch_failed" in log_events
    assert "user_cache_store_failed" in log_events

    class JsonRedis:
        def __init__(self, payload: Any) -> None:
            self.payload = payload
            self.stored: tuple[str, int, str] | None = None

        def get(self, key: str) -> Any:
            return self.payload

        def setex(self, key: str, ttl: int, value: str) -> None:
            self.stored = (key, ttl, value)

    bad_json = JsonRedis("{")
    monkeypatch.setattr("keynetra.infrastructure.cache.user_cache.get_redis", lambda: bad_json)
    assert user_cache.get_cached_user_context("u:3") is None
    assert "user_cache_decode_failed" in log_events

    list_json = JsonRedis(json.dumps(["not", "a", "dict"]))
    monkeypatch.setattr("keynetra.infrastructure.cache.user_cache.get_redis", lambda: list_json)
    assert user_cache.get_cached_user_context("u:4") is None

    good_json = JsonRedis(json.dumps({"id": "u-5"}))
    monkeypatch.setattr("keynetra.infrastructure.cache.user_cache.get_redis", lambda: good_json)
    assert user_cache.get_cached_user_context("u:5") == {"id": "u-5"}
    user_cache.set_cached_user_context("u:5", {"id": "u-5"}, 0)
    assert good_json.stored == ("u:5", 1, '{"id":"u-5"}')

    with pytest.raises(AttributeValidationError, match="user must be an object"):
        validate_user("bad")
    with pytest.raises(AttributeValidationError, match="resource too large"):
        validate_resource({str(i): i for i in range(201)})
    with pytest.raises(AttributeValidationError, match="keys must be strings"):
        validate_user({1: "bad"})
    with pytest.raises(AttributeValidationError, match="list too large"):
        validate_resource({"items": list(range(201))})
    with pytest.raises(AttributeValidationError, match="too deep"):
        validate_user({"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}})

    validate_user({"id": 1, "profile": {"team": "ops"}})
    assert AuditWriter.__name__ == "SqlAuditRepository"


def test_access_indexer_covers_cache_memo_and_invalidation(monkeypatch: pytest.MonkeyPatch) -> None:
    cached_entry = AccessIndexEntry(
        resource_type="document",
        resource_id="doc-1",
        action="read",
        allowed_subjects=("user:u-1",),
        source="acl",
    )

    class AccessCache:
        def __init__(self, cached: list[AccessIndexEntry] | None = None) -> None:
            self.cached = cached
            self.set_calls: list[list[AccessIndexEntry]] = []
            self.invalidated: list[tuple[int, str, str]] = []
            self.invalidated_tenants: list[int] = []

        def get(self, **kwargs: Any) -> list[AccessIndexEntry] | None:
            return self.cached

        def set(self, **kwargs: Any) -> None:
            self.set_calls.append(kwargs["entries"])
            self.cached = kwargs["entries"]

        def invalidate(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None:
            self.invalidated.append((tenant_id, resource_type, resource_id))

        def invalidate_tenant(self, *, tenant_id: int) -> None:
            self.invalidated_tenants.append(tenant_id)

        def invalidate_global(self) -> None:
            self.invalidated_tenants.append(-1)

    class ACLCache:
        def __init__(self, cached: list[ACLRecord] | None = None) -> None:
            self.cached = cached
            self.set_calls: list[list[ACLRecord]] = []
            self.invalidated: list[tuple[int, str, str]] = []

        def get(self, **kwargs: Any) -> list[ACLRecord] | None:
            return self.cached

        def set(self, **kwargs: Any) -> None:
            self.set_calls.append(kwargs["acl_entries"])
            self.cached = kwargs["acl_entries"]

        def invalidate(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None:
            self.invalidated.append((tenant_id, resource_type, resource_id))

    acl_record = ACLRecord(
        id=7,
        tenant_id=1,
        subject_type="user",
        subject_id="u-1",
        resource_type="document",
        resource_id="doc-1",
        action="read",
        effect="allow",
    )
    relationship_row = RelationshipRecord(
        subject_type="relationship",
        subject_id="ignored",
        relation="viewer",
        object_type="document",
        object_id="doc-1",
    )
    user_relationship = RelationshipRecord(
        subject_type="user",
        subject_id="u-2",
        relation="editor",
        object_type="document",
        object_id="doc-1",
    )

    access_cache = AccessCache()
    acl_cache = ACLCache()
    acl_repository = SimpleNamespace(find_matching_acl=lambda **kwargs: [acl_record])
    relationships = SimpleNamespace(
        list_for_object=lambda **kwargs: [relationship_row, user_relationship],
        list_for_subject=lambda **kwargs: [user_relationship],
    )

    indexer = AccessIndexer(
        acl_repository=acl_repository,
        acl_cache=acl_cache,
        access_index_cache=access_cache,
        relationships=relationships,
    )

    entries = indexer.build_resource_index(
        tenant_id=1,
        resource_type="document",
        resource_id="doc-1",
        action="read",
    )
    assert len(entries) == 2
    assert entries[0].acl_id == 7
    assert "relationship:viewer:document:doc-1" in entries[1].allowed_subjects
    assert "user:u-2" in entries[1].allowed_subjects
    assert acl_cache.set_calls
    assert access_cache.set_calls
    assert relationship_descriptor(relationship_row) == "relationship:viewer:document:doc-1"
    assert AccessSubject(subject_type="user", subject_id="u-1").to_descriptor() == "user:u-1"

    access_cache.cached = [cached_entry]
    assert indexer.build_resource_index(
        tenant_id=1,
        resource_type="document",
        resource_id="doc-1",
        action="read",
    ) == [cached_entry]

    access_cache.cached = None
    cache_key = (1, "document", "doc-1", "read")
    indexer._memo_set(cache_key, [cached_entry])  # noqa: SLF001
    refresh_calls: list[str] = []
    monkeypatch.setattr(
        indexer,
        "_schedule_background_refresh",
        lambda **kwargs: refresh_calls.append("scheduled"),
    )
    assert indexer.build_resource_index(
        tenant_id=1,
        resource_type="document",
        resource_id="doc-1",
        action="read",
    ) == [cached_entry]
    assert refresh_calls == ["scheduled"]

    monkeypatch.setattr("keynetra.services.access_indexer.time.time", lambda: 0.0)
    indexer._memo[cache_key] = (-1.0, [cached_entry])  # noqa: SLF001
    assert indexer._memo_get(cache_key) is None  # noqa: SLF001

    indexer.invalidate_resource(tenant_id=1, resource_type="document", resource_id="doc-1")
    assert acl_cache.invalidated == [(1, "document", "doc-1")]
    assert access_cache.invalidated == [(1, "document", "doc-1")]

    other_key = (1, "report", "r-1", "read")
    indexer._memo_set(other_key, [cached_entry])  # noqa: SLF001
    indexer.invalidate_tenant(tenant_id=1)
    assert access_cache.invalidated_tenants == [1]
    assert indexer._memo == {}  # noqa: SLF001

    descriptors = indexer.subject_descriptors(
        {
            "id": 1,
            "roles": ["admin"],
            "permissions": ["read"],
            "relations": [{"relation": "viewer", "object_type": "document", "object_id": "doc-1"}],
        }
    )
    assert descriptors == {
        "user:1",
        "role:admin",
        "permission:read",
        "relationship:viewer:document:doc-1",
    }
