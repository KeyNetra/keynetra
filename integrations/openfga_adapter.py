"""OpenFGA adapter with bidirectional tuple and model translation.

Translates between KeyNetra's relationship/auth model format and
OpenFGA's tuple-based authorization format. Supports import, export,
model translation, and evaluation delegation to an external OpenFGA server.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal

from integrations.interfaces import TupleRecord, TupleStoreAdapter
from keynetra.modeling.schema_parser import (
    AndExpr,
    AuthorizationSchema,
    Expr,
    IdentifierExpr,
    NotExpr,
    OrExpr,
    parse_authorization_schema,
)


@dataclass(frozen=True)
class OpenFGATuple:
    """A single OpenFGA relationship tuple."""
    user: str
    relation: str
    object: str
    condition: str | None = None

    def to_tuple_record(self) -> TupleRecord:
        return TupleRecord(
            subject=self.user,
            relation=self.relation,
            object=self.object,
        )

    @staticmethod
    def from_tuple_record(record: TupleRecord) -> OpenFGATuple:
        return OpenFGATuple(
            user=record.subject,
            relation=record.relation,
            object=record.object,
        )

    def to_dict(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {
            "user": self.user,
            "relation": self.relation,
            "object": self.object,
        }
        if self.condition:
            result["condition"] = self.condition
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> OpenFGATuple:
        return OpenFGATuple(
            user=str(data.get("user", "")),
            relation=str(data.get("relation", "")),
            object=str(data.get("object", "")),
            condition=str(data["condition"]) if data.get("condition") else None,
        )


@dataclass(frozen=True)
class OpenFGATypeDefinition:
    """An OpenFGA type definition (equivalent to a KeyNetra type)."""
    type: str
    relations: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class OpenFGAModel:
    """An OpenFGA authorization model."""
    schema_version: str
    type_definitions: list[OpenFGATypeDefinition]
    conditions: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "type_definitions": [
                {
                    "type": td.type,
                    "relations": td.relations,
                }
                for td in self.type_definitions
            ],
        }
        if self.conditions:
            result["conditions"] = self.conditions
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> OpenFGAModel:
        type_defs = [
            OpenFGATypeDefinition(
                type=td.get("type", ""),
                relations=td.get("relations", {}),
                metadata=td.get("metadata"),
            )
            for td in data.get("type_definitions", [])
        ]
        return OpenFGAModel(
            schema_version=str(data.get("schema_version", "1.1")),
            type_definitions=type_defs,
            conditions=data.get("conditions", {}),
        )


@dataclass(frozen=True)
class OpenFGACheckResult:
    """Result of an OpenFGA Check call."""
    allowed: bool
    resolution: str | None


class OpenFGATupleAdapter(TupleStoreAdapter):
    """Full OpenFGA tuple adapter with model support.

    Handles:
    - Tuple import/export in OpenFGA format
    - Translation between KeyNetra relationships and OpenFGA tuples
    - Authorization model translation from KeyNetra schema to OpenFGA
    - HTTP-based Check API calls against an OpenFGA server
    """

    def __init__(
        self,
        tuples: list[OpenFGATuple] | None = None,
        *,
        openfga_endpoint: str | None = None,
        openfga_store_id: str | None = None,
        openfga_bearer_token: str | None = None,
        model: OpenFGAModel | None = None,
    ) -> None:
        self._tuples: list[OpenFGATuple] = list(tuples or [])
        self._openfga_endpoint = openfga_endpoint
        self._openfga_store_id = openfga_store_id
        self._openfga_bearer_token = openfga_bearer_token
        self._model = model

    # ---- Core tuple operations ----

    def import_tuples(self, records: list[TupleRecord]) -> int:
        """Import TupleRecords as OpenFGA tuples."""
        count = 0
        for record in records:
            self._tuples.append(OpenFGATuple.from_tuple_record(record))
            count += 1
        return count

    def export_tuples(self) -> list[TupleRecord]:
        """Export all tuples as TupleRecords."""
        return [t.to_tuple_record() for t in self._tuples]

    def import_raw_tuples(self, raw_tuples: list[dict[str, Any]]) -> int:
        """Import tuples from raw dict format (OpenFGA JSON format)."""
        count = 0
        for raw in raw_tuples:
            self._tuples.append(OpenFGATuple.from_dict(raw))
            count += 1
        return count

    def export_raw_tuples(self) -> list[dict[str, Any]]:
        """Export tuples in OpenFGA JSON format."""
        return [t.to_dict() for t in self._tuples]

    # ---- KeyNetra relationship translation ----

    def import_from_keynetra_relationships(
        self,
        relationships: list[dict[str, Any]],
        *,
        default_type: str = "document",
    ) -> int:
        """Import KeyNetra relationship edges as OpenFGA tuples.

        KeyNetra relationship format:
          {"user_id": "...", "relation": "...", "resource_type": "...", "resource_id": "..."}

        OpenFGA tuple format:
          {"user": "user:<id>", "relation": "<relation>", "object": "<type>:<id>"}
        """
        count = 0
        for rel in relationships:
            user_id = rel.get("user_id", rel.get("subject_id", ""))
            relation = rel.get("relation", "")
            object_type = rel.get("resource_type", rel.get("object_type", default_type))
            object_id = rel.get("resource_id", rel.get("object_id", ""))

            if not user_id or not relation or not object_id:
                continue

            self._tuples.append(OpenFGATuple(
                user=f"user:{user_id}",
                relation=relation,
                object=f"{object_type}:{object_id}",
            ))
            count += 1
        return count

    def export_to_keynetra_relationships(self) -> list[dict[str, str]]:
        """Export OpenFGA tuples as KeyNetra relationship edges."""
        relationships: list[dict[str, str]] = []
        for t in self._tuples:
            # Parse OpenFGA "user:user_id" -> KeyNetra {user_id}
            user_id = t.user
            if t.user.startswith("user:"):
                user_id = t.user[5:]

            # Parse OpenFGA "type:id" -> KeyNetra {resource_type, resource_id}
            object_type = t.object
            object_id = t.object
            if ":" in t.object:
                object_type, object_id = t.object.split(":", 1)

            relationships.append({
                "user_id": user_id,
                "relation": t.relation,
                "resource_type": object_type,
                "resource_id": object_id,
            })
        return relationships

    # ---- Tuple CRUD operations ----

    def add_tuple(self, user: str, relation: str, object: str, condition: str | None = None) -> None:
        """Add a single tuple."""
        self._tuples.append(OpenFGATuple(user=user, relation=relation, object=object, condition=condition))

    def remove_tuple(self, user: str, relation: str, object: str) -> bool:
        """Remove the first matching tuple. Returns True if found and removed."""
        for i, t in enumerate(self._tuples):
            if t.user == user and t.relation == relation and t.object == object:
                self._tuples.pop(i)
                return True
        return False

    def list_tuples(
        self,
        *,
        user: str | None = None,
        relation: str | None = None,
        object: str | None = None,
    ) -> list[OpenFGATuple]:
        """List tuples, optionally filtered by user/relation/object."""
        result = list(self._tuples)
        if user is not None:
            result = [t for t in result if t.user == user]
        if relation is not None:
            result = [t for t in result if t.relation == relation]
        if object is not None:
            result = [t for t in result if t.object == object]
        return result

    def count(self) -> int:
        """Return the number of stored tuples."""
        return len(self._tuples)

    def clear(self) -> None:
        """Remove all tuples."""
        self._tuples.clear()

    # ---- Authorization model operations ----

    def import_model_from_keynetra_schema(self, schema: str | AuthorizationSchema) -> OpenFGAModel:
        """Convert a KeyNetra authorization schema to an OpenFGA model.

        KeyNetra schema format (from schema_parser.py):
          model schema 1
          type document
          relations
            owner: [user]
            editor: [user]
            viewer: [user]
          permissions
            read: owner or editor or viewer
            write: owner or editor
            delete: owner

        OpenFGA model format:
          {
            "schema_version": "1.1",
            "type_definitions": [
              {
                "type": "document",
                "relations": {
                  "owner": {"this": {}},
                  "editor": {"this": {}},
                  "viewer": {"this": {}},
                  "can_read": {
                    "union": {
                      "child": [
                        {"computedUserset": {"relation": "owner"}},
                        {"computedUserset": {"relation": "editor"}},
                        {"computedUserset": {"relation": "viewer"}},
                      ]
                    }
                  },
                  "can_write": {
                    "union": {
                      "child": [
                        {"computedUserset": {"relation": "owner"}},
                        {"computedUserset": {"relation": "editor"}},
                      ]
                    }
                  },
                  "can_delete": {
                    "computedUserset": {"relation": "owner"}
                  }
                }
              }
            ]
          }
        """
        if isinstance(schema, str):
            parsed = parse_authorization_schema(schema)
        else:
            parsed = schema

        # Build OpenFGA relations: direct relations are "this"
        relations: dict[str, dict[str, Any]] = {}
        for rel_name, _subjects in parsed.relations.items():
            relations[rel_name] = {"this": {}}

        # Build OpenFGA relations for permissions
        for perm_name, expr in parsed.permissions.items():
            fga_relation = self._permission_expr_to_openfga(expr, parsed)
            relations[f"can_{perm_name}"] = fga_relation

        type_definitions = [
            OpenFGATypeDefinition(
                type=type_name,
                relations=relations,
            )
            for type_name in parsed.types
        ]

        if not type_definitions and relations:
            # If no explicit types but we have relations, create a default type
            type_definitions.append(
                OpenFGATypeDefinition(
                    type="default",
                    relations=relations,
                )
            )

        self._model = OpenFGAModel(
            schema_version="1.1",
            type_definitions=type_definitions,
        )
        return self._model

    def _permission_expr_to_openfga(self, expr: Expr, schema: AuthorizationSchema) -> dict[str, Any]:
        """Convert a KeyNetra permission expression to OpenFGA relation definition.

        Flattens nested union/intersection chains (e.g. a or b or c becomes a
        single union with 3 children, not nested unions).
        """
        if isinstance(expr, IdentifierExpr):
            return {"computedUserset": {"relation": expr.name}}

        if isinstance(expr, NotExpr):
            inner = self._permission_expr_to_openfga(expr.value, schema)
            return {"not": inner}

        if isinstance(expr, OrExpr):
            children = list(self._flatten_or_children(expr, schema))
            return {
                "union": {
                    "child": children,
                }
            }

        if isinstance(expr, AndExpr):
            children = list(self._flatten_and_children(expr, schema))
            return {
                "intersection": {
                    "child": children,
                }
            }

        raise ValueError(f"Unknown expression type: {type(expr)}")

    def _flatten_or_children(self, expr: Expr, schema: AuthorizationSchema) -> list[dict[str, Any]]:
        """Flatten nested OrExpr into a flat list of children."""
        children: list[dict[str, Any]] = []
        if isinstance(expr, OrExpr):
            children.extend(self._flatten_or_children(expr.left, schema))
            children.extend(self._flatten_or_children(expr.right, schema))
        elif isinstance(expr, AndExpr):
            children.append(self._permission_expr_to_openfga(expr, schema))
        else:
            children.append(self._permission_expr_to_openfga(expr, schema))
        return children

    def _flatten_and_children(self, expr: Expr, schema: AuthorizationSchema) -> list[dict[str, Any]]:
        """Flatten nested AndExpr into a flat list of children."""
        children: list[dict[str, Any]] = []
        if isinstance(expr, AndExpr):
            children.extend(self._flatten_and_children(expr.left, schema))
            children.extend(self._flatten_and_children(expr.right, schema))
        elif isinstance(expr, OrExpr):
            children.append(self._permission_expr_to_openfga(expr, schema))
        else:
            children.append(self._permission_expr_to_openfga(expr, schema))
        return children

    def export_model_to_keynetra_schema(self) -> str:
        """Convert the stored OpenFGA model back to KeyNetra schema format."""
        if not self._model:
            return ""

        schema_lines: list[str] = []
        schema_lines.append("model schema 1")

        for td in self._model.type_definitions:
            schema_lines.append(f"type {td.type}")

            # Extract direct relations (non-permission relations)
            direct_relations = {
                name: info
                for name, info in td.relations.items()
                if not name.startswith("can_")
            }
            if direct_relations:
                schema_lines.append("relations")
                for name, info in direct_relations.items():
                    schema_lines.append(f"  {name}: [user]")

            # Extract permissions
            permissions = {
                name[4:]: info  # strip "can_" prefix
                for name, info in td.relations.items()
                if name.startswith("can_")
            }
            if permissions:
                schema_lines.append("permissions")
                for perm_name, info in permissions.items():
                    expr_text = self._openfga_relation_to_expr_text(info, td)
                    schema_lines.append(f"  {perm_name}: {expr_text}")

        return "\n".join(schema_lines)

    def _openfga_relation_to_expr_text(self, rel_def: dict[str, Any], td: OpenFGATypeDefinition) -> str:
        """Convert an OpenFGA relation definition back to KeyNetra expression text."""
        if "this" in rel_def:
            return "self"

        if "computedUserset" in rel_def:
            return rel_def["computedUserset"]["relation"]

        if "union" in rel_def:
            children = rel_def["union"].get("child", [])
            parts = [self._openfga_relation_to_expr_text(c, td) for c in children]
            return " or ".join(parts)

        if "intersection" in rel_def:
            children = rel_def["intersection"].get("child", [])
            parts = [self._openfga_relation_to_expr_text(c, td) for c in children]
            return " and ".join(parts)

        if "not" in rel_def:
            inner = self._openfga_relation_to_expr_text(rel_def["not"], td)
            return f"not {inner}"

        return "unknown"

    # ---- OpenFGA Check API ----

    def check_via_openfga(
        self,
        user: str,
        relation: str,
        object: str,
        *,
        context: dict[str, Any] | None = None,
        timeout: int = 10,
    ) -> OpenFGACheckResult:
        """Perform an access check against the OpenFGA Check API.

        Requires openfga_endpoint and openfga_store_id to be configured.
        """
        if not self._openfga_endpoint:
            raise RuntimeError(
                "OpenFGA endpoint not configured. Set openfga_endpoint in constructor."
            )
        if not self._openfga_store_id:
            raise RuntimeError(
                "OpenFGA store ID not configured. Set openfga_store_id in constructor."
            )

        url = f"{self._openfga_endpoint.rstrip('/')}/stores/{self._openfga_store_id}/check"
        body: dict[str, Any] = {
            "tuple_key": {
                "user": user,
                "relation": relation,
                "object": object,
            },
        }
        if context:
            body["context"] = context
        if self._openfga_bearer_token:
            body["authorization"] = f"Bearer {self._openfga_bearer_token}"

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._openfga_bearer_token:
            req.add_header("Authorization", f"Bearer {self._openfga_bearer_token}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            raise RuntimeError(f"OpenFGA Check API call failed: {e}") from e

        allowed = result.get("allowed", False)
        resolution = result.get("resolution")
        return OpenFGACheckResult(allowed=bool(allowed), resolution=str(resolution) if resolution else None)

    def check_locally(self, user: str, relation: str, object: str) -> bool:
        """Perform a local tuple lookup check.

        Simple check: does a tuple (user, relation, object) exist in our store?
        This is a simplified check that doesn't walk the relationship graph
        like OpenFGA does. For full graph evaluation, use check_via_openfga().
        """
        for t in self._tuples:
            if t.user == user and t.relation == relation and t.object == object:
                return True
        return False

    # ---- KeyNetra check translation ----

    def keynetra_check_to_openfga(
        self,
        *,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> OpenFGACheckResult:
        """Translate a KeyNetra access check to an OpenFGA check.

        Converts KeyNetra semantics (user, action, resource) to
        OpenFGA semantics (user, relation, object) and performs a local check.
        """
        openfga_user = f"user:{user_id}"
        openfga_object = f"{resource_type}:{resource_id}"
        # Actions map to "can_<action>" relations in OpenFGA
        openfga_relation = f"can_{action}" if not action.startswith("can_") else action

        allowed = self.check_locally(openfga_user, openfga_relation, openfga_object)
        return OpenFGACheckResult(
            allowed=allowed,
            resolution="LOCAL_TUPLE_LOOKUP" if allowed else "NO_MATCHING_TUPLE",
        )

    # ---- Model CRUD via OpenFGA API ----

    def write_model_via_openfga(self) -> dict[str, Any]:
        """Write the current authorization model to the OpenFGA API."""
        if not self._openfga_endpoint:
            raise RuntimeError("OpenFGA endpoint not configured.")
        if not self._openfga_store_id:
            raise RuntimeError("OpenFGA store ID not configured.")
        if not self._model:
            raise RuntimeError("No model to write. Import a model first.")

        url = f"{self._openfga_endpoint.rstrip('/')}/stores/{self._openfga_store_id}/authorization-models"

        req = urllib.request.Request(
            url,
            data=json.dumps(self._model.to_dict()).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._openfga_bearer_token:
            req.add_header("Authorization", f"Bearer {self._openfga_bearer_token}")

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to write model to OpenFGA: {e}") from e

    def write_tuples_via_openfga(self) -> dict[str, Any]:
        """Write all stored tuples to the OpenFGA Write API."""
        if not self._openfga_endpoint:
            raise RuntimeError("OpenFGA endpoint not configured.")
        if not self._openfga_store_id:
            raise RuntimeError("OpenFGA store ID not configured.")
        if not self._tuples:
            return {"written": 0}

        url = f"{self._openfga_endpoint.rstrip('/')}/stores/{self._openfga_store_id}/write"

        writes = [t.to_dict() for t in self._tuples]
        body = {"writes": {"tuple_keys": writes}}

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._openfga_bearer_token:
            req.add_header("Authorization", f"Bearer {self._openfga_bearer_token}")

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to write tuples to OpenFGA: {e}") from e

    def __repr__(self) -> str:
        model_status = "loaded" if self._model else "none"
        return (
            f"OpenFGATupleAdapter(tuples={len(self._tuples)}, "
            f"model={model_status}, "
            f"openfga={'connected' if self._openfga_endpoint else 'local'})"
        )