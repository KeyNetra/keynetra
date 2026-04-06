from __future__ import annotations

from dataclasses import dataclass, field

from integrations.interfaces import TupleRecord, TupleStoreAdapter


@dataclass
class InMemoryOpenFGATupleAdapter(TupleStoreAdapter):
    """Starter adapter for OpenFGA tuple import/export workflows."""

    tuples: list[TupleRecord] = field(default_factory=list)

    def import_tuples(self, tuples: list[TupleRecord]) -> int:
        self.tuples.extend(tuples)
        return len(tuples)

    def export_tuples(self) -> list[TupleRecord]:
        return list(self.tuples)
