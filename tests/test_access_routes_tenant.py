from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import Request

from keynetra.api.routes.access import _resolve_tenant_key
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.config.tenancy import DEFAULT_TENANT_KEY, TENANT_HEADER_NAME


class DummyServices(SimpleNamespace):
    pass


def request_with_header(value: str | None) -> Request:
    return SimpleNamespace(
        headers={TENANT_HEADER_NAME: value} if value else {},
        state=SimpleNamespace(),
    )


def principal_with_tenant(tenant: str | None):
    if not tenant:
        return {}
    return {"type": "jwt", "claims": {"tenant": tenant}}


def test_resolve_tenant_from_header():
    request = request_with_header("acme")
    principal = principal_with_tenant(None)
    services = DummyServices(settings=SimpleNamespace(strict_tenancy=False, is_development=lambda: False))
    assert _resolve_tenant_key(request=request, principal=principal, services=services) == "acme"


def test_resolve_tenant_falls_back_to_principal():
    request = request_with_header(None)
    principal = principal_with_tenant("tenant-x")
    services = DummyServices(settings=SimpleNamespace(strict_tenancy=False, is_development=lambda: False))
    assert _resolve_tenant_key(request=request, principal=principal, services=services) == "tenant-x"


def test_resolve_tenant_development_default():
    request = request_with_header(None)
    principal = {}
    services = DummyServices(settings=SimpleNamespace(strict_tenancy=False, is_development=lambda: True))
    assert _resolve_tenant_key(request=request, principal=principal, services=services) == DEFAULT_TENANT_KEY


def test_resolve_tenant_strict_without_tenant_raises():
    request = request_with_header(None)
    principal = {}
    settings = SimpleNamespace(strict_tenancy=True, is_development=lambda: False)
    services = DummyServices(settings=settings)
    with pytest.raises(ApiError) as exc:
        _resolve_tenant_key(request=request, principal=principal, services=services)
    assert exc.value.code == ApiErrorCode.VALIDATION_ERROR
