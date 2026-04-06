"""Redis-backed token bucket middleware for external endpoints."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from keynetra.config.redis_client import get_redis
from keynetra.config.settings import Settings


@dataclass
class _LocalBucket:
    tokens: float
    updated_at: float


_local_limits: dict[str, _LocalBucket] = {}
_local_limits_lock = Lock()
_EXEMPT_PATHS = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json"}
_REDIS_BUCKET_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local values = redis.call("HMGET", key, "tokens", "updated_at")
local tokens = tonumber(values[1])
local updated_at = tonumber(values[2])

if tokens == nil then
    tokens = capacity
end
if updated_at == nil then
    updated_at = now
end

local elapsed = math.max(0, now - updated_at)
tokens = math.min(capacity, tokens + (elapsed * refill_rate))

local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end

redis.call("HMSET", key, "tokens", tokens, "updated_at", now)
redis.call("EXPIRE", key, ttl)

local retry_after = 0
if allowed == 0 then
    retry_after = math.ceil((requested - tokens) / refill_rate)
end

return {allowed, tokens, retry_after}
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:  # type: ignore[override]
        super().__init__(app)
        self._settings = settings
        with _local_limits_lock:
            _local_limits.clear()

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if request.method.upper() == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        decision = self._consume(request)
        if isinstance(decision, Response):
            return decision
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.retry_after)
        return response

    def _consume(self, request: Request) -> "_BucketDecision | Response":
        rate = max(1, self._settings.rate_limit_per_minute)
        interval = max(1, self._settings.rate_limit_window_seconds)
        capacity = max(1, self._settings.rate_limit_burst or rate)
        refill_rate = rate / interval
        now = time.time()
        principal = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        if principal is None:
            principal = request.client.host if request.client else "anonymous"
        principal_hash = hashlib.sha256(principal.encode("utf-8")).hexdigest()[:32]
        key = f"rl:tb:{principal_hash}"
        ttl = max(interval, math.ceil(capacity / refill_rate) * 2)

        redis_client = get_redis()
        if redis_client is not None:
            try:
                allowed, remaining, retry_after = redis_client.eval(
                    _REDIS_BUCKET_SCRIPT,
                    1,
                    key,
                    str(now),
                    str(refill_rate),
                    str(capacity),
                    "1",
                    str(ttl),
                )
                allowed_bool = int(allowed) == 1
                remaining_tokens = max(0, int(float(remaining)))
                retry_after_seconds = max(0, int(retry_after))
                if not allowed_bool:
                    return self._limited_response(limit=capacity, retry_after=retry_after_seconds)
                return _BucketDecision(
                    limit=capacity, remaining=remaining_tokens, retry_after=retry_after_seconds
                )
            except Exception:
                pass

        with _local_limits_lock:
            bucket = _local_limits.get(key)
            if bucket is None:
                bucket = _LocalBucket(tokens=float(capacity), updated_at=now)
                _local_limits[key] = bucket
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(float(capacity), bucket.tokens + (elapsed * refill_rate))
            bucket.updated_at = now
            if bucket.tokens < 1.0:
                retry_after = max(1, math.ceil((1.0 - bucket.tokens) / refill_rate))
                return self._limited_response(limit=capacity, retry_after=retry_after)
            bucket.tokens -= 1.0
            remaining = max(0, int(bucket.tokens))
            return _BucketDecision(limit=capacity, remaining=remaining, retry_after=0)

    def _limited_response(self, *, limit: int, retry_after: int) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={
                "Retry-After": str(max(1, retry_after)),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(max(1, retry_after)),
            },
            content={
                "data": None,
                "error": {
                    "code": "too_many_requests",
                    "message": "rate limit exceeded",
                    "details": None,
                },
            },
        )


@dataclass(frozen=True)
class _BucketDecision:
    limit: int
    remaining: int
    retry_after: int
