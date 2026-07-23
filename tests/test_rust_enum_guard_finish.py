"""Review-bound Rust enum proposal and exact native regression-guard proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/rust-guard-finish"
EXTRACT = ROOT / ".claude/skills/extract-enum/scripts/collect_rust_state.py"
GENERATE = ROOT / ".claude/skills/prevent-regression/scripts/generate_rust_state_guard.py"
VERIFY = ROOT / ".claude/skills/prevent-regression/scripts/verify_rust_state_guard.py"
CARGO = shutil.which("cargo")
RUSTC = shutil.which("rustc")
CLIPPY = shutil.which("cargo-clippy")
RUSTFMT = shutil.which("rustfmt")
pytestmark = pytest.mark.skipif(
    any(tool is None for tool in (CARGO, RUSTC, CLIPPY, RUSTFMT)),
    reason="Cargo, rustc, Clippy, and rustfmt are required",
)

NONCLAIMS = [
    "macro expansions",
    "build-script or include! output",
    "unselected cfg or target variants",
    "trait dispatch or generic owners",
    "unsafe or FFI behavior",
    "serialization or wire compatibility",
    "public API compatibility",
]


def _run(*args: str, cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _host(tmp_path: Path, shape: str) -> Path:
    host = tmp_path / shape
    shutil.copytree(FIXTURE / shape, host)
    return host


def _source_manifest(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not any(part in {"reports", "target"} for part in path.relative_to(host).parts)
    }


def _line(path: Path, needle: str) -> int:
    return next(
        number
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if needle in text
    )


def _findings(host: Path, *, status: str = "complete", candidates: bool = True) -> Path:
    state = host / "state-core/src/state.rs"
    hashes = _source_manifest(host)
    candidate = {
        "owner": "Job",
        "name": "state",
        "type": "String",
        "generic_owner": False,
        "owner_line": _line(state, "pub struct Job"),
        "file": "state-core/src/state.rs",
        "line": _line(state, "pub state: String"),
        "classification": "extract_enum_candidate",
        "human_verdict": "required",
        "literals": ["done", "queued", "running"],
        "operations": [
            {
                "file": "state-core/src/state.rs",
                "line": _line(state, 'state: "queued"'),
                "syntax": 'state: "queued".to_owned(),',
                "literals": ["queued"],
            },
            {
                "file": "state-core/src/state.rs",
                "line": _line(state, 'job.state = "running"'),
                "syntax": 'job.state = "running".to_owned();',
                "literals": ["running"],
            },
            {
                "file": "state-core/src/state.rs",
                "line": _line(state, 'job.state == "done"'),
                "syntax": 'job.state == "done"',
                "literals": ["done"],
            },
        ],
        "boundary": "candidate only; the domain is not proven closed",
    }
    payload = {
        "schema_version": "rust-implicit-state-v1",
        "language": "rust",
        "status": status,
        "analyzer": "cargo-compiler+rust-analyzer-field-definitions",
        "read_only": True,
        "target": "state-core",
        "fact_pack_sha256": "a" * 64,
        "source_hashes": [
            {
                "path": path,
                "sha256": digest,
                "role": "production-module" if path.endswith(".rs") else "manifest",
            }
            for path, digest in hashes.items()
        ],
        "candidates": [candidate] if candidates else [],
        "classifications": [] if candidates else [{"classification": "typed_state"}],
        "deferred": [],
        "summary": {"extract_enum_candidate": int(candidates)},
        "limits": NONCLAIMS,
    }
    path = host / "reports/implicit-state/rust/findings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _collect(
    host: Path,
    script: Path = EXTRACT,
    *,
    label: str = "job-state",
    candidate: str | None = "Job.state",
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-I",
        "-S",
        str(script),
        "--findings",
        "reports/implicit-state/rust/findings.json",
        "--project-root",
        str(host),
        "--output",
        f"reports/extract-enum/{label}/targets.json",
        "--proposal",
        f"reports/extract-enum/{label}/proposal.md",
    ]
    if candidate is not None:
        command.extend(("--candidate", candidate))
    return _run(*command, cwd=host)


def _accepted_review(host: Path, targets: Path) -> Path:
    payload = json.loads(targets.read_text(encoding="utf-8"))
    review = {
        "schema_version": "rust-enum-review-v1",
        "status": "accepted",
        "targets_sha256": hashlib.sha256(targets.read_bytes()).hexdigest(),
        "authority": payload["authority"],
        "enum": {
            "type_name": payload["proposed_enum"]["type_name"],
            "crate_import": "state_core",
            "module_path": "state",
            "variants": payload["proposed_enum"]["variants"],
        },
        "guard": {
            "package": "state-core",
            "test_destination": "state-core/tests/job_state_type_guard.rs",
        },
        "accepted_nonclaims": NONCLAIMS,
    }
    path = targets.with_name("accepted-review.json")
    path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_rust_proposal_is_read_only_exact_and_runs_from_copied_skill(tmp_path: Path) -> None:
    host = _host(tmp_path, "before")
    _findings(host)
    before = _source_manifest(host)
    installed = tmp_path / "installed/extract-enum"
    shutil.copytree(EXTRACT.parents[1], installed)

    result = _collect(host, installed / "scripts/collect_rust_state.py")

    assert result.returncode == 0, result.stdout + result.stderr
    targets_path = host / "reports/extract-enum/job-state/targets.json"
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    proposal = (targets_path.parent / "proposal.md").read_text(encoding="utf-8")
    assert targets["status"] == "review_required"
    assert targets["outcome"] == "proposal_ready"
    assert targets["read_only"] is True
    assert targets["authority"]["owner"] == "Job"
    assert targets["authority"]["field"] == "state"
    assert targets["authority"]["owner_visibility"] == "public"
    assert targets["authority"]["visibility"] == "public"
    assert [row["wire_value"] for row in targets["proposed_enum"]["variants"]] == [
        "done",
        "queued",
        "running",
    ]
    assert targets["nonclaims"] == NONCLAIMS
    assert "Human review gate" in proposal
    assert "does not edit Rust source" in proposal
    assert "serialization or wire compatibility" in proposal
    assert _source_manifest(host) == before
    assert not any(path.suffix == ".rs" for path in (host / "reports").rglob("*"))


def test_rust_proposal_clean_partial_failure_stale_and_lifecycle(tmp_path: Path) -> None:
    host = _host(tmp_path, "before")
    findings = _findings(host, candidates=False)
    clean = _collect(host, candidate=None)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    targets = json.loads((host / "reports/extract-enum/job-state/targets.json").read_text())
    assert targets["status"] == "complete" and targets["outcome"] == "clean"
    assert not (host / "reports/extract-enum/job-state/proposal.md").exists()

    payload = json.loads(findings.read_text())
    payload["status"] = "partial"
    findings.write_text(json.dumps(payload))
    partial = _collect(host)
    assert partial.returncode == 2
    assert "partial" in partial.stderr
    assert not (host / "reports/extract-enum/job-state").exists()

    payload["status"] = "failed"
    findings.parent.mkdir(parents=True, exist_ok=True)
    findings.write_text(json.dumps(payload))
    failed = _collect(host)
    assert failed.returncode == 2
    assert "failed" in failed.stderr
    assert not (host / "reports/extract-enum/job-state").exists()

    findings = _findings(host)
    source = host / "state-core/src/state.rs"
    source.write_text(source.read_text() + "\n// stale evidence\n")
    stale = _collect(host)
    assert stale.returncode == 2
    assert "stale" in stale.stderr
    assert not (host / "reports/extract-enum/job-state").exists()


def test_rust_guard_stages_exact_native_assertion_and_catches_seeded_regression(
    tmp_path: Path,
) -> None:
    before_host = _host(tmp_path, "before")
    after_host = _host(tmp_path, "after")
    _findings(before_host)
    assert _collect(before_host).returncode == 0
    targets = before_host / "reports/extract-enum/job-state/targets.json"
    review = _accepted_review(before_host, targets)
    source_before = _source_manifest(before_host)
    installed = tmp_path / "installed/prevent-regression"
    shutil.copytree(GENERATE.parents[1], installed)
    stage = before_host / "reports/prevent-regression/job-state"

    generated = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts/generate_rust_state_guard.py"),
        "--targets",
        str(targets),
        "--accepted-review",
        str(review),
        "--project-root",
        str(before_host),
        "--output-root",
        str(stage),
        cwd=before_host,
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    guard = stage / "guard/exact_field_type_guard.rs"
    text = guard.read_text(encoding="utf-8")
    assert "let _: &JobState = &value.state;" in text
    assert "OtherJob" not in text and '"queued"' not in text
    assert _source_manifest(before_host) == source_before

    verified = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts/verify_rust_state_guard.py"),
        "--stage",
        str(stage),
        "--project-root",
        str(after_host),
        "--cargo",
        str(CARGO),
        "--rustc",
        str(RUSTC),
        "--rustfmt",
        str(RUSTFMT),
        "--cargo-clippy",
        str(CLIPPY),
        "--output",
        "reports/prevent-regression/job-state/verification.json",
        cwd=after_host,
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    report = json.loads(
        (after_host / "reports/prevent-regression/job-state/verification.json").read_text()
    )
    assert report["status"] == "complete"
    assert report["outcome"] == "guard_proved"
    assert report["clean_native"]["cargo_test"]["returncode"] == 0
    assert report["clean_native"]["cargo_clippy"]["returncode"] == 0
    assert report["clean_native"]["cargo_fmt"]["returncode"] == 0
    assert report["seeded_regression"]["without_guard"]["returncode"] == 0
    assert report["seeded_regression"]["with_guard"]["returncode"] != 0
    assert report["seeded_regression"]["caught_by_guard"] is True
    assert report["must_not_fire"]["unrelated_string_field"] is True
    assert report["nonclaims"] == NONCLAIMS
    assert _source_manifest(after_host) == _source_manifest(FIXTURE / "after")


def test_rust_guard_requires_accepted_fresh_review_and_clears_stale_success(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path, "before")
    _findings(host)
    assert _collect(host).returncode == 0
    targets = host / "reports/extract-enum/job-state/targets.json"
    review = _accepted_review(host, targets)
    stage = host / "reports/prevent-regression/job-state"
    command = [
        sys.executable,
        "-I",
        "-S",
        str(GENERATE),
        "--targets",
        str(targets),
        "--accepted-review",
        str(review),
        "--project-root",
        str(host),
        "--output-root",
        str(stage),
    ]
    assert _run(*command, cwd=host).returncode == 0
    payload = json.loads(review.read_text())
    payload["status"] = "review_required"
    review.write_text(json.dumps(payload))
    rejected = _run(*command, cwd=host)
    assert rejected.returncode == 2
    assert "accepted" in rejected.stderr
    assert not stage.exists()

    review = _accepted_review(host, targets)
    payload = json.loads(review.read_text())
    payload["targets_sha256"] = "0" * 64
    review.write_text(json.dumps(payload))
    stale = _run(*command, cwd=host)
    assert stale.returncode == 2
    assert "stale" in stale.stderr
    assert not stage.exists()

    target_payload = json.loads(targets.read_text())
    target_payload["authority"]["owner_visibility"] = "private"
    targets.write_text(json.dumps(target_payload, indent=2, sort_keys=True) + "\n")
    _accepted_review(host, targets)
    partial = _run(*command, cwd=host)
    assert partial.returncode == 2
    assert "partial" in partial.stderr
    assert not stage.exists()
