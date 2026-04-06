from __future__ import annotations

import base64
import json

import pytest

from keynetra.api.errors import ApiError
from keynetra.api.pagination import decode_cursor
from keynetra.config import redis_client
from keynetra.config.tenancy import get_tenant_key


def test_get_tenant_key_returns_default() -> None:
    assert get_tenant_key() == "default"


def test_decode_cursor_rejects_invalid_base64() -> None:
    with pytest.raises(ApiError) as exc:
        decode_cursor("not-a-valid-cursor")
    assert exc.value.message == "invalid cursor"


def test_decode_cursor_rejects_non_object_payload() -> None:
    raw = json.dumps(["not", "an", "object"]).encode("utf-8")
    cursor = base64.urlsafe_b64encode(raw).decode("ascii")
    with pytest.raises(ApiError) as exc:
        decode_cursor(cursor)
    assert exc.value.message == "invalid cursor"


def test_get_redis_returns_client_when_configured(monkeypatch) -> None:
    class _Settings:
        redis_url = "redis://localhost:6379/0"

    class _Redis:
        class Redis:
            @staticmethod
            def from_url(url: str, decode_responses: bool = True):
                return {"url": url, "decode_responses": decode_responses}

    redis_client.get_redis.cache_clear()
    monkeypatch.setattr(redis_client, "get_settings", lambda: _Settings())
    monkeypatch.setattr(redis_client, "redis", _Redis)
    assert redis_client.get_redis()["url"] == "redis://localhost:6379/0"
