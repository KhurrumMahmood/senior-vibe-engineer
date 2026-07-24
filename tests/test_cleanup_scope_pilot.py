"""End-to-end scope-mode pilot for which-cleanup and find-comment-drift."""
from __future__ import annotations

import argparse
import json
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER_SOURCE = ROOT / ".claude" / "skills" / "which-cleanup"
REPOSITORY_ROUTER = ROUTER_SOURCE / "scripts" / "run.py"
DETECTOR = ROOT / ".claude" / "skills" / "find-comment-drift" / "scripts" / "detect.py"


def _run(*command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), cwd=cwd, check=False, capture_output=True, text=True
    )


def _git(repo: Path, *args: str) -> str:
    result = _run("git", *args, cwd=repo)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "Scope Pilot")
    _git(repo, "config", "user.email", "scope@example.invalid")


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _route(router: Path, host: Path, mode: str, *scope_args: str) -> dict:
    result = _run(
        sys.executable,
        "-I",
        "-S",
        str(router / "scripts" / "route.py"),
        *scope_args,
        "--scope-mode",
        mode,
        "--project-root",
        str(host),
        "--library-root",
        str(ROOT),
        "--json",
        cwd=host,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _detect(host: Path, request: dict, output: Path) -> tuple[list[dict], dict]:
    request_path = output.with_name(f"{output.stem}-request.json")
    request_path.write_text(json.dumps(request), encoding="utf-8")
    result = _run(
        sys.executable,
        "-I",
        "-S",
        str(DETECTOR),
        "--project-root",
        str(host),
        "--scan-request",
        str(request_path),
        "--output",
        str(output),
        cwd=host,
    )
    assert result.returncode == 0, result.stderr
    findings = [json.loads(line) for line in output.read_text().splitlines()]
    scope = json.loads(output.with_name(f"{output.stem}-scope.json").read_text())
    return findings, scope


def _load_detector():
    scripts = DETECTOR.parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("comment_drift_scope_pilot", DETECTOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_router_module():
    scripts = ROUTER_SOURCE / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    route_path = scripts / "route.py"
    spec = importlib.util.spec_from_file_location("cleanup_scope_pilot_router", route_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_installed_router_and_comment_scanner_distinguish_hunks_from_files(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    _init_repo(host)
    original = [
        "value = 1",
        "# SiteConfig pre-existing wording",
        "",
        "def keep():",
        "    return value",
        "",
        "def changed():",
        "    return value",
    ]
    _write(host / "src" / "app.py", original)
    (host / ".gitignore").write_text(".agents/\n", encoding="utf-8")
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    changed = [*original]
    changed[7] = "    return value  # SiteConfig newly changed wording"
    _write(host / "src" / "app.py", changed)
    for index in range(5):
        _write(host / "src" / f"extra_{index}.py", [f"value_{index} = {index}"])

    installed_router = host / ".agents" / "skills" / "which-cleanup"
    installed_router.parent.mkdir(parents=True)
    shutil.copytree(ROUTER_SOURCE, installed_router)

    line_payload = _route(installed_router, host, "diff-lines")
    comment = next(
        row
        for row in line_payload["recommendations"]
        if row["skill"] == "find-comment-drift"
    )
    assert line_payload["scan_request"]["selector"] == {"kind": "working-tree"}
    assert len(line_payload["scan_request"]["resolved_paths"]) == 6
    assert "src/app.py" in line_payload["scan_request"]["resolved_paths"]
    assert comment["scan"]["effective_mode"] == "diff-lines"
    assert comment["scan"]["diff_semantics"] == "filter-findings"

    line_findings, line_scope = _detect(
        host, line_payload["scan_request"], tmp_path / "line-findings.jsonl"
    )
    assert [(row["file"], row["lineno"]) for row in line_findings] == [
        ("src/app.py", 8)
    ]
    assert line_scope == {
        "analyzed_file_count": 6,
        "effective_mode": "diff-lines",
        "error_count": 0,
        "incomplete_or_error_count": 0,
        "raw_finding_count": 2,
        "requested_mode": "diff-lines",
        "scope_filtered_count": 1,
        "selector": {"kind": "working-tree"},
    }

    file_payload = _route(installed_router, host, "changed-files")
    file_findings, file_scope = _detect(
        host, file_payload["scan_request"], tmp_path / "file-findings.jsonl"
    )
    assert [(row["file"], row["lineno"]) for row in file_findings] == [
        ("src/app.py", 2),
        ("src/app.py", 8),
    ]
    assert file_scope["raw_finding_count"] == 2
    assert file_scope["scope_filtered_count"] == 0
    assert file_scope["effective_mode"] == "changed-files"

    scans = {row["skill"]: row["scan"] for row in line_payload["recommendations"]}
    assert scans["find-test-obligation-drift"]["effective_mode"] == "changed-files"
    assert scans["find-test-obligation-drift"]["status"] == "widened"
    assert scans["find-duplication"]["effective_mode"] == "paths"
    assert scans["find-duplication"]["status"] == "widened"
    assert scans["find-omnibus"]["effective_mode"] == "paths"

    repository_result = _run(
        sys.executable,
        str(REPOSITORY_ROUTER),
        "--scope-mode",
        "diff-lines",
        "--project-root",
        str(host),
        "--reports-dir",
        str(tmp_path / "reports"),
        "--skip-effectiveness-log",
        "--json",
        cwd=host,
    )
    assert repository_result.returncode == 0, repository_result.stderr
    repository_payload = json.loads(repository_result.stdout)
    repository_comment = next(
        row
        for bucket in repository_payload["checklist"].values()
        for row in bucket
        if row["skill"] == "find-comment-drift"
    )
    assert repository_payload["scan_request"] == line_payload["scan_request"]
    assert repository_comment["scan"]["effective_mode"] == "diff-lines"


def test_multiline_finding_intersects_any_changed_line() -> None:
    detector = _load_detector()
    finding = detector.Finding(
        pattern="multiline",
        file="src/app.py",
        lineno=2,
        end_lineno=4,
        summary="spans a changed line",
        recommendation="review it",
    )
    request = {
        "changes": [
            {
                "path": "src/app.py",
                "line_ranges": [{"start": 4, "end": 4}],
            }
        ]
    }

    assert detector._filter_findings_to_changed_lines([finding], request) == [finding]


def test_staged_content_drift_degrades_line_filter_explicitly(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _init_repo(host)
    (host / ".gitignore").write_text(".agents/\n", encoding="utf-8")
    _write(host / "app.py", ["before"])
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    _write(host / "app.py", ["staged"])
    _git(host, "add", "app.py")
    _write(host / "app.py", ["unstaged", "staged"])

    installed_router = host / ".agents" / "skills" / "which-cleanup"
    installed_router.parent.mkdir(parents=True)
    shutil.copytree(ROUTER_SOURCE, installed_router)
    payload = _route(installed_router, host, "diff-lines", "--staged")
    comment = next(
        row
        for row in payload["recommendations"]
        if row["skill"] == "find-comment-drift"
    )

    assert payload["scan_request"]["line_filter_safe"] is False
    assert comment["scan"] == {
        "adapter": "line-filter",
        "diff_semantics": "filter-findings",
        "effective_mode": "changed-files",
        "reason": "content_basis_mismatch",
        "requested_mode": "diff-lines",
        "selector": {"kind": "staged"},
        "status": "degraded",
    }


def test_router_resolves_scope_once_for_all_recommendations(
    tmp_path: Path, monkeypatch
) -> None:
    host = tmp_path / "host"
    _init_repo(host)
    _write(host / "app.py", ["before"])
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    _write(host / "app.py", ["after"])
    router = _load_router_module()
    real_builder = router.build_scan_request
    calls = 0

    def counted_builder(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_builder(*args, **kwargs)

    monkeypatch.setattr(router, "build_scan_request", counted_builder)
    result = router.build_result(
        argparse.Namespace(
            paths=[],
            staged=False,
            changed_from=None,
            commit=None,
            range=None,
            scope_mode="diff-lines",
            project_root=host,
            library_root=ROOT,
            source=router.DEFAULT_SOURCE,
            skills_cli_version=router.DEFAULT_CLI_VERSION,
            agent="codex",
            json=True,
        )
    )

    assert calls == 1
    assert len(result["recommendations"]) >= 3
    assert {
        json.dumps(item["scan"]["selector"], sort_keys=True)
        for item in result["recommendations"]
    } == {json.dumps(result["scan_request"]["selector"], sort_keys=True)}


def test_deletion_only_change_retains_file_level_closeout_obligation(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    _init_repo(host)
    _write(host / "removed.py", ["value = 1"])
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    (host / "removed.py").unlink()

    result = _run(
        sys.executable,
        str(REPOSITORY_ROUTER),
        "--scope-mode",
        "diff-lines",
        "--project-root",
        str(host),
        "--reports-dir",
        str(tmp_path / "reports"),
        "--skip-effectiveness-log",
        "--json",
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["resolved_paths"] == []
    assert payload["scan_request"]["changes"][0]["change_type"] == "deleted"
    test_obligation = next(
        row
        for bucket in payload["checklist"].values()
        for row in bucket
        if row["skill"] == "find-test-obligation-drift"
    )
    assert test_obligation["scan"]["effective_mode"] == "changed-files"
    assert test_obligation["scan"]["status"] == "widened"


def test_help_describes_scope_without_running_a_scan(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    router_help = _run(
        sys.executable,
        "-I",
        "-S",
        str(ROUTER_SOURCE / "scripts" / "route.py"),
        "--help",
        cwd=host,
    )
    detector_help = _run(
        sys.executable,
        "-I",
        "-S",
        str(DETECTOR),
        "--help",
        cwd=host,
    )

    assert router_help.returncode == detector_help.returncode == 0
    normalized_help = " ".join(router_help.stdout.split())
    assert "diff-lines" in normalized_help
    assert "changed-files" in normalized_help
    assert "reports only findings intersecting changed lines" in normalized_help
    assert "analyzes selected files in full" in normalized_help
    assert not list(host.iterdir())


def test_scanner_rejects_tampered_request_path_outside_project(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_root": str(host),
                "requested_mode": "changed-files",
                "selector": {"kind": "working-tree"},
                "resolved_paths": ["../outside.py"],
                "changes": [
                    {
                        "path": "../outside.py",
                        "line_ranges": [{"start": 1, "end": 1}],
                    }
                ],
                "line_filter_safe": True,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "findings.jsonl"

    result = _run(
        sys.executable,
        "-I",
        "-S",
        str(DETECTOR),
        "--project-root",
        str(host),
        "--scan-request",
        str(request_path),
        "--output",
        str(output),
        cwd=host,
    )

    assert result.returncode == 2
    assert "outside the project root" in result.stderr
    assert not output.exists()
