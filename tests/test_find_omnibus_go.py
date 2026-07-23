"""Go final-outcome, boundary, and copied-closure proof for find-omnibus."""
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
SKILL = ROOT / ".claude" / "skills" / "find-omnibus"
FIXTURE = ROOT / "tests" / "fixtures" / "find-omnibus-go"


def _go() -> Path:
    executable = shutil.which("go")
    if executable:
        return Path(executable)
    fallback = Path("/opt/homebrew/bin/go")
    if fallback.is_file():
        return fallback
    pytest.skip("Go toolchain is unavailable")


def _env(cache: Path, *, path: str | None = None) -> dict[str, str]:
    go = _go()
    return {
        **os.environ,
        "PATH": path if path is not None else f"{go.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GOCACHE": str(cache),
    }


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env(tmp_path / "go-cache")
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _pipeline(
    skill: Path,
    host: Path,
    env: dict[str, str],
    output: Path,
    *,
    isolated: bool = False,
) -> tuple[list[dict], dict]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    detections = output / "omnibus.jsonl"
    detect = _run(
        *prefix,
        str(skill / "scripts" / "detect.py"),
        "--target",
        str(host),
        "--project-root",
        str(host),
        "--output",
        str(detections),
        "--language",
        "go",
        cwd=host,
        env=env,
    )
    assert detect.returncode == 0, detect.stdout + detect.stderr
    candidates = output / "candidates.jsonl"
    collapse = _run(
        *prefix,
        str(skill / "scripts" / "collapse.py"),
        "--detections",
        str(detections),
        "--output",
        str(candidates),
        cwd=host,
        env=env,
    )
    assert collapse.returncode == 0, collapse.stdout + collapse.stderr
    candidate = _records(candidates)[0]
    scout = output / "scout"
    scout.mkdir()
    (scout / f"{candidate['candidate_id']}.json").write_text(
        json.dumps({
            "candidate_id": candidate["candidate_id"],
            "file": candidate["file"],
            "bucket": "confirmed_omnibus",
            "domains_confirmed": ["invoice", "shipment", "customer", "inventory"],
            "facets_collapsed": [],
            "srp_rewrite": "This package file handles four independent record domains.",
            "decomposition_sketch": [],
            "decomposition_depth_note": "Each domain has a separate public surface.",
            "false_positive_reason": None,
            "notes": "Locked Go outcome fixture.",
            "recommendation": "decompose",
        }),
        encoding="utf-8",
    )
    report = _run(
        *prefix,
        str(skill / "scripts" / "report.py"),
        "--candidates",
        str(candidates),
        "--scout-dir",
        str(scout),
        "--output-md",
        str(output / "report.md"),
        "--output-json",
        str(output / "findings.json"),
        "--scan-id",
        "g1-go",
        "--target",
        ".",
        cwd=host,
        env=env,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    return _records(detections), json.loads((output / "findings.json").read_text())


def _assert_outcome(records: list[dict], findings: dict) -> None:
    assert [record["file"] for record in records] == ["src/omnibus.go"]
    record = records[0]
    assert record["language"] == "go"
    assert record["analyzer"] == "go-parser-go-ast"
    assert record["and_count"] == 3
    assert {cluster["name"] for cluster in record["clusters"]} == {
        "customer", "inventory", "invoice", "shipment",
    }
    assert findings["summary"]["bucket_counts"]["confirmed_omnibus"] == 1


def test_go_pipeline_reaches_final_report_without_source_changes(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _fingerprints(host)

    records, findings = _pipeline(SKILL, host, env, host / "reports" / "go")

    _assert_outcome(records, findings)
    assert _fingerprints(host) == before


def test_copied_go_closure_is_self_contained(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    copied = tmp_path / "on-demand" / "find-omnibus"
    shutil.copytree(SKILL, copied)

    records, findings = _pipeline(copied, host, env, host / "reports" / "copied", isolated=True)

    _assert_outcome(records, findings)
    assert (copied / "scripts" / "detect_go_symbols.go").is_file()


def test_go_syntax_and_tool_failures_are_explicit(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    broken = host / "src" / "broken.go"
    broken.write_text("package omnibus\nfunc broken( {\n", encoding="utf-8")
    command = (
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--target",
        str(host / "src"),
        "--project-root",
        str(host),
        "--output",
        str(host / "broken.jsonl"),
        "--language",
        "go",
    )

    syntax = _run(*command, cwd=host, env=env)
    assert syntax.returncode == 2
    assert "syntax error" in syntax.stderr

    broken.unlink()
    missing = _run(*command, cwd=host, env=_env(tmp_path / "missing-cache", path=""))
    assert missing.returncode == 2
    assert "Go toolchain is unavailable" in missing.stderr

    generated_platform = host / "src" / "generated_windows.go"
    generated_platform.write_text(
        "// Code generated by fixture-builder. DO NOT EDIT.\n\n"
        "package omnibus\nfunc generatedPlatform() {}\n",
        encoding="utf-8",
    )
    generated = _run(*command, cwd=host, env=env)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    generated_platform.unlink()

    constrained = host / "src" / "constrained.go"
    constrained.write_text(
        "//go:build special\n\npackage omnibus\nfunc constrained() {}\n",
        encoding="utf-8",
    )
    ambiguous = _run(*command, cwd=host, env=env)
    assert ambiguous.returncode == 2
    assert "build-constrained Go source is unsupported" in ambiguous.stderr

    constrained.unlink()
    platform = host / "src" / "platform_windows.go"
    platform.write_text("package omnibus\nfunc platformOnly() {}\n", encoding="utf-8")
    implicit = _run(*command, cwd=host, env=env)
    assert implicit.returncode == 2
    assert "build-constrained Go source is unsupported" in implicit.stderr
    platform.unlink()

    unconstrained = host / "src" / "clean_linux_impl.go"
    unconstrained.write_text(
        "package omnibus\nfunc cleanLinuxImplementation() {}\n", encoding="utf-8"
    )
    ordinary = _run(*command, cwd=host, env=env)
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    unconstrained.unlink()

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_go = fake_bin / "go"
    fake_go.write_text(
        "#!/bin/sh\necho 'go version go1.21.13 fixture'\n",
        encoding="utf-8",
    )
    fake_go.chmod(0o755)
    old = _run(*command, cwd=host, env=_env(tmp_path / "old-cache", path=str(fake_bin)))
    assert old.returncode == 2
    assert "requires Go >= 1.22.0" in old.stderr


def test_narrow_vendor_target_cannot_bypass_go_source_policy(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    output = host / "vendor.jsonl"

    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--target",
        str(host / "vendor"),
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--language",
        "go",
        cwd=host,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _records(output) == []


def test_go_frontmatter_declares_support() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "scans: [python, javascript, typescript, go, java, rust, swift]" in text
    assert "--language python|javascript|typescript|go|java" in text
