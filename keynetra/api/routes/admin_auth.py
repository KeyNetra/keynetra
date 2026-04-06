from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, status
from jose import jwt

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.settings import Settings, get_settings
from keynetra.config.tenancy import DEFAULT_TENANT_KEY
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import AdminLoginRequest, AdminLoginResponse

router = APIRouter(prefix="/admin")


@router.post("/login", response_model=SuccessResponse[AdminLoginResponse], tags=["auth"])
def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    username = settings.admin_username
    password = settings.admin_password
    password_hash = settings.admin_password_hash

    if not username or (not password and not password_hash):
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ApiErrorCode.FORBIDDEN,
            message="admin login is disabled",
        )

    valid_username = hmac.compare_digest(payload.username, username)
    valid_password = False
    if password_hash:
        candidate_hash = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
        valid_password = hmac.compare_digest(candidate_hash, password_hash)
    elif password:
        valid_password = hmac.compare_digest(payload.password, password)
    if not (valid_username and valid_password):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ApiErrorCode.UNAUTHORIZED,
            message="invalid admin credentials",
        )

    expires_at = datetime.now(UTC) + timedelta(minutes=max(1, settings.admin_token_expiry_minutes))
    token = jwt.encode(
        {
            "sub": payload.username,
            "role": "admin",
            "admin_role": "admin",
            "tenant_roles": {DEFAULT_TENANT_KEY: "admin"},
            "exp": int(expires_at.timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return success_response(
        data=AdminLoginResponse(
            access_token=token,
            expires_in=max(1, settings.admin_token_expiry_minutes) * 60,
            tenant_key=DEFAULT_TENANT_KEY,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )
