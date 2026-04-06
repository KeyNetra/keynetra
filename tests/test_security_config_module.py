from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from keynetra.config.security import _matches_api_key, _scopes_are_defined, get_principal


class DummyRequest(SimpleNamespace):
    def __init__(self, *, headers=None, client=None, state=None, method="GET", url=None):
        super().__init__()
        self.headers = headers or {}
        self.client = client
        self.method = method
        self.state = state or SimpleNamespace()
        self.url = SimpleNamespace(path=url or "/")


class DummySettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self._api_key_hashes = {"key-hash"}
        self.jwks_cache_ttl_seconds = 60
        self.jwks_backoff_max_seconds = 60
        self.jwt_secret = kwargs.get("jwt_secret", "secret")
        self.jwt_algorithm = kwargs.get("jwt_algorithm", "HS256")
        self.oidc_jwks_url = kwargs.get("oidc_jwks_url")
        self.oidc_audience = kwargs.get("oidc_audience")
        self.oidc_issuer = kwargs.get("oidc_issuer")
        self._development = kwargs.get("development", False)

    def parsed_api_key_hashes(self) -> set[str]:
        return self._api_key_hashes

    def parsed_api_key_scopes(self) -> dict[str, dict[str, object]]:
        return {list(self._api_key_hashes)[0]: {"role": "admin"}}

    def is_development(self) -> bool:
        return self._development


def test_matches_api_key_returns_true_for_valid_candidate():
    stored = hashlib.sha256(b"secret").hexdigest()
    assert _matches_api_key("secret", {stored})


def test_matches_api_key_returns_false_for_invalid_candidate():
    stored = hashlib.sha256(b"secret").hexdigest()
    assert not _matches_api_key("bad", {stored})


def test_scopes_defined_with_role_and_permission():
    assert _scopes_are_defined({"role": "admin"})
    assert _scopes_are_defined({"permissions": ["read"]})


def test_scopes_undefined_without_role_or_permissions():
    assert not _scopes_are_defined({"role": ""})
    assert not _scopes_are_defined({"permissions": []})


def test_get_principal_raises_without_credentials(monkeypatch):
    request = DummyRequest()
    settings = DummySettings()
    monkeypatch.setattr("keynetra.config.security.get_settings", lambda: settings)
    with pytest.raises(HTTPException):
        get_principal(request, settings=settings, authorization=None, x_api_key=None)


def test_get_principal_returns_jwt_structure(monkeypatch):
    request = DummyRequest()
    token = SimpleNamespace(scheme="bearer", credentials="token")
    settings = DummySettings(jwt_secret="secret", jwt_algorithm="HS256")
    monkeypatch.setattr("keynetra.config.security.get_settings", lambda: settings)
    monkeypatch.setattr(
        "keynetra.config.security.jwt.decode",
        lambda token, key, algorithms: {"sub": "user:1"},
    )
    principal = get_principal(
        request,
        settings=settings,
        authorization=token,
        x_api_key=None,
    )
    assert principal["type"] == "jwt"
    assert principal["id"] == "user:1"
