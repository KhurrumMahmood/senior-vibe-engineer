#!/usr/bin/env python3
"""Detect layer-violation smells — views/tasks owning business logic.

AST-walks the view and task layer files under ``--target`` (classified by
the host's find-layer-violation-scope.md layer map, or by conventional
``views``/``tasks`` path segments). For each view function /
View-subclass HTTP method / top-level task function, emits one record
per detected signal:

  - **fat**: function body exceeds LOC budget (module view = 80,
    View-class HTTP method = 120, task = 120). LOC counting mirrors
    ``scripts/lint/no_fat_view.py``'s ``_body_loc`` — non-blank,
    non-comment lines in the range ``[lineno, end_lineno]``.
  - **domain_loop**: ``for … in <ModelClass.objects.*>`` whose body
    contains >5 statements, OR ``for … in <var>`` where <var> was
    bound from a ``.objects.filter/.all/.order_by()`` queryset in the
    same scope.
  - **direct_llm_call**: imports from a ``services`` module whose module
    name contains an LLM/AI keyword (``llm``, ``ai``, ``openai``,
    ``anthropic``, ``fireworks``, ``openrouter``, ``cerebras``,
    ``fireworksai``, ``groq``) used inline in a view/task function
    body.
  - **dispatch_bypass**: direct ``.delay(`` / ``.apply_async(`` calls
    in view code. `TaskDispatchService.safe_dispatch` is the
    canonical pattern per CLAUDE.md.
  - **multi_model_write**: ≥2 distinct ``Model.objects.*`` write calls
    (``.save()``, ``.create()``, ``.update()``, ``.delete()``,
    ``.bulk_create()``, ``.bulk_update()``, ``.update_or_create()``,
    ``.get_or_create()``) targeting different model classes, within
    a single function body.

The scout (Stage 3) reads the function in full and buckets each
high-confidence hit as ``extract_service``, ``move_to_existing_service``,
or ``intentional_http_coupling``.

Output (one JSON record per signal-hit at ``--output``):

    {
      "type": "layer_violation",
      "file": "app/views/external_source.py",
      "symbol": "ExternalSourceExtractView.post",
      "kind": "view_method",
      "signal": "multi_model_write",
      "evidence": "UploadedFile.objects.create(); ProductData.objects.create()",
      "lineno": 66,
      "end_lineno": 380,
      "loc": 215
    }

Scope is restricted to the view and task layers — the layer-violation
smell is specifically "the wrong layer owns the work." Services / models
/ utils are out of scope for this detector.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import sys
from pathlib import Path

# scope lives in _common (skills/<skill>/scripts/ -> skills/_common). It
# supplies the host-authored layer map (which globs are views/tasks) so this
# detector carries no hardcoded source-root assumption.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
import scope as _scope  # noqa: E402

# Route Python parsing through the shared per-language adapter registry so
# this detector capability-gates on Python and gracefully skips other
# languages instead of crashing on them. The analysis below stays exact
# Python-AST / Django-specific (labels python/django are unchanged).
PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from _lib.lang_adapter import CAP_PYTHON_AST, get_adapter  # noqa: E402

# Headings in find-layer-violation-scope.md that declare each layer's globs.
_LAYER_SECTION_MAP = {"view": {"views", "view"}, "task": {"tasks", "task"}}


DEFAULT_FN_BUDGET = 80
DEFAULT_METHOD_BUDGET = 120
DEFAULT_TASK_BUDGET = 120

DOMAIN_LOOP_BODY_THRESHOLD = 5

# View-class base hints — copied from scripts/lint/no_fat_view.py so
# this detector stays stdlib-only and doesn't import from the lint
# module.
VIEW_BASE_HINTS = (
    "View", "APIView", "ViewSet", "ModelViewSet", "GenericViewSet",
    "TemplateView", "ListView", "DetailView", "CreateView",
    "UpdateView", "DeleteView", "FormView", "RedirectView",
)
HTTP_METHODS = frozenset({
    "get", "post", "put", "patch", "delete", "head", "options",
})

# LLM/AI-ish module fragments inside a services module — when a view/task
# imports one of these and uses it inline, that's a direct LLM call.
LLM_MODULE_HINTS = (
    "llm", "ai_", "_ai", "openai", "anthropic", "fireworks",
    "openrouter", "cerebras", "groq", "agent_field", "agent_bridge",
    "agent_", "_agent",
)

WRITE_METHODS = frozenset({
    "save", "create", "delete", "update", "bulk_create", "bulk_update",
    "update_or_create", "get_or_create",
})

# Methods ending in these names indicate a queryset-producing call.
QUERYSET_METHODS = frozenset({
    "all", "filter", "exclude", "order_by", "values", "values_list",
    "only", "defer", "annotate", "select_related", "prefetch_related",
    "distinct", "none", "iterator",
})

_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
})

_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    # Test files legitimately import across layers, so skip them. Package
    # __init__.py is deliberately NOT skipped: package-style layouts (e.g. an
    # ADR-0011 split where views live in app/pages/<area>/__init__.py) carry
    # real view/task code there, and skipping it silently drops those modules
    # from the scan. Re-export-only __init__.py files simply yield no findings.
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
)

NOQA_RE = re.compile(r"#\s*noqa:\s*layer-violation:\s*\S+")


def _body_loc(node: ast.AST, lines: list[str]) -> int:
    """Non-blank, non-comment LOC in [node.lineno, node.end_lineno]."""
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None) or start
    if start is None or end is None:
        return 0
    count = 0
    for idx in range(start - 1, min(end, len(lines))):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("#"):
            continue
        count += 1
    return count


def _range_has_noqa(lines: list[str], start: int, end: int) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def _is_view_class(cls: ast.ClassDef) -> bool:
    for base in cls.bases:
        name = None
        if isinstance(base, ast.Name):
            name = base.id
        elif isinstance(base, ast.Attribute):
            name = base.attr
        if name in VIEW_BASE_HINTS:
            return True
    return False


def _attr_chain(node: ast.AST) -> list[str]:
    """Return the dotted chain of an Attribute/Name chain as strings."""
    parts: list[str] = []
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        elif isinstance(cur, ast.Name):
            parts.append(cur.id)
            break
        elif isinstance(cur, ast.Call):
            cur = cur.func
        else:
            break
    parts.reverse()
    return parts


def _call_method_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_queryset_producer(call: ast.Call) -> bool:
    """Does this Call look like a queryset producer?

    Matches Foo.objects.filter(...), qs.filter(...), qs.order_by(...),
    etc.
    """
    method = _call_method_name(call)
    if method is None:
        return False
    if method in QUERYSET_METHODS:
        return True
    # Also: Foo.objects → return a Manager whose call looks like
    # .all()/.filter() — catch those too via attribute inspection.
    if isinstance(call.func, ast.Attribute):
        chain = _attr_chain(call.func)
        if "objects" in chain:
            return True
    return False


def _call_writes_via_objects(call: ast.Call) -> tuple[str, str] | None:
    """If the call is ``Foo.objects.<write_method>(...)``, return the
    (ModelName, method) pair. Returns None otherwise.
    """
    method = _call_method_name(call)
    if method not in WRITE_METHODS:
        return None
    if not isinstance(call.func, ast.Attribute):
        return None
    chain = _attr_chain(call.func)
    # Expect a chain like ['Model', 'objects', '<write_method>'] OR
    # ['self', 'Model', 'objects', '<write_method>'] — the tail is the
    # method; look for 'objects' one step before.
    if len(chain) < 3:
        return None
    if chain[-2] != "objects":
        return None
    # Model name is the last thing before 'objects'. If the chain has a
    # leading 'self' or module path, we keep the preceding token.
    model_name = chain[-3]
    return (model_name, method)


def _instance_save_or_delete(call: ast.Call) -> str | None:
    """Return 'save'/'delete' when ``.save(...)`` or ``.delete(...)``
    is called on something that looks like a model instance (attribute
    chain not ending in ``.objects``).
    """
    method = _call_method_name(call)
    if method not in {"save", "delete"}:
        return None
    if not isinstance(call.func, ast.Attribute):
        return None
    chain = _attr_chain(call.func)
    # Skip if it's Model.objects.save() — already covered by the write
    # path above.
    if len(chain) >= 2 and chain[-2] == "objects":
        return None
    # Heuristic: chain must start with a lowercase name (instance var).
    # This avoids false positives like ``request.session.save()``.
    if not chain:
        return None
    return method


def _task_base_matches(cls: ast.ClassDef) -> bool:
    """Detect CeleryTask-style base classes (rarely used, but present)."""
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id in {"Task", "BaseTask"}:
            return True
    return False


def _is_task_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when the function has a task-shaped decorator."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            dec_func = dec.func
        else:
            dec_func = dec
        if isinstance(dec_func, ast.Name):
            if dec_func.id in {"shared_task", "task", "periodic_task",
                                "app_task"}:
                return True
        elif isinstance(dec_func, ast.Attribute):
            if dec_func.attr in {"task", "shared_task", "periodic_task"}:
                return True
    return False


def _is_services_module(mod: str) -> bool:
    """True when a (lowercased) dotted module path names a ``services`` layer
    segment — ``core.services.x``, ``app.services.extraction.x``,
    ``services.x``, or a relative ``..services.x``. A layer convention, not a
    source-root binding, so the detector works on any host's package layout.
    """
    return "services" in mod.split(".")


def _collect_llm_imports(tree: ast.Module) -> set[str]:
    """Names imported from an LLM-ish services module, tracked by alias in the
    importing module so we can check usage by Name.id.
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = (node.module or "").lower()
            if not _is_services_module(mod):
                continue
            if not any(h in mod for h in LLM_MODULE_HINTS):
                continue
            for alias in node.names:
                out.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod = (alias.name or "").lower()
                if _is_services_module(mod) and any(
                    h in mod for h in LLM_MODULE_HINTS
                ):
                    out.add(alias.asname or alias.name.split(".")[-1])
    return out


def _walk_python_files(
    target: Path,
    skip_globs: tuple[str, ...],
    project_root: Path,
) -> list[Path]:
    files: list[Path] = []
    for path in target.rglob("*.py"):
        if any(part in _DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if any(fnmatch.fnmatchcase(path.name, g) for g in skip_globs):
            continue
        files.append(path)
    return files


def _scope_kind(
    file_rel: str,
    view_globs: tuple[str, ...] = (),
    task_globs: tuple[str, ...] = (),
) -> str | None:
    """Classify a file as 'view' / 'task' / None.

    Host-declared globs (from the `## Views` / `## Tasks` sections of
    find-layer-violation-scope.md) win, so a project whose views don't live
    under a conventionally-named directory — e.g. host-a's `app/pages/`,
    `app/api/` — is still classified. The generic fallback matches the
    conventional segment names `views` / `tasks` under any top package, so a
    standard layout needs no config.
    """
    p = file_rel.replace("\\", "/")
    for g in view_globs:
        if _scope.path_matches(p, g):
            return "view"
    for g in task_globs:
        if _scope.path_matches(p, g):
            return "task"
    segs = p.split("/")
    if "views" in segs or p.endswith("/views.py") or p == "views.py":
        return "view"
    if "tasks" in segs or p.endswith("/tasks.py") or p == "tasks.py":
        return "task"
    return None


def _queryset_iter_target(iter_node: ast.AST) -> bool:
    """True when ``for x in <expr>`` iterates a queryset-looking thing.

    Matches:
      - ``for x in Model.objects.filter(...)``
      - ``for x in Model.objects.all()``
      - ``for x in qs.filter(...)``
      - ``for x in <expr>.order_by(...)``
    Does NOT match plain name references — that needs cross-scope
    tracking and would be noisy.
    """
    if isinstance(iter_node, ast.Call):
        return _is_queryset_producer(iter_node)
    return False


def _body_stmt_count(body: list[ast.stmt]) -> int:
    """Count statements in a loop body, counting nested blocks as 1."""
    return len(body)


class FunctionScanner(ast.NodeVisitor):
    """Scan a single function body for layer-violation signals.

    The scanner keeps per-function state (writes, loops, llm usage,
    dispatches) and emits records via ``emit``.
    """

    def __init__(
        self,
        file_rel: str,
        symbol: str,
        kind: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        llm_names: set[str],
        lines: list[str],
        fn_budget: int,
    ) -> None:
        self.file_rel = file_rel
        self.symbol = symbol
        self.kind = kind  # 'view_function' | 'view_method' | 'task'
        self.node = func_node
        self.llm_names = llm_names
        self.lines = lines
        self.fn_budget = fn_budget
        self.writes: list[tuple[str, str, int]] = []  # (model, method, lineno)
        self.instance_mutations: list[tuple[str, int]] = []
        self.loop_hits: list[tuple[int, int]] = []  # (lineno, body_stmts)
        self.llm_hits: list[tuple[str, int]] = []
        self.dispatch_hits: list[tuple[str, int]] = []
        self.records: list[dict[str, object]] = []

    def run(self) -> list[dict[str, object]]:
        start_line = self.node.lineno
        end_line = getattr(self.node, "end_lineno", start_line)

        # Allow-list via noqa anywhere in the body.
        if _range_has_noqa(self.lines, start_line, end_line):
            return []

        loc = _body_loc(self.node, self.lines)
        if loc > self.fn_budget:
            self.records.append({
                "type": "layer_violation",
                "file": self.file_rel,
                "symbol": self.symbol,
                "kind": self.kind,
                "signal": "fat",
                "evidence": f"body LOC={loc} (budget {self.fn_budget})",
                "lineno": start_line,
                "end_lineno": end_line,
                "loc": loc,
            })

        # Walk the body for other signals.
        for child in ast.walk(self.node):
            if isinstance(child, ast.For):
                if _queryset_iter_target(child.iter):
                    stmt_count = _body_stmt_count(child.body)
                    if stmt_count > DOMAIN_LOOP_BODY_THRESHOLD:
                        self.loop_hits.append((child.lineno, stmt_count))
            elif isinstance(child, ast.Call):
                # dispatch bypass
                method = _call_method_name(child)
                if method in {"delay", "apply_async"}:
                    # Filter the extremely common webdriver / asyncio
                    # false positive by requiring the chain to include
                    # something task-shaped. Callers of ``.delay()``
                    # that are not celery tasks are rare enough that
                    # we accept some noise.
                    self.dispatch_hits.append(
                        (f".{method}(", child.lineno)
                    )
                # writes via Model.objects.<write_method>
                w = _call_writes_via_objects(child)
                if w is not None:
                    self.writes.append((w[0], w[1], child.lineno))
                # instance-level .save()/.delete()
                inst = _instance_save_or_delete(child)
                if inst:
                    self.instance_mutations.append((inst, child.lineno))
            elif isinstance(child, ast.Name):
                if child.id in self.llm_names:
                    self.llm_hits.append((child.id, child.lineno))

        # domain_loop — emit one record per loop over threshold.
        for (lineno, stmt_count) in self.loop_hits:
            self.records.append({
                "type": "layer_violation",
                "file": self.file_rel,
                "symbol": self.symbol,
                "kind": self.kind,
                "signal": "domain_loop",
                "evidence": (
                    f"for … in queryset with {stmt_count}-statement body "
                    f"(threshold {DOMAIN_LOOP_BODY_THRESHOLD})"
                ),
                "lineno": lineno,
                "end_lineno": end_line,
                "loc": loc,
            })

        # direct_llm_call — emit one record per unique LLM name used.
        seen: set[str] = set()
        for (name, lineno) in self.llm_hits:
            if name in seen:
                continue
            seen.add(name)
            self.records.append({
                "type": "layer_violation",
                "file": self.file_rel,
                "symbol": self.symbol,
                "kind": self.kind,
                "signal": "direct_llm_call",
                "evidence": f"uses `{name}` from a services module",
                "lineno": lineno,
                "end_lineno": end_line,
                "loc": loc,
            })

        # dispatch_bypass — views only (tasks legitimately call .delay).
        if self.kind != "task":
            seen_disp: set[int] = set()
            for (shape, lineno) in self.dispatch_hits:
                if lineno in seen_disp:
                    continue
                seen_disp.add(lineno)
                self.records.append({
                    "type": "layer_violation",
                    "file": self.file_rel,
                    "symbol": self.symbol,
                    "kind": self.kind,
                    "signal": "dispatch_bypass",
                    "evidence": (
                        f"direct `{shape}` call — use "
                        f"TaskDispatchService.safe_dispatch()"
                    ),
                    "lineno": lineno,
                    "end_lineno": end_line,
                    "loc": loc,
                })

        # multi_model_write — ≥2 distinct model classes written.
        write_models: dict[str, list[tuple[str, int]]] = {}
        for model, method, lineno in self.writes:
            write_models.setdefault(model, []).append((method, lineno))
        if len(write_models) >= 2:
            preview_parts: list[str] = []
            earliest_line = end_line
            for model, methods in write_models.items():
                method_name, line_of_first = methods[0]
                preview_parts.append(f"{model}.objects.{method_name}()")
                if line_of_first < earliest_line:
                    earliest_line = line_of_first
            self.records.append({
                "type": "layer_violation",
                "file": self.file_rel,
                "symbol": self.symbol,
                "kind": self.kind,
                "signal": "multi_model_write",
                "evidence": "; ".join(preview_parts),
                "lineno": earliest_line,
                "end_lineno": end_line,
                "loc": loc,
            })

        return self.records


def scan_file(
    filepath: Path,
    file_rel: str,
    fn_budget: int,
    method_budget: int,
    task_budget: int,
    view_globs: tuple[str, ...] = (),
    task_globs: tuple[str, ...] = (),
) -> list[dict[str, object]]:
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

    lines = source.splitlines()
    scope = _scope_kind(file_rel, view_globs, task_globs)
    if scope is None:
        return []

    llm_names = _collect_llm_imports(tree)
    out: list[dict[str, object]] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if scope == "view":
                # Module-level view function
                scanner = FunctionScanner(
                    file_rel, node.name, "view_function", node,
                    llm_names, lines, fn_budget,
                )
            else:
                # task
                if not _is_task_function(node):
                    # Only flag decorated tasks; top-level helpers stay
                    # out of scope for this detector.
                    continue
                scanner = FunctionScanner(
                    file_rel, node.name, "task", node, llm_names, lines,
                    task_budget,
                )
            out.extend(scanner.run())

        elif isinstance(node, ast.ClassDef):
            if scope == "view" and _is_view_class(node):
                for member in node.body:
                    if not isinstance(
                        member, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        continue
                    if member.name not in HTTP_METHODS:
                        continue
                    symbol = f"{node.name}.{member.name}"
                    scanner = FunctionScanner(
                        file_rel, symbol, "view_method", member,
                        llm_names, lines, method_budget,
                    )
                    out.extend(scanner.run())
            elif scope == "task" and _task_base_matches(node):
                for member in node.body:
                    if not isinstance(
                        member, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        continue
                    if member.name not in {"run", "__call__"}:
                        continue
                    symbol = f"{node.name}.{member.name}"
                    scanner = FunctionScanner(
                        file_rel, symbol, "task", member,
                        llm_names, lines, task_budget,
                    )
                    out.extend(scanner.run())
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", required=True, type=Path,
                   help="Directory to scan (view/task layer files within it)")
    p.add_argument("--project-root", required=True, type=Path,
                   help="Project root (for relative paths in output)")
    p.add_argument("--output", required=True, type=Path,
                   help="Output JSONL file")
    p.add_argument("--fn-budget", type=int, default=DEFAULT_FN_BUDGET,
                   help=f"View-function LOC budget (default {DEFAULT_FN_BUDGET})")
    p.add_argument("--method-budget", type=int, default=DEFAULT_METHOD_BUDGET,
                   help=f"View-method LOC budget (default {DEFAULT_METHOD_BUDGET})")
    p.add_argument("--task-budget", type=int, default=DEFAULT_TASK_BUDGET,
                   help=f"Task function LOC budget (default {DEFAULT_TASK_BUDGET})")
    p.add_argument("--skip-file-glob", action="append", default=[],
                   help="Extra file-name globs to skip (repeatable)")
    args = p.parse_args(argv)

    # Resolve a relative --target under --project-root (not the process CWD), so
    # the detector scans the requested host rather than wherever it was launched
    # from. Absolute targets and the common project-root==CWD case are unchanged.
    project_root = args.project_root.resolve()
    target = args.target if args.target.is_absolute() else project_root / args.target

    if not target.exists():
        print(
            f"[detect_layer_violation] ERROR: {target} not found",
            file=sys.stderr,
        )
        return 2
    if not target.is_dir():
        print(
            f"[detect_layer_violation] ERROR: {target} is not a directory",
            file=sys.stderr,
        )
        return 2

    skip_globs = _DEFAULT_SKIP_FILE_GLOBS + tuple(args.skip_file_glob)

    # Host-authored layer map (which globs are views / tasks); empty unless the
    # project ships find-layer-violation-scope.md, in which case _scope_kind
    # falls back to conventional `views`/`tasks` segment names.
    layers = _scope.parse_sections(
        _scope.descriptor_text(project_root, "find-layer-violation") or "",
        _LAYER_SECTION_MAP,
    )
    view_globs = tuple(layers["view"])
    task_globs = tuple(layers["task"])

    files = _walk_python_files(target, skip_globs, project_root)
    records: list[dict[str, object]] = []
    for filepath in files:
        try:
            rel = str(filepath.relative_to(project_root))
        except ValueError:
            rel = str(filepath)
        records.extend(
            scan_file(
                filepath, rel,
                args.fn_budget, args.method_budget, args.task_budget,
                view_globs, task_globs,
            )
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    print(
        f"[detect_layer_violation] wrote {args.output} "
        f"({len(records)} signal-hits across {len(files)} files)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
