"""Terraform provider adapter for KeyNetra policy resources.

Enables Terraform-based management of KeyNetra policies, authorization models,
and relationship tuples using OpenTofu/Terraform HCL. Supports plan/apply lifecycle,
state import, and drift detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from integrations.interfaces import TerraformResourceAdapter


@dataclass(frozen=True)
class TerraformResourceChange:
    """A single planned resource change."""
    action: Literal["create", "update", "delete", "no-op"]
    resource_type: str
    resource_id: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None


@dataclass
class TerraformPolicyResourceAdapter(TerraformResourceAdapter):
    """Terraform adapter for KeyNetra policy resources.

    Manages KeyNetra policies as Terraform resources with HCL-compatible
    schema support, state tracking, and apply/plan lifecycle.

    Resource types supported:
    - keynetra_policy: An authorization policy rule
    - keynetra_auth_model: An authorization schema model
    - keynetra_relationship: A relationship tuple
    """

    policies: list[dict[str, Any]] = field(default_factory=list)
    models: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)

    # Internal state tracking
    _applied_policies: list[dict[str, Any]] = field(default_factory=list)
    _applied_models: list[dict[str, Any]] = field(default_factory=list)
    _applied_relationships: list[dict[str, Any]] = field(default_factory=list)
    _changes: list[TerraformResourceChange] = field(default_factory=list)

    def plan(self) -> dict[str, object]:
        """Generate a plan comparing desired vs applied state.

        Returns a dict with planned changes per resource type.
        """
        changes: list[TerraformResourceChange] = []

        # Diff policies
        for desired in self.policies:
            policy_id = desired.get("policy_id", desired.get("action", "unknown"))
            existing = self._find_matching_policy(desired)
            if existing is None:
                changes.append(TerraformResourceChange(
                    action="create",
                    resource_type="keynetra_policy",
                    resource_id=policy_id,
                    before=None,
                    after=desired,
                ))
            elif existing != desired:
                changes.append(TerraformResourceChange(
                    action="update",
                    resource_type="keynetra_policy",
                    resource_id=policy_id,
                    before=existing,
                    after=desired,
                ))

        # Detect deletions (in applied but not in desired)
        desired_ids = {
            p.get("policy_id", p.get("action", f"p{i}"))
            for i, p in enumerate(self.policies)
        }
        for existing in self._applied_policies:
            existing_id = existing.get("policy_id", existing.get("action", "unknown"))
            if existing_id not in desired_ids:
                changes.append(TerraformResourceChange(
                    action="delete",
                    resource_type="keynetra_policy",
                    resource_id=existing_id,
                    before=existing,
                    after=None,
                ))

        # Diff models
        for i, desired_model in enumerate(self.models):
            model_id = desired_model.get("type", f"model_{i}")
            existing = self._find_matching_model(desired_model)
            if existing is None:
                changes.append(TerraformResourceChange(
                    action="create",
                    resource_type="keynetra_auth_model",
                    resource_id=model_id,
                    before=None,
                    after=desired_model,
                ))
            elif existing != desired_model:
                changes.append(TerraformResourceChange(
                    action="update",
                    resource_type="keynetra_auth_model",
                    resource_id=model_id,
                    before=existing,
                    after=desired_model,
                ))

        # Diff relationships
        for desired_rel in self.relationships:
            rel_id = f"{desired_rel.get('user_id', '?')}:{desired_rel.get('relation', '?')}:{desired_rel.get('resource_id', '?')}"
            existing = self._find_matching_relationship(desired_rel)
            if existing is None:
                changes.append(TerraformResourceChange(
                    action="create",
                    resource_type="keynetra_relationship",
                    resource_id=rel_id,
                    before=None,
                    after=desired_rel,
                ))

        self._changes = changes

        return {
            "total_changes": len(changes),
            "resource_types": {
                "keynetra_policy": len([c for c in changes if c.resource_type == "keynetra_policy"]),
                "keynetra_auth_model": len([c for c in changes if c.resource_type == "keynetra_auth_model"]),
                "keynetra_relationship": len([c for c in changes if c.resource_type == "keynetra_relationship"]),
            },
            "changes": [
                {
                    "action": c.action,
                    "resource_type": c.resource_type,
                    "resource_id": c.resource_id,
                }
                for c in changes
            ],
        }

    def apply(self) -> dict[str, object]:
        """Apply the planned changes.

        Persists the desired state as the new applied state.
        Returns the results of the apply operation.
        """
        if not self._changes:
            # Run plan first if not already planned
            self.plan()

        applied_policies = list(self.policies)
        applied_models = list(self.models)
        applied_relationships = list(self.relationships)

        self._applied_policies = applied_policies
        self._applied_models = applied_models
        self._applied_relationships = applied_relationships

        result = {
            "applied": True,
            "resource_count": len(applied_policies) + len(applied_models) + len(applied_relationships),
            "changes_applied": len(self._changes),
            "resources": {
                "policies": len(applied_policies),
                "models": len(applied_models),
                "relationships": len(applied_relationships),
            },
        }

        self._changes = []
        return result

    def import_state(self, resource_type: str, resource_id: str, data: dict[str, Any]) -> None:
        """Import an existing resource into Terraform state.

        Args:
            resource_type: The resource type (e.g., "keynetra_policy")
            resource_id: The resource identifier
            data: The resource attributes
        """
        if resource_type == "keynetra_policy":
            self._applied_policies.append(data)
            # Also add to desired if not present
            if not self._find_matching_policy(data):
                self.policies.append(data)
        elif resource_type == "keynetra_auth_model":
            self._applied_models.append(data)
            if not self._find_matching_model(data):
                self.models.append(data)
        elif resource_type == "keynetra_relationship":
            self._applied_relationships.append(data)
            if not self._find_matching_relationship(data):
                self.relationships.append(data)

    def export_state(self) -> dict[str, list[dict[str, Any]]]:
        """Export the current applied state for Terraform state file generation."""
        return {
            "keynetra_policy": list(self._applied_policies),
            "keynetra_auth_model": list(self._applied_models),
            "keynetra_relationship": list(self._applied_relationships),
        }

    def detect_drift(self) -> list[dict[str, Any]]:
        """Detect drift between desired and applied state.

        Returns a list of drift records identifying resources that have diverged.
        """
        drift: list[dict[str, Any]] = []

        # Check for drift in policies
        for desired in self.policies:
            existing = self._find_matching_policy(desired)
            if existing is None:
                drift.append({
                    "type": "keynetra_policy",
                    "id": desired.get("policy_id", desired.get("action", "unknown")),
                    "status": "missing_in_applied",
                    "desired": desired,
                })
            elif existing != desired:
                drift.append({
                    "type": "keynetra_policy",
                    "id": desired.get("policy_id", desired.get("action", "unknown")),
                    "status": "drifted",
                    "desired": desired,
                    "current": existing,
                    "differences": self._compute_diff(existing, desired),
                })

        return drift

    def to_hcl_example(self) -> str:
        """Generate example HCL for Terraform configuration."""
        lines = [
            '# Example Terraform configuration for KeyNetra',
            'terraform {',
            '  required_providers {',
            '    keynetra = {',
            '      source  = "keynetra/terraform-provider-keynetra"',
            '      version = "~> 0.1.0"',
            '    }',
            '  }',
            '}',
            '',
            'provider "keynetra" {',
            '  endpoint = "http://localhost:8080"',
            '  api_key  = var.keynetra_api_key',
            '}',
            '',
            '# Policy resources',
            'resource "keynetra_policy" "admin_read" {',
            '  action   = "read"',
            '  effect   = "allow"',
            '  priority = 10',
            '  policy_id = "document-read-admin"',
            '  conditions = jsonencode({',
            '    role = "admin"',
            '    resource_type = "document"',
            '  })',
            '}',
            '',
            '# Authorization model',
            'resource "keynetra_auth_model" "document_model" {',
            '  type = "document"',
            '  relations = jsonencode({',
            '    owner = ["user"],',
            '    editor = ["user"],',
            '    viewer = ["user"],',
            '  })',
            '  permissions = jsonencode({',
            '    read = "owner or editor or viewer",',
            '    write = "owner or editor",',
            '    delete = "owner",',
            '  })',
            '}',
            '',
            '# Relationship tuples',
            'resource "keynetra_relationship" "alice_owner_doc1" {',
            '  user_id       = "user_123"',
            '  relation      = "owner"',
            '  resource_type = "document"',
            '  resource_id   = "document_456"',
            '}',
        ]
        return "\n".join(lines)

    def _find_matching_policy(self, desired: dict[str, Any]) -> dict[str, Any] | None:
        """Find a matching policy in applied state."""
        for existing in self._applied_policies:
            desired_id = desired.get("policy_id")
            existing_id = existing.get("policy_id")
            if desired_id and existing_id and desired_id == existing_id:
                return existing
            if (desired.get("action") == existing.get("action")
                    and desired.get("conditions", {}).get("role") == existing.get("conditions", {}).get("role")):
                return existing
        return None

    def _find_matching_model(self, desired: dict[str, Any]) -> dict[str, Any] | None:
        """Find a matching model in applied state."""
        for existing in self._applied_models:
            if desired.get("type") == existing.get("type"):
                return existing
        return None

    def _find_matching_relationship(self, desired: dict[str, Any]) -> dict[str, Any] | None:
        """Find a matching relationship in applied state."""
        for existing in self._applied_relationships:
            if (desired.get("user_id") == existing.get("user_id")
                    and desired.get("relation") == existing.get("relation")
                    and desired.get("resource_id") == existing.get("resource_id")):
                return existing
        return None

    def _compute_diff(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        """Compute a diff between two resource states."""
        diffs: dict[str, Any] = {}
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            if before_val != after_val:
                diffs[key] = {"before": before_val, "after": after_val}
        return diffs

    def __repr__(self) -> str:
        return (
            f"TerraformPolicyResourceAdapter("
            f"policies={len(self.policies)}, "
            f"models={len(self.models)}, "
            f"relationships={len(self.relationships)})"
        )