"""Go exact-clone final outcome, boundaries, failures, and copied closure."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "find-duplication"
FIXTURE = ROOT / "tests" / "fixtures" / "find-duplication-go"


def _go() -> Path:
    executable = shutil.which("go")
    if executable:
        return Path(executable)
    pytest.skip("Go toolchain is unavailable")


def _env(tmp_path: Path, *, path: str | None = None) -> dict[str, str]:
    go = _go()
    return {
        **os.environ,
        "PATH": path if path is not None else f"{go.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GOCACHE": str(tmp_path / "go-cache"),
        "GOTOOLCHAIN": "local",
    }


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env(tmp_path)
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(host).parts
    }


def _pipeline(
    skill: Path,
    host: Path,
    env: dict[str, str],
    report: Path,
    *,
    isolated: bool = False,
) -> tuple[dict, dict]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    collapsed = report / "collapsed.json"
    detect = _run(
        *prefix,
        str(skill / "scripts" / "run_go.py"),
        "--target",
        ".",
        "--project-root",
        str(host),
        "--output",
        str(collapsed),
        cwd=host,
        env=env,
    )
    assert detect.returncode == 0, detect.stdout + detect.stderr
    ranked = report / "ranked.json"
    rank = _run(
        *prefix,
        str(skill / "scripts" / "rank.py"),
        "--input",
        str(collapsed),
        "--output",
        str(ranked),
        cwd=host,
        env=env,
    )
    assert rank.returncode == 0, rank.stdout + rank.stderr
    final = report / "findings.json"
    render = _run(
        *prefix,
        str(skill / "scripts" / "report.py"),
        "--input",
        str(ranked),
        "--output-md",
        str(report / "triage.md"),
        "--output-json",
        str(final),
        "--scan-id",
        "go-g1d",
        cwd=host,
        env=env,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    return json.loads(collapsed.read_text()), json.loads(final.read_text())


def _assert_outcome(report: Path, collapsed: dict, final: dict) -> None:
    meta = collapsed["scan_meta"]
    assert meta["status"] == "partial"
    assert meta["analyzer"] == "go-parser-exact-function-body"
    assert meta["source_inventory"] == {"go_candidates": 10, "policy_excluded": 3}
    assert meta["analysis"]["file_status_counts"] == {
        "build-constraint-ambiguous": 2,
        "complete": 4,
        "generated": 1,
    }
    assert len(collapsed["findings"]) == 1
    finding = final["findings"][0]
    assert finding["finding_id"] == "go-exact-0001"
    assert finding["consolidation_safety"] == "unknown_human_review_required"
    assert {(site["file"], site["method"]) for site in finding["sites"]} == {
        ("src/pending.go", "SummarizePending"),
        ("src/queued.go", "SummarizeQueued"),
    }
    triage = (report / "triage.md").read_text()
    assert "Go v1 boundary" in triage
    assert "Scan status:** `partial`" in triage
    assert "Partial Go scan" in triage
    assert "2 build-constrained source file(s) were not analyzed" in triage
    assert "Do not consolidate automatically" in triage
    assert "semantic equivalence" in triage


def test_go_pipeline_reaches_final_report_and_preserves_source(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _fingerprints(host)
    report = host / "reports" / "duplication" / "go"

    collapsed, final = _pipeline(SKILL, host, env, report)

    _assert_outcome(report, collapsed, final)
    assert _fingerprints(host) == before


def test_copied_go_closure_reaches_final_report(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    copied = tmp_path / "on-demand" / "find-duplication"
    shutil.copytree(SKILL, copied)
    report = host / "reports" / "duplication" / "copied"

    collapsed, final = _pipeline(copied, host, env, report, isolated=True)

    _assert_outcome(report, collapsed, final)
    assert (copied / "scripts" / "detect_go.go").is_file()
    assert "scripts/_lib" not in "\n".join(
        path.read_text(errors="ignore")
        for path in (copied / "scripts").iterdir()
        if path.is_file()
    )


def test_go_failure_and_exclusion_outcomes_are_not_clean(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    output = host / "reports" / "failed.json"
    command = (
        sys.executable,
        str(SKILL / "scripts" / "run_go.py"),
        "--target",
        ".",
        "--project-root",
        str(host),
        "--output",
        str(output),
    )

    broken = host / "src" / "broken.go"
    broken.write_text("package duplicate\nfunc Broken( {\n", encoding="utf-8")
    malformed = _run(*command, cwd=host, env=env)
    assert malformed.returncode == 2
    assert "status=failed" in malformed.stderr
    assert "syntax-error" in malformed.stderr
    assert not output.exists()
    broken.unlink()

    missing = _run(*command, cwd=host, env=_env(tmp_path, path=""))
    assert missing.returncode == 2
    assert "status=unsupported" in missing.stderr
    assert "Go toolchain is unavailable" in missing.stderr
    assert not output.exists()

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_go = fake_bin / "go"
    fake_go.write_text("#!/bin/sh\necho 'go version go1.21.13 fixture'\n", encoding="utf-8")
    fake_go.chmod(0o755)
    old = _run(*command, cwd=host, env=_env(tmp_path, path=str(fake_bin)))
    assert old.returncode == 2
    assert "requires Go >= 1.22" in old.stderr
    assert not output.exists()

    vendor_output = host / "reports" / "vendor.json"
    narrowed = _run(
        sys.executable,
        str(SKILL / "scripts" / "run_go.py"),
        "--target",
        "vendor",
        "--project-root",
        str(host),
        "--output",
        str(vendor_output),
        cwd=host,
        env=env,
    )
    assert narrowed.returncode == 2
    assert "status=unsupported" in narrowed.stderr
    assert not vendor_output.exists()

    generated_output = host / "reports" / "generated.json"
    generated = _run(
        sys.executable,
        str(SKILL / "scripts" / "run_go.py"),
        "--target",
        "src/generated.go",
        "--project-root",
        str(host),
        "--output",
        str(generated_output),
        cwd=host,
        env=env,
    )
    assert generated.returncode == 2
    assert "status=unsupported" in generated.stderr
    assert "no analyzable first-party Go source" in generated.stderr
    assert not generated_output.exists()


def test_same_file_pair_is_not_labeled_cross_file(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    same_file = host / "same_file.go"
    same_file.write_text(
        """package duplicate

func First(values []string) string {
	result := ""
	for _, value := range values {
		result += value
	}
	return result
}

func Second(values []string) string {
	result := ""
	for _, value := range values {
		result += value
	}
	return result
}
""",
        encoding="utf-8",
    )
    output = host / "reports" / "same-file.json"

    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "run_go.py"),
        "--target",
        "same_file.go",
        "--project-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    finding = json.loads(output.read_text())["findings"][0]
    assert finding["shape_hint"] == "same_file_clone"


def test_go_output_overlap_is_rejected_without_source_mutation(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    source = host / "src" / "queued.go"
    before = source.read_bytes()

    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "run_go.py"),
        "--target",
        "src/queued.go",
        "--project-root",
        str(host),
        "--output",
        str(source),
        cwd=host,
        env=env,
    )

    assert result.returncode == 2
    assert "output overlaps Go source" in result.stderr
    assert source.read_bytes() == before


def test_go_contract_declares_bounded_evidence() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    _, raw_frontmatter, _ = text.split("---", 2)
    scans = set(yaml.safe_load(raw_frontmatter)["scans"])
    assert {"python", "javascript", "typescript", "go"} <= scans
    assert "Go exact-function evidence branch" in text
    assert "go/parser" in text
    assert "Do not consolidate automatically" in text
