"""Copied-install, final-artifact proof for the neutral planning batch.

These skills are prompt-led workflows: their installed closure is SKILL.md plus
any local knowledge, not a Python/Node launcher.  The executable oracle below
therefore checks the durable artifacts produced for five distinct natural tasks
against the same untouched, locked TypeScript host.  It deliberately does not
pretend that the host's planning scripts are part of a single-skill install.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "validated-neutral-typescript" / "planning"
RAW_HOST = FIXTURE_ROOT / "host"
TASKS = FIXTURE_ROOT / "tasks"
ARTIFACTS = FIXTURE_ROOT / "artifacts"
SKILL_NAMES = (
    "architecture-fit",
    "decide",
    "design-it-twice",
    "plan-spec",
    "scope-feature",
)
KNOWLEDGE_CLOSURE = {
    "decide": "knowledge/rules.md",
    "scope-feature": "knowledge/structure-redesign-lessons.md",
}


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _frontmatter_value(text: str, key: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError(f"missing frontmatter key {key!r}")


def _apply_artifact(host: Path, skill: str) -> None:
    """Materialize the recorded final artifact, never touching host source."""
    shutil.copytree(ARTIFACTS / skill, host, dirs_exist_ok=True)


def _assert_scope_feature(host: Path) -> None:
    artifact = host / "ai-docs" / "plans" / "webhook-replay-protection.md"
    text = artifact.read_text(encoding="utf-8")
    assert _frontmatter_value(text, "status") == "scoped"
    assert "## 1. Scope & Bounds" in text
    assert "## 2. Success Criteria" in text
    assert "src/api/webhook.ts" in text
    assert "src/worker/delivery.ts" in text
    assert "Retry scheduling policy" in text
    assert "admin replay UI" in text
    assert text.count("- ") >= 9


def _assert_architecture_fit(host: Path) -> None:
    artifact = host / "ai-docs" / "plans" / "delivery-retry-boundary.md"
    text = artifact.read_text(encoding="utf-8")
    assert _frontmatter_value(text, "status") == "architected"
    assert "## 5. Architecture Fit" in text
    assert "## 6. Open Decisions" in text
    assert "Layer violation" in text
    assert "P0" in text
    assert "/design-it-twice delivery-retry-execution" in text


def _assert_decide(host: Path) -> None:
    artifact = host / "ai-docs" / "decisions" / "0001-webhook-signature-boundary.md"
    text = artifact.read_text(encoding="utf-8")
    assert _frontmatter_value(text, "id") == "0001"
    assert _frontmatter_value(text, "status") == "proposed"
    for heading in (
        "## Context",
        "## Decision",
        "## Alternatives considered",
        "## Consequences",
        "## Verification",
    ):
        assert heading in text
    assert "verify the signature at the http boundary" in text.lower()
    assert text.count("Rejected:") >= 2


def _assert_design_it_twice(host: Path) -> None:
    scan = host / "reports" / "design-it-twice" / "scan-20260719-140000"
    analysis = scan / "delivery-retry-execution.md"
    text = analysis.read_text(encoding="utf-8")
    designs = sorted(scan.glob("design-axis*.md"))
    assert len(designs) == 3
    assert "## Divergence axes" in text
    assert "## Where they agreed" in text
    assert "## Where they diverged" in text
    assert "## Recommendation" in text
    assert "/decide delivery-retry-execution" in text
    axes = {path.stem.split("-", 3)[-1] for path in designs}
    assert len(axes) == 3
    for design in designs:
        design_text = design.read_text(encoding="utf-8")
        assert "## Design" in design_text
        assert "## Strengths under this axis" in design_text
        assert "## Weaknesses where this axis hurts" in design_text


def _assert_plan_spec(host: Path) -> None:
    plan = host / "ai-docs" / "plans" / "webhook-delivery-contract.md"
    spec = host / "ai-docs" / "specs" / "webhook-delivery-contract.md"
    plan_text = plan.read_text(encoding="utf-8")
    spec_text = spec.read_text(encoding="utf-8")
    assert _frontmatter_value(plan_text, "status") == "promoted"
    assert _frontmatter_value(plan_text, "successor_spec") == "webhook-delivery-contract"
    assert _frontmatter_value(spec_text, "status") == "draft"
    assert "# Provenance" in spec_text
    assert "Promoted from plan `webhook-delivery-contract`" in spec_text
    for heading in (
        "## Goals",
        "## Architecture",
        "## Implementation",
        "## Learnings",
        "## Exceptions",
    ):
        assert heading in spec_text
    assert "src/api/webhook.ts" in spec_text
    assert "src/worker/delivery.ts" in spec_text


ARTIFACT_ORACLES = {
    "scope-feature": _assert_scope_feature,
    "architecture-fit": _assert_architecture_fit,
    "decide": _assert_decide,
    "design-it-twice": _assert_design_it_twice,
    "plan-spec": _assert_plan_spec,
}


def test_stock_installed_neutral_planning_skills_reach_durable_typescript_artifacts(
    tmp_path: Path,
) -> None:
    """One stock install, five natural tasks, and no mutation of TS source."""
    host = tmp_path / "typescript-planning-host"
    shutil.copytree(RAW_HOST, host)
    source_before = _tree_fingerprint(host / "src")

    native_install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert native_install.returncode == 0, native_install.stdout + native_install.stderr
    typecheck = _run("npm", "run", "typecheck", cwd=host)
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr

    install = _run(
        "npx",
        "--yes",
        "skills@1.5.19",
        "add",
        str(REPO_ROOT),
        *[item for name in SKILL_NAMES for item in ("--skill", name)],
        "--agent",
        "codex",
        "--copy",
        "-y",
        cwd=host,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    assert _tree_fingerprint(host / "src") == source_before

    installed_root = host / ".agents" / "skills"
    assert {path.name for path in installed_root.iterdir()} == set(SKILL_NAMES)
    for name in SKILL_NAMES:
        installed = installed_root / name
        assert (installed / "SKILL.md").is_file()
        assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())
        skill_text = (installed / "SKILL.md").read_text(encoding="utf-8")
        assert "language: any" in skill_text
        assert "framework: any" in skill_text
        if name in KNOWLEDGE_CLOSURE:
            assert (installed / KNOWLEDGE_CLOSURE[name]).is_file()

    # Each task is intentionally distinct; its immutable prompt remains next
    # to the captured final artifact so a later D6 replay has no expected
    # answer embedded in the task itself.
    for name, oracle in ARTIFACT_ORACLES.items():
        task = (TASKS / f"{name}.md").read_text(encoding="utf-8")
        assert "Expected artifact" not in task
        assert "TypeScript planning host" in task
        _apply_artifact(host, name)
        oracle(host)
        assert _tree_fingerprint(host / "src") == source_before
