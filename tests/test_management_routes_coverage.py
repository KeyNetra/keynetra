from __future__ import annotations

import os

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _client(database_url: str) -> TestClient:
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
    )
    os.environ.pop("KEYNETRA_REDIS_URL", None)
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def test_permissions_roles_relationships_and_policies_management_paths(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'mgmt.db'}")
    headers = {"X-API-Key": "testkey"}

    # Permissions CRUD + validation/error branches.
    bad_limit = client.get("/permissions?limit=0", headers=headers)
    assert bad_limit.status_code == 422

    created_permission = client.post("/permissions", json={"action": "deploy"}, headers=headers)
    assert created_permission.status_code == 201
    permission_id = created_permission.json()["data"]["id"]

    duplicate_permission = client.post("/permissions", json={"action": "deploy"}, headers=headers)
    assert duplicate_permission.status_code == 409

    missing_permission_update = client.put(
        "/permissions/9999",
        json={"action": "deploy_v2"},
        headers=headers,
    )
    assert missing_permission_update.status_code == 404

    updated_permission = client.put(
        f"/permissions/{permission_id}",
        json={"action": "deploy_v2"},
        headers=headers,
    )
    assert updated_permission.status_code == 200
    assert updated_permission.json()["data"]["action"] == "deploy_v2"

    # Roles CRUD + permission assignment paths.
    created_role = client.post("/roles", json={"name": "operators"}, headers=headers)
    assert created_role.status_code == 201
    role_id = created_role.json()["data"]["id"]

    duplicate_role = client.post("/roles", json={"name": "operators"}, headers=headers)
    assert duplicate_role.status_code == 409

    missing_role_update = client.put("/roles/9999", json={"name": "ops"}, headers=headers)
    assert missing_role_update.status_code == 404

    updated_role = client.put(f"/roles/{role_id}", json={"name": "ops"}, headers=headers)
    assert updated_role.status_code == 200
    assert updated_role.json()["data"]["name"] == "ops"

    add_permission = client.post(f"/roles/{role_id}/permissions/{permission_id}", headers=headers)
    assert add_permission.status_code == 201

    role_permissions = client.get(f"/roles/{role_id}/permissions", headers=headers)
    assert role_permissions.status_code == 200
    assert role_permissions.json()["data"][0]["id"] == permission_id

    permission_roles = client.get(f"/permissions/{permission_id}/roles", headers=headers)
    assert permission_roles.status_code == 200
    assert permission_roles.json()["data"][0]["id"] == role_id

    remove_permission = client.delete(
        f"/roles/{role_id}/permissions/{permission_id}", headers=headers
    )
    assert remove_permission.status_code == 200

    deleted_role = client.delete(f"/roles/{role_id}", headers=headers)
    assert deleted_role.status_code == 200

    delete_missing_role = client.delete("/roles/9999", headers=headers)
    assert delete_missing_role.status_code == 404

    deleted_permission = client.delete(f"/permissions/{permission_id}", headers=headers)
    assert deleted_permission.status_code == 200

    delete_missing_permission = client.delete("/permissions/9999", headers=headers)
    assert delete_missing_permission.status_code == 404

    # Relationships list/create/conflict + validation branch.
    bad_relationship_limit = client.get(
        "/relationships?subject_type=user&subject_id=u1&limit=0",
        headers=headers,
    )
    assert bad_relationship_limit.status_code == 422

    relationship_payload = {
        "subject_type": "user",
        "subject_id": "u1",
        "relation": "owner",
        "object_type": "document",
        "object_id": "doc-1",
    }
    created_relationship = client.post("/relationships", json=relationship_payload, headers=headers)
    assert created_relationship.status_code == 201

    duplicate_relationship = client.post(
        "/relationships", json=relationship_payload, headers=headers
    )
    assert duplicate_relationship.status_code == 409

    listed_relationships = client.get(
        "/relationships?subject_type=user&subject_id=u1&limit=1",
        headers=headers,
    )
    assert listed_relationships.status_code == 200
    assert listed_relationships.json()["data"][0]["object_id"] == "doc-1"

    # Policies CRUD + validation/error branches.
    bad_policy_limit = client.get("/policies?limit=0", headers=headers)
    assert bad_policy_limit.status_code == 422

    created_policy = client.post(
        "/policies",
        json={
            "action": "read_document",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin", "policy_key": "read-admin"},
        },
        headers=headers,
    )
    assert created_policy.status_code == 201

    updated_policy = client.put(
        "/policies/read-admin",
        json={"action": "read_document", "effect": "deny", "priority": 5, "conditions": {}},
        headers=headers,
    )
    assert updated_policy.status_code == 200
    assert updated_policy.json()["data"]["effect"] == "deny"

    bad_dsl = client.post("/policies/dsl", json={"dsl": "invalid"}, headers=headers)
    assert bad_dsl.status_code == 422

    missing_rollback = client.post("/policies/read-admin/rollback/999", headers=headers)
    assert missing_rollback.status_code == 404

    deleted_policy = client.delete("/policies/read-admin", headers=headers)
    assert deleted_policy.status_code == 200
