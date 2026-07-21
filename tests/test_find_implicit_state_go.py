"""Go implicit-state detector outcome and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "find-implicit-state-go"
SKILL = ROOT / ".claude" / "skills" / "find-implicit-state"
EXTRACT = ROOT / ".claude" / "skills" / "extract-enum"
GUARD = ROOT / ".claude" / "skills" / "prevent-regression"
CATALOG = ROOT / ".claude" / "skills" / "which-skill" / "catalog.json"
MATRIX = ROOT / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
PYTHON = Path(sys.executable)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _hash_sources(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.go"))
        if "reports" not in path.relative_to(root).parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_go_implicit_state_reports_resolved_review_candidates(tmp_path: Path) -> None:
    host = tmp_path / "host"
    installed = tmp_path / "installed" / "find-implicit-state"
    installed_extract = tmp_path / "installed" / "extract-enum"
    installed_guard = tmp_path / "installed" / "prevent-regression"
    shutil.copytree(FIXTURE, host)
    shutil.copytree(SKILL, installed)
    shutil.copytree(EXTRACT, installed_extract)
    shutil.copytree(GUARD, installed_guard)
    before = _hash_sources(host)
    native = _run("go", "test", "./...", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr

    output = host / "reports" / "implicit-state" / "go.jsonl"
    scan = _run(
        str(PYTHON), str(installed / "scripts" / "detect_go_state.py"),
        "--target", str(host), "--project-root", str(host), "--output", str(output),
        cwd=host,
    )
    assert scan.returncode == 0, scan.stdout + scan.stderr
    records = _records(output)
    operations = [record for record in records if record["record_kind"] == "operation"]
    candidates = [record for record in operations if record["classification"] == "first_party_state_operation"]
    assert len(candidates) == 4
    assert {record["literal"] for record in candidates} == {"queued", "running", "done"}
    assert {record["operation"] for record in candidates} == {"comparison", "assignment"}
    assert all(record["field"] == "State" for record in candidates)
    assert all(record["carrier_type"] == "Job" for record in candidates)
    assert all(record["field_type"] == "string" for record in candidates)
    assert all(record["evidence_strength"] == "review_candidate" for record in candidates)

    typed = [record for record in operations if record["classification"] == "typed_state_authority"]
    assert len(typed) == 1
    assert typed[0]["field_type"] == "DeliveryPhase"
    vendor = [record for record in operations if record["classification"] == "possible_vendor_boundary"]
    assert len(vendor) == 1
    assert vendor[0]["carrier_type"] == "VendorJobPayload"
    assert vendor[0]["evidence_strength"] == "naming_convention_candidate"
    insufficient = [record for record in operations if record["classification"] == "insufficient_closed_state_evidence"]
    assert len(insufficient) == 1
    assert insufficient[0]["carrier_type"] == "OneShot"
    unrelated = [record for record in operations if record["classification"] == "unrelated_string_field"]
    assert len(unrelated) == 1
    assert unrelated[0]["field"] == "Label"

    inventory = [record for record in records if record["record_kind"] == "source_inventory"]
    assert {record["file"] for record in inventory} == {"generated.go", "state.go", "state_test.go"}
    assert next(record for record in inventory if record["file"] == "state.go")["role"] == "first_party"
    assert next(record for record in inventory if record["file"] == "state_test.go")["role"] == "excluded_test"
    assert next(record for record in inventory if record["file"] == "generated.go")["role"] == "excluded_generated"
    assert not any(record["file"] == "generated.go" for record in operations)
    status = next(record for record in records if record["record_kind"] == "analysis_status")
    assert status["status"] == "complete"
    assert status["unavailable_files"] == []

    enum_dir = host / "reports" / "extract-enum" / "job-state"
    targets = enum_dir / "targets.json"
    proposal = enum_dir / "proposal.md"
    collect = _run(
        str(PYTHON), str(installed_extract / "scripts" / "collect_go_state.py"),
        "--findings", str(output), "--project-root", str(host),
        "--output", str(targets), "--proposal", str(proposal), cwd=host,
    )
    assert collect.returncode == 0, collect.stdout + collect.stderr
    target_data = json.loads(targets.read_text(encoding="utf-8"))
    assert target_data["status"] == "review_required"
    assert target_data["carrier_type"] == "Job"
    assert target_data["field"] == "State"
    assert target_data["proposed_type"] == "JobState"
    assert [item["value"] for item in target_data["literals"]] == ["done", "queued", "running"]
    assert target_data["vendor_boundary_candidates"] == ["state.go"]
    proposal_text = proposal.read_text(encoding="utf-8")
    assert "type JobState string" in proposal_text
    assert 'JobStateQueued JobState = "queued"' in proposal_text
    assert "This is a review candidate, not proof that the domain is closed" in proposal_text

    guard_root = host / "reports" / "prevent-regression" / "job-state"
    generate = _run(
        str(PYTHON), str(installed_guard / "scripts" / "generate_go_state_guard.py"),
        "--targets", str(targets), "--project-root", str(host),
        "--output-root", str(guard_root), cwd=host,
    )
    assert generate.returncode == 0, generate.stdout + generate.stderr
    rule = guard_root / "scripts" / "lint" / "no_stringly_state.py"
    bad = guard_root / "tests" / "lint" / "no_stringly_state_bad.go"
    good = guard_root / "tests" / "lint" / "no_stringly_state_good.go"
    assert rule.is_file()
    assert (guard_root / "scripts" / "lint" / "detect_go_state.go").is_file()
    assert (guard_root / "host-wiring.diff").is_file()
    historical = _run(str(PYTHON), str(rule), "--project-root", str(host), str(host / "state.go"), cwd=host)
    assert historical.returncode == 1, historical.stdout + historical.stderr
    assert len(historical.stdout.splitlines()) == 4
    verify = _run(
        str(PYTHON), str(installed_guard / "scripts" / "verify_go_state_guard.py"),
        "--rule", str(rule), "--project-root", str(host),
        "--bad", str(bad), "--good", str(good), cwd=host,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "PASS: BAD_RC=1, GOOD_RC=0" in verify.stdout
    assert before == _hash_sources(host)


def test_go_state_guard_declares_its_companion_closure() -> None:
    catalog = {row["name"]: row for row in json.loads(CATALOG.read_text(encoding="utf-8"))["skills"]}
    assert catalog["prevent-regression"]["install_with"] == ["find-implicit-state"]
    matrix = {row["skill"]: row for row in json.loads(MATRIX.read_text(encoding="utf-8"))["skills"]}
    row = matrix["prevent-regression"]
    assert row["on_demand_closure"]["closure_skills"] == [
        "prevent-regression", "find-implicit-state",
    ]
    assert "--skill prevent-regression --skill find-implicit-state" in row["optional_install"]["command"]


def test_go_implicit_state_refuses_malformed_source(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    (host / "broken.go").write_text("package implicitstate\nfunc broken( {\n", encoding="utf-8")
    output = host / "reports" / "implicit-state" / "go.jsonl"
    scan = _run(
        str(PYTHON), str(SKILL / "scripts" / "detect_go_state.py"),
        "--target", str(host), "--project-root", str(host), "--output", str(output),
        cwd=host,
    )
    assert scan.returncode == 2
    assert "syntax-error" in scan.stderr or "type facts unavailable" in scan.stderr
    assert not output.exists()


def test_go_implicit_state_reports_missing_and_old_toolchains(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    output = host / "reports" / "implicit-state" / "go.jsonl"
    missing = _run(
        str(PYTHON), str(SKILL / "scripts" / "detect_go_state.py"),
        "--target", str(host), "--project-root", str(host), "--output", str(output),
        "--go-executable", str(tmp_path / "missing-go"), cwd=host,
    )
    assert missing.returncode == 2
    assert "cannot run" in missing.stderr or "No such file" in missing.stderr

    old = tmp_path / "old-go"
    old.write_text("#!/bin/sh\necho 'go version go1.21.9 fixture'\n", encoding="utf-8")
    old.chmod(0o755)
    unsupported = _run(
        str(PYTHON), str(SKILL / "scripts" / "detect_go_state.py"),
        "--target", str(host), "--project-root", str(host), "--output", str(output),
        "--go-executable", str(old), cwd=host,
    )
    assert unsupported.returncode == 2
    assert "requires Go >= 1.22" in unsupported.stderr
    assert not output.exists()


def test_go_implicit_state_preserves_inactive_build_files_as_partial(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    (host / "inactive.go").write_text(
        "//go:build never\n\npackage implicitstate\n\n"
        "type InactiveJob struct { State string }\n"
        "func inactive(value *InactiveJob) bool {\n"
        ' value.State = "queued"\n return value.State == "running" || value.State == "done"\n}\n',
        encoding="utf-8",
    )
    output = host / "reports" / "implicit-state" / "go.jsonl"
    scan = _run(
        str(PYTHON), str(SKILL / "scripts" / "detect_go_state.py"),
        "--target", str(host), "--project-root", str(host), "--output", str(output),
        cwd=host,
    )
    assert scan.returncode == 0, scan.stdout + scan.stderr
    records = _records(output)
    inventory = [record for record in records if record["record_kind"] == "source_inventory"]
    assert next(record for record in inventory if record["file"] == "inactive.go")["role"] == "inactive_build"
    status = next(record for record in records if record["record_kind"] == "analysis_status")
    assert status == {
        "record_kind": "analysis_status",
        "status": "partial",
        "unavailable_files": ["inactive.go"],
    }
    targets = host / "reports" / "extract-enum" / "partial" / "targets.json"
    proposal = host / "reports" / "extract-enum" / "partial" / "proposal.md"
    collect = _run(
        str(PYTHON), str(EXTRACT / "scripts" / "collect_go_state.py"),
        "--findings", str(output), "--project-root", str(host),
        "--output", str(targets), "--proposal", str(proposal), cwd=host,
    )
    assert collect.returncode == 2
    assert "partial" in collect.stderr
    assert not targets.exists()
    assert not proposal.exists()
