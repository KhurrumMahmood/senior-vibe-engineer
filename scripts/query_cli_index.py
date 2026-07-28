#!/usr/bin/env python3
"""Query-CLI index generator.

Emits `.claude/docs/query-cli-index.md` — the answer to "what can I *ask*
this repo?", one row per argparse subcommand under `scripts/`.

Why this exists: `scripts/` holds 42 top-level utilities, 22 of which
expose subcommands, and there is no entry point above them — no Makefile,
no justfile, no index. Nothing distinguishes the commands that answer a
question from the ones that rewrite a registry. So an agent that needs
"which subsystem owns this path?" has to *find* `subsystems.py for-path`
by grepping for a word it hopes the author also chose, and when the grep
misses it concludes the capability does not exist and rebuilds it.
Getting should be predictable; finding should not be the mechanism.

---------------------------------------------------------------------------
Four decisions, and why
---------------------------------------------------------------------------

1. INTROSPECTION — AST, not `--help`, not import.

   All three candidates were on the table:

   - **`--help` subprocess.** Rejected on two independent grounds. It
     executes every script's module level (111 processes here), and —
     fatally for a pre-commit hook — its output is not deterministic
     across machines. `scripts/subsystems.py:156` builds its help string
     as `f"Subsystem registry (default: {DEFAULT_REGISTRY})"`, and
     `DEFAULT_REGISTRY` is an **absolute path** derived from `__file__`.
     The generated file would differ between two checkouts and the hook
     would flap forever.
   - **Guarded import.** Setting `__name__ != "__main__"` skips `main()`
     but still executes module level. Same side-effect hazard, minus the
     subprocess cost. Not worth the risk for a doc generator.
   - **AST walk.** Executes nothing. Deterministic by construction,
     stdlib only, fast enough to run in a hook.

   The cost of AST is real and is stated rather than hidden: it sees only
   what is *literally written*. A subcommand registered in a loop, or a
   `help=` built by an f-string, is invisible or unlabelled. Every such
   case lands in a visible bucket (`(no help text)`, `Unclassified`)
   rather than being silently dropped. Nothing here calls a `main()`.

2. QUERY vs ACTION — read the code's write effects, don't trust the verb.

   The obvious mechanical signal is the subcommand's verb (`list`/`show`
   read, `init`/`prune` write). It is also wrong often enough to be
   dangerous in the one direction that matters: an agent running something
   it believed was read-only. This tree supplies the counterexample —
   `distribution_probe.py verify-matrix` is explicitly "read-only", while
   `skill_installer.py verify` and `sweep/__main__.py verify` both write.
   One verb, both answers.

   So the classifier is the *behaviour*. For each subcommand this resolves
   its handler and walks it for filesystem writes, following calls up to
   three hops and *across module boundaries*. The cross-module hop is not
   optional here: `agent_policy/grant.py` does all of its writing through
   `save_grants`, imported from `agent_policy/grants.py` (grant.py:17,29),
   so a same-module-only scan called `grant`, `revoke`, `clear`, and
   `prune` safe. Writes reached only inside an `if` testing an `args.*`
   flag are reported as flag-gated with the flag named.

   The verb lexicon survives, but only as a one-way safety promotion: it
   can move a subcommand *into* the action table, never out of it. Both
   signals under-report in the same direction (the scan cannot see a
   dynamic or third-party writer; a verb is only a name), so the rule is
   monotone toward the answer that is safe to be wrong about. An
   unresolvable handler with an unrecognised verb stays Unclassified and
   is labelled treat-as-action; three subcommands sit there today.

   The write-primitive set was tuned against this tree by measurement, not
   taste. Counting `.replace` as a path write (rather than `str.replace`)
   moved 12 genuine queries into the action table; counting `subprocess.*`
   as a write moved another 4, because subprocess here is overwhelmingly
   read-only `git` plumbing. An action table full of `list` and `show` is
   one nobody believes, so both were excluded.

   Explicitly rejected: a declared `# query:` / `# action:` marker in each
   script. That is 57 file edits to buy a fact the code already states,
   and it decays the moment someone adds a write to an existing handler —
   which the AST scan notices and a comment does not.

3. SCOPE — all of `scripts/`, recursively, minus fixtures.

   One recursive root rather than a declared list: this tree has no domain
   sub-toolkit worth carving out (`_lib/` holds 28 modules and exposes no
   CLI at all, so including it costs nothing), and a recursive root keeps
   a new `scripts/` package indexed the day it lands.

   Excluded, each with a reason and a pointer rather than a silent
   omission — silence in a catalog reads as "nothing exists", which is the
   failure this file was built to stop:

   - `.claude/skills/*/scripts/` — 109 skill-private helpers. They are the
     private implementation of the SKILL.md that invokes them;
     `skill-catalog.md` and `/which-skill` are already the router, and
     `find-skill-artifact-drift` already gates SKILL.md -> script
     existence. 109 near-identically-named `detect.py` / `report.py` rows
     would be noise, not signal.
   - `scripts/skill_comply/fixtures/` — deliberately defective sample
     projects kept as test input, excluded from ruff for the same reason
     (`pyproject.toml` `extend-exclude`). Indexing them would advertise
     commands that are meant to fail.

4. THE UNIT — the subcommand, and the flat script as one row.

   A subcommand is the smallest thing you can actually invoke, and its
   `help=` is an annotation the source already carries. Scripts with an
   argparse CLI but no subparsers get one row each (docstring summary),
   because leaving them out would make this index the next source of
   false-absence claims.

Usage:
  .venv/bin/python scripts/query_cli_index.py
  .venv/bin/python scripts/query_cli_index.py --check   # CI/pre-commit

Stdlib only, deterministic, executes nothing. Writes exactly one file (or,
with --check, none).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

OUT_PATH = Path(".claude/docs/query-cli-index.md")

# One recursive root. This tree has no domain sub-toolkit worth carving
# out — `_lib/` holds 23 modules and exposes no CLI at all, so including
# it costs nothing — and a recursive root keeps a new `scripts/` package
# indexed the day it lands instead of the day someone remembers.
ROOT = "scripts"

# Named in the rendered header so the exclusions are a visible decision,
# not a gap.
EXCLUDED = (
    (".claude/skills/*/scripts/",
     "109 skill-private helpers, invoked by the SKILL.md that owns them; "
     "`skill-catalog.md` and `/which-skill` are the router, and "
     "`find-skill-artifact-drift` already gates SKILL.md -> script existence"),
    ("scripts/skill_comply/fixtures/",
     "deliberately defective sample projects, excluded from ruff for the "
     "same reason"),
)

# `fixtures` holds the skill_comply sample projects: intentionally broken
# code kept as test input. Indexing them would advertise commands that are
# meant to fail.
SKIP_DIRS = frozenset({"__pycache__", "node_modules", "fixtures"})

# Filesystem effects. Every name here was checked against this tree for
# collisions with a same-named method on a non-path object, because a
# false positive is not a harmless over-warning — it pushes a genuine
# query into the action table, and an action table full of `list` and
# `show` is one nobody believes.
#
# Excluded after measuring, each for a specific collision:
#   `.replace`   — `str.replace`. Was the single largest false positive
#                  here: it put `decisions.py list`, `plans.py show`, and
#                  `skill_meta.py lint` in the action table via one call
#                  inside the shared frontmatter parser.
#   `.remove`    — `list.remove`. Kept only as `os.remove` below.
#   `.write`     — `sys.stdout.write`.
#   subprocess.* — in this tree subprocess is overwhelmingly read-only git
#                  plumbing (`git grep`, `git log`); treating it as a write
#                  mislabels every history-reading query as an action.
WRITE_METHODS = frozenset({
    "write_text", "write_bytes", "writelines", "mkdir", "makedirs", "touch",
    "unlink", "rmtree", "rename", "copyfile", "copy2", "copytree",
    "symlink_to", "hardlink_to", "chmod",
})
# `module.attr` shapes whose bare method name is too common to match alone.
WRITE_QUALIFIED = frozenset({
    ("os", "remove"), ("os", "rmdir"), ("os", "replace"), ("os", "removedirs"),
    ("shutil", "move"), ("shutil", "copy"), ("shutil", "rmtree"),
})

# Fallback only — consulted when the handler cannot be resolved (decision
# 2). Kept small on purpose; the residue is meant to be visible.
QUERY_VERBS = frozenset({
    "list", "show", "check", "audit", "validate", "lint", "report", "status",
    "summary", "summarize", "coverage", "history", "verify", "diff", "find",
    "get", "print", "describe", "inspect", "count", "for", "search",
})
ACTION_VERBS = frozenset({
    "init", "add", "append", "update", "rebuild", "promote", "create",
    "delete", "remove", "clear", "prune", "apply", "install", "uninstall",
    "set", "write", "record", "import", "export", "run", "build", "generate",
    "sync", "migrate", "revoke", "grant", "withdraw", "renew", "collect",
})

# How far to follow calls out of a handler. Three hops covers the shape
# this tree actually uses — `cmd_grant -> add_grant -> save_grants ->
# write_text` crosses two module boundaries. Deeper reaches generic
# helpers whose writes say nothing about the subcommand.
MAX_DEPTH = 3

# Keyword names this tree binds a subcommand handler under. Both are in
# live use: the registry scripts (`decisions.py`, `plans.py`, `specs.py`)
# use `func=`, while `sweep/__main__.py` binds all eight of its
# subcommands with `handler=`. Matching only `func=` left every sweep
# subcommand unresolved.
HANDLER_KWARGS = ("func", "handler")

WHITESPACE_RE = re.compile(r"\s+")
MAX_HELP = 130


# --------------------------------------------------------------------------- #
# Source collection                                                           #
# --------------------------------------------------------------------------- #

def iter_script_paths(project_root: Path) -> list[Path]:
    """Every in-scope `.py`, sorted for determinism.

    A missing root raises rather than yielding an empty index: a scan root
    that silently disappears turns this file into a confident claim that
    nothing exists, which is the exact failure it was built to prevent.
    """
    base = project_root / ROOT
    if not base.is_dir():
        raise FileNotFoundError(
            f"declared scan root not found: {base}. Update ROOT in "
            "scripts/query_cli_index.py rather than skipping it."
        )
    keep: list[Path] = []
    for path in base.rglob("*.py"):
        if SKIP_DIRS.intersection(path.relative_to(project_root).parts):
            continue
        keep.append(path)
    return sorted(set(keep))


def parse(path: Path) -> ast.Module | None:
    """Parse, or None if the file will not compile.

    A syntax error is that file's problem; skipping keeps the index
    generable on a broken tree instead of blocking every commit behind an
    unrelated defect.
    """
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return None


def _one_line(text: str) -> str:
    """Collapse to a single table-safe cell, truncated on a word boundary."""
    collapsed = WHITESPACE_RE.sub(" ", text).strip()
    if len(collapsed) > MAX_HELP:
        collapsed = collapsed[:MAX_HELP].rsplit(" ", 1)[0] + "…"
    return collapsed.replace("|", "\\|")


def summary_sentence(tree: ast.Module) -> str:
    """The module docstring's first paragraph, collapsed to one line."""
    docstring = ast.get_docstring(tree)
    if not docstring:
        return ""
    paragraph: list[str] = []
    for line in docstring.strip().splitlines():
        if not line.strip():
            break
        paragraph.append(line.strip())
    return _one_line(" ".join(paragraph))


# --------------------------------------------------------------------------- #
# Subcommand extraction                                                       #
# --------------------------------------------------------------------------- #

def _literal(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def subcommands(tree: ast.Module) -> list[tuple[str, str, int, str | None]]:
    """`(name, help, lineno, assigned_var)` per literal `add_parser(...)`.

    Declaration order is preserved — it is what `--help` shows, and it is
    deterministic from the AST without any sorting choice of ours.
    """
    assigned: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned[id(node.value)] = target.id

    found: list[tuple[str, str, int, str | None]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "add_parser" or not node.args:
            continue
        name = _literal(node.args[0])
        if name is None:
            continue  # dynamically named — invisible to AST by construction
        help_text = _literal(_kwarg(node, "help")) or ""
        found.append((name, help_text, node.lineno, assigned.get(id(node))))
    found.sort(key=lambda row: row[2])
    return found


def _handler_by_set_defaults(tree: ast.Module) -> list[tuple[str, int, str]]:
    """`(var, lineno, func_name)` per handler-binding `X.set_defaults(...)`.

    Only the keywords in `HANDLER_KWARGS` count — `set_defaults` is also
    used to seed plain option defaults (`scan.set_defaults(dirty=None)`),
    and treating those as handler bindings would name a constant as the
    function to scan.
    """
    out: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "set_defaults" or not isinstance(node.func.value, ast.Name):
            continue
        for keyword in HANDLER_KWARGS:
            target = _kwarg(node, keyword)
            if isinstance(target, ast.Name):
                out.append((node.func.value.id, node.lineno, target.id))
                break
    return out


def _handler_by_dispatch(tree: ast.Module) -> dict[str, list[ast.stmt]]:
    """`{subcommand: branch body}` from `if args.cmd == "x": ...`.

    The second of the two dispatch styles here. The whole branch is the
    scan unit rather than "the first same-module call in it", because the
    branch is not always a one-line delegation — `agent_policy/friction.py`
    inlines its `report` body, and picking one call out of it would be
    reading an arbitrary statement as the handler.
    """
    out: dict[str, list[ast.stmt]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        names = [
            _literal(operand)
            for operand in [node.test.left, *node.test.comparators]
            if _literal(operand) is not None
        ]
        if len(names) == 1 and node.body:
            out.setdefault(names[0], node.body)
    return out


def resolve_handlers(
    tree: ast.Module, subs: list[tuple[str, str, int, str | None]]
) -> dict[str, str | list[ast.stmt]]:
    """Map each subcommand to its handler function name or branch body."""
    handlers: dict[str, str | list[ast.stmt]] = dict(_handler_by_dispatch(tree))
    defaults = _handler_by_set_defaults(tree)
    for name, _help, lineno, var in subs:
        if var is None:
            continue
        # The nearest `set_defaults` below this `add_parser` on the same
        # variable. Variables are reused (`p = sub.add_parser(...)` in a
        # row), so proximity below is the binding, not name alone.
        best: tuple[int, str] | None = None
        for dvar, dline, func in defaults:
            if dvar == var and dline > lineno and (best is None or dline < best[0]):
                best = (dline, func)
        if best is not None:
            handlers[name] = best[1]
    return handlers


# --------------------------------------------------------------------------- #
# Write-effect analysis                                                       #
# --------------------------------------------------------------------------- #

def _args_flags(test: ast.expr) -> frozenset[str]:
    """`args.apply` / `not args.apply` -> {"apply"} — the gating flag names."""
    flags: set[str] = set()
    for node in ast.walk(test):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "args":
                flags.add(node.attr)
    return frozenset(flags)


def _is_write_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr in WRITE_METHODS:
            return True
        base = func.value
        return isinstance(base, ast.Name) and (base.id, func.attr) in WRITE_QUALIFIED
    if isinstance(func, ast.Name) and func.id == "open":
        mode = node.args[1] if len(node.args) > 1 else _kwarg(node, "mode")
        literal = _literal(mode) or ""
        return any(ch in literal for ch in "wax+")
    return False


class ModuleIndex:
    """Lazy `module key -> (functions, import bindings)` over the repo tree.

    Handlers delegate the actual write across module boundaries far more
    often than not. `agent_policy/grant.py` is the measured case here: it
    does all four of its mutations through `save_grants`, `add_grant`,
    `revoke_grant`, and `prune_expired` imported from
    `agent_policy/grants.py` (grant.py:17,29), and with call-following
    disabled every one of `grant`, `revoke`, `clear`, and `prune` reports
    as non-writing. That is the *dangerous* direction of error — an agent
    reads "safe" and runs a mutation — so calls are followed one repo
    module at a time, resolved from each file's own import statements.

    Only in-repo modules resolve. `shutil`/`subprocess`/`yaml` find no file
    and stop the walk, which is correct — the write primitives that matter
    from those are matched directly by `_is_write_call`.
    """

    def __init__(self, project_root: Path):
        self.root = project_root
        self._cache: dict[str, tuple[dict[str, ast.FunctionDef], dict, dict] | None] = {}

    def _module_file(self, dotted: str) -> Path | None:
        parts = dotted.split(".")
        for base in (self.root, self.root / "scripts"):
            for candidate in (base.joinpath(*parts).with_suffix(".py"),
                              base.joinpath(*parts) / "__init__.py"):
                if candidate.is_file():
                    return candidate
        return None

    def load(self, dotted: str):
        """`(functions, {name: (module, func)}, {alias: module})`, or None."""
        if dotted in self._cache:
            return self._cache[dotted]
        path = self._module_file(dotted)
        tree = parse(path) if path is not None else None
        if tree is None:
            self._cache[dotted] = None
            return None
        self._cache[dotted] = (
            {
                node.name: node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            },
            *import_bindings(tree, dotted),
        )
        return self._cache[dotted]


def import_bindings(tree: ast.Module, self_dotted: str) -> tuple[dict, dict]:
    """`({bound name: (module, attr)}, {alias: module})` for one module.

    `ast.walk` rather than a top-level pass on purpose: eight modules here
    import inside a function body to isolate a heavy or circular dependency
    — `agent_policy/friction.py:138` reaches for `agent_policy.grants`,
    `queue_status.py:125` for `sweep.schemas` — and a top-level-only pass
    would drop exactly those edges.
    """
    package = self_dotted.rsplit(".", 1)[0] if "." in self_dotted else ""
    from_names: dict[str, tuple[str, str]] = {}
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                trimmed = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join([*trimmed, node.module] if node.module else trimmed)
            else:
                base = node.module or ""
            if not base:
                continue
            for alias in node.names:
                from_names[alias.asname or alias.name] = (base, alias.name)
                aliases.setdefault(alias.asname or alias.name, f"{base}.{alias.name}")
    return from_names, aliases


class _WriteScan:
    """Accumulates (ungated, gated-by) write findings under one handler."""

    def __init__(self, index: ModuleIndex):
        self.index = index
        self.ungated = False
        self.gates: set[str] = set()
        self.seen: set[tuple[str, str]] = set()

    def _callee(self, node: ast.Call, module: str) -> tuple[str, str] | None:
        loaded = self.index.load(module)
        if loaded is None:
            return None
        funcs, from_names, aliases = loaded
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in funcs:
                return module, func.id
            if func.id in from_names:
                return from_names[func.id]
            return None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            target = aliases.get(func.value.id)
            if target:
                return target, func.attr
        return None

    def visit(self, node: ast.AST, gates: frozenset[str], module: str, depth: int) -> None:
        if isinstance(node, ast.If):
            deeper = gates | _args_flags(node.test)
            for stmt in node.body:
                self.visit(stmt, deeper, module, depth)
            for stmt in node.orelse:
                self.visit(stmt, gates, module, depth)
            return
        if isinstance(node, ast.Call):
            if _is_write_call(node):
                if gates:
                    self.gates |= set(gates)
                else:
                    self.ungated = True
            if depth < MAX_DEPTH:
                callee = self._callee(node, module)
                if callee is not None and callee not in self.seen:
                    self.seen.add(callee)
                    self.enter(callee[0], callee[1], gates, depth + 1)
        for child in ast.iter_child_nodes(node):
            self.visit(child, gates, module, depth)

    def enter(self, module: str, func_name: str, gates: frozenset[str], depth: int) -> bool:
        loaded = self.index.load(module)
        if loaded is None:
            return False
        target = loaded[0].get(func_name)
        if target is None:
            return False
        for stmt in target.body:
            self.visit(stmt, gates, module, depth)
        return True


def write_effect(
    index: ModuleIndex, module: str, handler: str | list[ast.stmt] | None
) -> tuple[str, list[str]]:
    """`("yes"|"flag-gated"|"no"|"?", [flag names])` for one handler."""
    if handler is None:
        return "?", []
    scan = _WriteScan(index)
    if isinstance(handler, str):
        scan.seen.add((module, handler))
        if not scan.enter(module, handler, frozenset(), 0):
            return "?", []
    else:
        for stmt in handler:
            scan.visit(stmt, frozenset(), module, 0)
    if scan.ungated:
        return "yes", []
    if scan.gates:
        return "flag-gated", sorted(scan.gates)
    return "no", []


# --------------------------------------------------------------------------- #
# Classification                                                              #
# --------------------------------------------------------------------------- #

def classify(name: str, effect: str) -> str:
    """`query` | `action` | `unclassified` for one subcommand.

    Behaviour leads; the verb lexicon can only ever *promote* toward
    action, never demote toward query. Both signals are incomplete in the
    same direction — the write scan cannot see a dynamic or third-party
    writer, and a verb is only a name — so the rule is monotone toward the
    safe answer: a subcommand is a query only when the scan found no
    ungated write **and** its verb is not an action verb. An unresolvable
    handler with an unrecognised verb stays `unclassified` rather than
    being guessed into `query`.
    """
    verb = name.split("-")[0].lower()
    if effect == "yes" or verb in ACTION_VERBS:
        return "action"
    if effect in ("no", "flag-gated"):
        return "query"
    return "query" if verb in QUERY_VERBS else "unclassified"


# --------------------------------------------------------------------------- #
# Collection                                                                  #
# --------------------------------------------------------------------------- #

def collect(project_root: Path) -> tuple[dict[str, list[str]], list[str], int]:
    """Return (`{bucket: rows}`, single-command rows, scanned file count)."""
    buckets: dict[str, list[str]] = {"query": [], "action": [], "unclassified": []}
    singles: list[str] = []
    scanned = 0
    index = ModuleIndex(project_root)

    for path in iter_script_paths(project_root):
        tree = parse(path)
        if tree is None:
            continue
        scanned += 1
        rel = path.relative_to(project_root).as_posix()
        subs = subcommands(tree)
        if not subs:
            has_cli = any(
                isinstance(node, ast.Call)
                and (getattr(node.func, "attr", "") == "ArgumentParser"
                     or getattr(node.func, "id", "") == "ArgumentParser")
                for node in ast.walk(tree)
            )
            if has_cli:
                singles.append(f"| `{rel}` | {summary_sentence(tree) or '(no docstring)'} |")
            continue

        module_key = rel[: -len(".py")].replace("/", ".")
        module_key = module_key[len("scripts."):] if module_key.startswith("scripts.") else module_key
        handlers = resolve_handlers(tree, subs)
        for name, help_text, _lineno, _var in subs:
            effect, flags = write_effect(index, module_key, handlers.get(name))
            bucket = classify(name, effect)
            if effect == "flag-gated":
                mutates = "only with " + ", ".join(f"`--{f.replace('_', '-')}`" for f in flags)
            elif effect == "yes":
                mutates = "yes"
            elif effect == "no":
                mutates = "no"
            else:
                mutates = "unknown"
            cell = _one_line(help_text) if help_text else "(no help text)"
            buckets[bucket].append(f"| `{rel} {name}` | {cell} | {mutates} |")

    return buckets, singles, scanned


# --------------------------------------------------------------------------- #
# Render                                                                      #
# --------------------------------------------------------------------------- #

def render(buckets: dict[str, list[str]], singles: list[str], scanned: int) -> str:
    total = sum(len(rows) for rows in buckets.values())
    lines = [
        "<!-- GENERATED by scripts/query_cli_index.py — do not edit by hand. -->",
        "",
        "# Query-CLI index",
        "",
        "What you can *ask* this repo. One row per argparse subcommand under",
        "`scripts/`, derived by AST introspection — no script is imported or",
        "executed to build this file.",
        "",
        "Reach for this before writing a one-off scan, and before concluding",
        "that no command answers a question: `scripts/` has no entry point,",
        "no task runner, and no other index, so the alternative is grepping",
        "for a word and hoping the author picked the same one.",
        "",
        "`Mutates` is read out of each subcommand's handler — filesystem",
        "writes, followed up to three calls deep and across module",
        "boundaries — not guessed from its name: `verify-matrix` is",
        "read-only while `skill_installer.py verify` writes. `only with",
        "--flag` means the write is reachable only inside a branch testing",
        "that flag, so the bare form is safe to run. A subcommand whose",
        "verb says action is filed as one even when no write was found, so",
        "this errs toward warning rather than toward reassurance.",
        "",
        f"{total} subcommands across {scanned} scanned files, plus",
        f"{len(singles)} single-command scripts.",
        "",
        "Out of scope, deliberately — each already has a lookup surface:",
        "",
    ]
    lines += [f"- `{path}` — {why}" for path, why in EXCLUDED]
    lines += [
        "",
        "Regenerate with `.venv/bin/python scripts/query_cli_index.py`.",
        "",
    ]

    sections = (
        ("Query subcommands", "query",
         "Safe to run to answer a question. Nothing here writes unless the "
         "named flag is passed."),
        ("Action subcommands", "action",
         "These write. Read the help text before running one."),
        ("Unclassified subcommands", "unclassified",
         "The handler could not be resolved from the AST and the verb is not "
         "in the fallback lexicon. **Treat as an action** until classified — "
         "a `set_defaults(func=...)` or `set_defaults(handler=...)` binding, "
         "or a recognised verb, moves the row into a real section."),
    )
    for title, key, blurb in sections:
        rows = buckets[key]
        lines += [f"## {title} — {len(rows)}", "", blurb, ""]
        if rows:
            lines += ["| Command | Answers | Mutates |", "|---|---|---|", *sorted(rows), ""]
        else:
            lines += ["None.", ""]

    lines += [
        f"## Single-command scripts — {len(singles)}",
        "",
        "An argparse CLI with no subcommands. Listed by their own docstring",
        "summary so this index is not itself a source of false absence.",
        "",
    ]
    if singles:
        lines += ["| Script | Does |", "|---|---|", *sorted(singles), ""]
    else:
        lines += ["None.", ""]
    return "\n".join(lines)


def build(project_root: Path) -> str:
    """The whole artifact as a string — the unit the tests and --check share."""
    buckets, singles, scanned = collect(project_root)
    return render(buckets, singles, scanned)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate .claude/docs/query-cli-index.md")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the committed file is stale; never write.",
    )
    args = parser.parse_args()

    project_root = args.root.resolve()
    content = build(project_root)
    out = project_root / OUT_PATH

    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != content:
            print(
                f"{OUT_PATH} is stale. Run:\n"
                "  .venv/bin/python scripts/query_cli_index.py",
                file=sys.stderr,
            )
            return 1
        print(f"{OUT_PATH} is current")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
