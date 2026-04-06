from __future__ import annotations

from locust import HttpUser, between, task


class CacheWarmColdUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task(5)
    def warm_path(self) -> None:
        self.client.post(
            "/check-access",
            headers={"X-API-Key": "devkey"},
            json={
                "user": {"id": 1, "role": "member"},
                "action": "read",
                "resource": {"id": "doc-warm"},
                "context": {},
            },
            name="cache/warm",
        )

    @task(1)
    def cold_path(self) -> None:
        self.client.post(
            "/check-access",
            headers={"X-API-Key": "devkey"},
            json={
                "user": {"id": 1, "role": "member"},
                "action": "read",
                "resource": {"id": "doc-cold"},
                "context": {"nonce": "cold"},
            },
            name="cache/cold",
        )
