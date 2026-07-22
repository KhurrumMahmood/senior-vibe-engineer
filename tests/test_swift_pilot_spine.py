"""Frozen SwiftPM-only P7 spine, native boundary, and unsupported truth."""
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
FIXTURE = ROOT / "tests" / "fixtures" / "swift-pilot"
BASELINE = ROOT / ".claude" / "tasks" / "p7-baseline" / "swift-pilot-baseline.json"
COVERAGE = ROOT / ".claude" / "tasks" / "swift-language-coverage.json"
INVENTORY = ROOT / "scripts" / "source_inventory.py"

EXPECTED_SKILLS = {
    "adapt-project",
    "audit-decisions",
    "explain-code",
    "extract-enum",
    "find-comment-drift",
    "find-complexity-hotspots",
    "find-concept-divergence",
    "find-dormant",
    "find-duplication",
    "find-folder-topology-drift",
    "find-implicit-state",
    "find-incomplete-sweep",
    "find-omnibus",
    "find-semantic-duplication",
    "find-standard-gaps",
    "map-subsystem",
    "move-path",
    "prevent-regression",
    "propose-boundary",
    "propose-folder-reorganization",
    "rename-concept",
    "unify-shadows",
}


def _manifest(root: Path) -> tuple[str, int, list[str]]:
    rows: list[tuple[str, str, int]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        content = path.read_bytes()
        rows.append(
            (
                path.relative_to(root).as_posix(),
                hashlib.sha256(content).hexdigest(),
                len(content),
            )
        )
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
        elif path.is_file():
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _restrictive_build_command(swift: str, host: Path, state: Path) -> list[str]:
    return [
        swift,
        "build",
        "--package-path",
        str(host),
        "--cache-path",
        str(state / "cache"),
        "--config-path",
        str(state / "config"),
        "--security-path",
        str(state / "security"),
        "--scratch-path",
        str(state / "build"),
        "--disable-dependency-cache",
        "--manifest-cache",
        "local",
        "--disable-netrc",
        "--disable-keychain",
        "--disable-prefetching",
        "--disable-automatic-resolution",
        "--enable-index-store",
        "--product",
        "swift-pilot-smoke",
    ]


def test_swift_pilot_fixture_and_runtime_closure_match_frozen_manifests() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    fixture_digest, fixture_bytes, fixture_files = _manifest(FIXTURE)
    assert fixture_digest == baseline["fixture"]["manifest_sha256"]
    assert fixture_bytes == baseline["fixture"]["total_bytes"]
    assert fixture_files == baseline["fixture"]["files"]

    closure = baseline["runtime_closure"]
    closure_root = ROOT
    rows = [closure_root / path for path in closure["files"]]
    digest = hashlib.sha256()
    for path in rows:
        file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(path.relative_to(closure_root).as_posix().encode())
        digest.update(b"\0" + file_digest.encode() + b"\n")
    assert digest.hexdigest() == closure["manifest_sha256"]
    assert sum(path.stat().st_size for path in rows) == closure["total_bytes"]


def test_swift_inventory_roles_symlink_boundary_and_no_mutation(tmp_path: Path) -> None:
    pilot = tmp_path / "swift-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "LinkedExternal").symlink_to(
        pilot / "symlink-target", target_is_directory=True
    )
    before = _tree_state(host)

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(INVENTORY),
            "--project-root",
            str(host),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _tree_state(host) == before
    payload = json.loads(completed.stdout)
    files = {row["path"]: row for row in payload["files"]}
    assert files["Package.swift"]["role"] == "configuration"
    assert files["Sources/BillingCore/BillingCore.swift"]["role"] == "source"
    assert files["Sources/SwiftPilotSmoke/main.swift"]["role"] == "source"
    assert files["Tests/BillingCoreTests/InvoiceServiceTests.swift"]["role"] == "test"
    assert files["generated/GeneratedInvoice.swift"]["role"] == "generated"
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded[".build"] == "build"
    assert excluded["vendor"] == "vendor"
    assert excluded["LinkedExternal"] == "symlink"
    assert not any(path.startswith((".build/", "vendor/", "LinkedExternal/")) for path in files)


def test_swift_native_restrictive_build_smoke_ast_and_malformed_boundary(
    tmp_path: Path,
) -> None:
    swift = shutil.which("swift")
    swiftc = shutil.which("swiftc")
    if swift is None or swiftc is None:
        pytest.skip("Swift/Swiftc unavailable; the profile doctor reports this boundary")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    state = tmp_path / "swift-state"
    for directory in ("cache", "config", "security"):
        (state / directory).mkdir(parents=True, exist_ok=True)
    before = _tree_state(host)

    built = subprocess.run(
        _restrictive_build_command(swift, host, state),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    smoke = subprocess.run(
        [str(state / "build" / "debug" / "swift-pilot-smoke")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "invoice:INV-42:fixed-2026\n"

    source = host / "Sources" / "BillingCore" / "BillingCore.swift"
    typed = subprocess.run(
        [swiftc, "-typecheck", str(source)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert typed.returncode == 0, typed.stdout + typed.stderr
    ast = subprocess.run(
        [swiftc, "-dump-ast", str(source)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ast.returncode == 0, ast.stdout + ast.stderr
    assert 'struct_decl' in ast.stdout
    assert '"InvoiceService"' in ast.stdout

    malformed = subprocess.run(
        [swiftc, "-typecheck", str(FIXTURE / "malformed" / "Broken.swift")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert malformed.returncode != 0
    assert "expected '}' in struct" in malformed.stdout + malformed.stderr
    assert _tree_state(host) == before


def test_swift_frozen_cohorts_preserve_fact_and_mutation_boundaries() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    cohorts = baseline["pilot_cohorts"]

    syntax = cohorts["syntax"]
    assert syntax["skill"] == "find-omnibus"
    assert syntax["producer"] == "swiftc compiler syntax/typecheck and -dump-ast"
    assert syntax["disposition"] == "swift-unsupported"
    assert "SwiftSyntax" in syntax["forbidden_claims"]

    semantic = cohorts["semantic-project"]
    assert semantic["skill"] == "map-subsystem"
    assert semantic["disposition"] == "swift-unsupported"
    assert semantic["mixed_target_policy"] == "any selected-target failure makes the final outcome partial or failed, never clean/complete"
    assert {"SwiftPM manifest/target graph", "successful build/index facts", "SourceKit-LSP references"} <= set(semantic["required_facts"])

    mutation = cohorts["mutation"]
    assert mutation["skill"] == "move-path"
    assert mutation["disposition"] == "swift-unsupported"
    assert mutation["scope"] == "one SwiftPM source-file or target-directory move"
    assert {"preview", "source fingerprint", "rollback", "restrictive swift build", "executable smoke"} <= set(mutation["required_proofs"])
    assert baseline["mutation_performed"] is False


def test_all_22_swift_skill_rows_remain_explicitly_unsupported() -> None:
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]

    assert coverage["decision"] == "spine-only"
    assert len(rows) == 22
    assert {row["skill"] for row in rows} == EXPECTED_SKILLS
    assert {row["disposition"] for row in rows} == {"swift-unsupported"}
    assert all(row["evidence_path"] == ".claude/tasks/p7-baseline/swift-pilot-baseline.json" for row in rows)
    assert all(row["limitation"] and row["native_check"] for row in rows)
