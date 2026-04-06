from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from keynetra.config.settings import Settings, get_settings
from keynetra.infrastructure.logging import log_event

api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
_auth_logger = logging.getLogger("keynetra.auth")


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
    log_event(
        _auth_logger,
        event="auth_failed",
        reason=reason,
        path=request.url.path,
        method=request.method,
        request_id=getattr(request.state, "request_id", None),
        tenant_id="default",
        client_host=request.client.host if request.client else None,
        api_key_prefix=(api_key or "")[:12] or None,
    )


def _matches_api_key(candidate: str, stored_hashes: set[str]) -> bool:
    candidate_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    return any(hmac.compare_digest(candidate_hash, stored_hash) for stored_hash in stored_hashes)


def get_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    x_api_key: str | None = Security(api_key_scheme),
) -> dict[str, Any]:
    api_key_hashes = settings.parsed_api_key_hashes()
    if x_api_key:
        if _matches_api_key(x_api_key, api_key_hashes):
            return {
                "type": "api_key",
                "id": hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()[:12],
            }
        _log_failed_auth(request, reason="invalid_api_key", api_key=x_api_key)
        raise _unauthorized("invalid api key")

    if authorization and authorization.scheme.lower() == "bearer":
        token = authorization.credentials.strip()
        try:
            if settings.oidc_jwks_url:
                import httpx

                jwks = httpx.get(settings.oidc_jwks_url, timeout=5.0).json()
                payload = _decode_with_jwks(
                    token, jwks, settings.oidc_audience, settings.oidc_issuer
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
