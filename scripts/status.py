#!/usr/bin/env python3
"""Project status projection — one derived, versioned status.json.

Composes existing sources (plans, decisions, specs, idea ledger, judged sweep
digest, proposal chains, queue) into
`.engineering/local/status.json` per ADR 0037. Deterministic, agent-free,
read-only: every section degrades to an absent-marker when its source is
missing (exit 0 — ADR 0023 precedent), and nothing here ever writes into
a skill's report directory or invokes `sweep.py` (whose `ratchet`
rewrites its baseline in place).

The projection is derived and advisory — never authoritative over its
sources, and never a write target for any skill.

Source decision: `core:status-projection-schema` (ADR 0037).
"""
# spec:status-projection-and-presentation::IM-2
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCRIPT_PATH = Path(__file__).resolve()
TOOLKIT_ROOT = SCRIPT_PATH.parent.parent

_scripts_dir = str(SCRIPT_PATH.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _lib import artifact_scope, status_schema  # noqa: E402
from _lib.status_schema import absent  # noqa: E402
from sweep.pipeline import JudgmentGateError, validate_judged_digest  # noqa: E402

import plans as plans_mod  # noqa: E402
import specs as specs_mod  # noqa: E402


def _load_module(name: str, rel_path: str):
    """Import a non-package toolkit module by file location (shared loaders)."""
    path = TOOLKIT_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {rel_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ideas_lib = _load_module("status_ideas_lib", ".claude/skills/_common/ideas_lib.py")
_eng_home = _load_module("status_engineering_home", ".claude/skills/_common/engineering_home.py")
_project_state = _load_module(
    "status_project_state", ".claude/skills/find-standard-gaps/scripts/project_state.py"
)


# --- sections ---------------------------------------------------------------


def section_lifecycle(root: Path) -> dict[str, Any]:
    eng = root / ".engineering"
    if not eng.is_dir():
        return absent("no .engineering/ directory")
    ok, version = _eng_home.check_version(root)
    state = _project_state.load_project_state(root)
    project_dir = _eng_home.project_dir(root)
    return {
        "available": True,
        "engineering_manifest_version": version,
        "engineering_manifest_ok": ok,
        "project_state": state,  # null = undeclared (consumers assume MAX per ADR 0020)
        "adapter_present": (project_dir / "adapter.yml").is_file(),
        "profile_present": (project_dir / "profile.yml").is_file(),
        "open_questions_present": (project_dir / "open-questions.md").is_file(),
    }


def section_in_flight(root: Path) -> dict[str, Any]:
    plans_dir = root / "ai-docs" / "plans"
    specs_dir = root / "ai-docs" / "specs"
    ledger_path = root / ".claude" / "ideas" / "log.jsonl"
    if not (plans_dir.is_dir() or specs_dir.is_dir() or ledger_path.is_file()):
        return absent("no plans, specs, or idea ledger present")

    plans = [
        {"name": p["name"], "status": p["status"], "successor_spec": p["successor_spec"]}
        for p in plans_mod.load_plans(plans_dir)
    ]
    spec_rows = []
    if specs_dir.is_dir():
        for s in specs_mod.load_all_specs(specs_dir):
            spec_rows.append({"id": s.spec_id, "status": s.status})

    ideas: dict[str, Any] = {"available": False, "reason": "no idea ledger"}
    if ledger_path.is_file():
        projections = _ideas_lib.project_all(_ideas_lib.load_ledger(ledger_path))
        by_state: dict[str, int] = {}
        for proj in projections.values():
            by_state[proj["state"]] = by_state.get(proj["state"], 0) + 1
        ideas = {
            "available": True,
            "total": len(projections),
            "by_state": dict(sorted(by_state.items())),
            "in_flight": sorted(i for i, p in projections.items() if p["state"] == "in-flight"),
        }

    non_terminal = {"draft", "scoped", "impacted", "architected"}
    return {
        "available": True,
        "plans": sorted(plans, key=lambda r: r["name"]),
        "active_plans": sorted(p["name"] for p in plans if p["status"] in non_terminal),
        "specs": sorted(spec_rows, key=lambda r: r["id"]),
        "ideas": ideas,
    }


def resolve_sweep_digest(root: Path, override: Path | None) -> Path | None:
    """Resolve only the judgment-gated sweep projection, never raw findings."""
    candidates = [override] if override else [
        root / ".engineering" / "local" / "sweep" / "digest.json",
    ]
    for c in candidates:
        if c and c.is_file():
            return c
    return None


def section_structural_health(root: Path, digest_override: Path | None) -> dict[str, Any]:
    digest_path = resolve_sweep_digest(root, digest_override)
    if digest_path is None:
        return absent("no judged sweep digest found")
    try:
        digest = json.loads(digest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return absent(f"judged sweep digest unreadable: {exc}")
    try:
        validated = validate_judged_digest(digest)
    except JudgmentGateError as exc:
        return absent(f"judged sweep digest invalid: {exc}")
    mtime = datetime.fromtimestamp(digest_path.stat().st_mtime, tz=timezone.utc)
    return {
        "available": True,
        "digest_path": str(digest_path),
        "digest_mtime": mtime.isoformat(),
        "manifest_hash": validated["manifest_hash"],
        "judgment_hash": validated["judgment_hash"],
        "digest_hash": validated["digest_hash"],
        "total_actionable": validated["total_actionable"],
        "omitted_actionable": validated["omitted_actionable"],
        "counts": dict(validated["counts"]),
        "severity_histogram": dict(validated["severity_histogram"]),
        "outcomes": dict(validated["outcomes"]),
        "finding_ids": list(validated["finding_ids"]),
    }


# spec:status-projection-and-presentation::IM-3
_LINT_PATH_RE = re.compile(r"scripts/lint/[a-z0-9_]+\.py")
_SPEC_PATH_RE = re.compile(r"ai-docs/specs/[A-Za-z0-9_-]+\.md")


def _chain_closure(root: Path, proposal_md: Path, closure: str) -> bool:
    """Best-effort closure for the two detectable chains (AR-11)."""
    if closure == "none":
        return False
    try:
        text = proposal_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False  # noqa: silent-catch: unreadable proposal = not provably closed; stays pending
    pattern = _LINT_PATH_RE if closure == "installed_lint" else _SPEC_PATH_RE
    mentioned = pattern.findall(text)
    return bool(mentioned) and any((root / m).is_file() for m in mentioned)


def section_pending_approvals(root: Path, now: datetime) -> dict[str, Any]:
    reports = root / "reports"
    if not reports.is_dir():
        return absent("no reports/ directory")
    items = []
    for chain in status_schema.PROPOSAL_CHAINS:
        chain_dir = reports / chain["skill"]
        if not chain_dir.is_dir():
            continue
        for proposal_dir in sorted(p for p in chain_dir.iterdir() if p.is_dir()):
            proposal_md = proposal_dir / "proposal.md"
            if not proposal_md.is_file():
                continue
            if any((proposal_dir / m).is_file() for m in status_schema.DISMISSAL_MARKERS):
                status = status_schema.APPROVAL_DISMISSED
            elif _chain_closure(root, proposal_md, chain["closure"]):
                status = status_schema.APPROVAL_CLOSED
            else:
                status = status_schema.APPROVAL_PENDING
            mtime = datetime.fromtimestamp(proposal_md.stat().st_mtime, tz=timezone.utc)
            items.append({
                "chain": chain["skill"],
                "id": proposal_dir.name,
                "status": status,
                "closure_detectable": chain["closure"] != "none",
                "age_days": max(0, (now - mtime).days),
                "path": str(proposal_dir.relative_to(root)),
            })
    pending = [i for i in items if i["status"] == status_schema.APPROVAL_PENDING]
    return {
        "available": True,
        "pending_count": len(pending),
        "items": sorted(items, key=lambda i: (i["chain"], i["id"])),
    }


# spec:status-projection-and-presentation::IM-6
def _last_commit_touching(root: Path, paths: list[str]) -> datetime | None:
    out = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%cI", "--", *paths],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout.strip()
    return datetime.fromisoformat(out) if out else None


def section_staleness(root: Path, now: datetime) -> dict[str, Any]:
    reports = root / "reports"
    if not reports.is_dir():
        return absent("no reports/ directory")
    sidecars = sorted(
        set(reports.glob(f"*/{artifact_scope.SIDECAR_NAME}"))
        | set(reports.glob(f"*/*/{artifact_scope.SIDECAR_NAME}"))
    )
    artifacts = []
    for sidecar in sidecars:
        scope = artifact_scope.read_scope(sidecar.parent)
        if scope is None:
            continue
        written_raw = scope.get("written_at", "")
        try:
            written_at = datetime.fromisoformat(written_raw)
        except (TypeError, ValueError):
            continue  # noqa: silent-catch: malformed timestamp = untracked artifact, skip by design
        try:
            last_commit = _last_commit_touching(root, scope["paths"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return absent("git unavailable — input-drift staleness cannot be computed")
        state = (
            status_schema.STALE
            if last_commit is not None and last_commit > written_at
            else status_schema.FRESH
        )
        artifacts.append({
            "artifact": str(sidecar.parent.relative_to(root)),
            "state": state,
            "scope_written_at": written_raw,
            "last_input_commit": last_commit.isoformat() if last_commit else None,
        })
    return {
        "available": True,
        "stale_count": sum(1 for a in artifacts if a["state"] == status_schema.STALE),
        "artifacts": artifacts,
    }


def section_queue(root: Path) -> dict[str, Any]:
    queue_dir = root / ".engineering" / "local" / "queue"
    if not queue_dir.is_dir():
        return absent("no queue directory")
    items = []
    for item_path in sorted(queue_dir.glob("*.json")):
        try:
            item = json.loads(item_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            items.append({"id": item_path.stem, "status": "unreadable", "staged_at": None})
            continue
        items.append({
            "id": item_path.stem,
            "status": item.get("status", "staged"),
            "staged_at": item.get("staged_at"),
        })
    return {"available": True, "count": len(items), "items": items}


def section_goals(root: Path) -> dict[str, Any]:
    return absent("reserved in schema v1 — no goal artifact convention defined yet")


# --- assembly ----------------------------------------------------------------


def build_status(root: Path, sweep_digest: Path | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    builders: dict[str, Callable[[], dict[str, Any]]] = {
        "lifecycle": lambda: section_lifecycle(root),
        "structural_health": lambda: section_structural_health(root, sweep_digest),
        "pending_approvals": lambda: section_pending_approvals(root, now),
        "in_flight": lambda: section_in_flight(root),
        "staleness": lambda: section_staleness(root, now),
        "queue": lambda: section_queue(root),
        "goals": lambda: section_goals(root),
    }
    sections: dict[str, Any] = {}
    for name in status_schema.SECTIONS:
        try:
            sections[name] = builders[name]()
        except Exception as exc:  # noqa: BLE001 — section isolation: one broken source must not kill the projection
            print(f"warning: section {name} failed: {exc}", file=sys.stderr)
            sections[name] = absent(f"error: {exc}")
    return {
        "schema_version": status_schema.SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "root": str(root),
        "sections": sections,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the project status projection.")
    parser.add_argument("--root", type=Path, default=TOOLKIT_ROOT)
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output path (default: <root>/.engineering/local/status.json).",
    )
    parser.add_argument(
        "--sweep-digest",
        type=Path,
        default=None,
        help="Judgment-gated sweep digest override; raw manifests are rejected.",
    )
    parser.add_argument("--print", action="store_true", dest="print_doc")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    doc = build_status(root, args.sweep_digest)
    errors = status_schema.validate(doc)
    if errors:  # contract self-check; a failure here is a producer bug
        for e in errors:
            print(f"error: schema: {e}", file=sys.stderr)
        return 2

    out = args.out or root / ".engineering" / "local" / "status.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {out}: {exc}", file=sys.stderr)
        return 2
    if args.print_doc:
        print(json.dumps(doc, indent=1, sort_keys=True))
    available = sorted(k for k, v in doc["sections"].items() if v.get("available"))
    print(f"status.json written: {out} ({len(available)}/{len(status_schema.SECTIONS)} sections available: {', '.join(available) or 'none'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
