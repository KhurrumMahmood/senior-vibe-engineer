#!/usr/bin/env python3
"""Self-contained function inventory for the Python semantic-duplication path.

The old repository-level inventory also emitted workflow and artifact records
that the semantic-duplication pipeline never consumed.  This local helper
keeps the installed Python path honest: it inventories Python functions and
methods, preserves complete source spans, validates scout summaries, prepares
function comparison prompts, and provides optional lightweight caller counts.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


SOURCE_SUFFIX = ".py"
SKIP_DIRECTORIES = frozenset({
    ".git", ".venv", "venv", "__pycache__", "node_modules", "dist",
    "build", "coverage", "migrations", "tests", "test", "fixtures",
    "fixture", "generated", "vendor",
})
SKIP_NAME_PREFIXES = ("test_", "tests_")
SKIP_NAMES = frozenset({"setUp", "tearDown", "setUpClass", "tearDownClass"})

DEFINITION_FIELDS: dict[str, type | tuple[type, ...]] = {
    "type": str,
    "file": str,
    "name": str,
    "qualified_name": str,
    "line": int,
    "end_line": int,
    "kind": str,
    "arity": int,
    "size": int,
    "tier": str,
    "parent_class": (str, type(None)),
    "decorators": list,
    "domain_hint": str,
    "source": str,
}
SUMMARY_FIELDS: dict[str, type | tuple[type, ...]] = {
    "type": str,
    "file": str,
    "name": str,
    "qualified_name": str,
    "line": int,
    "end_line": int,
    "kind": str,
    "size": int,
    "tier": str,
    "purpose": str,
    "domain": str,
    "inputs": str,
    "outputs": str,
    "side_effects": list,
    "key_operations": list,
}


class InventoryError(ValueError):
    """A user-facing inventory precondition failure."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_project_path(project_root: Path, raw: str, label: str) -> Path:
    candidate = (project_root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if not _inside(project_root, candidate):
        raise InventoryError(f"{label} must stay inside project root: {raw}")
    return candidate


def _is_excluded(project_root: Path, path: Path, *, directory: bool = False) -> bool:
    relative = path.relative_to(project_root)
    parts = relative.parts if directory else relative.parts[:-1]
    if any(part.lower() in SKIP_DIRECTORIES for part in parts):
        return True
    if directory:
        return False
    name = path.name.lower()
    return name.startswith(SKIP_NAME_PREFIXES) or name == "conftest.py"


def _tier(size: int) -> str:
    if size <= 10:
        return "skip"
    if size <= 30:
        return "light"
    if size <= 100:
        return "full"
    return "priority"


def _decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    values: list[str] = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            values.append(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            values.append(decorator.attr)
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                values.append(decorator.func.id)
            elif isinstance(decorator.func, ast.Attribute):
                values.append(decorator.func.attr)
    return values


def _domain_hint(relative: str) -> str:
    lowered = relative.lower()
    for name in ("auth", "export", "extract", "crawl", "pricing", "email", "api"):
        if name in lowered:
            return name
    return "utility"


def _record(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    file: str,
    source: str,
    parent_class: str | None,
) -> dict[str, Any]:
    end_line = getattr(node, "end_lineno", node.lineno)
    arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    has_self = bool(arguments) and arguments[0].arg in {"self", "cls"}
    qname = f"{parent_class}.{node.name}" if parent_class else node.name
    segment = ast.get_source_segment(source, node) or ""
    return {
        "type": "def",
        "file": file,
        "name": node.name,
        "qualified_name": qname,
        "line": node.lineno,
        "end_line": end_line,
        "kind": "method" if parent_class else "function",
        "arity": len(arguments) - int(has_self),
        "size": end_line - node.lineno + 1,
        "tier": _tier(end_line - node.lineno + 1),
        "parent_class": parent_class,
        "decorators": _decorators(node),
        "domain_hint": _domain_hint(file),
        "source": segment,
    }


def _collect_file(project_root: Path, path: Path) -> list[dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        print(f"[semantic_inventory] WARN skipping {path}: {error}", file=sys.stderr)
        return []
    relative = path.relative_to(project_root).as_posix()
    records: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in SKIP_NAMES or node.name.startswith("__"):
                continue
            records.append(_record(node, file=relative, source=source, parent_class=None))
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if child.name in SKIP_NAMES or child.name.startswith("__"):
                    continue
                records.append(_record(child, file=relative, source=source, parent_class=node.name))
    return records


def _iter_sources(project_root: Path, target: Path) -> list[Path]:
    if target.is_symlink():
        raise InventoryError(f"target must not be a symbolic link: {target}")
    if target.is_file():
        if target.suffix != SOURCE_SUFFIX:
            raise InventoryError(f"target must be a Python file or directory: {target}")
        return [] if _is_excluded(project_root, target) else [target]
    if not target.is_dir():
        raise InventoryError(f"target must be a Python file or directory: {target}")
    if _is_excluded(project_root, target, directory=True):
        return []
    output: list[Path] = []
    for root, dirs, files in os.walk(target, followlinks=False):
        root_path = Path(root)
        dirs[:] = [
            name for name in dirs
            if not (root_path / name).is_symlink()
            and not _is_excluded(project_root, root_path / name, directory=True)
        ]
        for name in files:
            path = root_path / name
            if path.suffix == SOURCE_SUFFIX and not path.is_symlink() and not _is_excluded(project_root, path):
                output.append(path)
    return sorted(output)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def cmd_collect(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        raise InventoryError(f"project root is not a directory: {args.project_root}")
    target = _resolve_project_path(project_root, args.target, "target")
    records = [record for path in _iter_sources(project_root, target) for record in _collect_file(project_root, path)]
    _write_jsonl(Path(args.output), records)
    print(f"[semantic_inventory] collected={len(records)} output={args.output}")
    return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InventoryError(f"invalid JSONL at {path}: {error}") from error


def cmd_callers(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    definitions = [record for record in _read_jsonl(Path(args.inventory)) if record.get("type") == "def"]
    sources = _iter_sources(project_root, project_root)
    all_text = {path.relative_to(project_root).as_posix(): path.read_text(encoding="utf-8") for path in sources}
    records: list[dict[str, Any]] = []
    for definition in definitions:
        name = definition["name"]
        matches: list[str] = []
        pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
        for file, text in all_text.items():
            count = len(pattern.findall(text))
            if file == definition["file"]:
                count = max(count - 1, 0)
            if count:
                matches.extend([file] * count)
        records.append({
            "type": "caller_info",
            "qualified_name": definition["qualified_name"],
            "file": definition["file"],
            "total_refs": len(matches),
            "ref_files": sorted(set(matches)),
            "categorized": {"static_name_calls": len(matches)},
        })
    _write_jsonl(Path(args.output), records)
    print(f"[semantic_inventory] callers={len(records)} output={args.output}")
    return 0


def cmd_prompts(args: argparse.Namespace) -> int:
    summaries = _read_jsonl(Path(args.summaries))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in summaries:
        groups[str(record.get("domain") or "utility")].append(record)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for domain, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        compact = [{
            key: item[key] for key in (
                "file", "name", "qualified_name", "line", "end_line", "kind", "size", "tier",
            )
        } | {
            "purpose": item.get("purpose", ""),
            "key_operations": item.get("key_operations", []),
            "inputs": item.get("inputs", ""),
            "outputs": item.get("outputs", ""),
        } for item in items]
        payload = {
            "type": "comparison_prompt",
            "domain": domain,
            "item_count": len(compact),
            "items": compact,
            "output_schema": "candidate",
            "output_template": {
                "id": "SC-{n}", "level": "function", "similarity": 0,
                "a": {"qualified_name": "", "file": "", "line": 0, "end_line": 0, "size": 0},
                "b": {"qualified_name": "", "file": "", "line": 0, "end_line": 0, "size": 0},
                "rationale": "",
            },
            "instructions": "Nominate only function pairs that solve the same problem with different code.",
        }
        (output_dir / f"prompt_{domain}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        count += 1
    print(f"[semantic_inventory] prompts={count} output={output_dir}")
    return 0


def _validate(record: dict[str, Any], schema: str) -> list[str]:
    fields = DEFINITION_FIELDS if schema == "definition" else SUMMARY_FIELDS
    errors: list[str] = []
    for key, expected in fields.items():
        if key not in record:
            errors.append(f"missing {key}")
        elif not isinstance(record[key], expected):
            errors.append(f"{key} has wrong type")
    if schema == "definition" and record.get("type") != "def":
        errors.append("definition type must be def")
    if schema == "summary" and record.get("type") != "summary":
        errors.append("summary type must be summary")
    if isinstance(record.get("line"), int) and isinstance(record.get("end_line"), int) and record["end_line"] < record["line"]:
        errors.append("end_line precedes line")
    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    records = _read_jsonl(Path(args.file))
    schema = args.schema
    if not records:
        print(f"FAIL: input {args.file!r} contains no records")
        return 1
    failures = 0
    for index, record in enumerate(records):
        selected = schema
        if selected == "auto":
            selected = "definition" if record.get("type") == "def" else "summary" if record.get("type") == "summary" else "unknown"
        errors = _validate(record, selected) if selected in {"definition", "summary"} else ["unknown record type"]
        if errors:
            failures += 1
            if args.verbose:
                print(f"record {index}: {', '.join(errors)}", file=sys.stderr)
    status = "PASS" if failures == 0 else "FAIL"
    print(f"{status}: {len(records) - failures}/{len(records)} records valid")
    return int(failures > 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    collect = subcommands.add_parser("collect")
    collect.add_argument("--target", required=True)
    collect.add_argument("--project-root", required=True)
    collect.add_argument("--output", "-o", required=True)
    callers = subcommands.add_parser("callers")
    callers.add_argument("inventory")
    callers.add_argument("--project-root", required=True)
    callers.add_argument("--output", "-o", required=True)
    prompts = subcommands.add_parser("prompts")
    prompts.add_argument("summaries")
    prompts.add_argument("--output-dir", required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("file")
    validate.add_argument("--schema", choices=("auto", "definition", "summary"), default="auto")
    validate.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    try:
        return {
            "collect": cmd_collect,
            "callers": cmd_callers,
            "prompts": cmd_prompts,
            "validate": cmd_validate,
        }[args.command](args)
    except InventoryError as error:
        print(f"[semantic_inventory] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
