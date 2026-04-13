from __future__ import annotations

from fastapi import APIRouter

from keynetra.api.routes.access import router as access_router
from keynetra.api.routes.acl import router as acl_router
from keynetra.api.routes.admin_auth import router as admin_auth_router
from keynetra.api.routes.admin_tools import router as admin_tools_router
from keynetra.api.routes.audit import router as audit_router
from keynetra.api.routes.auth_model import router as auth_model_router
from keynetra.api.routes.dev import router as dev_router
from keynetra.api.routes.health import router as health_router
from keynetra.api.routes.metrics import router as metrics_router
from keynetra.api.routes.permissions import router as permissions_router
from keynetra.api.routes.playground import router as playground_router
from keynetra.api.routes.policies import router as policies_router
from keynetra.api.routes.relationships import router as relationships_router
from keynetra.api.routes.roles import router as roles_router
from keynetra.api.routes.simulation import router as simulation_router


def router_for_mode(mode: str) -> APIRouter:
    router = APIRouter()
    router.include_router(metrics_router, tags=["observability"])
    router.include_router(health_router, tags=["health"])

    mode = (mode or "all").lower()
    if mode in {"all", "access-api"}:
        router.include_router(access_router, tags=["access"])
    if mode in {"all", "policy-store"}:
        router.include_router(admin_auth_router, tags=["auth"])
        router.include_router(admin_tools_router, tags=["management"])
        router.include_router(policies_router, tags=["management"])
        router.include_router(acl_router, tags=["management"])
        router.include_router(auth_model_router, tags=["management"])
        router.include_router(simulation_router, tags=["management"])
        router.include_router(roles_router, tags=["management"])
        router.include_router(permissions_router, tags=["management"])
        router.include_router(relationships_router, tags=["management"])
        router.include_router(audit_router, tags=["management"])
        router.include_router(playground_router, tags=["playground"])
        router.include_router(dev_router, tags=["dev"])
    if mode == "policy-engine":
        # Engine is exposed via /check-access + /simulate routes (in access_router).
        router.include_router(access_router, tags=["engine"])

    return router
