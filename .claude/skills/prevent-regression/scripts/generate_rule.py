#!/usr/bin/env python3
"""Scaffold a new `scripts/lint/<rule>.py` from the silent-catch template.

The orchestrator calls this in Phase 2 after the rule-designer scout has
classified a pattern as "custom-ast". It produces a skeleton with the
right CLI contract, allow-list shape, and exit codes — but the AST match
logic is left as a `TODO` for the orchestrator to fill in based on
`pattern.md`.

Usage:

    python3 .claude/skills/prevent-regression/scripts/generate_rule.py \\
      --rule-name no-bare-int-request \\
      --intent "Flag bare int(request.POST.get(...)) — use safe_int instead." \\
      --output scripts/lint/no_bare_int_request.py

Stdlib-only — runs under bare `python3` without a populated .venv.

The generated file:

  * Uses snake_case of the rule name for the module.
  * Accepts `<file.py>...` positionals OR `--stdin --filename=<name>`.
  * Exits 0 on clean, 1 on violations, 2 on invocation error.
  * Supports `# noqa: <rule>: <reason>` with non-empty reason.

What you still have to write by hand:

  * The AST predicate — the `_matches()` body.
  * The violation message — what the developer sees.
  * The `_body_shape()` helper (or its equivalent) if the rule has
    multiple variants and the message should reflect which fired.

After generation, write the fixture pair and run
`verify_rule.py --rule scripts/lint/<name>.py --bad ... --good ...` to
confirm the rule catches the right variants.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEMPLATE = '''#!/usr/bin/env python3
"""{rule_name} lint rule.

{intent}

Allow-list: add ``# noqa: {rule_name}: <reason>`` on any line of the
matched span. The reason must be non-empty so the allow-list cannot be
spammed with a bare pragma.

Usage:

    scripts/lint/{module}.py <file.py> [<file.py> ...]
    scripts/lint/{module}.py --stdin --filename=<display-name>

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error (unreadable file, bad CLI)

Stdlib-only; safe to invoke under bare ``python3`` from a worktree that
does not yet have a populated ``.venv``.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

RULE = "{rule_name}"

# Reason must contain at least one non-whitespace character after the colon
# — a bare pragma would be trivially abusable.
NOQA_RE = re.compile(r"#\\s*noqa:\\s*" + re.escape(RULE) + r":\\s*\\S")


def _matches(node: ast.AST) -> bool:
    """Return True if *node* is an instance of the anti-pattern.

    TODO: fill in the predicate from ``pattern.md`` §AST shape.
    Example for silent-catch (do not copy verbatim — tailor to your
    rule)::

        if not isinstance(node, ast.ExceptHandler):
            return False
        t = node.type
        broad = t is None or (isinstance(t, ast.Name) and t.id in {{"Exception", "BaseException"}})
        return broad and _body_is_silent(node.body)
    """
    return False  # placeholder


def _span(node: ast.AST) -> tuple[int, int]:
    """Return (start_line, end_line) of the matched span for noqa lookup."""
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", None) or start
    return start, end


def _message(node: ast.AST) -> str:
    """Return the violation message shown to the developer.

    TODO: tailor. Keep it actionable — point at the canonical pattern
    and mention the allow-list shape.
    """
    return "anti-pattern detected — see `knowledge/`"


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
            f"{{filename}}:{{exc.lineno or 0}}: {{RULE}}: syntax error — {{exc.msg}}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not _matches(node):
            continue
        start, end = _span(node)
        if _range_has_noqa(lines, start, end):
            continue
        col = getattr(node, "col_offset", 0)
        hits.append((start, col, _message(node)))
    return hits


def _check_path(path: str) -> tuple[int, bool]:
    try:
        src = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{{path}}: {{RULE}}: cannot read — {{exc}}", file=sys.stderr)
        return 0, True
    hits = check_source(src, path)
    for line, col, msg in hits:
        print(f"{{path}}:{{line}}:{{col + 1}}: {{RULE}}: {{msg}}")
    return len(hits), False


def main(argv: list[str]) -> int:
    if not argv:
        print(
            f"usage: {{RULE}}.py <file.py> [...]  |  "
            f"{{RULE}}.py --stdin --filename=<name>",
            file=sys.stderr,
        )
        return 2

    if argv[0] == "--stdin":
        filename = "<stdin>"
        for a in argv[1:]:
            if a.startswith("--filename="):
                filename = a.split("=", 1)[1]
                break
        src = sys.stdin.read()
        hits = check_source(src, filename)
        for line, col, msg in hits:
            print(f"{{filename}}:{{line}}:{{col + 1}}: {{RULE}}: {{msg}}")
        return 1 if hits else 0

    total = 0
    had_io_error = False
    for path in argv:
        count, io_err = _check_path(path)
        total += count
        had_io_error = had_io_error or io_err
    if had_io_error:
        return 2
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


def _to_module_name(rule_name: str) -> str:
    """Convert `no-bare-int-request` → `no_bare_int_request`."""
    return rule_name.replace("-", "_")


def _validate_rule_name(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,23}", name):
        raise SystemExit(
            f"error: rule name {name!r} must be lowercase-kebab, ≤ 24 chars, "
            "starting with a letter."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule-name", required=True, help="e.g. no-bare-int-request")
    parser.add_argument(
        "--intent",
        required=True,
        help="One-sentence description of what the rule flags.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination path, e.g. scripts/lint/no_bare_int_request.py",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output if it exists (default: refuse).",
    )
    args = parser.parse_args()

    _validate_rule_name(args.rule_name)

    if args.output.exists() and not args.force:
        print(
            f"error: {args.output} already exists (use --force to overwrite)",
            file=sys.stderr,
        )
        return 1

    module = _to_module_name(args.rule_name)
    rendered = TEMPLATE.format(
        rule_name=args.rule_name,
        module=module,
        intent=args.intent.strip(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    args.output.chmod(0o755)
    print(f"wrote {args.output}")
    print(
        "next: fill in _matches() and _message(), write "
        f"tests/lint/{module}_{{bad,good}}.py, then run verify_rule.py."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
