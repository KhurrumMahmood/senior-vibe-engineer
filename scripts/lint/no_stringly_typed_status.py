#!/usr/bin/env python3
"""Stringly-typed-status lint rule.

Two checks in one rule:

**Check A — field declarations.** Flags Django model fields named
``status`` / ``phase`` / ``state`` declared as
``models.CharField`` / ``models.TextField`` without a
``choices=<TextChoices subclass>`` argument.

**Check B — comparisons.** Flags comparisons of the shape
``<expr>.status == "literal"`` (also ``!=``, ``in``, ``not in``;
both operand orderings for ``==``/``!=``). This is the typo-prone
call-site shape: a TextChoices enum exists, but the caller still
types a bare string, so the compare silently no-ops on rename or
typo.

See ``.claude/docs/architectural-smells.md`` smell 2 (stringly-typed
state) and the CLAUDE.md Canonical Pattern "stringly-status".

Canonical bad shapes::

    # A: field declaration without TextChoices
    class CrawlJob(models.Model):
        status = models.CharField(max_length=20, default="pending")

    # B: comparison against a string literal
    def is_pending(job):
        return job.status == "pending"            # flag

    def is_active(job):
        return job.state in ("queued", "running") # flag

Canonical good shapes::

    class JobStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"

    class CrawlJob(models.Model):
        status = models.CharField(
            max_length=20,
            choices=JobStatus.choices,
            default=JobStatus.PENDING,
        )

    def is_pending(job):
        return job.status == JobStatus.PENDING    # enum-member ref

Allow-list: add ``# noqa: stringly-status: <reason>`` on any line of
the flagged construct (field assignment or compare expression).
Reason must be non-empty. Typical legitimate reasons:

    # noqa: stringly-status: third-party schema mirrors external state verbatim
    # noqa: stringly-status: legacy column, migration pending in spec <id>
    # noqa: stringly-status: bridge value from vendor webhook, enum not yet available

Usage:

    scripts/lint/no_stringly_typed_status.py <file-or-dir> [<file-or-dir> ...]
    scripts/lint/no_stringly_typed_status.py --stdin --filename=<display-name>

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error

Stdlib-only.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from path_utils import expand_python_paths

# Field names that strongly signal enum-worthy state. Kept narrow — adding
# more names here broadens the rule; prefer per-project extension via a
# separate rule file if the list grows.
STATE_FIELD_NAMES = {"status", "phase", "state"}

# Django field constructors that carry string state. Other fields
# (IntegerField, ForeignKey, ...) can encode state too, but this rule
# targets the specific string-typed smell.
STATE_FIELD_CALLS = {"CharField", "TextField"}

NOQA_RE = re.compile(r"#\s*noqa:\s*stringly-status:\s*\S")


def _is_models_field_call(call: ast.Call, target_names: set[str]) -> bool:
    """Return True when ``call`` looks like ``models.CharField(...)`` or
    ``CharField(...)`` (after ``from django.db.models import CharField``).
    """
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in target_names:
        # models.CharField, db_models.CharField, etc.
        return True
    if isinstance(func, ast.Name) and func.id in target_names:
        return True
    return False


def _kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _has_textchoices_choices(call: ast.Call) -> bool:
    """Return True when ``choices=`` references something that looks like a
    TextChoices / IntegerChoices class. Cross-module resolution is out of
    scope; we accept any callee/attribute whose name ends in ``Choices``,
    ``Status``, ``State``, or ``Phase`` — the conventional TextChoices
    naming. An explicit hard-coded list (``choices=[(...)]``) does NOT
    satisfy the rule, because that's exactly the stringly-typed shape we
    want to eliminate.
    """
    choices = _kwarg(call, "choices")
    if choices is None:
        return False
    # `choices=JobStatus.choices` — Attribute on a Name
    if isinstance(choices, ast.Attribute):
        base = choices.value
        if isinstance(base, ast.Name) and _looks_like_choices_name(base.id):
            return True
        # Nested: some.module.JobStatus.choices
        if isinstance(base, ast.Attribute) and _looks_like_choices_name(base.attr):
            return True
    # `choices=JobStatus` — bare Name (less common but valid)
    if isinstance(choices, ast.Name) and _looks_like_choices_name(choices.id):
        return True
    return False


def _looks_like_choices_name(name: str) -> bool:
    return any(name.endswith(suffix) for suffix in ("Choices", "Status", "State", "Phase"))


def _inside_model_class(path: list[ast.AST]) -> bool:
    """Return True when the current AST stack is inside a class that
    inherits from ``models.Model`` (directly or via an obvious alias).
    """
    for node in path:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                return True
            if isinstance(base, ast.Name) and base.id == "Model":
                return True
    return False


def _range_has_noqa(lines: list[str], start: int, end: int) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def check_source(src: str, filename: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(
            f"{filename}:{exc.lineno or 0}: stringly-status: syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []

    def visit(node: ast.AST, path: list[ast.AST]) -> None:
        if isinstance(node, ast.Assign):
            if _inside_model_class(path):
                _check_assignment(node, lines, hits)
        elif isinstance(node, ast.Compare):
            _check_compare(node, lines, hits)
        for child in ast.iter_child_nodes(node):
            visit(child, path + [node])

    visit(tree, [])
    return hits


def _state_attr_name(node: ast.AST) -> str | None:
    """Return the attr name when ``node`` is ``<anything>.status`` /
    ``.phase`` / ``.state``. Returns None otherwise."""
    if isinstance(node, ast.Attribute) and node.attr in STATE_FIELD_NAMES:
        return node.attr
    return None


def _string_literal_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_string_literal_container(node: ast.AST) -> bool:
    """True for ``("a", "b")`` / ``["a", "b"]`` / ``{"a", "b"}`` whose
    elements are all string literals. An empty container doesn't
    count (``in ()`` would always be False — a different smell)."""
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return False
    if not node.elts:
        return False
    return all(_string_literal_value(elt) is not None for elt in node.elts)


def _check_compare(
    node: ast.Compare,
    lines: list[str],
    hits: list[tuple[int, int, str]],
) -> None:
    # Only handle single-comparator expressions. Chained comparisons
    # (``a < b < c``) complicate attribution and aren't a natural
    # shape for state checks.
    if len(node.ops) != 1:
        return
    op = node.ops[0]
    left = node.left
    right = node.comparators[0]

    if isinstance(op, (ast.Eq, ast.NotEq)):
        # Try both operand orders — ``job.status == "pending"`` and
        # ``"pending" == job.status`` are equally smelly.
        attr = _state_attr_name(left)
        if attr and _string_literal_value(right) is not None:
            _emit_compare_hit(node, attr, lines, hits)
            return
        attr = _state_attr_name(right)
        if attr and _string_literal_value(left) is not None:
            _emit_compare_hit(node, attr, lines, hits)
        return

    if isinstance(op, (ast.In, ast.NotIn)):
        attr = _state_attr_name(left)
        if attr and _is_string_literal_container(right):
            _emit_compare_hit(node, attr, lines, hits)


def _emit_compare_hit(
    node: ast.Compare,
    attr: str,
    lines: list[str],
    hits: list[tuple[int, int, str]],
) -> None:
    end_line = getattr(node, "end_lineno", None) or node.lineno
    if _range_has_noqa(lines, node.lineno, end_line):
        return
    msg = (
        f"comparison on `.{attr}` uses a string literal — reference the "
        f"`TextChoices` enum member (e.g. `JobStatus.PENDING`) or mark "
        f"with `# noqa: stringly-status: <reason>`"
    )
    hits.append((node.lineno, node.col_offset, msg))


def _check_assignment(
    node: ast.Assign,
    lines: list[str],
    hits: list[tuple[int, int, str]],
) -> None:
    # Need a single Name target (the field name) and a Call value.
    if len(node.targets) != 1:
        return
    target = node.targets[0]
    if not isinstance(target, ast.Name):
        return
    if target.id not in STATE_FIELD_NAMES:
        return
    value = node.value
    if not isinstance(value, ast.Call):
        return
    if not _is_models_field_call(value, STATE_FIELD_CALLS):
        return
    if _has_textchoices_choices(value):
        return
    end_line = getattr(node, "end_lineno", None) or node.lineno
    if _range_has_noqa(lines, node.lineno, end_line):
        return
    msg = (
        f"field `{target.id}` is a string-typed state field without "
        f"`choices=<TextChoices>` — define a `models.TextChoices` enum "
        f"or mark with `# noqa: stringly-status: <reason>`"
    )
    hits.append((node.lineno, node.col_offset, msg))


def _check_path(path: str) -> tuple[int, bool]:
    try:
        src = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{path}: stringly-status: cannot read — {exc}", file=sys.stderr)
        return 0, True
    hits = check_source(src, path)
    for line, col, msg in hits:
        print(f"{path}:{line}:{col + 1}: stringly-status: {msg}")
    return len(hits), False


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: no_stringly_typed_status.py <file-or-dir> [...]  |  "
            "no_stringly_typed_status.py --stdin --filename=<name>",
            file=sys.stderr,
        )
        return 2

    if argv[0] == "--stdin":
        filename = "<stdin>"
        rest = argv[1:]
        for a in rest:
            if a.startswith("--filename="):
                filename = a.split("=", 1)[1]
                break
        src = sys.stdin.read()
        hits = check_source(src, filename)
        for line, col, msg in hits:
            print(f"{filename}:{line}:{col + 1}: stringly-status: {msg}")
        return 1 if hits else 0

    total_hits = 0
    had_io_error = False
    for path in expand_python_paths(argv):
        count, io_err = _check_path(path)
        total_hits += count
        had_io_error = had_io_error or io_err
    if had_io_error:
        return 2
    return 1 if total_hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
