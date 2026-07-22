"""Java exact-clone final outcome, failure boundaries, and copied closure."""
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
SKILL = ROOT / ".claude/skills/find-duplication"
FIXTURE = ROOT / "tests/fixtures/find-duplication-java"


def _jdk() -> Path:
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java is None or javac is None:
        pytest.skip("JDK is unavailable")
    version = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
    rendered = version.stdout + version.stderr
    if version.returncode or "javac " not in rendered or int(rendered.split("javac ", 1)[1].split(".", 1)[0]) < 17:
        pytest.skip("JDK 17+ is unavailable")
    return Path(java).parent


def _env(tmp_path: Path, *, path: str | None = None) -> dict[str, str]:
    jdk = _jdk()
    java_tmp = tmp_path / "java-tmp"
    java_tmp.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "PATH": path if path is not None else f"{jdk}{os.pathsep}{os.environ.get('PATH', '')}",
        "JAVA_TOOL_OPTIONS": f"-Djava.io.tmpdir={java_tmp}",
    }


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env(tmp_path)
    sources = sorted(str(path) for path in (host / "src/main/java").rglob("*.java"))
    native = _run("javac", "-d", str(tmp_path / "classes"), *sources, cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(host).parts
    }


def _pipeline(skill: Path, host: Path, env: dict[str, str], report: Path, *, isolated: bool = False):
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    collapsed = report / "collapsed.json"
    detect = _run(
        *prefix,
        str(skill / "scripts/run_java.py"),
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
    rank = _run(*prefix, str(skill / "scripts/rank.py"), "--input", str(collapsed), "--output", str(ranked), cwd=host, env=env)
    assert rank.returncode == 0, rank.stdout + rank.stderr
    final = report / "findings.json"
    render = _run(
        *prefix,
        str(skill / "scripts/report.py"),
        "--input",
        str(ranked),
        "--output-md",
        str(report / "triage.md"),
        "--output-json",
        str(final),
        "--scan-id",
        "java-j1",
        cwd=host,
        env=env,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    return json.loads(collapsed.read_text()), json.loads(final.read_text())


def _assert_outcome(report: Path, collapsed: dict, final: dict) -> None:
    meta = collapsed["scan_meta"]
    assert meta["status"] == "complete"
    assert meta["analyzer"] == "jdk-tree-exact-method-body"
    assert meta["source_inventory"] == {"java_candidates": 5, "policy_excluded": 2}
    assert meta["analysis"]["file_status_counts"] == {"complete": 3}
    assert len(collapsed["findings"]) == 1
    finding = final["findings"][0]
    assert finding["finding_id"] == "java-exact-0001"
    assert finding["consolidation_safety"] == "unknown_human_review_required"
    assert {(site["file"], site["method"]) for site in finding["sites"]} == {
        ("src/main/java/example/PendingFormatter.java", "PendingFormatter.summarize"),
        ("src/main/java/example/QueuedFormatter.java", "QueuedFormatter.summarize"),
    }
    triage = (report / "triage.md").read_text(encoding="utf-8")
    assert "Java v1 boundary" in triage
    assert "Do not consolidate automatically" in triage
    assert "exact normalized method/constructor-body clone evidence" in triage


def test_java_pipeline_reaches_final_report_and_preserves_source(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _fingerprints(host)
    report = host / "reports/duplication/java"
    collapsed, final = _pipeline(SKILL, host, env, report)
    _assert_outcome(report, collapsed, final)
    assert _fingerprints(host) == before


def test_copied_java_closure_reaches_final_report(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    copied = tmp_path / "on-demand/find-duplication"
    shutil.copytree(SKILL, copied)
    report = host / "reports/duplication/copied"
    collapsed, final = _pipeline(copied, host, env, report, isolated=True)
    _assert_outcome(report, collapsed, final)
    assert (copied / "scripts/detect_java.java").is_file()
    closure = "\n".join(path.read_text(errors="ignore") for path in (copied / "scripts").iterdir() if path.is_file())
    assert "scripts/_lib" not in closure
    assert str(ROOT) not in closure


def test_java_detector_analyzes_physical_source_once_through_internal_aliases(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    source = host / "src/main/java/example/PendingFormatter.java"
    (host / "pending-alias.java").symlink_to(source)
    (host / "java-directory-alias").symlink_to(
        host / "src/main/java", target_is_directory=True
    )
    output = host / "reports/aliases.json"

    result = _run(
        sys.executable,
        str(SKILL / "scripts/run_java.py"),
        "--target",
        ".",
        "--project-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["scan_meta"]["analysis"]["file_status_counts"] == {"complete": 3}
    assert len(payload["findings"]) == 1
    sites = payload["findings"][0]["sites"]
    assert payload["findings"][0]["multiplicity"] == 2
    assert not any(site["file"] == "pending-alias.java" for site in sites)
    assert not any(site["file"].startswith("java-directory-alias/") for site in sites)


def test_java_failures_and_contract_are_honest(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    broken = host / "src/main/java/example/Broken.java"
    broken.write_text("package example; public class Broken { public void nope( { }\n", encoding="utf-8")
    output = host / "reports/failed.json"
    command = (
        sys.executable,
        str(SKILL / "scripts/run_java.py"),
        "--target",
        ".",
        "--project-root",
        str(host),
        "--output",
        str(output),
    )
    malformed = _run(*command, cwd=host, env=env)
    assert malformed.returncode == 2
    assert "status=failed" in malformed.stderr
    assert "syntax-error" in malformed.stderr
    assert not output.exists()
    broken.unlink()

    missing = _run(*command, cwd=host, env=_env(tmp_path / "missing", path=""))
    assert missing.returncode == 2
    assert "status=unsupported" in missing.stderr
    assert not output.exists()

    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "Java exact-method evidence branch" in text
    assert "JDK 17" in text
    assert "semantic equivalence" in text
