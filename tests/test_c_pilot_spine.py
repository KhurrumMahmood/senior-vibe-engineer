"""Frozen C-only P7 spine, compile-database gate, and unsupported truth."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "c-pilot"
BASELINE = ROOT / ".claude" / "tasks" / "p7-baseline" / "c-pilot-baseline.json"
COVERAGE = ROOT / ".claude" / "tasks" / "c-language-coverage.json"
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


def _source_state(host: Path) -> dict[str, str]:
    suffixes = {".c", ".h", ".inc"}
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and path.suffix in suffixes
    }


def _run(argv: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, check=False,
        timeout=30,
    )


def _materialize_database(host: Path, clang: str, make: str) -> None:
    completed = _run([make, "clean", "compile-db", f"CC={clang}"], host)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _database_state(host: Path) -> tuple[str, list[dict[str, object]]]:
    database = host / "compile_commands.json"
    if not database.is_file():
        return "missing", []
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return "malformed", []
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        return "malformed", []
    expected = {(host / "src" / name).resolve() for name in ("invoice.c", "main.c")}
    actual: set[Path] = set()
    for row in payload:
        if set(row) != {"directory", "file", "arguments"}:
            return "malformed", []
        if Path(str(row["directory"])) != host.resolve():
            return "mismatched-directory", []
        file_path = Path(str(row["file"]))
        arguments = row["arguments"]
        if not file_path.is_absolute() or not isinstance(arguments, list):
            return "malformed", []
        if any(not isinstance(token, str) for token in arguments):
            return "malformed", []
        if "-std=c17" not in arguments or "-c" not in arguments:
            return "non-c-command", []
        actual.add(file_path)
    if actual != expected:
        return "incomplete", []
    inputs = [
        host / "Makefile", host / "src" / "invoice.c", host / "src" / "main.c",
        host / "src" / "invoice_internal.h", host / "src" / "pilot_mode.inc",
        host / "include" / "cpilot" / "invoice.h",
    ]
    if database.stat().st_mtime_ns < max(path.stat().st_mtime_ns for path in inputs):
        return "stale", []
    return "valid", payload


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


def test_c_fixture_and_runtime_closure_match_frozen_manifests() -> None:
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


def test_c_generic_inventory_roles_header_ambiguity_symlink_and_preservation(tmp_path: Path) -> None:
    pilot = tmp_path / "c-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "linked-external").symlink_to(pilot / "symlink-target", target_is_directory=True)
    before = _source_state(host)
    completed = _run([sys.executable, "-I", "-S", str(INVENTORY), "--project-root", str(host)], tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _source_state(host) == before
    payload = json.loads(completed.stdout)
    files = {row["path"]: row for row in payload["files"]}
    assert files["src/invoice.c"]["role"] == "source"
    assert files["src/main.c"]["role"] == "source"
    assert files["tests/invoice_test.c"]["role"] == "test"
    assert files["generated/GeneratedInvoice.c"]["role"] == "generated"
    assert files["foreign/Foreign.cpp"]["language"] == "cpp"
    assert not any(
        path.endswith((".h", ".inc", ".m", ".mm", ".cu", ".cl", ".S"))
        for path in files
    )
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded["build"] == "build"
    assert excluded["vendor"] == "vendor"
    assert excluded["linked-external"] == "symlink"


def test_c_native_build_syntax_ast_tokens_malformed_and_database_gate(tmp_path: Path) -> None:
    clang = shutil.which("clang")
    clangd = shutil.which("clangd")
    make = shutil.which("make")
    if clang is None or clangd is None or make is None:
        pytest.skip("Clang/clangd/Make unavailable; the generic doctor reports this boundary")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    before = _source_state(host)

    built = _run([make, "clean", "test", f"CC={clang}"], host, env={**os.environ, "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "ALL_PROXY": "http://127.0.0.1:9"})
    assert built.returncode == 0, built.stdout + built.stderr
    smoke = _run([str(host / ".native-build" / "c-pilot-smoke")], host)
    assert smoke.returncode == 0
    assert smoke.stdout == "invoice:INV-42:1:pilot\n"

    assert _database_state(host)[0] == "missing"
    _materialize_database(host, clang, make)
    state, entries = _database_state(host)
    assert state == "valid"
    assert len(entries) == 2
    for entry in entries:
        compiled = _run(list(entry["arguments"]), host)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    checked = _run(
        [
            clangd,
            f"--check={host / 'src' / 'invoice.c'}",
            f"--compile-commands-dir={host}",
            "--log=verbose",
        ],
        host,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "Compile command from CDB is" in checked.stdout + checked.stderr

    invoice_entry = next(row for row in entries if str(row["file"]).endswith("/invoice.c"))
    ast = _run(_analysis_argv(invoice_entry, "-Xclang", "-ast-dump=json", "-fsyntax-only"), host)
    assert ast.returncode == 0, ast.stdout + ast.stderr
    ast_payload = json.loads(ast.stdout)
    assert ast_payload["kind"] == "TranslationUnitDecl"
    assert '"name": "invoice_render"' in ast.stdout
    tokens = _run(_analysis_argv(invoice_entry, "-Xclang", "-dump-raw-tokens", "-fsyntax-only"), host)
    assert tokens.returncode == 0
    assert "decision: keep the sequence translation-unit local" in tokens.stdout + tokens.stderr
    dependencies = _run(_analysis_argv(invoice_entry, "-MM"), host)
    assert dependencies.returncode == 0, dependencies.stdout + dependencies.stderr
    assert "include/cpilot/invoice.h" in dependencies.stdout
    assert "src/invoice_internal.h" in dependencies.stdout
    assert "src/pilot_mode.inc" in dependencies.stdout
    assert "orphan.h" not in dependencies.stdout and "orphan.inc" not in dependencies.stdout

    malformed = _run([clang, "-x", "c", "-std=c17", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only", str(FIXTURE / "malformed" / "Broken.c")], host)
    assert malformed.returncode != 0
    assert "error:" in malformed.stderr
    assert _source_state(host) == before

    database = host / "compile_commands.json"
    valid_payload = database.read_text(encoding="utf-8")
    database.write_text("{", encoding="utf-8")
    assert _database_state(host)[0] == "malformed"
    database.write_text(valid_payload, encoding="utf-8")
    incomplete = json.loads(valid_payload)[:1]
    database.write_text(json.dumps(incomplete), encoding="utf-8")
    assert _database_state(host)[0] == "incomplete"
    database.write_text(valid_payload, encoding="utf-8")
    mismatched = json.loads(valid_payload)
    mismatched[0]["directory"] = str(tmp_path)
    database.write_text(json.dumps(mismatched), encoding="utf-8")
    assert _database_state(host)[0] == "mismatched-directory"
    database.write_text(valid_payload, encoding="utf-8")
    newer = database.stat().st_mtime_ns + 2_000_000_000
    os.utime(host / "src" / "main.c", ns=(newer, newer))
    assert _database_state(host)[0] == "stale"


def test_c_generic_doctor_reports_markers_tools_missing_and_old(tmp_path: Path) -> None:
    clang = shutil.which("clang")
    clangd = shutil.which("clangd")
    make = shutil.which("make")
    if clang is None or clangd is None or make is None:
        pytest.skip("Clang/clangd/Make unavailable; missing state is covered below")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(host), "--language", "c"], tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "available"
    assert payload["project_markers"]["present"] == ["Makefile"]
    assert {row["id"]: row["status"] for row in payload["tools"]} == {"clang": "available", "clangd": "available", "make": "available"}

    _materialize_database(host, clang, make)
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(host), "--language", "c"], tmp_path)
    payload = json.loads(completed.stdout)
    assert payload["project_markers"]["present"] == ["Makefile", "compile_commands.json"]

    missing_host = tmp_path / "missing"
    missing_host.mkdir()
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(missing_host), "--language", "c"], tmp_path, env={**os.environ, "PATH": ""})
    missing = json.loads(completed.stdout)
    assert missing["status"] == "unavailable"
    assert set(missing["status_reasons"]) == {"toolchain-unavailable", "project-metadata-unavailable"}
    assert all(row["reason"] == "not-found" for row in missing["tools"])

    old_host = tmp_path / "old"
    tools = old_host / ".tools"
    tools.mkdir(parents=True)
    (old_host / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
    versions = {"clang": "Apple clang version 20.0.0", "clangd": "Apple clangd version 20.0.0", "make": "GNU Make 3.80"}
    for name, version in versions.items():
        path = tools / name
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
        path.chmod(0o755)
    completed = _run([sys.executable, "-I", "-S", str(DOCTOR), "--project-root", str(old_host), "--language", "c"], tmp_path, env={**os.environ, "PATH": ""})
    old = json.loads(completed.stdout)
    assert old["status"] == "too-old"
    assert old["status_reasons"] == ["toolchain-too-old"]
    assert all(row["reason"] == "below-minimum-version" for row in old["tools"])


def test_c_frozen_contracts_and_all_22_initial_dispositions() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    contracts = baseline["pilot_contracts"]
    assert contracts["lexical"]["skill"] == "find-comment-drift"
    assert contracts["lexical"]["disposition"] == "c-pending-implementation"
    assert contracts["semantic"]["skill"] == "map-subsystem"
    assert contracts["semantic"]["compile_database_gate"] == ["valid", "current", "complete", "C-mode", "no-fallback"]
    assert contracts["mutation"]["skill"] == "move-path"
    assert contracts["mutation"]["state"] == "deferred-until-semantic-lineage"
    assert baseline["mutation_performed"] is False

    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]
    assert coverage["decision"] == "expand"
    assert len(rows) == 22
    assert {row["skill"] for row in rows} == EXPECTED_SKILLS
    assert {
        row["skill"] for row in rows if row["disposition"] == "c-supported"
    } == {"find-comment-drift", "map-subsystem"}
    assert sum(row["disposition"] == "c-pending-implementation" for row in rows) == 20
    assert all(
        row["evidence_path"]
        and row["native_check"]
        and row["reviewed_revision"]
        and row["limitation"]
        for row in rows
    )
