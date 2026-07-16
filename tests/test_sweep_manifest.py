from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pytest

from sweep import manifest as manifest_module
from sweep.manifest import (
    FindingInput,
    ManifestIdentityError,
    PrototypeMigration,
    build_diff,
    build_manifest,
    read_manifest,
    write_manifest,
)
from sweep.schemas import SchemaValidationError, validate_diff, validate_manifest


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
REVISION = "29352227a54428c3c574be9514ccbcc9ade67895"
PROTOTYPE_ORACLE = Path(__file__).parent / "fixtures" / "sweep" / "prototype-oracle"


def _provider(
    *,
    tool_version: str = "1.0",
    provider: str = "ruff",
    language: str = "python",
    path: str = "src",
    case_sensitive: bool = True,
):
    return {
        "schema_version": 1,
        "provider": provider,
        "language": language,
        "provider_kind": "native",
        "scope": {
            "paths": [path],
            "case_sensitive": case_sensitive,
            "roots": [path],
            "exclusions": [],
        },
        "command": {
            "executable": provider,
            "argv": [provider, "check", "src"],
            "timeout_seconds": 30,
            "output_format": "json",
            "output_byte_limit": 1_048_576,
        },
        "tool_version": tool_version,
        "exit": {"code": 0, "classification": "clean"},
        "raw": {
            "stdout_sha256": EMPTY_SHA256,
            "stderr_sha256": EMPTY_SHA256,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
        },
        "status": "completed",
        "failure": None,
    }


def _finding(**overrides) -> FindingInput:
    values = {
        "provider": "ruff",
        "language": "python",
        "native_rule_id": "F401",
        "rule_semantic_key": "F401:v1",
        "path": "src/example.py",
        "semantic_anchor": "native:F401:unused-import",
        "native_severity": "error",
        "severity": 2,
        "line": 10,
        "column": 2,
        "end_line": 10,
        "end_column": 8,
        "message": "unused import",
        "summary": "Unused import",
        "metrics": {"count": 1},
        "observation_index": 0,
    }
    values.update(overrides)
    return FindingInput(**values)


def _manifest(
    findings,
    *,
    case_sensitive: bool = True,
    tool_version: str = "1.0",
    repo_root: Path | None = None,
):
    return build_manifest(
        capability_registry_version=1,
        paths=["src"],
        case_sensitive=case_sensitive,
        roots=["src"],
        exclusions=[],
        source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=[_provider(tool_version=tool_version, case_sensitive=case_sensitive)],
        findings=findings,
        repo_root=repo_root,
    )


def test_im_3_anonymous_occurrences_follow_source_order_for_every_input_permutation():
    findings = [
        _finding(line=line, end_line=line, message=f"anonymous occurrence at {line}")
        for line in (40, 10, 30, 20)
    ]

    expected = None
    for permutation in itertools.permutations(findings):
        manifest = _manifest(permutation)
        observed = [
            (row["location"]["line"], row["identity"]["occurrence"], row["id"])
            for row in manifest["findings"]
        ]
        if expected is None:
            expected = observed
        assert observed == expected

    assert [(line, occurrence) for line, occurrence, _ in expected] == [
        (10, 0),
        (20, 1),
        (30, 2),
        (40, 3),
    ]


def test_im_3_digest_collision_with_unequal_payloads_is_rejected(monkeypatch):
    monkeypatch.setattr(manifest_module, "_finding_identifier", lambda identity: "f2_" + "a" * 24)

    with pytest.raises(ManifestIdentityError, match="digest collision"):
        _manifest(
            [
                _finding(path="src/one.py", semantic_anchor="function:one"),
                _finding(path="src/two.py", semantic_anchor="function:two"),
            ]
        )


def test_im_3_case_policy_is_required_recorded_and_never_machine_inferred():
    with pytest.raises(TypeError, match="case_sensitive"):
        build_manifest(
            capability_registry_version=1,
            paths=["src"],
            roots=["src"],
            exclusions=[],
            source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
            providers=[_provider()],
            findings=[_finding()],
        )

    insensitive_upper = _manifest([_finding(path="src/Example.py")], case_sensitive=False)
    insensitive_lower = _manifest([_finding(path="src/example.py")], case_sensitive=False)
    sensitive_upper = _manifest([_finding(path="src/Example.py")], case_sensitive=True)
    sensitive_lower = _manifest([_finding(path="src/example.py")], case_sensitive=True)

    assert insensitive_upper["scope"]["case_sensitive"] is False
    assert insensitive_upper["findings"][0]["identity"]["path"] == "src/example.py"
    assert insensitive_upper["findings"][0]["id"] == insensitive_lower["findings"][0]["id"]
    assert sensitive_upper["findings"][0]["id"] != sensitive_lower["findings"][0]["id"]


def test_im_3_tool_upgrade_preserves_identity_but_semantic_rule_revision_does_not():
    before = _manifest([_finding()], tool_version="1.0")
    upgraded = _manifest([_finding(line=999, end_line=999)], tool_version="2.0")
    semantic_change = _manifest([_finding(rule_semantic_key="F401:v2")], tool_version="2.0")

    old_id = before["findings"][0]["id"]
    assert upgraded["findings"][0]["id"] == old_id
    assert semantic_change["findings"][0]["native_rule_id"] == "F401"
    assert semantic_change["findings"][0]["id"] != old_id
    assert build_diff(before, upgraded)["persisting"] == [old_id]
    changed = build_diff(before, semantic_change)
    assert changed["fixed"] == [old_id]
    assert changed["new"] == [semantic_change["findings"][0]["id"]]


def test_im_3_writer_emits_only_valid_canonical_schema_1(tmp_path):
    destination = tmp_path / "nested" / "manifest.json"
    built = _manifest([_finding()])

    written = write_manifest(destination, built)

    assert written == built
    assert json.loads(destination.read_text(encoding="utf-8")) == built
    assert destination.read_bytes().endswith(b"\n")
    assert destination.read_bytes().count(b"\n") == 1
    assert validate_manifest(built) == built
    assert built["schema_version"] == 1
    assert built["finding_id_schema"] == 2
    assert built["hashes"]["semantic"] != built["hashes"]["artifacts"]


def test_im_4_normalized_paths_persist_and_renames_require_a_unique_alias(tmp_path):
    before = _manifest([_finding(path="src/./example.py")], repo_root=tmp_path)
    old_id = before["findings"][0]["id"]
    after = _manifest(
        [_finding(path="src/domain/example.py", legacy_ids=(old_id,))], repo_root=tmp_path
    )

    diff = validate_diff(build_diff(before, after))

    assert before["findings"][0]["identity"]["path"] == "src/example.py"
    assert diff["fixed"] == []
    assert diff["new"] == []
    assert diff["persisting"] == [after["findings"][0]["id"]]


@pytest.mark.parametrize("case_sensitive, expected", [(True, "changed"), (False, "persisting")])
def test_im_4_case_only_path_change_obeys_manifest_policy(case_sensitive, expected):
    before = _manifest([_finding(path="src/Example.py")], case_sensitive=case_sensitive)
    after = _manifest([_finding(path="src/example.py")], case_sensitive=case_sensitive)
    diff = build_diff(before, after)

    if expected == "persisting":
        assert diff["fixed"] == diff["new"] == []
        assert len(diff["persisting"]) == 1
    else:
        assert len(diff["fixed"]) == len(diff["new"]) == 1
        assert diff["persisting"] == []


def test_im_4_duplicate_and_ambiguous_aliases_are_rejected_without_deduplication():
    old_id = _manifest([_finding()])["findings"][0]["id"]

    with pytest.raises(ManifestIdentityError, match="duplicate legacy alias"):
        _manifest([_finding(path="src/new.py", legacy_ids=(old_id, old_id))])

    with pytest.raises(ManifestIdentityError, match="ambiguous legacy alias"):
        _manifest(
            [
                _finding(path="src/one.py", semantic_anchor="function:one", legacy_ids=(old_id,)),
                _finding(path="src/two.py", semantic_anchor="function:two", legacy_ids=(old_id,)),
            ]
        )


def test_im_4_schema_1_reader_rejects_aliases_that_bypass_the_writer():
    document = _manifest(
        [
            _finding(path="src/one.py", semantic_anchor="function:one"),
            _finding(path="src/two.py", semantic_anchor="function:two"),
        ]
    )
    first_id, second_id = [row["id"] for row in document["findings"]]
    document["findings"][0]["legacy_ids"] = [second_id]
    with pytest.raises(SchemaValidationError, match="current finding id"):
        validate_manifest(document)

    document["findings"][0]["legacy_ids"] = ["111111111111"]
    document["findings"][1]["legacy_ids"] = ["111111111111"]
    with pytest.raises(SchemaValidationError, match="claimed by multiple findings"):
        validate_manifest(document)


def test_im_4_cross_payload_and_cyclic_aliases_are_rejected():
    before = _manifest([_finding()])
    old_id = before["findings"][0]["id"]
    cross_payload = _manifest(
        [
            _finding(
                path="src/renamed.py",
                semantic_anchor="different:anchor",
                legacy_ids=(old_id,),
            )
        ]
    )
    with pytest.raises(ManifestIdentityError, match="cross-payload"):
        build_diff(before, cross_payload)

    first_after = _manifest([_finding(path="src/renamed.py", legacy_ids=(old_id,))])
    new_id = first_after["findings"][0]["id"]
    cyclic_before = _manifest([_finding(legacy_ids=(new_id,))])
    cyclic_after = _manifest([_finding(path="src/renamed.py", legacy_ids=(old_id,))])
    with pytest.raises(ManifestIdentityError, match="cyclic"):
        build_diff(cyclic_before, cyclic_after)

    before_plain = _manifest(
        [
            _finding(path="src/a.py"),
            _finding(path="src/c.py"),
        ]
    )
    after_plain = _manifest(
        [
            _finding(path="src/b.py"),
            _finding(path="src/d.py"),
        ]
    )
    old_a, old_c = [row["id"] for row in before_plain["findings"]]
    new_b, new_d = [row["id"] for row in after_plain["findings"]]
    long_cycle_before = _manifest(
        [
            _finding(path="src/a.py", legacy_ids=(new_b,)),
            _finding(path="src/c.py", legacy_ids=(new_d,)),
        ]
    )
    long_cycle_after = _manifest(
        [
            _finding(path="src/b.py", legacy_ids=(old_c,)),
            _finding(path="src/d.py", legacy_ids=(old_a,)),
        ]
    )
    with pytest.raises(ManifestIdentityError, match="cyclic"):
        build_diff(long_cycle_before, long_cycle_after)


def test_im_4_prototype_read_migrates_to_v2_and_all_writes_are_new_schema(tmp_path):
    prototype = {
        "target": "/workspace/repo",
        "scope": ["src"],
        "counts": {"cx": 1},
        "total": 1,
        "errors": {},
        "findings": [
            {
                "id": "011a6cd88c34",
                "rule": "cx:nested-loop",
                "path": "src/example.py",
                "symbol": "nested_lookup",
                "severity": 3,
                "summary": "nested loop",
                "line": 9,
            }
        ],
    }
    prototype_path = tmp_path / "prototype.json"
    prototype_path.write_text(json.dumps(prototype), encoding="utf-8")
    migration = PrototypeMigration(
        capability_registry_version=1,
        case_sensitive=True,
        roots=("src",),
        exclusions=(),
        source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=(
            _provider(
                provider="cx",
                language="python",
                path=prototype["scope"][0],
            ),
        ),
        language_by_provider={"cx": "python"},
        semantic_rule_versions={"cx:nested-loop": 1},
    )

    migrated = read_manifest(prototype_path, prototype_migration=migration)
    destination = tmp_path / "manifest.json"
    write_manifest(destination, migrated)

    assert migrated["schema_version"] == 1
    assert migrated["finding_id_schema"] == 2
    assert migrated["findings"][0]["legacy_ids"] == ["011a6cd88c34"]
    assert migrated["findings"][0]["rule_semantic_key"] == "cx:nested-loop:v1"
    assert read_manifest(destination) == migrated
    assert json.loads(destination.read_text(encoding="utf-8"))["schema_version"] == 1


def test_im_4_copied_prototype_oracle_migrates_every_finding_with_its_v1_alias():
    prototype = json.loads(
        PROTOTYPE_ORACLE.joinpath("prototype-manifest.json").read_text(encoding="utf-8")
    )
    versions = {row["rule"]: 1 for row in prototype["findings"]}
    migration = PrototypeMigration(
        capability_registry_version=1,
        case_sensitive=True,
        roots=tuple(prototype["scope"]),
        exclusions=(),
        source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=(
            _provider(
                provider="cx",
                language="python",
                path=prototype["scope"][0],
            ),
        ),
        language_by_provider={"cx": "python"},
        semantic_rule_versions=versions,
    )

    migrated = read_manifest(
        PROTOTYPE_ORACLE / "prototype-manifest.json",
        prototype_migration=migration,
    )

    assert migrated["total"] == prototype["total"] == 6
    assert {alias for row in migrated["findings"] for alias in row["legacy_ids"]} == {
        row["id"] for row in prototype["findings"]
    }


def test_im_4_manifest_version_gate_never_false_deduplicates(tmp_path):
    current = _manifest([_finding()])
    current_path = tmp_path / "current.json"
    current_path.write_text(json.dumps(current), encoding="utf-8")
    assert read_manifest(current_path) == current

    tampered = copy.deepcopy(current)
    tampered["findings"][0]["message"] = "changed without rebinding the manifest hash"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(SchemaValidationError, match="canonical manifest content"):
        read_manifest(tampered_path)

    future = copy.deepcopy(current)
    future["schema_version"] = 2
    future_path = tmp_path / "future.json"
    future_path.write_text(json.dumps(future), encoding="utf-8")
    with pytest.raises(SchemaValidationError, match="schema_version must be 1"):
        read_manifest(future_path)

    prototype_path = tmp_path / "prototype.json"
    prototype_path.write_text(
        json.dumps({"target": "/repo", "scope": [], "counts": {}, "total": 0, "errors": {}, "findings": []}),
        encoding="utf-8",
    )
    with pytest.raises(SchemaValidationError, match="explicit migration mode"):
        read_manifest(prototype_path)
