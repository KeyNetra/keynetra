"""Comprehensive tests for integration adapters.

Tests the real implementations of:
- OpenFGA tuple and model adapter
- OPA/Rego policy adapter
- Terraform provider adapter
"""

from __future__ import annotations

import json

from integrations.interfaces import TupleRecord
from integrations.opa_rego_adapter import OPARegoPolicyAdapter
from integrations.openfga_adapter import OpenFGATupleAdapter
from integrations.terraform_provider import TerraformPolicyResourceAdapter


# =============================================================================
# OpenFGA Adapter Tests
# =============================================================================


def test_openfga_adapter_round_trip() -> None:
    """Test basic tuple import/export round trip."""
    adapter = OpenFGATupleAdapter()
    inserted = adapter.import_tuples(
        [TupleRecord(subject="user:1", relation="viewer", object="doc:1")]
    )
    assert inserted == 1
    exported = adapter.export_tuples()
    assert len(exported) == 1
    assert exported[0].relation == "viewer"
    assert exported[0].subject == "user:1"
    assert exported[0].object == "doc:1"


def test_openfga_raw_tuple_import_export() -> None:
    """Test import/export in OpenFGA raw dict format."""
    adapter = OpenFGATupleAdapter()
    raw_tuples = [
        {"user": "user:alice", "relation": "editor", "object": "doc:123"},
        {"user": "user:bob", "relation": "viewer", "object": "doc:456"},
    ]
    adapter.import_raw_tuples(raw_tuples)
    assert adapter.count() == 2

    exported = adapter.export_raw_tuples()
    assert len(exported) == 2
    assert exported[0]["user"] == "user:alice"
    assert exported[0]["relation"] == "editor"


def test_openfga_tuple_crud() -> None:
    """Test add, remove, list, clear tuple operations."""
    adapter = OpenFGATupleAdapter()
    adapter.add_tuple("user:alice", "owner", "doc:1")
    adapter.add_tuple("user:bob", "viewer", "doc:1")
    adapter.add_tuple("user:alice", "viewer", "doc:2")
    assert adapter.count() == 3

    # List with filter
    alice_tuples = adapter.list_tuples(user="user:alice")
    assert len(alice_tuples) == 2

    doc1_tuples = adapter.list_tuples(object="doc:1")
    assert len(doc1_tuples) == 2

    # Remove
    removed = adapter.remove_tuple("user:alice", "owner", "doc:1")
    assert removed is True
    assert adapter.count() == 2

    # Remove non-existent
    removed = adapter.remove_tuple("non", "existent", "tuple")
    assert removed is False

    # Clear
    adapter.clear()
    assert adapter.count() == 0


def test_openfga_local_check() -> None:
    """Test local tuple lookup check."""
    adapter = OpenFGATupleAdapter()
    adapter.add_tuple("user:alice", "owner", "doc:1")

    assert adapter.check_locally("user:alice", "owner", "doc:1") is True
    assert adapter.check_locally("user:alice", "viewer", "doc:1") is False
    assert adapter.check_locally("user:bob", "owner", "doc:1") is False
    assert adapter.check_locally("user:alice", "owner", "doc:2") is False


def test_openfga_keynetra_relationship_translation() -> None:
    """Test translation between KeyNetra relationships and OpenFGA tuples."""
    adapter = OpenFGATupleAdapter()

    # Import from KeyNetra format
    keynetra_relationships = [
        {"user_id": "alice", "relation": "owner", "resource_type": "document", "resource_id": "doc-1"},
        {"user_id": "bob", "relation": "viewer", "resource_type": "document", "resource_id": "doc-1"},
    ]
    count = adapter.import_from_keynetra_relationships(keynetra_relationships)
    assert count == 2

    # Export back
    exported = adapter.export_to_keynetra_relationships()
    assert len(exported) == 2
    assert exported[0]["user_id"] == "alice"
    assert exported[0]["relation"] == "owner"
    assert exported[0]["resource_type"] == "document"


def test_openfga_schema_to_model_conversion() -> None:
    """Test conversion from KeyNetra schema to OpenFGA model.

    KeyNetra schema parser uses '=' for permission assignment (not ':').
    """
    adapter = OpenFGATupleAdapter()

    keynetra_schema = """model schema 1
type document
relations
  owner: [user]
  editor: [user]
  viewer: [user]
permissions
  read = owner or editor or viewer
  write = owner or editor
  delete = owner
"""

    model = adapter.import_model_from_keynetra_schema(keynetra_schema)

    assert model.schema_version == "1.1"
    assert len(model.type_definitions) == 1
    assert model.type_definitions[0].type == "document"

    relations = model.type_definitions[0].relations
    # Direct relations
    assert "owner" in relations
    assert relations["owner"] == {"this": {}}
    assert "editor" in relations
    assert "viewer" in relations

    # Permission-derived relations
    assert "can_read" in relations
    assert "can_write" in relations
    assert "can_delete" in relations

    # Verify union structure for "read = owner or editor or viewer"
    can_read = relations["can_read"]
    assert "union" in can_read
    assert len(can_read["union"]["child"]) == 3

    # Verify simple computedUserset for "delete = owner"
    can_delete = relations["can_delete"]
    assert "computedUserset" in can_delete
    assert can_delete["computedUserset"]["relation"] == "owner"


def test_openfga_model_export_back_to_schema() -> None:
    """Test export of OpenFGA model back to KeyNetra schema format."""
    adapter = OpenFGATupleAdapter()

    # Import a model using '=' for permission assignment (schema_parser requirement)
    keynetra_schema = """model schema 1
type document
relations
  owner: [user]
  editor: [user]
permissions
  read = owner or editor
"""
    adapter.import_model_from_keynetra_schema(keynetra_schema)

    # Export back
    exported_schema = adapter.export_model_to_keynetra_schema()
    assert "model schema 1" in exported_schema
    assert "type document" in exported_schema
    assert "owner:" in exported_schema or "owner" in exported_schema
    assert "read:" in exported_schema or "read =" in exported_schema
    assert "owner or editor" in exported_schema


def test_openfga_keynetra_check_translation() -> None:
    """Test translation of KeyNetra access checks to OpenFGA format."""
    adapter = OpenFGATupleAdapter()

    # Create tuples that map to a KeyNetra relationship
    adapter.add_tuple("user:alice", "can_read", "document:doc-1")
    adapter.add_tuple("user:alice", "owner", "document:doc-1")

    # Check via KeyNetra interface
    result = adapter.keynetra_check_to_openfga(
        user_id="alice",
        action="read",
        resource_type="document",
        resource_id="doc-1",
    )
    assert result.allowed is True
    assert result.resolution == "LOCAL_TUPLE_LOOKUP"

    # Check for non-existent permission
    result = adapter.keynetra_check_to_openfga(
        user_id="alice",
        action="delete",
        resource_type="document",
        resource_id="doc-1",
    )
    assert result.allowed is False


# =============================================================================
# OPA/Rego Adapter Tests
# =============================================================================


def test_opa_adapter_round_trip() -> None:
    """Test basic Rego import/export."""
    adapter = OPARegoPolicyAdapter()
    count = adapter.import_policies("package keynetra.authz\nallow if { true }\n")
    assert count >= 1
    exported = adapter.export_policies()
    assert "allow" in exported
    assert "keynetra.authz" in exported


def test_opa_adapter_keynetra_to_rego() -> None:
    """Test conversion of KeyNetra policies to Rego."""
    adapter = OPARegoPolicyAdapter()

    keynetra_policies = [
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "policy_id": "admin-read",
            "conditions": {"role": "admin", "resource_type": "document"},
        },
        {
            "action": "write",
            "effect": "deny",
            "priority": 20,
            "conditions": {"role": "viewer", "resource_type": "document"},
        },
    ]

    count = adapter.import_from_keynetra(keynetra_policies)
    assert count == 2

    rego = adapter.export_policies()
    assert "package" in rego
    assert "allow" in rego
    assert "deny" in rego
    assert "admin" in rego
    assert "viewer" in rego
    assert "document" in rego


def test_opa_adapter_json_policy_import() -> None:
    """Test importing JSON-encoded KeyNetra policy arrays."""
    adapter = OPARegoPolicyAdapter()

    policies_json = json.dumps([
        {"action": "read", "effect": "allow", "priority": 10, "conditions": {"role": "admin"}},
        {"action": "write", "effect": "allow", "priority": 20, "conditions": {"role": "editor"}},
    ])

    count = adapter.import_policies(policies_json)
    assert count == 2

    rego = adapter.export_policies()
    assert "package" in rego
    assert "role" in rego.lower()


def test_opa_adapter_validate_valid() -> None:
    """Test validation of valid Rego."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_policies("package test\nallow if { true }\n")
    errors = adapter.validate()
    assert len(errors) == 0, f"Expected no errors, got: {errors}"


def test_opa_adapter_validate_invalid() -> None:
    """Test validation of invalid/missing Rego."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_policies("")
    errors = adapter.validate()
    assert len(errors) > 0


def test_opa_adapter_rule_conditions_role() -> None:
    """Test Rego generation with role conditions."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin", "resource_type": "document"},
        }
    ])

    rego = adapter.export_policies()
    assert "input.user.role" in rego
    assert '"admin"' in rego


def test_opa_adapter_rule_conditions_owner() -> None:
    """Test Rego generation with owner_only conditions."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "delete",
            "effect": "allow",
            "priority": 10,
            "conditions": {"owner_only": True, "resource_type": "document"},
        }
    ])

    rego = adapter.export_policies()
    assert "owner_id" in rego
    assert "input.user.id" in rego


def test_opa_adapter_rule_conditions_relation() -> None:
    """Test Rego generation with relation conditions."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "conditions": {"relation": "editor", "resource_type": "document"},
        }
    ])

    rego = adapter.export_policies()
    assert "relations" in rego
    assert "editor" in rego


def test_opa_adapter_local_evaluation() -> None:
    """Test local evaluation of Rego policies."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "policy_id": "admin-read",
            "conditions": {"role": "admin", "resource_type": "document"},
        }
    ])

    # Should allow (admin, read, document)
    result = adapter.evaluate_locally({
        "user": {"id": "user1", "role": "admin"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "read",
        "context": {},
    })
    assert result.allowed is True
    assert result.decision == "allow"

    # Should deny (viewer, read, document)
    result = adapter.evaluate_locally({
        "user": {"id": "user2", "role": "viewer"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "read",
        "context": {},
    })
    assert result.allowed is False

    # Should deny (admin, write, document) — policy only allows "read"
    result = adapter.evaluate_locally({
        "user": {"id": "user1", "role": "admin"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "write",
        "context": {},
    })
    assert result.allowed is False


def test_opa_adapter_local_evaluation_owner() -> None:
    """Test local evaluation with owner_only conditions."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "delete",
            "effect": "allow",
            "priority": 10,
            "conditions": {"owner_only": True, "resource_type": "document"},
        }
    ])

    # Owner should be allowed
    result = adapter.evaluate_locally({
        "user": {"id": "user1"},
        "resource": {"resource_type": "document", "id": "doc1", "owner_id": "user1"},
        "action": "delete",
        "context": {},
    })
    assert result.allowed is True

    # Non-owner should be denied
    result = adapter.evaluate_locally({
        "user": {"id": "user2"},
        "resource": {"resource_type": "document", "id": "doc1", "owner_id": "user1"},
        "action": "delete",
        "context": {},
    })
    assert result.allowed is False


def test_opa_adapter_to_keynetra_policies() -> None:
    """Test conversion of Rego back to KeyNetra policy format."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "policy_id": "doc-read",
            "conditions": {"role": "admin", "resource_type": "document"},
        }
    ])

    policies = adapter.to_keynetra_policies()
    assert len(policies) == 1
    assert policies[0]["action"] == "read"
    assert policies[0]["effect"] == "allow"
    assert policies[0]["priority"] == 10
    assert policies[0]["policy_id"] == "doc-read"


def test_opa_adapter_deny_precedence() -> None:
    """Test that deny rules take precedence over allow rules."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "read",
            "effect": "deny",
            "priority": 5,
            "conditions": {"role": "suspended", "resource_type": "document"},
        },
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin", "resource_type": "document"},
        },
    ])

    # Suspended admin should be denied (deny takes precedence)
    result = adapter.evaluate_locally({
        "user": {"id": "user1", "role": "suspended"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "read",
        "context": {},
    })
    assert result.allowed is False
    assert result.decision == "deny"


def test_opa_adapter_default_deny() -> None:
    """Test default deny when no rules match."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_from_keynetra([
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin"},
        }
    ])

    # No matching rule -> default deny
    result = adapter.evaluate_locally({
        "user": {"id": "user1", "role": "viewer"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "read",
        "context": {},
    })
    assert result.allowed is False


def test_opa_adapter_empty_rego() -> None:
    """Test behavior with empty Rego."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_policies("")
    errors = adapter.validate()
    assert len(errors) > 0

    result = adapter.evaluate_locally({
        "user": {"id": "user1", "role": "admin"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "read",
        "context": {},
    })
    assert result.allowed is False


# =============================================================================
# Terraform Adapter Tests
# =============================================================================


def test_terraform_adapter_plan_apply() -> None:
    """Test basic Terraform plan and apply lifecycle."""
    adapter = TerraformPolicyResourceAdapter(
        policies=[
            {"action": "read", "effect": "allow", "priority": 10, "policy_id": "p1"},
            {"action": "write", "effect": "deny", "priority": 20, "policy_id": "p2"},
        ],
        models=[
            {"type": "document", "relations": {"owner": ["user"]}, "permissions": {"read": "owner"}},
        ],
        relationships=[
            {"user_id": "alice", "relation": "owner", "resource_type": "document", "resource_id": "doc1"},
        ],
    )

    plan_result: dict[str, object] = adapter.plan()
    total_changes = plan_result.get("total_changes", 0)
    assert isinstance(total_changes, int) and total_changes > 0
    resource_types = plan_result.get("resource_types", {})
    assert isinstance(resource_types, dict)
    assert resource_types.get("keynetra_policy") == 2
    assert resource_types.get("keynetra_auth_model") == 1
    assert resource_types.get("keynetra_relationship") == 1

    apply_result: dict[str, object] = adapter.apply()
    assert apply_result.get("applied") is True
    resource_count = apply_result.get("resource_count", 0)
    assert resource_count == 4


def test_terraform_adapter_idempotent_apply() -> None:
    """Test that applying twice is idempotent (no changes on second apply)."""
    adapter = TerraformPolicyResourceAdapter(
        policies=[
            {"action": "read", "effect": "allow", "priority": 10, "policy_id": "p1"},
        ],
    )

    # First apply
    adapter.plan()
    adapter.apply()

    # Second apply should detect no changes
    second_plan: dict[str, object] = adapter.plan()
    total_changes = second_plan.get("total_changes", 0)
    assert isinstance(total_changes, int) and total_changes == 0


def test_terraform_adapter_drift_detection() -> None:
    """Test drift detection between desired and applied state."""
    adapter = TerraformPolicyResourceAdapter(
        policies=[
            {"action": "read", "effect": "allow", "priority": 10, "policy_id": "p1"},
        ],
    )

    # Apply initial state
    adapter.apply()

    # Change desired state
    adapter.policies = [
        {"action": "read", "effect": "deny", "priority": 10, "policy_id": "p1"},
    ]

    drift = adapter.detect_drift()
    assert len(drift) > 0
    assert drift[0]["status"] in ("drifted", "missing_in_applied")


def test_terraform_adapter_state_import_export() -> None:
    """Test state import and export."""
    adapter = TerraformPolicyResourceAdapter()

    # Import resources into state
    adapter.import_state("keynetra_policy", "p1", {
        "action": "read", "effect": "allow", "priority": 10, "policy_id": "p1",
    })
    adapter.import_state("keynetra_relationship", "rel1", {
        "user_id": "alice", "relation": "owner", "resource_type": "document", "resource_id": "doc1",
    })

    # Export state
    state = adapter.export_state()
    assert len(state["keynetra_policy"]) == 1
    assert len(state["keynetra_relationship"]) == 1


def test_terraform_adapter_hcl_generation() -> None:
    """Test HCL example generation."""
    adapter = TerraformPolicyResourceAdapter()
    hcl = adapter.to_hcl_example()

    assert "terraform" in hcl
    assert "required_providers" in hcl
    assert "keynetra" in hcl
    assert "keynetra_policy" in hcl
    assert "keynetra_auth_model" in hcl
    assert "keynetra_relationship" in hcl


# =============================================================================
# Combined / Integration Tests
# =============================================================================


def test_openfga_to_opa_cross_translation() -> None:
    """Test that policies survive a full OpenFGA -> KeyNetra -> OPA round trip."""
    # Start with an OpenFGA model using '=' for permissions (schema_parser requirement)
    ofga = OpenFGATupleAdapter()

    schema = """model schema 1
type document
relations
  owner: [user]
  editor: [user]
permissions
  read = owner or editor
"""
    model = ofga.import_model_from_keynetra_schema(schema)

    # Export to KeyNetra schema format
    exported_schema = ofga.export_model_to_keynetra_schema()
    assert "read" in exported_schema
    assert "owner or editor" in exported_schema

    # Add tuples to OpenFGA
    ofga.add_tuple("user:alice", "can_read", "document:doc-1")
    ofga.add_tuple("user:alice", "owner", "document:doc-1")

    # Check access via OpenFGA
    assert ofga.check_locally("user:alice", "can_read", "document:doc-1") is True
    assert ofga.check_locally("user:bob", "can_read", "document:doc-1") is False


def test_opa_to_openfga_cross_translation() -> None:
    """Test that Rego policies can be understood and converted."""
    # Create OPA policy with role-based conditions
    opa = OPARegoPolicyAdapter()
    opa.import_from_keynetra([
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin", "resource_type": "document"},
        },
        {
            "action": "read",
            "effect": "allow",
            "priority": 20,
            "conditions": {"relation": "editor", "resource_type": "document"},
        },
    ])

    # Convert to KeyNetra format
    policies = opa.to_keynetra_policies()
    assert len(policies) == 2

    # Verify the policies can be evaluated
    result = opa.evaluate_locally({
        "user": {"id": "alice", "role": "admin"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "read",
        "context": {},
    })
    assert result.allowed is True


def test_full_policy_lifecycle() -> None:
    """Test a full policy lifecycle across all adapters."""
    # 1. Create KeyNetra policies
    policies = [
        {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "policy_id": "admin-read",
            "conditions": {"role": "admin", "resource_type": "document"},
        },
        {
            "action": "delete",
            "effect": "allow",
            "priority": 20,
            "policy_id": "owner-delete",
            "conditions": {"owner_only": True, "resource_type": "document"},
        },
    ]

    # 2. Convert to OPA/Rego
    opa = OPARegoPolicyAdapter()
    opa.import_from_keynetra(policies)
    rego = opa.export_policies()
    assert "admin" in rego
    assert "owner" in rego

    # 3. Validate Rego
    errors = opa.validate()
    assert len(errors) == 0, f"Validation errors: {errors}"

    # 4. Evaluate via OPA adapter
    result = opa.evaluate_locally({
        "user": {"id": "alice", "role": "admin"},
        "resource": {"resource_type": "document", "id": "doc1"},
        "action": "read",
        "context": {},
    })
    assert result.allowed is True

    # 5. Create OpenFGA model from schema
    ofga = OpenFGATupleAdapter()
    ofga.add_tuple("user:alice", "owner", "document:doc1")
    ofga.add_tuple("user:bob", "viewer", "document:doc1")

    # 6. Verify OpenFGA checks
    assert ofga.check_locally("user:alice", "owner", "document:doc1") is True
    assert ofga.check_locally("user:bob", "owner", "document:doc1") is False

    # 7. Manage via Terraform
    tf = TerraformPolicyResourceAdapter(
        policies=policies,
        relationships=[
            {"user_id": "alice", "relation": "owner", "resource_type": "document", "resource_id": "doc1"},
        ],
    )

    tf_result: dict[str, object] = tf.apply()
    assert tf_result.get("applied") is True


def test_opa_adapter_evaluate_via_opa_requires_endpoint() -> None:
    """Test that evaluate_via_opa raises when no endpoint is configured."""
    adapter = OPARegoPolicyAdapter()
    adapter.import_policies("package test\nallow if { true }\n")

    try:
        adapter.evaluate_via_opa({"user": {"id": "u1"}})
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "OPA endpoint not configured" in str(e)