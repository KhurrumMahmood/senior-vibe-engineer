"""Go outcome, boundary, and copied-closure proof for complexity hotspots."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-complexity-hotspots"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-complexity-hotspots-go"
LOCAL_GO = Path("/opt/homebrew/bin/go")


def _go_bin() -> Path:
    found = shutil.which("go")
    if found:
        return Path(found)
    if LOCAL_GO.is_file():
        return LOCAL_GO
    pytest.skip("Go toolchain is unavailable")


def _go_env(cache_root: Path, *, path: str | None = None) -> dict[str, str]:
    go = _go_bin()
    return {
        **os.environ,
        "PATH": path if path is not None else f"{go.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GOCACHE": str(cache_root),
    }


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _fingerprints(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.parts
    }


def _copy_host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _go_env(tmp_path / "go-cache")
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    go_files = sorted(
        str(path.relative_to(host))
        for path in host.rglob("*.go")
        if "vendor" not in path.parts
    )
    formatted = _run("gofmt", "-d", *go_files, cwd=host, env=env)
    assert formatted.returncode == 0, formatted.stdout + formatted.stderr
    assert formatted.stdout == ""
    return host, env


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _run_pipeline(skill: Path, host: Path, env: dict[str, str], *, isolated: bool = False) -> tuple[dict, list[dict]]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    result = _run(
        *prefix,
        str(skill / "scripts" / "run.py"),
        "--project-root",
        str(host),
        "--language",
        "go",
        "--skip-effectiveness-log",
        "src",
        cwd=host,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report_dir = (host / "reports" / "find-complexity-hotspots" / "latest").resolve()
    payload = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    return payload, _records(report_dir / "detections.jsonl")


def _assert_go_outcome(payload: dict, records: list[dict]) -> None:
    assert payload["status"] == "partial"
    assert payload["summary"]["findings_total"] == 2
    assert payload["analysis"]["go"]["status"] == "partial"
    assert payload["analysis"]["go"]["analyzer"] == "go-parser-go-ast"
    assert payload["analysis"]["go"]["minimum_go_version"] == "1.22.0"
    assert payload["analysis"]["go"]["ambiguous"] == [
        {"file": "src/tagged_ambiguous.go", "reason": "build-constraint-ambiguous"}
    ]
    assert {record["file"] for record in records} == {"src/complexity.go"}
    assert {record["symbol"] for record in records} == {
        "declaredHotspot",
        "(*ComplexityService).methodHotspot",
    }
    assert {record["kind"] for record in records} == {"function", "method"}
    assert {record["language"] for record in records} == {"go"}
    assert {record["analyzer"] for record in records} == {"go-parser-go-ast"}
    assert {record["branch_score"] for record in records} == {18}
    for record in records:
        source = (FIXTURE / record["file"]).read_text(encoding="utf-8").splitlines()
        assert record["symbol"].split(".")[-1] in source[record["lineno"] - 1]
        assert source[record["end_lineno"] - 1].strip() == "}"


def test_go_outcome_reaches_final_report_with_partial_build_tag_and_no_source_mutation(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    before = _fingerprints(host)

    payload, records = _run_pipeline(SKILL, host, env)

    _assert_go_outcome(payload, records)
    assert _fingerprints(host) == before
    report = (host / "reports" / "find-complexity-hotspots" / "latest" / "report.md").read_text(encoding="utf-8")
    assert "**Status:** partial" in report
    assert "go-parser-go-ast" in report
    assert "build-constraint-ambiguous" in report


def test_go_direct_exclusions_and_nested_function_do_not_fire(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    targets = (
        "src/clean.go",
        "src/nested_func.go",
        "src/fixture_test.go",
        "src/zz_generated.go",
        "src/wire.go",
        "src/generated/complexity_generated.go",
        "vendor/example.com/thirdparty/complexity.go",
    )
    for index, target in enumerate(targets):
        output = host / f"excluded-{index}.jsonl"
        result = _run(
            sys.executable,
            str(SKILL / "scripts" / "detect.py"),
            "--project-root",
            str(host),
            "--output",
            str(output),
            "--language",
            "go",
            target,
            cwd=host,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert _records(output) == [], target


def test_go_syntax_and_tool_failures_are_explicit_and_not_clean(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    broken = host / "src" / "broken.go"
    broken.write_text("package complexity\nfunc broken( { return 1 }\n", encoding="utf-8")
    syntax = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(host / "broken.jsonl"),
        "--language",
        "go",
        "src/broken.go",
        cwd=host,
        env=env,
    )
    assert syntax.returncode == 2
    assert "syntax error" in syntax.stderr

    missing = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(host / "missing.jsonl"),
        "--language",
        "go",
        "src/complexity.go",
        cwd=host,
        env=_go_env(tmp_path / "missing-cache", path=""),
    )
    assert missing.returncode == 2
    assert "Go toolchain is unavailable" in missing.stderr

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_go = fake_bin / "go"
    fake_go.write_text(
        "#!/bin/sh\nif [ \"$1\" = version ]; then echo 'go version go1.21.13 test'; exit 0; fi\nexit 99\n",
        encoding="utf-8",
    )
    fake_go.chmod(0o755)
    old = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(host / "old.jsonl"),
        "--language",
        "go",
        "src/complexity.go",
        cwd=host,
        env=_go_env(tmp_path / "old-cache", path=str(fake_bin)),
    )
    assert old.returncode == 2
    assert "requires Go >= 1.22.0" in old.stderr


def test_malformed_go_rerun_invalidates_latest_report(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    _run_pipeline(SKILL, host, env)
    latest = host / "reports" / "find-complexity-hotspots" / "latest"
    previous_report = latest.resolve()
    (host / "src" / "broken.go").write_text(
        "package complexity\nfunc broken( { return 1 }\n", encoding="utf-8"
    )

    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "run.py"),
        "--project-root",
        str(host),
        "--language",
        "go",
        "--skip-effectiveness-log",
        "src",
        cwd=host,
        env=env,
    )

    assert result.returncode == 2
    assert "syntax error" in result.stderr
    assert not latest.exists()
    assert not latest.is_symlink()
    assert (previous_report / "findings.json").is_file()


def test_missing_go_tool_rerun_invalidates_latest_report(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    _run_pipeline(SKILL, host, env)
    latest = host / "reports" / "find-complexity-hotspots" / "latest"
    previous_report = latest.resolve()

    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "run.py"),
        "--project-root",
        str(host),
        "--language",
        "go",
        "--skip-effectiveness-log",
        "src",
        cwd=host,
        env=_go_env(tmp_path / "missing-cache", path=""),
    )

    assert result.returncode == 2
    assert "Go toolchain is unavailable" in result.stderr
    assert not latest.exists()
    assert not latest.is_symlink()
    assert (previous_report / "findings.json").is_file()


def test_copied_skill_runs_without_toolkit_or_sibling_runtime(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    installed = tmp_path / "installed" / "find-complexity-hotspots"
    shutil.copytree(SKILL, installed)

    payload, records = _run_pipeline(installed, host, env, isolated=True)

    _assert_go_outcome(payload, records)
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in closure
    assert "/_common" not in closure


def test_frontmatter_and_docs_name_the_narrow_go_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "go" in text
    assert "Go >= 1.22.0" in text
    assert "go/parser" in text
    assert "build-constraint-ambiguous" in text
