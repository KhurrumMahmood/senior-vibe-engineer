"""Accepted-evidence-only final outcomes for the two C structure proposals."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
CLANG = Path(shutil.which("clang") or "")
CLANGD = Path(shutil.which("clangd") or "")
MAKE = Path(shutil.which("make") or "")
BOUNDARY_FIXTURE = ROOT / "tests/fixtures/c-structure-proposals/boundary/host"
FOLDER_FIXTURE = BOUNDARY_FIXTURE
MAP = ROOT / ".claude/skills/map-subsystem/scripts/map_c.py"
OMNIBUS = ROOT / ".claude/skills/find-omnibus/scripts/run_c.py"
TOPOLOGY = ROOT / ".claude/skills/find-folder-topology-drift/scripts/detect_c.py"
BOUNDARY = ROOT / ".claude/skills/propose-boundary/scripts/propose_c.py"
FOLDER = ROOT / ".claude/skills/propose-folder-reorganization/scripts/propose_c.py"


def _clang_21() -> bool:
    if not CLANG.is_file():
        return False
    result = subprocess.run(
        [CLANG, "--version"], capture_output=True, text=True, check=False
    )
    match = re.search(r"(?:Apple )?clang version (\d+)\.(\d+)\.(\d+)", result.stdout)
    return bool(match and tuple(map(int, match.groups())) >= (21, 0, 0))


pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, CLANGD, MAKE)) or not _clang_21(),
    reason="frozen product Python, Clang/clangd 21+, and Make are required",
)


def _run(
    *args: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): _sha256(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and (path.suffix in {".c", ".i", ".h", ".inc"} or path.name == "Makefile")
        and not any(part in {"reports", ".native-build"} for part in path.relative_to(host).parts)
    }


def _copy(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    return destination


def _compile_database(host: Path) -> None:
    _run(MAKE, "clean", "compile-db", f"CC={CLANG}", cwd=host)


def _map(host: Path, name: str) -> Path:
    evidence = host / f"reports/map/{name}/c-map.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        MAP,
        "--name",
        name,
        "--target",
        ".",
        "--project-root",
        host,
        "--output",
        host / f".engineering/docs/subsystems/{name}.md",
        "--evidence",
        evidence,
        "--clang",
        CLANG,
        "--clangd",
        CLANGD,
        cwd=host,
    )
    assert _json(evidence)["status"] == "complete"
    return evidence


def _native_obligations(smoke: str, test_stdout: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "compile-database",
            "argv": ["make", "clean", "compile-db", "CC=clang"],
            "expected_returncode": 0,
        },
        {
            "name": "native-test",
            "argv": ["make", "test", "CC=clang"],
            "expected_returncode": 0,
            "expected_stdout_contains": test_stdout,
        },
        {
            "name": "smoke",
            "argv": [smoke],
            "expected_returncode": 0,
        },
    ]


def _acceptance(
    host: Path,
    *,
    consumer: str,
    decision: str,
    artifacts: dict[str, Path],
    selection: dict[str, Any],
    smoke: str,
    smoke_stdout: str,
    test_stdout: str,
) -> Path:
    obligations = _native_obligations(smoke, test_stdout)
    obligations[-1]["expected_stdout"] = smoke_stdout
    payload: dict[str, Any] = {
        "schema_version": "c-structure-accepted-evidence-v1",
        "consumer": consumer,
        "decision": decision,
        "artifacts": [
            {
                "kind": kind,
                "path": path.relative_to(host).as_posix(),
                "sha256": _sha256(path),
            }
            for kind, path in sorted(artifacts.items())
        ],
        "source_hashes": [
            {"path": path, "sha256": digest}
            for path, digest in _source_hashes(host).items()
        ],
        "selection": selection,
        "human_verdict": {
            "status": "accepted",
            "reviewer": "c-structure-fixture-owner",
            "reviewed_boundaries": [
                "function pointers and callbacks",
                "ABI and object layout",
                "external consumers and alternate build variants",
            ],
        },
        "native_obligations": obligations,
    }
    payload["acceptance_hash"] = _canonical_hash(payload)
    return _write_json(
        host / f"reports/accepted/{consumer}/{decision}/acceptance.json", payload
    )


def _boundary_inputs(host: Path, decision: str = "extract_boundary") -> tuple[Path, Path, Path]:
    _compile_database(host)
    map_evidence = _map(host, "boundary")
    omnibus_dir = host / "reports/omnibus/c"
    _run(
        PYTHON,
        "-I",
        "-S",
        OMNIBUS,
        "--project-root",
        host,
        "--target",
        "src/legacy.c",
        "--output-dir",
        omnibus_dir,
        "--scout-dir",
        host / "c-scouts",
        "--clang",
        CLANG,
        cwd=host,
    )
    omnibus = omnibus_dir / "findings.json"
    assert _json(omnibus)["findings"][0]["bucket"] == "confirmed_omnibus"
    selection: dict[str, Any] = {
        "candidate_id": "candidate-001",
        "target": "src/legacy.c",
        "domain": "export",
        "declarations": ["render_export", "write_export"],
        "public_header": "include/cproposal/legacy.h",
        "new_public_header": "include/cproposal/export.h",
        "new_translation_unit": "src/legacy_export.c",
        "caller_impact": [
            {
                "path": "src/main.c",
                "symbol": "render_export",
                "impact": "legacy compatibility header preserves spelling",
            },
            {
                "path": "tests/native_test.c",
                "symbol": "write_export",
                "impact": "legacy compatibility header preserves spelling",
            },
        ],
        "include_impact": [
            {
                "path": "include/cproposal/legacy.h",
                "before": "int render_export(void);\nint write_export(void);",
                "after": "#include \"cproposal/export.h\"",
            },
            {
                "path": "src/legacy_export.c",
                "after": "#include \"cproposal/export.h\"",
            },
        ],
        "make_impact": [
            {
                "path": "Makefile",
                "before": "SOURCES = src/legacy.c src/billing_parser.c src/billing_types.c src/billing_validator.c src/main.c",
                "after": "SOURCES = src/legacy.c src/legacy_export.c src/billing_parser.c src/billing_types.c src/billing_validator.c src/main.c",
            },
            {
                "path": "Makefile",
                "before": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/native_test.o",
                "after": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/legacy_export.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/native_test.o",
            },
        ],
        "exact_edits": [
            {
                "path": "src/legacy.c",
                "before": "int render_export(void) { return 5; }\nint write_export(void) { return 6; }\n",
                "after": "",
                "expected_occurrences": 1,
            },
            {
                "path": "include/cproposal/legacy.h",
                "before": "int render_export(void);\nint write_export(void);",
                "after": "#include \"cproposal/export.h\"",
                "expected_occurrences": 1,
            },
            {
                "path": "Makefile",
                "before": "SOURCES = src/legacy.c src/billing_parser.c src/billing_types.c src/billing_validator.c src/main.c",
                "after": "SOURCES = src/legacy.c src/legacy_export.c src/billing_parser.c src/billing_types.c src/billing_validator.c src/main.c",
                "expected_occurrences": 1,
            },
            {
                "path": "Makefile",
                "before": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/native_test.o",
                "after": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/legacy_export.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/native_test.o",
                "expected_occurrences": 1,
            },
        ],
        "create_files": [
            {
                "path": "include/cproposal/export.h",
                "contents": (
                    "#ifndef C_PROPOSAL_EXPORT_H\n"
                    "#define C_PROPOSAL_EXPORT_H\n\n"
                    "int render_export(void);\n"
                    "int write_export(void);\n\n"
                    "#endif\n"
                ),
            },
            {
                "path": "src/legacy_export.c",
                "contents": (
                    "#include \"cproposal/export.h\"\n\n"
                    "int render_export(void) { return 5; }\n"
                    "int write_export(void) { return 6; }\n"
                ),
            },
        ],
        "expected_translation_units_after": [
            "src/billing_parser.c",
            "src/billing_types.c",
            "src/billing_validator.c",
            "src/legacy.c",
            "src/legacy_export.c",
            "src/main.c",
        ],
        "test_surface": ["tests/native_test.c", "src/main.c"],
    }
    acceptance = _acceptance(
        host,
        consumer="propose-boundary",
        decision=decision,
        artifacts={"c-map": map_evidence, "confirmed-omnibus": omnibus},
        selection=selection,
        smoke=".native-build/c-structure-smoke",
        smoke_stdout="c-structure:16\n",
        test_stdout="c-structure-native:ok\n",
    )
    return omnibus, map_evidence, acceptance


def _folder_inputs(host: Path, decision: str = "reorganize") -> tuple[Path, Path, Path]:
    _compile_database(host)
    map_evidence = _map(host, "folder")
    topology = host / "reports/folder/findings.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        TOPOLOGY,
        "--project-root",
        host,
        "--c-root",
        "src",
        "--min-cluster-size",
        "3",
        "--output",
        host / "reports/folder/detections.jsonl",
        "--clang",
        CLANG,
        "--make",
        MAKE,
        "--test-target",
        "test",
        "--smoke",
        ".native-build/c-structure-smoke",
        cwd=host,
    )
    finding = _json(topology)["findings"][0]
    make_replacements = [
        ("src/billing_parser.c", "src/billing/parser.c", 1),
        ("src/billing_types.c", "src/billing/types.c", 1),
        ("src/billing_validator.c", "src/billing/validator.c", 1),
    ]
    selection: dict[str, Any] = {
        "finding_evidence_sha256": finding["evidence_sha256"],
        "parent": "src",
        "prefix": "billing",
        "files": finding["files"],
        "project_convention": "group-three-prefix-translation-units",
        "exact_moves": [
            {"from": "src/billing_parser.c", "to": "src/billing/parser.c"},
            {"from": "src/billing_types.c", "to": "src/billing/types.c"},
            {"from": "src/billing_validator.c", "to": "src/billing/validator.c"},
            {"from": "src/billing_internal.h", "to": "src/billing/internal.h"},
        ],
        "include_impact": [
            {
                "path": "src/billing/parser.c",
                "before": "#include \"billing_internal.h\"",
                "after": "#include \"internal.h\"",
            },
            {
                "path": "src/billing/validator.c",
                "before": "#include \"billing_internal.h\"",
                "after": "#include \"internal.h\"",
            },
        ],
        "make_impact": [
            {"path": "Makefile", "before": before, "after": after}
            for before, after, _count in make_replacements
        ] + [
            {
                "path": "Makefile",
                "before": "\t$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@",
                "after": "\tmkdir -p $(dir $@)\n\t$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@",
            },
            {
                "path": "Makefile",
                "before": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/native_test.o",
                "after": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing/validator.o $(BUILD_DIR)/native_test.o",
            },
        ],
        "exact_edits": [
            {
                "path": "src/billing/parser.c",
                "before": "#include \"billing_internal.h\"",
                "after": "#include \"internal.h\"",
                "expected_occurrences": 1,
            },
            {
                "path": "src/billing/validator.c",
                "before": "#include \"billing_internal.h\"",
                "after": "#include \"internal.h\"",
                "expected_occurrences": 1,
            },
            *[
                {
                    "path": "Makefile",
                    "before": before,
                    "after": after,
                    "expected_occurrences": count,
                }
                for before, after, count in make_replacements
            ],
            {
                "path": "Makefile",
                "before": "\t$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@",
                "after": "\tmkdir -p $(dir $@)\n\t$(CC) $(CFLAGS) $(CPPFLAGS) -c $(CURDIR)/$< -o $@",
                "expected_occurrences": 2,
            },
            {
                "path": "Makefile",
                "before": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing_validator.o $(BUILD_DIR)/native_test.o",
                "after": "$(BUILD_DIR)/native-test: $(BUILD_DIR)/legacy.o $(BUILD_DIR)/billing/validator.o $(BUILD_DIR)/native_test.o",
                "expected_occurrences": 1,
            },
        ],
        "caller_impact": [
            {
                "path": "src/main.c",
                "impact": "public cbilling/invoice.h include and function spelling remain unchanged",
            },
            {
                "path": "tests/native_test.c",
                "impact": "public cbilling/invoice.h include and function spelling remain unchanged",
            },
        ],
        "expected_translation_units_after": [
            "src/billing/parser.c",
            "src/billing/types.c",
            "src/billing/validator.c",
            "src/legacy.c",
            "src/main.c",
        ],
        "test_surface": ["tests/native_test.c", "src/main.c"],
    }
    acceptance = _acceptance(
        host,
        consumer="propose-folder-reorganization",
        decision=decision,
        artifacts={"c-map": map_evidence, "lexical-topology": topology},
        selection=selection,
        smoke=".native-build/c-structure-smoke",
        smoke_stdout="c-structure:16\n",
        test_stdout="c-structure-native:ok\n",
    )
    return topology, map_evidence, acceptance


def _invoke(
    script: Path,
    host: Path,
    producer: Path,
    map_evidence: Path,
    acceptance: Path,
    name: str,
    *,
    expected: int = 0,
) -> Path:
    skill = script.parents[1].name
    producer_flag = "--omnibus" if skill == "propose-boundary" else "--topology"
    output = host / "reports" / skill / name
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        producer_flag,
        producer,
        "--map-evidence",
        map_evidence,
        "--acceptance",
        acceptance,
        "--output-dir",
        output,
        "--clang",
        CLANG,
        "--make",
        MAKE,
        cwd=host,
        expected=expected,
    )
    return output


def _apply_plan(root: Path, payload: dict[str, Any]) -> None:
    for move in payload.get("exact_moves", []):
        source, destination = root / move["from"], root / move["to"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    for edit in payload.get("exact_edits", []):
        path = root / edit["path"]
        text = path.read_text(encoding="utf-8")
        assert text.count(edit["before"]) == edit["expected_occurrences"]
        path.write_text(text.replace(edit["before"], edit["after"]), encoding="utf-8")
    for create in payload.get("create_files", []):
        path = root / create["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(create["contents"], encoding="utf-8")


def _independent_native(host: Path, expected_smoke: str, smoke: str) -> None:
    _run(MAKE, "clean", "compile-db", f"CC={CLANG}", cwd=host)
    _run(MAKE, "test", f"CC={CLANG}", cwd=host)
    result = _run(host / smoke, cwd=host)
    assert result.stdout == expected_smoke


def test_positive_plans_are_exact_read_only_and_disposable_native_verified(
    tmp_path: Path,
) -> None:
    boundary_host = _copy(BOUNDARY_FIXTURE, tmp_path / "boundary")
    boundary_inputs = _boundary_inputs(boundary_host)
    boundary_before = _source_hashes(boundary_host)
    boundary_output = _invoke(BOUNDARY, boundary_host, *boundary_inputs, "ready")
    boundary = _json(boundary_output / "inspection.json")

    assert boundary["status"] == "ready_for_human_review"
    assert boundary["outcome"] == "boundary_plan_ready"
    assert boundary["declarations"] == ["render_export", "write_export"]
    assert len(boundary["caller_impact"]) == 2
    assert len(boundary["include_impact"]) == 2
    assert len(boundary["make_impact"]) == 2
    assert boundary["native_verification"]["current_tree"]["status"] == "passed"
    assert boundary["native_verification"]["disposable_after_tree"]["status"] == "passed"
    assert boundary["native_verification"]["disposable_after_tree"][
        "compile_database_translation_units"
    ] == boundary["expected_translation_units_after"]
    assert boundary["source_preservation"]["verified"] is True
    assert boundary["source_mutations"] == 0
    assert any("ABI" in claim for claim in boundary["nonclaims"])
    assert any("external" in claim for claim in boundary["nonclaims"])
    assert _source_hashes(boundary_host) == boundary_before
    proposal = (boundary_output / "proposal.md").read_text(encoding="utf-8")
    for heading in (
        "Accepted C seam",
        "Declarations and public header",
        "Caller impact",
        "Include impact",
        "Make and compile-database impact",
        "Native obligations",
    ):
        assert heading in proposal

    folder_host = _copy(FOLDER_FIXTURE, tmp_path / "folder")
    folder_inputs = _folder_inputs(folder_host)
    folder_before = _source_hashes(folder_host)
    folder_output = _invoke(FOLDER, folder_host, *folder_inputs, "ready")
    folder = _json(folder_output / "inspection.json")

    assert folder["status"] == "ready_for_human_review"
    assert folder["outcome"] == "folder_plan_ready"
    assert folder["project_convention"] == "group-three-prefix-translation-units"
    assert folder["accounting"] == {
        "cluster_members": 3,
        "planned_cluster_members": 3,
        "auxiliary_owned_headers": 1,
    }
    assert len(folder["exact_moves"]) == 4
    assert len(folder["include_impact"]) == 2
    assert len(folder["make_impact"]) == 5
    assert folder["native_verification"]["disposable_after_tree"]["status"] == "passed"
    assert folder["native_verification"]["disposable_after_tree"][
        "compile_database_translation_units"
    ] == folder["expected_translation_units_after"]
    assert folder["source_preservation"]["verified"] is True
    assert folder["source_mutations"] == 0
    assert _source_hashes(folder_host) == folder_before
    folder_proposal = (folder_output / "proposal.md").read_text(encoding="utf-8")
    for heading in (
        "Accepted project convention",
        "Current → proposed tree",
        "Include impact",
        "Make and compile-database regeneration",
        "Disposable after-tree proof",
    ):
        assert heading in folder_proposal

    for host, payload, expected_smoke, smoke in (
        (boundary_host, boundary, "c-structure:16\n", ".native-build/c-structure-smoke"),
        (folder_host, folder, "c-structure:16\n", ".native-build/c-structure-smoke"),
    ):
        disposable = tmp_path / f"independent-{payload['language']}-{payload['skill']}"
        shutil.copytree(host, disposable, ignore=shutil.ignore_patterns("reports", ".native-build"))
        _apply_plan(disposable, payload)
        _independent_native(disposable, expected_smoke, smoke)


def test_cohesive_keep_flat_and_no_convention_are_complete_defers(tmp_path: Path) -> None:
    boundary_host = _copy(BOUNDARY_FIXTURE, tmp_path / "boundary")
    boundary_inputs = _boundary_inputs(boundary_host, "keep_cohesive")
    boundary_output = _invoke(BOUNDARY, boundary_host, *boundary_inputs, "cohesive")
    boundary = _json(boundary_output / "inspection.json")
    assert boundary["status"] == "complete"
    assert boundary["outcome"] == "safely_deferred"
    assert boundary["recommendation"] == "defer_cohesive_target"
    assert "disposable_after_tree" not in boundary["native_verification"]
    assert "cohesive" in (boundary_output / "proposal.md").read_text(encoding="utf-8")

    for decision, recommendation in (
        ("keep_flat", "keep_flat"),
        ("defer_no_convention", "defer_project_convention_required"),
    ):
        folder_host = _copy(FOLDER_FIXTURE, tmp_path / decision)
        folder_inputs = _folder_inputs(folder_host, decision)
        folder_output = _invoke(FOLDER, folder_host, *folder_inputs, decision)
        folder = _json(folder_output / "inspection.json")
        assert folder["status"] == "complete"
        assert folder["outcome"] == "safely_deferred"
        assert folder["recommendation"] == recommendation
        assert "disposable_after_tree" not in folder["native_verification"]
        assert (folder_output / "proposal.md").is_file()


@pytest.mark.parametrize("kind", ["boundary", "folder"])
def test_stale_or_unaccepted_inputs_replace_success_and_recover(
    kind: str, tmp_path: Path
) -> None:
    fixture = BOUNDARY_FIXTURE if kind == "boundary" else FOLDER_FIXTURE
    host = _copy(fixture, tmp_path / kind)
    inputs = _boundary_inputs(host) if kind == "boundary" else _folder_inputs(host)
    script = BOUNDARY if kind == "boundary" else FOLDER
    output = _invoke(script, host, *inputs, "reuse")
    assert _json(output / "inspection.json")["status"] == "ready_for_human_review"

    acceptance = inputs[-1]
    accepted = _json(acceptance)
    accepted["human_verdict"]["status"] = "pending"
    accepted.pop("acceptance_hash")
    accepted["acceptance_hash"] = _canonical_hash(accepted)
    _write_json(acceptance, accepted)
    _invoke(script, host, *inputs, "reuse", expected=2)
    refused = _json(output / "inspection.json")
    assert refused["status"] == "failed"
    assert refused["outcome"] == "refused"
    assert refused["failure_kind"] == "human_acceptance_required"

    accepted["human_verdict"]["status"] = "accepted"
    accepted.pop("acceptance_hash")
    accepted["acceptance_hash"] = _canonical_hash(accepted)
    _write_json(acceptance, accepted)
    _invoke(script, host, *inputs, "reuse")
    assert _json(output / "inspection.json")["status"] == "ready_for_human_review"

    source = host / ("src/legacy.c" if kind == "boundary" else "src/billing_parser.c")
    source.write_text(source.read_text(encoding="utf-8") + "\n/* stale */\n", encoding="utf-8")
    _invoke(script, host, *inputs, "reuse", expected=2)
    stale = _json(output / "inspection.json")
    assert stale["failure_kind"] == "stale_accepted_source"


@pytest.mark.parametrize("kind", ["boundary", "folder"])
def test_copied_consumer_is_self_contained_and_never_redetects(
    kind: str, tmp_path: Path
) -> None:
    fixture = BOUNDARY_FIXTURE if kind == "boundary" else FOLDER_FIXTURE
    host = _copy(fixture, tmp_path / f"host-{kind}")
    inputs = _boundary_inputs(host) if kind == "boundary" else _folder_inputs(host)
    source = BOUNDARY if kind == "boundary" else FOLDER
    copied = tmp_path / f"installed/.agents/skills/{source.parents[1].name}/scripts/{source.name}"
    copied.parent.mkdir(parents=True)
    shutil.copy2(source, copied)

    output = _invoke(copied, host, *inputs, "copied")

    assert _json(output / "inspection.json")["status"] == "ready_for_human_review"
    text = copied.read_text(encoding="utf-8")
    assert str(ROOT) not in text
    assert "run_c.py" not in text
    assert "detect_c.py" not in text
    assert "map_c.py" not in text
    assert "clang_ast" not in text
