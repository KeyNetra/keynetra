from fastapi import APIRouter

from keynetra.api.service_modes import router_for_mode

# Backward-compatible full router alias; canonical routing lives in service_modes.py.
api_router: APIRouter = router_for_mode("all")
