#!/usr/bin/env python3
"""AST-based "defined but never referenced" detector.

Walks the target directory, extracts every top-level def/class/method,
then uses `git grep -w` to check whether the name has any non-definition
reference anywhere in the repo. Emits JSONL candidates that survive both
the cross-file and same-file reference checks.

Output (one JSON record per line at `--output`):
{
  "type": "unreferenced_def",
  "file": "core/services/foo.py",
  "line": 42,
  "name": "FooHelper",
  "qualified_name": "FooHelper",          # or "FooService.helper"
  "kind": "function | async_function | class | method"
}

The detector is intentionally *lenient* — it does not filter Django
false positives, it does not check templates, it does not do any of the
6a-6f verification. That's the scout's job. If the scout reads the JSON
and sees a CBV dispatch method, it buckets as false_positive.

The detector's only goal: reduce the candidate set from "every def in
the codebase" (~10,000 in core/) to "plausibly unreferenced" (~dozens to
a few hundred). It errs toward more candidates so scouts can do the
real verification work.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
})

_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
    "vendor_*.py",
)

# Names that Python / Django will always dispatch to by string — grepping
# for them via `git grep -w` doesn't tell you if they're dead. The scout
# is responsible for the deeper false-positive analysis; these just keep
# the candidate file short.
_HARD_SKIP_NAMES: frozenset[str] = frozenset({
    # Dunders
    "__init__", "__str__", "__repr__", "__len__", "__iter__",
    "__enter__", "__exit__", "__eq__", "__hash__", "__call__",
    "__getitem__", "__setitem__", "__contains__",
    # Python / Django / test scaffolding dispatched by attribute name
    "setUp", "tearDown", "setUpClass", "tearDownClass", "setUpTestData",
    # Django AppConfig lifecycle
    "ready",
    # Django management command entry
    "handle", "add_arguments",
    # Django CBV handlers
    "get", "post", "put", "delete", "patch", "head", "options", "dispatch",
    "form_valid", "form_invalid", "get_queryset", "get_context_data",
    "get_object", "get_form_class", "get_success_url", "get_initial",
    # Django model lifecycle
    "save", "clean", "full_clean",
    # DRF viewset actions
    "list", "retrieve", "create", "update", "partial_update", "destroy",
    "perform_create", "perform_update", "perform_destroy",
    # Django Admin
    "get_actions",
    # Inner classes
    "Meta",
})


def _walk_python_files(
    target: Path, skip_globs: tuple[str, ...]
) -> list[Path]:
    files: list[Path] = []
    for path in target.rglob("*.py"):
        if any(part in _DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if any(fnmatch.fnmatchcase(path.name, g) for g in skip_globs):
            continue
        files.append(path)
    return files


def _extract_defs(filepath: Path) -> list[dict[str, object]]:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []

    out: list[dict[str, object]] = []

    def walk(node: ast.AST, class_stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                if child.name in _HARD_SKIP_NAMES:
                    walk(child, class_stack + [child.name])
                    continue
                qual = ".".join(class_stack + [child.name])
                out.append({
                    "name": child.name,
                    "qualified_name": qual,
                    "line": child.lineno,
                    "kind": "class",
                    "is_method": bool(class_stack),
                })
                walk(child, class_stack + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name in _HARD_SKIP_NAMES:
                    continue
                # Skip decorated methods that Django dispatches dynamically
                if any(
                    _is_dynamic_dispatch_decorator(d) for d in child.decorator_list
                ):
                    continue
                qual = ".".join(class_stack + [child.name])
                out.append({
                    "name": child.name,
                    "qualified_name": qual,
                    "line": child.lineno,
                    "kind": (
                        "method" if class_stack
                        else ("async_function" if isinstance(child, ast.AsyncFunctionDef) else "function")
                    ),
                    "is_method": bool(class_stack),
                })
                # Don't recurse into nested defs — closures rarely matter for
                # dead-code audits, and they complicate the "unreferenced"
                # check (their name is only visible in an enclosing scope).
            else:
                walk(child, class_stack)

    walk(tree, [])
    return out


def _is_dynamic_dispatch_decorator(dec: ast.expr) -> bool:
    """Return True if the decorator marks the fn as dispatched-by-framework.

    Covers: @receiver(...), @register.filter, @register.tag,
    @register.simple_tag, @shared_task, @periodic_task, @task,
    @app.task, @celery.task, @admin.register, @admin.action.
    """
    # Strip Call wrapper: @receiver(sig) → look at .func
    expr = dec.func if isinstance(dec, ast.Call) else dec
    # Bare @name (e.g. @receiver — already imported)
    if isinstance(expr, ast.Name):
        return expr.id in {
            "receiver", "shared_task", "task", "periodic_task",
        }
    # Attribute @obj.name (e.g. @register.filter, @admin.register)
    if isinstance(expr, ast.Attribute):
        return expr.attr in {
            "filter", "tag", "simple_tag", "inclusion_tag", "register",
            "task", "action", "display",
        }
    return False


def _external_reference_files(
    name: str, defining_file: str, project_root: Path
) -> list[str] | None:
    """Return list of files (excluding defining file) that reference `name`.

    Returns None on subprocess error — including a non-legit exit code
    from ``git grep`` (e.g. "not a git repository", bad path) — so the
    caller can skip the candidate rather than risk recommending deletion
    on incomplete data. ``git grep`` returns 0 on match, 1 on no-match,
    anything else is a real error.
    """
    try:
        result = subprocess.run(
            [
                "git", "grep", "-l", "-w", name, "--",
                f":(exclude){defining_file}",
            ],
            capture_output=True, text=True, timeout=15,
            cwd=str(project_root),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode not in (0, 1):
        # Surface the error once per candidate; caller treats None as "skip".
        stderr = (result.stderr or "").strip().splitlines()[:1]
        hint = stderr[0] if stderr else f"exit {result.returncode}"
        print(
            f"[detect_unreferenced] git grep error for {name!r}: {hint}",
            file=sys.stderr,
        )
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_url_module(filepath: str) -> bool:
    """A URL-routing module is a wiring file, not a "real" caller.

    Covers `urls.py`, anything ending in `_urls.py`, and the conventional
    `core/api_urls.py` sibling. A view class referenced only in a URL
    module is an orphan-endpoint candidate, not a false positive.
    """
    return (
        filepath == "urls.py"
        or filepath.endswith("/urls.py")
        or filepath.endswith("_urls.py")
    )


def _has_same_file_caller(
    name: str, defining_file: str, def_line: int, project_root: Path
) -> bool:
    """Return True if `name` appears in its defining file on a line
    other than the `def`/`class` line itself."""
    try:
        result = subprocess.run(
            ["git", "grep", "-n", "-w", name, "--", defining_file],
            capture_output=True, text=True, timeout=10,
            cwd=str(project_root),
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    for line in result.stdout.splitlines():
        # format: file:lineno:content
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        try:
            lineno = int(parts[1])
        except ValueError:
            continue
        content = parts[2]
        if lineno == def_line:
            continue
        # Definition-only lines (e.g., a `def name(` that wraps across lines
        # and gets re-matched) should not count.
        if f"def {name}" in content or f"class {name}" in content:
            continue
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", required=True, type=Path,
                   help="Directory to scan for definitions (e.g. core/)")
    p.add_argument("--project-root", required=True, type=Path,
                   help="Project root for `git grep` cwd")
    p.add_argument("--output", required=True, type=Path,
                   help="Output JSONL file")
    p.add_argument("--skip-file-glob", action="append", default=[],
                   help="Extra file globs to skip (repeatable)")
    args = p.parse_args(argv)

    if not args.target.exists():
        print(f"[detect_unreferenced] ERROR: {args.target} not found",
              file=sys.stderr)
        return 2

    skip_globs = _DEFAULT_SKIP_FILE_GLOBS + tuple(args.skip_file_glob)
    project_root = args.project_root.resolve()

    files = _walk_python_files(args.target, skip_globs)
    print(f"[detect_unreferenced] scanning {len(files)} python files",
          file=sys.stderr)

    candidates: list[dict[str, object]] = []
    seen = 0
    for filepath in files:
        try:
            rel = str(filepath.relative_to(project_root))
        except ValueError:
            rel = str(filepath)
        for d in _extract_defs(filepath):
            seen += 1
            name = d["name"]
            ext_files = _external_reference_files(name, rel, project_root)
            if ext_files is None:
                continue  # subprocess error — skip rather than risk false delete
            real_refs = [f for f in ext_files if not _is_url_module(f)]
            if real_refs:
                continue  # legitimate cross-file callers
            if _has_same_file_caller(name, rel, int(d["line"]), project_root):
                continue
            url_refs = [f for f in ext_files if _is_url_module(f)]
            candidates.append({
                "type": "unreferenced_def",
                "file": rel,
                "line": d["line"],
                "name": name,
                "qualified_name": d["qualified_name"],
                "kind": d["kind"],
                "url_wired_hint": bool(url_refs),
                "url_wire_files": url_refs,
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for c in candidates:
            fh.write(json.dumps(c) + "\n")
    print(
        f"[detect_unreferenced] wrote {args.output} "
        f"({len(candidates)} candidates out of {seen} defs)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
