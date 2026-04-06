from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from keynetra.config.config_loader import load_config_file
from keynetra.config.file_loaders import (
    load_authorization_model_from_file,
    load_authorization_model_from_paths,
    load_policies_from_paths,
)
from keynetra.config.policies import DEFAULT_POLICIES
from keynetra.engine.keynetra_engine import AuthorizationDecision, AuthorizationInput, KeyNetraEngine
from keynetra.engine.model_graph.permission_graph import CompiledPermissionGraph
from keynetra.modeling.permission_compiler import compile_authorization_schema


@dataclass
class KeyNetra:
    """Embedded, headless authorization facade."""

    _engine: KeyNetraEngine
    _permission_graph: CompiledPermissionGraph | None = None

    @classmethod
    def from_config(cls, path: str | Path) -> "KeyNetra":
        config = load_config_file(path)
        policies = load_policies_from_paths(list(config.policy_paths)) or list(DEFAULT_POLICIES)
        engine = cls(_engine=KeyNetraEngine(policies))

        schema = load_authorization_model_from_paths(list(config.model_paths))
        if schema:
            engine._permission_graph = CompiledPermissionGraph(
                tenant_key="default",
                model=compile_authorization_schema(schema),
            )
        return engine

    def load_policies(self, path: str | Path) -> None:
        loaded = load_policies_from_paths([str(path)])
        if not loaded:
            raise ValueError("no policies found in the provided path")
        self._engine = KeyNetraEngine(loaded)

    def load_model(self, path: str | Path) -> None:
        schema = load_authorization_model_from_file(path)
        self._permission_graph = CompiledPermissionGraph(
            tenant_key="default",
            model=compile_authorization_schema(schema),
        )

    def check_access(
        self,
        *,
        subject: str | dict[str, Any],
        action: str,
        resource: str | dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AuthorizationDecision:
        user_payload = self._subject_to_user(subject)
        resource_payload = self._resource_to_payload(resource)
        return self._engine.decide(
            AuthorizationInput(
                user=user_payload,
                action=action,
                resource=resource_payload,
                context=dict(context or {}),
                permission_graph=self._permission_graph,
            )
        )

    def _subject_to_user(self, subject: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(subject, dict):
            return dict(subject)
        kind, identifier = _parse_descriptor(subject)
        if kind == "user":
            return {"id": identifier}
        return {"id": identifier, "subject_type": kind}

    def _resource_to_payload(self, resource: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(resource, dict):
            return dict(resource)
        resource_type, resource_id = _parse_descriptor(resource)
        return {
            "id": resource_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "type": resource_type,
        }


def _parse_descriptor(value: str) -> tuple[str, str]:
    normalized = str(value).strip()
    if ":" not in normalized:
        return normalized or "unknown", normalized or ""
    prefix, suffix = normalized.split(":", 1)
    return prefix.strip() or "unknown", suffix.strip()
