from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from keynetra.config.policies import DEFAULT_POLICIES

_DEV_ENVIRONMENTS = {"development", "dev", "local"}
_VALID_ENVIRONMENTS = _DEV_ENVIRONMENTS | {"ci", "prod", "production"}


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
    api_key_scopes_json: str | None = Field(default=None)
    jwt_secret: str = Field(default="change-me")
    jwt_algorithm: str = Field(default="HS256")
    admin_username: str | None = Field(default=None)
    admin_password: str | None = Field(default=None)
    admin_password_hash: str | None = Field(default=None)
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
    async_authorization_enabled: bool = Field(default=False)
    strict_tenancy: bool = Field(default=False)

    # Policy distribution
    policy_events_channel: str = Field(default="keynetra:policy_events")

    # OIDC / JWKS (optional)
    oidc_jwks_url: str | None = Field(default=None)
    oidc_audience: str | None = Field(default=None)
    oidc_issuer: str | None = Field(default=None)
    jwks_cache_ttl_seconds: int = Field(default=300)
    jwks_backoff_max_seconds: int = Field(default=60)

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in _VALID_ENVIRONMENTS:
            raise ValueError("environment must be one of: development, dev, local, ci, prod")
        return normalized

    @field_validator("service_timeout_seconds")
    @classmethod
    def _validate_service_timeout(cls, value: float) -> float:
        if value < 0.05 or value > 120:
            raise ValueError("service_timeout_seconds must be between 0.05 and 120")
        return value

    @field_validator("critical_retry_attempts")
    @classmethod
    def _validate_retry_attempts(cls, value: int) -> int:
        if value < 1 or value > 10:
            raise ValueError("critical_retry_attempts must be between 1 and 10")
        return value

    @field_validator("rate_limit_per_minute")
    @classmethod
    def _validate_rate_limit_per_minute(cls, value: int) -> int:
        if value < 1 or value > 1_000_000:
            raise ValueError("rate_limit_per_minute must be between 1 and 1000000")
        return value

    @field_validator("rate_limit_window_seconds")
    @classmethod
    def _validate_rate_limit_window_seconds(cls, value: int) -> int:
        if value < 1 or value > 3600:
            raise ValueError("rate_limit_window_seconds must be between 1 and 3600")
        return value

    @field_validator("rate_limit_burst")
    @classmethod
    def _validate_rate_limit_burst(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 1 or value > 1_000_000:
            raise ValueError("rate_limit_burst must be between 1 and 1000000")
        return value

    @field_validator("jwks_cache_ttl_seconds")
    @classmethod
    def _validate_jwks_cache_ttl_seconds(cls, value: int) -> int:
        if value < 10 or value > 86400:
            raise ValueError("jwks_cache_ttl_seconds must be between 10 and 86400")
        return value

    @field_validator("jwks_backoff_max_seconds")
    @classmethod
    def _validate_jwks_backoff_max_seconds(cls, value: int) -> int:
        if value < 1 or value > 3600:
            raise ValueError("jwks_backoff_max_seconds must be between 1 and 3600")
        return value

    @model_validator(mode="after")
    def _validate_security_profile(self) -> Settings:
        auth_enabled = (
            bool(self.parsed_api_key_hashes())
            or bool(self.oidc_jwks_url)
            or (bool(self.jwt_secret) and self.jwt_secret.strip() != "change-me")
        )
        non_dev = self.environment not in _DEV_ENVIRONMENTS
        if non_dev and not auth_enabled:
            raise ValueError(
                "configure at least one auth method: api_keys/api_key_hashes or jwt/oidc"
            )
        if self.environment == "prod" and self.jwt_secret.strip() == "change-me":
            raise ValueError("rejecting weak KEYNETRA_JWT_SECRET=change-me outside development")
        if non_dev and self.admin_password and not self.admin_password_hash:
            raise ValueError(
                "admin_password is not allowed outside development; use KEYNETRA_ADMIN_PASSWORD_HASH"
            )
        if non_dev and self.admin_username and self.admin_username.strip().lower() == "admin":
            raise ValueError("rejecting default admin username outside development")

        db_url = self.database_url.strip().lower()
        if self.environment == "prod" and "sqlite" in db_url:
            raise ValueError("sqlite is not allowed in production mode")

        if self.redis_url is not None and not self.redis_url.strip():
            raise ValueError("redis_url cannot be blank when provided")
        return self

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

    def parsed_api_key_scopes(self) -> dict[str, dict[str, Any]]:
        if not self.api_key_scopes_json:
            return {}
        try:
            decoded = json.loads(self.api_key_scopes_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(decoded, dict):
            return {}
        parsed: dict[str, dict[str, Any]] = {}
        for key, scopes in decoded.items():
            if not isinstance(scopes, dict):
                continue
            key_hash = str(key).strip()
            if len(key_hash) != 64:
                key_hash = hashlib.sha256(key_hash.encode("utf-8")).hexdigest()
            parsed[key_hash] = {
                "tenant": scopes.get("tenant"),
                "role": scopes.get("role"),
                "permissions": (
                    scopes.get("permissions") if isinstance(scopes.get("permissions"), list) else []
                ),
            }
        return parsed

    def is_development(self) -> bool:
        return self.environment in _DEV_ENVIRONMENTS

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
