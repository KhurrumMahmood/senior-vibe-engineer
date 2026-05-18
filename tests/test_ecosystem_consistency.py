from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK_PATH = REPO_ROOT / ".claude" / "skills" / "check-ecosystem-consistency" / "scripts" / "check.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_module("ecosystem_consistency_check", CHECK_PATH)


def _write_skill(root: Path, slug: str, *, job: str = "suspect") -> None:
    skill_dir = root / ".claude" / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {slug}
description: Test skill {slug}.
argument-hint: "[target]"
allowed-tools: Bash, Read
user-invocable: true
tier: maintenance
job: {job}
best_for: Test usage.
not_for: Non-test usage.
language: any
framework: any
---

# /{slug}
""",
        encoding="utf-8",
    )


def _write_shapes(root: Path, first_next: str = "/adapt-project") -> None:
    shape_dir = root / ".claude" / "skills" / "which-shape"
    shape_dir.mkdir(parents=True, exist_ok=True)
    (shape_dir / "shapes.yml").write_text(
        f"""schema_version: 1
shapes:
  - id: project-intake
    title: Project Intake
    summary: Discover context.
    first_next: "{first_next}"
    sequence:
      - "{first_next}"
    stop: "Stop after context exists."
    cues:
      strong: [unknown]
      normal: [project]
      negative: [typo]
    alternatives: []
""",
        encoding="utf-8",
    )


def _write_docs(root: Path, count: int, *, catalog: str = "/adapt-project\n/which-shape\n") -> None:
    (root / "README.md").write_text(f"# Test\n\n- `.claude/skills/` - {count} skills\n", encoding="utf-8")
    (root / "ONBOARDING.md").write_text(f"This repo has {count} skills.\n", encoding="utf-8")
    catalog_path = root / ".claude" / "docs"
    catalog_path.mkdir(parents=True, exist_ok=True)
    (catalog_path / "skill-catalog.md").write_text(catalog, encoding="utf-8")


def _base_repo(root: Path, count: int = 2) -> None:
    _write_skill(root, "adapt-project", job="meta")
    _write_skill(root, "which-shape", job="meta")
    _write_shapes(root)
    _write_docs(root, count)


def test_new_skill_is_diffed_against_last_state_and_flags_shape_review(tmp_path):
    _base_repo(tmp_path, count=2)
    previous = check.discover_state(tmp_path)
    state_path = tmp_path / ".claude" / "ecosystem" / "last-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(previous), encoding="utf-8")

    _write_skill(tmp_path, "new-skill")
    _write_docs(tmp_path, 3)
    current = check.discover_state(tmp_path)
    findings = check.compare_states(previous, current)
    patterns = {record["pattern"] for record in findings}

    assert "skill_added" in patterns
    assert "new_skill_not_reviewed_for_shape_registry" in patterns
    assert "new_skill_missing_catalog_review" in patterns


def test_docs_skill_count_mismatch_is_reported(tmp_path):
    _base_repo(tmp_path, count=1)
    current = check.discover_state(tmp_path)
    findings = check.compare_states(None, current)

    mismatches = [record for record in findings if record["pattern"] == "docs_skill_count_mismatch"]
    assert mismatches
    assert mismatches[0]["file"] == "README.md"


def test_missing_shape_skill_reference_is_reported(tmp_path):
    _write_skill(tmp_path, "which-shape", job="meta")
    _write_shapes(tmp_path, first_next="/missing-skill")
    _write_docs(tmp_path, 1, catalog="/which-shape\n")

    current = check.discover_state(tmp_path)
    findings = check.compare_states(None, current)

    assert any(record["pattern"] == "missing_shape_skill_reference" for record in findings)


def test_slash_separated_prose_is_not_treated_as_skill_reference():
    refs = check.extract_skill_refs("add a narrow lint/test/policy guard, then /prevent-regression")

    assert refs == {"prevent-regression"}


def test_update_state_establishes_diff_baseline(tmp_path):
    _base_repo(tmp_path, count=2)
    state_path = tmp_path / ".claude" / "ecosystem" / "last-state.json"
    output_root = tmp_path / "reports" / "check-ecosystem-consistency"

    assert check.main(["--project-root", str(tmp_path), "--state-path", str(state_path), "--output-root", str(output_root), "--update-state"]) == 0
    assert state_path.exists()

    assert check.main(["--project-root", str(tmp_path), "--state-path", str(state_path), "--output-root", str(output_root)]) == 0
    latest = output_root / "latest"
    scan_dir = latest.resolve() if latest.is_symlink() else latest
    findings = json.loads((scan_dir / "findings.json").read_text(encoding="utf-8"))

    assert findings["findings_total"] == 0
    assert (scan_dir / "report.md").exists()
    assert (scan_dir / "state.json").exists()
    assert (scan_dir / "evidence.json").exists()
