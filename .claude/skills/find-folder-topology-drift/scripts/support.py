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
import re
import shutil
import subprocess
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
GO_MINIMUM_VERSION = (1, 22, 0)
GO_MINIMUM_VERSION_TEXT = "1.22.0"
GO_TEST_DIRS = frozenset({"test", "tests", "__tests__", "testdata", "fixtures"})
GO_GENERATED_DIRS = frozenset({"generated", "gen"})
GO_GENERATED_MARKER_RE = re.compile(
    r"^// Code generated .* DO NOT EDIT\.$", re.MULTILINE
)
JAVA_TEST_DIRS = frozenset(
    {"test", "tests", "__tests__", "testdata", "fixtures", "integrationtest", "testfixtures"}
)
JAVA_GENERATED_DIRS = frozenset({"generated", "gen", "target", "build", "out", ".gradle"})
JAVA_GENERATED_MARKER_RE = re.compile(
    r"^\s*// Code generated .* DO NOT EDIT\.\s*$", re.MULTILINE
)
JAVA_GENERATED_ANNOTATION_RE = re.compile(
    r"^\s*@(?:javax\.annotation\.processing\.)?Generated(?:\s*\(|\s*$)", re.MULTILINE
)
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


def probe_go() -> tuple[dict[str, Any], int]:
    """Discover the Go 1.22+ toolchain and preserve outcome distinctions."""
    go_path = shutil.which("go")
    if not go_path:
        return {
            "status": "unsupported",
            "failure_kind": "go-tool-missing",
            "minimum_go_version": GO_MINIMUM_VERSION_TEXT,
        }, 2
    try:
        result = subprocess.run(
            [go_path, "version"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        return {
            "status": "failed",
            "failure_kind": "go-version-failed",
            "detail": str(exc),
            "go_path": go_path,
            "minimum_go_version": GO_MINIMUM_VERSION_TEXT,
        }, 1
    if result.returncode != 0:
        return {
            "status": "failed",
            "failure_kind": "go-version-failed",
            "detail": (result.stderr or result.stdout).strip(),
            "go_path": go_path,
            "minimum_go_version": GO_MINIMUM_VERSION_TEXT,
        }, 1
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.(\d+))?\b", result.stdout)
    if not match:
        return {
            "status": "failed",
            "failure_kind": "go-version-unrecognized",
            "detail": result.stdout.strip(),
            "go_path": go_path,
            "minimum_go_version": GO_MINIMUM_VERSION_TEXT,
        }, 1
    version = tuple(int(value or 0) for value in match.groups())
    evidence = {
        "go_path": go_path,
        "go_version": match.group(0),
        "minimum_go_version": GO_MINIMUM_VERSION_TEXT,
    }
    if version < GO_MINIMUM_VERSION:
        return {
            **evidence,
            "status": "unsupported",
            "failure_kind": "go-version-too-old",
        }, 2
    return {**evidence, "status": "complete"}, 0


def _go_exclusion(
    path: Path, project_root: Path, text: str | None, excludes: list[str]
) -> str | None:
    rel = path.relative_to(project_root)
    rel_text = rel.as_posix()
    parents = {part.lower() for part in rel.parts[:-1]}
    name = path.name.lower()
    if "vendor" in parents:
        return "vendor"
    if parents & GO_TEST_DIRS:
        return "test-tree"
    if name.endswith("_test.go"):
        return "test-file"
    if parents & GO_GENERATED_DIRS:
        return "generated-tree"
    if name.endswith(("_generated.go", ".generated.go")) or name.startswith("zz_generated"):
        return "generated-file"
    if text is not None and GO_GENERATED_MARKER_RE.search(text[:2048]):
        return "generated-marker"
    if matches_any(rel_text, excludes):
        return "declared-exclude"
    return None


def inventory_go(
    roots: Iterable[Path], project_root: Path, excludes: list[str]
) -> tuple[list[dict[str, Any]], list[Path], list[str]]:
    """Inventory every selected Go file before filename eligibility rules."""
    project_root = project_root.resolve()
    discovered: dict[str, Path] = {}
    errors: list[str] = []
    for root in roots:
        if root.is_symlink():
            errors.append(f"symlink-root:{root.relative_to(project_root).as_posix()}")
            continue
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(directory)
            dirnames[:] = sorted(
                name for name in dirnames if not (current / name).is_symlink()
            )
            for name in sorted(filenames):
                if not name.lower().endswith(".go"):
                    continue
                path = current / name
                discovered[path.relative_to(project_root).as_posix()] = path

    inventory: list[dict[str, Any]] = []
    eligible: list[Path] = []
    for rel, path in sorted(discovered.items()):
        if path.is_symlink():
            inventory.append({"file": rel, "role": "excluded", "reason": "symlink"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            inventory.append(
                {"file": rel, "role": "failed", "reason": "read-error", "detail": str(exc)}
            )
            continue
        reason = _go_exclusion(path, project_root, text, excludes)
        if reason:
            inventory.append({"file": rel, "role": "excluded", "reason": reason})
            continue
        inventory.append({"file": rel, "role": "eligible"})
        eligible.append(path)
    return inventory, eligible, errors


def go_scan_payload(
    tool: dict[str, Any], inventory: list[dict[str, Any]], errors: list[str]
) -> dict[str, Any]:
    failed = sum(row["role"] == "failed" for row in inventory)
    return {
        **tool,
        "status": "partial" if failed or errors else "complete",
        "language": "go",
        "analyzer": "python-filesystem-names",
        "syntax_contract": "filename-only; Go parse validity is not inspected",
        "inventory": inventory,
        "errors": errors,
        "summary": {
            "discovered": len(inventory),
            "eligible": sum(row["role"] == "eligible" for row in inventory),
            "excluded": sum(row["role"] == "excluded" for row in inventory),
            "failed": failed + len(errors),
        },
    }


def _java_exclusion(
    path: Path, project_root: Path, text: str | None, excludes: list[str]
) -> str | None:
    rel = path.relative_to(project_root)
    rel_text = rel.as_posix()
    parents = {part.casefold() for part in rel.parts[:-1]}
    name = path.name
    if "vendor" in parents:
        return "vendor"
    if parents & JAVA_TEST_DIRS:
        return "test-tree"
    if parents & JAVA_GENERATED_DIRS:
        return "generated-tree"
    if text is not None and JAVA_GENERATED_MARKER_RE.search(text[:4096]):
        return "generated-marker"
    if text is not None and JAVA_GENERATED_ANNOTATION_RE.search(text[:4096]):
        return "generated-annotation"
    if re.search(r"(?:Test|Tests|IT)\.java$", name):
        return "test-file"
    if name.startswith("Generated") or name.endswith("_Generated.java"):
        return "generated-file"
    if matches_any(rel_text, excludes):
        return "declared-exclude"
    return None


def inventory_java(
    roots: Iterable[Path], project_root: Path, excludes: list[str]
) -> tuple[list[dict[str, Any]], list[Path], list[str]]:
    """Inventory every selected Java file before filename eligibility rules."""
    project_root = project_root.resolve()
    discovered: dict[str, Path] = {}
    errors: list[str] = []
    for root in roots:
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(directory)
            dirnames[:] = sorted(
                name for name in dirnames if not (current / name).is_symlink()
            )
            for name in sorted(filenames):
                if not name.casefold().endswith(".java"):
                    continue
                path = current / name
                discovered[path.relative_to(project_root).as_posix()] = path

    inventory: list[dict[str, Any]] = []
    eligible: list[Path] = []
    for rel, path in sorted(discovered.items()):
        if path.is_symlink():
            inventory.append({"file": rel, "role": "excluded", "reason": "symlink"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            inventory.append(
                {"file": rel, "role": "failed", "reason": "read-error", "detail": str(exc)}
            )
            continue
        reason = _java_exclusion(path, project_root, text, excludes)
        if reason:
            inventory.append({"file": rel, "role": "excluded", "reason": reason})
            continue
        inventory.append({"file": rel, "role": "eligible"})
        eligible.append(path)
    return inventory, eligible, errors


def java_scan_payload(
    inventory: list[dict[str, Any]], errors: list[str]
) -> dict[str, Any]:
    failed = sum(row["role"] == "failed" for row in inventory)
    return {
        "status": "partial" if failed or errors else "complete",
        "language": "java",
        "analyzer": "python-filesystem-names",
        "syntax_contract": "filename-only; Java parse validity is not inspected",
        "inventory": inventory,
        "errors": errors,
        "summary": {
            "discovered": len(inventory),
            "eligible": sum(row["role"] == "eligible" for row in inventory),
            "excluded": sum(row["role"] == "excluded" for row in inventory),
            "failed": failed + len(errors),
        },
    }


def render_simple_report(
    title: str,
    records: list[dict[str, Any]],
    target: str,
    language: str,
    scan: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    buckets: dict[str, int] = {}
    for record in records:
        pattern = str(record.get("pattern") or "finding")
        buckets[pattern] = buckets.get(pattern, 0) + 1
    lines = [
        f"# {title}",
        "",
        *([f"**Status:** `{scan['status']}`"] if scan else []),
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
    payload: dict[str, Any] = {
        "scan_meta": {
            "language": language,
            "supported_patterns": sorted(buckets),
            "target": target,
        },
        "summary": {"findings_total": len(records), "buckets": buckets},
        "findings": records,
    }
    if scan:
        payload["status"] = scan["status"]
        payload["analysis"] = {scan["language"]: scan}
    return "\n".join(lines), payload
