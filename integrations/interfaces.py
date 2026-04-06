from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TupleRecord:
    subject: str
    relation: str
    object: str


class TupleStoreAdapter(Protocol):
    def import_tuples(self, tuples: list[TupleRecord]) -> int: ...

    def export_tuples(self) -> list[TupleRecord]: ...


class PolicyAdapter(Protocol):
    def import_policies(self, payload: str) -> int: ...

    def export_policies(self) -> str: ...


class TerraformResourceAdapter(Protocol):
    def plan(self) -> dict[str, object]: ...

    def apply(self) -> dict[str, object]: ...
