from __future__ import annotations

import asyncio
import os
import time

import httpx
import pytest

from keynetra.api.routes.access import _legacy_service_override
from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.storage.session import create_session_factory, initialize_database
from keynetra.main import create_app


class _SlowSyncAuthorizationService:
    def authorize(self, **kwargs):
        time.sleep(0.1)

        class _Decision:
            allowed = True
            decision = "allow"
            matched_policies = ()
            reason = "ok"
            policy_id = None
            explain_trace = ()

        class _Result:
            decision = _Decision()
            cached = False
            revision = 1

        return _Result()


@pytest.mark.anyio
async def test_async_access_route_offloads_sync_authorization(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'async-access.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"acme","role":"admin","permissions":["*"]}}'
    )
    os.environ["KEYNETRA_ASYNC_AUTHORIZATION_ENABLED"] = "false"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1000"
    reset_settings_cache()
    initialize_database(database_url)
    session = create_session_factory(database_url)()
    try:
        SqlTenantRepository(session).create("acme")
    finally:
        session.close()

    app = create_app()
    app.dependency_overrides[_legacy_service_override] = lambda: _SlowSyncAuthorizationService()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = time.perf_counter()
        responses = await asyncio.gather(
            *[
                client.post(
                    "/check-access",
                    json={
                        "user": {"id": "u1"},
                        "action": "read",
                        "resource": {"id": f"doc-{index}"},
                        "context": {},
                    },
                    headers={"X-API-Key": "testkey", "X-Tenant-Id": "acme"},
                )
                for index in range(5)
            ]
        )
        elapsed = time.perf_counter() - started

    assert all(response.status_code == 200 for response in responses)
    assert elapsed < 0.35
