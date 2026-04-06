"""Parser for schema-first authorization models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IdentifierExpr:
    name: str


@dataclass(frozen=True)
class NotExpr:
    value: Any


@dataclass(frozen=True)
class AndExpr:
    left: Any
    right: Any


@dataclass(frozen=True)
class OrExpr:
    left: Any
    right: Any


Expr = IdentifierExpr | NotExpr | AndExpr | OrExpr


@dataclass(frozen=True)
class AuthorizationSchema:
    version: int
    types: tuple[str, ...] = ()
    relations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    permissions: dict[str, Expr] = field(default_factory=dict)
    raw: str = ""


_TOKEN_RE = re.compile(r"\s*(\(|\)|and\b|or\b|not\b|[A-Za-z_][A-Za-z0-9_:-]*)\s*")


def parse_authorization_schema(schema_text: str) -> AuthorizationSchema:
    lines = [line.split("#", 1)[0].strip() for line in schema_text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError("schema is empty")

    header = lines.pop(0)
    match = re.fullmatch(r"model\s+schema\s+(?P<version>\d+)", header, flags=re.IGNORECASE)
    if not match:
        raise ValueError("schema must start with 'model schema <version>'")

    version = int(match.group("version"))
    types: list[str] = []
    relations: dict[str, tuple[str, ...]] = {}
    permissions: dict[str, Expr] = {}
    section = None

    for line in lines:
        lowered = line.lower()
        if lowered in {"relations", "permissions"}:
            section = lowered
            continue
        if lowered.startswith("type "):
            types.append(line.split(None, 1)[1].strip())
            continue
        if section == "relations":
            name, subjects = _parse_relation(line)
            relations[name] = subjects
            continue
        if section == "permissions":
            name, expr = _parse_permission(line)
            permissions[name] = expr
            continue
        raise ValueError(f"unexpected schema line: {line}")

    return AuthorizationSchema(
        version=version,
        types=tuple(types),
        relations=relations,
        permissions=permissions,
        raw=schema_text,
    )


def _parse_relation(line: str) -> tuple[str, tuple[str, ...]]:
    if ":" not in line:
        raise ValueError(f"invalid relation: {line}")
    name, subject_text = line.split(":", 1)
    name = name.strip()
    subject_text = subject_text.strip()
    if not name:
        raise ValueError(f"invalid relation: {line}")
    if not subject_text.startswith("[") or not subject_text.endswith("]"):
        raise ValueError(f"invalid relation subjects: {line}")
    subjects = [item.strip() for item in subject_text[1:-1].split(",") if item.strip()]
    if not subjects:
        raise ValueError(f"invalid relation subjects: {line}")
    return name, tuple(subjects)


def _parse_permission(line: str) -> tuple[str, Expr]:
    if "=" not in line:
        raise ValueError(f"invalid permission: {line}")
    name, expr_text = line.split("=", 1)
    name = name.strip()
    expr_text = expr_text.strip()
    if not name or not expr_text:
        raise ValueError(f"invalid permission: {line}")
    tokens = _tokenize(expr_text)
    expr, index = _parse_expr(tokens, 0)
    if index != len(tokens):
        raise ValueError(f"invalid permission expression: {line}")
    return name, expr


def _tokenize(expr_text: str) -> list[str]:
    tokens = [match.group(1) for match in _TOKEN_RE.finditer(expr_text)]
    if "".join(tokens).replace(" ", "") != expr_text.replace(" ", ""):
        raise ValueError(f"invalid permission expression: {expr_text}")
    return tokens


def _parse_expr(tokens: list[str], index: int) -> tuple[Expr, int]:
    left, index = _parse_term(tokens, index)
    while index < len(tokens) and tokens[index].lower() == "or":
        right, index = _parse_term(tokens, index + 1)
        left = OrExpr(left=left, right=right)
    return left, index


def _parse_term(tokens: list[str], index: int) -> tuple[Expr, int]:
    left, index = _parse_factor(tokens, index)
    while index < len(tokens) and tokens[index].lower() == "and":
        right, index = _parse_factor(tokens, index + 1)
        left = AndExpr(left=left, right=right)
    return left, index


def _parse_factor(tokens: list[str], index: int) -> tuple[Expr, int]:
    if index >= len(tokens):
        raise ValueError("unexpected end of expression")
    token = tokens[index]
    lowered = token.lower()
    if lowered == "not":
        value, next_index = _parse_factor(tokens, index + 1)
        return NotExpr(value=value), next_index
    if token == "(":
        expr, next_index = _parse_expr(tokens, index + 1)
        if next_index >= len(tokens) or tokens[next_index] != ")":
            raise ValueError("missing closing parenthesis")
        return expr, next_index + 1
    if token in {")", "and", "or"}:
        raise ValueError("invalid expression")
    return IdentifierExpr(name=token), index + 1
