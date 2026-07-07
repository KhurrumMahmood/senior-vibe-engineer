#!/usr/bin/env python3
"""Locate `except Exception` / bare `except:` blocks that swallow errors.

AST-walks the target directory. For each `ExceptHandler`, flag when:
  - the handled type is `Exception`, `BaseException`, or bare
  - the handler body is a single `pass`, `return None`, `return`, or
    `continue`
  - (looser) the handler body is a logger call followed by `return None`

These are Flavor-3 dormant candidates: code that runs, throws, and
never surfaces the failure. The scout is responsible for reading the
protected block to decide whether the swallow is benign (log cleanup)
or hides real broken behavior.

Output (one JSON record per line at `--output`):
{
  "type": "silent_catch",
  "file": "core/services/foo.py",
  "line": 87,
  "handler": "except Exception | bare_except",
  "body_shape": "pass | return_none | continue | log_and_return",
  "enclosing_function": "FooService.lookup",   # or "<module>"
  "protected_lines": [67, 86]                  # inclusive range of try body
}

No git-grep or verification here — the scout applies Rule R3 (read 20
lines above the except, look for model-field / URL / ImportError /
DoesNotExist smells).
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
from pathlib import Path

# Route Python parsing through the shared per-language adapter registry
# (ADR 0032). The silent-catch analysis is Python-specific (ExceptHandler
# shapes, logger-call recognition), so this stays a Python-only consumer:
# ask the registry for the file's adapter and only proceed when it exposes
# the raw `ast.Module` (CAP_PYTHON_AST), keeping the existing AST walk.
# Wire the repo `scripts/` dir onto sys.path so the package imports when
# this skill script runs standalone.
PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _lib.lang_adapter import CAP_PYTHON_AST, get_adapter  # noqa: E402


_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
})

_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
)


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


def _handler_label(handler: ast.ExceptHandler) -> str | None:
    """Return "except Exception", "bare_except", or None for others."""
    if handler.type is None:
        return "bare_except"
    if isinstance(handler.type, ast.Name):
        if handler.type.id in {"Exception", "BaseException"}:
            return f"except {handler.type.id}"
    if isinstance(handler.type, ast.Tuple):
        # Tuple of types — treat as broad only if it contains Exception.
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name) and elt.id in {"Exception", "BaseException"}:
                return f"except (..., {elt.id}, ...)"
    return None


def _body_shape(body: list[ast.stmt]) -> str | None:
    """Classify the handler body. Returns None for "does real work"."""
    if not body:
        return None
    # Single-statement swallow
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            return "pass"
        if isinstance(stmt, ast.Continue):
            return "continue"
        if isinstance(stmt, ast.Return):
            if stmt.value is None:
                return "return"
            if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                return "return_none"
    # Log-then-return shape: 1-2 logger calls followed by Return(None | empty)
    if len(body) <= 3:
        last = body[-1]
        if isinstance(last, ast.Return):
            returns_nullish = (
                last.value is None
                or (
                    isinstance(last.value, ast.Constant)
                    and last.value.value is None
                )
            )
            if returns_nullish and all(
                _is_logger_call(s) for s in body[:-1]
            ):
                return "log_and_return"
    return None


def _is_logger_call(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Expr):
        return False
    call = stmt.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr in {
            "debug", "info", "warning", "error", "exception", "critical",
        }
    return False


def _scan_file(filepath: Path, rel: str) -> list[dict[str, object]]:
    # Route through the shared adapter registry; this analysis needs the
    # raw Python AST, so skip any file whose adapter can't supply it
    # (non-Python suffix, or no adapter) rather than crash.
    adapter = get_adapter(filepath)
    if adapter is None or CAP_PYTHON_AST not in adapter.capabilities:
        return []
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    tree = adapter.parse(source)
    if tree is None:
        return []

    out: list[dict[str, object]] = []

    def visit(node: ast.AST, func_stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                new_stack = func_stack + [child.name]
                visit(child, new_stack)
                continue
            if isinstance(child, ast.Try):
                # Compute protected-block line span
                try_start = child.body[0].lineno if child.body else child.lineno
                try_end = (
                    getattr(child.body[-1], "end_lineno", child.body[-1].lineno)
                    if child.body else child.lineno
                )
                for handler in child.handlers:
                    label = _handler_label(handler)
                    if not label:
                        continue
                    shape = _body_shape(handler.body)
                    if not shape:
                        continue
                    out.append({
                        "type": "silent_catch",
                        "file": rel,
                        "line": handler.lineno,
                        "handler": label,
                        "body_shape": shape,
                        "enclosing_function": (
                            ".".join(func_stack) if func_stack else "<module>"
                        ),
                        "protected_lines": [try_start, try_end],
                    })
                visit(child, func_stack)
            else:
                visit(child, func_stack)

    visit(tree, [])
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", required=True, type=Path,
                   help="Directory to scan")
    p.add_argument("--project-root", required=True, type=Path,
                   help="Project root (used for relative paths in output)")
    p.add_argument("--output", required=True, type=Path,
                   help="Output JSONL file")
    p.add_argument("--skip-file-glob", action="append", default=[],
                   help="Extra file globs to skip (repeatable)")
    args = p.parse_args(argv)

    if not args.target.exists():
        print(f"[detect_silent_catches] ERROR: {args.target} not found",
              file=sys.stderr)
        return 2

    skip_globs = _DEFAULT_SKIP_FILE_GLOBS + tuple(args.skip_file_glob)
    project_root = args.project_root.resolve()

    files = _walk_python_files(args.target, skip_globs)
    records: list[dict[str, object]] = []
    for filepath in files:
        try:
            rel = str(filepath.relative_to(project_root))
        except ValueError:
            rel = str(filepath)
        records.extend(_scan_file(filepath, rel))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    print(
        f"[detect_silent_catches] wrote {args.output} "
        f"({len(records)} catches across {len(files)} files)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
