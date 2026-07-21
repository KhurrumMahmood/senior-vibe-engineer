#!/usr/bin/env python3
"""Self-contained filesystem and report helpers for find-comment-drift."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "generated",
    "migrations",
    "node_modules",
    "reports",
    "staticfiles",
    "test",
    "tests",
    "__tests__",
    "vendor",
    "venv",
}

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


def resolve_project_root(explicit: Path | None = None) -> Path:
    """Use the explicit host root, git toplevel, or current directory."""
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd()
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return cwd.resolve()
    root = result.stdout.strip()
    return Path(root).resolve() if root else cwd.resolve()


def iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """Return supported files below ``root`` while skipping generated trees."""
    if not root.exists():
        return []

    root = root.resolve()

    def is_eligible(path: Path) -> bool:
        relative = path.relative_to(root)
        parent_parts = relative.parts[:-1]
        try:
            path.resolve().relative_to(root)
        except (OSError, ValueError):
            return False
        return (
            path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in suffixes
            and not path.name.lower().endswith((".min.js", ".min.jsx", ".min.mjs", ".min.cjs"))
            and not any(
                part in SKIP_DIRS or part.startswith(".") for part in parent_parts
            )
        )

    return sorted(
        path
        for path in root.rglob("*")
        if is_eligible(path)
    )


def relpath(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"cannot read required detections file {path}: {exc}") from None
    try:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSONL in required detections file {path}: {exc}") from None


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def probe_go() -> tuple[dict[str, Any], int]:
    """Return Go tool evidence plus the detector exit code for that evidence."""
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


def _go_exclusion(path: Path, project_root: Path, text: str | None) -> str | None:
    rel = path.relative_to(project_root)
    parent_parts = {part.lower() for part in rel.parts[:-1]}
    name = path.name.lower()
    if "vendor" in parent_parts:
        return "vendor"
    if parent_parts & GO_TEST_DIRS:
        return "test-tree"
    if name.endswith("_test.go"):
        return "test-file"
    if parent_parts & GO_GENERATED_DIRS:
        return "generated-tree"
    if name.endswith(("_generated.go", ".generated.go")) or name.startswith("zz_generated"):
        return "generated-file"
    if text is not None and GO_GENERATED_MARKER_RE.search(text[:2048]):
        return "generated-marker"
    return None


def inventory_go(
    targets: Iterable[str], project_root: Path
) -> tuple[list[dict[str, Any]], list[Path], list[str]]:
    """Inventory every selected Go file before applying comment eligibility."""
    project_root = project_root.resolve()
    discovered: dict[str, Path] = {}
    errors: list[str] = []
    for raw in targets:
        logical = Path(raw)
        logical = logical if logical.is_absolute() else project_root / logical
        logical = Path(os.path.abspath(logical))
        try:
            logical.relative_to(project_root)
        except ValueError:
            errors.append(f"target-outside-project:{raw}")
            continue
        if not logical.exists():
            errors.append(f"target-missing:{raw}")
            continue
        if logical.is_symlink():
            if logical.suffix.lower() == ".go":
                discovered[logical.relative_to(project_root).as_posix()] = logical
            continue
        if logical.is_file():
            if logical.suffix.lower() == ".go":
                discovered[logical.relative_to(project_root).as_posix()] = logical
            continue
        for directory, dirnames, filenames in os.walk(logical, followlinks=False):
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
        reason = _go_exclusion(path, project_root, text)
        if reason:
            inventory.append({"file": rel, "role": "excluded", "reason": reason})
            continue
        inventory.append({"file": rel, "role": "eligible"})
        eligible.append(path)
    return inventory, eligible, errors


def go_scan_payload(
    tool: dict[str, Any], inventory: list[dict[str, Any]], errors: list[str]
) -> dict[str, Any]:
    """Build the family-owned Go status and inventory artifact."""
    failed = sum(row["role"] == "failed" for row in inventory)
    status = "partial" if failed or errors else "complete"
    return {
        **tool,
        "status": status,
        "language": "go",
        "analyzer": "python-go-comment-lexer",
        "syntax_contract": "lexical-only; Go parse validity is not inspected",
        "inventory": inventory,
        "errors": errors,
        "summary": {
            "discovered": len(inventory),
            "eligible": sum(row["role"] == "eligible" for row in inventory),
            "excluded": sum(row["role"] == "excluded" for row in inventory),
            "failed": failed + len(errors),
        },
    }


def _java_exclusion(path: Path, project_root: Path, text: str | None) -> str | None:
    rel = path.relative_to(project_root)
    parent_parts = {part.casefold() for part in rel.parts[:-1]}
    name = path.name.casefold()
    if "vendor" in parent_parts:
        return "vendor"
    if parent_parts & JAVA_TEST_DIRS:
        return "test-tree"
    if parent_parts & JAVA_GENERATED_DIRS:
        return "generated-tree"
    if text is not None and JAVA_GENERATED_MARKER_RE.search(text[:4096]):
        return "generated-marker"
    if text is not None and JAVA_GENERATED_ANNOTATION_RE.search(text[:4096]):
        return "generated-annotation"
    if name.endswith(("test.java", "tests.java", "it.java")):
        return "test-file"
    if name.startswith("generated") or name.endswith("_generated.java"):
        return "generated-file"
    return None


def inventory_java(
    targets: Iterable[str], project_root: Path
) -> tuple[list[dict[str, Any]], list[Path], list[str]]:
    """Inventory every selected Java file before comment eligibility."""
    project_root = project_root.resolve()
    discovered: dict[str, Path] = {}
    errors: list[str] = []
    for raw in targets:
        logical = Path(raw)
        logical = logical if logical.is_absolute() else project_root / logical
        logical = Path(os.path.abspath(logical))
        try:
            logical.relative_to(project_root)
        except ValueError:
            errors.append(f"target-outside-project:{raw}")
            continue
        if not logical.exists():
            errors.append(f"target-missing:{raw}")
            continue
        if logical.is_symlink():
            if logical.suffix.casefold() == ".java":
                discovered[logical.relative_to(project_root).as_posix()] = logical
            continue
        if logical.is_file():
            if logical.suffix.casefold() == ".java":
                discovered[logical.relative_to(project_root).as_posix()] = logical
            continue
        for directory, dirnames, filenames in os.walk(logical, followlinks=False):
            current = Path(directory)
            dirnames[:] = sorted(
                name for name in dirnames if not (current / name).is_symlink()
            )
            for name in sorted(filenames):
                if name.casefold().endswith(".java"):
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
        reason = _java_exclusion(path, project_root, text)
        if reason:
            inventory.append({"file": rel, "role": "excluded", "reason": reason})
            continue
        inventory.append({"file": rel, "role": "eligible"})
        eligible.append(path)
    return inventory, eligible, errors


def java_scan_payload(
    inventory: list[dict[str, Any]], errors: list[str]
) -> dict[str, Any]:
    """Build the family-owned Java lexical status and inventory artifact."""
    failed = sum(row["role"] == "failed" for row in inventory)
    return {
        "status": "partial" if failed or errors else "complete",
        "language": "java",
        "analyzer": "python-java-comment-lexer",
        "syntax_contract": "lexical-only; Java parse validity is not inspected",
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
    scan: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    buckets: dict[str, int] = {}
    for record in records:
        key = str(record.get("pattern") or record.get("bucket") or "finding")
        buckets[key] = buckets.get(key, 0) + 1

    lines = [f"# {title}", ""]
    if scan:
        lines.extend(
            [
                f"**Status:** `{scan['status']}`",
                f"**Language:** `{scan['language']}`",
                f"**Analyzer:** `{scan['analyzer']}`",
            ]
        )
    lines.extend([f"**Target:** `{target}`", f"**Findings:** {len(records)}", ""])
    if buckets:
        lines.extend(["## Buckets", "", "| Bucket | Count |", "|---|---|"])
        for bucket, count in sorted(buckets.items()):
            lines.append(f"| `{bucket}` | {count} |")
        lines.append("")
    if records:
        lines.extend(["## Findings", ""])
        for index, record in enumerate(records, start=1):
            file = record.get("file", "?")
            line = record.get("lineno", "?")
            pattern = record.get("pattern", record.get("bucket", "finding"))
            summary = record.get("summary") or record.get("message") or record.get("evidence") or ""
            lines.extend([f"### {index}. `{pattern}`", "", f"- **Location:** `{file}:{line}`"])
            if summary:
                lines.append(f"- **Evidence:** {summary}")
            recommendation = record.get("recommendation")
            if recommendation:
                lines.append(f"- **Recommendation:** {recommendation}")
            lines.append("")

    payload: dict[str, Any] = {
        "summary": {"findings_total": len(records), "buckets": buckets},
        "findings": records,
    }
    if scan:
        payload["status"] = scan["status"]
        payload["analysis"] = {scan["language"]: scan}
    return "\n".join(lines), payload
