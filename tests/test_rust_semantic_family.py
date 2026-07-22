"""Final-artifact tests for the bounded Rust semantic skill family."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/rust-semantic-family/host"
COMMON = ROOT / ".claude/skills/map-subsystem/scripts/rust_semantic_facts.py"
SCRIPTS = {
    "dormant": ROOT / ".claude/skills/find-dormant/scripts/detect_rust_dormant.py",
    "state": ROOT / ".claude/skills/find-implicit-state/scripts/detect_rust_state.py",
    "sweep": ROOT / ".claude/skills/find-incomplete-sweep/scripts/detect_rust_incomplete_sweep.py",
    "duplicate": ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_rust_semantic.py",
    "rename": ROOT / ".claude/skills/rename-concept/scripts/rust_identifier_evidence.py",
}
CARGO = shutil.which("cargo")
RUSTC = shutil.which("rustc")
RUST_ANALYZER = shutil.which("rust-analyzer")
CLIPPY = shutil.which("cargo-clippy")
RUSTFMT = shutil.which("rustfmt")
pytestmark = pytest.mark.skipif(
    any(tool is None for tool in (CARGO, RUSTC, RUST_ANALYZER, CLIPPY, RUSTFMT)),
    reason="Rust 1.85+, Cargo, rust-analyzer, Clippy, and rustfmt are required",
)


def _run(
    *args: str, cwd: Path, env: dict[str, str] | None = None, timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=timeout
    )


def _module():
    spec = importlib.util.spec_from_file_location("test_rust_semantic_facts", COMMON)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _host(tmp_path: Path, *, history: bool = True) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    (host / "semantic-core/src/linked.rs").symlink_to("dormant.rs")
    if not history:
        return host
    present = [host / f"semantic-core/src/sweep/present_{name}.rs" for name in "abc"]
    canonical = [path.read_text(encoding="utf-8") for path in present]
    module = host / "semantic-core/src/sweep/mod.rs"
    canonical_module = module.read_text(encoding="utf-8")
    for path in present:
        path.unlink()
    module.write_text(
        "\n".join(
            line
            for line in canonical_module.splitlines()
            if not line.startswith("pub mod present_")
        )
        + "\n",
        encoding="utf-8",
    )
    assert _run("git", "init", "-q", cwd=host).returncode == 0
    _run("git", "config", "user.email", "fixture@example.com", cwd=host)
    _run("git", "config", "user.name", "Fixture", cwd=host)
    old_env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
    }
    assert _run("git", "add", ".", cwd=host, env=old_env).returncode == 0
    assert _run("git", "commit", "-qm", "initial", cwd=host, env=old_env).returncode == 0
    for path, value in zip(present, canonical, strict=True):
        path.write_text(value, encoding="utf-8")
    module.write_text(canonical_module, encoding="utf-8")
    new_env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2024-02-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2024-02-01T00:00:00Z",
    }
    assert (
        _run(
            "git",
            "add",
            str(module.relative_to(host)),
            *[str(path.relative_to(host)) for path in present],
            cwd=host,
            env=new_env,
        ).returncode
        == 0
    )
    assert _run("git", "commit", "-qm", "audit sweep", cwd=host, env=new_env).returncode == 0
    return host


def _source_bytes(host: Path) -> dict[str, str]:
    rows = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".agents", ".git", "reports", "target"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


QUERIES = [
    "used_helper",
    "dormant_discount",
    "unsafe_dormant",
    "state",
    "status",
    "phase",
    "ChargeOptions",
    "summarize_invoice",
    "build_statement",
    "wrapper_decoy",
    "policy_decoy",
    "LegacyStatus",
    "CanonicalStatus",
]


def _facts(host: Path, tmp_path: Path, **tools: str) -> dict:
    return _module().collect(
        host,
        "semantic-core",
        QUERIES,
        cargo=tools.get("cargo", str(CARGO)),
        rustc=tools.get("rustc", str(RUSTC)),
        rust_analyzer=tools.get("rust_analyzer", str(RUST_ANALYZER)),
        cargo_target_dir=tmp_path / "facts-target",
    )


def _write_facts(payload: dict, path: Path) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _native(host: Path, tmp_path: Path, label: str) -> None:
    env = {
        **os.environ,
        "CARGO_NET_OFFLINE": "true",
        "CARGO_TARGET_DIR": str(tmp_path / f"native-{label}"),
    }
    commands = [
        (str(CARGO), "metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"),
        (
            str(CARGO),
            "check",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ),
        (
            str(CARGO),
            "test",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ),
        (
            str(CARGO),
            "clippy",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--",
            "-D",
            "warnings",
        ),
        (str(CARGO), "fmt", "--all", "--", "--check"),
    ]
    for command in commands:
        result = _run(*command, cwd=host, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(
        str(CARGO),
        "run",
        "--quiet",
        "--locked",
        "--offline",
        "-p",
        "semantic-smoke",
        cwd=host,
        env=env,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "33\n"


def _consumer_runs(host: Path, facts: Path, scripts: dict[str, Path] = SCRIPTS) -> None:
    calls = [
        (scripts["dormant"], "--output-dir", "reports/find-dormant/rust"),
        (scripts["state"], "--output-dir", "reports/implicit-state/rust"),
        (scripts["sweep"], "--report-dir", "reports/find-incomplete-sweep/rust"),
        (scripts["duplicate"], "--output-dir", "reports/semantic-duplication/rust"),
    ]
    for script, output_flag, output in calls:
        result = _run(
            sys.executable,
            str(script),
            "--project-root",
            str(host),
            "--target",
            "semantic-core",
            output_flag,
            output,
            "--facts",
            str(facts),
            cwd=host,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_rust_semantic_family_produces_five_distinct_read_only_handoffs(tmp_path: Path) -> None:
    host = _host(tmp_path)
    _native(host, tmp_path, "before")
    before = _source_bytes(host)
    payload = _facts(host, tmp_path)
    assert payload["status"] == "complete"
    assert payload["compiler"]["state"] == "clean"
    assert payload["semantic_analysis"]["state"] == "complete"
    assert payload["semantic_analysis"]["selected_definitions"]["protocol"] == "LSP"
    assert payload["semantic_analysis"]["selected_definitions"]["unstable_cli_used"] is False
    assert payload["fact_pack_sha256"]
    roles = {row["path"]: row["role"] for row in payload["source_inventory"]}
    assert roles["semantic-core/src/dormant.rs"] == "production-module"
    assert roles["semantic-core/tests/semantic_test.rs"] == "test"
    assert roles["semantic-core/examples/semantic_example.rs"] == "example"
    assert roles["semantic-core/benches/semantic_bench.rs"] == "bench"
    assert roles["semantic-core/build.rs"] == "custom-build"
    assert roles["generated/Generated.rs"] == "generated"
    assert roles["vendor/Vendor.rs"] == "vendor"
    assert roles["target/Target.rs"] == "target-output"
    assert roles["semantic-core/src/linked.rs"] == "symlink-excluded"
    assert any("procedural-macro" in limit for limit in payload["limits"])
    assert any(row["kind"] == "unsafe" for row in payload["unsafe_ffi_boundaries"])
    assert any(
        row["name"] == "derive" and row["expanded"] is False
        for row in payload["attribute_boundaries"]
    )
    assert payload["macro_regions"] and all(
        row["expanded"] is False for row in payload["macro_regions"]
    )

    facts_path = _write_facts(payload, tmp_path / "facts.json")
    _consumer_runs(host, facts_path)
    assert _source_bytes(host) == before

    dormant = json.loads((host / "reports/find-dormant/rust/findings.json").read_text())
    assert dormant["schema_version"] == "rust-dormant-v1"
    assert dormant["summary"]["certain_delete"] == 0
    assert [row["name"] for row in dormant["candidates"]] == ["dormant_discount"]
    assert all(row["classification"] == "review_required" for row in dormant["candidates"])
    assert "used_helper" not in {row["name"] for row in dormant["candidates"]}
    assert "unsafe_dormant" not in {row["name"] for row in dormant["candidates"]}
    assert any("string/reflection" in row["reason"] for row in dormant["uncertain"])
    assert any("unsafe/FFI" in row["reason"] for row in dormant["uncertain"])

    state = json.loads((host / "reports/implicit-state/rust/findings.json").read_text())
    assert state["schema_version"] == "rust-implicit-state-v1"
    assert [(row["owner"], row["name"]) for row in state["candidates"]] == [("Job", "state")]
    assert state["candidates"][0]["literals"] == ["done", "queued", "running"]
    assert state["candidates"][0]["human_verdict"] == "required"
    assert {row["classification"] for row in state["classifications"]} == {
        "typed_state",
        "insufficient_operations",
    }

    sweep = json.loads((host / "reports/find-incomplete-sweep/rust/manifest.json").read_text())
    assert sweep["schema_version"] == 1 and sweep["language"] == "rust"
    assert sweep["read_only"] is True
    assert sweep["summary"] == {"gated_in": 1, "gated_out": 0, "deferred": 0}
    assert sweep["findings"][0]["callee"] == "ChargeOptions"
    assert sweep["findings"][0]["kwarg"] == "audit"
    assert sweep["findings"][0]["group_size"] == 4
    assert "AFTER the straggler" in sweep["findings"][0]["trajectory"]
    scout = _run(
        sys.executable,
        str(ROOT / ".claude/skills/find-incomplete-sweep/scripts/scout.py"),
        "--scan-dir",
        str(host / "reports/find-incomplete-sweep/rust"),
        cwd=host,
    )
    assert scout.returncode == 0, scout.stdout + scout.stderr
    packets = json.loads(
        (host / "reports/find-incomplete-sweep/rust/scout_packets.json").read_text()
    )
    assert packets["packet_count"] == 1 and packets["packets"][0]["id"] == "SW-01"
    (host / "reports/find-incomplete-sweep/rust/scout_verdicts.json").write_text(
        json.dumps(
            {
                "verdicts": [
                    {
                        "id": "SW-01",
                        "verdict": "forgotten",
                        "rationale": "The newer audit sweep missed the older defaulted literal.",
                        "completion": "Pass audit explicitly after separate approval.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    triage = _run(
        sys.executable,
        str(ROOT / ".claude/skills/find-incomplete-sweep/scripts/triage.py"),
        "--scan-dir",
        str(host / "reports/find-incomplete-sweep/rust"),
        cwd=host,
    )
    assert triage.returncode == 0, triage.stdout + triage.stderr
    assert (
        "human-verdict handoff"
        in (host / "reports/find-incomplete-sweep/rust/triaged.md").read_text()
    )

    duplicate = json.loads((host / "reports/semantic-duplication/rust/analysis.json").read_text())
    assert duplicate["schema_version"] == "rust-semantic-duplication-v1"
    assert len(duplicate["confirmed"]) == 1
    lead = duplicate["confirmed"][0]
    assert [row["name"] for row in lead["functions"]] == ["summarize_invoice", "build_statement"]
    assert lead["return_shape"] == {"type": "InvoiceSummary", "fields": ["subtotal", "tax"]}
    assert lead["human_verdict"] == "required"
    assert "not behavioral equivalence" in lead["boundary"]
    assert {row["reason"] for row in duplicate["rejected"]} >= {
        "direct_wrapper_relationship",
        "policy_or_return_shape_mismatch",
    }
    assert (host / "reports/semantic-duplication/rust/capability-matrix-rsd-01.md").is_file()

    assessment = _run(
        sys.executable,
        str(ROOT / ".claude/skills/rename-concept/scripts/assess.py"),
        "LegacyStatus",
        "CanonicalStatus",
        "--project-root",
        str(host),
        "--output",
        "reports/rename-concept/assessment.json",
        "--report",
        "reports/rename-concept/impact.md",
        cwd=host,
    )
    assert assessment.returncode == 0, assessment.stdout + assessment.stderr
    rename = json.loads((host / "reports/rename-concept/assessment.json").read_text())
    assert rename["verdict"] == "HALF-APPLIED / INCOMPLETE"
    rust = rename["rust_identifier_evidence"]
    assert rust["status"] == "resolved" and rust["authority_status"] == "resolved"
    assert rust["read_only"] is True
    assert len(rust["declarations"]["old"]) == len(rust["declarations"]["new"]) == 1
    assert any(row["classification"] == "old_concept_symbol" for row in rust["occurrences"])
    assert any(row["kind"] == "reflection_or_string" for row in rust["deferred_references"])
    assert rename["read_only"] is True
    assert _source_bytes(host) == before
    _native(host, tmp_path, "after")


def test_fact_pack_tool_lifecycle_and_stale_replacement_are_honest(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _source_bytes(host)

    complete = _facts(host, tmp_path / "complete")
    tampered = dict(complete)
    tampered["workspace"] = {"tampered": True}
    tampered_path = _write_facts(tampered, tmp_path / "tampered.json")
    with pytest.raises(ValueError, match="hash does not verify"):
        _module().load_or_collect(
            facts=tampered_path,
            project_root=host,
            target="semantic-core",
            queries=QUERIES,
            cargo=str(CARGO),
            rustc=str(RUSTC),
            rust_analyzer=str(RUST_ANALYZER),
            cargo_target_dir=None,
        )
    complete_path = _write_facts(complete, tmp_path / "complete.json")
    changed = host / "semantic-core/src/state.rs"
    original = changed.read_text(encoding="utf-8")
    changed.write_text(original + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="is stale"):
        _module().load_or_collect(
            facts=complete_path,
            project_root=host,
            target="semantic-core",
            queries=QUERIES,
            cargo=str(CARGO),
            rustc=str(RUSTC),
            rust_analyzer=str(RUST_ANALYZER),
            cargo_target_dir=None,
        )
    changed.write_text(original, encoding="utf-8")

    missing = _facts(host, tmp_path, cargo=str(tmp_path / "missing-cargo"))
    assert missing["status"] == "partial" and missing["failure_kind"] == "cargo_missing"
    assert missing["fact_pack_sha256"] and missing["source_snapshot"]
    report = host / "reports/find-dormant/missing"
    report.mkdir(parents=True)
    (report / "findings.json").write_text('{"stale": true}\n', encoding="utf-8")
    missing_path = _write_facts(missing, tmp_path / "missing.json")
    result = _run(
        sys.executable,
        str(SCRIPTS["dormant"]),
        "--project-root",
        str(host),
        "--target",
        "semantic-core",
        "--output-dir",
        "reports/find-dormant/missing",
        "--facts",
        str(missing_path),
        cwd=host,
    )
    assert result.returncode == 0
    replaced = json.loads((report / "findings.json").read_text())
    assert replaced["status"] == "partial" and "stale" not in replaced
    assert replaced["summary"]["certain_delete"] == 0
    duplicate_report = host / "reports/semantic-duplication/stale"
    duplicate_report.mkdir(parents=True)
    (duplicate_report / "capability-matrix-rsd-99.md").write_text(
        "stale matrix\n", encoding="utf-8"
    )
    duplicate_result = _run(
        sys.executable,
        str(SCRIPTS["duplicate"]),
        "--project-root",
        str(host),
        "--target",
        "semantic-core",
        "--output-dir",
        "reports/semantic-duplication/stale",
        "--facts",
        str(missing_path),
        cwd=host,
    )
    assert duplicate_result.returncode == 0
    assert not (duplicate_report / "capability-matrix-rsd-99.md").exists()
    assert json.loads((duplicate_report / "analysis.json").read_text())["status"] == "partial"

    no_lsp = _facts(host, tmp_path / "no-lsp", rust_analyzer=str(tmp_path / "missing-ra"))
    assert no_lsp["status"] == "partial"
    assert no_lsp["failure_kind"] == "rust_analyzer_missing_old_or_failed"

    old_cargo = tmp_path / "old-cargo"
    old_cargo.write_text("#!/bin/sh\necho 'cargo 1.84.0 (old)'\n", encoding="utf-8")
    old_cargo.chmod(0o755)
    old = _facts(host, tmp_path / "old", cargo=str(old_cargo))
    assert old["status"] == "partial" and old["failure_kind"] == "rust_toolchain_too_old"
    assert "unsupported" not in json.dumps(old).lower()

    failing_cargo = tmp_path / "failing-cargo"
    failing_cargo.write_text(
        "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'cargo 1.97.1 (fixture)'; exit 0; fi\necho 'metadata failed' >&2\nexit 9\n",
        encoding="utf-8",
    )
    failing_cargo.chmod(0o755)
    failed = _facts(host, tmp_path / "failed", cargo=str(failing_cargo))
    assert failed["status"] == "failed" and failed["failure_kind"] == "cargo_metadata_failed"

    incomplete = _host(tmp_path / "incomplete", history=False)
    incomplete.joinpath("Cargo.lock").unlink()
    incomplete_payload = _facts(incomplete, tmp_path / "incomplete-facts")
    assert incomplete_payload["status"] in {"failed", "partial"}
    assert incomplete_payload["status"] != "unsupported"

    broken = _host(tmp_path / "broken", history=False)
    source = broken / "semantic-core/src/lib.rs"
    source.write_text(source.read_text(encoding="utf-8") + "\npub fn broken(\n", encoding="utf-8")
    broken_before = _source_bytes(broken)
    compiler_failed = _facts(broken, tmp_path / "broken-facts")
    assert compiler_failed["status"] == "failed"
    assert compiler_failed["failure_kind"] == "cargo_check_failed"
    assert compiler_failed["compiler"]["diagnostics"]
    assert _source_bytes(broken) == broken_before
    assert _source_bytes(host) == before


def test_clean_rust_project_keeps_all_five_final_outcomes_clean(tmp_path: Path) -> None:
    host = _host(tmp_path, history=False)
    (host / "semantic-core/src/linked.rs").unlink()
    (host / "semantic-core/src/dormant.rs").write_text(
        "fn used_helper(value: i32) -> i32 { value + 1 }\n"
        "pub fn used_total(value: i32) -> i32 { used_helper(value) }\n",
        encoding="utf-8",
    )
    (host / "semantic-core/src/state.rs").write_text(
        "#[derive(Clone, Copy)]\npub enum TypedPhase { Ready, Complete }\n"
        "pub struct Job { pub state: TypedPhase }\n"
        "pub fn ready(job: &Job) -> bool { matches!(job.state, TypedPhase::Ready) }\n",
        encoding="utf-8",
    )
    straggler = host / "semantic-core/src/sweep/straggler.rs"
    straggler.write_text(
        "use super::ChargeOptions;\n\n"
        "pub fn options() -> ChargeOptions {\n"
        "    ChargeOptions { amount: 40, audit: true }\n"
        "}\n",
        encoding="utf-8",
    )
    (host / "semantic-core/src/duplication/mod.rs").write_text(
        "pub mod caller_a;\npub mod caller_b;\n"
        "pub struct InvoiceSummary { pub subtotal: i32, pub tax: i32 }\n"
        "pub struct StatementSummary { pub subtotal: i32, pub tax: i32 }\n"
        "pub fn summarize_invoice(value: i32) -> InvoiceSummary {\n"
        "    InvoiceSummary { subtotal: value, tax: value / 10 }\n}\n"
        "pub fn build_statement(value: i32) -> StatementSummary {\n"
        "    StatementSummary { subtotal: value, tax: value / 10 }\n}\n",
        encoding="utf-8",
    )
    (host / "semantic-core/src/rename.rs").write_text(
        "pub struct CanonicalStatus;\n"
        "pub fn canonical() -> CanonicalStatus { CanonicalStatus }\n",
        encoding="utf-8",
    )
    (host / "generated/Generated.rs").write_text("pub struct GeneratedStatus;\n", encoding="utf-8")
    _run(str(CARGO), "fmt", "--all", cwd=host)
    _native(host, tmp_path, "clean")
    payload = _facts(host, tmp_path / "clean-facts")
    assert payload["status"] == "complete"
    facts = _write_facts(payload, tmp_path / "clean.json")
    _consumer_runs(host, facts)
    dormant = json.loads((host / "reports/find-dormant/rust/findings.json").read_text())
    state = json.loads((host / "reports/implicit-state/rust/findings.json").read_text())
    sweep = json.loads((host / "reports/find-incomplete-sweep/rust/manifest.json").read_text())
    duplicate = json.loads((host / "reports/semantic-duplication/rust/analysis.json").read_text())
    assert dormant["candidates"] == []
    assert state["candidates"] == []
    assert sweep["findings"] == [] and sweep["gated_out"] == []
    assert duplicate["confirmed"] == []

    assessment = _run(
        sys.executable,
        str(ROOT / ".claude/skills/rename-concept/scripts/assess.py"),
        "LegacyStatus",
        "CanonicalStatus",
        "--project-root",
        str(host),
        "--output",
        "reports/rename-concept/assessment.json",
        "--report",
        "reports/rename-concept/impact.md",
        cwd=host,
    )
    assert assessment.returncode == 0, assessment.stdout + assessment.stderr
    rename = json.loads((host / "reports/rename-concept/assessment.json").read_text())
    assert rename["verdict"] in {"COMPLETE", "LIKELY COMPLETE"}
    assert rename["rust_identifier_evidence"]["declarations"]["old"] == []
    assert rename["rust_identifier_evidence"]["deferred_references"] == []


def test_copied_closures_share_only_the_bounded_fact_pack_and_deletion_is_visible(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    installed_map = host / ".agents/skills/map-subsystem"
    shutil.copytree(COMMON.parents[1], installed_map)
    assert (installed_map / "scripts/rust_semantic_facts.py").is_file()
    assert (installed_map / "scripts/map_rust.py").is_file()
    facts = host / "reports/rust-semantic-facts/batch.json"
    fact_command = [
        sys.executable,
        str(installed_map / "scripts/rust_semantic_facts.py"),
        "--project-root",
        str(host),
        "--target",
        "semantic-core",
        "--output",
        str(facts),
        "--cargo-target-dir",
        str(tmp_path / "copied-facts-target"),
    ]
    for query in QUERIES:
        fact_command.extend(("--query", query))
    fact_result = _run(*fact_command, cwd=host)
    assert fact_result.returncode == 0, fact_result.stdout + fact_result.stderr
    assert json.loads(facts.read_text())["status"] == "complete"
    installed_scripts: dict[str, Path] = {}
    skill_names = {
        "dormant": "find-dormant",
        "state": "find-implicit-state",
        "sweep": "find-incomplete-sweep",
        "duplicate": "find-semantic-duplication",
    }
    for key in ("dormant", "state", "sweep", "duplicate"):
        installed_skill = host / ".agents/skills" / skill_names[key]
        shutil.copytree(SCRIPTS[key].parents[1], installed_skill)
        scripts = installed_skill / "scripts"
        installed = scripts / SCRIPTS[key].name
        installed_scripts[key] = installed
    _consumer_runs(host, facts, installed_scripts)

    rename_skill = host / ".agents/skills/rename-concept"
    shutil.copytree(SCRIPTS["rename"].parents[1], rename_skill)
    rename_scripts = rename_skill / "scripts"
    rename_result = _run(
        sys.executable,
        str(rename_scripts / SCRIPTS["rename"].name),
        "--project-root",
        str(host),
        "--old-terms",
        '["LegacyStatus"]',
        "--new-terms",
        '["CanonicalStatus"]',
        "--sources",
        '["semantic-core/src/rename.rs"]',
        "--output",
        str(tmp_path / "rename.json"),
        cwd=host,
    )
    assert rename_result.returncode == 0, rename_result.stdout + rename_result.stderr
    assert json.loads((tmp_path / "rename.json").read_text())["status"] == "resolved"

    standalone = _run(
        sys.executable,
        str(installed_scripts["dormant"]),
        "--project-root",
        str(host),
        "--target",
        "semantic-core",
        "--output-dir",
        "reports/find-dormant/standalone",
        cwd=host,
    )
    assert standalone.returncode == 0, standalone.stdout + standalone.stderr
    assert (
        json.loads((host / "reports/find-dormant/standalone/findings.json").read_text())["summary"][
            "review_required"
        ]
        == 1
    )

    (installed_map / "scripts/rust_semantic_facts.py").unlink()
    deletion = _run(
        sys.executable,
        str(installed_scripts["dormant"]),
        "--project-root",
        str(host),
        "--target",
        "semantic-core",
        "--output-dir",
        "reports/find-dormant/deleted",
        "--facts",
        str(facts),
        cwd=host,
    )
    assert deletion.returncode != 0
    assert "fact pack is missing" in deletion.stderr

    helper_lines = len(COMMON.read_text(encoding="utf-8").splitlines())
    consumer_lines = sum(
        len(path.read_text(encoding="utf-8").splitlines()) for path in SCRIPTS.values()
    )
    duplicated = consumer_lines + helper_lines * len(SCRIPTS)
    shared = consumer_lines + helper_lines
    assert (duplicated - shared) / duplicated >= 0.25
    for path in SCRIPTS.values():
        text = path.read_text(encoding="utf-8")
        assert "load_or_collect" in text or path == SCRIPTS["rename"]
        assert "textDocument/definition" not in text
        assert "cargo metadata" not in text
