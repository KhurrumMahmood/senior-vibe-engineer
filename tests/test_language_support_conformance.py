"""Read-only copied-closure conformance for the documented omnibus journey."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping

import pytest

from tests.support.portability_journey import (
    JourneyContext,
    JourneyObservation,
    JourneyResult,
    NativeCheck,
    SyntaxFailure,
    ToolMissing,
    run_read_only_journey,
)


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "find-omnibus"
BASELINE = json.loads(
    (ROOT / ".claude" / "tasks" / "p3-baseline" / "find-omnibus-baseline.json").read_text(
        encoding="utf-8"
    )
)
TYPESCRIPT_FIXTURE = ROOT / "tests" / "fixtures" / "b4_typescript_omnibus"
JAVA_FIXTURE = ROOT / "tests" / "fixtures" / "find-omnibus-java"
FINAL_ARTIFACTS = (
    "omnibus.jsonl",
    "scan.json",
    "candidates.jsonl",
    "report.md",
    "findings.json",
)
TYPESCRIPT_FINAL_ARTIFACTS = tuple(name for name in FINAL_ARTIFACTS if name != "scan.json")
TERMINAL_OUTCOMES = frozenset(
    {
        "complete",
        "partial",
        "unsupported",
        "tool-missing",
        "syntax-error",
        "native-check-failure",
        "unexpected-source-mutation",
    }
)
P3_ALLOWED_SKILL_CHANGES = frozenset(
    {
        "SKILL.md",
        "scripts/detect.py",
        "scripts/detect_swift_symbols.py",
        "scripts/report.py",
    }
)
POST_P3_ADDITIVE_FILES = frozenset(
    {
        "scripts/detect_swift_symbols.py",
        "scripts/run_c.py",
        "scripts/run_cpp.py",
        "scripts/run_dart.py",
        "scripts/run_php.py",
        "scripts/run_ruby.py",
        "scripts/run_rust.py",
    }
)


def _run(
    argv: tuple[str, ...], *, cwd: Path, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _manifest(root: Path, paths: list[str]) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for relative in sorted(paths):
        content = (root / relative).read_bytes()
        total += len(content)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), total


def _assert_frozen_tree(root: Path, baseline: Mapping[str, object]) -> None:
    rows = baseline["files"]
    assert isinstance(rows, list)
    paths = [row["path"] for row in rows]
    current_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert current_paths - set(paths) == POST_P3_ADDITIVE_FILES
    assert set(paths) <= current_paths
    for row in rows:
        relative = row["path"]
        content = (root / relative).read_bytes()
        if relative not in P3_ALLOWED_SKILL_CHANGES:
            assert hashlib.sha256(content).hexdigest() == row["sha256"]
    for relative in P3_ALLOWED_SKILL_CHANGES:
        assert (root / relative).read_bytes() == (SKILL / relative).read_bytes()


def _assert_frozen_fixture(host: Path, language: str) -> None:
    baseline = BASELINE["fixtures"][language]
    assert isinstance(baseline, dict)
    paths = baseline["files"]
    assert isinstance(paths, list)
    assert {
        path.relative_to(host).as_posix()
        for path in host.rglob("*")
        if path.is_file()
    } == set(paths)
    actual, total = _manifest(host, paths)
    assert actual == baseline["manifest_sha256"]
    assert total == baseline["total_bytes"]


def _host_python(host: Path) -> Path:
    python = host / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(Path(sys.executable))
    return python


def _typescript_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(TYPESCRIPT_FIXTURE, host)
    _assert_frozen_fixture(host, "typescript")
    _host_python(host)
    installed = _run(("npm", "ci", "--offline", "--ignore-scripts"), cwd=host)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return host


def _java_host(tmp_path: Path) -> Path:
    javac = shutil.which("javac")
    if javac is None:
        pytest.skip("JDK 17 compiler is unavailable")
    try:
        version = subprocess.run(
            (javac, "-version"),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("JDK compiler version probe timed out")
    rendered = version.stdout + version.stderr
    if version.returncode != 0 or not any(
        f" {major}." in rendered for major in range(17, 100)
    ):
        pytest.skip("JDK 17 or newer compiler is unavailable")
    host = tmp_path / "host"
    shutil.copytree(JAVA_FIXTURE, host)
    _assert_frozen_fixture(host, "java")
    _host_python(host)
    return host


def _java_env(*, path: str | None = None) -> dict[str, str]:
    javac = shutil.which("javac")
    system_path = str(Path(javac).parent) if javac is not None else ""
    java_home = os.environ.get("JAVA_HOME")
    if java_home is None and javac is not None:
        java_home = str(Path(javac).resolve().parent.parent)
    return {
        **os.environ,
        "PATH": path if path is not None else f"{system_path}{os.pathsep}{os.environ.get('PATH', '')}",
        "JAVA_HOME": java_home or "",
    }


def _copied_library(tmp_path: Path, host: Path) -> tuple[Path, dict[str, object]]:
    """Copy exactly the skill plus the declared shared inventory closure."""
    library = tmp_path / "on-demand-library"
    copied_skill = library / ".claude" / "skills" / "find-omnibus"
    ignore_bytecode = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(SKILL, copied_skill, ignore=ignore_bytecode)
    shared = library / "scripts"
    shared.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "source_inventory.py", shared / "source_inventory.py")
    shutil.copytree(ROOT / "scripts" / "language_profiles", shared / "language_profiles")
    (shared / "_lib").mkdir()
    shutil.copy2(ROOT / "scripts" / "_lib" / "__init__.py", shared / "_lib" / "__init__.py")
    shutil.copytree(
        ROOT / "scripts" / "_lib" / "language_support",
        shared / "_lib" / "language_support",
        ignore=ignore_bytecode,
    )
    linked = host / ".agents" / "skills" / "find-omnibus"
    linked.parent.mkdir(parents=True)
    linked.symlink_to(copied_skill, target_is_directory=True)
    return library, {
        "mode": "on_demand_library",
        "available": True,
        "library_root": str(library),
        "skills": ["find-omnibus"],
        "guides": [
            {
                "skill": "find-omnibus",
                "skill_root": str(copied_skill),
                "guide": str(copied_skill / "SKILL.md"),
                "bundled_tooling": str(copied_skill / "scripts"),
            }
        ],
        "shared_tooling": str(shared),
        "source_inventory_tool": str(shared / "source_inventory.py"),
    }


def _documented_block(skill: Path, stage: str) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    start = f"<!-- installed-command:{stage}:start -->"
    end = f"<!-- installed-command:{stage}:end -->"
    return text.split(start, 1)[1].split(end, 1)[0]


def _assert_documented_stage_shape(skill: Path) -> None:
    setup = _documented_block(skill, "setup")
    detect = _documented_block(skill, "detect")
    collapse = _documented_block(skill, "collapse")
    report = _documented_block(skill, "report")
    assert 'REPORT_DIR="reports/omnibus/scan-${TS}"' in setup
    assert 'ln -sfn "scan-${TS}" reports/omnibus/latest' in setup
    assert '"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/detect.py"' in detect
    assert '--target "${TARGET}"' in detect
    assert '--project-root "$(pwd)"' in detect
    assert '"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/collapse.py"' in collapse
    assert "--top 30" in collapse
    assert '"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/report.py"' in report
    assert '--scan-id "$(basename "${REPORT_DIR}")"' in report


def _setup_documented_destination(host: Path, report_dir: Path) -> None:
    destination = host / report_dir
    (destination / "scout").mkdir(parents=True, exist_ok=True)
    latest = host / "reports" / "omnibus" / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(report_dir.name)


def _documented_argv(
    *,
    host: Path,
    skill: Path,
    target: str,
    report_dir: Path,
) -> dict[str, tuple[str, ...]]:
    """Expand the documented executable stages without invoking a command shell."""
    prefix = str(report_dir)
    return {
        "detect": (
            str(host / ".venv" / "bin" / "python"),
            str(skill / "scripts" / "detect.py"),
            "--target",
            target,
            "--project-root",
            str(host),
            "--output",
            f"{prefix}/omnibus.jsonl",
        ),
        "collapse": (
            str(host / ".venv" / "bin" / "python"),
            str(skill / "scripts" / "collapse.py"),
            "--detections",
            f"{prefix}/omnibus.jsonl",
            "--output",
            f"{prefix}/candidates.jsonl",
            "--top",
            "30",
        ),
        "report": (
            str(host / ".venv" / "bin" / "python"),
            str(skill / "scripts" / "report.py"),
            "--candidates",
            f"{prefix}/candidates.jsonl",
            "--scout-dir",
            f"{prefix}/scout",
            "--output-md",
            f"{prefix}/report.md",
            "--output-json",
            f"{prefix}/findings.json",
            "--scan-id",
            report_dir.name,
            "--target",
            target,
        ),
    }


def _write_scouts(candidates: Path, scout_dir: Path) -> None:
    scout_dir.mkdir(parents=True, exist_ok=True)
    for candidate in _records(candidates):
        (scout_dir / f"{candidate['candidate_id']}.json").write_text(
            json.dumps(
                {
                    "candidate_id": candidate["candidate_id"],
                    "file": candidate["file"],
                    "bucket": "confirmed_omnibus",
                    "domains_confirmed": ["invoice", "shipment", "customer", "inventory"],
                    "facets_collapsed": [],
                    "srp_rewrite": "The fixture has four independent record domains.",
                    "decomposition_sketch": [],
                    "decomposition_depth_note": "Each domain has a separate public surface.",
                    "false_positive_reason": None,
                    "notes": "P3 read-only conformance fixture.",
                    "recommendation": "decompose",
                }
            ),
            encoding="utf-8",
        )


def _run_documented_pipeline(
    context: JourneyContext,
    *,
    target: str,
    report_dir: Path,
    env: Mapping[str, str] | None,
) -> JourneyObservation:
    _assert_documented_stage_shape(context.guides[0].parent)
    _setup_documented_destination(context.project_root, report_dir)
    commands = _documented_argv(
        host=context.project_root,
        skill=context.guides[0].parent,
        target=target,
        report_dir=report_dir,
    )
    detected = _run(commands["detect"], cwd=context.project_root, env=env)
    destination = context.project_root / report_dir
    scan = destination / "scan.json"
    if detected.returncode:
        detail = detected.stderr.strip() or detected.stdout.strip()
        if scan.is_file() and json.loads(scan.read_text(encoding="utf-8"))["status"] == "unsupported":
            collapsed = _run(commands["collapse"], cwd=context.project_root, env=env)
            assert collapsed.returncode == 0, collapsed.stdout + collapsed.stderr
            rendered = _run(commands["report"], cwd=context.project_root, env=env)
            assert rendered.returncode == 0, rendered.stdout + rendered.stderr
            payload = json.loads((destination / "findings.json").read_text(encoding="utf-8"))
            assert payload["status"] == "unsupported"
            return JourneyObservation("unsupported", "documented unsupported final artifact")
        if "syntax error" in detail.lower():
            raise SyntaxFailure(detail)
        if "JDK is unavailable" in detail or "JDK >= 17.0.0" in detail:
            raise ToolMissing(detail)
        raise AssertionError(detail)

    collapsed = _run(commands["collapse"], cwd=context.project_root, env=env)
    assert collapsed.returncode == 0, collapsed.stdout + collapsed.stderr
    _write_scouts(destination / "candidates.jsonl", destination / "scout")
    rendered = _run(commands["report"], cwd=context.project_root, env=env)
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert (destination / "findings.json").is_file()
    return JourneyObservation("complete", "documented final artifact")


def _journey(
    *,
    host: Path,
    handoff: Mapping[str, object],
    target: str,
    env: Mapping[str, str] | None,
    native_checks: tuple[NativeCheck, ...] = (),
    artifact_names: tuple[str, ...] = FINAL_ARTIFACTS,
) -> JourneyResult:
    report_dir = Path("reports") / "omnibus" / "scan-20260721-000000"
    return run_read_only_journey(
        project_root=host,
        handoff=handoff,
        closure=lambda context: _run_documented_pipeline(
            context,
            target=target,
            report_dir=report_dir,
            env=env,
        ),
        native_checks=native_checks,
        artifact_paths=tuple(host / report_dir / name for name in artifact_names),
    )


def _assert_read_only(result: JourneyResult) -> None:
    assert result.outcome in TERMINAL_OUTCOMES
    assert result.source_changes == ()
    assert result.source_digests["before"] == result.source_digests["after_closure"]
    assert result.source_digests["after_closure"] == result.source_digests["after_native"]


def _assert_copied_closure(
    result: JourneyResult,
    library: Path,
    host: Path,
) -> None:
    skill_baseline = BASELINE["skill_tree"]
    assert isinstance(skill_baseline, dict)
    _assert_frozen_tree(library / ".claude" / "skills" / "find-omnibus", skill_baseline)
    assert all(path.is_relative_to(library) for path in result.absolute_closure_paths)
    assert all(not path.is_relative_to(ROOT) for path in result.absolute_closure_paths)
    isolated = _run(
        (
            str(host / ".venv" / "bin" / "python"),
            "-I",
            "-S",
            str(library / "scripts" / "source_inventory.py"),
            "--project-root",
            str(host),
        ),
        cwd=host,
    )
    assert isolated.returncode == 0, isolated.stdout + isolated.stderr


def _artifact_values(result: JourneyResult, stage: str) -> set[str | None]:
    return set(result.artifact_hashes[stage].values())


def test_typescript_documented_copied_closure_reaches_final_artifact_and_recovers(
    tmp_path: Path,
) -> None:
    host = _typescript_host(tmp_path)
    library, handoff = _copied_library(tmp_path, host)
    native_checks = (NativeCheck("typescript-typecheck", ("npm", "run", "typecheck")),)

    positive = _journey(
        host=host,
        handoff=handoff,
        target="src",
        env=None,
        native_checks=native_checks,
        artifact_names=TYPESCRIPT_FINAL_ARTIFACTS,
    )

    _assert_read_only(positive)
    _assert_copied_closure(positive, library, host)
    assert positive.outcome == "complete"
    assert [check.status for check in positive.native_results] == ["passed"]
    report_dir = host / "reports" / "omnibus" / "scan-20260721-000000"
    assert {record["file"] for record in _records(report_dir / "omnibus.jsonl")} == {
        "src/omnibus.ts",
        "src/omnibus.tsx",
    }
    findings = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    assert findings["summary"]["bucket_counts"]["confirmed_omnibus"] == 2

    broken = host / "src" / "broken.ts"
    broken.write_text("export function broken(: string { return ''; }\n", encoding="utf-8")
    failed = _journey(
        host=host,
        handoff=handoff,
        target="src",
        env=None,
        artifact_names=TYPESCRIPT_FINAL_ARTIFACTS,
    )
    _assert_read_only(failed)
    assert failed.outcome == "syntax-error"

    broken.unlink()
    recovered = _journey(
        host=host,
        handoff=handoff,
        target="src",
        env=None,
        native_checks=native_checks,
        artifact_names=TYPESCRIPT_FINAL_ARTIFACTS,
    )
    _assert_read_only(recovered)
    assert recovered.outcome == "complete"
    assert all(value is not None for value in recovered.artifact_hashes["after_native"].values())


def test_typescript_valid_to_failed_same_destination_clears_final_artifacts(
    tmp_path: Path,
) -> None:
    host = _typescript_host(tmp_path)
    _, handoff = _copied_library(tmp_path, host)
    positive = _journey(
        host=host,
        handoff=handoff,
        target="src",
        env=None,
        artifact_names=TYPESCRIPT_FINAL_ARTIFACTS,
    )
    assert positive.outcome == "complete"
    broken = host / "src" / "broken.ts"
    broken.write_text("export function broken(: string { return ''; }\n", encoding="utf-8")

    failed = _journey(
        host=host,
        handoff=handoff,
        target="src",
        env=None,
        artifact_names=TYPESCRIPT_FINAL_ARTIFACTS,
    )

    _assert_read_only(failed)
    assert failed.outcome == "syntax-error"
    assert _artifact_values(failed, "after_closure") == {None}


def test_java_documented_copied_closure_handles_both_same_destination_transitions(
    tmp_path: Path,
) -> None:
    host = _java_host(tmp_path)
    library, handoff = _copied_library(tmp_path, host)
    sources = tuple(
        path.relative_to(host).as_posix()
        for path in sorted(host.rglob("*.java"))
    )
    native_checks = (
        NativeCheck(
            "java-compile",
            ("javac", "--release", "17", "-d", "reports/omnibus/native-classes", *sources),
        ),
    )

    positive = _journey(
        host=host,
        handoff=handoff,
        target="src",
        env=_java_env(),
        native_checks=native_checks,
    )

    _assert_read_only(positive)
    _assert_copied_closure(positive, library, host)
    assert positive.outcome == "complete"
    report_dir = host / "reports" / "omnibus" / "scan-20260721-000000"
    assert [record["file"] for record in _records(report_dir / "omnibus.jsonl")] == [
        "src/main/java/example/OmnibusService.java"
    ]
    assert json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))["status"] == "complete"

    broken = host / "src" / "main" / "java" / "example" / "Broken.java"
    broken.write_text("package example; class Broken { void bad( { } }\n", encoding="utf-8")
    failed = _journey(host=host, handoff=handoff, target="src", env=_java_env())

    _assert_read_only(failed)
    assert failed.outcome == "syntax-error"
    assert _artifact_values(failed, "after_closure") == {None}
    assert not (report_dir / "scout").exists()

    broken.unlink()
    recovered = _journey(
        host=host,
        handoff=handoff,
        target="src",
        env=_java_env(),
        native_checks=native_checks,
    )
    _assert_read_only(recovered)
    assert recovered.outcome == "complete"
    assert _artifact_values(recovered, "before") == {None}
    assert all(value is not None for value in recovered.artifact_hashes["after_native"].values())


def test_java_documented_empty_target_reaches_unsupported_final_artifact(tmp_path: Path) -> None:
    host = _java_host(tmp_path)
    _, handoff = _copied_library(tmp_path, host)
    (host / "empty").mkdir()

    result = _journey(host=host, handoff=handoff, target="empty", env=_java_env())

    _assert_read_only(result)
    assert result.outcome == "unsupported"
    report_dir = host / "reports" / "omnibus" / "scan-20260721-000000"
    findings = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    assert findings["status"] == "unsupported"
    assert json.loads((report_dir / "scan.json").read_text(encoding="utf-8"))["failure_kind"] == "no-java-files"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("", "JDK is unavailable"),
        ("fake", "JDK >= 17.0.0"),
    ],
)
def test_java_missing_and_old_tool_failures_are_distinct_terminal_outcomes(
    tmp_path: Path,
    path: str,
    expected: str,
) -> None:
    host = _java_host(tmp_path)
    _, handoff = _copied_library(tmp_path, host)
    tool_path = path
    if path == "fake":
        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        for name, version in (("java", 'openjdk version "11.0.22"'), ("javac", "javac 11.0.22")):
            executable = fake_bin / name
            executable.write_text(f"#!/bin/sh\necho '{version}' >&2\n", encoding="utf-8")
            executable.chmod(0o755)
        tool_path = str(fake_bin)

    result = _journey(host=host, handoff=handoff, target="src", env=_java_env(path=tool_path))

    _assert_read_only(result)
    assert result.outcome == "tool-missing"
    assert result.failure is not None
    assert expected in result.failure
