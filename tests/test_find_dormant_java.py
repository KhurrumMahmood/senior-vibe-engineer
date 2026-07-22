"""JDK 17 final-artifact, boundary, and copied-closure proof for Java dormant review."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "find-dormant"
FIXTURE = ROOT / "tests" / "fixtures" / "find-dormant-java"
SCRIPT = SKILL / "scripts" / "detect_java_dormant.java"
JAVA = shutil.which("java")
JAVAC = shutil.which("javac")
pytestmark = pytest.mark.skipif(
    JAVA is None or JAVAC is None,
    reason="A JDK with java and javac is required",
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _native_compile(host: Path) -> subprocess.CompletedProcess[str]:
    classes = host / "classes"
    sources = sorted((host / "src" / "main" / "java").rglob("*.java"))
    return _run(JAVAC, "--release", "17", "-proc:none", "-d", str(classes), *map(str, sources), cwd=host)


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts
    }


def _scan(
    skill: Path,
    host: Path,
    *,
    target: str = "src/main/java/example/dormant",
    name: str = "java",
    minimum_jdk: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    report = host / "reports" / "find-dormant" / name
    args = [
        JAVA,
        str(skill / "scripts" / "detect_java_dormant.java"),
        "--target",
        target,
        "--project-root",
        str(host),
        "--report-dir",
        str(report),
    ]
    if minimum_jdk is not None:
        args.extend(["--minimum-jdk", minimum_jdk])
    return _run(*args, cwd=host), report


def _payload(report: Path) -> dict:
    return json.loads((report / "findings.json").read_text(encoding="utf-8"))


def test_java_final_report_is_review_only_and_preserves_source(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    assert _native_compile(host).returncode == 0
    before = _hashes(host)

    result, report = _scan(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(report)
    assert payload["language"] == "java"
    assert payload["analyzer"] == "jdk17-javactask-trees"
    assert payload["status"] == "complete"
    assert payload["summary"] == {
        "review_required": 1,
        "uncertain": 1,
        "certain_delete": 0,
    }
    assert payload["source_inventory"]["generated"] == 1
    assert [candidate["name"] for candidate in payload["candidates"]] == ["unusedPrivate"]
    unused = payload["candidates"][0]
    assert unused["kind"] == "private_method"
    assert unused["static_references"] == 0
    assert unused["verdict"] == "review_required"
    assert unused["recommendation"] == "human_review_only"
    assert payload["uncertain_symbols"] == [{
        "file": "src/main/java/example/dormant/Dormant.java",
        "line": 10,
        "name": "dynamicByName",
        "kind": "private_method",
        "reason": "An exact matching string literal may be reflective or dynamic reachability; static analysis cannot resolve it.",
        "verdict": "uncertain",
    }]
    assert {flag["kind"] for flag in payload["uncertainty_flags"]} >= {
        "generated_source_excluded",
        "reflection_or_dynamic_lookup",
        "runtime_boundary",
    }
    report_text = (report / "report.md").read_text(encoding="utf-8")
    assert "Never safe deletion" in report_text
    assert "reflection" in report_text
    assert _hashes(host) == before
    assert _native_compile(host).returncode == 0


def test_java_copied_closure_reaches_final_report_without_checkout_runtime(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    copied = tmp_path / "on-demand" / "find-dormant"
    shutil.copytree(SKILL, copied)
    before = _hashes(host)

    result, report = _scan(copied, host, name="copied")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (report / "report.md").is_file()
    assert _payload(report)["summary"]["certain_delete"] == 0
    closure = (copied / "scripts" / "detect_java_dormant.java").read_text(encoding="utf-8")
    assert "scripts/_lib" not in closure
    assert "/_common" not in closure
    assert str(ROOT) not in closure
    assert _hashes(host) == before


def test_java_partial_failed_and_unsupported_states_are_explicit(tmp_path: Path) -> None:
    partial_host = _copy_host(tmp_path, "partial")
    (partial_host / "src" / "main" / "java" / "example" / "dormant" / "Missing.java").write_text(
        "package example.dormant;\n\nimport missing.Dependency;\n\nfinal class Missing { Dependency value; }\n",
        encoding="utf-8",
    )
    partial, partial_report = _scan(SKILL, partial_host, name="partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    partial_payload = _payload(partial_report)
    assert partial_payload["status"] == "partial"
    assert partial_payload["failure_kind"] == "unresolved_compilation"
    assert partial_payload["summary"]["certain_delete"] == 0
    assert "Incomplete compiler evidence" in (partial_report / "report.md").read_text(encoding="utf-8")

    malformed_host = _copy_host(tmp_path, "malformed")
    (malformed_host / "src" / "main" / "java" / "example" / "dormant" / "Broken.java").write_text(
        "package example.dormant; final class Broken { void nope( { }\n",
        encoding="utf-8",
    )
    malformed, malformed_report = _scan(SKILL, malformed_host, name="malformed")
    assert malformed.returncode == 2
    assert "syntax_error" in malformed.stderr
    assert not malformed_report.exists()

    old_host = _copy_host(tmp_path, "old")
    old, old_report = _scan(SKILL, old_host, name="old", minimum_jdk="99")
    assert old.returncode == 0, old.stdout + old.stderr
    old_payload = _payload(old_report)
    assert old_payload["status"] == "unsupported"
    assert old_payload["failure_kind"] == "jdk_version_too_old"

    missing_host = _copy_host(tmp_path, "missing")
    missing, missing_report = _scan(SKILL, missing_host, target="does-not-exist", name="missing")
    assert missing.returncode == 0, missing.stdout + missing.stderr
    assert _payload(missing_report)["failure_kind"] == "target_missing"


def test_java_refuses_symlink_source_and_failed_scan_preserves_last_good_report(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    good, report = _scan(SKILL, host, name="stable")
    assert good.returncode == 0, good.stdout + good.stderr
    before = {name: (report / name).read_bytes() for name in ("findings.json", "report.md")}

    broken = host / "src" / "main" / "java" / "example" / "dormant" / "Broken.java"
    broken.write_text("package example.dormant; final class Broken { void nope( { }\n", encoding="utf-8")
    failed, _ = _scan(SKILL, host, name="stable")
    assert failed.returncode == 2
    assert "syntax_error" in failed.stderr
    assert {name: (report / name).read_bytes() for name in before} == before
    broken.unlink()

    external = tmp_path / "Outside.java"
    external.write_text("package example.dormant; final class Outside {}\n", encoding="utf-8")
    linked = host / "src" / "main" / "java" / "example" / "dormant" / "Outside.java"
    os.symlink(external, linked)
    unsafe, unsafe_report = _scan(SKILL, host, name="unsafe")
    assert unsafe.returncode == 0, unsafe.stdout + unsafe.stderr
    unsafe_payload = _payload(unsafe_report)
    assert unsafe_payload["status"] == "unsupported"
    assert unsafe_payload["failure_kind"] == "unsafe_source"
