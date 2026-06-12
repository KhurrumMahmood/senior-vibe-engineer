#!/usr/bin/env python3
"""Enumerate literals + callers for one stringly-typed state field.

Stage-1 collector for `/extract-enum`. Given a target `Model.<field>`,
walks the repository and produces ``targets.json`` with:

- Field declaration metadata (file path, current CharField/TextField
  kwargs — max_length, default, existing tuple-style choices list).
- Every distinct string literal compared against ``<anything>.<field>``
  anywhere in the project, ranked by occurrence count.
- Every caller site for those comparisons (file, symbol, evidence line).
- Every bare-string assignment of the shape ``obj.<field> = "..."``
  (these also need migration to enum members).

Two input shapes:

**Form A — finding id + findings.json.**
::

    collect.py --from-finding implicit-state-0007 \\
      --findings reports/implicit-state/latest/findings.json \\
      --project-root /path/to/your-project \\
      --output reports/extract-enum/<target>/targets.json

Loads the finding, extracts ``file``, infers ``<Model>`` and
``<field>`` from the finding's ``fields_touched`` / ``hits`` records,
then runs the repo scan.

**Form B — explicit ``<file>::<field>`` target.**
::

    collect.py --target <pkg>/models/crawl_jobs.py::status \\
      --project-root /path/to/your-project \\
      --output reports/extract-enum/<target>/targets.json

Parses the target string, locates the matching assignment inside a
``models.Model`` subclass, then runs the repo scan.

Output schema (written to ``--output``)::

    {
      "target_slug": "crawl_jobs__status",
      "model_class": "CrawlJob",
      "field_name": "status",
      "field_file": "<pkg>/models/crawl_jobs.py",
      "field_symbol": "CrawlJob.status",
      "current_kwargs": {
        "max_length": 20,
        "default": "pending",
        "tuple_choices": [["pending", "Pending"], ["running", "Running"]]
      },
      "literals": [
        {"value": "pending", "count": 12, "case_variant_of": null},
        {"value": "Pending", "count": 2, "case_variant_of": "pending"}
      ],
      "comparison_sites": [
        {"file": "<pkg>/views/crawling.py", "symbol": "is_pending",
         "op": "==", "literal": "pending",
         "evidence": "job.status == 'pending'"}
      ],
      "assignment_sites": [
        {"file": "<pkg>/tasks/crawling.py", "symbol": "start_job",
         "literal": "running",
         "evidence": "job.status = 'running'"}
      ],
      "callers_by_file": {
        "<pkg>/views/crawling.py": 4,
        "<pkg>/tasks/crawling.py": 8
      }
    }

Exit status:

    0  targets.json written (≥ 1 literal found)
    1  target resolved but 0 literals/comparisons found
    2  invocation error (finding not resolvable, field not found)

Stdlib-only. Runs under ``python3``.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
import scope as _scope  # noqa: E402

STATE_FIELD_CALLS = frozenset({"CharField", "TextField"})

_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
    "reference_code",
})
_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
)


def _walk_python_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in _DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if any(fnmatch.fnmatchcase(path.name, g) for g in _DEFAULT_SKIP_FILE_GLOBS):
            continue
        out.append(path)
    return out


def _enclosing_symbol(path: list[ast.AST]) -> str:
    for node in reversed(path):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node.name
    return "<module>"


def _annotation_name(node: ast.AST | None) -> str | None:
    """Extract a model class name from a type annotation, best-effort."""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value  # forward ref: "CrawlJob"
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        slice_node = getattr(node, "slice", None)
        return _annotation_name(slice_node)
    return None


def _climb_to_base_name(node: ast.AST) -> str | None:
    """Walk down nested Attribute/Call chains until we hit a Name."""
    visited = 0
    while visited < 32:
        visited += 1
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            node = node.value
            continue
        if isinstance(node, ast.Call):
            node = node.func
            continue
        return None
    return None


def _rhs_model_name(value: ast.AST | None) -> str | None:
    """If the RHS is ``<Model>(...)`` or ``<Model>.objects.<X>(...)``, return ``<Model>``."""
    if value is None:
        return None
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    if isinstance(func, ast.Name):
        return func.id if func.id[:1].isupper() else None
    if isinstance(func, ast.Attribute):
        base = _climb_to_base_name(func.value)
        return base if base and base[:1].isupper() else None
    return None


def _build_local_model_map(
    tree: ast.AST, target_model: str
) -> dict[int, set[str]]:
    """Map id(FunctionDef) → set of Name ids proven to reference ``target_model``.

    Sources of attribution inside a function body:
      - ``name: target_model = ...`` (AnnAssign with matching annotation).
      - ``name = target_model.objects.<method>(...)`` or
        ``... .filter(...).first()`` — RHS is a call whose base is
        ``target_model``.
      - ``name = target_model(...)`` (direct construction).
      - ``for name in target_model.objects....:`` loop iterator binding.
    We intentionally do NOT track across calls or re-assignments — the
    goal is catch the common idiomatic case, not be a full type inferrer.
    """
    out: dict[int, set[str]] = {}
    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        locals_of_target: set[str] = set()
        for stmt in ast.walk(func_node):
            if isinstance(stmt, ast.AnnAssign):
                ann = _annotation_name(stmt.annotation)
                if ann == target_model and isinstance(stmt.target, ast.Name):
                    locals_of_target.add(stmt.target.id)
            elif isinstance(stmt, ast.Assign):
                if _rhs_model_name(stmt.value) == target_model:
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            locals_of_target.add(t.id)
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                if (_rhs_model_name(stmt.iter) == target_model
                        and isinstance(stmt.target, ast.Name)):
                    locals_of_target.add(stmt.target.id)
        if locals_of_target:
            out[id(func_node)] = locals_of_target
    return out


def _attributed_to_model(
    attr_node: ast.Attribute,
    path: list[ast.AST],
    model_class: str,
    local_map: dict[int, set[str]],
    rel_file: str,
    decl_file: str | None,
) -> bool:
    """Return True when we can attribute ``<attr_node>.value`` to a
    ``model_class`` instance. Conservative — returns False when unsure.
    """
    # Direct class access: Model.field (e.g. CrawlJob.status).
    if isinstance(attr_node.value, ast.Name) and attr_node.value.id == model_class:
        return True
    # Same-file-as-declaration: class methods on the model itself. When
    # the file defines multiple Model classes (e.g. crawl_jobs.py with
    # CrawlJob + SitemapCrawlJob + UrlCrawlJob), the enclosing ClassDef
    # name must match ``model_class``; module-level helpers still pass.
    if decl_file and rel_file == decl_file:
        enclosing_class: str | None = None
        for n in reversed(path):
            if isinstance(n, ast.ClassDef):
                enclosing_class = n.name
                break
        if enclosing_class is None or enclosing_class == model_class:
            return True
    # Enclosing-function local-variable attribution.
    enclosing_func: ast.AST | None = None
    for n in reversed(path):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            enclosing_func = n
            break
    if enclosing_func is None:
        return False
    var_set = local_map.get(id(enclosing_func))
    if not var_set:
        return False
    if isinstance(attr_node.value, ast.Name) and attr_node.value.id in var_set:
        return True
    return False


def _string_literal_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_models_field_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in STATE_FIELD_CALLS:
        return True
    if isinstance(func, ast.Name) and func.id in STATE_FIELD_CALLS:
        return True
    return False


def _inside_model_class(path: list[ast.AST]) -> tuple[bool, str | None]:
    """Return (is_inside, class_name) walking outward from the node."""
    for node in reversed(path):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                return True, node.name
            if isinstance(base, ast.Name) and base.id == "Model":
                return True, node.name
    return False, None


def _segment_source(src_lines: list[str], node: ast.AST, limit: int = 240) -> str:
    lineno = getattr(node, "lineno", None)
    if lineno is None or lineno < 1 or lineno > len(src_lines):
        return ""
    raw = src_lines[lineno - 1].strip()
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return raw


def _extract_field_kwargs(call: ast.Call) -> dict[str, Any]:
    """Best-effort extraction of interesting CharField kwargs."""
    out: dict[str, Any] = {}
    for kw in call.keywords:
        if kw.arg is None:
            continue
        value = kw.value
        if kw.arg == "max_length" and isinstance(value, ast.Constant):
            out["max_length"] = value.value
            continue
        if kw.arg == "default":
            lit = _string_literal_value(value)
            if lit is not None:
                out["default"] = lit
            elif isinstance(value, ast.Attribute):
                # e.g. default=JobStatus.PENDING (already migrated)
                out["default"] = ast.unparse(value)
            continue
        if kw.arg == "choices":
            # Tuple-style: choices=STATUS_CHOICES (a Name) or choices=[(...)].
            if isinstance(value, ast.Name):
                out["choices_ref"] = value.id
            elif isinstance(value, (ast.List, ast.Tuple)):
                pairs: list[list[str]] = []
                for elt in value.elts:
                    if isinstance(elt, (ast.Tuple, ast.List)) and len(elt.elts) == 2:
                        a = _string_literal_value(elt.elts[0])
                        b = _string_literal_value(elt.elts[1])
                        if a is not None and b is not None:
                            pairs.append([a, b])
                if pairs:
                    out["tuple_choices"] = pairs
            elif isinstance(value, ast.Attribute):
                out["choices_ref"] = ast.unparse(value)
    return out


def _find_field_declaration(
    file_path: Path,
    rel: str,
    field_name: str,
    model_class: str | None,
) -> dict[str, Any] | None:
    """Locate the field declaration inside a models.Model subclass.

    Returns a dict with file, symbol (``Cls.field``), current_kwargs.
    When ``model_class`` is None, returns the first matching field
    declaration found in any Model subclass in the file.
    """
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        tree = ast.parse(src, filename=str(file_path))
    except SyntaxError:
        return None

    found: dict[str, Any] | None = None

    def visit(node: ast.AST, path: list[ast.AST]) -> None:
        nonlocal found
        if found is not None:
            return
        if isinstance(node, ast.Assign):
            inside, cls = _inside_model_class(path)
            if inside and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id == field_name:
                    if model_class and cls != model_class:
                        pass
                    else:
                        if isinstance(node.value, ast.Call) and _is_models_field_call(node.value):
                            found = {
                                "field_file": rel,
                                "field_symbol": f"{cls}.{field_name}",
                                "model_class": cls or "<unknown>",
                                "field_name": field_name,
                                "current_kwargs": _extract_field_kwargs(node.value),
                            }
                            return
        for child in ast.iter_child_nodes(node):
            visit(child, path + [node])

    visit(tree, [])
    return found


def _scan_comparisons_and_assignments(
    files: list[Path],
    project_root: Path,
    field_name: str,
    model_class: str | None = None,
    decl_file: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Return (comparison_sites, assignment_sites, dropped_count).

    Comparison: ``<expr>.<field> <op> "lit"``, both operand orders for
    ``==``/``!=``; ``in`` / ``not in`` with string-literal containers.
    Assignment: ``<expr>.<field> = "lit"`` (also ``AnnAssign``).

    When ``model_class`` is provided, hits that cannot be attributed to a
    ``model_class`` instance (via direct class access, same-file as the
    declaration, or enclosing-function local-variable tracking) are
    dropped. ``dropped_count`` counts those skipped hits for stderr
    transparency. When ``model_class`` is ``None``, every hit is kept.
    """
    comparisons: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    dropped = 0

    def _handle_compare(
        node: ast.Compare,
        src_lines: list[str],
        rel: str,
        path: list[ast.AST],
        local_map: dict[int, set[str]],
    ) -> None:
        nonlocal dropped
        if len(node.ops) != 1:
            return
        op = node.ops[0]
        left = node.left
        right = node.comparators[0]

        def _is_field_attr(n: ast.AST) -> bool:
            return isinstance(n, ast.Attribute) and n.attr == field_name

        if isinstance(op, (ast.Eq, ast.NotEq)):
            attr_node: ast.Attribute | None = None
            lit_node: ast.AST | None = None
            if _is_field_attr(left):
                attr_node, lit_node = left, right  # type: ignore[assignment]
            elif _is_field_attr(right):
                attr_node, lit_node = right, left  # type: ignore[assignment]
            if attr_node is None:
                return
            lit = _string_literal_value(lit_node)
            if lit is None:
                return
            if model_class and not _attributed_to_model(
                attr_node, path, model_class, local_map, rel, decl_file,
            ):
                dropped += 1
                return
            comparisons.append({
                "file": rel,
                "symbol": _enclosing_symbol(path),
                "op": "==" if isinstance(op, ast.Eq) else "!=",
                "literal": lit,
                "lineno": node.lineno,
                "evidence": _segment_source(src_lines, node),
            })
            return

        if isinstance(op, (ast.In, ast.NotIn)) and _is_field_attr(left):
            if isinstance(right, (ast.Tuple, ast.List, ast.Set)) and right.elts:
                lits: list[str] = []
                for elt in right.elts:
                    v = _string_literal_value(elt)
                    if v is None:
                        return
                    lits.append(v)
                if model_class and not _attributed_to_model(
                    left, path, model_class, local_map, rel, decl_file,  # type: ignore[arg-type]
                ):
                    dropped += len(lits)
                    return
                for lit in lits:
                    comparisons.append({
                        "file": rel,
                        "symbol": _enclosing_symbol(path),
                        "op": "in" if isinstance(op, ast.In) else "not in",
                        "literal": lit,
                        "lineno": node.lineno,
                        "evidence": _segment_source(src_lines, node),
                    })

    def _handle_assign(
        node: ast.Assign | ast.AnnAssign,
        src_lines: list[str],
        rel: str,
        path: list[ast.AST],
        local_map: dict[int, set[str]],
    ) -> None:
        nonlocal dropped
        # We only want OBJECT attribute assignments like `job.status = "..."`.
        # Skip assignments that ARE the field declaration — those are
        # detected separately. The declaration happens inside a Model
        # ClassDef via a Name target, not an Attribute target.
        if isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        else:
            if len(node.targets) != 1:
                return
            target = node.targets[0]
            value = node.value
        if value is None:
            return
        if not isinstance(target, ast.Attribute) or target.attr != field_name:
            return
        lit = _string_literal_value(value)
        if lit is None:
            return
        if model_class and not _attributed_to_model(
            target, path, model_class, local_map, rel, decl_file,
        ):
            dropped += 1
            return
        assignments.append({
            "file": rel,
            "symbol": _enclosing_symbol(path),
            "literal": lit,
            "lineno": node.lineno,
            "evidence": _segment_source(src_lines, node),
        })

    for file_path in files:
        try:
            src = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(src, filename=str(file_path))
        except SyntaxError:
            continue
        try:
            rel = str(file_path.relative_to(project_root))
        except ValueError:
            rel = str(file_path)
        src_lines = src.splitlines()
        local_map = (
            _build_local_model_map(tree, model_class) if model_class else {}
        )

        def visit(
            node: ast.AST,
            path: list[ast.AST],
            src_lines: list[str] = src_lines,
            rel: str = rel,
            local_map: dict = local_map,
        ) -> None:
            if isinstance(node, ast.Compare):
                _handle_compare(node, src_lines, rel, path, local_map)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                _handle_assign(node, src_lines, rel, path, local_map)
            for child in ast.iter_child_nodes(node):
                visit(child, path + [node])

        visit(tree, [])

    return comparisons, assignments, dropped


def _rank_literals(
    comparisons: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank literals by total occurrence (comparisons + assignments)
    and flag case-variants.

    Case-variants: two literals whose ``.lower()`` matches but whose
    raw form differs (e.g. ``"Pending"`` and ``"pending"``). The
    lower-cased form is the canonical; all other cases point at it via
    ``case_variant_of``.
    """
    counts: dict[str, int] = defaultdict(int)
    for site in comparisons:
        counts[site["literal"]] += 1
    for site in assignments:
        counts[site["literal"]] += 1
    if not counts:
        return []

    # Identify canonical vs variant.
    canonicals: dict[str, str] = {}  # lower -> chosen canonical
    for lit in counts:
        low = lit.lower()
        current = canonicals.get(low)
        # Prefer the lower-case form; else the highest-count form.
        if current is None:
            canonicals[low] = lit
        else:
            if lit == low and current != low:
                canonicals[low] = lit
            elif counts[lit] > counts[current] and current != low:
                canonicals[low] = lit

    ranked: list[dict[str, Any]] = []
    for lit, count in counts.items():
        low = lit.lower()
        canonical = canonicals[low]
        ranked.append({
            "value": lit,
            "count": count,
            "case_variant_of": None if lit == canonical else canonical,
        })
    ranked.sort(key=lambda r: (-r["count"], r["value"]))
    return ranked


def _callers_by_file(
    comparisons: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for site in comparisons:
        out[site["file"]] += 1
    for site in assignments:
        out[site["file"]] += 1
    return dict(out)


def _target_slug(model_class: str | None, field_name: str, fallback_path: Path) -> str:
    base = (model_class or fallback_path.stem).lower()
    # Keep it filesystem-safe.
    base = "".join(c if c.isalnum() or c in "_-" else "_" for c in base)
    return f"{base}__{field_name}"


def _resolve_from_finding(
    findings_path: Path, finding_id: str
) -> tuple[str, str, str | None]:
    """Return (file, field_name, model_class_hint) from a findings.json.

    ``findings.json`` shape is the schema produced by ``/find-implicit-state``
    (one JSONL record per candidate). We accept either JSONL or a JSON
    object with ``{"candidates": [...]}``.

    The ``model_class_hint`` is the finding's ``recommendation_hint_symbol``
    when present — needed because ``file`` is the *caller* site (where the
    smell was detected), not necessarily the file that declares the field.
    """
    if not findings_path.exists():
        raise FileNotFoundError(
            f"findings file not found: {findings_path}\n"
            "Run /find-implicit-state first."
        )
    try:
        raw = findings_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"could not read findings file: {findings_path}\n{exc}") from exc
    records: list[dict[str, Any]] = []
    if raw.startswith("{"):
        obj = json.loads(raw)
        records = obj.get("findings") or obj.get("candidates") or []
    else:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    match = next(
        (r for r in records if r.get("candidate_id") == finding_id
         or r.get("id") == finding_id),
        None,
    )
    if match is None:
        ids = ", ".join(
            str(r.get("candidate_id") or r.get("id") or "?")
            for r in records[:10]
        ) or "<none>"
        raise KeyError(
            f"finding {finding_id!r} not present in {findings_path}. "
            f"First 10 IDs: {ids}"
        )
    file = match.get("file")
    if not file:
        raise ValueError(f"finding {finding_id} has no 'file' field")
    fields = match.get("fields_touched") or []
    field_name = fields[0] if fields else None
    if not field_name:
        # Fallback: inspect hits for 'field'.
        for hit in match.get("hits", []):
            f = hit.get("field")
            if isinstance(f, str):
                field_name = f
                break
    if not field_name:
        raise ValueError(
            f"finding {finding_id} has no 'fields_touched' — "
            "cannot infer which state field to extract"
        )
    hint = match.get("recommendation_hint_symbol")
    model_class_hint = hint.strip() if isinstance(hint, str) and hint.strip() else None
    return file, field_name, model_class_hint


def _parse_explicit_target(target: str) -> tuple[str, str, str | None]:
    """Parse ``<file>::<field>`` or ``<file>::<field>::<ModelClass>``."""
    if "::" not in target:
        raise ValueError(
            f"--target must be '<file>::<field>' or "
            f"'<file>::<field>::<ModelClass>', got: {target!r}"
        )
    parts = [p.strip() for p in target.split("::")]
    if len(parts) == 2:
        file, field = parts
        model_class = None
    elif len(parts) == 3:
        file, field, model_class = parts
        model_class = model_class or None
    else:
        raise ValueError(
            f"--target accepts at most 3 ::-separated parts: {target!r}"
        )
    if not file or not field:
        raise ValueError(f"--target must be non-empty on both sides: {target!r}")
    return file, field, model_class


def _find_model_declaration_file(
    project_root: Path, model_class: str
) -> Path | None:
    """Locate the file declaring ``class <model_class>(`` anywhere in scope.

    Walks the host-authored ignore-first scope (whole repo minus the builtin
    noise floor minus the host's `## Ignore`, or the optional `## Roots`
    narrowing) rather than assuming any one app-root layout. Returns the first
    file (the iterator is already sorted) whose text contains
    ``class <model_class>(``, else ``None``.
    """
    needle = f"class {model_class}("
    for path in _scope.iter_paths(
        project_root, _scope.Scope(), extensions=frozenset({".py"})
    ):
        try:
            src = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if needle in src:
            return path
    return None


# spec:status-projection-and-presentation::IM-5
def _write_scope_sidecar(artifact_dir: Path, paths: list[str]) -> None:
    """scope.json sidecar (ADR 0037) — declares which repo paths this
    artifact's conclusions depend on, so the status projection can flag
    input drift. Strictly additive; silently skipped when the toolkit
    helper is absent (skill vendored without scripts/_lib)."""
    helper = Path(__file__).resolve().parents[4] / "scripts" / "_lib" / "artifact_scope.py"
    if not helper.is_file():
        return
    import importlib.util

    spec = importlib.util.spec_from_file_location("artifact_scope", helper)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.write_scope(artifact_dir, paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-finding", dest="from_finding", metavar="CANDIDATE_ID",
                     help="Candidate ID in --findings to resolve")
    src.add_argument("--target", dest="target", metavar="FILE::FIELD",
                     help="Explicit target, e.g. <pkg>/models/crawl_jobs.py::status")
    parser.add_argument("--findings", type=Path,
                        default=Path("reports/implicit-state/latest/findings.json"),
                        help="findings.json from /find-implicit-state (Form A)")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-class", default=None,
                        help="Optional: narrow to a specific Model subclass "
                             "when the field name is reused across models")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()

    try:
        if args.from_finding:
            rel_file, field_name, finding_hint = _resolve_from_finding(
                args.findings, args.from_finding
            )
        else:
            rel_file, field_name, finding_hint = _parse_explicit_target(args.target)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Effective model class: explicit --model-class wins, then finding hint.
    model_class = args.model_class or finding_hint

    field_path = (project_root / rel_file).resolve()
    try:
        field_path.relative_to(project_root)
    except ValueError:
        print(
            f"error: target {rel_file!r} resolves outside project root "
            f"{project_root} — refusing to read",
            file=sys.stderr,
        )
        return 2
    if not field_path.exists():
        print(f"error: field file not found: {field_path}", file=sys.stderr)
        return 2

    decl = _find_field_declaration(
        field_path, rel_file, field_name, model_class
    )
    if decl is None and model_class:
        # The finding's file may be a caller site, not the model declaration.
        # Fall back to searching the in-scope tree for `class <model_class>(`.
        alt_path = _find_model_declaration_file(project_root, model_class)
        if alt_path is not None:
            try:
                alt_rel = str(alt_path.relative_to(project_root))
            except ValueError:
                alt_rel = str(alt_path)
            alt_decl = _find_field_declaration(
                alt_path, alt_rel, field_name, model_class
            )
            if alt_decl is not None:
                print(
                    f"[collect_extract_enum] note: {rel_file!r} is a caller "
                    f"site; resolved {model_class}.{field_name} declaration "
                    f"in {alt_rel}",
                    file=sys.stderr,
                )
                rel_file = alt_rel
                field_path = alt_path
                decl = alt_decl
    if decl is None:
        print(
            f"error: no Model subclass in {rel_file} declares "
            f"`{field_name}` as CharField/TextField"
            + (f" (model={model_class})" if model_class else ""),
            file=sys.stderr,
        )
        print(
            "hint: if the carrier is NOT a Django model field (a dataclass "
            "attribute, function return, module constant, or command-internal "
            "sentinel), the endpoint is a plain str-valued Enum (enum.StrEnum "
            "on 3.11+, or class X(str, Enum)), not TextChoices — this collector "
            "only walks model fields. Apply it by hand; do not # noqa a "
            "first-party sentinel.",
            file=sys.stderr,
        )
        return 2

    files = _walk_python_files(project_root)
    model_class_for_filter = decl.get("model_class")
    if model_class_for_filter == "<unknown>":
        model_class_for_filter = None
    comparisons, assignments, dropped = _scan_comparisons_and_assignments(
        files,
        project_root,
        field_name,
        model_class=model_class_for_filter,
        decl_file=decl.get("field_file"),
    )

    literals = _rank_literals(comparisons, assignments)
    if not literals:
        print(
            f"error: zero comparisons/assignments found for "
            f"`<expr>.{field_name}` anywhere in {project_root}",
            file=sys.stderr,
        )
        return 1

    target = {
        "target_slug": _target_slug(
            decl["model_class"], field_name, field_path
        ),
        "model_class": decl["model_class"],
        "field_name": field_name,
        "field_file": decl["field_file"],
        "field_symbol": decl["field_symbol"],
        "current_kwargs": decl["current_kwargs"],
        "literals": literals,
        "comparison_sites": comparisons,
        "assignment_sites": assignments,
        "callers_by_file": _callers_by_file(comparisons, assignments),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(target, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_scope_sidecar(
        args.output.parent,
        sorted({decl["field_file"], *target["callers_by_file"]}),
    )

    # Stderr summary.
    unique_callers = len(target["callers_by_file"])
    case_variants = sum(1 for lit in literals if lit.get("case_variant_of"))
    dropped_note = f" — dropped {dropped} ambiguous cross-model hits" if dropped else ""
    print(
        f"[collect_extract_enum] wrote {args.output}: "
        f"{decl['field_symbol']} — {len(literals)} literals "
        f"({case_variants} case-variants) across {unique_callers} files "
        f"({len(comparisons)} comparisons, {len(assignments)} assignments)"
        f"{dropped_note}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
