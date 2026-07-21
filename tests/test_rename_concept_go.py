"""Copied-closure and semantic-evidence proof for Go concept rename assessment."""
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
SKILL = ROOT / ".claude" / "skills" / "rename-concept"
DETECTOR = ROOT / ".claude" / "skills" / "find-concept-divergence"
FIXTURE = ROOT / "tests" / "fixtures" / "rename-concept-go" / "host"


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    go = shutil.which("go")
    if not go:
        pytest.skip("Go toolchain is unavailable")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = {
        **os.environ,
        "PATH": f"{Path(go).parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GOCACHE": str(tmp_path / "go-cache"),
        "GOTOOLCHAIN": "local",
    }
    assert _run("git", "init", "--quiet", cwd=host, env=env).returncode == 0
    assert _run("git", "add", "-A", cwd=host, env=env).returncode == 0
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.go"))
        if "reports" not in path.relative_to(host).parts
    }


def test_installed_go_assessment_uses_resolved_identifier_evidence(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    skills = tmp_path / "installed" / ".agents" / "skills"
    shutil.copytree(SKILL, skills / "rename-concept")
    shutil.copytree(DETECTOR, skills / "find-concept-divergence")
    before = _hashes(host)
    output = host / "reports" / "rename-concept" / "assessment.json"

    result = _run(
        sys.executable, "-I", "-S", str(skills / "rename-concept" / "scripts" / "assess.py"),
        "legacy-status", "canonical-status", "--project-root", str(host),
        "--output", str(output), cwd=host, env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Go: RESOLVED" in result.stdout
    assert "old_concept_symbol" in result.stdout
    assert "shadowed_local" in result.stdout
    assert "property_key" in result.stdout
    assert "HALF-APPLIED / INCOMPLETE" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    evidence = payload["go_identifier_evidence"]
    assert evidence["status"] == "resolved"
    assert evidence["go_version"].startswith("go version go")
    assert {item["name"] for item in evidence["declarations"]["old"]} == {"LegacyStatus"}
    assert {item["name"] for item in evidence["declarations"]["new"]} == {"CanonicalStatus"}
    assert {item["classification"] for item in evidence["occurrences"]} >= {
        "old_concept_symbol", "new_concept_symbol", "shadowed_local", "property_key"
    }
    assert any(
        item["file"] == "transition.go"
        and item["name"] == "LegacyStatus"
        and item["classification"] == "old_concept_symbol"
        for item in evidence["occurrences"]
    )
    assert _hashes(host) == before


def test_go_assessment_missing_tool_is_incomplete_without_mutation(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    skills = tmp_path / "installed" / ".agents" / "skills"
    shutil.copytree(SKILL, skills / "rename-concept")
    shutil.copytree(DETECTOR, skills / "find-concept-divergence")
    before = _hashes(host)
    output = host / "reports" / "rename-concept" / "missing-go.json"
    env["PATH"] = "/usr/bin:/bin"

    result = _run(
        sys.executable, "-I", "-S", str(skills / "rename-concept" / "scripts" / "assess.py"),
        "legacy-status", "canonical-status", "--project-root", str(host),
        "--output", str(output), cwd=host, env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["go_identifier_evidence"]["status"] == "unavailable"
    assert payload["verdict"] == "INCONCLUSIVE"
    assert "Go semantic evidence unavailable" in payload["open_items"]
    assert _hashes(host) == before
