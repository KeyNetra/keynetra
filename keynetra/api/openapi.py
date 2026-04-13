from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.openapi.utils import get_openapi

from keynetra.api.errors import ApiErrorCode


def build_openapi_schema(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    _apply_route_metadata(app, schema)
    _normalize_for_sdk_codegen(schema)
    _inject_reusable_contract_components(schema)
    _document_non_json_exceptions(schema)
    _apply_standard_contract_metadata(schema)
    app.openapi_schema = schema
    return schema


def _apply_route_metadata(app: FastAPI, schema: dict[str, Any]) -> None:
    seen_operation_ids: set[str] = set()

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        path_item = schema.get("paths", {}).get(route.path_format)
        if not isinstance(path_item, dict):
            continue

        for method in sorted(route.methods or set()):
            method_name = method.lower()
            if method_name == "head":
                continue

            operation = path_item.get(method_name)
            if not isinstance(operation, dict):
                continue

            operation["operationId"] = _unique_operation_id(route.name, seen_operation_ids)
            tags = operation.get("tags")
            if isinstance(tags, list):
                operation["tags"] = list(dict.fromkeys(tags))


def _unique_operation_id(name: str, seen_operation_ids: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in seen_operation_ids:
        candidate = f"{name}_{suffix}"
        suffix += 1
    seen_operation_ids.add(candidate)
    return candidate


def _normalize_for_sdk_codegen(document: dict[str, Any]) -> None:
    document["openapi"] = "3.0.3"
    document["servers"] = [
        {
            "url": "/",
            "description": "Relative base URL. Configure the SDK/client host per environment.",
        }
    ]
    _normalize_node(document)


def _normalize_node(node: Any, *, parent_key: str | None = None) -> None:
    if isinstance(node, list):
        for item in node:
            _normalize_node(item)
        return

    if not isinstance(node, dict):
        return

    for key, value in list(node.items()):
        _normalize_node(value, parent_key=key)

    nullable_variant = _extract_nullable_variant(node)
    if nullable_variant is not None:
        siblings = {key: value for key, value in node.items() if key != "anyOf"}
        node.clear()
        node.update(nullable_variant)
        node.update(siblings)
        node["nullable"] = True
        return

    schema_type = node.get("type")
    if isinstance(schema_type, list) and "null" in schema_type:
        remaining_types = [value for value in schema_type if value != "null"]
        if len(remaining_types) == 1:
            node["type"] = remaining_types[0]
        elif remaining_types:
            node["type"] = remaining_types
        else:
            node.pop("type", None)
        node["nullable"] = True
        return

    if schema_type == "null":
        title = node.get("title")
        description = node.get("description")
        replacement: dict[str, Any]
        if parent_key == "error":
            replacement = {
                "allOf": [{"$ref": "#/components/schemas/ErrorBody"}],
                "nullable": True,
            }
        else:
            replacement = {"nullable": True}
        if title is not None:
            replacement["title"] = title
        if description is not None:
            replacement["description"] = description
        node.clear()
        node.update(replacement)


def _extract_nullable_variant(node: dict[str, Any]) -> dict[str, Any] | None:
    any_of = node.get("anyOf")
    if not isinstance(any_of, list) or len(any_of) != 2:
        return None

    non_null_schemas = [item for item in any_of if not _is_null_schema(item)]
    null_schemas = [item for item in any_of if _is_null_schema(item)]
    if len(non_null_schemas) != 1 or len(null_schemas) != 1:
        return None

    return deepcopy(non_null_schemas[0])


def _is_null_schema(node: Any) -> bool:
    return isinstance(node, dict) and node.get("type") == "null"


def _inject_reusable_contract_components(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {})
    parameters = components.setdefault("parameters", {})
    headers = components.setdefault("headers", {})
    responses = components.setdefault("responses", {})
    schemas = components.setdefault("schemas", {})

    parameters["ApiVersionHeader"] = {
        "name": "X-API-Version",
        "in": "header",
        "required": False,
        "schema": {"type": "string", "default": "v1"},
        "description": "Requested API version. Supported values: v1.",
    }
    parameters["TenantHeader"] = {
        "name": "X-Tenant-Id",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
        "description": "Tenant key for strict tenancy and management operations.",
    }

    headers["ApiVersionHeader"] = {
        "description": "Resolved API version for the response.",
        "schema": {"type": "string", "default": "v1"},
    }
    headers["RequestIdHeader"] = {
        "description": "Correlation id for the request.",
        "schema": {"type": "string"},
    }

    schemas.setdefault(
        "ApiErrorCode",
        {
            "title": "ApiErrorCode",
            "type": "string",
            "enum": [code.value for code in ApiErrorCode],
        },
    )
    schemas.setdefault(
        "ErrorBody",
        {
            "title": "ErrorBody",
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"$ref": "#/components/schemas/ApiErrorCode"},
                "message": {"title": "Message", "type": "string"},
                "details": {"title": "Details", "nullable": True},
            },
        },
    )
    schemas.setdefault(
        "ErrorResponse",
        {
            "title": "ErrorResponse",
            "type": "object",
            "required": ["error"],
            "properties": {
                "data": {"nullable": True, "title": "Data"},
                "meta": {"$ref": "#/components/schemas/MetaBody"},
                "error": {"$ref": "#/components/schemas/ErrorBody"},
            },
        },
    )
    schemas["ValidationError"] = {
        "title": "ValidationError",
        "type": "object",
        "required": ["loc", "msg", "type"],
        "properties": {
            "loc": {
                "title": "Location",
                "type": "array",
                "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            },
            "msg": {"title": "Message", "type": "string"},
            "type": {"title": "Error Type", "type": "string"},
            "input": {"title": "Input", "nullable": True},
            "ctx": {"title": "Context", "type": "object", "nullable": True},
        },
    }
    schemas["HTTPValidationError"] = {
        "title": "HTTPValidationError",
        "type": "object",
        "properties": {
            "detail": {
                "title": "Detail",
                "type": "array",
                "items": {"$ref": "#/components/schemas/ValidationError"},
            }
        },
    }

    error_schema_ref = {"$ref": "#/components/schemas/ErrorResponse"}
    for status_code, description in {
        "400": "Bad Request",
        "401": "Unauthorized",
        "403": "Forbidden",
        "404": "Not Found",
        "409": "Conflict",
        "422": "Validation Error",
        "429": "Too Many Requests",
        "500": "Internal Server Error",
    }.items():
        responses[f"Error{status_code}"] = {
            "description": description,
            "content": {
                "application/json": {
                    "schema": error_schema_ref,
                    "examples": {
                        "error": {
                            "summary": "Standard error envelope",
                            "value": _error_example(status_code),
                        }
                    },
                }
            },
            "headers": {
                "X-Request-Id": {"$ref": "#/components/headers/RequestIdHeader"},
                "X-API-Version": {"$ref": "#/components/headers/ApiVersionHeader"},
            },
        }


def _apply_standard_contract_metadata(schema: dict[str, Any]) -> None:
    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for _, operation in path_item.items():
            if not isinstance(operation, dict):
                continue

            parameters = operation.setdefault("parameters", [])
            _ensure_parameter_ref(parameters, "#/components/parameters/ApiVersionHeader")
            if _requires_tenant_header(path):
                _ensure_parameter_ref(parameters, "#/components/parameters/TenantHeader")

            responses = operation.setdefault("responses", {})
            _ensure_response_header_refs(responses)
            if path == "/metrics":
                continue
            _ensure_common_error_responses(responses)
            _ensure_response_examples(responses)


def _ensure_parameter_ref(parameters: list[Any], ref: str) -> None:
    if any(isinstance(item, dict) and item.get("$ref") == ref for item in parameters):
        return
    parameters.append({"$ref": ref})


def _requires_tenant_header(path: str) -> bool:
    prefixes = (
        "/check-access",
        "/simulate",
        "/policies",
        "/roles",
        "/permissions",
        "/relationships",
        "/playground",
        "/audit",
        "/tenants",
        "/users",
        "/policy-tests",
        "/bulk",
    )
    return path.startswith(prefixes)


def _ensure_response_header_refs(responses: dict[str, Any]) -> None:
    for response in responses.values():
        if not isinstance(response, dict):
            continue
        headers = response.setdefault("headers", {})
        headers.setdefault("X-Request-Id", {"$ref": "#/components/headers/RequestIdHeader"})
        headers.setdefault("X-API-Version", {"$ref": "#/components/headers/ApiVersionHeader"})


def _ensure_common_error_responses(responses: dict[str, Any]) -> None:
    for status_code in ("400", "401", "403", "404", "409", "422", "429", "500"):
        if status_code in responses:
            responses[status_code].setdefault("headers", {})
            responses[status_code]["content"] = {
                "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
            }
            responses[status_code]["headers"].setdefault(
                "X-Request-Id", {"$ref": "#/components/headers/RequestIdHeader"}
            )
            responses[status_code]["headers"].setdefault(
                "X-API-Version", {"$ref": "#/components/headers/ApiVersionHeader"}
            )
            continue
        responses[status_code] = {"$ref": f"#/components/responses/Error{status_code}"}


def _ensure_response_examples(responses: dict[str, Any]) -> None:
    for status_code, response in responses.items():
        if not isinstance(response, dict) or "$ref" in response:
            continue
        content = response.get("content", {})
        app_json = content.get("application/json")
        if not isinstance(app_json, dict):
            continue
        if status_code.startswith("2"):
            app_json.setdefault(
                "examples",
                {
                    "success": {
                        "summary": "Standard success envelope",
                        "value": _success_example(),
                    }
                },
            )
        else:
            app_json.setdefault(
                "examples",
                {
                    "error": {
                        "summary": "Standard error envelope",
                        "value": _error_example(status_code),
                    }
                },
            )


def _document_non_json_exceptions(schema: dict[str, Any]) -> None:
    schema.setdefault("paths", {})["/metrics"] = {
        "get": {
            "tags": ["observability"],
            "summary": "Metrics",
            "description": "Prometheus scrape endpoint. This is intentionally not wrapped in the JSON API envelope.",
            "operationId": "metrics",
            "parameters": [{"$ref": "#/components/parameters/ApiVersionHeader"}],
            "responses": {
                "200": {
                    "description": "Prometheus metrics payload",
                    "headers": {
                        "X-Request-Id": {"$ref": "#/components/headers/RequestIdHeader"},
                        "X-API-Version": {"$ref": "#/components/headers/ApiVersionHeader"},
                    },
                    "content": {
                        "text/plain": {
                            "schema": {"type": "string"},
                            "examples": {
                                "prometheus": {
                                    "summary": "Prometheus exposition format",
                                    "value": "# HELP keynetra_requests_total Total requests\n# TYPE keynetra_requests_total counter",
                                }
                            },
                        }
                    },
                }
            },
        }
    }


def _success_example() -> dict[str, Any]:
    return {
        "data": {},
        "meta": {
            "request_id": "req_example_123",
            "limit": None,
            "next_cursor": None,
            "extra": {},
        },
        "error": None,
    }


def _error_example(status_code: str) -> dict[str, Any]:
    return {
        "data": None,
        "meta": {
            "request_id": "req_example_123",
            "limit": None,
            "next_cursor": None,
            "extra": {},
        },
        "error": {
            "code": _error_code_for_status(status_code),
            "message": "request failed",
            "details": None,
        },
    }


def _error_code_for_status(status_code: str) -> str:
    return {
        "400": "bad_request",
        "401": "unauthorized",
        "403": "forbidden",
        "404": "not_found",
        "409": "conflict",
        "422": "validation_error",
        "429": "too_many_requests",
        "500": "internal_error",
    }.get(status_code, "bad_request")
