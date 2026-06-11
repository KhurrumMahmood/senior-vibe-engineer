#!/usr/bin/env python3
"""Scan the given source directories for:

  (A) Bare-name collisions with divergent signatures — the same class
      of issue that produced the `_call_llm` shadow cluster.  A name
      that lands on ≥2 defs whose param sets don't match is a shadow
      in disguise: readers see the same name everywhere but get
      different contracts.

  (B) Generic verb names on non-trivial functions.  Names like
      `process`, `handle`, `run`, `do_thing` don't describe the
      operation — readers have to open the body to learn what it does.

Usage: python3 scripts/name_audit.py <dir> [<dir> ...] [--top N]

Output groups:

  * shadows     — name collisions with divergent param lists
  * dupes       — name collisions with matching signatures (maybe
                  genuine duplicates, maybe Django overrides)
  * generics    — non-trivial functions with mushy verb names

Reports file:line, enclosing class (if any), bare param list.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from collections import defaultdict


ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_NAME_PREFIXES = ("tests_", "test_")
SKIP_DIR_NAMES = {"migrations", "__pycache__"}

# Names we do NOT want to flag as shadows / dupes — they are:
# - dunders (universal)
# - Django model/form/view framework hooks (every subclass overrides)
# - common test-setup (though we skip test files anyway)
FRAMEWORK_NAMES = {
    "save", "delete", "clean", "clean_fields", "full_clean",
    "get_absolute_url", "get_queryset", "get_context_data",
    "form_valid", "form_invalid", "get", "post", "put", "patch",
    "dispatch", "ready", "Meta", "__init_subclass__",
    "setUp", "tearDown", "setUpClass", "tearDownClass",
    "natural_key",
}

GENERIC_VERBS = {
    "process", "handle", "run", "do", "execute", "perform",
    "check", "make", "helper", "do_thing", "go", "step",
    "_process", "_handle", "_run", "_do", "_execute", "_perform",
    "_check", "_make",
}

# Bodies smaller than this aren't worth flagging — trivial getters /
# one-line delegates won't benefit from a better name.
MIN_GENERIC_BODY_LINES = 6


def iter_py_files(target: pathlib.Path):
    for path in target.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if any(path.name.startswith(p) for p in SKIP_NAME_PREFIXES):
            continue
        yield path


def param_sig(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    a = fn.args
    parts = []
    parts.extend(arg.arg for arg in a.posonlyargs)
    parts.extend(arg.arg for arg in a.args)
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    parts.extend(arg.arg for arg in a.kwonlyargs)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return tuple(parts)


def body_lines(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    if fn.end_lineno is None:
        return 0
    # Exclude the def line itself.
    return max(0, fn.end_lineno - fn.lineno)


def is_property(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        # @property or @foo.setter / @foo.deleter
        if isinstance(dec, ast.Name) and dec.id == "property":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr in ("setter", "deleter", "getter"):
            return True
    return False


def _display(path: pathlib.Path) -> str:
    """Repo-relative path for reporting; falls back to the absolute path."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def collect(targets: list[pathlib.Path]):
    by_name: dict[str, list[dict]] = defaultdict(list)
    for target in targets:
        if not target.exists():
            continue
        for path in iter_py_files(target):
            try:
                tree = ast.parse(path.read_text(), filename=str(path))
            except SyntaxError as e:
                print(f"# parse fail: {path}: {e}", file=sys.stderr)
                continue
            # Top-level defs
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    by_name[node.name].append({
                        "path": _display(path),
                        "lineno": node.lineno,
                        "class": None,
                        "params": param_sig(node),
                        "body_lines": body_lines(node),
                        "is_property": is_property(node),
                        "is_staticmethod": any(
                            isinstance(d, ast.Name) and d.id == "staticmethod"
                            for d in node.decorator_list
                        ),
                    })
                elif isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            by_name[child.name].append({
                                "path": _display(path),
                                "lineno": child.lineno,
                                "class": node.name,
                                "params": param_sig(child),
                                "body_lines": body_lines(child),
                                "is_property": is_property(child),
                                "is_staticmethod": any(
                                    isinstance(d, ast.Name) and d.id == "staticmethod"
                                    for d in child.decorator_list
                                ),
                            })
    return by_name


def classify(by_name: dict[str, list[dict]]):
    shadows = []   # divergent param sets
    dupes = []     # same param set, multiple files
    generics = []  # mushy verb names

    for name, defs in by_name.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        if name in FRAMEWORK_NAMES:
            continue

        # Generic verb check — per definition
        if name in GENERIC_VERBS:
            for d in defs:
                if d["body_lines"] >= MIN_GENERIC_BODY_LINES and not d["is_property"]:
                    generics.append((name, d))

        if len(defs) < 2:
            continue

        # Drop properties from dupe/shadow analysis — overloading fine
        real = [d for d in defs if not d["is_property"]]
        if len(real) < 2:
            continue

        # Drop defs within the same file — those are usually valid
        # (e.g. dispatcher variants, nested classes). Shadow pattern
        # we care about is cross-file.
        by_path = defaultdict(list)
        for d in real:
            by_path[d["path"]].append(d)
        if len(by_path) < 2:
            continue

        # Compare param sigs, ignoring first arg if it's `self`/`cls`
        def canon(d):
            p = d["params"]
            if p and p[0] in ("self", "cls") and not d["is_staticmethod"]:
                p = p[1:]
            return p

        sigs = {canon(d) for d in real}
        if len(sigs) == 1:
            dupes.append((name, real))
        else:
            shadows.append((name, real))

    return shadows, dupes, generics


def fmt_def(d: dict) -> str:
    where = f"{d['path']}:{d['lineno']}"
    cls = f"{d['class']}." if d["class"] else ""
    params = ", ".join(d["params"]) or "—"
    return f"  {where}  {cls}(params: {params})  [body {d['body_lines']}L]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+", type=pathlib.Path,
                    help="Source directories to scan for name collisions.")
    ap.add_argument("--top", type=int, default=20,
                    help="Max items per bucket (default 20)")
    args = ap.parse_args()

    by_name = collect([t.resolve() for t in args.targets])
    shadows, dupes, generics = classify(by_name)

    # Rank shadows by (member count desc, total body lines desc) — the
    # biggest, most-duplicated names surface first.
    shadows.sort(key=lambda kv: (-len(kv[1]), -sum(d["body_lines"] for d in kv[1])))
    dupes.sort(key=lambda kv: (-len(kv[1]), -sum(d["body_lines"] for d in kv[1])))
    generics.sort(key=lambda g: -g[1]["body_lines"])

    print("=" * 72)
    print(f"SHADOWS — same bare name, divergent param lists ({len(shadows)} names)")
    print("=" * 72)
    for name, defs in shadows[: args.top]:
        print(f"\n• {name}   ({len(defs)} defs)")
        for d in defs:
            print(fmt_def(d))

    print()
    print("=" * 72)
    print(f"DUPES — same bare name, matching params, multiple files ({len(dupes)} names)")
    print("=" * 72)
    for name, defs in dupes[: args.top]:
        print(f"\n• {name}   ({len(defs)} defs)")
        for d in defs:
            print(fmt_def(d))

    print()
    print("=" * 72)
    print(f"GENERICS — mushy verb names on non-trivial bodies ({len(generics)} defs)")
    print("=" * 72)
    for name, d in generics[: args.top]:
        print(f"\n• {name}")
        print(fmt_def(d))


if __name__ == "__main__":
    main()
