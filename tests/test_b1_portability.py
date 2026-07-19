from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"
FIXTURE_HOST = REPO_ROOT / "tests" / "fixtures" / "b1-portability" / "concept-host"
SKILL_NAMES = (
    "find-concept-divergence",
    "find-rule-surface-drift",
    "find-skill-artifact-drift",
    "find-skill-intent-drift",
    "find-stale-artifacts",
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _isolated(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return _run(sys.executable, "-I", "-S", str(script), *args, cwd=cwd)


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_concept_glossary_scans_ts_and_tsx_through_final_report(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE_HOST, host)
    out = host / "reports" / "find-concept-divergence" / "scan-b1"
    findings = out / "findings.jsonl"
    report = out / "report.md"

    result = _run(
        sys.executable,
        str(SKILLS_ROOT / "find-concept-divergence" / "scripts" / "scan.py"),
        "--project-root",
        str(host),
        "--output",
        str(findings),
        "--report",
        str(report),
        ".",
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(findings)
    files = {record["file"] for record in records}
    assert {"src/deprecated.ts", "src/deprecated.tsx"} <= files
    assert not {
        "src/canonical.tsx",
        "src/homonym.ts",
        "src/compatibility-alias.ts",
        "node_modules/vendor/deprecated.ts",
        "dist/generated.tsx",
    } & files
    assert "src/deprecated.tsx" in report.read_text(encoding="utf-8")


def test_b1_frontmatter_is_host_language_neutral_without_fake_ts_scans() -> None:
    expected_scans = {
        "find-concept-divergence": "scans: [python, javascript, typescript, markdown, templates]",
        "find-rule-surface-drift": "scans: [markdown]",
        "find-skill-artifact-drift": "scans: [python, markdown]",
        "find-stale-artifacts": "scans: [markdown]",
    }
    for name in SKILL_NAMES:
        text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
        assert "language: any" in text
        assert "framework: any" in text
        if name in expected_scans:
            assert expected_scans[name] in text
    assert "scans: [typescript]" not in (
        SKILLS_ROOT / "find-rule-surface-drift" / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_copied_b1_skills_run_with_isolated_host_tools(tmp_path: Path) -> None:
    installed_root = tmp_path / "installed"
    for name in SKILL_NAMES:
        shutil.copytree(SKILLS_ROOT / name, installed_root / name)
    host = tmp_path / "host"
    shutil.copytree(FIXTURE_HOST, host)

    concept_out = host / "reports" / "find-concept-divergence" / "scan-b1"
    concept_findings = concept_out / "findings.jsonl"
    concept_report = concept_out / "report.md"
    concept = _isolated(
        installed_root / "find-concept-divergence" / "scripts" / "scan.py",
        "--project-root",
        str(host),
        "--output",
        str(concept_findings),
        "--report",
        str(concept_report),
        ".",
        cwd=host,
    )
    assert concept.returncode == 0, concept.stdout + concept.stderr
    assert {
        (record["band"], record["file"], record["term"])
        for record in _records(concept_findings)
    } == {
        ("avoid_term_hit", "src/deprecated.ts", "deprecated status"),
        ("avoid_term_hit", "src/deprecated.tsx", "deprecated status"),
    }
    concept_report_text = concept_report.read_text(encoding="utf-8")
    assert "src/deprecated.tsx" in concept_report_text
    assert "No drift detected" not in concept_report_text

    rules_root = host / ".claude"
    rules_root.mkdir(exist_ok=True)
    (rules_root / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")
    (host / "ONBOARDING.md").write_text("# Onboarding\n", encoding="utf-8")
    rule_out = host / "reports" / "find-rule-surface-drift" / "scan-b1"
    rule_detect = _isolated(
        installed_root / "find-rule-surface-drift" / "scripts" / "detect.py",
        "--root",
        str(rules_root),
        "--project-root",
        str(host),
        "--output",
        str(rule_out / "detections.jsonl"),
        cwd=host,
    )
    assert rule_detect.returncode == 0, rule_detect.stdout + rule_detect.stderr
    rule_report = _isolated(
        installed_root / "find-rule-surface-drift" / "scripts" / "report.py",
        "--detections",
        str(rule_out / "detections.jsonl"),
        "--output-md",
        str(rule_out / "report.md"),
        "--output-json",
        str(rule_out / "findings.json"),
        "--target",
        "agent rules",
        cwd=host,
    )
    assert rule_report.returncode == 0, rule_report.stdout + rule_report.stderr
    assert json.loads((rule_out / "findings.json").read_text())["summary"]["findings_total"] == 0

    artifact_skills = host / ".claude" / "skills"
    artifact_skills.mkdir(parents=True)
    (artifact_skills / "clean-skill").mkdir()
    (artifact_skills / "clean-skill" / "SKILL.md").write_text(
        "---\nname: clean-skill\nallowed-tools: Bash, Read\n---\n\n# Clean skill\n",
        encoding="utf-8",
    )
    artifact_out = host / "reports" / "find-skill-artifact-drift" / "scan-b1"
    artifact_detect = _isolated(
        installed_root / "find-skill-artifact-drift" / "scripts" / "detect.py",
        "--skills-dir",
        str(artifact_skills),
        "--output",
        str(artifact_out / "detections.jsonl"),
        cwd=host,
    )
    assert artifact_detect.returncode == 0, artifact_detect.stdout + artifact_detect.stderr
    artifact_report = _isolated(
        installed_root / "find-skill-artifact-drift" / "scripts" / "report.py",
        str(artifact_out / "detections.jsonl"),
        "--output",
        str(artifact_out / "report.md"),
        cwd=host,
    )
    assert artifact_report.returncode == 0, artifact_report.stdout + artifact_report.stderr
    assert json.loads((artifact_out / "findings.json").read_text())["summary"]["findings_total"] == 0

    intent_contracts = host / ".claude" / "contracts" / "skills"
    intent_contracts.mkdir(parents=True)
    intent_skills = host / "intent-skills" / "clean-skill"
    intent_skills.mkdir(parents=True)
    (intent_skills / "SKILL.md").write_text(
        "---\nname: clean-skill\ndescription: Inspect a contract.\n---\n",
        encoding="utf-8",
    )
    (intent_contracts / "clean-skill.yaml").write_text(
        json.dumps(
            {
                "skill": "clean-skill",
                "job": "suspect",
                "problem_class": "contract-audit",
                "intent": "Inspect a contract.",
                "solves": "Missing contract evidence.",
                "born": {"commit": "fixture", "date": "2026-07-18"},
                "dogfood_kind": "fixture-pair",
                "provenance_confidence": {
                    "textual": "high",
                    "structural": "high",
                    "temporal": "high",
                    "dogfood": "high",
                },
            }
        ),
        encoding="utf-8",
    )
    intent = _isolated(
        installed_root / "find-skill-intent-drift" / "scripts" / "scan.py",
        "--skills-root",
        str(intent_skills.parent),
        "--contracts-dir",
        str(intent_contracts),
        "--no-index",
        cwd=host,
    )
    assert intent.returncode == 0, intent.stdout + intent.stderr
    assert "TOTAL findings: 0" in intent.stdout

    stale_out = host / "reports" / "find-stale-artifacts" / "scan-b1"
    stale_detect = _isolated(
        installed_root / "find-stale-artifacts" / "scripts" / "detect.py",
        "--root",
        str(host / "empty-artifacts"),
        "--output",
        str(stale_out / "detections.jsonl"),
        cwd=host,
    )
    assert stale_detect.returncode == 0, stale_detect.stdout + stale_detect.stderr
    stale_report = _isolated(
        installed_root / "find-stale-artifacts" / "scripts" / "report.py",
        "--detections",
        str(stale_out / "detections.jsonl"),
        "--output-md",
        str(stale_out / "report.md"),
        "--output-json",
        str(stale_out / "findings.json"),
        "--target",
        "working artifacts",
        cwd=host,
    )
    assert stale_report.returncode == 0, stale_report.stdout + stale_report.stderr
    assert json.loads((stale_out / "findings.json").read_text())["summary"]["findings_total"] == 0


def test_copied_concept_skill_preserves_quoted_comma_alias_in_final_report(tmp_path: Path) -> None:
    installed_skill = tmp_path / "installed" / "find-concept-divergence"
    shutil.copytree(SKILLS_ROOT / "find-concept-divergence", installed_skill)
    host = tmp_path / "host"
    shutil.copytree(FIXTURE_HOST, host)
    (host / ".claude" / "contracts" / "concepts.yaml").write_text(
        """\
concepts:
  - name: legacy-status
    aliases: ["legacy, status"]
    superseded_by: canonical-status
  - name: canonical-status
    aliases: ["canonical, status"]
flagged_ambiguities: []
        """,
        encoding="utf-8",
    )
    shutil.rmtree(host / "src")
    (host / "src").mkdir()
    (host / "src" / "quoted-alias.ts").write_text(
        "export const statusTransition = `legacy, status -> canonical, status`;\n",
        encoding="utf-8",
    )
    out = host / "reports" / "find-concept-divergence" / "quoted-alias"
    findings = out / "findings.jsonl"
    report = out / "report.md"

    result = _isolated(
        installed_skill / "scripts" / "scan.py",
        "--project-root",
        str(host),
        "--output",
        str(findings),
        "--report",
        str(report),
        ".",
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _records(findings) == [
        {
            "band": "superseded_co_occurrence",
            "concept": "legacy-status",
            "superseded_by": "canonical-status",
            "file": "src/quoted-alias.ts",
            "side": "old",
            "line": 1,
            "term": "legacy, status",
            "match": "export const statusTransition = `legacy, status -> canonical, status`;",
        }
    ]
    report_text = report.read_text(encoding="utf-8")
    assert "superseded_co_occurrence (1)" in report_text
    assert "`legacy, status`" in report_text
