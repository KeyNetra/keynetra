from __future__ import annotations

from locust import HttpUser, between, task


class RBACHeavyUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def check_access_rbac(self) -> None:
        self.client.post(
            "/check-access",
            headers={"X-API-Key": "devkey"},
            json={
                "user": {"id": "u-rbac-1", "role": "manager", "permissions": ["approve_payment"]},
                "action": "approve_payment",
                "resource": {"id": "invoice-1", "amount": 500},
                "context": {},
            },
            name="rbac/check-access",
        )
