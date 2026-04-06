from __future__ import annotations

from typing import Any


class AttributeValidationError(ValueError):
    pass


def _validate_dict(obj: Any, *, name: str, max_keys: int, max_depth: int, depth: int = 0) -> None:
    if not isinstance(obj, dict):
        raise AttributeValidationError(f"{name} must be an object")
    if len(obj) > max_keys:
        raise AttributeValidationError(f"{name} too large")
    if depth > max_depth:
        raise AttributeValidationError(f"{name} too deep")
    for k, v in obj.items():
        if not isinstance(k, str):
            raise AttributeValidationError(f"{name} keys must be strings")
        if isinstance(v, dict):
            _validate_dict(v, name=name, max_keys=max_keys, max_depth=max_depth, depth=depth + 1)
        elif isinstance(v, list) and len(v) > max_keys:
            raise AttributeValidationError(f"{name} list too large")


def validate_user(user: dict[str, Any]) -> None:
    _validate_dict(user, name="user", max_keys=200, max_depth=5)


def validate_resource(resource: dict[str, Any]) -> None:
    _validate_dict(resource, name="resource", max_keys=200, max_depth=5)
