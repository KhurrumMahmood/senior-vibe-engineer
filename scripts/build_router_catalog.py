#!/usr/bin/env python3
"""Build the metadata-only catalog bundled with the installed skill router."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DEFAULT_OUTPUT = SKILLS_DIR / "which-skill" / "catalog.json"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _lib.yaml_frontmatter import FrontmatterError, read  # noqa: E402

FIELDS = (
    "name",
    "description",
    "tier",
    "job",
    "best_for",
    "not_for",
    "lanes",
    "stage",
    "entrypoint",
    "consumes",
    "produces",
    "evidence_required",
    "risk_triggers",
    "max_overhead",
)


def build_catalog(skills_dir: Path) -> dict:
    skills = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            metadata = read(skill_md).metadata
        except (OSError, UnicodeDecodeError, FrontmatterError) as exc:
            raise ValueError(f"cannot read {skill_md}: {exc}") from exc
        if not metadata.get("name"):
            raise ValueError(f"skill has no name: {skill_md}")
        entry = {field: metadata[field] for field in FIELDS if field in metadata}
        entry["_path"] = f"skills/{entry['name']}"
        skills.append(entry)
    if not skills:
        raise ValueError(f"no skills found under {skills_dir}")
    return {"schema_version": 1, "skills": skills}


def render(catalog: dict) -> str:
    return json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", type=Path, default=SKILLS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit nonzero when the bundled catalog is stale",
    )
    args = parser.parse_args(argv)
    try:
        rendered = render(build_catalog(args.skills_dir))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            actual = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read {args.output}: {exc}", file=sys.stderr)
            return 1
        if actual != rendered:
            print(f"error: stale router catalog: {args.output}", file=sys.stderr)
            return 1
        print(f"router catalog current: {len(json.loads(rendered)['skills'])} skills")
        return 0

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
