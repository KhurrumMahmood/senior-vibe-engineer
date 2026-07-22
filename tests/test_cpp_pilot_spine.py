"""Frozen C++-only P7 spine, compile-database gate, and pending-work truth."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.cpp_language_provider import (
    CPP_DECLARATION_SUFFIXES,
    CPP_SOURCE_SUFFIXES,
    cpp_suffix_role,
    validate_cpp_compile_database,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "cpp-pilot"
BASELINE = ROOT / ".claude" / "tasks" / "p7-baseline" / "cpp-pilot-baseline.json"
COVERAGE = ROOT / ".claude" / "tasks" / "cpp-language-coverage.json"
DOCTOR = ROOT / "scripts" / "language_doctor.py"
INVENTORY = ROOT / "scripts" / "source_inventory.py"

EXPECTED_SKILLS = {
    "adapt-project", "audit-decisions", "explain-code", "extract-enum",
    "find-comment-drift", "find-complexity-hotspots",
    "find-concept-divergence", "find-dormant", "find-duplication",
    "find-folder-topology-drift", "find-implicit-state",
    "find-incomplete-sweep", "find-omnibus", "find-semantic-duplication",
    "find-standard-gaps", "map-subsystem", "move-path",
    "prevent-regression", "propose-boundary",
    "propose-folder-reorganization", "rename-concept", "unify-shadows",
}


def _manifest(root: Path) -> tuple[str, int, list[str]]:
    rows: list[tuple[str, str, int]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        content = path.read_bytes()
        rows.append((path.relative_to(root).as_posix(), hashlib.sha256(content).hexdigest(), len(content)))
    digest = hashlib.sha256()
    for path, file_digest, _size in rows:
        digest.update(path.encode() + b"\0" + file_digest.encode() + b"\n")
    return digest.hexdigest(), sum(row[2] for row in rows), [row[0] for row in rows]


def _tree_state(root: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file() and cpp_suffix_role(path) is not None:
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _run(argv: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, check=False,
        timeout=30,
    )


def _expected_sources(host: Path) -> list[Path]:
    return [host / "src" / "invoice.cpp", host / "src" / "main.cpp"]


def _freshness_inputs(host: Path) -> list[Path]:
    return [
        host / "Makefile", host / "src" / "invoice.cpp", host / "src" / "main.cpp",
        host / "src" / "invoice_internal.hpp", host / "src" / "pilot_mode.inc",
        host / "include" / "cpppilot" / "invoice.hpp",
        host / "include" / "cpppilot" / "render.hpp",
    ]


def _database_state(host: Path):
    return validate_cpp_compile_database(
        host,
        expected_sources=_expected_sources(host),
        freshness_inputs=_freshness_inputs(host),
    )


def _materialize_database(host: Path, clangxx: str, make: str) -> None:
    completed = _run([make, "clean", "compile-db", f"CXX={clangxx}"], host)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _analysis_argv(entry: dict[str, object], *extra: str) -> list[str]:
    raw = list(entry["arguments"])
    source = str(entry["file"])
    filtered: list[str] = []
    skip = False
    for token in raw[1:]:
        if skip:
            skip = False
            continue
        if token == "-o":
            skip = True
            continue
        if token in {"-c", source}:
            continue
        filtered.append(token)
    return [raw[0], *filtered, *extra, source]


def test_cpp_fixture_and_runtime_closure_match_frozen_manifests() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    digest, total_bytes, files = _manifest(FIXTURE)
    assert (digest, total_bytes, files) == (
        baseline["fixture"]["manifest_sha256"],
        baseline["fixture"]["total_bytes"],
        baseline["fixture"]["files"],
    )
    closure = baseline["runtime_closure"]
    paths = [ROOT / path for path in closure["files"]]
    closure_digest = hashlib.sha256()
    for path in paths:
        closure_digest.update(path.relative_to(ROOT).as_posix().encode())
        closure_digest.update(b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    assert closure_digest.hexdigest() == closure["manifest_sha256"]
    assert sum(path.stat().st_size for path in paths) == closure["total_bytes"]
    assert baseline["runtime_timings_seconds"]


def test_cpp_profile_suffix_truth_inventory_roles_symlink_and_preservation(tmp_path: Path) -> None:
    profile = json.loads((ROOT / "scripts" / "language_profiles" / "cpp.json").read_text())
    assert {".cc", ".cpp", ".cxx", ".c++", ".ii"} <= set(profile["suffixes"])
    assert not ({".c", ".i", ".m", ".mm"} & set(profile["suffixes"]))
    assert CPP_SOURCE_SUFFIXES == {".cc", ".cpp", ".cxx", ".c++", ".C", ".ii"}
    assert cpp_suffix_role(Path("Source.C")) == "source"
    assert cpp_suffix_role(Path("Source.c")) is None
    assert cpp_suffix_role(Path("Bridge.mm")) is None
    assert cpp_suffix_role(Path("shared.h")) == "ambiguous-header"
    assert CPP_DECLARATION_SUFFIXES <= set(profile["suffixes"])

    pilot = tmp_path / "cpp-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "linked-external").symlink_to(pilot / "symlink-target", target_is_directory=True)
    before = _tree_state(host)
    completed = _run([sys.executable, "-I", "-S", str(INVENTORY), "--project-root", str(host)], tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _tree_state(host) == before
    payload = json.loads(completed.stdout)
    cpp_files = {row["path"]: row for row in payload["files"] if row["language"] == "cpp"}
    assert cpp_files["src/invoice.cpp"]["role"] == "source"
    assert cpp_files["src/main.cpp"]["role"] == "source"
    assert cpp_files["include/cpppilot/invoice.hpp"]["role"] == "declaration"
    assert cpp_files["include/cpppilot/render.hpp"]["role"] == "declaration"
    assert cpp_files["src/invoice_internal.hpp"]["role"] == "declaration"
    assert cpp_files["tests/invoice_test.cpp"]["role"] == "test"
    assert cpp_files["generated/GeneratedInvoice.cpp"]["role"] == "generated"
    assert not any(path.endswith((".c", ".i", ".h", ".inc", ".m", ".mm")) for path in cpp_files)
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded["build"] == "build"
    assert excluded["vendor"] == "vendor"
    assert excluded["linked-external"] == "symlink"


def test_cpp_native_build_compiler_facts_and_compile_database_gate(tmp_path: Path) -> None:
    clangxx = shutil.which("clang++")
    clangd = shutil.which("clangd")
    make = shutil.which("make")
    if clangxx is None or clangd is None or make is None:
        pytest.skip("Clang++/clangd/Make unavailable; the generic doctor reports this boundary")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    before = _tree_state(host)
    offline = {
        **os.environ,
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
    }
    built = _run([make, "clean", "test", f"CXX={clangxx}"], host, env=offline)
    assert built.returncode == 0, built.stdout + built.stderr
    smoke = _run([str(host / ".native-build" / "cpp-pilot-smoke")], host)
    assert smoke.returncode == 0
    assert smoke.stdout == "invoice:INV-42:pending:pilot\n"

    assert _database_state(host).state == "missing"
    _materialize_database(host, clangxx, make)
    result = _database_state(host)
    assert result.state == "valid"
    assert len(result.entries) == 2
    for entry in result.entries:
        compiled = _run(list(entry["arguments"]), host)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    checked = _run(
        [clangd, f"--check={host / 'src' / 'main.cpp'}", f"--compile-commands-dir={host}", "--log=verbose"],
        host,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "Compile command from CDB is" in checked.stdout + checked.stderr

    invoice_entry = next(row for row in result.entries if str(row["file"]).endswith("/invoice.cpp"))
    ast = _run(_analysis_argv(invoice_entry, "-Xclang", "-ast-dump=json", "-fsyntax-only"), host)
    assert ast.returncode == 0, ast.stdout + ast.stderr
    assert json.loads(ast.stdout)["kind"] == "TranslationUnitDecl"
    assert '"name": "render_invoice"' in ast.stdout
    tokens = _run(_analysis_argv(invoice_entry, "-Xclang", "-dump-raw-tokens", "-fsyntax-only"), host)
    assert tokens.returncode == 0
    assert "decision: keep label policy private" in tokens.stdout + tokens.stderr
    dependencies = _run(_analysis_argv(invoice_entry, "-MM"), host)
    assert dependencies.returncode == 0, dependencies.stdout + dependencies.stderr
    for expected in ("include/cpppilot/invoice.hpp", "include/cpppilot/render.hpp", "src/invoice_internal.hpp", "src/pilot_mode.inc"):
        assert expected in dependencies.stdout
    assert "orphan.h" not in dependencies.stdout and "orphan.inc" not in dependencies.stdout

    malformed = _run([clangxx, "-x", "c++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only", str(FIXTURE / "malformed" / "Broken.cpp")], host)
    assert malformed.returncode != 0
    assert "error:" in malformed.stderr
    assert _tree_state(host) == before

    database = host / "compile_commands.json"
    valid_payload = database.read_text(encoding="utf-8")
    database.write_text("{", encoding="utf-8")
    assert _database_state(host).state == "malformed"
    database.write_text(valid_payload, encoding="utf-8")
    incomplete = json.loads(valid_payload)[:1]
    database.write_text(json.dumps(incomplete), encoding="utf-8")
    assert _database_state(host).state == "incomplete"
    database.write_text(valid_payload, encoding="utf-8")
    mismatched = json.loads(valid_payload)
    mismatched[0]["directory"] = str(tmp_path)
    database.write_text(json.dumps(mismatched), encoding="utf-8")
    assert _database_state(host).state == "mismatched-directory"
    database.write_text(valid_payload, encoding="utf-8")
    wrong_language = json.loads(valid_payload)
    wrong_language[0]["file"] = str(host / "src" / "foreign.c")
    wrong_language[0]["arguments"][-3] = str(host / "src" / "foreign.c")
    database.write_text(json.dumps(wrong_language), encoding="utf-8")
    assert _database_state(host).state == "wrong-language"
    database.write_text(valid_payload, encoding="utf-8")
    wrong_mode = json.loads(valid_payload)
    wrong_mode[0]["arguments"][0] = "/usr/bin/clang"
    wrong_mode[0]["arguments"][1] = "-std=c17"
    database.write_text(json.dumps(wrong_mode), encoding="utf-8")
    assert _database_state(host).state == "wrong-mode"
    database.write_text(valid_payload, encoding="utf-8")
    newer = database.stat().st_mtime_ns + 2_000_000_000
    os.utime(host / "src" / "main.cpp", ns=(newer, newer))
    assert _database_state(host).state == "stale"
    restored = database.stat().st_mtime_ns - 1
    os.utime(host / "src" / "main.cpp", ns=(restored, restored))
    _materialize_database(host, clangxx, make)
    assert _database_state(host).state == "valid"


def test_cpp_generic_doctor_reports_markers_tools_missing_and_old(tmp_path: Path) -> None:
    clangxx = shutil.which("clang++")
    clangd = shutil.which("clangd")
    make = shutil.which("make")
    if clangxx is None or clangd is None or make is None:
        pytest.skip("Clang++/clangd/Make unavailable; missing state is covered below")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(host), "--language", "cpp"], tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "available"
    assert payload["project_markers"]["present"] == ["Makefile"]
    assert {row["id"]: row["status"] for row in payload["tools"]} == {"clangxx": "available", "clangd": "available", "make": "available"}

    _materialize_database(host, clangxx, make)
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(host), "--language", "cpp"], tmp_path)
    assert json.loads(completed.stdout)["project_markers"]["present"] == ["Makefile", "compile_commands.json"]

    missing_host = tmp_path / "missing"
    missing_host.mkdir()
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(missing_host), "--language", "cpp"], tmp_path, env={**os.environ, "PATH": ""})
    missing = json.loads(completed.stdout)
    assert missing["status"] == "unavailable"
    assert set(missing["status_reasons"]) == {"toolchain-unavailable", "project-metadata-unavailable"}
    assert all(row["reason"] == "not-found" for row in missing["tools"])

    old_host = tmp_path / "old"
    tools = old_host / ".tools"
    tools.mkdir(parents=True)
    (old_host / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
    versions = {"clang++": "Apple clang version 20.0.0", "clangd": "Apple clangd version 20.0.0", "make": "GNU Make 3.80"}
    for name, version in versions.items():
        path = tools / name
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
        path.chmod(0o755)
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(old_host), "--language", "cpp"], tmp_path, env={**os.environ, "PATH": ""})
    old = json.loads(completed.stdout)
    assert old["status"] == "too-old"
    assert old["status_reasons"] == ["toolchain-too-old"]
    assert all(row["reason"] == "below-minimum-version" for row in old["tools"])


def test_cpp_frozen_contracts_and_all_22_initial_dispositions() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    contracts = baseline["pilot_contracts"]
    assert contracts["lexical"]["skill"] == "find-comment-drift"
    assert contracts["lexical"]["disposition"] == "cpp-pending-implementation"
    assert contracts["semantic"]["skill"] == "map-subsystem"
    assert contracts["semantic"]["compile_database_gate"] == ["valid", "current", "complete", "C++20-mode", "no-fallback"]
    assert contracts["mutation"]["skill"] == "move-path"
    assert contracts["mutation"]["state"] == "deferred-until-semantic-lineage"
    assert baseline["mutation_performed"] is False

    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]
    assert coverage["decision"] == "expand"
    assert len(rows) == 22
    assert {row["skill"] for row in rows} == EXPECTED_SKILLS
    assert all(row["disposition"] == "cpp-pending-implementation" for row in rows)
    assert all(row["evidence_path"] and row["native_check"] and row["reviewed_revision"] and row["limitation"] for row in rows)
