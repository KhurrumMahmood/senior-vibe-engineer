"""Go folder proposal artifacts, convention gates, and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "propose-folder-reorganization"
SCRIPT = SKILL / "scripts" / "propose_go.go"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "propose-folder-reorganization-go"
GO = shutil.which("go")
pytestmark = pytest.mark.skipif(GO is None, reason="Go toolchain is required")


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _copy_host(tmp_path: Path, name: str) -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / name, host)
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and (path.suffix == ".go" or path.name in {"go.mod", "go.sum"})
    }


def _propose(
    skill: Path,
    host: Path,
    *,
    name: str,
    conventions: str | None = "conventions.json",
    minimum_go: str = "1.22",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    root = host / "reports" / "propose-folder-reorganization" / name
    args = [
        GO,
        "run",
        str(skill / "scripts" / "propose_go.go"),
        "--parent",
        "internal/legacy",
        "--prefix",
        "billing",
        "--cluster-judgment",
        "split",
        "--project-root",
        str(host),
        "--minimum-go",
        minimum_go,
        "--inspection",
        str(root / "inspection.json"),
        "--proposal",
        str(root / "proposal.md"),
    ]
    if conventions is not None:
        args.extend(["--conventions", conventions])
    result = _run(*args, cwd=host)
    return result, root / "inspection.json", root / "proposal.md"


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documented_command(skill: Path) -> str:
    text = (skill / "knowledge" / "go-v1.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:go-proposal:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:go-proposal:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_go_positive_requires_and_records_project_convention_and_complete_impact(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    before = _fingerprints(host)
    native = _run(GO, "test", "./...", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr

    result, inspection, proposal = _propose(SKILL, host, name="positive")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(inspection)
    assert payload["status"] == "ready"
    assert payload["recommendation"] == "refactor"
    assert payload["language"] == "go"
    assert payload["analyzer"] == "go-list-plus-stdlib-types"
    assert payload["conventions"]["source"] == "conventions.json"
    assert payload["conventions"]["applied_rules"][0]["action"] == "allow_package_split"
    assert payload["conventions"]["conflicts"] == []
    assert payload["conventions"]["unresolved_assumptions"] == []
    assert payload["summary"] == {
        "cluster_size": 3,
        "test_file_count": 1,
        "resolved_import_impact_count": 2,
        "cross_boundary_reference_count": 0,
    }
    assert [row["current_path"] for row in payload["cluster_files"]] == [
        "internal/legacy/billing_parser.go",
        "internal/legacy/billing_rules.go",
        "internal/legacy/billing_summary.go",
    ]
    assert payload["test_files"][0]["new_path"] == "internal/legacy/billing/parser_test.go"
    assert {row["symbol"] for row in payload["import_impact"]} == {"ParseInvoice", "Summary"}
    assert all(row["after_import_path"] == "example.com/folder-reorg/internal/legacy/billing" for row in payload["import_impact"])
    assert payload["native_verification"]["commands"] == ["go test ./...", "go vet ./..."]
    rendered = proposal.read_text(encoding="utf-8")
    assert "## Convention basis" in rendered
    assert "## Complete resolved import-impact table" in rendered
    assert "go test ./..." in rendered


def test_go_without_explicit_convention_defers_instead_of_universalizing_threshold(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    result, inspection, proposal = _propose(SKILL, host, name="no-convention", conventions=None)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(inspection)
    assert payload["status"] == "deferred"
    assert payload["recommendation"] == "defer_project_convention_required"
    assert payload["conventions"]["source"] == "none"
    assert payload["conventions"]["unresolved_assumptions"]
    assert "threshold is evidence of a cluster, not authority" in proposal.read_text(encoding="utf-8")


def test_go_conflicting_conventions_and_unexported_boundary_are_blocked(tmp_path: Path) -> None:
    conflict = _copy_host(tmp_path, "positive")
    profile = json.loads((conflict / "conventions.json").read_text(encoding="utf-8"))
    profile["rules"].append({
        "parent": "internal/legacy",
        "prefix": "billing",
        "action": "deny_package_split",
        "rationale": "Framework convention keeps this package flat.",
    })
    (conflict / "conventions.json").write_text(json.dumps(profile), encoding="utf-8")
    result, inspection, _ = _propose(SKILL, conflict, name="conflict")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(inspection)
    assert payload["status"] == "blocked"
    assert payload["recommendation"] == "defer_convention_conflict"
    assert payload["conventions"]["conflicts"]

    unexported = _copy_host(tmp_path, "unexported")
    result, inspection, proposal = _propose(SKILL, unexported, name="unexported")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(inspection)
    assert payload["status"] == "blocked"
    assert payload["recommendation"] == "defer_cross_package_boundary"
    assert any(row["symbol"] == "legacySecret" for row in payload["cross_boundary_references"])
    assert "package-private" in proposal.read_text(encoding="utf-8")


def test_go_build_constraints_malformed_and_old_tool_never_claim_ready(tmp_path: Path) -> None:
    tagged = _copy_host(tmp_path, "build-tagged")
    result, inspection, _ = _propose(SKILL, tagged, name="tagged")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(inspection)
    assert payload["status"] == "partial"
    assert payload["recommendation"] == "defer_build_constraints"

    malformed = _copy_host(tmp_path, "malformed")
    result, inspection, _ = _propose(SKILL, malformed, name="malformed")
    assert result.returncode != 0
    assert _payload(inspection)["status"] == "failed"

    old = _copy_host(tmp_path, "positive")
    result, inspection, _ = _propose(SKILL, old, name="old", minimum_go="99.0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _payload(inspection)["status"] == "unsupported"


def test_go_paths_reject_escape_and_symlinked_artifacts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    outside = tmp_path / "outside"
    outside.mkdir()
    result = _run(
        GO, "run", str(SCRIPT),
        "--parent", "../outside", "--prefix", "billing", "--cluster-judgment", "split",
        "--project-root", str(host), "--conventions", "conventions.json",
        "--inspection", str(host / "reports/propose-folder-reorganization/escape/inspection.json"),
        "--proposal", str(host / "reports/propose-folder-reorganization/escape/proposal.md"),
        cwd=host,
    )
    assert result.returncode != 0
    assert "inside project root" in result.stderr

    linked = tmp_path / "positive-linked"
    shutil.copytree(FIXTURE / "positive", linked)
    (linked / "reports").mkdir()
    shutil.rmtree(linked / "reports")
    os.symlink(linked / "internal", linked / "reports")
    result, _, _ = _propose(SKILL, linked, name="linked")
    assert result.returncode != 0
    assert "symbolic link" in result.stderr


def test_copied_skill_closure_replays_documented_go_command(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "positive")
    installed = host / ".agents" / "skills" / "propose-folder-reorganization"
    shutil.copytree(SKILL, installed)
    before = _fingerprints(host)
    command = _documented_command(installed)
    replay = _run(
        "/bin/bash", "-c", command,
        cwd=host,
        env={
            **os.environ,
            "PFR_PARENT": "internal/legacy",
            "PFR_PREFIX": "billing",
            "PFR_NAME": "installed-go",
            "PFR_CONVENTIONS": "conventions.json",
        },
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr
    payload = _payload(host / "reports/propose-folder-reorganization/installed-go/inspection.json")
    assert payload["status"] == "ready"
    assert _fingerprints(host) == before
    assert str(REPO_ROOT) not in SCRIPT.read_text(encoding="utf-8")


def test_typescript_and_python_proposal_regressions_still_pass() -> None:
    assert (SKILL / "scripts" / "propose_typescript.mjs").is_file()
    assert (SKILL / "scripts" / "inspect.py").is_file()
