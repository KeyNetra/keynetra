"""Validation for authorization modeling schemas."""

from __future__ import annotations

from keynetra.modeling.schema_parser import (
    AndExpr,
    AuthorizationSchema,
    IdentifierExpr,
    NotExpr,
    OrExpr,
)


def validate_authorization_schema(schema: AuthorizationSchema) -> None:
    if schema.version < 1:
        raise ValueError("schema version must be >= 1")
    if not schema.types:
        raise ValueError("schema must define at least one type")
    if "user" not in schema.types:
        raise ValueError("schema must define type user")
    if not schema.permissions:
        raise ValueError("schema must define permissions")
    for relation, subjects in schema.relations.items():
        if not relation:
            raise ValueError("relation names must be non-empty")
        for subject in subjects:
            if subject not in schema.types:
                raise ValueError(f"relation {relation} references unknown type {subject}")
    for permission, expr in schema.permissions.items():
        if not permission:
            raise ValueError("permission names must be non-empty")
        _validate_expr(expr, schema)


def _validate_expr(expr, schema: AuthorizationSchema) -> None:
    if isinstance(expr, IdentifierExpr):
        if expr.name not in schema.relations and expr.name not in schema.permissions:
            raise ValueError(f"unknown relation or permission {expr.name}")
        return
    if isinstance(expr, NotExpr):
        _validate_expr(expr.value, schema)
        return
    if isinstance(expr, AndExpr) or isinstance(expr, OrExpr):
        _validate_expr(expr.left, schema)
        _validate_expr(expr.right, schema)
        return
    raise ValueError("invalid expression node")
