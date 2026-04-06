from __future__ import annotations

import json
from pathlib import Path

import pytest

from keynetra.config.file_loaders import (
    load_authorization_model_from_file,
    load_authorization_model_from_paths,
    load_policies_from_file,
    load_policies_from_paths,
)


def test_load_policies_from_paths_supports_direct_file_path(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        "allow:\n  action: read\n  priority: 10\n  when:\n    role: admin\n",
        encoding="utf-8",
    )

    policies = load_policies_from_paths([str(policy_file)])

    assert len(policies) == 1
    assert policies[0]["action"] == "read"


def test_load_policies_from_file_rejects_unsupported_extension(tmp_path: Path) -> None:
    bad_file = tmp_path / "policies.txt"
    bad_file.write_text("not supported", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported policy format"):
        load_policies_from_file(bad_file)


def test_load_policies_from_file_rejects_invalid_payload_and_policy_shapes(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text('value: "missing action and effect"', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid policy payload"):
        load_policies_from_file(invalid)

    bad_block = tmp_path / "bad_block.yaml"
    bad_block.write_text("allow: []", encoding="utf-8")
    with pytest.raises(ValueError, match="policy block must be an object"):
        load_policies_from_file(bad_block)

    missing_action = tmp_path / "missing_action.yaml"
    missing_action.write_text("allow:\n  priority: 10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="policy action is required"):
        load_policies_from_file(missing_action)

    bad_conditions = tmp_path / "bad_conditions.yaml"
    bad_conditions.write_text("allow:\n  action: read\n  when: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="policy conditions must be an object"):
        load_policies_from_file(bad_conditions)


def test_load_policies_from_file_rejects_invalid_polar_lines(tmp_path: Path) -> None:
    bad_effect = tmp_path / "bad_effect.polar"
    bad_effect.write_text("maybe action=read\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid .polar rule"):
        load_policies_from_file(bad_effect)

    bad_token = tmp_path / "bad_token.polar"
    bad_token.write_text("allow action=read role\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid .polar token"):
        load_policies_from_file(bad_token)

    missing_action = tmp_path / "missing_action.polar"
    missing_action.write_text("allow role=admin\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing action in .polar rule"):
        load_policies_from_file(missing_action)


def test_load_authorization_model_from_paths_supports_txt_and_schema_files(tmp_path: Path) -> None:
    schema_txt = tmp_path / "model.txt"
    schema_txt.write_text("model schema 1\n", encoding="utf-8")

    schema = load_authorization_model_from_paths([str(schema_txt)])
    assert schema == "model schema 1"

    empty_txt = tmp_path / "empty.txt"
    empty_txt.write_text("   \n", encoding="utf-8")
    assert load_authorization_model_from_paths([str(empty_txt)]) is None


def test_load_authorization_model_from_file_supports_json_string_and_rejects_non_object(
    tmp_path: Path,
) -> None:
    as_string = tmp_path / "model.json"
    as_string.write_text(json.dumps("model schema 2"), encoding="utf-8")
    assert load_authorization_model_from_file(as_string) == "model schema 2"

    blank_string = tmp_path / "blank.json"
    blank_string.write_text(json.dumps("   "), encoding="utf-8")
    with pytest.raises(ValueError, match="authorization model file is empty"):
        load_authorization_model_from_file(blank_string)

    not_object = tmp_path / "number.json"
    not_object.write_text(json.dumps(42), encoding="utf-8")
    with pytest.raises(ValueError, match="must contain an object"):
        load_authorization_model_from_file(not_object)


def test_load_authorization_model_from_file_rejects_invalid_model_shapes(tmp_path: Path) -> None:
    invalid_model = tmp_path / "invalid_model.yaml"
    invalid_model.write_text("model: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="model must be an object"):
        load_authorization_model_from_file(invalid_model)

    bad_relations = tmp_path / "bad_relations.yaml"
    bad_relations.write_text(
        "model:\n  relations: owner\n  permissions:\n    read: owner\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="relations and permissions must be objects"):
        load_authorization_model_from_file(bad_relations)

    bad_subjects = tmp_path / "bad_subjects.yaml"
    bad_subjects.write_text(
        "model:\n  relations:\n    owner: 1\n  permissions:\n    read: owner\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid relation subjects for owner"):
        load_authorization_model_from_file(bad_subjects)


def test_load_authorization_model_from_file_rejects_unsupported_extension(tmp_path: Path) -> None:
    unsupported = tmp_path / "model.schema"
    unsupported.write_text("model schema 1", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported authorization model format"):
        load_authorization_model_from_file(unsupported)
