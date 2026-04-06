from __future__ import annotations

from integrations.interfaces import TupleRecord
from integrations.opa_rego_adapter import OPARegoPolicyAdapter
from integrations.openfga_adapter import InMemoryOpenFGATupleAdapter
from integrations.terraform_provider import TerraformPolicyResourceAdapter


def test_openfga_adapter_round_trip() -> None:
    adapter = InMemoryOpenFGATupleAdapter()
    inserted = adapter.import_tuples(
        [TupleRecord(subject="user:1", relation="viewer", object="doc:1")]
    )
    assert inserted == 1
    exported = adapter.export_tuples()
    assert len(exported) == 1
    assert exported[0].relation == "viewer"


def test_opa_adapter_round_trip() -> None:
    adapter = OPARegoPolicyAdapter()
    count = adapter.import_policies("package keynetra\nallow { true }\n")
    assert count >= 1
    assert "allow" in adapter.export_policies()


def test_terraform_adapter_plan_apply() -> None:
    adapter = TerraformPolicyResourceAdapter(policy_count=3)
    assert adapter.plan()["changes"] == 3
    assert adapter.apply()["applied"] is True
