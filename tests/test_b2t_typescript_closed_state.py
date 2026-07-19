"""B2T TypeScript closed-state outcome proof.

The test deliberately exercises the installed outcome boundary: a host-owned,
pinned TypeScript compiler, detector JSONL, extractor proposal, reviewed
before/after mutation, and generated guard artifact.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "b2t_typescript_closed_state"
DETECT = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "find-implicit-state"
    / "scripts"
    / "detect_typescript_state.mjs"
)
COLLECT = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "extract-enum"
    / "scripts"
    / "collect_typescript_state.mjs"
)
GENERATE_GUARD = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "prevent-regression"
    / "scripts"
    / "generate_typescript_state_guard.mjs"
)
VERIFY_GUARD = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "prevent-regression"
    / "scripts"
    / "verify_typescript_state_guard.mjs"
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, state: str) -> Path:
    host = tmp_path / f"host-{state}"
    shutil.copytree(FIXTURE / state, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    return host


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _typecheck_and_test(host: Path) -> None:
    typecheck = _run("npm", "run", "typecheck", cwd=host)
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    native = _run("npm", "test", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr


def test_b2t_typescript_closed_state_outcome_and_installed_guard(tmp_path: Path) -> None:
    installed_root = tmp_path / "installed"
    shutil.copytree(DETECT.parents[1], installed_root / "find-implicit-state")
    shutil.copytree(COLLECT.parents[1], installed_root / "extract-enum")
    shutil.copytree(GENERATE_GUARD.parents[1], installed_root / "prevent-regression")
    before = _copy_host(tmp_path, "before")
    _typecheck_and_test(before)

    report_dir = before / "reports" / "implicit-state" / "scan-b2t"
    report_dir.mkdir(parents=True)
    findings = report_dir / "findings.jsonl"
    detect = _run(
        "node", str(installed_root / "find-implicit-state" / "scripts" / DETECT.name),
        "--target", str(before), "--project-root", str(before),
        "--tsconfig", str(before / "tsconfig.json"), "--output", str(findings), cwd=before,
    )
    assert detect.returncode == 0, detect.stdout + detect.stderr
    records = _read_jsonl(findings)
    classifications = {record["classification"] for record in records}
    assert {
        "first_party_state_operation",
        "typed_state_authority",
        "vendor_wire_boundary",
        "unrelated_status_text",
        "excluded_test_or_fixture",
        "open_ended_string",
    } <= classifications
    authority_kinds = {
        record.get("authority_kind")
        for record in records
        if record["classification"] == "typed_state_authority"
    }
    assert {"literal_union", "string_enum"} <= authority_kinds
    first_party = [r for r in records if r["classification"] == "first_party_state_operation"]
    assert {(r["operation"], r["literal"]) for r in first_party} == {
        ("assignment", "queued"),
        ("comparison", "running"),
        ("comparison", "done"),
    }
    assert all(r["carrier_type"] == "JobState" for r in first_party)
    missing_tsconfig = _run(
        "node", str(installed_root / "find-implicit-state" / "scripts" / DETECT.name),
        "--target", str(before), "--project-root", str(before),
        "--tsconfig", str(before / "missing-tsconfig.json"), "--output", str(tmp_path / "unused.jsonl"),
        cwd=before,
    )
    assert missing_tsconfig.returncode == 2
    assert "project-local TypeScript requires tsconfig" in missing_tsconfig.stderr

    enum_dir = before / "reports" / "extract-enum" / "job-state"
    targets = enum_dir / "targets.json"
    proposal = enum_dir / "proposal.md"
    collect = _run(
        "node", str(installed_root / "extract-enum" / "scripts" / COLLECT.name),
        "--findings", str(findings), "--project-root", str(before),
        "--output", str(targets), "--proposal", str(proposal), cwd=before,
    )
    assert collect.returncode == 0, collect.stdout + collect.stderr
    target_data = json.loads(targets.read_text(encoding="utf-8"))
    assert target_data["runtime_value_name"] == "JobState"
    assert target_data["callers_by_file"] == {"src/jobs.ts": 3}
    assert target_data["vendor_boundaries"] == ["src/vendor.ts"]
    proposal_text = proposal.read_text(encoding="utf-8")
    assert "export const JobState = {" in proposal_text
    assert "export type JobState =" in proposal_text
    assert "src/vendor.ts" in proposal_text

    after = _copy_host(tmp_path, "after")
    _typecheck_and_test(after)

    stage = after / "reports" / "prevent-regression" / "b2t-state"
    generate = _run(
        "node", str(installed_root / "prevent-regression" / "scripts" / "generate_typescript_state_guard.mjs"),
        "--id", "b2t-state", "--project-root", str(after),
        "--tsconfig", str(after / "tsconfig.json"), "--output-root", str(stage), cwd=after,
    )
    assert generate.returncode == 0, generate.stdout + generate.stderr
    guard = stage / "scripts" / "lint" / "no_stringly_state.mjs"
    bad_ts = stage / "tests" / "lint" / "no_stringly_state_bad.ts"
    bad_tsx = stage / "tests" / "lint" / "no_stringly_state_bad.tsx"
    good_ts = stage / "tests" / "lint" / "no_stringly_state_good.ts"
    good_tsx = stage / "tests" / "lint" / "no_stringly_state_good.tsx"
    assert guard.is_file()
    assert (stage / "host-wiring.diff").is_file()

    bad = _run("node", str(guard), str(bad_ts), str(bad_tsx), cwd=after)
    good = _run("node", str(guard), str(good_ts), str(good_tsx), cwd=after)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert len(bad.stdout.splitlines()) == 4
    assert good.returncode == 0, good.stdout + good.stderr
    assert good.stdout == ""
    verify = _run(
        "node", str(installed_root / "prevent-regression" / "scripts" / VERIFY_GUARD.name), "--rule", str(guard),
        "--bad", str(bad_ts), "--bad-tsx", str(bad_tsx),
        "--good", str(good_ts), "--good-tsx", str(good_tsx), cwd=after,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "PASS: BAD_RC=1, GOOD_RC=0" in verify.stdout
    bad_cli = _run("node", str(guard), cwd=after)
    assert bad_cli.returncode == 2
    assert "usage: no_stringly_state.mjs" in bad_cli.stderr

    missing_prerequisite = _run(
        "node", str(guard), "--project-root", str(tmp_path / "missing"), str(good_ts), cwd=after,
    )
    assert missing_prerequisite.returncode == 2
    assert "project-local TypeScript" in missing_prerequisite.stderr
