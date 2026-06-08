#!/usr/bin/env python3
"""find-incomplete-sweep — placeholder-residue band (roadmap band, now built).

The kwarg-omission band catches a sweep that missed a sibling *call site*. This
band catches the OTHER incomplete-execution residue named in the skill brief:
a CONCRETE function/method that was scaffolded but never filled in — a body that
is only `raise NotImplementedError`, only `pass` / `...`, only a docstring, or a
`return None  # TODO`-style stub — left behind while the surrounding code moved
on and now CALLS it as if it were done.

Why this is NOT /find-dormant or /find-orphaned-ideas --todo
------------------------------------------------------------
* /find-dormant finds *unreferenced* code (the unwired half). A stub that nobody
  calls is dormant, not a forgotten sweep — this band requires the stub to be
  REFERENCED (called / overriding an implemented sibling), so it is the
  over-referenced-at-empty-shape half, the mirror image dormant cannot see.
* /find-orphaned-ideas --todo surfaces *raw TODO markers* anywhere. This band
  fires only on a placeholder BODY in concrete code, gated by recency +
  reference-asymmetry, so a `# TODO: tune this` inside a working function is not
  a hit here.

Precision gates (both required, or it just spews noise)
------------------------------------------------------
1. CONCRETE only. An abstract method (`@abstractmethod`, a body inside an ABC /
   `Protocol`, a `...`-only stub on a Protocol/overloaded signature) is a
   contract, not residue — excluded.
2. RECENT. A stub whose defining line has been stable for longer than
   `--max-age-days` (default 120) is accepted debt, not abandonment — excluded.
   (Uses `git blame` on the stub's signature line, same plumbing as scan.py.)
3. REFERENCE-ASYMMETRY. The stub must be either
   (a) referenced elsewhere by name (called/imported as if complete), OR
   (b) a concrete method that OVERRIDES / sits beside sibling methods of the same
       name that ARE implemented (newly-added empty method among filled siblings).
   A stub that is neither referenced nor a sibling-of-implemented is just dead
   scaffolding — route to /find-dormant, not here.

Detection only. Never edits code. Advisory SUSPECT output.

Usage:
    .venv/bin/python .claude/skills/find-incomplete-sweep/scripts/placeholder.py \
        --paths scripts [--max-age-days 120] [--out reports/find-incomplete-sweep/scan-<TS>]
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
import time
from dataclasses import dataclass

# Reuse the file iterator and blame plumbing from the kwarg-omission band so the
# scanned-file definition and recency signal stay identical across bands.
_SKILL_SCRIPTS = pathlib.Path(__file__).resolve().parent
if str(_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL_SCRIPTS))
import scan as _scan  # sibling module loaded by path (sys.path adjusted above)

# Base classes whose presence marks a body as a CONTRACT, not residue.
ABSTRACT_BASES = {"ABC", "Protocol", "ABCMeta"}
# Dunder / framework hooks that are legitimately empty by convention.
ALLOWED_EMPTY = {"__init_subclass__", "__set_name__"}


@dataclass
class Placeholder:
    symbol: str            # dotted: Class.method or bare function
    name: str              # bare final name (for reference search)
    kind: str              # not_implemented | empty_body | todo_stub
    file: str
    line: int              # signature line (def ...)
    in_test: bool = False
    # populated by the gates:
    age_days: float | None = None
    recent: bool = False
    ref_count: int = 0          # references by name outside its own def
    implemented_siblings: int = 0  # same-name methods elsewhere with a real body
    reference_asymmetry: str = ""
    gated_in: bool = False
    note: str = ""


def _is_docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _body_after_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if body and _is_docstring(body[0]):
        return body[1:]
    return body


def _classify_body(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Return a placeholder kind for a stub body, or None if it is real code."""
    rest = _body_after_docstring(fn.body)
    if not rest:
        # body was docstring-only (or empty, which is a SyntaxError so unreachable)
        return "empty_body"
    # only `pass`
    if all(isinstance(s, ast.Pass) for s in rest):
        return "empty_body"
    # only `...` (ellipsis expression)
    if all(
        isinstance(s, ast.Expr)
        and isinstance(s.value, ast.Constant)
        and s.value.value is Ellipsis
        for s in rest
    ):
        return "empty_body"
    # `raise NotImplementedError` (bare or called) as the only statement
    if len(rest) == 1 and isinstance(rest[0], ast.Raise):
        exc = rest[0].exc
        exc_name = None
        if isinstance(exc, ast.Call):
            exc = exc.func
        if isinstance(exc, ast.Name):
            exc_name = exc.id
        elif isinstance(exc, ast.Attribute):
            exc_name = exc.attr
        if exc_name == "NotImplementedError":
            return "not_implemented"
    # `return None  # TODO` — a return of None/nothing whose line carries a TODO/FIXME
    if len(rest) == 1 and isinstance(rest[0], ast.Return):
        val = rest[0].value
        if val is None or (isinstance(val, ast.Constant) and val.value is None):
            return "todo_stub"  # caller confirms the TODO marker on the line
    return None


def _has_abstract_decorator(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
        if name in {"abstractmethod", "abstractproperty", "overload"}:
            return True
    return False


def _class_is_abstract(cls: ast.ClassDef) -> bool:
    for base in cls.bases:
        name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)
        if name in ABSTRACT_BASES:
            return True
    # metaclass=ABCMeta
    for kw in cls.keywords:
        if kw.arg == "metaclass":
            v = kw.value
            name = v.attr if isinstance(v, ast.Attribute) else getattr(v, "id", None)
            if name in ABSTRACT_BASES:
                return True
    return False


def collect_placeholders(paths: list[str]) -> tuple[list[Placeholder], int]:
    """Walk concrete functions/methods and collect placeholder-bodied ones.

    Skips ABC/Protocol bodies, @abstractmethod/@overload, and allow-listed empty
    dunders. Tests are included but tagged `in_test` (empty test bodies are a
    distinct residue the brief names explicitly).
    """
    out: list[Placeholder] = []
    scanned = 0
    for f in _iter_files_including_tests(paths):
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError):
            continue
        scanned += 1
        src_lines = src.splitlines()
        in_test = f.name.startswith("test_") or "/tests/" in str(f)
        # Map each function node to its enclosing class (if any) for sibling logic.
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            cls_abstract = _class_is_abstract(node)
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _maybe_add(out, stmt, node, cls_abstract, f, src_lines, in_test)
        # module-level functions (no class)
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _maybe_add(out, stmt, None, False, f, src_lines, in_test)
    return out, scanned


def _maybe_add(out, fn, cls, cls_abstract, f, src_lines, in_test):
    if _has_abstract_decorator(fn) or cls_abstract:
        return
    if fn.name in ALLOWED_EMPTY:
        return
    kind = _classify_body(fn)
    if kind is None:
        return
    if kind == "todo_stub":
        # Confirm a TODO/FIXME marker on the return line; else it is a real
        # `return None` and not residue.
        ln = fn.body[-1].lineno
        line_text = src_lines[ln - 1] if 0 <= ln - 1 < len(src_lines) else ""
        if not any(m in line_text.upper() for m in ("TODO", "FIXME", "XXX")):
            return
    symbol = f"{cls.name}.{fn.name}" if cls is not None else fn.name
    out.append(Placeholder(
        symbol=symbol, name=fn.name, kind=kind,
        file=str(f), line=fn.lineno, in_test=in_test,
    ))


def _iter_files_including_tests(paths):
    """Like scan.iter_py_files but KEEPS tests/ (empty test bodies are in scope
    for this band). Still skips migrations / __pycache__ / .venv."""
    for p in paths:
        root = pathlib.Path(p)
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        for fp in root.rglob("*.py"):
            sp = str(fp)
            if any(seg in sp for seg in ("/migrations/", "/__pycache__/", "/.venv/")):
                continue
            yield fp


def _count_references(name: str, paths: list[str], own_file: str) -> int:
    """Count by-name references to a symbol across the scanned paths, excluding
    its own `def` lines. Uses `git grep`-free ripgrep-style scan via Python so it
    runs without extra deps; word-boundary match on the bare name.

    A method/function referenced as `obj.name(`, `name(`, `self.name`, or
    imported `from x import name` all count. We do not resolve types — an
    over-count here only makes the asymmetry gate MORE permissive, and the
    sibling-implemented gate is the independent corroborator.
    """
    pat = re.compile(rf"(?<![\w.])\.?{re.escape(name)}\b")
    count = 0
    for fp in _iter_files_including_tests(paths):
        try:
            text = fp.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            stripped = line.lstrip()
            # skip the definition line itself
            if stripped.startswith(("def ", "async def ")) and f"{name}(" in line and str(fp) == own_file:
                continue
            for m in pat.finditer(line):
                # discount the bare `def name(` definition token everywhere
                if line[: m.start()].lstrip().startswith(("def ", "async def ")):
                    continue
                count += 1
    return count


def _implemented_siblings(name: str, paths: list[str], own_symbol: str) -> int:
    """Count methods/functions of the SAME name, elsewhere, that have a REAL
    (non-placeholder) body. A newly-added empty method among filled siblings is
    the canonical 'sweep added a sibling but left it blank' residue."""
    count = 0
    for fp in _iter_files_including_tests(paths):
        try:
            tree = ast.parse(fp.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                if _classify_body(node) is None and not _has_abstract_decorator(node):
                    count += 1
    return count


def apply_gates(items: list[Placeholder], paths: list[str], max_age_days: float):
    now = time.time()
    for it in items:
        ts = _scan.line_commit_time(it.file, it.line)
        if ts is None:
            it.recent = False
            it.note = "no blame data — cannot establish recency"
            continue
        it.age_days = round((now - ts) / 86400.0, 1)
        it.recent = it.age_days <= max_age_days
        it.ref_count = _count_references(it.name, paths, it.file)
        it.implemented_siblings = _implemented_siblings(it.name, paths, it.symbol)
        referenced = it.ref_count > 0
        sibling_filled = it.implemented_siblings > 0
        if referenced and sibling_filled:
            it.reference_asymmetry = "referenced AND sibling(s) of same name implemented"
        elif referenced:
            it.reference_asymmetry = f"referenced by name {it.ref_count}x outside its def"
        elif sibling_filled:
            it.reference_asymmetry = (
                f"{it.implemented_siblings} implemented sibling(s) of same name "
                "(empty method among filled)"
            )
        else:
            it.reference_asymmetry = "neither referenced nor sibling-implemented"
        it.gated_in = it.recent and (referenced or sibling_filled)
        if not it.recent:
            it.note = f"stub stable {it.age_days}d (> {max_age_days}d) — accepted debt, not abandonment"
        elif not (referenced or sibling_filled):
            it.note = "no reference-asymmetry — route to /find-dormant (unwired), not here"
        else:
            it.note = f"recent ({it.age_days}d) + {it.reference_asymmetry}"


def render(items, scanned, paths, max_age_days) -> str:
    gated = [i for i in items if i.gated_in]
    ungated = [i for i in items if not i.gated_in]
    gated.sort(key=lambda i: (i.kind, i.file, i.line))

    L = ["# find-incomplete-sweep — findings (band: placeholder-residue)\n"]
    L.append(f"- paths: `{', '.join(paths)}`")
    L.append(f"- files scanned: {scanned}")
    L.append(f"- max-age-days (recency gate): {max_age_days}")
    L.append(f"- raw placeholder bodies: {len(items)}")
    L.append(f"- **gated IN (recent + reference-asymmetry): {len(gated)}**")
    L.append(f"- gated out (stale / no asymmetry / no blame): {len(ungated)}\n")

    def block(i: Placeholder) -> str:
        return "\n".join([
            f"### `{i.symbol}` — {i.kind}" + ("  (test)" if i.in_test else ""),
            f"- location: `{_scan.rel(i.file)}:{i.line}`",
            f"- age: {i.age_days}d  | refs: {i.ref_count}  | "
            f"implemented siblings: {i.implemented_siblings}",
            f"- asymmetry: {i.reference_asymmetry}",
            f"- note: {i.note}",
        ])

    L.append("## Gated IN — recent referenced stubs (likely forgotten work)\n")
    L.append("\n\n".join(block(i) for i in gated) if gated else "_none_")
    L.append("\n\n## Gated OUT — stale / unreferenced / no-blame (review separately)\n")
    L.append("\n\n".join(block(i) for i in ungated[:25]) if ungated else "_none_")
    if len(ungated) > 25:
        L.append(f"\n_… {len(ungated) - 25} more gated-out placeholders omitted._")
    return "\n".join(L) + "\n"


def run(paths: list[str], max_age_days: float):
    items, scanned = collect_placeholders(paths)
    apply_gates(items, paths, max_age_days)
    return items, scanned


def manifest(items, scanned, max_age_days) -> dict:
    return {
        "band": "placeholder-residue",
        "files_scanned": scanned,
        "max_age_days": max_age_days,
        "raw_candidates": len(items),
        "gated_in": sum(1 for i in items if i.gated_in),
        "findings": [
            {"symbol": i.symbol, "kind": i.kind,
             "location": f"{_scan.rel(i.file)}:{i.line}",
             "age_days": i.age_days, "ref_count": i.ref_count,
             "implemented_siblings": i.implemented_siblings,
             "reference_asymmetry": i.reference_asymmetry,
             "gated_in": i.gated_in, "note": i.note}
            for i in items
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paths", nargs="+", required=True,
                    help="one or more source roots / files to scan (e.g. scripts). "
                         "Required — there is no default scan root.")
    ap.add_argument("--max-age-days", type=float, default=120.0,
                    help="recency gate: stubs older than this are accepted debt")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    items, scanned = run(args.paths, args.max_age_days)
    report = render(items, scanned, args.paths, args.max_age_days)
    if args.out:
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "placeholder_findings.md").write_text(report)
        (out / "placeholder_manifest.json").write_text(
            json.dumps(manifest(items, scanned, args.max_age_days), indent=2))
        print(f"wrote {out}/placeholder_findings.md  "
              f"({sum(1 for i in items if i.gated_in)} gated-in / {len(items)} raw)")
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
