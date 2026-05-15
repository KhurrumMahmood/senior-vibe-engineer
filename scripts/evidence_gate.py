#!/usr/bin/env python3
"""Evidence gate (PR D).

Soft check that a skill's `evidence_required` frontmatter tokens were
produced by a given scan. Reads the skill's SKILL.md frontmatter via the
shared parser, then validates a per-scan `evidence.json` manifest:

  reports/<skill>/scan-<TS>/
  +-- evidence.json    <- mapping from each required token to a path

Each token in `evidence_required` must (a) appear in the manifest's
`evidence` map with a non-empty path, and (b) point at a file that
exists on disk (paths are interpreted relative to the scan-dir).

Subcommands:
  check --skill <name> --scan-dir <path>   Validate manifest vs frontmatter
  init  --skill <name> --scan-dir <path>   Scaffold a stub manifest
  show  --skill <name>                     Print the skill's requirements

Exit codes:
  0  pass / no requirements / scaffold succeeded
  1  evidence missing / declared file not found / refuse to overwrite
  2  usage error (unknown skill, missing arg, scan-dir absent)

Soft gate by design — never refuses to do other work, never edits
production code. PR F will wire this into CI; PR G will turn the
warnings into hard refusals where appropriate.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
MANIFEST_FILENAME = "evidence.json"

_lib_parent = str(SCRIPT_PATH.parent)
if _lib_parent not in sys.path:
    sys.path.insert(0, _lib_parent)
from _lib.yaml_frontmatter import FrontmatterError, read  # noqa: E402


def _load_skill_frontmatter(skill: str, skills_dir: Path) -> dict[str, Any]:
    skill_md = skills_dir / skill / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"no SKILL.md for /{skill} at {skill_md}")
    try:
        doc = read(skill_md)
    except FrontmatterError as exc:
        raise ValueError(f"frontmatter error in {skill_md}: {exc}") from exc
    return doc.metadata


def _required_tokens(fm: dict[str, Any]) -> list[str]:
    raw = fm.get("evidence_required") or []
    if not isinstance(raw, list):
        return []
    return [t for t in raw if isinstance(t, str) and t.strip()]


def _check_paths(manifest_evidence: dict[str, Any], required: list[str], scan_dir: Path) -> list[dict[str, Any]]:
    """Return one row per required token with status / path / reason."""
    rows: list[dict[str, Any]] = []
    for token in required:
        declared = manifest_evidence.get(token)
        if not declared or not isinstance(declared, str) or not declared.strip():
            rows.append({"token": token, "status": "missing_token", "path": None})
            continue
        candidate = Path(declared)
        if not candidate.is_absolute():
            candidate = scan_dir / candidate
        if not candidate.exists():
            rows.append({"token": token, "status": "missing_file", "path": declared})
            continue
        rows.append({"token": token, "status": "ok", "path": declared})
    return rows


def _render_text(skill: str, scan_dir: Path, rows: list[dict[str, Any]], summary: str) -> str:
    lines = [f"Evidence gate for /{skill} on {scan_dir}:"]
    for row in rows:
        marker = "[ok]" if row["status"] == "ok" else "[FAIL]"
        if row["status"] == "ok":
            lines.append(f"  {marker} {row['token']} -> {row['path']}")
        elif row["status"] == "missing_token":
            lines.append(f"  {marker} {row['token']} -> MISSING (no path declared in manifest)")
        else:
            lines.append(f"  {marker} {row['token']} -> DECLARED but file not found at {row['path']}")
    lines.append("")
    lines.append(summary)
    return "\n".join(lines)


def cmd_check(args: argparse.Namespace) -> int:
    skills_dir = Path(args.skills_dir).resolve()
    try:
        fm = _load_skill_frontmatter(args.skill, skills_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    scan_dir = Path(args.scan_dir).resolve()
    if not scan_dir.is_dir():
        print(f"error: scan-dir not found: {scan_dir}", file=sys.stderr)
        return 2

    required = _required_tokens(fm)

    if not required:
        payload = {
            "skill": args.skill,
            "scan_dir": str(scan_dir),
            "status": "no_requirements",
            "rows": [],
            "required_total": 0,
            "ok_total": 0,
        }
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print(f"Evidence gate for /{args.skill} on {scan_dir}:")
            print(f"  /{args.skill} declares no evidence_required. Nothing to check.")
        return 0

    manifest_path = scan_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        payload = {
            "skill": args.skill,
            "scan_dir": str(scan_dir),
            "status": "no_manifest",
            "manifest_path": str(manifest_path),
            "required": required,
        }
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print(f"Evidence gate for /{args.skill} on {scan_dir}:")
            print(f"  [FAIL] no manifest found at {manifest_path}")
            print(f"  Required tokens: {', '.join(required)}")
            print(f"  Hint: scaffold one with `evidence_gate.py init --skill {args.skill} --scan-dir {scan_dir}`.")
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: malformed manifest at {manifest_path}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(manifest, dict):
        print(f"error: manifest at {manifest_path} must be a JSON object", file=sys.stderr)
        return 2

    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}

    rows = _check_paths(evidence, required, scan_dir)
    ok_total = sum(1 for r in rows if r["status"] == "ok")
    status = "pass" if ok_total == len(required) else "fail"
    summary = f"{'OK' if status == 'pass' else 'FAIL'}: {ok_total}/{len(required)} required evidence shapes present."

    if args.json:
        print(json.dumps({
            "skill": args.skill,
            "scan_dir": str(scan_dir),
            "manifest_path": str(manifest_path),
            "status": status,
            "rows": rows,
            "required_total": len(required),
            "ok_total": ok_total,
        }, sort_keys=True))
    else:
        print(_render_text(args.skill, scan_dir, rows, summary))

    return 0 if status == "pass" else 1


def cmd_init(args: argparse.Namespace) -> int:
    skills_dir = Path(args.skills_dir).resolve()
    try:
        fm = _load_skill_frontmatter(args.skill, skills_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    scan_dir = Path(args.scan_dir).resolve()
    if not scan_dir.is_dir():
        print(f"error: scan-dir not found: {scan_dir}", file=sys.stderr)
        return 2

    required = _required_tokens(fm)
    if not required:
        msg = f"/{args.skill} declares no evidence_required. Nothing to scaffold."
        if args.json:
            print(json.dumps({"skill": args.skill, "status": "no_requirements", "message": msg}, sort_keys=True))
        else:
            print(msg)
        return 0

    manifest_path = scan_dir / MANIFEST_FILENAME
    if manifest_path.exists() and not args.force:
        msg = f"manifest already exists at {manifest_path}; pass --force to overwrite."
        if args.json:
            print(json.dumps({"skill": args.skill, "status": "exists", "manifest_path": str(manifest_path), "message": msg}, sort_keys=True))
        else:
            print(f"error: {msg}", file=sys.stderr)
        return 1

    stub = {
        "skill": args.skill,
        "scan_id": scan_dir.name,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence": {token: "" for token in required},
        "notes": "",
    }
    manifest_path.write_text(json.dumps(stub, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({"skill": args.skill, "status": "scaffolded", "manifest_path": str(manifest_path), "required": required}, sort_keys=True))
    else:
        print(f"scaffolded {manifest_path} with {len(required)} required token(s):")
        for token in required:
            print(f"  - {token}")
        print("Fill in each path (relative to the scan-dir) before running `check`.")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    skills_dir = Path(args.skills_dir).resolve()
    try:
        fm = _load_skill_frontmatter(args.skill, skills_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    required = _required_tokens(fm)
    payload = {
        "skill": args.skill,
        "evidence_required": required,
        "produces": fm.get("produces") if isinstance(fm.get("produces"), list) else [],
        "consumes": fm.get("consumes") if isinstance(fm.get("consumes"), list) else [],
    }
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"/{args.skill}:")
        if required:
            print("  evidence_required:")
            for token in required:
                print(f"    - {token}")
        else:
            print("  evidence_required: (none declared)")
        if payload["produces"]:
            print("  produces:")
            for token in payload["produces"]:
                print(f"    - {token}")
        if payload["consumes"]:
            print("  consumes:")
            for token in payload["consumes"]:
                print(f"    - {token}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skills-dir", default=str(DEFAULT_SKILLS_DIR),
                        help=f"Skills root (default: {DEFAULT_SKILLS_DIR})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="Validate evidence manifest against skill frontmatter")
    p_check.add_argument("--skill", required=True)
    p_check.add_argument("--scan-dir", required=True)
    p_check.add_argument("--json", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_init = sub.add_parser("init", help="Scaffold an evidence.json stub from skill frontmatter")
    p_init.add_argument("--skill", required=True)
    p_init.add_argument("--scan-dir", required=True)
    p_init.add_argument("--force", action="store_true", help="Overwrite an existing manifest")
    p_init.add_argument("--json", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_show = sub.add_parser("show", help="Print evidence_required / produces / consumes for a skill")
    p_show.add_argument("--skill", required=True)
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
