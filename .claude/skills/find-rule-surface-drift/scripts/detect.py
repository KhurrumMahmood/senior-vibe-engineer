#!/usr/bin/env python3
"""Detect drift on the agent-rules surface (ADR 0005).

Detection bands:
  - oversized_root: CLAUDE.md exceeds the soft char budget.
  - oversized_doc:  a .claude/docs/*.md exceeds the per-doc budget.
  - dormant_doc:    docs/*.md exists with no row in CLAUDE.md's
                    Supplementary Documentation table.
  - missing_doc:    table row references a file not on disk.
  - unreferenced_doc: registered doc has no greppable references from
                    any other artifact under <root> (CLAUDE.md
                    excluded, since the registration itself is there).
  - missing_link:   ONBOARDING.md links to a path that doesn't exist on
                    disk — broken human-onboarding pointer.
  - dormant_in_onboarding: a doc registered in CLAUDE.md's table is
                    not linked from ONBOARDING.md. Info-level —
                    most agent-only docs legitimately stay unmentioned.

Output: JSONL with one finding per line. Each record has the keys
`pattern`, `file`, `lineno`, `summary`, `recommendation` so the shared
render_simple_report helper can render it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_MAX_ROOT_CHARS = 30_000
DEFAULT_MAX_DOC_CHARS = 50_000

BACKTICK_RE = re.compile(r"`([^`]+)`")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_onboarding_links(path: Path) -> list[tuple[str, int]]:
    """Return [(target, lineno)] for each local-file markdown link in `path`.

    Skips http(s):// and mailto: URLs and anchor-only links. Strips any
    trailing `#anchor` from each target so the existence check resolves
    against the file/directory path itself.
    """
    if not path.exists():
        return []
    links: list[tuple[str, int]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return links
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in MD_LINK_RE.finditer(line):
            if match.start() > 0 and line[match.start() - 1] == "!":
                continue  # image link `![alt](path)`, not a doc reference
            target = match.group(2).strip()
            if not target or "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            target = target.split("#", 1)[0]
            if target:
                links.append((target, lineno))
    return links


def resolve_onboarding_link(target: str, onboarding_md: Path, project_root: Path) -> Path:
    """Resolve a markdown link target to an absolute filesystem path.

    Absolute paths and leading-slash paths are interpreted as
    project-root-relative; everything else is relative to ONBOARDING.md's
    directory.
    """
    if target.startswith("/"):
        return project_root / target.lstrip("/")
    return onboarding_md.parent / target


def _safe_resolve(path: Path) -> Path:
    """Resolve `path` to an absolute filesystem path; return it unchanged on OSError."""
    try:
        return path.resolve()
    except OSError:
        return path


def parse_supplementary_table(claude_md_path: Path) -> list[tuple[str, int]]:
    """Return [(filename, lineno)] for each row of the Supplementary Documentation table.

    The table is recognized by a header row containing both "| File "
    and "Read when". Rows are parsed by extracting the first
    backtick-quoted token.
    """
    if not claude_md_path.exists():
        return []
    rows: list[tuple[str, int]] = []
    in_table = False
    try:
        text = claude_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return rows
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not in_table:
            if stripped.startswith("| File ") and "Read when" in stripped:
                in_table = True
            continue
        if stripped.startswith("|---"):
            continue
        if not stripped.startswith("|"):
            break  # End of table
        m = BACKTICK_RE.search(line)
        if m:
            rows.append((m.group(1), lineno))
    return rows


def resolve_doc_path(filename: str, docs_root: Path, project_root: Path) -> Path:
    """Resolve a table-row filename to an on-disk path.

    A leading slash means "project root" (`/CONTEXT.md`); anything else
    is interpreted relative to the docs subdir.
    """
    if filename.startswith("/"):
        return project_root / filename.lstrip("/")
    return docs_root / filename


def find_unreferenced(filename: str, claude_md_path: Path, root: Path) -> bool:
    """Return True if `filename` appears in no file under `root` other than `claude_md_path`."""
    result = subprocess.run(
        [
            "grep",
            "-rl",
            "--exclude-dir=worktrees",
            "--exclude-dir=__pycache__",
            "--",
            filename,
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return False  # treat grep error as "don't fire the band"
    claude_md_resolved = _safe_resolve(claude_md_path)
    for line in result.stdout.splitlines():
        if not line:
            continue
        try:
            resolved = Path(line).resolve()
        except OSError:
            continue
        if resolved != claude_md_resolved:
            return False
    return True


def detect(
    *,
    project_root: Path,
    claude_root: Path,
    claude_md_path: Path,
    docs_root: Path,
    max_root_chars: int,
    max_doc_chars: int,
    onboarding_md_path: Path | None = None,
) -> list[dict]:
    findings: list[dict] = []

    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            return str(path)

    # 1. oversized_root
    if claude_md_path.exists():
        try:
            char_count = len(claude_md_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            char_count = 0
        if char_count > max_root_chars:
            findings.append({
                "pattern": "oversized_root",
                "file": rel(claude_md_path),
                "lineno": 1,
                "summary": (
                    f"CLAUDE.md is {char_count:,} chars (> {max_root_chars:,} soft budget)."
                ),
                "recommendation": (
                    "Demote content to load-on-demand docs in .claude/docs/ and register the "
                    "trigger in the Supplementary Documentation table. Don't subdivide into "
                    "more bullets at root — every always-loaded character competes with every "
                    "other for the agent's attention."
                ),
            })

    # 2. oversized_doc — top-level docs only
    if docs_root.is_dir():
        for doc in sorted(docs_root.glob("*.md")):
            if doc.parent != docs_root:
                continue
            try:
                char_count = len(doc.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            if char_count > max_doc_chars:
                findings.append({
                    "pattern": "oversized_doc",
                    "file": rel(doc),
                    "lineno": 1,
                    "summary": (
                        f"{doc.name} is {char_count:,} chars (> {max_doc_chars:,} per-doc budget)."
                    ),
                    "recommendation": (
                        "Consider whether this is one topic or two. If it's a legitimate "
                        "inventory (subsystem map, full catalogue, exhaustive reference), "
                        "raise the per-doc threshold or note the exemption; otherwise split "
                        "by topic or extract a glossary section."
                    ),
                })

    # 3. + 4. parse table, resolve every row once, share the result with §5/§7.
    table_rows = parse_supplementary_table(claude_md_path)
    registered_basenames: set[str] = set()
    resolved_rows: list[tuple[str, int, Path, bool]] = []
    for filename, lineno in table_rows:
        resolved = resolve_doc_path(filename, docs_root, project_root)
        exists = resolved.exists()
        resolved_rows.append((filename, lineno, resolved, exists))
        if not filename.startswith("/"):
            registered_basenames.add(filename)
        if not exists:
            findings.append({
                "pattern": "missing_doc",
                "file": rel(claude_md_path),
                "lineno": lineno,
                "summary": (
                    f"Supplementary Documentation table references `{filename}` but no file "
                    f"exists at {rel(resolved)}."
                ),
                "recommendation": (
                    "Either remove the table row or create the doc. A row pointing at nothing "
                    "trains agents to expect content that isn't there."
                ),
            })

    # 3. dormant_doc — every top-level docs/*.md should appear in the table
    if docs_root.is_dir():
        for doc in sorted(docs_root.glob("*.md")):
            if doc.parent != docs_root:
                continue
            if doc.name not in registered_basenames:
                findings.append({
                    "pattern": "dormant_doc",
                    "file": rel(doc),
                    "lineno": 1,
                    "summary": (
                        f"`{doc.name}` exists under `.claude/docs/` but has no row in "
                        "CLAUDE.md's Supplementary Documentation table."
                    ),
                    "recommendation": (
                        "Add a 'Read when…' trigger row to the table, or remove the doc. "
                        "Load-on-demand docs without a trigger row are unreachable by design."
                    ),
                })

    # 5. unreferenced_doc — file exists, in table, but no grep hits outside CLAUDE.md
    for filename, lineno, resolved, exists in resolved_rows:
        if not exists:
            continue  # already reported as missing_doc
        if find_unreferenced(filename, claude_md_path, claude_root):
            findings.append({
                "pattern": "unreferenced_doc",
                "file": rel(resolved),
                "lineno": lineno,
                "summary": (
                    f"`{filename}` is registered in the Supplementary Documentation table but "
                    f"appears in no other artifact under {rel(claude_root)}."
                ),
                "recommendation": (
                    "Confirm the doc is reachable via its trigger only (legitimate; ignore the "
                    "finding) or check whether it has gone dead and should be pruned."
                ),
            })

    # 6. + 7. ONBOARDING.md scanning (human entry point)
    if onboarding_md_path and onboarding_md_path.exists():
        links = parse_onboarding_links(onboarding_md_path)
        linked_paths: set[Path] = set()
        for target, lineno in links:
            resolved = resolve_onboarding_link(target, onboarding_md_path, project_root)
            linked_paths.add(_safe_resolve(resolved))
            if not resolved.exists():
                findings.append({
                    "pattern": "missing_link",
                    "file": rel(onboarding_md_path),
                    "lineno": lineno,
                    "summary": (
                        f"ONBOARDING.md links to `{target}` but no file or directory exists at "
                        f"{rel(resolved)}."
                    ),
                    "recommendation": (
                        "Either fix the link target or remove the link. ONBOARDING.md is the "
                        "human entry point — broken links here block onboarding directly. If "
                        "the target moved, update the link to its new path; if it was deleted, "
                        "remove this section or replace it with the closest live equivalent."
                    ),
                })

        # dormant_in_onboarding — registered docs that ONBOARDING.md doesn't link.
        # Info-level: many agent-only docs legitimately stay unmentioned. Points
        # at the CLAUDE.md row (file + lineno) so editor jumps land at the
        # registration site, where the curator decides whether to add a human
        # follow-up.
        for filename, lineno, resolved, exists in resolved_rows:
            if not exists:
                continue  # already reported as missing_doc
            if _safe_resolve(resolved) in linked_paths:
                continue
            findings.append({
                "pattern": "dormant_in_onboarding",
                "file": rel(claude_md_path),
                "lineno": lineno,
                "summary": (
                    f"`{filename}` is registered in CLAUDE.md's Supplementary Documentation "
                    "table but is not linked from ONBOARDING.md."
                ),
                "recommendation": (
                    "Info-level only. Most agent-targeted docs (oracle, model-tiering, "
                    "deployment, sub-agents, etc.) legitimately don't appear in human "
                    "onboarding. Use this finding when triaging newly-registered docs to "
                    "decide whether the human path should reference them. No blocking action."
                ),
            })

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".claude"), help="Claude root directory")
    parser.add_argument("--claude-md", type=Path, help="Path to CLAUDE.md (default: <root>/CLAUDE.md)")
    parser.add_argument("--docs-subdir", default="docs", help="Subdir under root holding load-on-demand docs")
    parser.add_argument(
        "--onboarding-md",
        type=Path,
        help="Path to ONBOARDING.md (default: <project-root>/ONBOARDING.md). "
        "Pass an empty string or a non-existent path to skip the onboarding bands.",
    )
    parser.add_argument("--max-root-chars", type=int, default=DEFAULT_MAX_ROOT_CHARS)
    parser.add_argument("--max-doc-chars", type=int, default=DEFAULT_MAX_DOC_CHARS)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    claude_root = (args.root if args.root.is_absolute() else (Path.cwd() / args.root)).resolve()
    claude_md_path = args.claude_md if args.claude_md else (claude_root / "CLAUDE.md")
    docs_root = claude_root / args.docs_subdir
    onboarding_md_path = args.onboarding_md if args.onboarding_md else (project_root / "ONBOARDING.md")

    findings = detect(
        project_root=project_root,
        claude_root=claude_root,
        claude_md_path=claude_md_path,
        docs_root=docs_root,
        max_root_chars=args.max_root_chars,
        max_doc_chars=args.max_doc_chars,
        onboarding_md_path=onboarding_md_path,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for finding in findings:
            f.write(json.dumps(finding) + "\n")

    print(f"detect: wrote {len(findings)} findings to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
