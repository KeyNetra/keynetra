from __future__ import annotations

from itertools import cycle

from locust import HttpUser, between, task

_TENANTS = cycle(["tenant-a", "tenant-b", "tenant-c"])


class MultiTenantUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def check_access_multi_tenant(self) -> None:
        tenant = next(_TENANTS)
        self.client.post(
            "/check-access",
            headers={"X-API-Key": "devkey"},
            params={"policy_set": "active"},
            json={
                "user": {"id": f"{tenant}-u1", "role": "member"},
                "action": "view_dashboard",
                "resource": {"id": f"{tenant}-dashboard"},
                "context": {"tenant": tenant},
            },
            name="multi-tenant/check-access",
        )
