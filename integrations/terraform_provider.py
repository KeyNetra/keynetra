from __future__ import annotations

from dataclasses import dataclass

from integrations.interfaces import TerraformResourceAdapter


@dataclass
class TerraformPolicyResourceAdapter(TerraformResourceAdapter):
    """Placeholder adapter boundary for Terraform-managed policy resources."""

    policy_count: int = 0

    def plan(self) -> dict[str, object]:
        return {"changes": self.policy_count, "resource": "keynetra_policy"}

    def apply(self) -> dict[str, object]:
        return {"applied": True, "resource_count": self.policy_count}
