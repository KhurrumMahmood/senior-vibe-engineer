#!/usr/bin/env python3
"""Decision registry CLI.

Reads architectural decision records (ADRs) under ai-docs/decisions/ and
provides round-trip operations for the registry: create, list, show,
audit, and link-check.

Subcommands:
  init <slug>       Scaffold a new ADR with auto-assigned id
  list              List all decisions, one line each
  show <id>         Print one decision in full
  rebuild           Rebuild reports/architecture/decision-index.json
  audit             Run drift checks; exit 1 if any drift
  link-check        Verify supersedes/superseded_by chains and applies_to paths

Format: ai-docs/decisions/<NNNN>-<slug>.md with frontmatter:

  id: "0001"          # quoted: PyYAML SafeLoader parses unquoted 0010 as octal 8
  title: Use TextChoices for all status fields
  status: accepted
  date: 2026-04-30
  deciders: [khurrum]
  supersedes: []
  superseded_by: null
  applies_to: [core/]
  tags: [stringly-state, lint]
  related_smell: stringly-typed-state
  related_pattern: stringly-status

Frontmatter parsing comes from scripts/_lib/yaml_frontmatter.py (PyYAML).

Exit codes: 0 = clean / results, 1 = drift / not found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_DECISIONS_DIR = REPO_ROOT / "ai-docs" / "decisions"
DEFAULT_INDEX_PATH = REPO_ROOT / "reports" / "architecture" / "decision-index.json"

_lib_parent = str(SCRIPT_PATH.parent)
if _lib_parent not in sys.path:
    sys.path.insert(0, _lib_parent)
from _lib.yaml_frontmatter import FrontmatterError, parse  # noqa: E402

VALID_STATUSES = {"proposed", "accepted", "superseded", "deprecated"}
ID_RE = re.compile(r"^(\d{4})-([a-z][a-z0-9_-]*)\.md$")
SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
PROPOSED_AGE_DAYS = 30


def load_decisions(decisions_dir: Path) -> list[dict]:
    """Load every decision file as a dict with id/title/status/path/frontmatter/body."""
    if not decisions_dir.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(decisions_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        m = ID_RE.match(path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        try:
            doc = parse(text, path=path)
        except FrontmatterError as exc:
            print(f"warning: skipping {path.name}: {exc}", file=sys.stderr)
            continue
        fm, body = doc.metadata, doc.body
        # The filename is the source of truth for ADR id. YAML 1.1 (PyYAML
        # SafeLoader) parses unquoted leading-zero ints as octal, so id: 0010
        # silently becomes int 8. If the frontmatter id disagrees with the
        # filename, warn — the file should quote the id (id: "0010").
        file_id = m.group(1)
        raw_id = fm.get("id")
        if raw_id is not None:
            try:
                fm_id = f"{int(raw_id):04d}"
            except (TypeError, ValueError):
                fm_id = str(raw_id)
            if fm_id != file_id and str(raw_id) != file_id:
                print(
                    f"warning: {path.name} frontmatter id={raw_id!r} disagrees with "
                    f"filename id={file_id} (likely YAML 1.1 octal); quote the id "
                    f'(id: "{file_id}") to silence this',
                    file=sys.stderr,
                )
        out.append({
            "id": file_id,
            "slug": m.group(2),
            "title": str(fm.get("title") or ""),
            "status": str(fm.get("status") or "proposed"),
            "date": str(fm.get("date") or ""),
            "supersedes": fm.get("supersedes") or [],
            "superseded_by": fm.get("superseded_by"),
            "applies_to": fm.get("applies_to") or [],
            "tags": fm.get("tags") or [],
            "related_smell": fm.get("related_smell"),
            "related_pattern": fm.get("related_pattern"),
            "path": path,
            "frontmatter": fm,
            "body": body,
        })
    return out


# ---- subcommands ---------------------------------------------------------

def cmd_init(args, decisions_dir: Path) -> int:
    slug = args.slug
    if not SLUG_RE.match(slug):
        print(f"error: invalid slug {slug!r} — lowercase, [a-z0-9_-], starts with a letter", file=sys.stderr)
        return 2
    existing = load_decisions(decisions_dir)
    next_id = max((int(d["id"]) for d in existing), default=0) + 1
    decisions_dir.mkdir(parents=True, exist_ok=True)
    path = decisions_dir / f"{next_id:04d}-{slug}.md"
    if path.exists():
        print(f"error: {path} already exists", file=sys.stderr)
        return 2
    title = args.title or slug.replace("-", " ").replace("_", " ").title()
    today = args.date or _dt.date.today().isoformat()
    body = (
        "---\n"
        f'id: "{next_id:04d}"\n'
        f"title: {title}\n"
        "status: proposed\n"
        f"date: {today}\n"
        "deciders: []\n"
        "supersedes: []\n"
        "superseded_by: null\n"
        "applies_to: []\n"
        "tags: []\n"
        "related_smell: null\n"
        "related_pattern: null\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Context\n\n_(why is this decision needed? what changed?)_\n\n"
        "## Decision\n\n_(the choice in one sentence, then enough prose to be unambiguous)_\n\n"
        "## Alternatives considered\n\n_(what else was on the table; why each was rejected)_\n\n"
        "## Consequences\n\n_(what becomes easier; what becomes harder; what is now disallowed)_\n\n"
        "## Verification\n\n_(how will we know this decision was followed? lint rule? characterization test? doc backref?)_\n"
    )
    path.write_text(body, encoding="utf-8")
    print(f"Scaffolded ADR: {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    print(f"  id:    {next_id:04d}")
    print(f"  title: {title}")
    print("  status: proposed")
    return 0


def cmd_list(args, decisions_dir: Path) -> int:
    decisions = load_decisions(decisions_dir)
    if not decisions:
        print("(no decisions)")
        return 0
    if args.json:
        print(json.dumps([{k: v for k, v in d.items() if k not in ("path", "frontmatter", "body")} for d in decisions], default=str, indent=2))
        return 0
    for d in decisions:
        sup = f" (superseded by {d['superseded_by']})" if d.get("superseded_by") else ""
        print(f"  {d['id']}  [{d['status']:11s}]  {d['title']}{sup}")
    return 0


def cmd_show(args, decisions_dir: Path) -> int:
    decisions = load_decisions(decisions_dir)
    target = args.id.lstrip("0") or "0"
    matches = [d for d in decisions if d["id"].lstrip("0") == target or d["id"] == args.id]
    if not matches:
        print(f"error: no decision matches id={args.id!r}", file=sys.stderr)
        return 1
    print(matches[0]["path"].read_text(encoding="utf-8"))
    return 0


def cmd_rebuild(args, decisions_dir: Path, index_path: Path) -> int:
    decisions = load_decisions(decisions_dir)
    index = {
        "version": 1,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "count": len(decisions),
        "decisions": [
            {k: v for k, v in d.items() if k not in ("path", "frontmatter", "body")}
            | {"path": str(d["path"].relative_to(REPO_ROOT))}
            for d in decisions
        ],
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, default=str, indent=2) + "\n", encoding="utf-8")
    print(f"Rebuilt {index_path.relative_to(REPO_ROOT)} ({len(decisions)} decisions)")
    return 0


def _audit_drift(decisions: list[dict]) -> list[str]:
    """Return human-readable drift diagnostics, empty list = clean."""
    diags: list[str] = []
    today = _dt.date.today()
    by_id = {d["id"]: d for d in decisions}
    for d in decisions:
        if d["status"] not in VALID_STATUSES:
            diags.append(f"{d['id']}: invalid status {d['status']!r} (allowed: {sorted(VALID_STATUSES)})")
        if d["status"] == "proposed" and d["date"]:
            try:
                age = (today - _dt.date.fromisoformat(d["date"])).days
                if age > PROPOSED_AGE_DAYS:
                    diags.append(f"{d['id']}: proposed for {age} days (>{PROPOSED_AGE_DAYS}) — accept or reject")
            except ValueError:
                diags.append(f"{d['id']}: malformed date {d['date']!r}")
        for sup_id in d.get("supersedes") or []:
            sup_id = str(sup_id).zfill(4)
            if sup_id not in by_id:
                diags.append(f"{d['id']}: supersedes {sup_id} which does not exist")
        sb = d.get("superseded_by")
        if sb and str(sb).zfill(4) not in by_id:
            diags.append(f"{d['id']}: superseded_by {sb} which does not exist")
    return diags


def cmd_audit(args, decisions_dir: Path) -> int:
    decisions = load_decisions(decisions_dir)
    diags = _audit_drift(decisions)
    if args.json:
        print(json.dumps({"count": len(decisions), "drift_count": len(diags), "drift": diags, "decisions": [{k: v for k, v in d.items() if k not in ("path", "frontmatter", "body")} for d in decisions]}, default=str, indent=2))
        return 1 if diags else 0
    if not diags:
        print(f"OK — {len(decisions)} decisions, no drift")
        return 0
    for d in diags:
        print(d)
    return 1


def cmd_link_check(args, decisions_dir: Path) -> int:
    decisions = load_decisions(decisions_dir)
    diags: list[str] = []
    for d in decisions:
        for sup_id in d.get("supersedes") or []:
            sup_id = str(sup_id).zfill(4)
            if not any(o["id"] == sup_id for o in decisions):
                diags.append(f"{d['id']}: supersedes {sup_id} → not found")
        sb = d.get("superseded_by")
        if sb and not any(o["id"] == str(sb).zfill(4) for o in decisions):
            diags.append(f"{d['id']}: superseded_by {sb} → not found")
        for path_str in d.get("applies_to") or []:
            applies_path = REPO_ROOT / str(path_str)
            if not applies_path.exists():
                diags.append(f"{d['id']}: applies_to {path_str} → path does not exist")
    if not diags:
        print(f"OK — {len(decisions)} decisions, all links resolve")
        return 0
    for d in diags:
        print(d)
    return 1


# ---- main ----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decision registry CLI for ai-docs/decisions/.")
    parser.add_argument("--decisions-dir", type=Path, default=DEFAULT_DECISIONS_DIR)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Scaffold a new ADR")
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument("--date")

    p = sub.add_parser("list", help="List all decisions")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("show", help="Print one decision in full")
    p.add_argument("id")

    sub.add_parser("rebuild", help="Rebuild decision-index.json")

    p = sub.add_parser("audit", help="Run drift checks")
    p.add_argument("--json", action="store_true")

    sub.add_parser("link-check", help="Verify supersedes / applies_to links")

    args = parser.parse_args(argv)
    if args.cmd == "init":
        return cmd_init(args, args.decisions_dir)
    if args.cmd == "list":
        return cmd_list(args, args.decisions_dir)
    if args.cmd == "show":
        return cmd_show(args, args.decisions_dir)
    if args.cmd == "rebuild":
        return cmd_rebuild(args, args.decisions_dir, args.index_path)
    if args.cmd == "audit":
        return cmd_audit(args, args.decisions_dir)
    if args.cmd == "link-check":
        return cmd_link_check(args, args.decisions_dir)
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
