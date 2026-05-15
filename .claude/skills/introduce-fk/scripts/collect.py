#!/usr/bin/env python3
"""Enumerate tuple-inferred-identity sites for one owner/owned pair.

Stage-1 collector for `/introduce-fk`. Given an owner model and a
target relationship currently inferred via
``<TargetModel>.objects.filter(<state kwargs>, <time kwargs>).first()``,
walks the repo and produces ``targets.json`` with:

- Owner + target model metadata (file paths, whether a direct FK
  already exists — a run on an existing FK is an error).
- Every call site of the tuple-inference pattern, tagged with:

  - The exact kwargs passed to ``.filter(...)`` (state + time).
  - The terminal shape (``.first()`` / ``[0]``).
  - The assignment target name, if any (``active_job``,
    ``active_crawl_job``, ``latest_export``), used as an FK-name hint.
- Derived FK metadata: proposed field name, ``on_delete`` default,
  ``related_name`` candidate.

Two input shapes:

**Form A — finding id + findings.json.** (same layout as `/extract-enum`)
::

    collect.py --from-finding implicit-state-0012 \\
      --findings reports/implicit-state/latest/findings.json \\
      --project-root /path/to/your-project \\
      --output reports/introduce-fk/<target>/targets.json

Loads the `tuple_identity` candidate, resolves owner/target models
from the hits' filter-chain metadata.

**Form B — explicit target spec.** A structured ``owner -> target via
field`` string:
::

    collect.py \\
      --target "core/models/sitemaps.py::UrlCollection -> core/models/crawl_jobs.py::UrlCrawlJob via active_crawl_job" \\
      --project-root /path/to/your-project \\
      --output reports/introduce-fk/<target>/targets.json

Output schema (written to ``--output``)::

    {
      "target_slug": "urlcollection__active_crawl_job",
      "owner_model": "UrlCollection",
      "owner_file": "core/models/sitemaps.py",
      "target_model": "UrlCrawlJob",
      "target_file": "core/models/crawl_jobs.py",
      "proposed_fk_name": "active_crawl_job",
      "proposed_related_name": "+",
      "proposed_on_delete": "SET_NULL",
      "tuple_inference_shape": {
        "state_kwargs": ["status"],
        "state_literal_kwargs": {"status__in": ["pending", "running", "paused"]},
        "time_kwargs": [],
        "extra_kwargs": ["current_url_status__icontains"],
        "terminal": "first"
      },
      "call_sites": [
        {
          "file": "core/views/collections.py",
          "symbol": "StartCollectionCrawlView.post",
          "lineno": 349,
          "assigned_to": "active_job",
          "evidence": "active_job = UrlCrawlJob.objects.filter(..."
        }
      ],
      "owner_has_existing_fk": false,
      "existing_fk_candidates": []
    }

Exit status:

    0  targets.json written (≥ 1 call site)
    1  target resolved but 0 call sites found
    2  invocation error

Stdlib-only. Runs under ``python3``.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

STATE_FIELD_NAMES = frozenset({"status", "phase", "state"})
TIME_LOOKUP_SUFFIXES = (
    "__gt", "__gte", "__lt", "__lte", "__range", "__isnull",
    "__date", "__year", "__month", "__day",
)
TIME_FIELD_SUFFIX = "_at"
# Lookups that signal "row identity is encoded inside another field's
# free text" — discriminating which row belongs to *this owner* via a
# substring/regex match instead of an FK. This is tuple-identity at its
# worst (brittle on column rename, vulnerable to data drift) and the
# /introduce-fk skill should treat it as evidence even when no time
# kwarg is present.
DISCRIMINATOR_LOOKUP_SUFFIXES = (
    "__icontains", "__contains", "__iexact",
    "__startswith", "__endswith",
    "__istartswith", "__iendswith",
    "__regex", "__iregex",
)

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


def _string_literal_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _string_literal_container(node: ast.AST) -> list[str] | None:
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return None
    if not node.elts:
        return None
    out: list[str] = []
    for elt in node.elts:
        v = _string_literal_value(elt)
        if v is None:
            return None
        out.append(v)
    return out


def _enclosing_symbol(path: list[ast.AST]) -> str:
    """Return the enclosing qualified symbol (ClassDef.method or func)."""
    parts: list[str] = []
    for node in path:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            parts.append(node.name)
    if not parts:
        return "<module>"
    return ".".join(parts)


def _segment_source(src_lines: list[str], node: ast.AST, limit: int = 240) -> str:
    lineno = getattr(node, "lineno", None)
    if lineno is None or lineno < 1 or lineno > len(src_lines):
        return ""
    raw = src_lines[lineno - 1].strip()
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return raw


def _is_state_kwarg(name: str | None) -> bool:
    if not name:
        return False
    base = name.split("__")[0]
    return base in STATE_FIELD_NAMES


def _is_time_kwarg(name: str | None) -> bool:
    if not name:
        return False
    parts = name.split("__")
    field_part = parts[0]
    if not field_part.endswith(TIME_FIELD_SUFFIX):
        return False
    if len(parts) == 1:
        return True
    return any(name.endswith(suffix) for suffix in TIME_LOOKUP_SUFFIXES)


def _has_discriminator_lookup(extra_kwargs: list[str]) -> bool:
    """True when an extra kwarg encodes row identity via substring /
    regex match on another field — e.g.
    ``current_url_status__icontains='Collection: foo'``.
    """
    return any(
        any(name.endswith(suf) for suf in DISCRIMINATOR_LOOKUP_SUFFIXES)
        for name in extra_kwargs
    )


def _model_hint_from_filter_chain(call: ast.Call) -> str | None:
    func = call.func
    while isinstance(func, ast.Attribute):
        if func.attr == "objects":
            base = func.value
            if isinstance(base, ast.Name):
                return base.id
            if isinstance(base, ast.Attribute):
                return base.attr
            return None
        inner = func.value
        if isinstance(inner, ast.Call):
            func = inner.func
            continue
        if isinstance(inner, ast.Attribute):
            func = inner
            continue
        break
    return None


def _walk_for_filter(node: ast.AST) -> ast.Call | None:
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, ast.Call):
            func = cur.func
            if isinstance(func, ast.Attribute) and func.attr == "filter":
                return cur
            if isinstance(func, ast.Attribute):
                cur = func.value
                continue
            return None
        if isinstance(cur, ast.Attribute):
            cur = cur.value
            continue
        return None
    return None


def _find_terminal_filter_usage(
    node: ast.AST,
) -> tuple[ast.Call, str] | None:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "first":
            filter_call = _walk_for_filter(func.value)
            if filter_call is not None:
                return filter_call, "first"
    if isinstance(node, ast.Subscript):
        idx = node.slice
        if isinstance(idx, ast.Constant) and idx.value == 0:
            filter_call = _walk_for_filter(node.value)
            if filter_call is not None:
                return filter_call, "index0"
    return None


def _assigned_target_name(stmt_stack: list[ast.AST]) -> str | None:
    for parent in reversed(stmt_stack):
        if isinstance(parent, ast.Assign):
            if len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
                return parent.targets[0].id
            return None
        if isinstance(parent, ast.AnnAssign):
            if isinstance(parent.target, ast.Name):
                return parent.target.id
            return None
    return None


def _collect_filter_kwargs_detail(call: ast.Call) -> dict[str, Any]:
    """Return the filter kwargs split by role (state / time / other)
    and capture literal values where we can."""
    state_kwargs: list[str] = []
    time_kwargs: list[str] = []
    extra_kwargs: list[str] = []
    state_literals: dict[str, Any] = {}
    for kw in call.keywords:
        name = kw.arg
        if name is None:
            continue
        if _is_state_kwarg(name):
            state_kwargs.append(name)
            lit = _string_literal_value(kw.value)
            if lit is not None:
                state_literals[name] = lit
            else:
                lits = _string_literal_container(kw.value)
                if lits is not None:
                    state_literals[name] = lits
        elif _is_time_kwarg(name):
            time_kwargs.append(name)
        else:
            extra_kwargs.append(name)
    return {
        "state_kwargs": state_kwargs,
        "time_kwargs": time_kwargs,
        "extra_kwargs": extra_kwargs,
        "state_literal_kwargs": state_literals,
    }


def _scan_file_for_pattern(
    file_path: Path,
    rel: str,
    target_model: str | None,
) -> list[dict[str, Any]]:
    """Find tuple-inference sites in one file.

    When ``target_model`` is provided, only sites filtering on that
    model's queryset are included.
    """
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src, filename=str(file_path))
    except SyntaxError:
        return []
    src_lines = src.splitlines()
    out: list[dict[str, Any]] = []

    def visit(node: ast.AST, path: list[ast.AST]) -> None:
        term = _find_terminal_filter_usage(node)
        if term is not None:
            filter_call, terminal = term
            model_hint = _model_hint_from_filter_chain(filter_call)
            if target_model and model_hint != target_model:
                pass  # skip
            else:
                detail = _collect_filter_kwargs_detail(filter_call)
                # Tuple-identity requires state narrowing PLUS one of:
                #   - a time kwarg (``created_at__gt=...``), OR
                #   - a discriminator-lookup extra kwarg
                #     (``current_url_status__icontains='Collection: '``).
                # State-only filter.first() is a read of "some row in
                # state X" — not identity inference. Time-only is a
                # "latest" query. The pair (state + time) encodes the
                # canonical ``(status=X, created_at__gt=Y).first()``
                # smell; the (state + discriminator-lookup) variant
                # encodes the worse "row identity inferred from a
                # substring/regex match on free text" smell.
                has_discriminator = _has_discriminator_lookup(detail["extra_kwargs"])
                if detail["state_kwargs"] and (
                    detail["time_kwargs"] or has_discriminator
                ):
                    assigned = _assigned_target_name(path)
                    out.append({
                        "file": rel,
                        "symbol": _enclosing_symbol(path),
                        "lineno": node.lineno,
                        "model_hint": model_hint,
                        "terminal": terminal,
                        "assigned_to": assigned,
                        "evidence": _segment_source(src_lines, node),
                        **detail,
                    })
        for child in ast.iter_child_nodes(node):
            visit(child, path + [node])

    visit(tree, [])
    return out


def _find_model_class(
    file_path: Path,
    model_name: str,
) -> dict[str, Any] | None:
    """Locate a ``models.Model`` subclass by name in ``file_path``.

    Returns {file, class_name, existing_fks: [{name, target}]}.
    """
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        tree = ast.parse(src, filename=str(file_path))
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name != model_name:
            continue
        is_model = False
        for base in node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                is_model = True
            elif isinstance(base, ast.Name) and base.id == "Model":
                is_model = True
        if not is_model:
            continue
        fks = _extract_foreign_keys(node)
        return {"class_name": model_name, "existing_fks": fks}
    return None


def _extract_foreign_keys(cls: ast.ClassDef) -> list[dict[str, Any]]:
    """Return [{name, target}] for every ForeignKey field on the class."""
    out: list[dict[str, Any]] = []
    for stmt in cls.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = stmt.value
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        name = None
        if isinstance(func, ast.Attribute) and func.attr == "ForeignKey":
            name = "ForeignKey"
        elif isinstance(func, ast.Name) and func.id == "ForeignKey":
            name = "ForeignKey"
        if name is None:
            continue
        # First positional arg is the target (string or class ref).
        target_model = None
        if value.args:
            t = value.args[0]
            lit = _string_literal_value(t)
            if lit is not None:
                target_model = lit
            elif isinstance(t, ast.Name):
                target_model = t.id
            elif isinstance(t, ast.Attribute):
                target_model = t.attr
        out.append({"name": target.id, "target": target_model})
    return out


def _proposed_fk_name(
    target_model: str,
    call_sites: list[dict[str, Any]],
) -> str:
    """Pick a conventional FK field name.

    Preference order:
    1. Most-common non-None ``assigned_to`` among call sites (e.g.
       ``active_job`` → ``active_job``, or normalized to match target).
    2. ``active_<target_model_lower_snake>`` as a generic default.
    """
    counts: dict[str, int] = defaultdict(int)
    for site in call_sites:
        name = site.get("assigned_to")
        if isinstance(name, str):
            counts[name] += 1
    if counts:
        # Highest count wins; tiebreak alphabetical.
        winner = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        # Skip single-letter or obviously-unrelated names.
        if len(winner) > 1:
            return winner
    snake = _camel_to_snake(target_model)
    return f"active_{snake}"


def _camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _target_slug(owner_model: str, fk_name: str) -> str:
    base = _camel_to_snake(owner_model)
    return f"{base}__{fk_name}"


_TARGET_RE = re.compile(
    r"^(?P<owner_file>[^:]+)::(?P<owner_model>\w+)\s*->\s*"
    r"(?P<target_file>[^:]+)::(?P<target_model>\w+)"
    r"(?:\s+via\s+(?P<fk_name>\w+))?\s*$"
)


def _parse_explicit_target(target: str) -> dict[str, str]:
    m = _TARGET_RE.match(target)
    if not m:
        raise ValueError(
            "--target must be 'OWNER_FILE::OwnerModel -> TARGET_FILE::TargetModel [via fk_name]'; "
            f"got: {target!r}"
        )
    out = m.groupdict()
    # Strip optional 'via' group into None if absent.
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in out.items()}


def _resolve_from_finding(findings_path: Path, finding_id: str) -> dict[str, Any]:
    if not findings_path.exists():
        raise FileNotFoundError(
            f"findings file not found: {findings_path}\n"
            "Run /find-implicit-state first."
        )
    raw = findings_path.read_text(encoding="utf-8").strip()
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
    pattern = match.get("pattern")
    if pattern != "tuple_identity":
        raise ValueError(
            f"finding {finding_id} has pattern={pattern!r}; "
            "/introduce-fk only handles tuple_identity. "
            f"Try /extract-enum instead for '{pattern}'."
        )
    return match


def _infer_owner_from_hits(
    finding: dict[str, Any],
    project_root: Path,
) -> tuple[str, str] | None:
    """Best-effort infer the owner model + file from a tuple_identity
    finding. The finding knows the *target* model (via ``model_hint``
    in each hit); we can't automatically know the *owner* without the
    user telling us. Return None when inference is impossible."""
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-finding", dest="from_finding", metavar="CANDIDATE_ID",
                     help="Candidate ID in --findings to resolve")
    src.add_argument("--target", dest="target", metavar="SPEC",
                     help="'OWNER_FILE::OwnerModel -> TARGET_FILE::TargetModel [via fk_name]'")
    parser.add_argument("--findings", type=Path,
                        default=Path("reports/implicit-state/latest/findings.json"),
                        help="findings.json from /find-implicit-state (Form A)")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--owner-spec", default=None,
                        help="For Form A only: 'OWNER_FILE::OwnerModel' — "
                             "the finding tells us the target model but not "
                             "the owner; supply it explicitly")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()

    owner_file: str | None = None
    owner_model: str | None = None
    target_file: str | None = None
    target_model: str | None = None
    fk_name_hint: str | None = None

    try:
        if args.from_finding:
            finding = _resolve_from_finding(args.findings, args.from_finding)
            hits = finding.get("hits") or []
            target_model = next(
                (h.get("model_hint") for h in hits if h.get("model_hint")),
                None,
            )
            if not target_model:
                print(
                    f"error: finding {args.from_finding} has no model_hint "
                    "on any hit — /introduce-fk needs the target model; "
                    "re-invoke with Form B (--target)",
                    file=sys.stderr,
                )
                return 2
            if not args.owner_spec:
                print(
                    f"error: finding {args.from_finding} identifies target "
                    f"model={target_model!r} but the owner model cannot be "
                    "inferred from a /find-implicit-state record; re-invoke "
                    "with --owner-spec 'OWNER_FILE::OwnerModel'",
                    file=sys.stderr,
                )
                return 2
            if "::" not in args.owner_spec:
                print(
                    f"error: --owner-spec must be 'FILE::Model'; got {args.owner_spec!r}",
                    file=sys.stderr,
                )
                return 2
            owner_file, owner_model = args.owner_spec.split("::", 1)
            owner_file = owner_file.strip()
            owner_model = owner_model.strip()
            # Try to locate the target model file inside the project.
            target_file = _locate_model_file(project_root, target_model)
            if target_file is None:
                print(
                    f"error: cannot locate model class {target_model!r} in "
                    f"{project_root}/core/models/",
                    file=sys.stderr,
                )
                return 2
        else:
            spec = _parse_explicit_target(args.target)
            owner_file = spec["owner_file"]
            owner_model = spec["owner_model"]
            target_file = spec["target_file"]
            target_model = spec["target_model"]
            fk_name_hint = spec.get("fk_name")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    assert owner_file and owner_model and target_file and target_model

    owner_path = (project_root / owner_file).resolve()
    target_path = (project_root / target_file).resolve()
    for label, path in (("owner", owner_path), ("target", target_path)):
        try:
            path.relative_to(project_root)
        except ValueError:
            print(
                f"error: {label} path resolves outside project root "
                f"{project_root}: {path} — refusing to read",
                file=sys.stderr,
            )
            return 2
    if not owner_path.exists():
        print(f"error: owner file not found: {owner_path}", file=sys.stderr)
        return 2
    if not target_path.exists():
        print(f"error: target file not found: {target_path}", file=sys.stderr)
        return 2

    owner_meta = _find_model_class(owner_path, owner_model)
    if owner_meta is None:
        print(
            f"error: {owner_file} does not declare a models.Model subclass named {owner_model!r}",
            file=sys.stderr,
        )
        return 2

    files = _walk_python_files(project_root)
    all_sites: list[dict[str, Any]] = []
    for f in files:
        try:
            rel = str(f.relative_to(project_root))
        except ValueError:
            rel = str(f)
        all_sites.extend(_scan_file_for_pattern(f, rel, target_model))

    if not all_sites:
        print(
            f"error: zero tuple-inference call sites found for "
            f"{target_model} (filter on state kwargs + .first()/[0]) in {project_root}",
            file=sys.stderr,
        )
        return 1

    existing_fk_match = next(
        (fk for fk in owner_meta["existing_fks"]
         if _fk_points_at(fk, target_model, target_file)),
        None,
    )
    owner_has_existing_fk = existing_fk_match is not None

    proposed_fk_name = fk_name_hint or _proposed_fk_name(target_model, all_sites)

    # Tuple shape summary: pick the most common state_kwargs + time_kwargs
    # signature across call sites.
    state_kwargs_set: set[str] = set()
    time_kwargs_set: set[str] = set()
    extra_kwargs_set: set[str] = set()
    state_literal_kwargs: dict[str, Any] = {}
    terminals: set[str] = set()
    for site in all_sites:
        state_kwargs_set.update(site.get("state_kwargs") or [])
        time_kwargs_set.update(site.get("time_kwargs") or [])
        extra_kwargs_set.update(site.get("extra_kwargs") or [])
        terminals.add(site.get("terminal") or "?")
        for k, v in (site.get("state_literal_kwargs") or {}).items():
            # Union literal sets.
            existing = state_literal_kwargs.get(k)
            if existing is None:
                state_literal_kwargs[k] = v
            elif isinstance(existing, list) and isinstance(v, list):
                state_literal_kwargs[k] = sorted(set(existing) | set(v))
            elif isinstance(existing, list) and isinstance(v, str):
                state_literal_kwargs[k] = sorted(set(existing) | {v})
            elif isinstance(existing, str) and isinstance(v, list):
                state_literal_kwargs[k] = sorted({existing} | set(v))
            elif isinstance(existing, str) and isinstance(v, str):
                if existing != v:
                    state_literal_kwargs[k] = sorted({existing, v})

    target = {
        "target_slug": _target_slug(owner_model, proposed_fk_name),
        "owner_model": owner_model,
        "owner_file": owner_file,
        "target_model": target_model,
        "target_file": target_file,
        "proposed_fk_name": proposed_fk_name,
        "proposed_related_name": "+",
        "proposed_on_delete": "SET_NULL",
        "tuple_inference_shape": {
            "state_kwargs": sorted(state_kwargs_set),
            "state_literal_kwargs": state_literal_kwargs,
            "time_kwargs": sorted(time_kwargs_set),
            "extra_kwargs": sorted(extra_kwargs_set),
            "terminals": sorted(terminals),
        },
        "call_sites": all_sites,
        "owner_has_existing_fk": owner_has_existing_fk,
        "existing_fk_candidates": owner_meta["existing_fks"],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(target, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        f"[collect_introduce_fk] wrote {args.output}: "
        f"{owner_model} -> {target_model} ({len(all_sites)} call sites, "
        f"proposed_fk_name={proposed_fk_name}, "
        f"owner_has_existing_fk={owner_has_existing_fk})",
        file=sys.stderr,
    )
    return 0


def _fk_points_at(fk: dict[str, Any], target_model: str, target_file: str) -> bool:
    """Best-effort: does fk.target look like `TargetModel` or
    `app.TargetModel`?"""
    t = fk.get("target") or ""
    if not isinstance(t, str):
        return False
    tail = t.rsplit(".", 1)[-1]
    return tail == target_model


def _locate_model_file(project_root: Path, model_name: str) -> str | None:
    """Find which `core/models/*.py` declares `class <model_name>(models.Model)`."""
    models_dir = project_root / "core" / "models"
    if not models_dir.exists():
        return None
    pattern = re.compile(
        rf"^\s*class\s+{re.escape(model_name)}\s*\(.*Model\b",
        re.MULTILINE,
    )
    for path in models_dir.glob("*.py"):
        try:
            src = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pattern.search(src):
            try:
                return str(path.relative_to(project_root))
            except ValueError:
                return str(path)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
