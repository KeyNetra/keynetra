from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("typer")
from typer.testing import CliRunner

from keynetra.cli import app
from keynetra.config.settings import get_settings, reset_settings_cache
from keynetra.services.policy_testing import parse_policy_test_suite, validate_policy_test_suite


def test_parse_policy_test_suite_supports_embedded_policy_dsl() -> None:
    suite = parse_policy_test_suite("""
policies:
  - allow:
      action: read
      priority: 10
      policy_key: read-admin
      when:
        role: admin
tests:
  - name: admin_allowed
    input:
      user:
        role: admin
      action: read
      resource: {}
    expect: allow
""")

    assert len(suite.policies) == 1
    assert suite.policies[0]["policy_id"] == "read-admin"
    assert suite.tests[0].authorization_input.action == "read"


def test_validate_policy_test_suite_runs_expected_decisions() -> None:
    results = validate_policy_test_suite("""
policies:
  - action: read
    effect: allow
    policy_id: read-admin
    conditions:
      role: admin
tests:
  - name: admin_allowed
    input:
      user:
        role: admin
      action: read
      resource: {}
    expect: allow
  - name: user_denied
    input:
      user:
        role: user
      action: read
      resource: {}
    expect: deny
""")

    assert [result.passed for result in results] == [True, True]
    assert results[0].policy_id == "read-admin"


def test_cli_test_policy_succeeds_for_example_file() -> None:
    runner = CliRunner()
    fixture = Path(__file__).resolve().parents[1] / "examples" / "policy_tests.yaml"

    result = runner.invoke(app, ["test-policy", str(fixture)])

    assert result.exit_code == 0
    assert "[PASS]" in result.output


def test_cli_test_policy_fails_when_expectation_is_wrong(tmp_path: Path) -> None:
    runner = CliRunner()
    fixture = tmp_path / "bad-policy.yaml"
    fixture.write_text(
        """
policies:
  - action: read
    effect: deny
tests:
  - name: should_fail
    input:
      user: {}
      action: read
      resource: {}
    expect: allow
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["test-policy", str(fixture)])

    assert result.exit_code == 1
    assert "[FAIL] should_fail" in result.output


def test_cli_seed_data_is_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    database_url = f"sqlite+pysqlite:///{tmp_path / 'seed.db'}"

    import os

    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    reset_settings_cache()
    get_settings.cache_clear()

    first = runner.invoke(app, ["seed-data"])
    second = runner.invoke(app, ["seed-data"])

    assert first.exit_code == 0
    assert '"created_tenant": true' in first.output.lower()
    assert second.exit_code == 0
    assert '"created_tenant": false' in second.output.lower()
