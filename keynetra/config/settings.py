from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from keynetra.config.policies import DEFAULT_POLICIES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KEYNETRA_", extra="ignore", populate_by_name=True)

    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    database_url: str = Field(
        default="sqlite+pysqlite:///./keynetra.db",
    )
    redis_url: str | None = Field(default=None)

    api_keys: str | None = Field(default=None)
    api_key_hashes: str | None = Field(default=None)
    jwt_secret: str = Field(default="change-me")
    jwt_algorithm: str = Field(default="HS256")
    admin_username: str | None = Field(default=None)
    admin_password: str | None = Field(default=None)
    admin_token_expiry_minutes: int = Field(default=60)

    cors_allow_origins: str | None = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    cors_allow_origin_regex: str | None = Field(default=None)
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: str = Field(default="*")
    cors_allow_headers: str = Field(default="*")

    policies_json: str | None = Field(default=None)
    policy_paths: str | None = Field(default=None)
    model_paths: str | None = Field(default=None)
    decision_cache_ttl_seconds: int = Field(default=5)
    service_timeout_seconds: float = Field(default=2.0)
    critical_retry_attempts: int = Field(default=3)
    resilience_mode: str = Field(default="fail_closed")
    resilience_fallback_behavior: str = Field(default="static")

    rate_limit_per_minute: int = Field(default=60)
    rate_limit_burst: int | None = Field(default=None)
    rate_limit_window_seconds: int = Field(default=60)
    otel_enabled: bool = Field(default=False)
    service_mode: str = Field(default="all")
    auto_seed_sample_data: bool = Field(default=False)
    server_host: str = Field(default="0.0.0.0")
    server_port: int = Field(default=8000)

    # Policy distribution
    policy_events_channel: str = Field(default="keynetra:policy_events")

    # OIDC / JWKS (optional)
    oidc_jwks_url: str | None = Field(default=None)
    oidc_audience: str | None = Field(default=None)
    oidc_issuer: str | None = Field(default=None)

    def load_policies(self) -> list[dict[str, Any]]:
        if not self.policies_json:
            paths = self.parsed_policy_paths()
            if paths:
                from keynetra.config.file_loaders import load_policies_from_paths

                loaded = load_policies_from_paths(paths)
                if loaded:
                    return loaded
            return DEFAULT_POLICIES

        try:
            decoded = json.loads(self.policies_json)
        except json.JSONDecodeError:
            return DEFAULT_POLICIES

        if not isinstance(decoded, list):
            return DEFAULT_POLICIES

        return [p for p in decoded if isinstance(p, dict)]

    def parsed_policy_paths(self) -> list[str]:
        if not self.policy_paths:
            return []
        return [path.strip() for path in self.policy_paths.split(",") if path.strip()]

    def parsed_model_paths(self) -> list[str]:
        if not self.model_paths:
            return []
        return [path.strip() for path in self.model_paths.split(",") if path.strip()]

    def parsed_api_keys(self) -> set[str]:
        if not self.api_keys:
            return set()
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    def parsed_api_key_hashes(self) -> set[str]:
        if self.api_key_hashes:
            return {value.strip() for value in self.api_key_hashes.split(",") if value.strip()}
        return {hashlib.sha256(key.encode("utf-8")).hexdigest() for key in self.parsed_api_keys()}

    def parsed_cors_allow_origins(self) -> list[str]:
        if not self.cors_allow_origins:
            return []
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    def parsed_cors_allow_methods(self) -> list[str]:
        value = (self.cors_allow_methods or "").strip()
        if not value or value == "*":
            return ["*"]
        return [m.strip() for m in value.split(",") if m.strip()]

    def parsed_cors_allow_headers(self) -> list[str]:
        value = (self.cors_allow_headers or "").strip()
        if not value or value == "*":
            return ["*"]
        return [h.strip() for h in value.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
