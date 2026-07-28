"""Go dormant-review final-artifact, boundary, and copied-closure proof."""
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
SKILL = ROOT / ".claude" / "skills" / "find-dormant"
FIXTURE = ROOT / "tests" / "fixtures" / "find-dormant-go"
SCRIPT = SKILL / "scripts" / "detect_go_dormant.py"


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
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(host).parts
    }


def _scan(
    skill: Path,
    host: Path,
    env: dict[str, str],
    *,
    target: str = ".",
    name: str = "go",
    isolated: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    report = host / "reports" / "find-dormant" / name
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    result = _run(
        *prefix,
        str(skill / "scripts" / "detect_go_dormant.py"),
        "--target",
        target,
        "--project-root",
        str(host),
        "--report-dir",
        str(report),
        cwd=host,
        env=env,
    )
    return result, report


def test_go_final_report_is_review_only_and_preserves_source(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _hashes(host)

    result, report = _scan(SKILL, host, env)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert payload["language"] == "go"
    assert payload["analyzer"] == "go-list-go-parser-go-types"
    assert payload["status"] == "complete"
    assert payload["summary"] == {
        "review_required": 2,
        "uncertain": 1,
        "certain_delete": 0,
    }
    assert payload["source_inventory"]["generated"] == 1
    assert payload["source_inventory"]["policy_excluded"] == 1
    assert {candidate["name"] for candidate in payload["candidates"]} == {
        "unusedCallback",
        "unusedPrivate",
    }
    unused = next(candidate for candidate in payload["candidates"] if candidate["name"] == "unusedPrivate")
    assert unused["kind"] == "function"
    assert unused["static_references"] == 0
    assert unused["verdict"] == "review_required"
    assert unused["recommendation"] == "human_review_only"
    assert any("generated" in item.lower() for item in unused["uncertainty"])
    assert all("Object" not in candidate for candidate in payload["candidates"])
    generated_flags = [
        flag for flag in payload["uncertainty_flags"]
        if flag["kind"] == "generated_registration"
    ]
    assert generated_flags == [{
        "kind": "generated_registration",
        "packages": ["src"],
        "message": "Generated Go source was excluded from use resolution and may register or reference symbols.",
        "evidence": ["src/zz_generated.go"],
    }]
    assert payload["uncertain_symbols"] == [{
        "file": "src/dormant.go",
        "line": 24,
        "name": "dynamicByName",
        "kind": "variable_function",
        "reason": "An exact matching string literal may be reflective or dynamic reachability; static analysis cannot resolve it.",
        "verdict": "uncertain",
    }]
    assert all(candidate["name"] not in {"directlyUsed", "usedCallback", "registeredHandler", "unusedMethod"} for candidate in payload["candidates"])
    report_text = (report / "report.md").read_text(encoding="utf-8")
    assert "Never safe deletion" in report_text
    assert "reflection" in report_text
    assert "//go:linkname" in report_text
    assert _hashes(host) == before
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr


def test_copied_go_closure_reaches_final_report_without_checkout_runtime(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    copied = tmp_path / "on-demand" / "find-dormant"
    shutil.copytree(SKILL, copied)
    before = _hashes(host)

    result, report = _scan(copied, host, env, name="copied", isolated=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (report / "report.md").is_file()
    assert json.loads((report / "findings.json").read_text(encoding="utf-8"))["summary"]["certain_delete"] == 0
    assert (copied / "scripts" / "detect_go_dormant.go").is_file()
    copied_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (copied / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in copied_runtime
    assert "/_common" not in copied_runtime
    assert _hashes(host) == before


def test_go_failures_and_partial_package_facts_are_explicit(tmp_path: Path) -> None:
    host, env = _host(tmp_path)

    broken = host / "src" / "broken.go"
    broken.write_text("package dormant\nfunc broken( {\n", encoding="utf-8")
    malformed, report = _scan(
        SKILL,
        host,
        env,
        target="src/dormant.go",
        name="malformed-sibling",
    )
    assert malformed.returncode == 2
    assert "syntax-error" in malformed.stderr
    assert not report.exists()
    broken.unlink()

    missing, report = _scan(SKILL, host, _env(tmp_path, path=""), name="missing")
    assert missing.returncode == 2
    assert "Go toolchain is unavailable" in missing.stderr
    assert not report.exists()

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_go = fake_bin / "go"
    fake_go.write_text("#!/bin/sh\necho 'go version go1.21.13 fixture'\n", encoding="utf-8")
    fake_go.chmod(0o755)
    old, report = _scan(SKILL, host, _env(tmp_path, path=str(fake_bin)), name="old")
    assert old.returncode == 2
    assert "requires Go >= 1.22" in old.stderr
    assert not report.exists()

    active_tagged = host / "src" / "active_tagged.go"
    active_tagged.write_text(
        "//go:build !never\n\npackage dormant\nfunc activeTagged() {}\n",
        encoding="utf-8",
    )
    active, report = _scan(
        SKILL,
        host,
        env,
        target="src/active_tagged.go",
        name="active-tagged",
    )
    assert active.returncode == 0, active.stdout + active.stderr
    active_payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert active_payload["status"] == "complete"
    assert [candidate["name"] for candidate in active_payload["candidates"]] == [
        "activeTagged",
    ]
    active_tagged.unlink()

    constrained = host / "src" / "inactive.go"
    constrained.write_text(
        "//go:build never\n\npackage dormant\nfunc inactiveOnly() {}\n",
        encoding="utf-8",
    )
    partial, report = _scan(SKILL, host, env, name="partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["project_resolution"]["state"] == "partial"
    assert payload["project_resolution"]["unavailable_files"] == [{
        "file": "src/inactive.go",
        "reason": "build-constraint-ambiguous",
    }]


def test_go_failed_scans_preserve_the_last_good_report(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    good, report = _scan(SKILL, host, env, name="stable")
    assert good.returncode == 0, good.stdout + good.stderr
    before = {
        name: (report / name).read_bytes()
        for name in ("findings.json", "report.md")
    }

    broken = host / "src" / "broken.go"
    broken.write_text("package dormant\nfunc broken( {\n", encoding="utf-8")
    failed, _ = _scan(
        SKILL,
        host,
        env,
        target="src/dormant.go",
        name="stable",
    )
    assert failed.returncode == 2
    assert "syntax-error" in failed.stderr
    broken.unlink()

    missing, _ = _scan(SKILL, host, _env(tmp_path, path=""), name="stable")
    assert missing.returncode == 2
    assert "Go toolchain is unavailable" in missing.stderr

    fake_bin = tmp_path / "fake-stable-bin"
    fake_bin.mkdir()
    fake_go = fake_bin / "go"
    fake_go.write_text("#!/bin/sh\necho 'go version go1.21.13 fixture'\n", encoding="utf-8")
    fake_go.chmod(0o755)
    old, _ = _scan(SKILL, host, _env(tmp_path, path=str(fake_bin)), name="stable")
    assert old.returncode == 2
    assert "requires Go >= 1.22" in old.stderr

    copied = tmp_path / "broken-helper" / "find-dormant"
    shutil.copytree(SKILL, copied)
    (copied / "scripts" / "detect_go_dormant.go").unlink()
    helper, _ = _scan(copied, host, env, name="stable")
    assert helper.returncode == 2
    assert "batched Go detector failed" in helper.stderr

    assert {
        name: (report / name).read_bytes()
        for name in ("findings.json", "report.md")
    } == before


def test_go_exclusions_and_report_symlinks_are_safe(tmp_path: Path) -> None:
    host, env = _host(tmp_path)

    linked_source = host / "src" / "linked.go"
    linked_source.symlink_to(host / "src" / "dormant.go")
    linked, report = _scan(SKILL, host, env, name="linked-source")
    assert linked.returncode == 2
    assert "symbolic-link Go source" in linked.stderr
    assert not report.exists()
    linked_source.unlink()

    excluded, report = _scan(SKILL, host, env, target="vendor", name="vendor")
    assert excluded.returncode == 2
    assert "no eligible first-party Go source" in excluded.stderr
    assert not report.exists()

    before = _hashes(host)
    reports = host / "reports"
    reports.mkdir()
    reports.rmdir()
    reports.symlink_to(host / "src")
    unsafe, _ = _scan(SKILL, host, env, name="unsafe")
    assert unsafe.returncode == 2
    assert "symbolic link" in unsafe.stderr
    assert _hashes(host) == before
    reports.unlink()


def test_go_docs_declare_the_bounded_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    scans = set(text.split("scans: [", 1)[1].split("]", 1)[0].split(", "))
    assert {"python", "typescript", "javascript", "go"} <= scans
    assert "## Go v1" in text
    assert "go/types" in text
    assert "never infer safe deletion" in text
