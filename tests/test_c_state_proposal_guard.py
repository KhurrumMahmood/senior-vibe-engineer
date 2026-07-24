"""Accepted-evidence C enum proposal and exact-field C17 guard proof."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
SKILLS = ROOT / ".claude/skills"
BASE_FIXTURE = ROOT / "tests/fixtures/c-semantic-family/host"
MIGRATED_OVERLAY = ROOT / "tests/fixtures/c-state-proposal-guard/migrated"
PROVIDER = SKILLS / "_c-semantic/c_semantic_facts.py"
DETECT = SKILLS / "find-implicit-state/scripts/detect_c_state.py"
COLLECT = SKILLS / "extract-enum/scripts/collect_c_state.py"
GENERATE = SKILLS / "prevent-regression/scripts/generate_c_state_guard.py"
VERIFY = SKILLS / "prevent-regression/scripts/verify_c_state_guard.py"
CLANG = shutil.which("clang")
MAKE = shutil.which("make")
SMOKE = "semantic:running:us:112:1:legacy_status\n"
GATES = {"abi": "approved", "external": "approved", "storage": "approved", "wire": "approved"}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or CLANG is None or MAKE is None,
    reason="product Python, Clang 21+, and Make are required",
)


def _run(*args: str | Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_hashes(host: Path) -> dict[str, str]:
    excluded = {".git", ".native-build", "reports", "reviews"}
    return {
        path.relative_to(host).as_posix(): _sha(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not (excluded & set(path.relative_to(host).parts))
    }


def _host(tmp_path: Path, name: str, *, migrated: bool = False) -> Path:
    host = tmp_path / name
    shutil.copytree(BASE_FIXTURE, host)
    if migrated:
        shutil.copytree(MIGRATED_OVERLAY, host, dirs_exist_ok=True)
    result = _run(MAKE or "make", "clean", "compile-db", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    return host


def _native(host: Path) -> None:
    result = _run(MAKE or "make", "test", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(host / ".native-build/c-semantic-smoke", cwd=host)
    assert smoke.returncode == 0
    assert smoke.stdout == SMOKE


def _accepted_evidence(host: Path) -> tuple[Path, Path]:
    facts = host / "reports/c-semantic/facts.json"
    findings = host / "reports/implicit-state/c/findings.json"
    produced = _run(
        PYTHON,
        PROVIDER,
        "--project-root",
        host,
        "--output",
        "reports/c-semantic/facts.json",
        "--clang",
        CLANG or "clang",
        cwd=host,
    )
    assert produced.returncode == 0, produced.stdout + produced.stderr
    detected = _run(
        PYTHON,
        DETECT,
        "--project-root",
        host,
        "--target",
        "src",
        "--facts",
        "reports/c-semantic/facts.json",
        "--output",
        "reports/implicit-state/c/findings.json",
        "--clang",
        CLANG or "clang",
        cwd=host,
    )
    assert detected.returncode == 0, detected.stdout + detected.stderr
    return facts, findings


def _collect(host: Path, script: Path = COLLECT) -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--findings",
        "reports/implicit-state/c/findings.json",
        "--facts",
        "reports/c-semantic/facts.json",
        "--candidate",
        "job.state",
        "--output-dir",
        "reports/extract-enum/job-state",
        cwd=host,
    )


def _proposal(host: Path, script: Path = COLLECT) -> Path:
    result = _collect(host, script)
    assert result.returncode == 0, result.stdout + result.stderr
    return host / "reports/extract-enum/job-state/targets.json"


def _review(host: Path, targets: Path, *, status: str = "accepted") -> Path:
    authority = _json(targets)["authority"]
    migrated_sources = [
        {
            "path": relative,
            "sha256": _sha(host / relative),
        }
        for relative in (
            "include/csemantic/semantic.h",
            "src/semantic.c",
            "src/main.c",
        )
    ]
    payload = {
        "schema_version": "c-enum-proposal-review-v1",
        "language": "c",
        "status": status,
        "decision": "approve_exact_field_guard",
        "targets_sha256": _sha(targets),
        "authority": authority,
        "approvals": GATES,
        "migration": {
            "enum_type": "job_state",
            "header_include": "csemantic/semantic.h",
            "migrated_sources": migrated_sources,
            "guard_destination": "tests/guards/job_state_type_guard.c",
            "native": {
                "compile_database_target": "compile-db",
                "make_target": "test",
                "smoke_path": ".native-build/c-semantic-smoke",
                "smoke_stdout": SMOKE,
                "guard_cflags": [
                    "-std=c17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-pedantic",
                    "-fno-common",
                    "-Iinclude",
                ],
            },
            "seeded_regression": {
                "field_replacement": {
                    "path": "include/csemantic/semantic.h",
                    "before": "    job_state state;",
                    "after": "    const char *state;",
                },
                "caller_replacements": [
                    {
                        "path": "src/semantic.c",
                        "before": "    value->state = JOB_STATE_QUEUED;",
                        "after": '    value->state = "queued";',
                    },
                    {
                        "path": "src/semantic.c",
                        "before": "    value->state = JOB_STATE_RUNNING;",
                        "after": '    value->state = "running";',
                    },
                    {
                        "path": "src/semantic.c",
                        "before": "    value->state = JOB_STATE_DONE;",
                        "after": '    value->state = "done";',
                    },
                    {
                        "path": "src/main.c",
                        "before": "        job_state_wire(value.state),",
                        "after": "        value.state,",
                    },
                ],
            },
        },
    }
    path = host / "reviews/c-state/job-state.json"
    _write_json(path, payload)
    return path


def _generate(
    host: Path,
    review: Path,
    script: Path = GENERATE,
) -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--targets",
        "reports/extract-enum/job-state/targets.json",
        "--accepted-review",
        review,
        "--output-dir",
        "reports/prevent-regression/job-state",
        cwd=host,
    )


def test_c_proposal_and_guard_reach_exact_native_final_outcomes_from_copied_skills(
    tmp_path: Path,
) -> None:
    before = _host(tmp_path, "before")
    _accepted_evidence(before)
    before_hashes = _source_hashes(before)
    copied_extract = tmp_path / "installed/extract-enum"
    shutil.copytree(COLLECT.parents[1], copied_extract)
    copied_collector = copied_extract / "scripts/collect_c_state.py"
    collector_source = copied_collector.read_text(encoding="utf-8")
    assert "detect_c_state" not in collector_source
    assert "c_semantic_facts.py" not in collector_source
    targets = _proposal(before, copied_collector)
    data = _json(targets)
    proposal = targets.with_name("proposal.md").read_text(encoding="utf-8")

    assert data["status"] == "review_required"
    assert data["outcome"] == "proposal_ready"
    assert data["read_only"] is True and data["source_mutations"] == 0
    assert data["authority"] == {
        "declaration_file": "include/csemantic/semantic.h",
        "declaration_line": 5,
        "field": "state",
        "owner": "job",
        "type": "const char *",
    }
    assert [row["wire_value"] for row in data["proposed_enum"]["enumerators"]] == [
        "done",
        "queued",
        "running",
    ]
    assert [row["function"] for row in data["callers"]] == [
        "job_queue",
        "job_start",
        "job_finish",
    ]
    assert set(data["current_source_hashes"]) == {
        "include/csemantic/semantic.h",
        "src/semantic.c",
    }
    assert data["approval_gates"] == {
        "abi": "human_approval_required",
        "external": "human_approval_required",
        "storage": "human_approval_required",
        "wire": "human_approval_required",
    }
    assert all(word in proposal for word in ("ABI", "wire", "storage", "external"))
    assert "edits no C source" in proposal
    assert _source_hashes(before) == before_hashes
    assert not any(path.suffix in {".c", ".h"} for path in targets.parent.rglob("*"))

    after = _host(tmp_path, "after", migrated=True)
    _native(after)
    shutil.copytree(targets.parent, after / "reports/extract-enum/job-state")
    after_targets = after / "reports/extract-enum/job-state/targets.json"
    review = _review(after, after_targets)
    after_hashes = _source_hashes(after)
    copied_guard = tmp_path / "installed/prevent-regression"
    shutil.copytree(GENERATE.parents[1], copied_guard)
    generated = _generate(after, review, copied_guard / "scripts/generate_c_state_guard.py")
    assert generated.returncode == 0, generated.stdout + generated.stderr
    stage = after / "reports/prevent-regression/job-state"
    guard = stage / "guard/exact_field_type_guard.c"
    guard_text = guard.read_text(encoding="utf-8")
    assert "_Static_assert" in guard_text and "_Generic" in guard_text
    assert "((job *)0)->state" in guard_text and "job_state: 1" in guard_text
    assert not (after / "tests/guards/job_state_type_guard.c").exists()

    verified = _run(
        PYTHON,
        "-I",
        "-S",
        copied_guard / "scripts/verify_c_state_guard.py",
        "--project-root",
        after,
        "--stage",
        "reports/prevent-regression/job-state",
        "--clang",
        CLANG or "clang",
        "--make",
        MAKE or "make",
        cwd=after,
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    report = _json(stage / "verification.json")
    assert report["status"] == "complete" and report["outcome"] == "guard_proved"
    assert report["clean_native"]["make_test"]["returncode"] == 0
    assert report["clean_native"]["smoke"]["stdout"] == SMOKE
    assert report["clean_guard"]["returncode"] == 0
    assert report["seeded_regression"]["without_guard"]["returncode"] == 0
    assert report["seeded_regression"]["with_guard"]["returncode"] != 0
    assert report["seeded_regression"]["caught_by_guard"] is True
    assert "job.state must remain job_state" in report["seeded_regression"]["with_guard"]["stderr"]
    assert report["installed"] is False and report["source_preserved"] is True
    assert _source_hashes(after) == after_hashes
    _native(after)


def test_c_proposal_rejects_partial_tampered_and_stale_evidence_without_stale_success(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path, "proposal-lifecycle")
    facts, findings = _accepted_evidence(host)
    assert _collect(host).returncode == 0
    output = host / "reports/extract-enum/job-state"
    assert (output / "proposal.md").is_file()

    finding_payload = _json(findings)
    finding_payload["status"] = "partial"
    _write_json(findings, finding_payload)
    partial = _collect(host)
    assert partial.returncode == 2
    assert not (output / "proposal.md").exists()
    assert _json(output / "refusal.json")["failure_kind"] == "evidence_incomplete"

    _accepted_evidence(host)
    facts_payload = _json(facts)
    facts_payload["limits"].append("tampered")
    _write_json(facts, facts_payload)
    tampered = _collect(host)
    assert tampered.returncode == 2
    assert _json(output / "refusal.json")["failure_kind"] == "evidence_tampered"

    _accepted_evidence(host)
    database = host / "compile_commands.json"
    database.write_text(database.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    stale_database = _collect(host)
    assert stale_database.returncode == 2
    assert _json(output / "refusal.json")["failure_kind"] == "evidence_stale"

    regenerated = _run(MAKE or "make", "compile-db", f"CC={CLANG}", cwd=host)
    assert regenerated.returncode == 0, regenerated.stdout + regenerated.stderr
    _accepted_evidence(host)
    header = host / "include/csemantic/semantic.h"
    original = header.read_text(encoding="utf-8")
    header.write_text(original + "\n", encoding="utf-8")
    stale = _collect(host)
    assert stale.returncode == 2
    assert _json(output / "refusal.json")["failure_kind"] == "evidence_stale"
    header.write_text(original, encoding="utf-8")
    regenerated = _run(MAKE or "make", "compile-db", f"CC={CLANG}", cwd=host)
    assert regenerated.returncode == 0, regenerated.stdout + regenerated.stderr
    _accepted_evidence(host)
    recovered = _collect(host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert (output / "proposal.md").is_file()
    assert not (output / "refusal.json").exists()


def test_c_guard_requires_fresh_explicit_approval_and_rejects_tampered_stage(
    tmp_path: Path,
) -> None:
    before = _host(tmp_path, "guard-before")
    _accepted_evidence(before)
    targets = _proposal(before)
    after = _host(tmp_path, "guard-after", migrated=True)
    shutil.copytree(targets.parent, after / "reports/extract-enum/job-state")
    after_targets = after / "reports/extract-enum/job-state/targets.json"
    review = _review(after, after_targets)
    stage = after / "reports/prevent-regression/job-state"
    assert _generate(after, review).returncode == 0
    assert (stage / "guard/exact_field_type_guard.c").is_file()

    payload = _json(review)
    payload["approvals"]["abi"] = "required"
    _write_json(review, payload)
    unapproved = _generate(after, review)
    assert unapproved.returncode == 2
    assert not (stage / "guard/exact_field_type_guard.c").exists()
    assert _json(stage / "refusal.json")["failure_kind"] == "approval_required"

    review = _review(after, after_targets)
    source = after / "src/main.c"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\n", encoding="utf-8")
    stale = _generate(after, review)
    assert stale.returncode == 2
    assert _json(stage / "refusal.json")["failure_kind"] == "migration_stale"
    source.write_text(original, encoding="utf-8")
    review = _review(after, after_targets)
    assert _generate(after, review).returncode == 0

    guard = stage / "guard/exact_field_type_guard.c"
    guard.write_text(guard.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    before_hashes = _source_hashes(after)
    invalid = _run(
        PYTHON,
        "-I",
        "-S",
        VERIFY,
        "--project-root",
        after,
        "--stage",
        "reports/prevent-regression/job-state",
        "--clang",
        CLANG or "clang",
        "--make",
        MAKE or "make",
        cwd=after,
    )
    assert invalid.returncode == 2
    assert _json(stage / "verification.json")["failure_kind"] == "stage_tampered"
    assert _source_hashes(after) == before_hashes
