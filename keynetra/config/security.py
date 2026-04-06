from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from keynetra.config.settings import Settings, get_settings
from keynetra.config.tenancy import DEFAULT_TENANT_KEY, tenant_for_logs
from keynetra.infrastructure.logging import log_event
from keynetra.observability.metrics import record_auth_failure, record_jwks_fetch

api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
_auth_logger = logging.getLogger("keynetra.auth")
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_jwks_backoff_until: dict[str, float] = {}
_jwks_lock = threading.Lock()


def _decode_with_jwks(token: str, jwks: dict, audience: str | None, issuer: str | None) -> dict:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
    for key in keys:
        if kid and key.get("kid") != kid:
            continue
        try:
            return jwt.decode(
                token, key, audience=audience, issuer=issuer, options={"verify_aud": bool(audience)}
            )
        except JWTError:
            continue
    raise JWTError("no matching jwk")


def _unauthorized(detail: str = "unauthorized") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _log_failed_auth(request: Request, *, reason: str, api_key: str | None = None) -> None:
    record_auth_failure(reason=reason)
    log_event(
        _auth_logger,
        event="auth_failed",
        reason=reason,
        path=request.url.path,
        method=request.method,
        request_id=getattr(request.state, "request_id", None),
        tenant_id=tenant_for_logs(request),
        client_host=request.client.host if request.client else None,
        api_key_prefix=(api_key or "")[:12] or None,
    )


def _matches_api_key(candidate: str, stored_hashes: set[str]) -> bool:
    candidate_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    return any(hmac.compare_digest(candidate_hash, stored_hash) for stored_hash in stored_hashes)


def _scopes_are_defined(scopes: dict[str, Any]) -> bool:
    role = scopes.get("role")
    permissions = scopes.get("permissions")
    return (isinstance(role, str) and role.strip() != "") or (
        isinstance(permissions, list) and len(permissions) > 0
    )


def _get_jwks(settings: Settings) -> dict[str, Any]:
    if not settings.oidc_jwks_url:
        raise JWTError("jwks url not configured")

    now = time.time()
    with _jwks_lock:
        cached = _jwks_cache.get(settings.oidc_jwks_url)
        if cached is not None and cached[0] > now:
            record_jwks_fetch(outcome="cache_hit")
            return cached[1]
        blocked_until = _jwks_backoff_until.get(settings.oidc_jwks_url, 0.0)
        if blocked_until > now:
            record_jwks_fetch(outcome="backoff")
            raise JWTError("jwks fetch in backoff window")

    import httpx

    try:
        response = httpx.get(settings.oidc_jwks_url, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise JWTError("invalid jwks payload")
        with _jwks_lock:
            _jwks_cache[settings.oidc_jwks_url] = (now + settings.jwks_cache_ttl_seconds, payload)
            _jwks_backoff_until.pop(settings.oidc_jwks_url, None)
        record_jwks_fetch(outcome="success")
        return payload
    except Exception as exc:
        with _jwks_lock:
            previous = _jwks_backoff_until.get(settings.oidc_jwks_url, now)
            next_backoff = min(
                max(1.0, (previous - now) * 2.0 if previous > now else 1.0),
                float(settings.jwks_backoff_max_seconds),
            )
            _jwks_backoff_until[settings.oidc_jwks_url] = now + next_backoff
        record_jwks_fetch(outcome="failure")
        raise JWTError("jwks fetch failed") from exc


def get_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    x_api_key: str | None = Security(api_key_scheme),
) -> dict[str, Any]:
    api_key_hashes = settings.parsed_api_key_hashes()
    parsed_scopes = settings.parsed_api_key_scopes()
    if x_api_key:
        key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
        if _matches_api_key(x_api_key, api_key_hashes):
            scopes = parsed_scopes.get(key_hash, {})
            has_explicit_scope_for_key = key_hash in parsed_scopes
            if not _scopes_are_defined(scopes):
                _log_failed_auth(
                    request,
                    reason="api_key_missing_scope",
                    api_key=x_api_key,
                )
                if settings.is_development() and not has_explicit_scope_for_key:
                    scopes = {
                        "tenant": DEFAULT_TENANT_KEY,
                        "role": "admin",
                        "permissions": ["*"],
                    }
                if not settings.is_development():
                    raise _unauthorized("api key scopes must include role or permissions")
            return {
                "type": "api_key",
                "id": key_hash[:12],
                "scopes": scopes,
            }
        _log_failed_auth(request, reason="invalid_api_key", api_key=x_api_key)
        raise _unauthorized("invalid api key")

    if authorization and authorization.scheme.lower() == "bearer":
        token = authorization.credentials.strip()
        try:
            if settings.oidc_jwks_url:
                payload = _decode_with_jwks(
                    token,
                    _get_jwks(settings),
                    settings.oidc_audience,
                    settings.oidc_issuer,
                )
            else:
                payload = jwt.decode(
                    token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
                )
        except Exception as e:
            _log_failed_auth(request, reason="invalid_jwt")
            raise _unauthorized("invalid jwt") from e
        subject = payload.get("sub") or payload.get("user_id") or payload.get("client_id") or "jwt"
        return {"type": "jwt", "id": str(subject), "claims": payload}

    _log_failed_auth(request, reason="missing_credentials")
    raise _unauthorized("missing credentials")
