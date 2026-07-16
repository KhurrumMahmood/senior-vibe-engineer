from __future__ import annotations

import pytest

from _lib.finding_identity import FindingIdentity, finding_record, normalize_repo_path


def _identity(**overrides) -> FindingIdentity:
    values = {
        "provider": "ecosystem",
        "rule": "stringly-state",
        "language": "typescript",
        "path": "src/state.ts",
        "semantic_anchor": "function:transition/property:status",
    }
    values.update(overrides)
    return FindingIdentity(**values)


def test_line_movement_and_tool_version_do_not_change_id():
    identity = _identity()

    before = finding_record(identity, tool_version="1.0", line=10)
    after = finding_record(identity, tool_version="2.0", line=400)

    assert before["id"] == after["id"]


def test_missing_symbol_multiplicity_uses_anchor_then_occurrence():
    first = _identity(semantic_anchor="anonymous:if/status", occurrence=0)
    second_anchor = _identity(semantic_anchor="anonymous:switch/status", occurrence=0)
    repeated = _identity(semantic_anchor="anonymous:if/status", occurrence=1)

    assert len({first.identifier(), second_anchor.identifier(), repeated.identifier()}) == 3


def test_language_and_provider_namespaces_prevent_mixed_host_collisions():
    typescript = _identity(language="typescript", provider="ast-grep")
    python = _identity(language="python", provider="python-ast")
    other_provider = _identity(language="typescript", provider="native-compiler")

    assert len({typescript.identifier(), python.identifier(), other_provider.identifier()}) == 3


def test_case_policy_is_explicit_and_reproducible():
    sensitive_a = _identity(path="src/State.ts", case_sensitive=True)
    sensitive_b = _identity(path="src/state.ts", case_sensitive=True)
    insensitive_a = _identity(path="src/State.ts", case_sensitive=False)
    insensitive_b = _identity(path="src/state.ts", case_sensitive=False)

    assert sensitive_a.identifier() != sensitive_b.identifier()
    assert insensitive_a.identifier() == insensitive_b.identifier()


def test_rename_or_move_intentionally_changes_id_and_can_carry_legacy_alias():
    before = _identity(path="src/state.ts")
    after = _identity(path="src/domain/state.ts")

    record = finding_record(after, tool_version="1.0", legacy_ids=[before.identifier()])

    assert record["id"] != before.identifier()
    assert record["legacy_ids"] == [before.identifier()]


def test_path_normalization_rejects_escape_and_supports_repo_absolute(tmp_path):
    path = tmp_path / "src" / "state.ts"
    path.parent.mkdir()
    path.write_text("", encoding="utf-8")

    assert normalize_repo_path(path, repo_root=tmp_path) == "src/state.ts"
    with pytest.raises(ValueError, match="inside the repository"):
        normalize_repo_path("../outside.ts")
