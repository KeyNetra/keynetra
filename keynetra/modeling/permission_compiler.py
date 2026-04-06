"""Compiles authorization schemas into executable permission graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from keynetra.modeling.model_validator import validate_authorization_schema
from keynetra.modeling.schema_parser import (
    AndExpr,
    AuthorizationSchema,
    Expr,
    IdentifierExpr,
    NotExpr,
    OrExpr,
    parse_authorization_schema,
)


@dataclass(frozen=True)
class CompiledPermission:
    name: str
    expression: Expr


@dataclass(frozen=True)
class CompiledAuthorizationModel:
    version: int
    types: tuple[str, ...]
    relations: dict[str, tuple[str, ...]]
    permissions: dict[str, CompiledPermission]
    raw: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "types": list(self.types),
            "relations": {name: list(subjects) for name, subjects in self.relations.items()},
            "permissions": {
                name: _expr_to_dict(permission.expression)
                for name, permission in self.permissions.items()
            },
            "raw": self.raw,
        }


def compile_authorization_schema(
    schema_text: str | AuthorizationSchema,
) -> CompiledAuthorizationModel:
    schema = (
        parse_authorization_schema(schema_text) if isinstance(schema_text, str) else schema_text
    )
    validate_authorization_schema(schema)
    permissions = {
        name: CompiledPermission(name=name, expression=expr)
        for name, expr in schema.permissions.items()
    }
    return CompiledAuthorizationModel(
        version=schema.version,
        types=schema.types,
        relations=schema.relations,
        permissions=permissions,
        raw=schema.raw,
    )


def _expr_to_dict(expr: Expr) -> dict[str, Any]:
    if isinstance(expr, IdentifierExpr):
        return {"kind": "identifier", "name": expr.name}
    if isinstance(expr, NotExpr):
        return {"kind": "not", "value": _expr_to_dict(expr.value)}
    if isinstance(expr, AndExpr):
        return {"kind": "and", "left": _expr_to_dict(expr.left), "right": _expr_to_dict(expr.right)}
    if isinstance(expr, OrExpr):
        return {"kind": "or", "left": _expr_to_dict(expr.left), "right": _expr_to_dict(expr.right)}
    raise ValueError("invalid expression")
