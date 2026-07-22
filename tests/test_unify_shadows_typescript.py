"""Structured handoff and installed-closure proof for TypeScript shadow proposals."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "unify-shadows"
SCRIPT = SKILL / "scripts" / "propose_typescript.mjs"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "unify-shadows-typescript" / "host"
FINDING_ID = "TS-SD-0001"
SHAPES = (
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
)


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    for command in (("npm", "run", "typecheck"), ("npm", "test")):
        native = _run(*command, cwd=host)
        assert native.returncode == 0, native.stdout + native.stderr
    return host


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_case(host: Path, name: str, transform) -> Path:
    source = host / "reports" / "semantic-duplication" / "locked" / "findings.json"
    payload = _load(source)
    transform(payload)
    case_dir = host / "reports" / "semantic-duplication" / name
    case_dir.mkdir(parents=True)
    shutil.copytree(source.parent / "capability_matrices", case_dir / "capability_matrices")
    case = case_dir / "findings.json"
    case.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return case


def _propose(
    skill: Path,
    host: Path,
    *,
    findings: Path | None = None,
    finding_id: str = FINDING_ID,
    name: str = "locked",
    proposal: Path | None = None,
    evidence: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    findings = findings or (
        host / "reports" / "semantic-duplication" / "locked" / "findings.json"
    )
    output_dir = host / "reports" / "unify-shadows" / name
    proposal = proposal or output_dir / "proposal.md"
    evidence = evidence or output_dir / "evidence.json"
    result = _run(
        "node",
        str(skill / "scripts" / "propose_typescript.mjs"),
        "--findings",
        str(findings),
        "--finding-id",
        finding_id,
        "--project-root",
        str(host),
        "--proposal",
        str(proposal),
        "--evidence",
        str(evidence),
        cwd=host,
    )
    return result, proposal, evidence


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((host / "src").rglob("*"))
        if path.is_file()
    }


def _documented_command(skill: Path, name: str) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- installed-command:{name}:start -->\n```bash\n(.*?)\n```\n"
        rf"<!-- installed-command:{name}:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None, name
    return match.group(1)


def test_confirmed_typescript_finding_reaches_evidence_cited_final_proposal(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _source_hashes(host)

    result, proposal, evidence = _propose(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    rendered = proposal.read_text(encoding="utf-8")
    for heading in (
        "## Members and source impact",
        "## Evidence",
        "## Proposed action",
        "## Caller impact",
        "## Native TypeScript test matrix",
        "## Stop condition",
        "## Authorization and handoff",
    ):
        assert heading in rendered
    assert "src/semantic.ts:5-9" in rendered
    assert "src/semantic.ts:11-19" in rendered
    assert "capability_matrices/TS-SD-0001.md:" in rendered
    assert "npm run typecheck" in rendered
    assert "npm test" in rendered
    assert "Human approval is required" in rendered
    assert f"/fix-workflow semantic:{FINDING_ID}" in rendered

    payload = _load(evidence)
    assert payload["status"] == "proposal_ready_for_human_review"
    assert payload["finding_id"] == FINDING_ID
    assert payload["language"] == "typescript"
    assert payload["shape"] == "share_utilities"
    assert payload["source_evidence"] == [
        "src/semantic.ts:5-9",
        "src/semantic.ts:11-19",
    ]
    scope = _load(proposal.parent / "scope.json")
    assert scope["paths"] == ["src/semantic.ts"]
    assert scope["written_at"]
    assert before == _source_hashes(host)

    for command in (("npm", "run", "typecheck"), ("npm", "test")):
        native = _run(*command, cwd=host)
        assert native.returncode == 0, native.stdout + native.stderr


@pytest.mark.parametrize("shape", SHAPES)
def test_each_supported_shape_has_an_honest_template(tmp_path: Path, shape: str) -> None:
    host = _copy_host(tmp_path, shape)

    def set_shape(payload: dict) -> None:
        payload["confirmed"][0]["consolidation_shape"] = shape
        payload["findings"][0]["consolidation_shape"] = shape

    findings = _write_case(host, f"shape-{shape}", set_shape)
    result, proposal, evidence = _propose(
        SKILL,
        host,
        findings=findings,
        name=f"shape-{shape}",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    rendered = proposal.read_text(encoding="utf-8")
    action = rendered.split("## Proposed action\n", 1)[1].split("\n## Caller impact", 1)[0]
    assert f"Template: `{shape}`" in action
    assert _load(evidence)["shape"] == shape
    if shape == "keep_separate_document_why":
        lowered = action.lower()
        assert "merge" not in lowered
        assert "migrat" not in lowered
        assert "preserve both implementations" in lowered
    elif shape == "share_utilities":
        assert "shared utility seam" in action.lower()
    elif shape == "complete_migration":
        assert "surviving implementation" in action.lower()
        assert "retired member" in action.lower()
    else:
        assert "workflow authority" in action.lower()
        assert "workflow evidence is unavailable" in action.lower()


@pytest.mark.parametrize(
    ("name", "transform", "error"),
    (
        (
            "unconfirmed",
            lambda payload: (
                payload.__setitem__("confirmed", []),
                payload.__setitem__("findings", []),
                payload.__setitem__(
                    "uncertain",
                    [
                        {
                            **_load(
                                FIXTURE
                                / "reports"
                                / "semantic-duplication"
                                / "locked"
                                / "findings.json"
                            )["confirmed"][0],
                            "investigation_status": "uncertain",
                        }
                    ],
                ),
            ),
            "is not confirmed",
        ),
        (
            "wrong-skill",
            lambda payload: payload.__setitem__("skill", "find-duplication"),
            "wrong finding kind",
        ),
        (
            "wrong-language",
            lambda payload: payload.__setitem__("language", "python"),
            "requires language=typescript",
        ),
        (
            "wrong-level",
            lambda payload: payload["confirmed"][0].__setitem__("level", "workflow"),
            "requires a function-level finding",
        ),
        (
            "not-confirmed-status",
            lambda payload: payload["confirmed"][0].__setitem__(
                "investigation_status", "uncertain"
            ),
            "must have investigation_status=confirmed",
        ),
    ),
)
def test_missing_unconfirmed_and_wrong_kind_inputs_fail_before_synthesis(
    tmp_path: Path,
    name: str,
    transform,
    error: str,
) -> None:
    host = _copy_host(tmp_path, name)
    findings = _write_case(host, name, transform)
    output_dir = host / "reports" / "unify-shadows" / name

    result, _, _ = _propose(SKILL, host, findings=findings, name=name)

    assert result.returncode == 2
    assert error in result.stderr
    assert not output_dir.exists()

    missing, _, _ = _propose(
        SKILL,
        host,
        findings=host / "reports" / "semantic-duplication" / "absent.json",
        name=f"{name}-missing",
    )
    assert missing.returncode == 2
    assert "findings file not found" in missing.stderr
    assert not (host / "reports" / "unify-shadows" / f"{name}-missing").exists()


def test_source_and_output_containment_fail_without_source_mutation(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_hashes(host)
    outside = tmp_path / "outside"
    outside.mkdir()

    escaped, _, _ = _propose(
        SKILL,
        host,
        name="escape",
        proposal=outside / "proposal.md",
        evidence=outside / "evidence.json",
    )
    assert escaped.returncode == 2
    assert "must stay beneath reports/unify-shadows/" in escaped.stderr

    reports = host / "reports" / "unify-shadows"
    reports.mkdir(parents=True)
    os.symlink(host / "src", reports / "linked")
    linked, _, _ = _propose(SKILL, host, name="linked")
    assert linked.returncode == 2
    assert "symbolic link" in linked.stderr
    assert before == _source_hashes(host)


def test_stock_selected_skill_copy_runs_without_repository_runtime(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = _run(
        "bash",
        "-c",
        _documented_command(SKILL, "stock-install"),
        cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1", "UNIFY_SHADOWS_SOURCE": str(REPO_ROOT)},
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "unify-shadows"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    before = _source_hashes(host)
    result = _run(
        "bash",
        "-c",
        _documented_command(installed, "typescript-proposal"),
        cwd=host,
        env={
            **os.environ,
            "UNIFY_FINDINGS": "reports/semantic-duplication/locked/findings.json",
            "UNIFY_FINDING_ID": FINDING_ID,
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    proposal = host / "reports" / "unify-shadows" / FINDING_ID / "proposal.md"
    assert proposal.is_file()
    assert str(REPO_ROOT) not in proposal.read_text(encoding="utf-8")
    assert before == _source_hashes(host)


def test_legacy_collector_accepts_unknown_callers_and_uses_copied_scope_fallback(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "unify-shadows"
    shutil.copytree(SKILL, copied)
    host = tmp_path / "legacy-host"
    (host / "app").mkdir(parents=True)
    (host / "app" / "a.py").write_text("def first():\n    return 1\n", encoding="utf-8")
    (host / "app" / "b.py").write_text("def second():\n    return 1\n", encoding="utf-8")
    triage = host / "triage.md"
    triage.write_text(
        "### SC-1: Unknown caller evidence [FUNCTION]\n\n"
        "**Members:**\n"
        "- `app/a.py:1` — `first` (2 lines, ? callers)\n"
        "- `app/b.py:1` — `second` (2 lines, 1 caller)\n\n"
        "**Consolidation shape:** `share_utilities`\n",
        encoding="utf-8",
    )
    output = host / "reports" / "unify-shadows" / "SC-1" / "targets.json"

    result = _run(
        sys.executable,
        str(copied / "scripts" / "collect_shadows.py"),
        "--triage",
        str(triage),
        "--finding-id",
        "SC-1",
        "--output",
        str(output),
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert [member["caller_count"] for member in _load(output)["members"]] == [None, 1]
    scope = _load(output.parent / "scope.json")
    assert scope["version"] == 1
    assert scope["paths"] == ["app/a.py", "app/b.py"]
