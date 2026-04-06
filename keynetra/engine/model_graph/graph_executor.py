"""Graph execution helpers for permission graphs."""

from __future__ import annotations

from keynetra.engine.model_graph.permission_graph import (
    CompiledPermissionGraph,
)


def execute_permission_graph(graph: CompiledPermissionGraph, authorization_input):
    return graph.evaluate(authorization_input)
