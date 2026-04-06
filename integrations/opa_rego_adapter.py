from __future__ import annotations

from dataclasses import dataclass

from integrations.interfaces import PolicyAdapter


@dataclass
class OPARegoPolicyAdapter(PolicyAdapter):
    """Minimal OPA/Rego policy adapter scaffold."""

    _rego: str = ""

    def import_policies(self, payload: str) -> int:
        self._rego = payload
        return len(payload.splitlines()) if payload else 0

    def export_policies(self) -> str:
        return self._rego
