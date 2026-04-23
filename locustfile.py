from __future__ import annotations

import os

from locust import HttpUser, between, task


class KeyNetraUser(HttpUser):
    wait_time = between(0.0, 0.1)

    def on_start(self) -> None:
        self.headers = {
            "X-API-Key": os.getenv("KEYNETRA_LOCUST_API_KEY", "devkey"),
            "X-Tenant-Id": os.getenv("KEYNETRA_LOCUST_TENANT_ID", "default"),
        }

    @task
    def check_access(self) -> None:
        self.client.post(
            "/check-access",
            json={
                "user": {"id": 1, "permissions": []},
                "action": "approve_payment",
                "resource": {"amount": 10},
            },
            headers=self.headers,
        )
