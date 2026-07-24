"""Accepted, refused, and copied outcomes for both C++ structure proposals."""

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
CLANGXX = Path(shutil.which("clang++") or "")
CLANGD = Path(shutil.which("clangd") or "")
MAKE = Path(shutil.which("make") or "")
FIXTURE = ROOT / "tests/fixtures/cpp-structure-proposals/host"
MAP = ROOT / ".claude/skills/map-subsystem/scripts/map_cpp.py"
OMNIBUS = ROOT / ".claude/skills/find-omnibus/scripts/run_cpp.py"
TOPOLOGY = ROOT / ".claude/skills/find-folder-topology-drift/scripts/detect_cpp.py"
BOUNDARY = ROOT / ".claude/skills/propose-boundary/scripts/propose_cpp.py"
FOLDER = ROOT / ".claude/skills/propose-folder-reorganization/scripts/propose_cpp.py"
UNCERTAINTIES = {
    "templates_specializations",
    "virtual_dynamic_dispatch",
    "function_pointers_callbacks",
    "header_exposure",
    "odr_abi",
    "external_consumers",
    "build_variants",
}


def _clang_21() -> bool:
    if not CLANGXX.is_file():
        return False
    result = subprocess.run(
        [CLANGXX, "--version"], capture_output=True, text=True, check=False
    )
    match = re.search(r"(?:Apple )?clang version (\d+)\.(\d+)\.(\d+)", result.stdout)
    return bool(match and tuple(map(int, match.groups())) >= (21, 0, 0))


pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, CLANGXX, CLANGD, MAKE)) or not _clang_21(),
    reason="frozen product Python, Clang++/clangd 21+, and Make are required",
)


def _run(
    *args: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 240,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, capture_output=True, text=True,
        check=False, timeout=timeout,
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
    suffixes = {".cpp", ".cc", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc", ".tpp"}
    return {
        path.relative_to(host).as_posix(): _sha256(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and (path.suffix in suffixes or path.name == "Makefile")
        and not any(
            part in {"reports", ".native-build", ".engineering"}
            for part in path.relative_to(host).parts
        )
    }


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(
        FIXTURE, host,
        ignore=shutil.ignore_patterns("reports", ".native-build", ".engineering", "compile_commands.json"),
    )
    return host


def _compile_database(host: Path) -> None:
    _run(MAKE, "clean", "compile-db", f"CXX={CLANGXX}", cwd=host)


def _map(host: Path) -> Path:
    evidence = host / "reports/map/structure/cpp-map.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        MAP,
        "--name",
        "structure",
        "--target",
        ".",
        "--project-root",
        host,
        "--output",
        host / ".engineering/docs/subsystems/structure.md",
        "--evidence",
        evidence,
        "--clangxx",
        CLANGXX,
        "--clangd",
        CLANGD,
        "--make",
        MAKE,
        cwd=host,
    )
    assert _json(evidence)["status"] == "complete"
    return evidence


def _producers(host: Path) -> tuple[Path, Path, Path]:
    _compile_database(host)
    map_evidence = _map(host)
    omnibus_dir = host / "reports/omnibus/cpp"
    _run(
        PYTHON,
        "-I",
        "-S",
        OMNIBUS,
        "--project-root",
        host,
        "--target",
        "src/legacy.cpp",
        "--output-dir",
        omnibus_dir,
        "--scout-dir",
        host / "cpp-scouts",
        "--clangxx",
        CLANGXX,
        cwd=host,
    )
    omnibus = omnibus_dir / "findings.json"
    assert _json(omnibus)["findings"][0]["bucket"] == "confirmed_omnibus"
    topology = host / "reports/folder/findings.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        TOPOLOGY,
        "--project-root",
        host,
        "--cpp-root",
        "src",
        "--min-cluster-size",
        "3",
        "--output",
        host / "reports/folder/detections.jsonl",
        "--clangxx",
        CLANGXX,
        cwd=host,
    )
    assert _json(topology)["outcome"] == "drift-found"
    return omnibus, topology, map_evidence


def _callers(map_evidence: dict[str, Any], keys: set[tuple[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for edge in map_evidence["reference_edges"]:
        target = edge["target"]
        if (target["qualified_name"], target["signature"]) not in keys:
            continue
        rows.append(
            {
                "path": edge["file"],
                "translation_unit": edge["translation_unit"],
                "direction": edge["direction"],
                "source": {
                    "qualified_name": edge["source"]["qualified_name"],
                    "signature": edge["source"]["signature"],
                },
                "target": {
                    "qualified_name": target["qualified_name"],
                    "signature": target["signature"],
                },
                "impact": "qualified spelling and private include remain unchanged",
            }
        )
    return rows


def _uncertainty_review() -> dict[str, dict[str, str]]:
    return {
        key: {
            "status": "resolved",
            "basis": f"fixture owner reviewed {key} for the selected private C++20 surface",
        }
        for key in sorted(UNCERTAINTIES)
    }


def _native_obligations() -> list[dict[str, Any]]:
    return [
        {
            "name": "compile-database",
            "argv": ["make", "clean", "compile-db", "CXX=clang++"],
            "expected_returncode": 0,
        },
        {
            "name": "native-test",
            "argv": ["make", "test", "CXX=clang++"],
            "expected_returncode": 0,
            "expected_stdout_contains": "cpp-structure-native:ok\n",
        },
        {
            "name": "smoke",
            "argv": [".native-build/cpp-structure-smoke"],
            "expected_returncode": 0,
            "expected_stdout": "cpp-structure:18\n",
        },
    ]


def _acceptance(
    host: Path,
    *,
    consumer: str,
    artifacts: dict[str, Path],
    selection: dict[str, Any],
    decision: str,
) -> Path:
    payload: dict[str, Any] = {
        "schema_version": "cpp-structure-accepted-evidence-v1",
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
            "reviewer": "cpp-structure-fixture-owner",
        },
        "uncertainty_review": _uncertainty_review(),
        "native_obligations": _native_obligations(),
    }
    payload["acceptance_hash"] = _canonical_hash(payload)
    return _write_json(
        host / f"reports/accepted/{consumer}/acceptance.json", payload
    )


def _boundary_acceptance(host: Path, omnibus: Path, map_path: Path) -> Path:
    map_evidence = _json(map_path)
    declarations = [
        {"qualified_name": "cppproposal::render_export", "signature": "int (int)", "kind": "function"},
        {
            "qualified_name": "cppproposal::render_export",
            "signature": "int (std::string_view)",
            "kind": "function",
        },
        {"qualified_name": "cppproposal::write_export", "signature": "int ()", "kind": "function"},
    ]
    keys = {(row["qualified_name"], row["signature"]) for row in declarations}
    source_block = (
        "int render_export(int value) { return value + 5; }\n"
        "int render_export(std::string_view value) { return static_cast<int>(value.size()) + 5; }\n"
        "int write_export() { return 6; }\n"
    )
    declaration_block = (
        "int render_export(int value);\n"
        "int render_export(std::string_view value);\n"
        "int write_export();\n"
    )
    make_sources = (
        "SOURCES = src/legacy.cpp src/billing_parser.cpp src/billing_rules.cpp "
        "src/billing_summary.cpp src/main.cpp"
    )
    make_sources_after = make_sources.replace("src/legacy.cpp", "src/legacy.cpp src/legacy_export.cpp")
    make_test = (
        "$(BUILD_DIR)/cpp-structure-native: $(BUILD_DIR)/legacy.o "
        "$(BUILD_DIR)/billing_rules.o $(BUILD_DIR)/native_check.o"
    )
    make_test_after = make_test.replace(
        "$(BUILD_DIR)/legacy.o", "$(BUILD_DIR)/legacy.o $(BUILD_DIR)/legacy_export.o"
    )
    header_contents = (
        "#ifndef CPP_STRUCTURE_EXPORT_HPP\n#define CPP_STRUCTURE_EXPORT_HPP\n\n"
        "#include <string_view>\n\nnamespace cppproposal {\n\n"
        f"{declaration_block}\n}}  // namespace cppproposal\n\n#endif\n"
    )
    unit_contents = (
        "#include \"export.hpp\"\n\nnamespace cppproposal {\n\n"
        f"{source_block}\n}}  // namespace cppproposal\n"
    )
    exact_edits = [
        {"path": "src/legacy.cpp", "before": source_block, "after": "", "expected_occurrences": 1},
        {
            "path": "src/legacy.hpp",
            "before": "#include <string_view>",
            "after": "#include \"export.hpp\"",
            "expected_occurrences": 1,
        },
        {"path": "src/legacy.hpp", "before": declaration_block, "after": "", "expected_occurrences": 1},
        {"path": "Makefile", "before": make_sources, "after": make_sources_after, "expected_occurrences": 1},
        {"path": "Makefile", "before": make_test, "after": make_test_after, "expected_occurrences": 1},
    ]
    selection = {
        "candidate_id": "candidate-001",
        "target": "src/legacy.cpp",
        "domain": "export",
        "declarations": declarations,
        "private_header": "src/legacy.hpp",
        "new_private_header": "src/export.hpp",
        "new_translation_unit": "src/legacy_export.cpp",
        "caller_impact": _callers(map_evidence, keys),
        "source_impact": [
            {
                "path": "src/legacy.cpp", "before": source_block, "after": "",
                "impact": "move the three exact overload-aware definitions",
            },
            {
                "path": "src/legacy_export.cpp", "after": "#include \"export.hpp\"",
                "impact": "create the private implementation translation unit",
            },
        ],
        "header_impact": [
            {
                "path": "src/legacy.hpp", "before": "#include <string_view>",
                "after": "#include \"export.hpp\"", "impact": "preserve private include compatibility",
            },
            {
                "path": "src/legacy.hpp", "before": declaration_block, "after": "",
                "impact": "move the complete selected overload set",
            },
            {
                "path": "src/export.hpp", "after": declaration_block,
                "impact": "create the private overload-aware declaration header",
            },
        ],
        "build_impact": [
            {
                "path": "Makefile", "before": make_sources, "after": make_sources_after,
                "impact": "compile the new translation unit in smoke and compile database",
            },
            {
                "path": "Makefile", "before": make_test, "after": make_test_after,
                "impact": "link the new object into the native test",
            },
        ],
        "exact_edits": exact_edits,
        "create_files": [
            {"path": "src/export.hpp", "contents": header_contents},
            {"path": "src/legacy_export.cpp", "contents": unit_contents},
        ],
        "expected_translation_units_after": sorted(
            [*map_evidence["translation_units"], "src/legacy_export.cpp"]
        ),
        "test_surface": ["src/main.cpp", "src/native_check.cpp"],
    }
    return _acceptance(
        host,
        consumer="propose-boundary",
        artifacts={"confirmed-omnibus": omnibus, "cpp-map": map_path},
        selection=selection,
        decision="extract_boundary",
    )


def _folder_acceptance(host: Path, topology: Path, map_path: Path) -> Path:
    map_evidence = _json(map_path)
    finding = _json(topology)["findings"][0]
    moves = [
        {"from": "src/billing_parser.cpp", "to": "src/billing/parser.cpp"},
        {"from": "src/billing_rules.cpp", "to": "src/billing/rules.cpp"},
        {"from": "src/billing_summary.cpp", "to": "src/billing/summary.cpp"},
        {"from": "src/billing_internal.hpp", "to": "src/billing/internal.hpp"},
    ]
    include_before, include_after = '#include "billing_internal.hpp"', '#include "internal.hpp"'
    replacements = [
        ("src/billing_parser.cpp", "src/billing/parser.cpp"),
        ("src/billing_rules.cpp", "src/billing/rules.cpp"),
        ("src/billing_summary.cpp", "src/billing/summary.cpp"),
    ]
    make_test = (
        "$(BUILD_DIR)/cpp-structure-native: $(BUILD_DIR)/legacy.o "
        "$(BUILD_DIR)/billing_rules.o $(BUILD_DIR)/native_check.o"
    )
    make_test_after = make_test.replace("billing_rules.o", "billing/rules.o")
    exact_edits = [
        {
            "path": "src/billing/parser.cpp", "before": include_before,
            "after": include_after, "expected_occurrences": 1,
        },
        {
            "path": "src/billing/summary.cpp", "before": include_before,
            "after": include_after, "expected_occurrences": 1,
        },
        *[
            {
                "path": "Makefile", "before": before, "after": after,
                "expected_occurrences": 1,
            }
            for before, after in replacements
        ],
        {
            "path": "Makefile", "before": make_test, "after": make_test_after,
            "expected_occurrences": 1,
        },
    ]
    keys = {
        ("cppproposal::billing_parse", "int ()"),
        ("cppproposal::billing_rule", "int ()"),
        ("cppproposal::billing_summary", "int ()"),
    }
    expected_after = (
        set(map_evidence["translation_units"])
        - set(finding["files"])
        | {row["to"] for row in moves[:3]}
    )
    selection = {
        "finding_evidence_sha256": finding["evidence_sha256"],
        "parent": "src",
        "prefix": "billing",
        "files": finding["files"],
        "project_convention": "group-three-private-cpp-translation-units",
        "exact_moves": moves,
        "caller_impact": _callers(map_evidence, keys),
        "source_impact": [
            {**row, "impact": "move one compiler-owned translation unit without namespace change"}
            for row in moves[:3]
        ],
        "header_impact": [
            {**moves[3], "impact": "move one compiler-owned private header"},
            {
                "path": "src/billing/parser.cpp", "before": include_before,
                "after": include_after, "impact": "retarget the local private include",
            },
            {
                "path": "src/billing/summary.cpp", "before": include_before,
                "after": include_after, "impact": "retarget the local private include",
            },
        ],
        "build_impact": [
            *[
                {
                    "path": "Makefile", "before": before, "after": after,
                    "impact": "retarget source and compile-database path",
                }
                for before, after in replacements
            ],
            {
                "path": "Makefile", "before": make_test, "after": make_test_after,
                "impact": "retarget the native-test object prerequisite",
            },
        ],
        "exact_edits": exact_edits,
        "expected_translation_units_after": sorted(expected_after),
        "test_surface": ["src/main.cpp", "src/native_check.cpp"],
    }
    return _acceptance(
        host,
        consumer="propose-folder-reorganization",
        artifacts={"lexical-topology": topology, "cpp-map": map_path},
        selection=selection,
        decision="reorganize",
    )


def _invoke(
    script: Path,
    host: Path,
    producer: Path,
    map_path: Path,
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
        map_path,
        "--acceptance",
        acceptance,
        "--output-dir",
        output,
        "--clangxx",
        CLANGXX,
        "--make",
        MAKE,
        cwd=host,
        expected=expected,
    )
    return output


def _apply_scope(root: Path, scope: dict[str, Any]) -> None:
    for row in scope.get("exact_moves", []):
        source, destination = root / row["from"], root / row["to"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    for row in scope.get("exact_edits", []):
        path = root / row["path"]
        text = path.read_text(encoding="utf-8")
        assert text.count(row["before"]) == row["expected_occurrences"]
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")
    for row in scope.get("create_files", []):
        path = root / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["contents"], encoding="utf-8")


def _independent_native(host: Path) -> list[str]:
    _run(MAKE, "clean", "compile-db", f"CXX={CLANGXX}", cwd=host)
    _run(MAKE, "test", f"CXX={CLANGXX}", cwd=host)
    assert _run(host / ".native-build/cpp-structure-smoke", cwd=host).stdout == "cpp-structure:18\n"
    return sorted(
        Path(row["file"]).resolve().relative_to(host.resolve()).as_posix()
        for row in _json(host / "compile_commands.json")
    )


def _rehash_acceptance(path: Path, mutate) -> dict[str, Any]:
    payload = _json(path)
    mutate(payload)
    payload.pop("acceptance_hash", None)
    payload["acceptance_hash"] = _canonical_hash(payload)
    _write_json(path, payload)
    return payload


def test_cpp_structure_proposals_reach_accepted_refused_and_copied_outcomes(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    omnibus, topology, map_path = _producers(host)
    boundary_acceptance = _boundary_acceptance(host, omnibus, map_path)
    folder_acceptance = _folder_acceptance(host, topology, map_path)
    before = _source_hashes(host)

    cases = (
        (BOUNDARY, omnibus, boundary_acceptance, "boundary"),
        (FOLDER, topology, folder_acceptance, "folder"),
    )
    for script, producer, acceptance, name in cases:
        output = _invoke(script, host, producer, map_path, acceptance, "accepted")
        assert {path.name for path in output.iterdir()} == {
            "proposal.md", "evidence.json", "scope.json"
        }
        evidence = _json(output / "evidence.json")
        scope = _json(output / "scope.json")
        assert evidence["status"] == "ready_for_human_review"
        assert evidence["native_verification"]["current_tree"]["status"] == "passed"
        assert evidence["native_verification"]["disposable_after_tree"]["status"] == "passed"
        assert evidence["source_preservation"]["verified"] is True
        assert evidence["source_mutations"] == 0
        assert scope["mutation_authorized"] is False and scope["read_only"] is True
        assert all("::" in row["qualified_name"] for row in scope["declarations"])
        assert scope["overload_sets"]
        assert scope["caller_impact"] and scope["source_impact"]
        assert scope["header_impact"] and scope["build_impact"]
        assert _source_hashes(host) == before
        independent = tmp_path / f"independent-{name}"
        shutil.copytree(
            host, independent,
            ignore=shutil.ignore_patterns("reports", ".native-build", ".engineering", "compile_commands.json"),
        )
        _apply_scope(independent, scope)
        assert _independent_native(independent) == scope["expected_translation_units_after"]

        original = _json(acceptance)
        for uncertainty in sorted(UNCERTAINTIES):
            _rehash_acceptance(
                acceptance,
                lambda payload, key=uncertainty: payload["uncertainty_review"][key].update(
                    status="unresolved"
                ),
            )
            refused_output = _invoke(
                script, host, producer, map_path, acceptance, "refused", expected=2
            )
            refused = _json(refused_output / "evidence.json")
            assert refused["outcome"] == "refused"
            assert refused["failure_kind"] == "cpp_uncertainty_unresolved"
            _write_json(acceptance, original)

        copied = tmp_path / f"installed/{script.parents[1].name}/scripts/{script.name}"
        copied.parent.mkdir(parents=True)
        shutil.copy2(script, copied)
        copied_output = _invoke(copied, host, producer, map_path, acceptance, "copied")
        assert _json(copied_output / "evidence.json")["status"] == "ready_for_human_review"
        text = copied.read_text(encoding="utf-8")
        assert str(ROOT) not in text
        assert "run_cpp.py" not in text
        assert "detect_cpp.py" not in text
        assert "map_cpp.py" not in text

    _rehash_acceptance(
        boundary_acceptance,
        lambda payload: payload["human_verdict"].update(status="pending"),
    )
    refused = _invoke(
        BOUNDARY, host, omnibus, map_path, boundary_acceptance, "human", expected=2
    )
    assert _json(refused / "evidence.json")["failure_kind"] == "human_acceptance_required"

    _rehash_acceptance(
        folder_acceptance,
        lambda payload: payload["selection"].update(project_convention=""),
    )
    refused = _invoke(
        FOLDER, host, topology, map_path, folder_acceptance, "convention", expected=2
    )
    assert _json(refused / "evidence.json")["failure_kind"] == "project_convention_required"
    assert _source_hashes(host) == before
