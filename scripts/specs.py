#!/usr/bin/env python
"""
Spec index CLI for requirements-first workflow.

Reads concern-based specs under ai-docs/specs/, parses checklist items and
frontmatter, greps code_roots for `# spec:<id>::<item>` comments, and reports
drift between what the spec claims and what the code does.

Subcommands:
  init              Scaffold a new stub spec for a legacy code cluster
  list              List specs with status + item counts
  show              Show one spec's checklist + code refs
  rebuild           Rebuild spec-index.json (mechanical grep pass)
  coverage          Audit one spec's checklist against code comments
  orphans           Find code refs pointing at missing spec items
  audit             Run coverage across every spec; exit 1 if any drift
  solid             Run SOLID quality gates for a spec (Phase 6.3 harness)
  size-check        Warn/error specs that exceed LOC soft/hard caps
  inventory-check   Verify a spec's narrative inventory matches code symbols
  violations        Grep anti-patterns declared in a spec and report compliance

Backing store: ai-docs/specs/*.md (authored; `init` is the only mutator).
Built artifact: reports/architecture/spec-index.json (built by `rebuild`).

Usage:
  .venv/bin/python scripts/specs.py init crawling-views \\
      --code-roots core/views/crawling.py
  .venv/bin/python scripts/specs.py list
  .venv/bin/python scripts/specs.py show async-tasks
  .venv/bin/python scripts/specs.py rebuild
  .venv/bin/python scripts/specs.py coverage async-tasks
  .venv/bin/python scripts/specs.py audit --json
  .venv/bin/python scripts/specs.py size-check
  .venv/bin/python scripts/specs.py inventory-check async-tasks --strict
  .venv/bin/python scripts/specs.py violations async-tasks --json

Exit codes: 0 = clean / results, 1 = drift / no results, 2 = usage error.
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import fnmatch
import hashlib
import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_SPECS_DIR = REPO_ROOT / "ai-docs" / "specs"
DEFAULT_INDEX_PATH = REPO_ROOT / "reports" / "architecture" / "spec-index.json"
INDEX_VERSION = 1

VALID_SECTIONS = ("G", "AR", "IM", "LR-U", "LR-T", "EX")
CHECKABLE_SECTIONS = {"IM", "AR", "EX"}  # LR-* is append-only, no markers

SIZE_SOFT_LOC = 500
SIZE_HARD_LOC = 1000

# SOLID quality gate thresholds (Phase 6.3 — applied to code files, not spec files)
SOLID_RECHECK_LOC = 800   # Gate 4: triggers re-check of Gates 1-3
SOLID_CEILING_LOC = 1000  # Gate 4: hard ceiling, escalate to user

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "staticfiles",
    "migrations",
    "reports",
}

_lib_parent = str(SCRIPT_PATH.parent)
if _lib_parent not in sys.path:
    sys.path.insert(0, _lib_parent)
from _lib.yaml_frontmatter import FrontmatterError, parse  # noqa: E402

# Matches the six valid ID prefixes: G, AR, IM, EX, LR-U, LR-T.
_ID_ALT = r"(?:LR-[UT]|G|AR|IM|EX)"
# Checklist lines:  `- [ ] IM-1: description`  /  `- [x] AR-2: ...`  /  `- [~] IM-4: ...`
CHECKLIST_RE = re.compile(
    rf"^-\s*\[(?P<mark>[ x~])\]\s*(?P<id>{_ID_ALT}-\d+)\s*:\s*(?P<desc>.*)$"
)
# Code comment:  `# spec:<spec-id>::<item-id>`
CODE_REF_RE = re.compile(
    rf"#\s*spec:(?P<spec>[a-z0-9][a-z0-9_\-]*)::(?P<item>{_ID_ALT}-\d+)"
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ChecklistItem:
    item_id: str  # e.g. "IM-1"
    section: str  # e.g. "IM"
    status: str  # " " | "x" | "~"
    description: str
    line: int  # 1-based line number in spec file


@dataclass
class Spec:
    spec_id: str
    path: Path
    frontmatter: dict
    title: str
    status: str
    code_roots: list[str]
    last_audited: str | None
    items: list[ChecklistItem] = field(default_factory=list)
    loc: int = 0
    body: str = ""
    # Anti-pattern enforcement table parsed from the `items:` frontmatter block.
    # Shape: {item_id: {canonical: str, anti_pattern: str, exclude: list[str]}}
    enforcement: dict[str, dict] = field(default_factory=dict)

    def items_by_id(self) -> dict[str, ChecklistItem]:
        return {it.item_id: it for it in self.items}

    def section_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {s: 0 for s in VALID_SECTIONS}
        for it in self.items:
            counts[it.section] = counts.get(it.section, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Pure functions: parsing
# ---------------------------------------------------------------------------


def parse_checklist_items(body: str) -> list[ChecklistItem]:
    """Extract all `- [m] <ID>: description` lines from spec body."""
    items: list[ChecklistItem] = []
    for lineno, line in enumerate(body.splitlines(), start=1):
        m = CHECKLIST_RE.match(line.rstrip())
        if not m:
            continue
        item_id = m.group("id")
        section = item_id.rsplit("-", 1)[0]  # "IM-1" -> "IM", "LR-U-2" -> "LR-U"
        items.append(
            ChecklistItem(
                item_id=item_id,
                section=section,
                status=m.group("mark"),
                description=m.group("desc").strip(),
                line=lineno,
            )
        )
    return items


def _coerce_date_str(value: Any) -> str | None:
    # PyYAML auto-parses YYYY-MM-DD into datetime.date, which json.dump can't
    # serialize. Normalize at the load boundary so callers don't need default=str.
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def load_spec(path: Path) -> Spec:
    """Read and parse a spec file into a Spec object.

    Raises FrontmatterError on malformed frontmatter so callers can decide
    whether to skip the file (see ``load_all_specs``) or surface the error.
    Matches the parse-error behavior in ``decisions.py.load_decisions`` /
    ``plans.py.load_plans``.
    """
    text = path.read_text(encoding="utf-8")
    doc = parse(text, path=path)
    fm, body = doc.metadata, doc.body
    items = parse_checklist_items(body)
    code_roots_raw = fm.get("code_roots", []) or []
    if isinstance(code_roots_raw, str):
        code_roots = [code_roots_raw]
    else:
        code_roots = [str(r) for r in code_roots_raw]
    spec_id = str(fm.get("id") or path.stem)
    enforcement_raw = fm.get("items") or {}
    if not isinstance(enforcement_raw, dict):
        enforcement_raw = {}
    # Normalize: ensure every entry has canonical/anti_pattern/exclude keys
    # for the pattern-enforcement path, AND preserve deleted/deleted_in_commit
    # markers for the coverage path (see `compute_coverage` — deletion-IMs
    # are opted out of coverage so they don't report permanent checkmark_lag).
    # NOTE: PyYAML handles YAML escape semantics natively; if a future spec
    # uses double-quoted strings with backslash escapes in canonical: /
    # anti_pattern:, be aware the parsed value follows YAML rules (e.g. \\
    # → \, \. → invalid escape) rather than the old `_unescape_yaml_double_quoted`
    # rules removed in PR-A. Prefer single-quoted strings or block scalars
    # for regex patterns so backslashes pass through literally.
    enforcement: dict[str, dict] = {}
    for item_id, cfg in enforcement_raw.items():
        if not isinstance(cfg, dict):
            continue
        entry: dict[str, Any] = {
            "canonical": str(cfg.get("canonical", "") or ""),
            "anti_pattern": str(cfg.get("anti_pattern", "") or ""),
            "exclude": list(cfg.get("exclude", []) or []),
        }
        if cfg.get("deleted") is True:
            entry["deleted"] = True
            if cfg.get("deleted_in_commit"):
                entry["deleted_in_commit"] = str(cfg["deleted_in_commit"])
        enforcement[str(item_id)] = entry
    return Spec(
        spec_id=spec_id,
        path=path,
        frontmatter=fm,
        title=str(fm.get("title") or fm.get("name") or spec_id),
        status=str(fm.get("status") or "draft"),
        code_roots=code_roots,
        last_audited=_coerce_date_str(fm.get("last_audited") or fm.get("last_synced")),
        items=items,
        loc=text.count("\n") + (0 if text.endswith("\n") else 1),
        body=body,
        enforcement=enforcement,
    )


def find_spec_files(specs_dir: Path) -> list[Path]:
    """List all *.md files under specs_dir (excluding INDEX.md / README.md)."""
    if not specs_dir.is_dir():
        return []
    out: list[Path] = []
    for entry in sorted(specs_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue
        if entry.name.lower() in ("index.md", "readme.md"):
            continue
        out.append(entry)
    return out


def load_all_specs(specs_dir: Path) -> list[Spec]:
    """Load every spec under ``specs_dir``; skip + warn on parse errors.

    Mirrors the skip-and-continue behavior in
    ``decisions.py.load_decisions`` / ``plans.py.load_plans``.
    """
    out: list[Spec] = []
    for path in find_spec_files(specs_dir):
        try:
            out.append(load_spec(path))
        except FrontmatterError as exc:
            print(f"warning: skipping {path.name}: {exc}", file=sys.stderr)
            continue
    return out


# ---------------------------------------------------------------------------
# Pure functions: code walking + grepping
# ---------------------------------------------------------------------------


def resolve_code_roots(
    repo_root: Path, code_roots: Iterable[str]
) -> list[Path]:
    """Turn spec-declared code_roots into absolute paths that exist.

    Rejects any root that escapes ``repo_root`` (absolute paths, ``../``
    climbs, symlinks pointing outside) so a crafted spec can't make
    ``inventory-check`` / ``solid`` read Python files from elsewhere
    on the filesystem.
    """
    resolved: list[Path] = []
    seen: set[Path] = set()
    repo_resolved = repo_root.resolve()
    for root in code_roots:
        if not root:
            continue
        root_str = str(root)
        if os.path.isabs(root_str):
            print(
                f"[specs] WARN: code_root {root_str!r} is absolute — "
                f"rejecting (must be relative to repo root)",
                file=sys.stderr,
            )
            continue
        candidate = (repo_root / root).resolve()
        try:
            candidate.relative_to(repo_resolved)
        except ValueError:
            print(
                f"[specs] WARN: code_root {root_str!r} resolves outside "
                f"repo root ({candidate}) — rejecting",
                file=sys.stderr,
            )
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(candidate)
    return resolved


def iter_code_files(
    repo_root: Path, roots: Iterable[Path], ignore: Iterable[str] = ()
) -> Iterator[str]:
    """Yield repo-relative paths of files under the resolved roots.

    Each root may be a file or a directory. Glob-like `*` patterns are NOT
    expanded; use directories instead (the scanner walks recursively anyway).
    """
    skip = IGNORED_DIRS | set(ignore)
    # Resolve repo_root once so the comparison with resolved file paths works
    # consistently (e.g. on macOS where /var -> /private/var).
    resolved_root = repo_root.resolve()
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            rel = _safe_rel(root, resolved_root)
            if rel and rel not in seen:
                seen.add(rel)
                yield rel
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip]
            for f in files:
                if not (f.endswith(".py") or f.endswith(".md")):
                    continue
                abs_p = Path(dirpath) / f
                rel = _safe_rel(abs_p, resolved_root)
                if rel and rel not in seen:
                    seen.add(rel)
                    yield rel


def _safe_rel(path: Path, resolved_root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(resolved_root))
    except ValueError:
        return None


def _display_path(path: Path, repo_root: Path) -> str:
    """Render path relative to repo_root for display; fall back to absolute."""
    rel = _safe_rel(path, repo_root.resolve())
    if rel is not None:
        return rel
    return str(path)


def grep_spec_refs_in_file(abs_path: Path) -> list[dict]:
    """Return list of {'spec': str, 'item': str, 'line': int} for each match."""
    out: list[dict] = []
    try:
        with abs_path.open("r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                for m in CODE_REF_RE.finditer(line):
                    out.append(
                        {
                            "spec": m.group("spec"),
                            "item": m.group("item"),
                            "line": lineno,
                        }
                    )
    except OSError:
        pass
    return out


def collect_refs_for_spec(
    spec: Spec, repo_root: Path
) -> dict[str, list[dict]]:
    """Grep all files in spec.code_roots; group matches by spec_id.

    Returns a map { "async-tasks": [ {path, line, item}, ... ] } so callers
    can detect cross-spec references (orphans pointing at other specs).
    """
    roots = resolve_code_roots(repo_root, spec.code_roots)
    grouped: dict[str, list[dict]] = {}
    for rel_path in iter_code_files(repo_root, roots):
        abs_path = repo_root / rel_path
        for ref in grep_spec_refs_in_file(abs_path):
            entry = {"path": rel_path, "line": ref["line"], "item": ref["item"]}
            grouped.setdefault(ref["spec"], []).append(entry)
    return grouped


# ---------------------------------------------------------------------------
# Pure functions: coverage logic
# ---------------------------------------------------------------------------


def compute_coverage(
    spec: Spec, refs_for_this_spec: list[dict]
) -> dict:
    """Compare spec checklist to code refs; return structured coverage dict.

    Semantic distinction between sections (per §22):
      - IM items are *work*. `[x]` means "implementation exists" and requires
        at least one code ref as evidence; `[x]` + no refs is drift.
      - AR items are *decisions*. `[x]` means "the decision has been made and
        documented" — a code ref is optional traceability, not evidence.
      - EX items are *acknowledged exceptions*. `[x]` means "documented =
        acknowledged" — a code ref is also optional.

    Categories:
      implemented          — IM with [x] AND refs, or AR/EX with [x] AND refs
      documented_only      — AR/EX with [x] but no refs (fine; not drift)
      checkmark_lag        — IM with [x] but no refs (DRIFT — blocks is_clean)
      implementation_ahead — any section with [ ] or [~] but HAS code refs
      partial              — item has [~] (separate tally)
      not_started          — item has [ ] and no code refs (normal pending)
      orphan_refs          — code refs pointing at item IDs not in spec

    Only `checkmark_lag` (IM only) and `orphan_refs` block `is_clean`.

    Deletion-IMs: an item flagged `deleted: true` in the `items:` enforcement
    frontmatter is excluded from coverage entirely. This is for items that
    describe *removing* code — once the deletion lands, there are no refs to
    find, and a naive audit would report permanent `checkmark_lag`. The
    `deleted: true` marker (optionally paired with `deleted_in_commit: <sha>`)
    acknowledges that the item is done and should stop counting.
    """
    items = spec.items_by_id()
    deleted_ids = {
        item_id
        for item_id, meta in spec.enforcement.items()
        if isinstance(meta, dict) and meta.get("deleted") is True
    }

    refs_by_item: dict[str, list[dict]] = {}
    for ref in refs_for_this_spec:
        refs_by_item.setdefault(ref["item"], []).append(ref)

    implemented: list[dict] = []
    documented_only: list[dict] = []
    checkmark_lag: list[dict] = []
    implementation_ahead: list[dict] = []
    partial: list[dict] = []
    not_started: list[dict] = []

    for item_id, item in items.items():
        if item.section not in CHECKABLE_SECTIONS:
            continue
        if item_id in deleted_ids:
            continue
        refs = refs_by_item.get(item_id, [])
        ref_count = len(refs)

        entry = {
            "item_id": item_id,
            "section": item.section,
            "status": item.status,
            "description": item.description,
            "ref_count": ref_count,
            "refs": refs,
        }

        if item.status == "x":
            if ref_count == 0:
                if item.section == "IM":
                    checkmark_lag.append(entry)
                else:
                    documented_only.append(entry)
            else:
                implemented.append(entry)
        elif item.status == "~":
            partial.append(entry)
            if ref_count > 0:
                implementation_ahead.append(entry)
        else:  # " "
            if ref_count > 0:
                implementation_ahead.append(entry)
            else:
                not_started.append(entry)

    spec_item_ids = set(items.keys())
    orphan_refs = [
        r for r in refs_for_this_spec if r["item"] not in spec_item_ids
    ]

    total_checkable = sum(
        1
        for it in items.values()
        if it.section in CHECKABLE_SECTIONS and it.item_id not in deleted_ids
    )

    return {
        "spec_id": spec.spec_id,
        "total_items": total_checkable,
        "implemented": implemented,
        "documented_only": documented_only,
        "checkmark_lag": checkmark_lag,
        "implementation_ahead": implementation_ahead,
        "partial": partial,
        "not_started": not_started,
        "orphan_refs": orphan_refs,
        "is_clean": not checkmark_lag and not orphan_refs,
    }


def audit_size(spec: Spec) -> dict:
    """Return size audit dict: ok / soft_warn / hard_error."""
    if spec.loc >= SIZE_HARD_LOC:
        level = "hard_error"
    elif spec.loc >= SIZE_SOFT_LOC:
        level = "soft_warn"
    else:
        level = "ok"
    return {
        "spec_id": spec.spec_id,
        "path": str(spec.path),
        "loc": spec.loc,
        "soft": SIZE_SOFT_LOC,
        "hard": SIZE_HARD_LOC,
        "level": level,
    }


# ---------------------------------------------------------------------------
# SOLID quality gates (Phase 6.3 harness — Levels 1 + 2)
# ---------------------------------------------------------------------------

# Required sections in a SOLID audit artifact.  For each key we accept any of
# the listed substrings (case-insensitive) as evidence the section exists.
_SOLID_AUDIT_MARKERS: dict[str, list[str]] = {
    "SRP": ["srp", "sentence test", "step 1"],
    "Clusters": ["cluster", "responsibility", "step 2"],
    "DRY": ["dry", "intra-file", "duplicate", "step 3"],
    "Linear": ["linear", "flow", "step 4"],
}


def solid_audit_artifact_check(spec_id: str, repo_root: Path) -> dict[str, Any]:
    """Level 1: verify the SOLID audit artifact exists and has required sections.

    The artifact is expected at
    ``reports/refactor/<spec-id>/phase-1-solid-audit.md``.  Returns a dict
    with ``pass`` (bool), ``exists`` (bool), and per-section details.
    """
    audit_path = repo_root / "reports" / "refactor" / spec_id / "phase-1-solid-audit.md"
    result: dict[str, Any] = {
        "spec_id": spec_id,
        "artifact_path": str(audit_path.relative_to(repo_root))
        if audit_path.is_relative_to(repo_root)
        else str(audit_path),
        "exists": False,
        "sections_found": [],
        "sections_missing": [],
        "pass": False,
    }
    if not audit_path.exists():
        result["sections_missing"] = list(_SOLID_AUDIT_MARKERS)
        return result

    result["exists"] = True
    content = audit_path.read_text(errors="replace").lower()
    for section, markers in _SOLID_AUDIT_MARKERS.items():
        if any(m in content for m in markers):
            result["sections_found"].append(section)
        else:
            result["sections_missing"].append(section)
    result["pass"] = not result["sections_missing"]
    return result


def _normalize_ast_dump(dump: str) -> str:
    """Normalize an ``ast.dump`` string so structurally-identical trees with
    different names/values hash to the same key.

    Replaces variable names, attribute names, string constants, and numeric
    constants with placeholders so that e.g.::

        uploaded_file.status = 'error'
        crawl_job.status = 'failed'

    produce the same normalized form.
    """
    s = re.sub(r"id='[^']*'", "id='_'", dump)
    s = re.sub(r"attr='[^']*'", "attr='_'", s)
    s = re.sub(r"value='[^']*'", "value='_'", s)
    s = re.sub(r"value=\"[^\"]*\"", 'value="_"', s)
    s = re.sub(r"value=-?\d+(\.\d+)?", "value=0", s)
    s = re.sub(r"arg='[^']*'", "arg='_'", s)
    return s


def find_duplicate_blocks(filepath: Path, min_block_lines: int = 3) -> list[dict[str, Any]]:
    """Level 2: find structurally duplicated except-handler bodies in one file.

    Parses the file's AST, extracts every ``except`` handler body of at least
    *min_block_lines* lines, normalises by dumping the AST and replacing all
    names/constants with placeholders, then groups by hash.  This catches
    handlers that differ only in variable names or string literals (e.g.
    ``obj.status = 'failed'`` vs ``job.status = 'error'``).

    Returns groups with 2+ structurally identical blocks, sorted by count
    descending.
    """
    try:
        source = filepath.read_text(errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return []

    lines = source.splitlines()
    blocks: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.body:
            start = node.body[0].lineno
            end_line = getattr(node.body[-1], "end_lineno", None) or start
            if end_line - start + 1 < min_block_lines:
                continue
            # Build structural fingerprint from AST, not source text
            body_dump = " ".join(ast.dump(stmt) for stmt in node.body)
            normalized = _normalize_ast_dump(body_dump)
            # MD5 here is a fast content fingerprint for clone grouping,
            # not a security primitive — `usedforsecurity=False` tells
            # Bandit/B324 and FIPS hosts it's a non-crypto digest.
            h = hashlib.md5(
                normalized.encode(), usedforsecurity=False
            ).hexdigest()[:12]
            # Keep source preview for human readability
            block_src = "\n".join(lines[start - 1 : end_line])
            preview = textwrap.dedent(block_src).strip()[:120]
            blocks.append({"start": start, "end": end_line, "hash": h, "preview": preview})

    # Group by hash, keep only duplicates
    groups: dict[str, list[dict]] = {}
    for b in blocks:
        groups.setdefault(b["hash"], []).append(b)

    return sorted(
        [
            {"count": len(g), "lines": [b["start"] for b in g], "preview": g[0]["preview"]}
            for g in groups.values()
            if len(g) >= 2
        ],
        key=lambda d: -d["count"],
    )


def solid_file_gates(filepath: Path) -> dict[str, Any]:
    """Level 2: run automated SOLID gates (2 + 4) on a single code file.

    Gate 1 (SRP) and Gate 3 (linear flow) require agent judgment and are not
    checked here.
    """
    try:
        loc = sum(1 for _ in filepath.open(errors="replace"))
    except OSError:
        return {"path": str(filepath), "error": "cannot read"}

    dups = find_duplicate_blocks(filepath)
    total_dup = sum(d["count"] for d in dups)

    gate2_pass = total_dup < 4

    if loc > SOLID_CEILING_LOC:
        gate4 = {"pass": False, "level": "hard_ceiling"}
    elif loc > SOLID_RECHECK_LOC:
        gate4 = {"pass": True, "level": "recheck_advisory"}
    else:
        gate4 = {"pass": True, "level": "ok"}
    gate4["loc"] = loc

    return {
        "path": str(filepath),
        "loc": loc,
        "gate2_dry": {
            "pass": gate2_pass,
            "groups": len(dups),
            "total_instances": total_dup,
            "details": dups[:5],
        },
        "gate4_size": gate4,
        "gates_1_3": "requires_agent_judgment",
    }


def cmd_solid(args: argparse.Namespace, specs: list[Spec], repo_root: Path) -> int:
    """Run SOLID quality gates for a specific spec (Phase 6.3 harness)."""
    match = next((s for s in specs if s.spec_id == args.spec_id), None)
    if not match:
        print(f"error: no spec with id '{args.spec_id}'", file=sys.stderr)
        return 2

    mode = getattr(args, "mode", "standard")

    # Level 1: artifact gate.  In standard mode the audit is optional —
    # Phase 1.2.5 is only mandatory for decomposition refactors, so a
    # missing artifact is SKIPPED (not FAILED) when mode=standard.
    artifact = solid_audit_artifact_check(args.spec_id, repo_root)
    level1_skipped = mode == "standard" and not artifact["exists"]
    level1_pass = artifact["pass"] or level1_skipped

    # Level 2: automated file gates on code_roots
    file_results: list[dict[str, Any]] = []
    for root_path in resolve_code_roots(repo_root, match.code_roots):
        if root_path.is_file() and root_path.suffix == ".py":
            file_results.append(solid_file_gates(root_path))
        elif root_path.is_dir():
            for py in sorted(root_path.rglob("*.py")):
                if not any(d in py.parts for d in IGNORED_DIRS):
                    file_results.append(solid_file_gates(py))

    level2_pass = all(
        r.get("gate2_dry", {}).get("pass", True)
        and r.get("gate4_size", {}).get("pass", True)
        for r in file_results
    )
    any_hard_ceiling = any(
        r.get("gate4_size", {}).get("level") == "hard_ceiling" for r in file_results
    )

    payload = {
        "spec_id": args.spec_id,
        "mode": mode,
        "level1_artifact": artifact,
        "level1_skipped": level1_skipped,
        "level2_files": file_results,
        "level1_pass": level1_pass,
        "level2_pass": level2_pass,
        "level3_agent": "not_automated",
        "overall": "pass" if (level1_pass and level2_pass) else "fail",
    }

    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if payload["overall"] == "pass" else 1

    # ---- human-readable output ----
    print(f"SOLID gates for {args.spec_id}:")
    print()

    # Level 1
    if level1_skipped:
        tag = "SKIP"
    elif artifact["pass"]:
        tag = "PASS"
    else:
        tag = "FAIL"
    print("  Level 1 \u2014 Artifact gate:")
    if artifact["exists"]:
        found = ", ".join(artifact["sections_found"]) or "(none)"
        print(f"    {tag}  audit file exists, sections: {found}")
        if artifact["sections_missing"]:
            missing = ", ".join(artifact["sections_missing"])
            print(f"         missing: {missing}")
    else:
        print(f"    {tag}  {artifact['artifact_path']} not found")
        if level1_skipped:
            print("         (mode=standard — Phase 1.2.5 audit is optional)")
        else:
            print("         (mode=decomposition — audit artifact is required)")
    print()

    # Level 2
    print(f"  Level 2 \u2014 Automated checks ({len(file_results)} file(s)):")
    for r in file_results:
        p = Path(r["path"])
        try:
            rel = p.relative_to(repo_root)
        except ValueError:
            rel = p
        loc = r.get("loc", "?")
        g2 = r.get("gate2_dry", {})
        g4 = r.get("gate4_size", {})
        g2_tag = "PASS" if g2.get("pass", True) else "FAIL"
        g4_tag = "PASS" if g4.get("pass", True) else "FAIL"
        if g4.get("level") == "recheck_advisory":
            g4_tag = "ADVI"
        print(f"    {rel} ({loc} LOC)")
        dup_msg = f"{g2.get('groups', 0)} dup group(s), {g2.get('total_instances', 0)} instance(s)"
        print(f"      Gate 2 (DRY):  {g2_tag} \u2014 {dup_msg}")
        if g4.get("level") == "hard_ceiling":
            print(f"      Gate 4 (Size): {g4_tag} \u2014 {loc} LOC > {SOLID_CEILING_LOC} ceiling")
        elif g4.get("level") == "recheck_advisory":
            print(f"      Gate 4 (Size): {g4_tag} \u2014 {loc} LOC > {SOLID_RECHECK_LOC}, re-check Gates 1-3")
        else:
            print(f"      Gate 4 (Size): {g4_tag}")
    print()

    # Level 3
    print("  Level 3 \u2014 Agent judgment gates:")
    print("    Gate 1 (SRP):    requires sub-agent \u2014 see SKILL.md \u00a76.3")
    print("    Gate 3 (Linear): requires sub-agent \u2014 see SKILL.md \u00a76.3")
    print()

    overall_tag = "PASS" if payload["overall"] == "pass" else "FAIL"
    print(f"  Overall (L1+L2): {overall_tag}")
    if any_hard_ceiling:
        print(f"  WARNING: file(s) exceed {SOLID_CEILING_LOC} LOC hard ceiling")

    return 0 if payload["overall"] == "pass" else 1


def build_index(specs: list[Spec], repo_root: Path) -> dict:
    """Build the full spec-index.json payload (used by `rebuild`)."""
    specs_out: dict[str, Any] = {}
    code_out: dict[str, dict] = {}

    for spec in specs:
        refs_grouped = collect_refs_for_spec(spec, repo_root)
        own_refs = refs_grouped.get(spec.spec_id, [])
        coverage = compute_coverage(spec, own_refs)

        declared_files = sorted(
            {
                rel
                for rel in iter_code_files(
                    repo_root, resolve_code_roots(repo_root, spec.code_roots)
                )
            }
        )

        specs_out[spec.spec_id] = {
            "path": _display_path(spec.path, repo_root),
            "title": spec.title,
            "status": spec.status,
            "last_audited": spec.last_audited,
            "code_roots": spec.code_roots,
            "declared_files": declared_files,
            "section_counts": spec.section_counts(),
            "loc": spec.loc,
            "coverage_summary": {
                "total": coverage["total_items"],
                "implemented": len(coverage["implemented"]),
                "documented_only": len(coverage["documented_only"]),
                "checkmark_lag": len(coverage["checkmark_lag"]),
                "implementation_ahead": len(coverage["implementation_ahead"]),
                "partial": len(coverage["partial"]),
                "not_started": len(coverage["not_started"]),
                "orphan_refs": len(coverage["orphan_refs"]),
                "is_clean": coverage["is_clean"],
            },
        }

        for rel_path in declared_files:
            abs_path = repo_root / rel_path
            file_refs = grep_spec_refs_in_file(abs_path)
            ids = sorted({r["item"] for r in file_refs if r["spec"] == spec.spec_id})
            record = code_out.setdefault(
                rel_path, {"covered_by": [], "referenced_ids": []}
            )
            if spec.spec_id not in record["covered_by"]:
                record["covered_by"].append(spec.spec_id)
            for i in ids:
                if i not in record["referenced_ids"]:
                    record["referenced_ids"].append(i)

    return {
        "version": INDEX_VERSION,
        "specs": specs_out,
        "code": code_out,
    }


def save_index(data: dict, path: Path) -> None:
    """Atomic write via .tmp + replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace, specs: list[Spec]) -> int:
    filtered = [
        s for s in specs if args.status is None or s.status == args.status
    ]
    if args.json:
        payload = [
            {
                "id": s.spec_id,
                "title": s.title,
                "status": s.status,
                "loc": s.loc,
                "sections": s.section_counts(),
                "code_roots": s.code_roots,
            }
            for s in filtered
        ]
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if filtered else 1
    if not filtered:
        print("no specs match", file=sys.stderr)
        return 1
    print(f"{'ID':<28}  {'STATUS':<12}  {'LOC':>5}  {'IM':>3}  {'AR':>3}  {'EX':>3}  TITLE")
    for s in filtered:
        counts = s.section_counts()
        print(
            f"{s.spec_id:<28}  {s.status:<12}  {s.loc:>5}  "
            f"{counts.get('IM', 0):>3}  {counts.get('AR', 0):>3}  "
            f"{counts.get('EX', 0):>3}  {s.title}"
        )
    return 0


def cmd_show(args: argparse.Namespace, specs: list[Spec], repo_root: Path) -> int:
    match = next((s for s in specs if s.spec_id == args.spec_id), None)
    if match is None:
        print(f"no spec with id {args.spec_id!r}", file=sys.stderr)
        return 1

    refs = collect_refs_for_spec(match, repo_root).get(match.spec_id, [])
    refs_by_item: dict[str, list[dict]] = {}
    for r in refs:
        refs_by_item.setdefault(r["item"], []).append(r)

    if args.json:
        payload = {
            "id": match.spec_id,
            "title": match.title,
            "status": match.status,
            "loc": match.loc,
            "path": _display_path(match.path, repo_root),
            "code_roots": match.code_roots,
            "last_audited": match.last_audited,
            "items": [
                {
                    "item_id": it.item_id,
                    "section": it.section,
                    "status": it.status,
                    "description": it.description,
                    "line": it.line,
                    "ref_count": len(refs_by_item.get(it.item_id, [])),
                }
                for it in match.items
            ],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    print(f"id: {match.spec_id}")
    print(f"title: {match.title}")
    print(f"status: {match.status}")
    print(f"loc: {match.loc}")
    print(f"path: {_display_path(match.path, repo_root)}")
    print(f"last_audited: {match.last_audited or '-'}")
    print(f"code_roots: {', '.join(match.code_roots) or '-'}")
    print()
    for section in VALID_SECTIONS:
        section_items = [it for it in match.items if it.section == section]
        if not section_items:
            continue
        print(f"[{section}] {len(section_items)} item(s)")
        for it in section_items:
            ref_n = len(refs_by_item.get(it.item_id, []))
            marker = f"[{it.status}]"
            print(f"  {marker} {it.item_id}: {it.description}  (refs={ref_n})")
        print()
    return 0


def cmd_rebuild(
    args: argparse.Namespace, specs: list[Spec], repo_root: Path, index_path: Path
) -> int:
    index = build_index(specs, repo_root)
    if args.dry_run:
        json.dump(index, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    save_index(index, index_path)
    n_specs = len(index["specs"])
    n_files = len(index["code"])
    display_path = _display_path(index_path, repo_root)
    print(f"rebuilt {display_path}: {n_specs} specs, {n_files} files")
    return 0


def cmd_coverage(
    args: argparse.Namespace, specs: list[Spec], repo_root: Path
) -> int:
    match = next((s for s in specs if s.spec_id == args.spec_id), None)
    if match is None:
        print(f"no spec with id {args.spec_id!r}", file=sys.stderr)
        return 2

    refs_grouped = collect_refs_for_spec(match, repo_root)
    own_refs = refs_grouped.get(match.spec_id, [])
    coverage = compute_coverage(match, own_refs)

    if args.json:
        json.dump(coverage, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if coverage["is_clean"] else 1

    total = coverage["total_items"]
    implemented = coverage["implemented"]
    documented_only = coverage["documented_only"]
    checkmark_lag = coverage["checkmark_lag"]
    impl_ahead = coverage["implementation_ahead"]
    partial = coverage["partial"]
    not_started = coverage["not_started"]
    orphans = coverage["orphan_refs"]

    print(f"Spec: {match.spec_id}  ({total} checkable items)")
    print(f"Code roots: {', '.join(match.code_roots) or '(none)'}")
    print()

    if implemented:
        print(f"Implemented ({len(implemented)}):")
        for e in implemented:
            print(f"  [x] {e['item_id']}: {e['description']}  ({e['ref_count']} refs)")
        print()

    if documented_only:
        print(f"Documented ({len(documented_only)}) — AR/EX marked [x], no code refs (OK):")
        for e in documented_only:
            print(f"  [x] {e['item_id']}: {e['description']}")
        print()

    if partial:
        print(f"Partial ({len(partial)}):")
        for e in partial:
            print(f"  [~] {e['item_id']}: {e['description']}  ({e['ref_count']} refs)")
        print()

    if not_started:
        print(f"Not started ({len(not_started)}):")
        for e in not_started:
            print(f"  [ ] {e['item_id']}: {e['description']}")
        print()

    if checkmark_lag:
        print(f"CHECKMARK LAG ({len(checkmark_lag)}) — IM marked [x] but no code refs:")
        for e in checkmark_lag:
            print(f"  ! {e['item_id']}: {e['description']}")
        print()

    if impl_ahead:
        print(f"IMPLEMENTATION AHEAD ({len(impl_ahead)}) — code exists but item not marked [x]:")
        for e in impl_ahead:
            print(f"  ? {e['item_id']}: {e['description']}  ({e['ref_count']} refs)")
        print()

    if orphans:
        print(f"ORPHAN REFS ({len(orphans)}) — code points at items not in spec:")
        for r in orphans:
            print(f"  ? {r['path']}:{r['line']}  ->  {r['item']}")
        print()

    print(
        f"Summary: {len(implemented)}/{total} implemented, "
        f"{len(documented_only)} documented, {len(partial)} partial, "
        f"{len(checkmark_lag)} checkmark-lag, {len(impl_ahead)} impl-ahead, "
        f"{len(orphans)} orphan-refs"
    )
    return 0 if coverage["is_clean"] else 1


def cmd_orphans(args: argparse.Namespace, specs: list[Spec], repo_root: Path) -> int:
    """Scan all specs' code roots for refs whose item IDs do not exist."""
    results: list[dict] = []
    for spec in specs:
        refs_grouped = collect_refs_for_spec(spec, repo_root)
        own_refs = refs_grouped.get(spec.spec_id, [])
        spec_ids = set(spec.items_by_id().keys())
        for ref in own_refs:
            if ref["item"] not in spec_ids:
                results.append(
                    {
                        "spec_id": spec.spec_id,
                        "item": ref["item"],
                        "path": ref["path"],
                        "line": ref["line"],
                    }
                )
    if args.json:
        json.dump(results, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if not results else 1
    if not results:
        print("no orphan refs")
        return 0
    print(f"{'SPEC':<24}  {'ITEM':<10}  LOCATION")
    for r in results:
        print(f"{r['spec_id']:<24}  {r['item']:<10}  {r['path']}:{r['line']}")
    return 1


def cmd_audit(args: argparse.Namespace, specs: list[Spec], repo_root: Path) -> int:
    """Run coverage on every spec; exit 1 if any drift detected."""
    all_reports: list[dict] = []
    size_reports: list[dict] = []
    any_drift = False
    for spec in specs:
        refs_grouped = collect_refs_for_spec(spec, repo_root)
        own_refs = refs_grouped.get(spec.spec_id, [])
        cov = compute_coverage(spec, own_refs)
        sz = audit_size(spec)
        all_reports.append(
            {
                "spec_id": spec.spec_id,
                "is_clean": cov["is_clean"],
                "summary": {
                    "total": cov["total_items"],
                    "implemented": len(cov["implemented"]),
                    "documented_only": len(cov["documented_only"]),
                    "checkmark_lag": len(cov["checkmark_lag"]),
                    "implementation_ahead": len(cov["implementation_ahead"]),
                    "partial": len(cov["partial"]),
                    "not_started": len(cov["not_started"]),
                    "orphan_refs": len(cov["orphan_refs"]),
                },
            }
        )
        size_reports.append(sz)
        if not cov["is_clean"] or sz["level"] == "hard_error":
            any_drift = True
    payload = {"coverage": all_reports, "sizes": size_reports, "clean": not any_drift}
    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if not any_drift else 1
    print(f"Audited {len(specs)} spec(s):")
    for r in all_reports:
        flag = "OK" if r["is_clean"] else "DRIFT"
        s = r["summary"]
        print(
            f"  {flag:<5}  {r['spec_id']:<28}  "
            f"impl={s['implemented']}/{s['total']}  "
            f"lag={s['checkmark_lag']}  ahead={s['implementation_ahead']}  "
            f"orphans={s['orphan_refs']}"
        )
    for sz in size_reports:
        if sz["level"] != "ok":
            label = "WARN" if sz["level"] == "soft_warn" else "ERROR"
            print(f"  {label}  {sz['spec_id']:<28}  loc={sz['loc']} (soft={sz['soft']}, hard={sz['hard']})")
    return 0 if not any_drift else 1


def cmd_size_check(args: argparse.Namespace, specs: list[Spec]) -> int:
    reports = [audit_size(s) for s in specs]
    has_hard_error = any(r["level"] == "hard_error" for r in reports)
    if args.json:
        json.dump(reports, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1 if has_hard_error else 0
    non_ok = [r for r in reports if r["level"] != "ok"]
    if not non_ok:
        print(f"all {len(reports)} spec(s) under {SIZE_SOFT_LOC} LOC")
        return 0
    print(f"{'LEVEL':<12}  {'LOC':>5}  ID")
    for r in non_ok:
        print(f"{r['level']:<12}  {r['loc']:>5}  {r['spec_id']}")
    return 1 if has_hard_error else 0


# ---------------------------------------------------------------------------
# inventory-check: narrative inventory vs code symbol extraction
# ---------------------------------------------------------------------------


INVENTORY_LOC_THRESHOLD = 1000

# Grep lines like `| 8745 | build_interchanges_from_external_task | ... |`
_INVENTORY_TABLE_ROW_RE = re.compile(
    r"^\|\s*(?P<line>\d+)\s*\|\s*`?(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)"
)
# Parenthetical fallback: `build_interchanges_from_external_task` in prose.
_INVENTORY_BACKTICK_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")

STUB_WARNING_RE = re.compile(r"(?i)\b(stub|incomplete|re-scan|known gaps?)\b")


def _classify_inventory_kind(rel_path: str) -> str:
    """Return the symbol category for a code file.

    Categories:
      - 'tasks'    -> @shared_task decorators
      - 'views'    -> class ...View(...)
      - 'services' -> class ...(...)
      - 'functions'-> top-level def
    """
    name = Path(rel_path).name.lower()
    parent = Path(rel_path).parent.name.lower()
    if name.startswith("tasks") and name.endswith(".py"):
        return "tasks"
    if name.startswith("views") and name.endswith(".py"):
        return "views"
    if parent == "services" or name == "services.py":
        return "services"
    return "functions"


def _has_shared_task_decorator(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """True if any decorator on the node is @shared_task (bare or called).

    Matches:
        @shared_task
        @shared_task()
        @shared_task(bind=True, queue="browser")
        @some.module.shared_task (attribute form — defensive match)

    Does NOT match unrelated decorators like `@task`, `@app.task`,
    or `@celery.task`.
    """
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "shared_task":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "shared_task":
            return True
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name) and func.id == "shared_task":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "shared_task":
                return True
    return False


def extract_symbols(path: Path, kind: str) -> list[tuple[int, str]]:
    """Return [(line_number, symbol_name), ...] for the given file + kind.

    AST-based: parses the file with `ast.parse` and walks `tree.body`.
    Only top-level (module-level) constructs are returned — nested defs
    and classes inside functions are intentionally ignored, because the
    narrative inventory tables list module-level symbols.

    Kinds:
        tasks     -> top-level def/async def decorated with @shared_task
        views     -> top-level class whose name ends with 'View'
        services  -> top-level class (any name)
        functions -> top-level def/async def

    Returns an empty list on read or parse error. Line numbers are
    1-based and correspond to the `def` / `class` keyword line, which
    matches what the pre-AST regex walker returned (compatible with
    existing inventory tables that cite def-line line numbers).

    This replaces a regex-based walker. Both this function and the
    AST chunker in `scripts/chunk_file.py` now derive top-level symbols
    from `ast.parse()` + `tree.body` — one primitive, two consumers.
    See `feedback_process_improvement_propagation.md` in memory for the
    convergence principle.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    out: list[tuple[int, str]] = []
    for node in tree.body:
        if kind == "tasks":
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _has_shared_task_decorator(node):
                    out.append((node.lineno, node.name))
        elif kind == "views":
            if isinstance(node, ast.ClassDef) and node.name.endswith("View"):
                out.append((node.lineno, node.name))
        elif kind == "services":
            if isinstance(node, ast.ClassDef):
                out.append((node.lineno, node.name))
        elif kind == "functions":
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append((node.lineno, node.name))
    return out


def parse_inventory_symbols(body: str) -> set[str]:
    """Extract symbol names referenced in a spec's narrative inventory.

    Looks for:
      1. Markdown table rows of the form `| <line> | <symbol> | ... |`
      2. Backticked identifiers inside an explicit "Known <kind> inventory"
         section (or "## Known ... inventory" heading).

    Returns a set of symbol names (without surrounding backticks).
    """
    symbols: set[str] = set()
    lines = body.splitlines()
    in_inventory = False
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("## "):
            heading = stripped.lower()
            in_inventory = "inventory" in heading and "known" in heading
            continue
        m = _INVENTORY_TABLE_ROW_RE.match(raw)
        if m:
            symbols.add(m.group("symbol"))
            continue
        if in_inventory:
            for m2 in _INVENTORY_BACKTICK_RE.finditer(raw):
                symbols.add(m2.group(1))
    return symbols


def detect_stub_warnings(body: str) -> list[tuple[int, str]]:
    """Return [(line_number, context_snippet), ...] for body lines that look
    like the author flagged the inventory as incomplete.
    """
    out: list[tuple[int, str]] = []
    for i, line in enumerate(body.splitlines(), start=1):
        if STUB_WARNING_RE.search(line):
            out.append((i, line.strip()))
    return out


def run_inventory_check(spec: Spec, repo_root: Path) -> dict:
    """Compare spec inventory to code symbol extraction.

    Returns a dict shaped for both human and strict-exit use:
      {
        "spec_id": str,
        "status": "clean" | "mismatch" | "stub",
        "files": [
          {"path": str, "loc": int, "kind": str,
           "symbols_in_code": [(line, name), ...],
           "symbols_in_spec": [name, ...],
           "missing_from_spec": [(line, name), ...],
           "stale_in_spec": [name, ...]},
          ...
        ],
        "stub_warnings": [(line_no, text), ...],
      }
    """
    spec_symbols = parse_inventory_symbols(spec.body)
    stub_warnings = detect_stub_warnings(spec.body)

    file_reports: list[dict] = []
    any_mismatch = False

    for rel_root in spec.code_roots:
        abs_root = (repo_root / rel_root).resolve()
        if not abs_root.exists():
            continue
        if not abs_root.is_file() or not rel_root.endswith(".py"):
            continue
        try:
            loc = abs_root.read_text(encoding="utf-8", errors="replace").count("\n")
        except OSError:
            loc = 0
        if loc <= INVENTORY_LOC_THRESHOLD:
            continue
        kind = _classify_inventory_kind(rel_root)
        code_symbols = extract_symbols(abs_root, kind)
        code_names = {name for _, name in code_symbols}
        missing_from_spec = [(ln, n) for ln, n in code_symbols if n not in spec_symbols]
        # "Stale" — in spec but not in code. Heuristic: only count spec
        # symbols whose name pattern plausibly matches the kind (e.g. a
        # tasks.py inventory row listing a name that ends in _task but
        # isn't in code).
        stale_in_spec: list[str] = []
        if kind == "tasks":
            # Pull out symbol-looking names present in spec — if they match
            # the tasks naming convention but aren't in code, they're stale.
            for name in spec_symbols:
                if name.endswith("_task") and name not in code_names:
                    stale_in_spec.append(name)
        else:
            for name in spec_symbols:
                if name not in code_names and re.search(r"[a-z_]{3,}", name):
                    # Heuristic — only warn if the name looks plausible.
                    # Keep conservative for non-tasks kinds: skip.
                    pass
        if missing_from_spec or stale_in_spec:
            any_mismatch = True
        file_reports.append(
            {
                "path": rel_root,
                "loc": loc,
                "kind": kind,
                "symbols_in_code": code_symbols,
                "symbols_in_spec_count": len(
                    [
                        n
                        for _, n in code_symbols
                        if n in spec_symbols
                    ]
                ),
                "code_count": len(code_symbols),
                "missing_from_spec": missing_from_spec,
                "stale_in_spec": stale_in_spec,
            }
        )

    if any_mismatch:
        status = "mismatch"
    elif stub_warnings:
        status = "stub"
    else:
        status = "clean"

    return {
        "spec_id": spec.spec_id,
        "status": status,
        "files": file_reports,
        "stub_warnings": stub_warnings,
    }


def cmd_inventory_check(
    args: argparse.Namespace, specs: list[Spec], repo_root: Path
) -> int:
    match = next((s for s in specs if s.spec_id == args.spec_id), None)
    if match is None:
        print(f"no spec with id {args.spec_id!r}", file=sys.stderr)
        return 2

    report = run_inventory_check(match, repo_root)

    print(f"Spec: {report['spec_id']}")
    print(f"Status: {report['status'].upper()}")
    print()

    if not report["files"]:
        print(
            "(no large Python code_roots to inventory — all files are under "
            f"{INVENTORY_LOC_THRESHOLD} LOC or not .py files)"
        )
    for fr in report["files"]:
        label_map = {
            "tasks": "@shared_task decorators",
            "views": "class ...View definitions",
            "services": "top-level class definitions",
            "functions": "top-level def definitions",
        }
        print(f"File: {fr['path']} ({fr['loc']} LOC)")
        print(f"  Symbol type: {label_map.get(fr['kind'], fr['kind'])}")
        print(f"  Symbols in code:  {fr['code_count']}")
        print(f"  Symbols in spec:  {fr['symbols_in_spec_count']}")
        missing = fr["missing_from_spec"]
        if missing:
            print(f"  Missing from spec ({len(missing)}):")
            for line_no, name in missing:
                print(f"    - line {line_no}: {name}")
        stale = fr["stale_in_spec"]
        if stale:
            print(f"  Removed / renamed ({len(stale)}):")
            for name in stale:
                print(f"    - {name}")
        print()

    if report["stub_warnings"]:
        print(f"Stub warnings: {len(report['stub_warnings'])}")
        for line_no, text in report["stub_warnings"][:5]:
            preview = text if len(text) <= 120 else text[:117] + "..."
            print(f'  - Line {line_no}: "{preview}"')
        if len(report["stub_warnings"]) > 5:
            print(f"  ... (+{len(report['stub_warnings']) - 5} more)")
        print()

    if report["status"] == "clean":
        print("Verdict: Inventory matches code; no stub warnings found.")
    elif report["status"] == "mismatch":
        total_missing = sum(len(fr["missing_from_spec"]) for fr in report["files"])
        print(
            f"Verdict: The spec's inventory is incomplete. {total_missing} "
            "symbol(s) are missing. Re-scan required before proceeding with "
            "a refactor."
        )
    else:  # stub
        print(
            "Verdict: The spec body contains explicit stub / re-scan / known-gap "
            "warnings. Treat the inventory as incomplete."
        )

    if args.strict and report["status"] != "clean":
        return 1
    return 0


# ---------------------------------------------------------------------------
# violations: grep anti-patterns declared in spec frontmatter
# ---------------------------------------------------------------------------


# Directories we never scan for violations (repo_root walk).
VIOLATIONS_IGNORED_DIRS = IGNORED_DIRS | {
    "ai-docs",
    "logs",
    "media",
    "static",
    "staticfiles",
    "theme",
    "sitemaps",
    "data",
    "docs",
    "templates",
}


def _path_matches_exclude(rel_path: str, excludes: list[str]) -> bool:
    """True if the given path matches any exclude glob.

    Supports fnmatch patterns. A trailing slash means "directory prefix"
    (e.g. `tests/test_*/` matches any file under a directory whose name
    begins with test_).
    """
    for pat in excludes:
        if not pat:
            continue
        if pat.endswith("/"):
            prefix = pat.rstrip("/")
            # Directory-glob match — check any path segment.
            parts = rel_path.split("/")
            for j in range(len(parts)):
                sub = "/".join(parts[: j + 1])
                if fnmatch.fnmatchcase(sub, prefix):
                    return True
            continue
        if fnmatch.fnmatchcase(rel_path, pat):
            return True
        # Bare basename match too — makes `tests/test_*.py` naturally work.
        if fnmatch.fnmatchcase(Path(rel_path).name, Path(pat).name):
            # Only accept if the directories up to the pattern also match.
            if fnmatch.fnmatchcase(rel_path, pat):
                return True
    return False


def _iter_repo_python_files(repo_root: Path) -> Iterator[str]:
    """Yield repo-relative paths of .py files, skipping ignored dirs."""
    resolved_root = repo_root.resolve()
    for dirpath, dirs, files in os.walk(resolved_root):
        dirs[:] = [
            d for d in dirs if not d.startswith(".") and d not in VIOLATIONS_IGNORED_DIRS
        ]
        for f in files:
            if not f.endswith(".py"):
                continue
            abs_p = Path(dirpath) / f
            rel = _safe_rel(abs_p, resolved_root)
            if rel:
                yield rel


def scan_violations(
    repo_root: Path, item_id: str, cfg: dict
) -> dict:
    """Grep the repo for a single enforcement item.

    Returns:
      {
        "item_id": ...,
        "canonical": ...,
        "anti_pattern": ...,
        "compliant_count": int,
        "violating_count": int,
        "compliance_pct": float | None,
        "violations": [{"file": rel, "line": int, "text": str}, ...],
        "offenders": [(rel_path, count), ...],  # top-5
      }
    """
    canonical = cfg.get("canonical", "")
    anti_pattern = cfg.get("anti_pattern", "")
    excludes = cfg.get("exclude", []) or []

    compliant_count = 0
    violating_count = 0
    violations: list[dict] = []
    offenders_by_file: dict[str, int] = {}

    try:
        ap_re = re.compile(anti_pattern) if anti_pattern else None
    except re.error as exc:
        return {
            "item_id": item_id,
            "canonical": canonical,
            "anti_pattern": anti_pattern,
            "compliant_count": 0,
            "violating_count": 0,
            "compliance_pct": None,
            "violations": [],
            "offenders": [],
            "error": f"invalid anti_pattern regex: {exc}",
        }

    for rel_path in _iter_repo_python_files(repo_root):
        if _path_matches_exclude(rel_path, excludes):
            continue
        abs_path = (repo_root / rel_path).resolve()
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            has_canonical = bool(canonical) and canonical in line
            has_anti = bool(ap_re) and ap_re.search(line) is not None
            if has_canonical and not has_anti:
                compliant_count += 1
            elif has_anti and not has_canonical:
                violating_count += 1
                violations.append(
                    {
                        "file": rel_path,
                        "line": lineno,
                        "text": line.rstrip(),
                    }
                )
                offenders_by_file[rel_path] = (
                    offenders_by_file.get(rel_path, 0) + 1
                )
            elif has_canonical and has_anti:
                # Treat as compliant (canonical wraps the anti-pattern call).
                compliant_count += 1

    total = compliant_count + violating_count
    pct: float | None
    if total == 0:
        pct = None
    else:
        pct = round(compliant_count * 100.0 / total, 1)

    offenders = sorted(
        offenders_by_file.items(), key=lambda kv: (-kv[1], kv[0])
    )[:5]

    return {
        "item_id": item_id,
        "canonical": canonical,
        "anti_pattern": anti_pattern,
        "compliant_count": compliant_count,
        "violating_count": violating_count,
        "compliance_pct": pct,
        "violations": violations,
        "offenders": offenders,
    }


def cmd_violations(
    args: argparse.Namespace, specs: list[Spec], repo_root: Path
) -> int:
    match = next((s for s in specs if s.spec_id == args.spec_id), None)
    if match is None:
        print(f"no spec with id {args.spec_id!r}", file=sys.stderr)
        return 2

    items_to_scan = match.enforcement
    if args.item:
        if args.item not in items_to_scan:
            print(
                f"spec {match.spec_id!r} has no enforcement item {args.item!r}",
                file=sys.stderr,
            )
            return 2
        items_to_scan = {args.item: items_to_scan[args.item]}

    reports: list[dict] = [
        scan_violations(repo_root, item_id, cfg)
        for item_id, cfg in items_to_scan.items()
    ]

    any_below_threshold = any(
        r["compliance_pct"] is not None and r["compliance_pct"] < 80.0
        for r in reports
    )

    if args.json:
        payload = {
            "spec": match.spec_id,
            "items": [
                {
                    "item_id": r["item_id"],
                    "canonical": r["canonical"],
                    "anti_pattern": r["anti_pattern"],
                    "compliant_count": r["compliant_count"],
                    "violating_count": r["violating_count"],
                    "compliance_pct": r["compliance_pct"],
                    "violations": r["violations"],
                }
                for r in reports
            ],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        if args.strict and any_below_threshold:
            return 1
        return 0

    print(f"Spec: {match.spec_id} — Convention adoption")
    print()
    if not reports:
        print("(no enforcement items declared in spec frontmatter)")
        return 0
    for r in reports:
        print(f"{r['item_id']}: {r['canonical'] or '(no canonical)'}")
        compliant = r["compliant_count"]
        violating = r["violating_count"]
        total = compliant + violating
        if r["compliance_pct"] is None:
            print("  Compliance: N/A (no canonical or anti-pattern matches found)")
        else:
            print(
                f"  Compliance: {r['compliance_pct']:.0f}% "
                f"({compliant} compliant / {violating} violating / {total} total)"
            )
        if r["anti_pattern"]:
            print(f"  Anti-pattern: {r['anti_pattern']}")
        if r["offenders"]:
            print("  Top offenders:")
            for path, count in r["offenders"]:
                print(f"    {path:<40}  — {count} violation(s)")
        print()

    if args.strict and any_below_threshold:
        return 1
    return 0


# ---------------------------------------------------------------------------
# init: scaffold a new spec for a legacy code cluster (§23 bidirectional
# retrofit bootstrap)
# ---------------------------------------------------------------------------


_SPEC_ID_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")


def _today_iso() -> str:
    """Return today's date as ISO 8601 (YYYY-MM-DD)."""
    return _dt.date.today().isoformat()


def _default_title_from_id(spec_id: str) -> str:
    """Turn 'crawling-views' into 'Crawling Views'."""
    parts = [
        p
        for p in re.split(r"[-_]+", spec_id)
        if p
    ]
    return " ".join(p.capitalize() for p in parts)


def _inventory_kind_label(kind: str) -> str:
    """Pretty label for the kind, used in section headings."""
    return {
        "tasks": "task",
        "views": "views",
        "services": "services",
        "functions": "functions",
    }.get(kind, "symbols")


def _scaffold_inventory_table(
    abs_path: Path, rel_path: str, kind: str
) -> str:
    """Generate a markdown inventory table for a code root.

    Returns an empty string when the code root is a directory, a non-.py
    file, missing, under the inventory LOC threshold, or contains no
    top-level symbols of the requested kind.

    The table is deliberately marked with stub-warning language so that
    `inventory-check` will report `status: stub` until a human or a
    scout pass replaces it with a vetted inventory.
    """
    if not abs_path.exists() or not abs_path.is_file():
        return ""
    if not rel_path.endswith(".py"):
        return ""
    try:
        loc = abs_path.read_text(encoding="utf-8", errors="replace").count("\n")
    except OSError:
        return ""
    if loc <= INVENTORY_LOC_THRESHOLD:
        return ""
    symbols = extract_symbols(abs_path, kind)
    if not symbols:
        return ""
    label = _inventory_kind_label(kind)
    lines = [
        f"## Known {label} inventory (stub — auto-generated, incomplete)",
        "",
        f"**Source:** `{rel_path}` ({loc} LOC, {len(symbols)} top-level {label})",
        "",
        "**Known gaps in this inventory:** this table was generated by",
        "`scripts/specs.py init` without context. A scout pass must validate the",
        "surface against the actual code paths and cross-reference it with",
        "CLAUDE.md / architecture notes before marking Phase 1.1 as complete.",
        "Re-scan required.",
        "",
        "| Line | Symbol |",
        "|------|--------|",
    ]
    for line_no, name in symbols:
        lines.append(f"| {line_no} | `{name}` |")
    lines.append("")
    return "\n".join(lines) + "\n"


def scaffold_spec_body(
    spec_id: str,
    title: str,
    code_roots: list[str],
    repo_root: Path,
    today: str,
    motivating_decision: str | None = None,
    lifecycle: str | None = None,
) -> str:
    """Return the full markdown body (frontmatter + sections) for a new spec.

    The scaffolded spec is a stub: all narrative sections are empty
    placeholders, the inventory tables carry explicit stub warnings,
    and the header blockquote calls out the bootstrap state. This
    shape is designed so that:
      * `inventory-check` reports `status: stub` (not clean, not
        mismatch) — the signal to a caller that the spec is present
        but not yet populated.
      * `/refactor-subsystem` Phase 1.1 has a concrete artifact to
        iterate on via scout dispatch (§23 bidirectional retrofit).
      * A human reader immediately sees "this came from a tool, not
        from a human decision" and knows to validate before trusting.

    `motivating_decision` and `lifecycle` are optional planning-tier
    fields — `/plan-feature` sets `motivating_decision: NNNN` to link
    a spec back to the ADR that authorized the work, and `lifecycle:
    proposed | planned | active | shipped` tracks where the spec sits
    in the planning pipeline. Both fields are tolerated by the read
    path (load_spec) regardless; they're written
    here only when callers ask for them.
    """
    code_root_lines = "\n".join(f"  - {r}" for r in code_roots)
    optional_lines = ""
    if motivating_decision:
        optional_lines += f'motivating_decision: "{motivating_decision}"\n'
    if lifecycle:
        optional_lines += f"lifecycle: {lifecycle}\n"
    frontmatter = (
        "---\n"
        f"id: {spec_id}\n"
        f"title: {json.dumps(title)}\n"  # quoted: a colon in an unquoted title is invalid YAML
        "status: STUB\n"
        f"last_audited: {today}\n"
        f"{optional_lines}"
        "# `coverage` scans Python `# spec:<id>::IM-N` markers inside\n"
        "# these roots only. Doc / skill / script / ADR IM items will\n"
        "# never auto-tick here; track them via the spec checklist and\n"
        "# audit-only `<!-- spec: -->` markers in the changed files.\n"
        "code_roots:\n"
        f"{code_root_lines}\n"
        "---\n"
    )
    header = (
        "\n"
        f"# {title}\n"
        "\n"
        f"> **Spec state: STUB.** This spec was scaffolded by\n"
        f"> `scripts/specs.py init {spec_id}` on {today}. The inventory\n"
        "> sections below (if any) were extracted automatically from\n"
        "> `code_roots` via an AST walk. Goals, architecture,\n"
        "> implementation targets, exceptions, and learnings are EMPTY\n"
        "> STUBS. Phase 1.1 of `/refactor-subsystem` must populate them\n"
        "> via scout dispatch. Treat as incomplete; re-scan required\n"
        "> before any refactor claims coverage of this subsystem.\n"
        "\n"
    )
    sections = (
        "## Goals\n"
        "\n"
        "_(empty — populate during Phase 1.1)_\n"
        "\n"
        "## Architecture\n"
        "\n"
        "_(empty — populate during Phase 1.1)_\n"
        "\n"
        "## Implementation\n"
        "\n"
        "_(empty — populate during Phase 1.1)_\n"
        "\n"
        "## Learnings\n"
        "\n"
        "### User-facing\n"
        "\n"
        "_(empty — append from extraction during Phase 2b)_\n"
        "\n"
        "### Technical\n"
        "\n"
        "_(empty — append from extraction during Phase 2b)_\n"
        "\n"
        "## Exceptions\n"
        "\n"
        "_(empty — populate during Phase 1.1)_\n"
        "\n"
        "---\n"
        "\n"
    )

    inventory_tables: list[str] = []
    for rel in code_roots:
        abs_path = (repo_root / rel).resolve()
        if not rel.endswith(".py"):
            continue
        kind = _classify_inventory_kind(rel)
        table = _scaffold_inventory_table(abs_path, rel, kind)
        if table:
            inventory_tables.append(table)

    if not inventory_tables:
        # No large .py code roots means nothing to tabulate, but the
        # header blockquote already contains stub-warning language, so
        # `inventory-check` will still classify this spec as a stub.
        inventory_tables.append(
            "## Known symbol inventory (stub — not tabulated)\n"
            "\n"
            "_(no code root is both a `.py` file and over "
            f"{INVENTORY_LOC_THRESHOLD} LOC — inventory table omitted at_\n"
            "_scaffold time. Re-scan required.)_\n"
        )

    return frontmatter + header + sections + "\n".join(inventory_tables)


def cmd_init(
    args: argparse.Namespace, specs_dir: Path, repo_root: Path
) -> int:
    """Scaffold a new spec for a legacy code cluster.

    This is the implementation of the §23 bidirectional retrofit
    bootstrap path: when a legacy subsystem has no spec, `init`
    creates a minimal stub so the refactor pipeline has something
    to iterate on. The resulting file is explicitly marked as
    incomplete so `inventory-check` reports `status: stub` until a
    human has authored real content.

    Exit codes:
      0 — scaffolded successfully
      2 — usage error (bad id, missing --code-roots, output exists
          without --force, or code_roots missing without --allow-missing)
    """
    spec_id = args.spec_id
    if not _SPEC_ID_RE.match(spec_id):
        print(
            f"error: invalid spec id {spec_id!r} — must be a lowercase "
            "slug (a-z, 0-9, _, -), starting with a letter, max 64 chars",
            file=sys.stderr,
        )
        return 2

    code_roots: list[str] = list(args.code_roots or [])
    if not code_roots:
        print(
            "error: at least one --code-roots argument is required",
            file=sys.stderr,
        )
        return 2

    out_path = specs_dir / f"{spec_id}.md"
    if out_path.exists() and not args.force:
        print(
            f"error: {out_path} already exists (use --force to overwrite)",
            file=sys.stderr,
        )
        return 2

    missing: list[str] = []
    for rel in code_roots:
        abs_path = (repo_root / rel).resolve()
        if not abs_path.exists():
            missing.append(rel)
    if missing and not args.allow_missing:
        print(
            "error: code_roots do not exist (use --allow-missing to ignore):",
            file=sys.stderr,
        )
        for rel in missing:
            print(f"  - {rel}", file=sys.stderr)
        return 2

    title = args.title or _default_title_from_id(spec_id)
    today = args.date or _today_iso()

    body = scaffold_spec_body(
        spec_id=spec_id,
        title=title,
        code_roots=code_roots,
        repo_root=repo_root,
        today=today,
        motivating_decision=getattr(args, "motivating_decision", None),
        lifecycle=getattr(args, "lifecycle", None),
    )

    specs_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")

    try:
        rel_out: Path | str = out_path.relative_to(repo_root)
    except ValueError:
        rel_out = out_path

    print(f"Scaffolded spec: {rel_out}")
    print(f"  Title:      {title}")
    print("  Status:     draft (stub)")
    print(f"  Code roots: {len(code_roots)}")
    for rel in code_roots:
        marker = "  (missing)" if rel in missing else ""
        print(f"    - {rel}{marker}")
    print()
    print("Next steps:")
    print(
        f"  1. Run `scripts/specs.py inventory-check {spec_id}` — expected "
        "status=STUB."
    )
    print(
        f"  2. Open {rel_out} and populate Goals / Architecture / "
        "Implementation / Exceptions."
    )
    print(
        "  3. Resume `/refactor-subsystem` from Phase 1.2 (Inventory) "
        "with a scout pass"
    )
    print(
        "     on each code_root to expand the auto-generated inventory."
    )
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="specs.py",
        description="Spec index + coverage CLI for ai-docs/specs/.",
    )
    p.add_argument(
        "--specs-dir",
        type=Path,
        default=None,
        help="Override specs directory (default: ai-docs/specs/)",
    )
    p.add_argument(
        "--index-path",
        type=Path,
        default=None,
        help="Override index JSON path (default: reports/architecture/spec-index.json)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Override repo root (default: script's parent.parent)",
    )

    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init",
        help="Scaffold a new stub spec for a legacy code cluster",
        description=(
            "Create a new stub spec for a legacy code cluster. Any .py "
            "code root above the inventory LOC threshold gets an "
            "auto-generated inventory table extracted via AST walk. All "
            "narrative sections are left as empty placeholders. The "
            "resulting spec is marked as a stub so `inventory-check` "
            "reports status=STUB until a human has authored real content."
        ),
    )
    p_init.add_argument(
        "spec_id",
        help="New spec id — lowercase slug (e.g. 'crawling-views').",
    )
    p_init.add_argument(
        "--code-roots",
        action="append",
        required=True,
        help=(
            "Repo-relative path to include as a code_root. Repeat for "
            "multiple roots (e.g. --code-roots core/views/crawling.py "
            "--code-roots core/services/crawling_service.py)."
        ),
    )
    p_init.add_argument(
        "--title",
        default=None,
        help="Override the spec title (default: derived from spec_id).",
    )
    p_init.add_argument(
        "--date",
        default=None,
        help="Override last_audited date (default: today in ISO 8601).",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the spec file if it already exists.",
    )
    p_init.add_argument(
        "--allow-missing",
        action="store_true",
        help="Allow code_roots that do not exist on disk yet.",
    )
    p_init.add_argument(
        "--motivating-decision",
        default=None,
        help=(
            "Optional ADR id (e.g. '0042') linking this spec back to the "
            "decision that authorized the work. Used by /plan-feature and "
            "the System-tier planning chain."
        ),
    )
    p_init.add_argument(
        "--lifecycle",
        default=None,
        choices=("proposed", "planned", "active", "shipped"),
        help=(
            "Optional planning-tier lifecycle marker. proposed=plan-feature "
            "stub; planned=approved for execution; active=in flight; "
            "shipped=closed."
        ),
    )

    p_list = sub.add_parser("list", help="List specs")
    p_list.add_argument(
        "--status", default=None, choices=["draft", "active", "in_progress", "deprecated"]
    )
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="Show one spec's items + ref counts")
    p_show.add_argument("spec_id")
    p_show.add_argument("--json", action="store_true")

    p_rb = sub.add_parser("rebuild", help="Rebuild spec-index.json")
    p_rb.add_argument("--dry-run", action="store_true")

    p_cov = sub.add_parser(
        "coverage",
        help="Audit one spec's checklist vs code refs",
        description=(
            "Audit one spec's checklist vs code-comment markers. SCOPE: "
            "scans Python `# spec:<id>::IM-N` comments inside the spec's "
            "`code_roots` only. HTML `<!-- spec: -->` markers and any "
            "files outside `code_roots` (docs under .claude/docs/, ADRs, "
            "skills under .claude/skills/, scripts/, etc.) are NOT "
            "scanned and will report as `checkmark_lag` if marked [x] "
            "in the spec. That lag is structural — track doc/skill/"
            "script IMs via the spec checklist and `<!-- spec: -->` "
            "audit-only markers; do not expand `code_roots` to chase "
            "coverage."
        ),
    )
    p_cov.add_argument("spec_id")
    p_cov.add_argument("--json", action="store_true")

    p_or = sub.add_parser("orphans", help="List code refs pointing at missing items")
    p_or.add_argument("--json", action="store_true")

    p_au = sub.add_parser("audit", help="Run coverage across every spec")
    p_au.add_argument("--json", action="store_true")

    p_so = sub.add_parser("solid", help="Run SOLID quality gates for a spec (Phase 6.3)")
    p_so.add_argument("spec_id")
    p_so.add_argument("--json", action="store_true")
    p_so.add_argument(
        "--mode",
        choices=("standard", "decomposition"),
        default="standard",
        help=(
            "standard (default): the Level 1 artifact is optional — "
            "Phase 1.2.5 is only mandatory for decomposition refactors; "
            "decomposition: the phase-1-solid-audit.md artifact is required."
        ),
    )

    p_sz = sub.add_parser("size-check", help="Warn/error on oversized specs")
    p_sz.add_argument("--json", action="store_true")

    p_inv = sub.add_parser(
        "inventory-check",
        help="Compare a spec's narrative inventory to code symbols",
    )
    p_inv.add_argument("spec_id")
    p_inv.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any mismatch or stub warning is detected",
    )

    p_vio = sub.add_parser(
        "violations",
        help="Grep anti-patterns declared in a spec and report compliance",
    )
    p_vio.add_argument("spec_id")
    p_vio.add_argument("--json", action="store_true")
    p_vio.add_argument(
        "--item",
        default=None,
        help="Filter to a single enforcement item id (e.g. AR-2)",
    )
    p_vio.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any item's compliance is below 80%%",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    specs_dir = (args.specs_dir or DEFAULT_SPECS_DIR).resolve()
    index_path = args.index_path or DEFAULT_INDEX_PATH
    repo_root = (args.repo_root or REPO_ROOT).resolve()

    # `init` is a mutator and may run against an empty or missing
    # specs_dir — handle it before load_all_specs so scaffolding
    # works from a clean slate.
    if args.command == "init":
        return cmd_init(args, specs_dir, repo_root)

    try:
        specs = load_all_specs(specs_dir)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read specs dir {specs_dir}: {exc}", file=sys.stderr)
        return 2

    if args.command == "list":
        return cmd_list(args, specs)
    if args.command == "show":
        return cmd_show(args, specs, repo_root)
    if args.command == "rebuild":
        return cmd_rebuild(args, specs, repo_root, index_path)
    if args.command == "coverage":
        return cmd_coverage(args, specs, repo_root)
    if args.command == "orphans":
        return cmd_orphans(args, specs, repo_root)
    if args.command == "audit":
        return cmd_audit(args, specs, repo_root)
    if args.command == "solid":
        return cmd_solid(args, specs, repo_root)
    if args.command == "size-check":
        return cmd_size_check(args, specs)
    if args.command == "inventory-check":
        return cmd_inventory_check(args, specs, repo_root)
    if args.command == "violations":
        return cmd_violations(args, specs, repo_root)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
