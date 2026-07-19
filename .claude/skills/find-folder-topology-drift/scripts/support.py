#!/usr/bin/env python3
"""Family-local scan scope and report helpers.

This module keeps the selected skill runnable after a stock copy.  It mirrors
only the scope behavior this detector needs: host-authored roots and ignores,
the repository-wide ignore, built-in noise pruning, and deterministic report
rendering.  It intentionally does not become a shared helper.
"""
from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


BUILTIN_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "__pycache__", "site-packages", "dist", "build", ".tox",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode",
    ".next", ".cache", "migrations",
})
BUILTIN_SKIP_PREFIXES = (".claude/worktrees", ".engineering")
_IGNORE_HEADINGS = {"ignore", "ignores", "skip", "path skip", "paths to skip"}
_ROOTS_HEADINGS = {"roots", "root", "scan", "scan roots", "include"}


@dataclass
class Scope:
    roots: list[str] | None = None
    ignore: list[str] = field(default_factory=list)


def _bullet_token(line: str) -> str | None:
    body = line[1:].strip()
    if "`" in body:
        start = body.index("`")
        end = body.find("`", start + 1)
        if end > start:
            return body[start + 1:end].strip() or None
    return body.split(" — ", 1)[0].strip() or None


def parse_scope(text: str) -> tuple[list[str] | None, list[str]]:
    roots: list[str] = []
    ignore: list[str] = []
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            section = "ignore" if heading in _IGNORE_HEADINGS else "roots" if heading in _ROOTS_HEADINGS else None
            continue
        if not line.startswith(("-", "*", "+")):
            continue
        token = _bullet_token(line)
        if not token:
            continue
        if section == "ignore":
            ignore.append(token)
        elif section == "roots":
            roots.append(token.rstrip("/"))
    return roots or None, ignore


def _read_scope_file(path: Path) -> tuple[list[str] | None, list[str]]:
    try:
        return parse_scope(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None, []


def load_scope(repo_root: Path, skill_name: str) -> Scope:
    path = repo_root / ".engineering" / "docs" / f"{skill_name}-scope.md"
    if not path.is_file():
        return Scope()
    roots, ignore = _read_scope_file(path)
    return Scope(roots=roots, ignore=ignore)


def load_repo_ignore(repo_root: Path) -> list[str]:
    path = repo_root / ".engineering" / "docs" / "ignore.md"
    if not path.is_file():
        return []
    _roots, ignore = _read_scope_file(path)
    return ignore


def path_matches(rel_posix: str, pattern: str) -> bool:
    normalized = pattern.rstrip("/")
    return (
        rel_posix == normalized
        or rel_posix.startswith(normalized + "/")
        or fnmatch.fnmatch(rel_posix, normalized)
        or fnmatch.fnmatch(rel_posix, normalized + "/*")
    )


def matches_any(rel_posix: str, patterns: Iterable[str]) -> bool:
    return any(path_matches(rel_posix, pattern) for pattern in patterns)


def iter_paths(repo_root: Path, scope: Scope) -> list[Path]:
    """Yield the legacy Python universe without importing repository helpers."""
    roots = scope.roots or None
    ignores = [*scope.ignore, *load_repo_ignore(repo_root)]
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        current = Path(dirpath)
        rel_dir = current.relative_to(repo_root).as_posix()
        kept: list[str] = []
        for name in dirnames:
            if name in BUILTIN_SKIP_DIRS:
                continue
            child_rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            if any(child_rel == prefix or child_rel.startswith(prefix + "/") for prefix in BUILTIN_SKIP_PREFIXES):
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            rel = path.relative_to(repo_root).as_posix()
            if roots and not matches_any(rel, roots):
                continue
            if matches_any(rel, ignores):
                continue
            out.append(path)
    return sorted(out)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"cannot read required detections file {path}: {exc}") from None
    try:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSONL in required detections file {path}: {exc}") from None


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_simple_report(title: str, records: list[dict[str, Any]], target: str, language: str) -> tuple[str, dict[str, Any]]:
    buckets: dict[str, int] = {}
    for record in records:
        pattern = str(record.get("pattern") or "finding")
        buckets[pattern] = buckets.get(pattern, 0) + 1
    lines = [
        f"# {title}",
        "",
        f"**Target:** `{target}`",
        f"**Language:** `{language}`",
        f"**Findings:** {len(records)}",
        "",
    ]
    if buckets:
        lines.extend(["## Buckets", "", "| Bucket | Count |", "|---|---|"])
        lines.extend(f"| `{pattern}` | {count} |" for pattern, count in sorted(buckets.items()))
        lines.append("")
    if records:
        lines.extend(["## Findings", ""])
        for index, record in enumerate(records, start=1):
            lines.extend([
                f"### {index}. `{record.get('pattern', 'finding')}`",
                "",
                f"- **Location:** `{record.get('file', '?')}:{record.get('lineno', '?')}`",
            ])
            if summary := record.get("summary"):
                lines.append(f"- **Evidence:** {summary}")
            if recommendation := record.get("recommendation"):
                lines.append(f"- **Recommendation:** {recommendation}")
            lines.append("")
    return "\n".join(lines), {
        "scan_meta": {
            "language": language,
            "supported_patterns": sorted(buckets),
            "target": target,
        },
        "summary": {"findings_total": len(records), "buckets": buckets},
        "findings": records,
    }
