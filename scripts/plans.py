#!/usr/bin/env python3
"""Plans registry CLI.

Reads forward-looking design plans under ai-docs/plans/ and provides
round-trip operations: init, list, show, promote, audit. A plan is the
artifact of *deciding to build*; promotion turns it into a behavior-
preserving spec under ai-docs/specs/ that `/refactor-subsystem` can
execute.

Subcommands:
  init <slug>        Scaffold a new plan stub (status=draft)
  list               List all plans, one line each
  show <slug>        Print one plan in full
  promote <slug>     Mark plan promoted; scaffold successor spec
  audit              Lifecycle + link drift; exit 1 if any drift

Format: ai-docs/plans/<slug>.md with frontmatter:

  name: <slug>
  title: <one-line>
  status: draft        # draft|scoped|impacted|architected|promoted|abandoned
  date: 2026-05-01
  authors: []
  motivating_decision: null   # ADR id once linked, e.g. "0001" (quoted; PyYAML 1.1 octal-shifts unquoted leading zeros)
  successor_spec: null        # spec slug once promoted
  subsystems: []
  workflows: []

Frontmatter parsing comes from scripts/_lib/yaml_frontmatter.py (PyYAML).

Exit codes: 0 = clean / results, 1 = drift / not found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_PLANS_DIR = REPO_ROOT / "ai-docs" / "plans"
DEFAULT_SPECS_DIR = REPO_ROOT / "ai-docs" / "specs"
DEFAULT_DECISIONS_DIR = REPO_ROOT / "ai-docs" / "decisions"
SPECS_SCRIPT = REPO_ROOT / "scripts" / "specs.py"

_lib_parent = str(SCRIPT_PATH.parent)
if _lib_parent not in sys.path:
    sys.path.insert(0, _lib_parent)
from _lib.yaml_frontmatter import FrontmatterError, parse  # noqa: E402

VALID_STATUSES = {
    "draft",
    "scoped",
    "impacted",
    "architected",
    "promoted",
    "abandoned",
}
SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
DECISION_ID_RE = re.compile(r"^\d{4}$")


def load_plans(plans_dir: Path) -> list[dict]:
    """Load every plan file as a dict."""
    if not plans_dir.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(plans_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        try:
            doc = parse(text, path=path)
        except FrontmatterError as exc:
            print(f"warning: skipping {path.name}: {exc}", file=sys.stderr)
            continue
        fm, body = doc.metadata, doc.body
        # PyYAML SafeLoader is YAML 1.1: unquoted leading-zero ints are octal
        # (id: 0010 → int 8). ADR ids should always be quoted strings; warn
        # and best-effort normalize when we see an int.
        md_raw = fm.get("motivating_decision")
        if isinstance(md_raw, int):
            print(
                f"warning: {path.name} motivating_decision={md_raw} is an int; "
                f'quote it (motivating_decision: "{md_raw:04d}") to avoid '
                f"YAML 1.1 octal interpretation",
                file=sys.stderr,
            )
            md_norm: str | None = f"{md_raw:04d}"
        elif md_raw is None:
            md_norm = None
        else:
            md_norm = str(md_raw)
        out.append({
            "name": str(fm.get("name") or path.stem),
            "title": str(fm.get("title") or ""),
            "status": str(fm.get("status") or "draft"),
            "date": str(fm.get("date") or ""),
            "authors": fm.get("authors") or [],
            "motivating_decision": md_norm,
            "successor_spec": fm.get("successor_spec"),
            "subsystems": fm.get("subsystems") or [],
            "workflows": fm.get("workflows") or [],
            "path": path,
            "frontmatter": fm,
            "body": body,
        })
    return out


def _scaffold_body(slug: str, title: str, today: str, motivating_decision: str | None) -> str:
    md = f'"{motivating_decision}"' if motivating_decision else "null"
    return (
        "---\n"
        f"name: {slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        f"date: {today}\n"
        "authors: []\n"
        f"motivating_decision: {md}\n"
        "successor_spec: null\n"
        "subsystems: []\n"
        "workflows: []\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## 1. Scope & Bounds\n\n"
        "_Filled by `/scope-feature`. List what is in scope, what is\n"
        "explicitly out of scope, and what counts as a non-goal._\n\n"
        "## 2. Success Criteria\n\n"
        "_Filled by `/scope-feature`. Observable outcomes that prove the\n"
        "feature works — not implementation milestones._\n\n"
        "## 3. Impact Map\n\n"
        "_Filled by `/impact-feature`. Subsystems, models, routes,\n"
        "services touched. Reach-and-blast analysis._\n\n"
        "## 4. Blast Radius\n\n"
        "_Filled by `/impact-feature`. Call sites and behaviors that\n"
        "must be preserved across the change._\n\n"
        "## 5. Architecture Fit\n\n"
        "_Filled by `/architecture-fit`. Decision conformance, canonical-\n"
        "pattern alignment, new smells introduced or avoided._\n\n"
        "## 6. Open Decisions\n\n"
        "_Filled by `/architecture-fit`. Material forks not yet decided —\n"
        "candidates for `/decide`._\n\n"
        "## 7. Promotion Notes\n\n"
        "_Filled by `/plan-spec` when promoted. What sections of the spec\n"
        "were derived from which sections of the plan; any deltas._\n"
    )


# ---- subcommands ---------------------------------------------------------

def cmd_init(args, plans_dir: Path) -> int:
    slug = args.slug
    if not SLUG_RE.match(slug):
        print(
            f"error: invalid slug {slug!r} — lowercase, [a-z0-9_-], starts with a letter",
            file=sys.stderr,
        )
        return 2
    plans_dir.mkdir(parents=True, exist_ok=True)
    path = plans_dir / f"{slug}.md"
    if path.exists() and not args.force:
        print(f"error: {path} already exists (use --force to overwrite)", file=sys.stderr)
        return 2
    md = args.motivating_decision
    if md is not None:
        md = str(md).zfill(4)
        if not DECISION_ID_RE.match(md):
            print(f"error: --motivating-decision must be a 4-digit ADR id (got {args.motivating_decision!r})", file=sys.stderr)
            return 2
        adr_path = DEFAULT_DECISIONS_DIR.glob(f"{md}-*.md")
        if not any(adr_path):
            print(f"warning: ADR {md} not found under {DEFAULT_DECISIONS_DIR}", file=sys.stderr)
    title = args.title or slug.replace("-", " ").replace("_", " ").title()
    today = args.date or _dt.date.today().isoformat()
    body = _scaffold_body(slug, title, today, md)
    path.write_text(body, encoding="utf-8")
    rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"Scaffolded plan: {rel}")
    print(f"  name:   {slug}")
    print(f"  title:  {title}")
    print("  status: draft")
    if md:
        print(f"  motivating_decision: {md}")
    print()
    print("Next steps:")
    print(f"  1. /scope-feature {slug}     (fill §1-2)")
    print(f"  2. /impact-feature {slug}    (fill §3-4)")
    print(f"  3. /architecture-fit {slug}  (fill §5-6)")
    print(f"  4. /plan-spec {slug}         (promote to spec)")
    return 0


def cmd_list(args, plans_dir: Path) -> int:
    plans = load_plans(plans_dir)
    if not plans:
        print("(no plans)")
        return 0
    if args.json:
        print(json.dumps(
            [{k: v for k, v in p.items() if k not in ("path", "frontmatter", "body")} for p in plans],
            default=str,
            indent=2,
        ))
        return 0
    for p in plans:
        suc = f" → spec:{p['successor_spec']}" if p.get("successor_spec") else ""
        title = p["title"] or "(untitled)"
        print(f"  {p['name']:<32s}  [{p['status']:<11s}]  {title}{suc}")
    return 0


def cmd_show(args, plans_dir: Path) -> int:
    plans = load_plans(plans_dir)
    matches = [p for p in plans if p["name"] == args.slug]
    if not matches:
        print(f"error: no plan matches name={args.slug!r}", file=sys.stderr)
        return 1
    print(matches[0]["path"].read_text(encoding="utf-8"))
    return 0


def cmd_promote(args, plans_dir: Path, specs_dir: Path) -> int:
    plans = load_plans(plans_dir)
    matches = [p for p in plans if p["name"] == args.slug]
    if not matches:
        print(f"error: no plan matches name={args.slug!r}", file=sys.stderr)
        return 1
    plan = matches[0]
    if plan["status"] in {"promoted", "abandoned"}:
        print(f"error: plan {plan['name']} is {plan['status']} — cannot re-promote", file=sys.stderr)
        return 2
    if plan["status"] != "architected" and not args.force:
        print(
            f"error: plan {plan['name']} is {plan['status']} (not architected) — "
            "run /architecture-fit before /plan-spec, or pass --force to override",
            file=sys.stderr,
        )
        return 2
    spec_id = args.spec_id or plan["name"]
    if not SLUG_RE.match(spec_id):
        print(f"error: invalid spec id {spec_id!r}", file=sys.stderr)
        return 2
    spec_path = specs_dir / f"{spec_id}.md"
    if spec_path.exists() and not args.force:
        print(f"error: {spec_path} already exists (use --force to overwrite)", file=sys.stderr)
        return 2
    code_roots: list[str] = list(args.code_roots or [])
    if not code_roots:
        print(
            "error: at least one --code-roots argument is required to scaffold the spec",
            file=sys.stderr,
        )
        return 2
    cmd: list[str] = [
        sys.executable,
        str(SPECS_SCRIPT),
        "init",
        spec_id,
    ]
    for root in code_roots:
        cmd.extend(["--code-roots", root])
    if plan["title"]:
        cmd.extend(["--title", plan["title"]])
    md = plan.get("motivating_decision")
    if md:
        cmd.extend(["--motivating-decision", str(md)])
    if args.allow_missing:
        cmd.append("--allow-missing")
    if args.force:
        cmd.append("--force")
    print(f"Scaffolding spec via: {' '.join(cmd)}")
    sys.stdout.flush()
    rc = subprocess.call(cmd, cwd=str(REPO_ROOT))
    if rc != 0:
        print(f"error: spec scaffold failed (rc={rc})", file=sys.stderr)
        return rc
    text = plan["path"].read_text(encoding="utf-8")
    new_text, status_subs = re.subn(
        r"^status:.*$", "status: promoted", text, count=1, flags=re.MULTILINE,
    )
    new_text, succ_subs = re.subn(
        r"^successor_spec:.*$", f"successor_spec: {spec_id}", new_text, count=1, flags=re.MULTILINE,
    )
    if status_subs != 1 or succ_subs != 1:
        # Plan frontmatter missing one of the required fields — the spec
        # exists but the plan can't be marked promoted. Roll back the
        # spec scaffold so the next attempt is clean.
        try:
            spec_path.unlink()
        except OSError:
            pass
        print(
            f"error: plan frontmatter missing status/successor_spec lines "
            f"(status_subs={status_subs}, succ_subs={succ_subs}); "
            f"scaffold spec rolled back. Re-init the plan via "
            f"`scripts/plans.py init {plan['name']}` or hand-fix frontmatter.",
            file=sys.stderr,
        )
        return 3
    plan["path"].write_text(new_text, encoding="utf-8")
    print(f"Promoted plan {plan['name']} → spec:{spec_id}")
    print("  Plan status:   promoted")
    print(f"  Spec scaffold: ai-docs/specs/{spec_id}.md")
    return 0


def _audit_drift(plans: list[dict], specs_dir: Path, decisions_dir: Path) -> list[str]:
    diags: list[str] = []
    for p in plans:
        if p["status"] not in VALID_STATUSES:
            diags.append(f"{p['name']}: invalid status {p['status']!r} (allowed: {sorted(VALID_STATUSES)})")
        if p["status"] == "promoted":
            sp = p.get("successor_spec")
            if not sp:
                diags.append(f"{p['name']}: status=promoted but successor_spec is unset")
            elif not (specs_dir / f"{sp}.md").exists():
                diags.append(f"{p['name']}: successor_spec {sp} → spec file does not exist")
        md = p.get("motivating_decision")
        if md:
            md_id = str(md).zfill(4)
            if not list(decisions_dir.glob(f"{md_id}-*.md")):
                diags.append(f"{p['name']}: motivating_decision {md_id} → ADR does not exist")
    return diags


def cmd_audit(args, plans_dir: Path, specs_dir: Path, decisions_dir: Path) -> int:
    plans = load_plans(plans_dir)
    diags = _audit_drift(plans, specs_dir, decisions_dir)
    if args.json:
        print(json.dumps({
            "count": len(plans),
            "drift_count": len(diags),
            "drift": diags,
            "plans": [{k: v for k, v in p.items() if k not in ("path", "frontmatter", "body")} for p in plans],
        }, default=str, indent=2))
        return 1 if diags else 0
    if not diags:
        print(f"OK — {len(plans)} plans, no drift")
        return 0
    for d in diags:
        print(d)
    return 1


# ---- main ----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plans registry CLI for ai-docs/plans/.")
    parser.add_argument("--plans-dir", type=Path, default=DEFAULT_PLANS_DIR)
    parser.add_argument("--specs-dir", type=Path, default=DEFAULT_SPECS_DIR)
    parser.add_argument("--decisions-dir", type=Path, default=DEFAULT_DECISIONS_DIR)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Scaffold a new plan")
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument("--date")
    p.add_argument("--motivating-decision", help="ADR id (e.g. 0001) that motivates this plan")
    p.add_argument("--force", action="store_true", help="Overwrite if the file exists")

    p = sub.add_parser("list", help="List all plans")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("show", help="Print one plan in full")
    p.add_argument("slug")

    p = sub.add_parser("promote", help="Promote plan → scaffold a spec, mark plan promoted")
    p.add_argument("slug")
    p.add_argument("--spec-id", help="Spec slug (defaults to plan slug)")
    p.add_argument("--code-roots", action="append", help="Spec code roots (repeat)", required=True)
    p.add_argument("--allow-missing", action="store_true", help="Allow missing code roots in scaffold")
    p.add_argument("--force", action="store_true", help="Overwrite existing spec")

    p = sub.add_parser("audit", help="Lifecycle + link drift checks")
    p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "init":
        return cmd_init(args, args.plans_dir)
    if args.cmd == "list":
        return cmd_list(args, args.plans_dir)
    if args.cmd == "show":
        return cmd_show(args, args.plans_dir)
    if args.cmd == "promote":
        return cmd_promote(args, args.plans_dir, args.specs_dir)
    if args.cmd == "audit":
        return cmd_audit(args, args.plans_dir, args.specs_dir, args.decisions_dir)
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
