from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional parser dependency
    yaml = None  # type: ignore[assignment]


def load_policies_from_paths(paths: list[str]) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    for path in paths:
        policy_path = Path(path).expanduser()
        if policy_path.is_dir():
            files = sorted(
                [
                    child
                    for child in policy_path.rglob("*")
                    if child.is_file() and child.suffix.lower() in {".yaml", ".yml", ".json", ".polar"}
                ]
            )
            for file_path in files:
                policies.extend(load_policies_from_file(file_path))
            continue
        if policy_path.is_file():
            policies.extend(load_policies_from_file(policy_path))
    return policies


def load_policies_from_file(path: str | Path) -> list[dict[str, Any]]:
    policy_path = Path(path).expanduser().resolve()
    suffix = policy_path.suffix.lower()
    raw = policy_path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise ValueError("PyYAML is required to parse YAML policy files")
        payload = yaml.safe_load(raw)
        return _normalize_policy_payload(payload)
    if suffix == ".json":
        payload = json.loads(raw)
        return _normalize_policy_payload(payload)
    if suffix == ".polar":
        return _parse_polar_policy_lines(raw)
    raise ValueError(f"unsupported policy format: {policy_path.suffix}")


def load_authorization_model_from_paths(paths: list[str]) -> str | None:
    for path in paths:
        model_path = Path(path).expanduser()
        if model_path.is_dir():
            files = sorted([child for child in model_path.rglob("*") if child.is_file()])
            for file_path in files:
                schema = _load_model_file_if_supported(file_path)
                if schema:
                    return schema
            continue
        if model_path.is_file():
            schema = _load_model_file_if_supported(model_path)
            if schema:
                return schema
    return None


def _load_model_file_if_supported(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml", ".json", ".toml"}:
        return load_authorization_model_from_file(path)
    if suffix in {".schema", ".txt"}:
        text = path.read_text(encoding="utf-8").strip()
        return text or None
    return None


def load_authorization_model_from_file(path: str | Path) -> str:
    model_path = Path(path).expanduser().resolve()
    suffix = model_path.suffix.lower()
    raw = model_path.read_text(encoding="utf-8")

    payload: Any
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise ValueError("PyYAML is required to parse YAML model files")
        payload = yaml.safe_load(raw)
    elif suffix == ".json":
        payload = json.loads(raw)
    elif suffix == ".toml":
        payload = tomllib.loads(raw)
    else:
        raise ValueError(f"unsupported authorization model format: {model_path.suffix}")

    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            raise ValueError("authorization model file is empty")
        return text
    if not isinstance(payload, dict):
        raise ValueError("authorization model file must contain an object")
    return _model_mapping_to_schema(payload)


def _normalize_policy_payload(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        policies: list[dict[str, Any]] = []
        for item in payload:
            policies.extend(_normalize_policy_payload(item))
        return policies
    if isinstance(payload, dict):
        if "policies" in payload and isinstance(payload["policies"], list):
            return _normalize_policy_payload(payload["policies"])
        if "allow" in payload or "deny" in payload:
            return [_policy_from_effect_block(payload)]
        if "action" in payload:
            effect = str(payload.get("effect", "deny")).lower()
            return [
                {
                    "action": str(payload.get("action", "")),
                    "effect": "allow" if effect == "allow" else "deny",
                    "priority": int(payload.get("priority", 100)),
                    "conditions": dict(payload.get("conditions") or {}),
                    "policy_id": (
                        None
                        if payload.get("policy_id") is None
                        else str(payload.get("policy_id"))
                    ),
                }
            ]
    raise ValueError("invalid policy payload")


def _policy_from_effect_block(payload: dict[str, Any]) -> dict[str, Any]:
    if "allow" in payload:
        effect = "allow"
        block = payload.get("allow")
    else:
        effect = "deny"
        block = payload.get("deny")
    if not isinstance(block, dict):
        raise ValueError("policy block must be an object")
    action = str(block.get("action", "")).strip()
    if not action:
        raise ValueError("policy action is required")
    conditions = block.get("when") or block.get("conditions") or {}
    if not isinstance(conditions, dict):
        raise ValueError("policy conditions must be an object")
    return {
        "action": action,
        "effect": effect,
        "priority": int(block.get("priority", 100)),
        "conditions": dict(conditions),
        "policy_id": None if block.get("policy_id") is None else str(block.get("policy_id")),
    }


def _parse_polar_policy_lines(text: str) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        parts = stripped.split()
        effect = parts[0].lower()
        if effect not in {"allow", "deny"}:
            raise ValueError(f"invalid .polar rule: {stripped}")
        attrs: dict[str, str] = {}
        for token in parts[1:]:
            if "=" not in token:
                raise ValueError(f"invalid .polar token: {token}")
            key, value = token.split("=", 1)
            attrs[key.strip()] = value.strip()
        action = attrs.pop("action", "").strip()
        if not action:
            raise ValueError(f"missing action in .polar rule: {stripped}")
        priority = int(attrs.pop("priority", "100"))
        policy_id = attrs.pop("policy_id", None)
        conditions = {key: _coerce_scalar(value) for key, value in attrs.items()}
        policies.append(
            {
                "action": action,
                "effect": effect,
                "priority": priority,
                "conditions": conditions,
                "policy_id": policy_id,
            }
        )
    return policies


def _coerce_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _model_mapping_to_schema(payload: dict[str, Any]) -> str:
    model = payload.get("model", payload)
    if not isinstance(model, dict):
        raise ValueError("model must be an object")
    version = int(model.get("schema_version", model.get("version", 1)))
    object_type = str(model.get("type", "resource")).strip() or "resource"
    relations_obj = model.get("relations") or {}
    permissions_obj = model.get("permissions") or {}

    if not isinstance(relations_obj, dict) or not isinstance(permissions_obj, dict):
        raise ValueError("relations and permissions must be objects")

    types = {"user", object_type}
    for subjects in relations_obj.values():
        if isinstance(subjects, str):
            types.add(subjects)
        elif isinstance(subjects, list):
            types.update(str(item) for item in subjects if item)

    lines: list[str] = [f"model schema {version}"]
    for type_name in sorted(types):
        lines.append(f"type {type_name}")

    lines.append("relations")
    for name, subjects in relations_obj.items():
        if isinstance(subjects, str):
            subject_list = [subjects]
        elif isinstance(subjects, list):
            subject_list = [str(item) for item in subjects if item]
        else:
            raise ValueError(f"invalid relation subjects for {name}")
        lines.append(f"{name}: [{', '.join(subject_list)}]")

    lines.append("permissions")
    for name, expr in permissions_obj.items():
        lines.append(f"{name} = {expr}")

    return "\n".join(lines)
