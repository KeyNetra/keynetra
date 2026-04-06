from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional parser dependency
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class KeyNetraFileConfig:
    database_url: str | None = None
    redis_url: str | None = None
    policy_paths: tuple[str, ...] = ()
    model_paths: tuple[str, ...] = ()
    seed_data: bool | None = None
    server_host: str | None = None
    server_port: int | None = None


def load_config_file(path: str | Path) -> KeyNetraFileConfig:
    config_path = Path(path).expanduser().resolve()
    suffix = config_path.suffix.lower()
    raw = config_path.read_text(encoding="utf-8")
    payload: Any
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise ValueError("PyYAML is required to parse YAML configuration files")
        payload = yaml.safe_load(raw)
    elif suffix == ".json":
        payload = json.loads(raw)
    elif suffix == ".toml":
        payload = tomllib.loads(raw)
    else:
        raise ValueError(f"unsupported config file format: {config_path.suffix}")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("configuration root must be an object")
    return _normalize_config(payload)


def apply_config_to_environment(config: KeyNetraFileConfig) -> None:
    if config.database_url:
        os.environ["KEYNETRA_DATABASE_URL"] = config.database_url
    if config.redis_url:
        os.environ["KEYNETRA_REDIS_URL"] = config.redis_url
    if config.policy_paths:
        os.environ["KEYNETRA_POLICY_PATHS"] = ",".join(config.policy_paths)
    if config.model_paths:
        os.environ["KEYNETRA_MODEL_PATHS"] = ",".join(config.model_paths)
    if config.seed_data is not None:
        os.environ["KEYNETRA_AUTO_SEED_SAMPLE_DATA"] = "true" if config.seed_data else "false"
    if config.server_host:
        os.environ["KEYNETRA_SERVER_HOST"] = config.server_host
    if config.server_port is not None:
        os.environ["KEYNETRA_SERVER_PORT"] = str(config.server_port)


def _normalize_config(payload: dict[str, Any]) -> KeyNetraFileConfig:
    database_url = _as_str(_nested(payload, "database", "url"))
    redis_url = _as_str(_nested(payload, "redis", "url"))
    policy_paths = _paths_from_payload(payload, section="policies", plural_key="policy_paths")
    model_paths = _paths_from_payload(payload, section="models", plural_key="model_paths")
    seed_data = _as_bool(payload.get("seed_data"))
    server_host = _as_str(_nested(payload, "server", "host"))
    server_port = _as_int(_nested(payload, "server", "port"))

    return KeyNetraFileConfig(
        database_url=database_url,
        redis_url=redis_url,
        policy_paths=policy_paths,
        model_paths=model_paths,
        seed_data=seed_data,
        server_host=server_host,
        server_port=server_port,
    )


def _paths_from_payload(
    payload: dict[str, Any], *, section: str, plural_key: str
) -> tuple[str, ...]:
    out: list[str] = []
    if isinstance(payload.get(plural_key), list):
        out.extend([str(item) for item in payload.get(plural_key, []) if isinstance(item, str)])
    section_obj = payload.get(section)
    if isinstance(section_obj, dict):
        single = section_obj.get("path")
        if isinstance(single, str):
            out.append(single)
        many = section_obj.get("paths")
        if isinstance(many, list):
            out.extend([str(item) for item in many if isinstance(item, str)])
    return tuple(dict.fromkeys(path.strip() for path in out if path and path.strip()))


def _nested(payload: dict[str, Any], section: str, key: str) -> Any:
    section_obj = payload.get(section)
    if not isinstance(section_obj, dict):
        return None
    return section_obj.get(key)


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return str(value)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None
