"""Go find-incomplete-sweep manifest, handoff, and copied-skill proof."""
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
SKILL = ROOT / ".claude" / "skills" / "find-incomplete-sweep"
FIXTURE = ROOT / "tests" / "fixtures" / "find-incomplete-sweep-go" / "host"
PYTHON = Path(sys.executable)


def _go() -> Path:
    executable = shutil.which("go")
    if executable is None:
        pytest.skip("Go toolchain is unavailable")
    return Path(executable)


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _env(tmp_path: Path) -> dict[str, str]:
    go = _go()
    return {
        **os.environ,
        "PATH": f"{go.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GOCACHE": str(tmp_path / "go-cache"),
        "GOTOOLCHAIN": "local",
    }


def _prepare_git_trajectory(host: Path) -> None:
    calls = host / "requests.go"
    current = calls.read_text(encoding="utf-8")
    initial = current.replace(" // swept", "")
    assert initial != current
    calls.write_text(initial, encoding="utf-8")
    assert _run("git", "init", cwd=host, env=os.environ.copy()).returncode == 0
    assert _run("git", "config", "user.email", "fixture@example.test", cwd=host, env=os.environ.copy()).returncode == 0
    assert _run("git", "config", "user.name", "Fixture", cwd=host, env=os.environ.copy()).returncode == 0
    assert _run("git", "add", ".", cwd=host, env=os.environ.copy()).returncode == 0
    first = _run(
        "git", "commit", "-m", "old request shapes", cwd=host,
        env={**os.environ, "GIT_AUTHOR_DATE": "2025-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2025-01-01T00:00:00Z"},
    )
    assert first.returncode == 0, first.stdout + first.stderr
    calls.write_text(current, encoding="utf-8")
    assert _run("git", "add", "requests.go", cwd=host, env=os.environ.copy()).returncode == 0
    second = _run(
        "git", "commit", "-m", "sweep request region", cwd=host,
        env={**os.environ, "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"},
    )
    assert second.returncode == 0, second.stdout + second.stderr


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env(tmp_path)
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    _prepare_git_trajectory(host)
    return host, env


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.go"))
        if "reports" not in path.relative_to(host).parts and not path.is_symlink()
    }


def _runtime_fingerprint(skill: Path) -> str:
    digest = hashlib.sha256()
    for name in ("detect_go_incomplete_sweep.py", "detect_go_incomplete_sweep.go"):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update((skill / "scripts" / name).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _scan(
    skill: Path,
    host: Path,
    env: dict[str, str],
    *,
    name: str = "go",
    target: str = ".",
    go_executable: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    report = host / "reports" / "find-incomplete-sweep" / name
    args = [
        str(PYTHON), str(skill / "scripts" / "detect_go_incomplete_sweep.py"),
        "--target", target,
        "--project-root", str(host),
        "--report-dir", str(report),
    ]
    if go_executable is not None:
        args.extend(("--go-executable", go_executable))
    return _run(*args, cwd=host, env=env), report


def _triage(skill: Path, report: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    packets = json.loads((report / "scout_packets.json").read_text(encoding="utf-8"))
    assert packets["packet_count"] == 1
    (report / "scout_verdicts.json").write_text(json.dumps({"verdicts": [{
        "id": packets["packets"][0]["id"],
        "verdict": "forgotten",
        "rationale": "Three later edits consistently carry the region option.",
        "completion": 'add `Region: "us"` to the RequestOptions literal',
    }]}), encoding="utf-8")
    return _run(str(PYTHON), str(skill / "scripts" / "triage.py"), "--scan-dir", str(report), cwd=report, env=env)


def test_go_resolved_candidate_reaches_manifest_packet_and_triage(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _source_hashes(host)
    result, report = _scan(SKILL, host, env)

    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((report / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["language"] == "go"
    assert manifest["analyzer"] == "go-list-go-parser-go-types"
    assert manifest["status"] == "complete"
    assert manifest["source_fingerprint"].startswith("sha256:")
    assert manifest["findings"] == [{
        "callee": "example.com/incomplete-sweep-fixture.BuildRequest",
        "kwarg": "Region",
        "option_position": 1,
        "group_size": 4,
        "present_count": 3,
        "majority_frac": 0.75,
        "straggler": "requests.go:30",
        "present_sites": [
            {"file": "requests.go", "line": 27},
            {"file": "requests.go", "line": 28},
            {"file": "requests.go", "line": 29},
        ],
        "gated_in": True,
        "value": "string:us",
        "trajectory": "3/3 option-present sites touched AFTER the straggler — consistent with a sweep that missed it",
    }]
    assert {item["reason"] for item in manifest["deferred"]} >= {
        "inconsistent_option_field_value",
        "ambiguous_multiple_stragglers",
        "method_or_interface_call",
        "function_value_call",
    }
    assert _source_hashes(host) == before

    scout = _run(str(PYTHON), str(SKILL / "scripts" / "scout.py"), "--scan-dir", str(report), "--project-root", str(host), cwd=host, env=env)
    assert scout.returncode == 0, scout.stdout + scout.stderr
    packets = json.loads((report / "scout_packets.json").read_text(encoding="utf-8"))
    assert packets["language"] == "go"
    assert packets["packet_count"] == 1
    assert len(packets["packets"][0]["present_sites"]) == 2

    triage = _triage(SKILL, report, env)
    assert triage.returncode == 0, triage.stdout + triage.stderr
    assert "## Forgotten (1)" in (report / "triaged.md").read_text(encoding="utf-8")
    assert _source_hashes(host) == before


def test_go_failure_modes_and_inactive_build_are_explicit(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    (host / "broken.go").write_text("package sweepfixture\nfunc broken( {\n", encoding="utf-8")
    malformed, report = _scan(SKILL, host, env, name="malformed")
    assert malformed.returncode == 2
    assert "failed" in malformed.stderr
    assert not report.exists()
    (host / "broken.go").unlink()

    missing, report = _scan(SKILL, host, env, name="missing", go_executable=str(tmp_path / "missing-go"))
    assert missing.returncode == 2
    assert "unsupported" in missing.stderr
    assert not report.exists()

    old = tmp_path / "old-go"
    old.write_text("#!/bin/sh\necho 'go version go1.21.9 fixture'\n", encoding="utf-8")
    old.chmod(0o755)
    unsupported, report = _scan(SKILL, host, env, name="old", go_executable=str(old))
    assert unsupported.returncode == 2
    assert "unsupported" in unsupported.stderr
    assert not report.exists()

    (host / "inactive.go").write_text(
        "//go:build never\n\npackage sweepfixture\n\n"
        "var inactive = BuildRequest(\"inactive\", RequestOptions{ID: \"inactive\", Region: \"us\"})\n",
        encoding="utf-8",
    )
    partial, report = _scan(SKILL, host, env, name="partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    manifest = json.loads((report / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["project_resolution"]["inactive_files"] == ["inactive.go"]


def test_go_target_isolated_from_unrelated_broken_package(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    unrelated = host / "unrelated"
    unrelated.mkdir()
    (unrelated / "broken.go").write_text(
        "package unrelated\nfunc broken( {\n",
        encoding="utf-8",
    )

    result, report = _scan(SKILL, host, env, name="isolated", target="requests.go")

    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((report / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert len(manifest["findings"]) == 1


def test_go_withholds_candidates_when_git_evidence_is_insufficient_or_failed(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    shutil.rmtree(host / ".git")
    insufficient, report = _scan(SKILL, host, env, name="no-git")
    assert insufficient.returncode == 0, insufficient.stdout + insufficient.stderr
    payload = json.loads((report / "manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["project_resolution"]["git_evidence"] == "insufficient"
    assert payload["findings"] == []
    assert "insufficient_git_evidence" in {item["reason"] for item in payload["deferred"]}

    host, env = _host(tmp_path / "failed")
    shim_dir = tmp_path / "failed-git"
    shim_dir.mkdir()
    shim = shim_dir / "git"
    shim.write_text(
        "#!/bin/sh\nif [ \"$1\" = rev-parse ]; then echo true; exit 0; fi\nexit 1\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    failed, report = _scan(
        SKILL, host, {**env, "PATH": f"{shim_dir}{os.pathsep}{_go().parent}"}, name="failed-git",
    )
    assert failed.returncode == 0, failed.stdout + failed.stderr
    payload = json.loads((report / "manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["project_resolution"]["git_evidence"] == "failed"
    assert payload["findings"] == []
    assert "failed_git_evidence" in {item["reason"] for item in payload["deferred"]}


def test_go_containment_copied_closure_and_source_fingerprint(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _source_hashes(host)
    os.symlink(host / "requests.go", host / "linked.go")
    linked, report = _scan(SKILL, host, env, name="linked", target="linked.go")
    assert linked.returncode == 2
    assert "symbolic link" in linked.stderr
    assert not report.exists()

    broken_link = host / "broken-link.go"
    os.symlink(host / "absent.go", broken_link)
    broken, report = _scan(SKILL, host, env, name="broken-link", target="broken-link.go")
    assert broken.returncode == 2
    assert "symbolic link" in broken.stderr
    assert not report.exists()

    reports = host / "reports" / "find-incomplete-sweep"
    reports.mkdir(parents=True)
    os.symlink(host, reports / "linked-report")
    unsafe, _ = _scan(SKILL, host, env, name="linked-report/scan")
    assert unsafe.returncode == 2
    assert "symbolic link" in unsafe.stderr
    (reports / "linked-report").unlink()

    copied = tmp_path / "on-demand" / "find-incomplete-sweep"
    shutil.copytree(SKILL, copied)
    copied_result, copied_report = _scan(copied, host, env, name="copied")
    assert copied_result.returncode == 0, copied_result.stdout + copied_result.stderr
    copied_manifest = json.loads((copied_report / "manifest.json").read_text(encoding="utf-8"))
    assert copied_manifest["source_fingerprint"] == _runtime_fingerprint(copied)
    assert (copied / "scripts" / "detect_go_incomplete_sweep.go").is_file()
    runtime = "\n".join(path.read_text(encoding="utf-8") for path in (copied / "scripts").iterdir() if path.is_file())
    assert "scripts/_lib" not in runtime
    assert "/_common" not in runtime

    os.symlink(host / "requests.go", copied_report / "scout_packets.json")
    unsafe_scout = _run(
        str(PYTHON), str(copied / "scripts" / "scout.py"), "--scan-dir", str(copied_report),
        "--project-root", str(host), cwd=host, env=env,
    )
    assert unsafe_scout.returncode == 2
    assert "symbolic link" in unsafe_scout.stderr
    (copied_report / "scout_packets.json").unlink()

    safe_scout = _run(
        str(PYTHON), str(copied / "scripts" / "scout.py"), "--scan-dir", str(copied_report),
        "--project-root", str(host), cwd=host, env=env,
    )
    assert safe_scout.returncode == 0, safe_scout.stdout + safe_scout.stderr
    packets = json.loads((copied_report / "scout_packets.json").read_text(encoding="utf-8"))
    (copied_report / "scout_verdicts.json").write_text(json.dumps({"verdicts": [{
        "id": packets["packets"][0]["id"],
        "verdict": "forgotten",
        "rationale": "The scoped evidence is a real sweep residue.",
        "completion": 'add `Region: "us"` to the RequestOptions literal',
    }]}), encoding="utf-8")
    os.symlink(host / "requests.go", copied_report / "triaged.md")
    unsafe_triage = _run(
        str(PYTHON), str(copied / "scripts" / "triage.py"), "--scan-dir", str(copied_report),
        cwd=host, env=env,
    )
    assert unsafe_triage.returncode == 2
    assert "symbolic link" in unsafe_triage.stderr
    assert _source_hashes(host) == before


def test_go_docs_state_the_bounded_semantic_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    guide = (SKILL / "knowledge" / "go-v1.md").read_text(encoding="utf-8")
    scans = set(text.split("scans: [", 1)[1].split("]", 1)[0].split(", "))
    assert {"python", "typescript", "javascript", "go", "java", "rust"} <= scans
    assert "`go list` + `go/parser` +" in text
    assert "exactly one literal omits the field" in guide
    assert "**every** present line newer" in text
    assert "Run the copied-install command" in text
    assert '"${SKILL_ROOT}/scripts/detect_go_incomplete_sweep.py"' in guide
    assert "Exit 0, `status=partial`" in guide
    assert "Exit 2, `unsupported`" in guide
    assert "Exit 2, `failed`" in guide
