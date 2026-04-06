from __future__ import annotations

import json
import os

from typer.testing import CliRunner

from keynetra.cli import app
from keynetra.config.settings import Settings
from keynetra.services.authorization import AuthorizationService
from keynetra.version import __version__


class _BrokenTenantRepo:
    def get_or_create(self, tenant_key: str):
        raise RuntimeError("tenant store unavailable")


class _NoopUserRepo:
    def get_user_context(self, user_id: int):
        return None


class _NoopRelationshipRepo:
    def list_for_subject(self, *, tenant_id: int, subject_type: str, subject_id: str):
        return []


class _NoopAuditRepo:
    def write(self, **kwargs):
        return None


class _NoopCache:
    def get(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def invalidate(self, *args, **kwargs):
        return None

    def make_key(self, **kwargs):
        return "cache-key"

    def bump_namespace(self, tenant_key: str):
        return 1


class _NoopPolicyRepo:
    def list_current_policies(self, *, tenant_id: int):
        return []


def _service(settings: Settings) -> AuthorizationService:
    return AuthorizationService(
        settings=settings,
        tenants=_BrokenTenantRepo(),
        policies=_NoopPolicyRepo(),
        users=_NoopUserRepo(),
        relationships=_NoopRelationshipRepo(),
        audit=_NoopAuditRepo(),
        policy_cache=_NoopCache(),
        relationship_cache=_NoopCache(),
        decision_cache=_NoopCache(),
    )


def test_resilience_fail_closed_denies_on_backend_failure() -> None:
    result = _service(
        Settings(resilience_mode="fail_closed", resilience_fallback_behavior="static")
    ).authorize(
        tenant_key="tenant-a",
        principal={"type": "test", "id": "p1"},
        user={"id": "u1"},
        action="read",
        resource={"id": "r1"},
        context={},
        audit=False,
    )

    assert result.decision.allowed is False
    assert result.decision.decision == "deny"


def test_resilience_fail_open_allows_on_backend_failure() -> None:
    result = _service(
        Settings(resilience_mode="fail_open", resilience_fallback_behavior="static")
    ).authorize(
        tenant_key="tenant-a",
        principal={"type": "test", "id": "p1"},
        user={"id": "u1"},
        action="read",
        resource={"id": "r1"},
        context={},
        audit=False,
    )

    assert result.decision.allowed is True
    assert result.decision.decision == "allow"


def test_resilience_default_policy_eval_uses_configured_policies() -> None:
    settings = Settings(
        resilience_mode="fail_closed",
        resilience_fallback_behavior="default_policy_eval",
        policies_json=json.dumps(
            [{"action": "read", "effect": "allow", "priority": 1, "conditions": {}}]
        ),
    )
    result = _service(settings).authorize(
        tenant_key="tenant-a",
        principal={"type": "test", "id": "p1"},
        user={"id": "u1"},
        action="read",
        resource={"id": "r1"},
        context={},
        audit=False,
    )

    assert result.decision.allowed is True
    assert any(step.step == "resilience_fallback" for step in result.decision.explain_trace)


def test_cli_explain_prints_decision_and_trace(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    runner = CliRunner()

    result = runner.invoke(app, ["explain", "--user", "u1", "--resource", "r1", "--action", "read"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "decision" in payload
    assert "explain_trace" in payload


def test_cli_version_prints_package_version() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_cli_help_cli_prints_examples() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["help-cli"])
    assert result.exit_code == 0
    assert "keynetra serve --config examples/keynetra.yaml" in result.stdout
    assert "keynetra compile-policies --config examples/keynetra.yaml" in result.stdout
