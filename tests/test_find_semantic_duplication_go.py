"""Go semantic-duplication final-artifact and copied-closure proof."""
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
SKILL = ROOT / ".claude" / "skills" / "find-semantic-duplication"
FIXTURE = ROOT / "tests" / "fixtures" / "find-semantic-duplication-go"
PYTHON = Path(sys.executable)


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


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.go"))
        if "reports" not in path.relative_to(host).parts
    }


def _scan(
    skill: Path,
    host: Path,
    env: dict[str, str],
    *,
    name: str = "go",
    target: str = ".",
    go_executable: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    report = host / "reports" / "semantic-duplication" / name
    args = [
        str(PYTHON),
        str(skill / "scripts" / "detect_go_semantic.py"),
        "--target",
        target,
        "--project-root",
        str(host),
        "--report-dir",
        str(report),
    ]
    if go_executable is not None:
        args.extend(("--go-executable", go_executable))
    return _run(*args, cwd=host, env=env), report


def test_go_semantic_triage_is_conservative_and_preserves_source(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _hashes(host)

    result, report = _scan(SKILL, host, env)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert payload["language"] == "go"
    assert payload["analyzer"] == "go-list-go-parser-go-types"
    assert payload["status"] == "complete"
    assert payload["capability_matrix"]["function_level_static_candidates"] == "available"
    confirmed = payload["confirmed"]
    assert [finding["finding_id"] for finding in confirmed] == ["GO-SD-0001"]
    assert {member["qualified_name"] for member in confirmed[0]["members"]} == {
        "SummarizeByIndex",
        "SummarizeByRange",
    }
    assert confirmed[0]["investigation_status"] == "confirmed"
    assert "not proof of behavioral equivalence" in confirmed[0]["notes"]
    assert {item["reason_code"] for item in payload["rejected"]} >= {
        "caller_callee",
        "token_similar_belongs_in_find_duplication",
        "load_bearing_divergence",
    }
    assert {item["reason_code"] for item in payload["uncertain"]} == {
        "direct_call_unresolved_or_dynamic",
    }
    matrix = report / confirmed[0]["matrix_path"]
    assert matrix.is_file()
    matrix_text = matrix.read_text(encoding="utf-8")
    assert "Static result type" in matrix_text
    assert "Resolved direct call relationship" in matrix_text
    assert "Panic / defer / goroutine policy" in matrix_text
    assert _hashes(host) == before


def test_copied_go_semantic_skill_reaches_final_report(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    copied = tmp_path / "on-demand" / "find-semantic-duplication"
    shutil.copytree(SKILL, copied)

    result, report = _scan(copied, host, env, name="copied")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (report / "triage.md").is_file()
    assert (copied / "scripts" / "detect_go_semantic.go").is_file()
    runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (copied / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in runtime
    assert "/_common" not in runtime


def test_go_semantic_failure_modes_leave_no_partial_report(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    (host / "broken.go").write_text("package semanticfixture\nfunc broken( {\n", encoding="utf-8")
    malformed, report = _scan(SKILL, host, env, name="malformed")
    assert malformed.returncode == 2
    assert "syntax-error" in malformed.stderr or "type facts unavailable" in malformed.stderr
    assert not report.exists()
    (host / "broken.go").unlink()

    missing, report = _scan(
        SKILL,
        host,
        env,
        name="missing",
        go_executable=str(tmp_path / "missing-go"),
    )
    assert missing.returncode == 2
    assert "Go toolchain" in missing.stderr or "cannot run" in missing.stderr
    assert not report.exists()

    old = tmp_path / "old-go"
    old.write_text("#!/bin/sh\necho 'go version go1.21.9 fixture'\n", encoding="utf-8")
    old.chmod(0o755)
    unsupported, report = _scan(
        SKILL,
        host,
        env,
        name="old",
        go_executable=str(old),
    )
    assert unsupported.returncode == 2
    assert "requires Go >= 1.22" in unsupported.stderr
    assert not report.exists()


def test_go_semantic_inactive_build_source_is_explicitly_partial(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    (host / "inactive.go").write_text(
        "//go:build never\n\npackage semanticfixture\n\n"
        "type InactiveSummary struct { Labels []string; Total int }\n"
        "func InactiveOne() InactiveSummary { "
        "return InactiveSummary{Labels: []string{\"one\"}, Total: 1} }\n",
        encoding="utf-8",
    )

    result, report = _scan(SKILL, host, env, name="partial")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    analysis = json.loads((report / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["unavailable_files"] == ["inactive.go"]


def test_go_semantic_rejects_symlinked_target_and_report_paths(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    os.symlink(host / "semantic.go", host / "linked.go")

    target_result, report = _scan(
        SKILL, host, env, name="linked-target", target="linked.go"
    )

    assert target_result.returncode == 2
    assert "symbolic link" in target_result.stderr
    assert not report.exists()

    report_root = host / "reports" / "semantic-duplication"
    report_root.mkdir(parents=True)
    os.symlink(host, report_root / "linked-report")
    report_result, _ = _scan(SKILL, host, env, name="linked-report/scan")
    assert report_result.returncode == 2
    assert "symbolic link" in report_result.stderr
