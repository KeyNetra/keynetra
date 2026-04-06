from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")
