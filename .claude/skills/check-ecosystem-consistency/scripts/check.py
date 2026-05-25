#!/usr/bin/env python3
"""Audit engineering-skills ecosystem consistency.

The script snapshots skill metadata and coordination surfaces, compares
them with the last reviewed state, and writes a report. It is advisory:
state is updated only with --update-state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]
SKILL_NAME = "check-ecosystem-consistency"
DEFAULT_STATE_PATH = REPO_ROOT / ".claude" / "ecosystem" / "last-state.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "reports" / SKILL_NAME
DOC_COUNT_FILES = ("README.md", "ONBOARDING.md")
CATALOG_PATH = ".claude/docs/skill-catalog.md"
SHAPES_PATH = ".claude/skills/which-shape/shapes.yml"
SKILL_REF_RE = re.compile(r"(?<![A-Za-z0-9_-])/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)")
SKILL_COUNT_RE = re.compile(r"\b(\d+)\s+skills\b", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


def utc_scan_id() -> str:
    return f"scan-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def relpath(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    payload = yaml.safe_load(match.group("body"))
    return payload if isinstance(payload, dict) else {}


def discover_skills(project_root: Path) -> dict[str, dict[str, Any]]:
    skills_dir = project_root / ".claude" / "skills"
    skills: dict[str, dict[str, Any]] = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        slug = skill_md.parent.name
        if slug.startswith("_"):
            continue
        text = read_text(skill_md)
        frontmatter = parse_frontmatter(text)
        skills[slug] = {
            "path": relpath(skill_md, project_root),
            "sha256": sha256_text(text),
            "name": frontmatter.get("name"),
            "tier": frontmatter.get("tier"),
            "job": frontmatter.get("job"),
            "description_sha256": sha256_text(str(frontmatter.get("description", ""))),
        }
    return dict(sorted(skills.items()))


def extract_skill_refs(value: Any) -> set[str]:
    if isinstance(value, str):
        text = value.replace("/find-*", "")
        return set(SKILL_REF_RE.findall(text))
    if isinstance(value, list):
        refs: set[str] = set()
        for item in value:
            refs.update(extract_skill_refs(item))
        return refs
    if isinstance(value, dict):
        refs = set()
        for item in value.values():
            refs.update(extract_skill_refs(item))
        return refs
    return set()


def validate_shapes_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["shape registry must be a YAML mapping"]
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("shape registry must declare schema_version: 1")
    shapes = payload.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        errors.append("shape registry must contain a non-empty shapes list")
        return errors
    seen: set[str] = set()
    required = {"id", "title", "summary", "first_next", "sequence", "stop", "cues", "alternatives"}
    for index, shape in enumerate(shapes):
        if not isinstance(shape, dict):
            errors.append(f"shape {index} must be a mapping")
            continue
        shape_id = shape.get("id")
        label = shape_id or f"shape {index}"
        if not isinstance(shape_id, str) or not shape_id:
            errors.append(f"{label}: missing string id")
        elif shape_id in seen:
            errors.append(f"{label}: duplicate shape id")
        else:
            seen.add(shape_id)
        missing = required - set(shape)
        if missing:
            errors.append(f"{label}: missing keys {sorted(missing)}")
        if not isinstance(shape.get("sequence"), list) or not shape.get("sequence"):
            errors.append(f"{label}: sequence must be a non-empty list")
    return errors


def discover_shape_registry(project_root: Path) -> dict[str, Any]:
    path = project_root / SHAPES_PATH
    if not path.exists():
        return {
            "path": SHAPES_PATH,
            "present": False,
            "sha256": None,
            "shape_ids": [],
            "referenced_skills": [],
            "schema_errors": ["shape registry is missing"],
        }
    text = read_text(path)
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return {
            "path": SHAPES_PATH,
            "present": True,
            "sha256": sha256_text(text),
            "shape_ids": [],
            "referenced_skills": [],
            "schema_errors": [f"invalid YAML: {exc}"],
        }
    schema_errors = validate_shapes_payload(payload)
    shapes = payload.get("shapes", []) if isinstance(payload, dict) else []
    shape_ids = [shape.get("id") for shape in shapes if isinstance(shape, dict) and isinstance(shape.get("id"), str)]
    refs: set[str] = set()
    for shape in shapes:
        if isinstance(shape, dict):
            refs.update(extract_skill_refs(shape.get("first_next")))
            refs.update(extract_skill_refs(shape.get("sequence")))
    return {
        "path": SHAPES_PATH,
        "present": True,
        "sha256": sha256_text(text),
        "shape_ids": sorted(shape_ids),
        "referenced_skills": sorted(refs),
        "schema_errors": schema_errors,
    }


def discover_docs(project_root: Path, skills: dict[str, dict[str, Any]]) -> dict[str, Any]:
    docs: dict[str, Any] = {}
    for rel in DOC_COUNT_FILES + (CATALOG_PATH,):
        path = project_root / rel
        if not path.exists():
            docs[rel] = {"present": False, "sha256": None, "skill_count_mentions": [], "mentioned_skills": []}
            continue
        text = read_text(path)
        mentioned = sorted(
            slug
            for slug in skills
            if f"/{slug}" in text or f"`{slug}`" in text or f"`/{slug}`" in text
        )
        docs[rel] = {
            "present": True,
            "sha256": sha256_text(text),
            "skill_count_mentions": [int(match) for match in SKILL_COUNT_RE.findall(text)],
            "mentioned_skills": mentioned,
        }
    return docs


def discover_state(project_root: Path) -> dict[str, Any]:
    skills = discover_skills(project_root)
    shape_registry = discover_shape_registry(project_root)
    docs = discover_docs(project_root, skills)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "project_root_name": project_root.name,
        "skill_count": len(skills),
        "skills": skills,
        "shape_registry": shape_registry,
        "docs": docs,
    }


def load_previous_state(state_path: Path) -> dict[str, Any] | None:
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def finding(
    pattern: str,
    summary: str,
    recommendation: str,
    *,
    file: str = "",
    severity: str = "warning",
    confidence: str = "medium",
    skill: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "pattern": pattern,
        "severity": severity,
        "file": file,
        "lineno": 1,
        "summary": summary,
        "recommendation": recommendation,
        "confidence": confidence,
        "surface": "skill_ecosystem",
    }
    if skill:
        record["skill"] = skill
    if extra:
        record.update(extra)
    return record


def compare_states(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    skills = current["skills"]
    skill_names = set(skills)
    shape_registry = current["shape_registry"]
    referenced_skills = set(shape_registry.get("referenced_skills", []))
    catalog_mentions = set(current["docs"].get(CATALOG_PATH, {}).get("mentioned_skills", []))

    if previous is None:
        findings.append(
            finding(
                "baseline_missing",
                "No previous ecosystem state was found, so this run can only perform point-in-time checks.",
                "Review this report, then rerun with --update-state to establish the diff baseline.",
                file=str(DEFAULT_STATE_PATH.relative_to(REPO_ROOT)),
                severity="info",
                confidence="high",
            )
        )
        added_skills: set[str] = set()
    else:
        previous_skills = set(previous.get("skills", {}))
        added_skills = skill_names - previous_skills
        removed_skills = previous_skills - skill_names
        for slug in sorted(added_skills):
            findings.append(
                finding(
                    "skill_added",
                    f"Skill /{slug} is new since the last reviewed ecosystem state.",
                    "Review catalog coverage, tests, and whether /which-shape should route to it.",
                    file=skills[slug]["path"],
                    severity="info",
                    confidence="high",
                    skill=slug,
                )
            )
        for slug in sorted(removed_skills):
            path = previous.get("skills", {}).get(slug, {}).get("path", f".claude/skills/{slug}/SKILL.md")
            findings.append(
                finding(
                    "skill_removed",
                    f"Skill /{slug} existed in the previous reviewed state but is no longer present.",
                    "Remove stale catalog, README, shape registry, and docs references if this removal is intentional.",
                    file=str(path),
                    severity="warning",
                    confidence="high",
                    skill=slug,
                )
            )
        for slug in sorted(skill_names & previous_skills):
            previous_hash = previous.get("skills", {}).get(slug, {}).get("sha256")
            if previous_hash and previous_hash != skills[slug].get("sha256"):
                findings.append(
                    finding(
                        "skill_contract_changed",
                        f"Skill /{slug} changed since the last reviewed ecosystem state.",
                        "Confirm the catalog, /which-shape routing, and tests still describe the changed behavior.",
                        file=skills[slug]["path"],
                        severity="info",
                        confidence="medium",
                        skill=slug,
                    )
                )
        previous_shape_hash = previous.get("shape_registry", {}).get("sha256")
        if previous_shape_hash and previous_shape_hash != shape_registry.get("sha256"):
            findings.append(
                finding(
                    "shape_registry_changed",
                    "/which-shape registry changed since the last reviewed ecosystem state.",
                    "Run the which-shape routing tests and review whether new shapes stay loop-level rather than catalog-level.",
                    file=SHAPES_PATH,
                    severity="info",
                    confidence="medium",
                )
            )

    for error in shape_registry.get("schema_errors", []):
        findings.append(
            finding(
                "shape_registry_schema_error",
                str(error),
                "Fix .claude/skills/which-shape/shapes.yml before trusting shape recommendations.",
                file=SHAPES_PATH,
                severity="error",
                confidence="high",
            )
        )

    for slug in sorted(referenced_skills - skill_names):
        findings.append(
            finding(
                "missing_shape_skill_reference",
                f"/which-shape references /{slug}, but no matching skill exists.",
                "Either add the missing skill or revise shapes.yml to point at an existing skill/ordinary action.",
                file=SHAPES_PATH,
                severity="error",
                confidence="high",
                skill=slug,
            )
        )

    for slug in sorted(added_skills - referenced_skills):
        findings.append(
            finding(
                "new_skill_not_reviewed_for_shape_registry",
                f"New skill /{slug} is not referenced by /which-shape.",
                "Decide whether this changes a durable problem-solving loop. If yes, update shapes.yml; if no, accept the omission and update the ecosystem state.",
                file=".claude/skills/which-shape/shapes.yml",
                severity="info",
                confidence="medium",
                skill=slug,
            )
        )

    for slug in sorted(added_skills - catalog_mentions):
        findings.append(
            finding(
                "new_skill_missing_catalog_review",
                f"New skill /{slug} is not mentioned in .claude/docs/skill-catalog.md.",
                "Add catalog coverage or intentionally leave it out before updating the ecosystem state.",
                file=CATALOG_PATH,
                severity="warning",
                confidence="medium",
                skill=slug,
            )
        )

    for rel in DOC_COUNT_FILES:
        doc = current["docs"].get(rel, {})
        for count in doc.get("skill_count_mentions", []):
            if count != current["skill_count"]:
                findings.append(
                    finding(
                        "docs_skill_count_mismatch",
                        f"{rel} says {count} skills, but the current inventory has {current['skill_count']}.",
                        "Update the public count or remove the exact count if it is not worth maintaining.",
                        file=rel,
                        severity="warning",
                        confidence="high",
                    )
                )
    return findings


def changed_paths(project_root: Path, *, staged: bool, changed_from: str | None) -> list[str]:
    cmd = ["git", "diff", "--name-only"]
    if staged:
        cmd.append("--cached")
    if changed_from:
        cmd.append(changed_from)
    try:
        completed = subprocess.run(cmd, cwd=project_root, text=True, capture_output=True, check=False)
    except OSError:
        return []
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def render_report(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    *,
    state_path: Path,
    changed: list[str],
) -> str:
    lines = [
        "# Ecosystem Consistency Report",
        "",
        f"- Skills: {current['skill_count']}",
        f"- Previous state: {'present' if previous else 'missing'} ({state_path})",
        f"- Shape registry refs: {len(current['shape_registry'].get('referenced_skills', []))}",
        f"- Findings: {len(findings)}",
    ]
    if changed:
        lines.extend(["", "## Changed Paths", ""])
        lines.extend(f"- `{path}`" for path in changed[:80])
        if len(changed) > 80:
            lines.append(f"- ... {len(changed) - 80} more")
    lines.extend(["", "## Findings", ""])
    if not findings:
        lines.append("No ecosystem consistency findings.")
    else:
        for record in findings:
            skill_suffix = f" ({record['skill']})" if record.get("skill") else ""
            lines.extend(
                [
                    f"### {record['pattern']}{skill_suffix}",
                    "",
                    f"- Severity: {record['severity']}",
                    f"- File: `{record['file'] or 'n/a'}`",
                    f"- Summary: {record['summary']}",
                    f"- Recommendation: {record['recommendation']}",
                    "",
                ]
            )
    lines.extend(["## Shape Registry", ""])
    if current["shape_registry"].get("present"):
        refs = current["shape_registry"].get("referenced_skills", [])
        lines.append("Referenced skills: " + (", ".join(f"`/{slug}`" for slug in refs) if refs else "none"))
    else:
        lines.append("Shape registry missing.")
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    output_root: Path,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    *,
    state_path: Path,
    changed: list[str],
) -> Path:
    scan_dir = output_root / utc_scan_id()
    scan_dir.mkdir(parents=True, exist_ok=True)
    write_json(scan_dir / "state.json", current)
    if previous is not None:
        write_json(scan_dir / "previous-state.json", previous)
    write_json(scan_dir / "findings.json", {"findings_total": len(findings), "findings": findings})
    report = render_report(current, previous, findings, state_path=state_path, changed=changed)
    (scan_dir / "report.md").write_text(report, encoding="utf-8")
    write_json(
        scan_dir / "evidence.json",
        {
            "skill": SKILL_NAME,
            "artifacts": ["report.md", "state.json", "findings.json"],
            "previous_state_present": previous is not None,
            "state_path": str(state_path),
            "finding_patterns": sorted({record["pattern"] for record in findings}),
        },
    )
    latest = output_root / "latest"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(scan_dir.name)
    except OSError:
        pass
    return scan_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--changed-from")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--update-state", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    state_path = args.state_path
    if not state_path.is_absolute():
        state_path = project_root / state_path
    output_root = args.output_root or (project_root / "reports" / SKILL_NAME)
    if not output_root.is_absolute():
        output_root = project_root / output_root

    current = discover_state(project_root)
    previous = load_previous_state(state_path)
    findings = compare_states(previous, current)
    changed = changed_paths(project_root, staged=args.staged, changed_from=args.changed_from)
    scan_dir = write_report(output_root, current, previous, findings, state_path=state_path, changed=changed)

    if args.update_state:
        write_json(state_path, current)

    result = {
        "scan_dir": str(scan_dir),
        "findings_total": len(findings),
        "finding_patterns": sorted({record["pattern"] for record in findings}),
        "state_updated": args.update_state,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"wrote {scan_dir}")
        if args.update_state:
            print(f"updated {state_path}")
        if findings:
            print(f"{len(findings)} finding(s): {', '.join(result['finding_patterns'])}")
        else:
            print("no ecosystem consistency findings")
    return 1 if any(record["severity"] == "error" for record in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
