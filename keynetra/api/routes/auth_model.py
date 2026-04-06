from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import SQLAlchemyError

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.security import get_principal
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.modeling import AuthModelCreate, AuthModelOut
from keynetra.engine.model_graph.permission_graph import MODEL_GRAPH_STORE, CompiledPermissionGraph
from keynetra.modeling import (
    compile_authorization_schema,
    parse_authorization_schema,
    validate_authorization_schema,
)
from keynetra.services.revisions import RevisionService

router = APIRouter(prefix="/auth-model", dependencies=[Depends(get_principal)])


@router.post("", response_model=SuccessResponse[AuthModelOut], status_code=status.HTTP_201_CREATED)
def create_auth_model(
    payload: AuthModelCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(access.tenant_key)
    try:
        schema = parse_authorization_schema(payload.schema_text)
        validate_authorization_schema(schema)
        compiled = compile_authorization_schema(schema)
        record = services.auth_model_repo.upsert_model(
            tenant_id=tenant.id,
            schema_text=payload.schema_text,
            schema_json={
                "version": schema.version,
                "types": list(schema.types),
                "relations": {name: list(subjects) for name, subjects in schema.relations.items()},
                "permissions": {name: name for name in schema.permissions},
            },
            compiled_json=compiled.to_dict(),
        )
        MODEL_GRAPH_STORE.set(
            access.tenant_key, CompiledPermissionGraph(tenant_key=access.tenant_key, model=compiled)
        )
        RevisionService(services.tenant_repo).bump_revision(tenant_key=access.tenant_key)
    except ValueError as error:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message=str(error)
        ) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=AuthModelOut(
            id=record.id,
            tenant_id=record.tenant_id,
            schema_text=record.schema_text,
            parsed=record.schema_json,
            compiled=record.compiled_json,
        ).model_dump(by_alias=True),
        request_id=request_id_from_state(request.state),
    )


@router.get("", response_model=SuccessResponse[AuthModelOut])
def get_auth_model(
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(access.tenant_key)
    record = services.auth_model_repo.get_model(tenant_id=tenant.id)
    if record is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="auth model not found")
    return success_response(
        data=AuthModelOut(
            id=record.id,
            tenant_id=record.tenant_id,
            schema_text=record.schema_text,
            parsed=record.schema_json,
            compiled=record.compiled_json,
        ).model_dump(by_alias=True),
        request_id=request_id_from_state(request.state),
    )
