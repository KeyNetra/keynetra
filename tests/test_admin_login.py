from __future__ import annotations

from jose import jwt
from typer.testing import CliRunner

from keynetra.cli import app
from keynetra.config.settings import reset_settings_cache
from keynetra.main import create_app


def test_admin_login_with_username_password_issues_admin_jwt(monkeypatch) -> None:
    monkeypatch.setenv("KEYNETRA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("KEYNETRA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("KEYNETRA_JWT_SECRET", "jwt-secret")
    monkeypatch.setenv("KEYNETRA_JWT_ALGORITHM", "HS256")
    reset_settings_cache()

    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post("/admin/login", json={"username": "admin", "password": "secret"})
    assert response.status_code == 200
    payload = response.json()["data"]
    token = payload["access_token"]
    claims = jwt.decode(token, "jwt-secret", algorithms=["HS256"])
    assert claims["role"] == "admin"
    assert claims["tenant_roles"]["default"] == "admin"


def test_admin_login_rejects_invalid_credentials(monkeypatch) -> None:
    monkeypatch.setenv("KEYNETRA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("KEYNETRA_ADMIN_PASSWORD", "secret")
    reset_settings_cache()

    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post("/admin/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_cli_admin_login_command_calls_login_endpoint(monkeypatch) -> None:
    called: dict[str, object] = {}

    class _Response:
        text = '{"data":{"access_token":"abc"}}'

        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, json: dict[str, str], timeout: float, headers: dict[str, str]):
        called["url"] = url
        called["json"] = json
        called["timeout"] = timeout
        called["headers"] = headers
        return _Response()

    monkeypatch.setattr("keynetra.cli.httpx.post", fake_post)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["admin-login", "--username", "admin", "--password", "secret", "--url", "http://localhost:8000/admin/login"],
    )
    assert result.exit_code == 0
    assert called["json"] == {"username": "admin", "password": "secret"}
