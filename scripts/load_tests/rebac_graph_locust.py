from __future__ import annotations

from locust import HttpUser, between, task


class ReBACGraphUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def check_access_rebac(self) -> None:
        self.client.post(
            "/check-access",
            headers={"X-API-Key": "devkey"},
            json={
                "user": {"id": "u-rebac-1"},
                "action": "read_document",
                "resource": {"resource_type": "document", "resource_id": "doc-42"},
                "context": {},
            },
            name="rebac/check-access",
        )
