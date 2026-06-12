#!/usr/bin/env python3
"""Seed a throwaway "mini-host" git repo that mirrors the guard infrastructure
a /prevent-regression run operates on.

This is Stage 1a scaffolding for the skill-comply conformance harness. It does
NOT touch the real repo tree — everything is built under a fresh
``tempfile.mkdtemp()`` directory (or an explicit ``--dest`` you control and are
willing to have clobbered).

What the seeded repo contains
-----------------------------

* The **target anti-pattern** — bare ``int(request.POST.get(...))`` /
  ``int(request.GET.get(...))`` parsing of user input without the canonical
  ``safe_int(...)`` helper — in two view files, plus a third view file
  (``app/views/reports.py``) holding **sibling syntactic forms** of the same
  bug (``self.request.POST.get(...)`` and an aliased receiver). The sibling
  file is the recall ground truth (C9): a rule that matches the plain form
  but misses the siblings is under-broad.
* A ``safe_int`` helper definition plus an already-correct ``safe_int(...)``
  call site, so a guard must not false-positive on the correct form, and must
  not flag ``int(x)`` on non-request values.
* A benign decoy file (``app/services/cart.py``) holding ``int(...)`` calls
  that are NOT the target anti-pattern — ``int(request.session.get(...))``
  (server-side state, not user POST/GET) and ``int(config.get(...))`` (a plain
  mapping). The narrow guard must leave both alone; an over-broad guard fires
  on them. This file is in ``app/`` (so it is in the rule's enforcement scope)
  but is NOT in ``antipattern_files`` — it is the ground truth the scorer's
  incidental-firing check (C8) uses to catch an over-broad rule.
* The guard plumbing a proposal wires into / the scorer checks:
  ``scripts/lint/run.py`` (same ``RuleSpec`` registry shape as the real repo),
  the shared ``scripts/lint/ast_lint.py`` + ``scripts/lint/path_utils.py``
  scaffold (so a rule placed under ``scripts/lint/`` resolves its sibling
  imports the way the real ``silent_catch.py`` does), a
  ``.pre-commit-config.yaml``, a ``.github/workflows/ci.yml``, a ``CLAUDE.md``
  with a "Canonical Patterns" section, and an empty ``tests/lint/`` package.
* A **2-commit history**: commit 1 introduces the anti-pattern across the view
  files; commit 2 (the "anchor") fixes exactly ONE of them to use
  ``safe_int``. The anchor lets the scorer do the historical-fire check via
  ``git show <anchor>^:<file>`` (pre-fix) vs ``git show HEAD:<file>`` (post-fix).

Output
------

Prints a single JSON object on stdout::

    {
      "repo": "/tmp/skill-comply-seed-XXXX",
      "anchor": "<sha of commit 2>",
      "antipattern_files": ["app/views/products.py", "app/views/checkout.py",
                            "app/views/reports.py"],
      "fixed_files": ["app/views/products.py"],
      "recall_files": ["app/views/reports.py"],
      "planted_instances": [{"id": "...", "file": "...", "line": N, "form": "..."}, ...],
      "rule_name": "no-bare-int-request"
    }

Stdlib-only. Idempotent per invocation (each run is a fresh mkdtemp unless
``--dest`` is given). Use ``--keep`` semantics by simply not deleting the dir
(this script never deletes; the caller owns cleanup).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_RULE_NAME = "no-bare-int-request"

# ---------------------------------------------------------------------------
# File bodies. Kept as module constants so a later stage can introspect them.
# ---------------------------------------------------------------------------

# Shared lint scaffold copied (essential structure only) from the real repo's
# scripts/lint/ast_lint.py + path_utils.py. A rule script dropped into
# scripts/lint/ imports these as siblings; Python puts the script's own dir on
# sys.path[0], so the import resolves regardless of cwd. Mirroring this is what
# makes the seeded repo a faithful target for a real guard proposal.

PATH_UTILS_PY = '''\
"""Shared path handling for project lint scripts (mini-host seed copy)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

PYTHON_SUFFIXES = (".py",)

SKIP_DIR_NAMES = {"migrations", ".venv", "node_modules", "__pycache__", "staticfiles"}


def should_skip_dir(dirname: str) -> bool:
    return dirname.startswith(".") or dirname in SKIP_DIR_NAMES


def expand_python_paths(paths: Iterable[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()

    def add(path) -> None:
        display = os.fspath(path)
        key = str(Path(display).resolve()) if Path(display).exists() else display
        if key in seen:
            return
        seen.add(key)
        expanded.append(display)

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames[:] = [d for d in sorted(dirnames) if not should_skip_dir(d)]
                for filename in sorted(filenames):
                    candidate = Path(dirpath) / filename
                    if candidate.suffix in PYTHON_SUFFIXES:
                        add(candidate)
            continue
        if path.exists() and path.suffix not in PYTHON_SUFFIXES:
            continue
        add(raw_path)
    return expanded
'''

AST_LINT_PY = '''\
"""Shared CLI/IO scaffold for line-oriented lint rules (mini-host seed copy).

Mirrors the real repo's scripts/lint/ast_lint.py contract: each rule supplies a
``check_source(src, filename) -> list[(line, col, msg)]`` with a 0-based column
(printed as col+1). The scaffold owns argv parsing, ``--stdin --filename=``
support, directory expansion, file reads, the ``path:line:col: rule: msg``
output line, and the 0/1/2 exit codes.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

from path_utils import expand_python_paths

Hit = tuple[int, int, str]
CheckSource = Callable[[str, str], list[Hit]]


def _print_hits(path: str, hits: list[Hit], rule_name: str) -> None:
    for line, col, msg in hits:
        print(f"{path}:{line}:{col + 1}: {rule_name}: {msg}")


def run_lint(
    argv: list[str],
    *,
    rule_name: str,
    check_source: CheckSource,
    expand: Callable[[Iterable[str]], Iterable[str]] = expand_python_paths,
    path_filter: Callable[[str], bool] | None = None,
    prog: str | None = None,
) -> int:
    prog = prog or Path(sys.argv[0]).name
    if not argv:
        print(
            f"usage: {prog} <file-or-dir> [...]  |  "
            f"{prog} --stdin --filename=<name>",
            file=sys.stderr,
        )
        return 2

    if argv[0] == "--stdin":
        filename = "<stdin>"
        for arg in argv[1:]:
            if arg.startswith("--filename="):
                filename = arg.split("=", 1)[1]
                break
        if path_filter is not None and not path_filter(filename):
            return 0
        hits = check_source(sys.stdin.read(), filename)
        _print_hits(filename, hits, rule_name)
        return 1 if hits else 0

    total = 0
    had_error = False
    for path in expand(argv):
        if path_filter is not None and not path_filter(path):
            continue
        try:
            src = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"{path}: {rule_name}: cannot read — {exc}", file=sys.stderr)
            had_error = True
            continue
        hits = check_source(src, path)
        _print_hits(path, hits, rule_name)
        total += len(hits)
    if had_error:
        return 2
    return 1 if total else 0
'''

# scripts/lint/run.py — same RuleSpec registry shape as the real repo, trimmed
# to the seed's needs. A guard proposal registers one RuleSpec here.
RUN_PY = '''\
#!/usr/bin/env python3
"""Run project-specific lint rules with one source of scope truth (seed)."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from path_utils import should_skip_dir


@dataclass(frozen=True)
class RuleSpec:
    name: str
    script: str
    include: "re.Pattern[str]"
    exclude: "re.Pattern[str] | None" = None
    suffixes: tuple = (".py",)


RULES: tuple = (
    # Baseline rule shipped with the seed so the registry is non-empty.
    RuleSpec(
        name="silent-catch",
        script="scripts/lint/silent_catch.py",
        include=re.compile(r"^app/(services|views|pages|api)/.*\\.py$"),
        exclude=re.compile(r"^tests/test_.*\\.py$"),
    ),
    # --- prevent-regression guard registers its RuleSpec below this line ---
)

RULE_BY_NAME = {rule.name: rule for rule in RULES}
RULE_CHOICES = ("all",) + tuple(rule.name for rule in RULES)


def selected_rules(rule_name: str) -> tuple:
    if rule_name == "all":
        return RULES
    return (RULE_BY_NAME[rule_name],)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", default="all", choices=RULE_CHOICES)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    repo_root = Path(".").resolve()
    exit_code = 0
    for rule in selected_rules(args.rule):
        scoped = [
            p for p in args.paths
            if rule.include.search(p) and not (rule.exclude and rule.exclude.search(p))
        ]
        if not scoped:
            continue
        result = subprocess.run([sys.executable, rule.script, *scoped], cwd=repo_root)
        if result.returncode:
            exit_code = max(exit_code, result.returncode)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
'''

# A real, conformant baseline guard so the seeded scripts/lint/ is not empty and
# the registry references a script that exists. Trimmed silent-catch.
SILENT_CATCH_PY = '''\
#!/usr/bin/env python3
"""Silent-catch lint rule (mini-host seed copy)."""
from __future__ import annotations

import ast
import re
import sys

from ast_lint import run_lint

BROAD_EXC_NAMES = {"Exception", "BaseException"}
NOQA_RE = re.compile(r"#\\s*noqa:\\s*(?:[A-Za-z0-9]+,\\s*)*silent-catch:\\s*\\S")


def _is_broad_except(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:
        return True
    return isinstance(t, ast.Name) and t.id in BROAD_EXC_NAMES


def _body_is_silent(body: list) -> bool:
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, (ast.Pass, ast.Continue)):
        return True
    if isinstance(stmt, ast.Return):
        if stmt.value is None:
            return True
        if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
            return True
    return False


def _range_has_noqa(lines: list, start: int, end: int) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def check_source(src: str, filename: str) -> list:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(f"{filename}:{exc.lineno or 0}: silent-catch: syntax error — {exc.msg}", file=sys.stderr)
        return []
    lines = src.splitlines()
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if not _is_broad_except(node):
            continue
        if not _body_is_silent(node.body):
            continue
        end_line = max((getattr(s, "end_lineno", None) or s.lineno) for s in node.body)
        if _range_has_noqa(lines, node.lineno, end_line):
            continue
        hits.append((node.lineno, node.col_offset, "except swallows failure — log or re-raise"))
    return hits


def main(argv: list) -> int:
    return run_lint(argv, rule_name="silent-catch", check_source=check_source)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

PARSING_PY = '''\
"""Canonical user-input parsing helpers (mini-host seed)."""
from __future__ import annotations


def safe_int(value, default: int = 0) -> int:
    """Coerce *value* to int, returning *default* on None / bad input.

    This is the canonical helper. Any parse of user-supplied request data
    must route through here instead of a bare ``int(request...get(...))``,
    which raises ``TypeError`` on a missing key and ``ValueError`` on junk.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
'''

# products.py — TWO bare int(request...) anti-patterns in commit 1; commit 2
# (anchor) rewrites this file to use safe_int. This is a "fixed file".
PRODUCTS_BAD = '''\
"""Product views (mini-host seed) — pre-fix: bare int(request...) parsing."""
from __future__ import annotations

from app.utils.parsing import safe_int  # noqa: F401  (kept for the good-form call below)


def list_products(request):
    # Anti-pattern: bare int() on POST user input, no safe_int.
    page = int(request.POST.get("page"))
    per_page = int(request.GET.get("per_page", "25"))
    return {"page": page, "per_page": per_page}


def product_detail(request, product_id):
    # Correct form already present — a guard must NOT flag this.
    qty = safe_int(request.GET.get("qty"), default=1)
    # Non-request int() — also must NOT be flagged.
    normalized = int(product_id)
    return {"qty": qty, "id": normalized}
'''

PRODUCTS_FIXED = '''\
"""Product views (mini-host seed) — post-fix: routes through safe_int."""
from __future__ import annotations

from app.utils.parsing import safe_int


def list_products(request):
    # Fixed: user input now parsed through the canonical helper.
    page = safe_int(request.POST.get("page"))
    per_page = safe_int(request.GET.get("per_page", "25"), default=25)
    return {"page": page, "per_page": per_page}


def product_detail(request, product_id):
    qty = safe_int(request.GET.get("qty"), default=1)
    normalized = int(product_id)
    return {"qty": qty, "id": normalized}
'''

# checkout.py — bare int(request...) anti-pattern; this file is NOT fixed by the
# anchor commit, so it stays dirty at HEAD. (It is the "follow-on finding" a
# real proposal would surface — and proves the guard fires on more than the one
# fixed file, but we only assert the historical-fire contract on fixed_files.)
CHECKOUT_BAD = '''\
"""Checkout views (mini-host seed) — bare int(request...) parsing (unfixed)."""
from __future__ import annotations


def apply_quantity(request):
    # Anti-pattern: bare int() on POST user input, no safe_int.
    quantity = int(request.POST.get("quantity"))
    return {"quantity": quantity}
'''

# reports.py — SIBLING FORMS of the anti-pattern, planted as recall ground
# truth (C9). Same bug — bare int() of user-supplied POST/GET data — expressed
# through receivers a narrowly-written matcher misses: ``self.request`` (the
# class-based-view form) and an aliased local. Present from commit 1, never
# fixed, so the instances are live at HEAD. A rule that matches the plain
# ``request.POST.get(...)`` form but not these siblings passes C3/C4/C8 and
# fails only C9. This file IS in ``antipattern_files`` (hits here are
# legitimate, so C8 allows them) and in ``recall_files`` (C9 requires hits).
REPORTS_PY = '''\
"""Reporting views (mini-host seed) — sibling-form anti-pattern instances (unfixed)."""
from __future__ import annotations


class ReportView:
    def current_page(self):
        # Sibling form 1: class-based-view receiver — self.request, not `request`.
        return int(self.request.POST.get("page"))


def export_rows(request):
    req = request
    # Sibling form 2: aliased receiver — same user input, different name.
    return int(req.GET.get("limit"))
'''

# cart.py — benign decoys for the incidental-firing check (C8). Neither call is
# the target anti-pattern (raw int() of user-supplied request POST/GET), so a
# correctly-scoped guard leaves them alone. An over-broad guard that fires on
# any int(...get(...)) wrongly flags them. This file is in the rule's scope
# (app/services/) but NOT in antipattern_files. It never changes across commits.
CART_PY = '''\
"""Cart service (mini-host seed) — benign int(...get(...)) a guard must NOT flag."""
from __future__ import annotations


def page_size_from_session(request) -> int:
    # request.session is server-side state, not user-supplied POST/GET input,
    # and the .get carries an int default — a correctly-scoped guard ignores it.
    return int(request.session.get("page_size", 20))


def retry_budget(config) -> int:
    # Plain mapping .get on a config dict — not request data at all.
    return int(config.get("retries", 3))
'''

PRE_COMMIT_YAML = '''\
# Pre-commit runs ONLY on staged files (diff-scoped enforcement). Mini-host seed.
minimum_pre_commit_version: "4.5.1"

repos:
  - repo: local
    hooks:
      - id: silent-catch
        name: "silent-catch (no bare except Exception: pass in views)"
        entry: python scripts/lint/run.py --rule silent-catch
        language: python
        types: [python]
        files: '^app/.*\\.py$'
      # --- prevent-regression guard adds its hook entry below this line ---
'''

CI_YAML = '''\
# Mini-host seed CI. The lint job is diff-scoped against the merge base.
name: ci
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: custom lint rules (diff-scoped)
        run: |
          BASE="origin/${{ github.base_ref || 'main' }}"
          python scripts/lint/run.py --changed-from "$BASE" --rule all
'''

CLAUDE_MD = '''\
# CLAUDE.md (mini-host seed)

Throwaway agent guide for the skill-comply seed repo. Mirrors only the bits a
/prevent-regression run touches.

## Python Environment

Lint scripts are stdlib-only and run under bare `python3`.

## Canonical Patterns

- **`safe_int` / `app/utils/parsing.py`** — coerce user input to int through
  the canonical helper; never `int(request.POST.get(...))` directly.
<!-- prevent-regression guard appends its canonical-pattern bullet below -->
'''

README_MD = '''\
# mini-host (skill-comply seed)

Throwaway fixture repo built by scripts/skill_comply/seed_fixture.py.
Do not edit by hand — re-seed instead.
'''


def _line_of(body: str, needle: str) -> int:
    """1-based line number of the first line containing *needle* in *body*.

    The seed bodies are module constants, so these line numbers are
    deterministic — they are the stable per-instance ground truth the
    ``planted_instances`` inventory (and the proposer-completeness oracle)
    keys on."""
    for idx, line in enumerate(body.splitlines(), start=1):
        if needle in line:
            return idx
    raise AssertionError(f"seed constant drifted: {needle!r} not found")


def _planted_instances() -> list[dict]:
    """Anti-pattern instances that are LIVE AT HEAD, with stable IDs.

    products.py instances are excluded: the anchor commit fixes them, so at
    HEAD they no longer exist. This list is the ground truth for the recall
    check (C9) and for oracle_proposer_completeness.py."""
    return [
        {
            "id": "checkout-post-quantity",
            "file": "app/views/checkout.py",
            "line": _line_of(CHECKOUT_BAD, 'int(request.POST.get("quantity"))'),
            "form": "plain-request",
        },
        {
            "id": "reports-self-request-page",
            "file": "app/views/reports.py",
            "line": _line_of(REPORTS_PY, 'int(self.request.POST.get("page"))'),
            "form": "self-request",
        },
        {
            "id": "reports-aliased-get-limit",
            "file": "app/views/reports.py",
            "line": _line_of(REPORTS_PY, 'int(req.GET.get("limit"))'),
            "form": "aliased-receiver",
        },
    ]


def _write(root: Path, rel: str, body: str) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Deterministic, hermetic identity so the seed never depends on global config.
    env.update(
        {
            "GIT_AUTHOR_NAME": "skill-comply-seed",
            "GIT_AUTHOR_EMAIL": "seed@skill-comply.invalid",
            "GIT_COMMITTER_NAME": "skill-comply-seed",
            "GIT_COMMITTER_EMAIL": "seed@skill-comply.invalid",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=check,
    )


def seed(dest: str | None = None, rule_name: str = DEFAULT_RULE_NAME) -> dict:
    """Build the seeded repo and return the manifest dict."""
    if dest is None:
        root = Path(tempfile.mkdtemp(prefix="skill-comply-seed-"))
    else:
        root = Path(dest)
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)

    # Static, anti-pattern-free plumbing (commit 1 includes these too).
    _write(root, "README.md", README_MD)
    _write(root, "CLAUDE.md", CLAUDE_MD)
    _write(root, ".pre-commit-config.yaml", PRE_COMMIT_YAML)
    _write(root, ".github/workflows/ci.yml", CI_YAML)
    _write(root, "scripts/lint/path_utils.py", PATH_UTILS_PY)
    _write(root, "scripts/lint/ast_lint.py", AST_LINT_PY)
    _write(root, "scripts/lint/run.py", RUN_PY)
    _write(root, "scripts/lint/silent_catch.py", SILENT_CATCH_PY)
    _write(root, "tests/lint/__init__.py", "")
    _write(root, "app/__init__.py", "")
    _write(root, "app/utils/__init__.py", "")
    _write(root, "app/utils/parsing.py", PARSING_PY)
    _write(root, "app/services/__init__.py", "")
    _write(root, "app/services/cart.py", CART_PY)
    _write(root, "app/views/__init__.py", "")

    # --- commit 1: introduce the anti-pattern across three view files ---
    _write(root, "app/views/products.py", PRODUCTS_BAD)
    _write(root, "app/views/checkout.py", CHECKOUT_BAD)
    _write(root, "app/views/reports.py", REPORTS_PY)

    _git(root, "init", "-q")
    _git(root, "checkout", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "Seed mini-host with bare int(request...) anti-pattern in views")

    # --- commit 2 (anchor): fix exactly ONE file to use safe_int ---
    _write(root, "app/views/products.py", PRODUCTS_FIXED)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "Route product views through safe_int (anchor fix)")

    anchor = _git(root, "rev-parse", "HEAD").stdout.strip()

    return {
        "repo": str(root),
        "anchor": anchor,
        "antipattern_files": [
            "app/views/products.py",
            "app/views/checkout.py",
            "app/views/reports.py",
        ],
        "fixed_files": ["app/views/products.py"],
        # Recall ground truth (C9): files holding sibling syntactic forms of the
        # anti-pattern, live at HEAD, that the rule MUST fire on.
        "recall_files": ["app/views/reports.py"],
        # Per-instance ground truth (stable IDs) for the proposer-completeness
        # oracle — anti-pattern instances live at HEAD.
        "planted_instances": _planted_instances(),
        "rule_name": rule_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        default=None,
        help="Explicit destination dir (CLOBBERED if it exists). Default: fresh mkdtemp.",
    )
    parser.add_argument(
        "--rule-name",
        default=DEFAULT_RULE_NAME,
        help=f"Rule name to embed in the manifest (default: {DEFAULT_RULE_NAME}).",
    )
    args = parser.parse_args()
    manifest = seed(dest=args.dest, rule_name=args.rule_name)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
