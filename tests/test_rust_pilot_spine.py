"""Frozen Rust-only P7 spine, Cargo boundary, and pending-work truth."""
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
FIXTURE = ROOT / "tests" / "fixtures" / "rust-pilot"
PROFILE = ROOT / "scripts" / "language_profiles" / "rust.json"
BASELINE = ROOT / ".claude" / "tasks" / "p7-baseline" / "rust-pilot-baseline.json"
COVERAGE = ROOT / ".claude" / "tasks" / "rust-language-coverage.json"
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
        rows.append(
            (path.relative_to(root).as_posix(), hashlib.sha256(content).hexdigest(), len(content))
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


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: float = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _fake_tool(path: Path, output: str, *, exit_code: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' {json.dumps(output)}\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _fake_project_tools(
    host: Path,
    versions: dict[str, str],
    *,
    exit_code: int = 0,
) -> dict[str, Path]:
    names = {
        "rustc": "rustc",
        "cargo": "cargo",
        "rust-analyzer": "rust-analyzer",
        "cargo-clippy": "cargo-clippy",
        "rustfmt": "rustfmt",
    }
    return {
        tool_id: _fake_tool(
            host / ".tools" / "rust" / "bin" / filename,
            versions[tool_id],
            exit_code=exit_code,
        )
        for tool_id, filename in names.items()
        if tool_id in versions
    }


def _doctor(host: Path, *, path: str) -> dict[str, object]:
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DOCTOR),
            "--project-root",
            str(host),
            "--language",
            "rust",
        ],
        host.parent,
        env={**os.environ, "PATH": path},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _cargo_environment(state: Path) -> dict[str, str]:
    cargo_home = state / "cargo-home"
    cargo_home.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "CARGO_HOME": str(cargo_home),
        "CARGO_NET_OFFLINE": "true",
        "CARGO_TARGET_DIR": str(state / "target"),
        "ALL_PROXY": "http://127.0.0.1:9",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
    }


def test_rust_fixture_and_runtime_closure_match_frozen_manifests() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert _manifest(FIXTURE) == (
        baseline["fixture"]["manifest_sha256"],
        baseline["fixture"]["total_bytes"],
        baseline["fixture"]["files"],
    )

    closure = baseline["runtime_closure"]
    paths = [ROOT / path for path in closure["files"]]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    assert digest.hexdigest() == closure["manifest_sha256"]
    assert sum(path.stat().st_size for path in paths) == closure["total_bytes"]


def test_rust_profile_inventory_roles_workspace_symlink_and_preservation(
    tmp_path: Path,
) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["suffixes"] == [".rs"]
    assert profile["project_markers"] == ["Cargo.toml", "Cargo.lock"]
    assert [row["id"] for row in profile["native_tools"]] == [
        "rustc", "cargo", "rust-analyzer", "cargo-clippy", "rustfmt"
    ]
    assert set(profile["fact_tiers"]) == {
        "lexical-filesystem", "syntax", "semantic-project"
    }
    limits = "\n".join(profile["explicit_limits"])
    for boundary in (
        "Cargo.toml", "Cargo.lock", "build.rs", "examples", "benches",
        "procedural macros", "cfg/feature/target variants", "workspace inheritance",
    ):
        assert boundary in limits

    pilot = tmp_path / "rust-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "linked-external").symlink_to(
        pilot / "symlink-target", target_is_directory=True
    )
    before = _tree_state(host)
    completed = _run(
        [
            sys.executable, "-I", "-S", str(INVENTORY),
            "--project-root", str(host),
        ],
        tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _tree_state(host) == before
    payload = json.loads(completed.stdout)
    rust_files = {
        row["path"]: row for row in payload["files"] if row["language"] == "rust"
    }
    assert rust_files["crates/billing-core/src/lib.rs"]["role"] == "source"
    assert rust_files["crates/billing-core/src/invoice/mod.rs"]["role"] == "source"
    assert rust_files["crates/billing-core/src/invoice/service.rs"]["role"] == "source"
    assert rust_files["crates/billing-core/build.rs"]["role"] == "configuration"
    assert rust_files["crates/billing-core/tests/invoice_service.rs"]["role"] == "test"
    assert rust_files["crates/billing-core/examples/invoice_example.rs"]["role"] == "source"
    assert rust_files["crates/billing-core/benches/invoice_bench.rs"]["role"] == "source"
    assert rust_files["rustc/direct_smoke.rs"]["role"] == "source"
    assert rust_files["generated/GeneratedInvoice.rs"]["role"] == "generated"
    assert not ({"Cargo.toml", "Cargo.lock"} & rust_files.keys())
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded["target"] == "build"
    assert excluded["vendor"] == "vendor"
    assert excluded["linked-external"] == "symlink"
    assert not any(
        path.startswith(("target/", "vendor/", "linked-external/"))
        for path in rust_files
    )


def test_rust_native_copied_workspace_tools_and_invalid_boundaries(
    tmp_path: Path,
) -> None:
    required = {name: shutil.which(name) for name in ("rustc", "cargo")}
    optional = {
        name: shutil.which(name)
        for name in ("rust-analyzer", "cargo-clippy", "rustfmt")
    }
    if any(path is None for path in (*required.values(), *optional.values())):
        pytest.skip("Rust native toolchain unavailable; the profile doctor reports this boundary")
    rustc = str(required["rustc"])
    cargo = str(required["cargo"])
    rust_analyzer = str(optional["rust-analyzer"])
    host = tmp_path / "copied-host"
    shutil.copytree(FIXTURE / "host", host)
    state = tmp_path / "rust-state"
    environment = _cargo_environment(state)
    before = _tree_state(host)

    metadata = _run(
        [cargo, "metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"],
        host,
        env=environment,
    )
    assert metadata.returncode == 0, metadata.stdout + metadata.stderr
    graph = json.loads(metadata.stdout)
    packages = {row["name"]: row for row in graph["packages"]}
    assert set(packages) == {"billing-core", "rust-pilot-smoke"}
    assert set(graph["workspace_members"]) == {
        package["id"] for package in packages.values()
    }
    target_kinds = {
        kind
        for package in packages.values()
        for target in package["targets"]
        for kind in target["kind"]
    }
    assert {"lib", "bin", "test", "example", "bench", "custom-build"} <= target_kinds
    assert packages["billing-core"]["features"] == {"default": [], "experimental": []}

    for argv in (
        [cargo, "check", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
        [cargo, "test", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
        [cargo, "clippy", "--locked", "--offline", "--workspace", "--all-targets", "--all-features", "--", "-D", "warnings"],
        [cargo, "fmt", "--all", "--", "--check"],
    ):
        completed = _run(argv, host, env=environment)
        assert completed.returncode == 0, completed.stdout + completed.stderr

    smoke = _run(
        [cargo, "run", "--quiet", "--locked", "--offline", "-p", "rust-pilot-smoke"],
        host,
        env=environment,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "invoice:INV-42:125\n"

    direct_test = state / "rustc-direct-test"
    compiled_test = _run(
        [rustc, "--edition=2024", "--test", str(host / "rustc/direct_smoke.rs"), "-o", str(direct_test)],
        host,
    )
    assert compiled_test.returncode == 0, compiled_test.stdout + compiled_test.stderr
    tested = _run([str(direct_test), "--quiet"], host)
    assert tested.returncode == 0, tested.stdout + tested.stderr
    assert "1 passed" in tested.stdout

    direct_smoke = state / "rustc-direct-smoke"
    compiled_smoke = _run(
        [rustc, "--edition=2024", str(host / "rustc/direct_smoke.rs"), "-o", str(direct_smoke)],
        host,
    )
    assert compiled_smoke.returncode == 0, compiled_smoke.stdout + compiled_smoke.stderr
    smoked = _run([str(direct_smoke)], host)
    assert smoked.returncode == 0
    assert smoked.stdout == "rustc:INV-42:ok\n"

    analyzed = _run(
        [
            rust_analyzer, "analysis-stats", str(host),
            "--disable-build-scripts", "--disable-proc-macros", "--no-test",
        ],
        host,
        env=environment,
    )
    assert analyzed.returncode == 0, analyzed.stdout + analyzed.stderr
    analysis_output = analyzed.stdout + analyzed.stderr
    assert "Workspace:" in analysis_output
    assert "proc_macros: 0" in analysis_output

    malformed = _run(
        [
            rustc, "--edition=2024", "--crate-type=lib", "--emit=metadata",
            str(FIXTURE / "malformed" / "Broken.rs"), "-o", str(state / "broken.rmeta"),
        ],
        host,
    )
    assert malformed.returncode != 0
    assert "unclosed delimiter" in malformed.stderr
    assert _tree_state(host) == before

    invalid = tmp_path / "invalid-manifest"
    shutil.copytree(FIXTURE / "host", invalid)
    (invalid / "Cargo.toml").write_text("[workspace\n", encoding="utf-8")
    invalid_before = _tree_state(invalid)
    rejected = _run(
        [cargo, "metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"],
        invalid,
        env=_cargo_environment(tmp_path / "invalid-state"),
    )
    assert rejected.returncode != 0
    assert "Cargo.toml" in rejected.stderr
    assert _tree_state(invalid) == invalid_before

    stale = tmp_path / "stale-lock"
    shutil.copytree(FIXTURE / "host", stale)
    lock = stale / "Cargo.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace(
            '\n[[package]]\nname = "rust-pilot-smoke"\nversion = "0.1.0"\n'
            'dependencies = [\n "billing-core",\n]\n',
            "",
        ),
        encoding="utf-8",
    )
    stale_before = _tree_state(stale)
    stale_result = _run(
        [cargo, "check", "--locked", "--offline", "--workspace"],
        stale,
        env=_cargo_environment(tmp_path / "stale-state"),
    )
    assert stale_result.returncode != 0
    assert "cannot update the lock file" in stale_result.stderr
    assert _tree_state(stale) == stale_before


def test_rust_doctor_strict_available_missing_old_broken_and_optional_states(
    tmp_path: Path,
) -> None:
    host = tmp_path / "real-host"
    shutil.copytree(FIXTURE / "host", host)
    real = _doctor(host, path=os.environ.get("PATH", ""))
    tools = {row["id"]: row for row in real["tools"]}
    assert real["status"] == "available"
    assert real["project_markers"]["present"] == ["Cargo.toml", "Cargo.lock"]
    assert {tool_id: tools[tool_id]["version"] for tool_id in tools} == {
        "rustc": "1.97.1",
        "cargo": "1.97.1",
        "rust-analyzer": "1.97.1",
        "cargo-clippy": "0.1.97",
        "rustfmt": "1.9.0",
    }
    assert tools["rustc"]["required"] is True
    assert tools["cargo"]["required"] is True
    assert all(
        tools[tool_id]["required"] is False
        for tool_id in ("rust-analyzer", "cargo-clippy", "rustfmt")
    )

    local = tmp_path / "local"
    local.mkdir()
    (local / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    local_tools = _fake_project_tools(
        local,
        {
            "rustc": "rustc 1.97.2 (fixture)",
            "cargo": "cargo 1.97.2 (fixture)",
            "rust-analyzer": "rust-analyzer 1.97.2 (fixture)",
            "cargo-clippy": "clippy 0.1.97 (fixture)",
            "rustfmt": "rustfmt 1.9.1-stable (fixture)",
        },
    )
    system_bin = tmp_path / "system-bin"
    system_bin.mkdir()
    for name, output in {
        "rustc": "rustc 9.0.0", "cargo": "cargo 9.0.0",
        "rust-analyzer": "rust-analyzer 9.0.0", "cargo-clippy": "clippy 9.0.0",
        "rustfmt": "rustfmt 9.0.0",
    }.items():
        _fake_tool(system_bin / name, output)
    local_payload = _doctor(local, path=str(system_bin))
    assert local_payload["status"] == "available"
    assert {
        row["id"]: (row["path"], row["provenance"])
        for row in local_payload["tools"]
    } == {
        tool_id: (str(path.absolute()), "project-local")
        for tool_id, path in local_tools.items()
    }

    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    missing_payload = _doctor(missing, path="")
    assert missing_payload["status"] == "unavailable"
    assert missing_payload["status_reasons"] == ["toolchain-unavailable"]
    assert all(row["reason"] == "not-found" for row in missing_payload["tools"])

    old = tmp_path / "old"
    old.mkdir()
    (old / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    _fake_project_tools(
        old,
        {
            "rustc": "rustc 1.84.1", "cargo": "cargo 1.84.1",
            "rust-analyzer": "rust-analyzer 1.84.1",
            "cargo-clippy": "clippy 0.1.84", "rustfmt": "rustfmt 1.7.1",
        },
    )
    old_payload = _doctor(old, path="")
    assert old_payload["status"] == "too-old"
    assert old_payload["status_reasons"] == ["toolchain-too-old"]
    assert all(row["reason"] == "below-minimum-version" for row in old_payload["tools"])

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    _fake_project_tools(
        broken,
        {tool_id: "broken" for tool_id in (
            "rustc", "cargo", "rust-analyzer", "cargo-clippy", "rustfmt"
        )},
        exit_code=7,
    )
    broken_payload = _doctor(broken, path="")
    assert broken_payload["status"] == "unavailable"
    assert all(
        row["reason"] == "version-command-failed" for row in broken_payload["tools"]
    )

    optional_missing = tmp_path / "optional-missing"
    optional_missing.mkdir()
    (optional_missing / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    _fake_project_tools(
        optional_missing,
        {"rustc": "rustc 1.97.1", "cargo": "cargo 1.97.1"},
    )
    optional_payload = _doctor(optional_missing, path="")
    assert optional_payload["status"] == "limited"
    assert optional_payload["status_reasons"] == ["partial-toolchain"]
    optional_tools = {row["id"]: row for row in optional_payload["tools"]}
    assert {optional_tools[name]["status"] for name in ("rustc", "cargo")} == {"available"}
    assert all(
        optional_tools[name]["status"] == "unavailable"
        and optional_tools[name]["required"] is False
        for name in ("rust-analyzer", "cargo-clippy", "rustfmt")
    )

    no_metadata = tmp_path / "no-metadata"
    no_metadata.mkdir()
    _fake_project_tools(
        no_metadata,
        {
            "rustc": "rustc 1.97.1", "cargo": "cargo 1.97.1",
            "rust-analyzer": "rust-analyzer 1.97.1",
            "cargo-clippy": "clippy 0.1.97", "rustfmt": "rustfmt 1.9.0",
        },
    )
    invalid_metadata = _doctor(no_metadata, path="")
    assert invalid_metadata["status"] == "limited"
    assert invalid_metadata["status_reasons"] == ["project-metadata-unavailable"]


def test_rust_frozen_cohort_contracts_and_all_22_initial_dispositions() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    contracts = baseline["pilot_contracts"]
    lexical = contracts["lexical"]
    assert lexical["skill"] == "find-comment-drift"
    assert lexical["disposition"] == "rust-pending-implementation"
    assert lexical["positive_obligation"]["path"] == (
        "host/crates/billing-core/src/invoice/service.rs"
    )
    assert {"generated", "vendor", "target", "test", "attributes"} <= set(
        lexical["must_not_fire"]
    )
    assert {"cargo check", "rustfmt check", "copied closure", "source fingerprint"} <= set(
        lexical["native_obligations"]
    )

    semantic = contracts["semantic"]
    assert semantic["skill"] == "map-subsystem"
    assert semantic["disposition"] == "rust-pending-implementation"
    assert semantic["cargo_gate"] == [
        "valid", "locked", "offline", "workspace-complete", "all-targets", "all-features"
    ]
    assert {"macro_rules expansion", "procedural macros", "build-script outputs", "cfg variants"} <= set(
        semantic["must_not_resolve_without_evidence"]
    )
    assert {"cargo metadata", "cargo check", "cargo test", "executable smoke"} <= set(
        semantic["native_obligations"]
    )

    mutation = contracts["mutation"]
    assert mutation["skill"] == "move-path"
    assert mutation["disposition"] == "rust-pending-implementation"
    assert mutation["candidate_move"] == {
        "from": "crates/billing-core/src/invoice/service.rs",
        "to": "crates/billing-core/src/invoice/invoice_service.rs",
    }
    assert {"include!", "procedural macros", "build.rs output", "cfg-dependent modules"} <= set(
        mutation["refusal_boundaries"]
    )
    assert {
        "preview", "exact bounded diff", "source fingerprint", "rollback",
        "cargo metadata", "cargo check", "cargo test", "Clippy", "rustfmt",
        "executable smoke",
    } <= set(mutation["native_obligations"])
    assert baseline["stale_artifact_contract"] == {
        "invalid-or-failed": "remove prior final artifacts before emitting the failure state",
        "clean-or-complete": "atomically replace prior artifacts; never inherit stale findings",
        "same-destination": "valid-to-failed and failed-to-valid transitions are mandatory",
    }
    assert baseline["mutation_performed"] is False

    tool_sources = baseline["tool_reuse"]
    assert tool_sources["stable_required"] == ["rustc", "Cargo"]
    assert tool_sources["rustup_optional_components"] == [
        "rust-analyzer", "Clippy", "rustfmt"
    ]
    assert tool_sources["forbidden_portability_dependency"] == ["private rustc APIs"]

    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]
    assert coverage["decision"] == "expand"
    assert len(rows) == 22
    assert {row["skill"] for row in rows} == EXPECTED_SKILLS
    dispositions = {row["skill"]: row["disposition"] for row in rows}
    assert dispositions["find-comment-drift"] == "rust-supported"
    assert dispositions["move-path"] == "rust-supported"
    assert dispositions["map-subsystem"] == "rust-partial"
    assert sum(value == "rust-pending-implementation" for value in dispositions.values()) == 19
    assert all(
        row["evidence_path"]
        and row["native_check"]
        and row["reviewed_revision"]
        and row["limitation"]
        for row in rows
    )
    assert "rust-unsupported" not in {row["disposition"] for row in rows}
