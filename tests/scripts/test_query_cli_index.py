"""Tests for `scripts/query_cli_index.py`.

Covers: AST subcommand extraction under the supported binding conventions,
the write-effect classifier (including the cross-module hop),
the monotone verb-promotion rule, byte-for-byte determinism, and the
freshness assertion the `query-cli-index-current` pre-commit hook makes.

The hermetic cases build a miniature `scripts/` tree rather than asserting
against today's real one, so they pin behaviour instead of contents. The
determinism and freshness cases deliberately run against the real tree —
that is the whole point of the artifact being checked in.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "query_cli_index.py"


def _load_module():
    """Import the generator by path; `scripts/` is not a package."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("query_cli_index", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(REPO_ROOT / "scripts"))


qci = _load_module()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def tree_root(tmp_path: Path) -> Path:
    """A miniature project whose only scan root is `scripts/`."""
    (tmp_path / "scripts").mkdir(parents=True)
    return tmp_path


# --------------------------------------------------------------------------- #
# Subcommand extraction                                                       #
# --------------------------------------------------------------------------- #

def _subs(source: str):
    return qci.subcommands(ast.parse(source))


def test_literal_name_and_help_are_captured():
    subs = _subs('sub.add_parser("for-path", help="Who owns this path?")\n')
    assert [(s[0], s[1]) for s in subs] == [("for-path", "Who owns this path?")]


def test_declaration_order_is_preserved():
    subs = _subs('sub.add_parser("show")\nsub.add_parser("audit")\nsub.add_parser("init")\n')
    assert [s[0] for s in subs] == ["show", "audit", "init"]


def test_dynamically_named_subcommand_is_skipped_not_guessed():
    assert _subs("sub.add_parser(name)\n") == []


def test_assigned_variable_is_recorded_for_handler_binding():
    assert _subs('p = sub.add_parser("list")\n')[0][3] == "p"


# --------------------------------------------------------------------------- #
# Handler resolution                                                          #
# --------------------------------------------------------------------------- #

def _resolve(source: str):
    tree = ast.parse(source)
    return qci.resolve_handlers(tree, qci.subcommands(tree))


def test_set_defaults_func_binds_to_the_nearest_add_parser_above_it():
    handlers = _resolve(
        'p = sub.add_parser("a")\n'
        "p.set_defaults(func=cmd_a)\n"
        'p = sub.add_parser("b")\n'
        "p.set_defaults(func=cmd_b)\n"
    )
    assert handlers["a"] == "cmd_a"
    assert handlers["b"] == "cmd_b"


def test_set_defaults_handler_is_also_a_binding():
    """Portable consumers may use `handler=` instead of `func=`."""
    handlers = _resolve('p = sub.add_parser("scan")\np.set_defaults(handler=_scan)\n')
    assert handlers["scan"] == "_scan"


def test_non_handler_set_defaults_is_not_mistaken_for_a_binding():
    """`scan.set_defaults(dirty=None)` seeds an option default, not a handler."""
    handlers = _resolve('p = sub.add_parser("scan")\np.set_defaults(dirty=None)\n')
    assert "scan" not in handlers


def test_if_dispatch_yields_the_whole_branch_body():
    handlers = _resolve(
        'sub.add_parser("a")\nif args.cmd == "a":\n    do_one()\n    do_two()\n'
    )
    assert len(handlers["a"]) == 2


def test_membership_dispatch_binds_each_literal_to_the_branch_body():
    handlers = _resolve(
        'sub.add_parser("status")\n'
        'sub.add_parser("plan")\n'
        'if args.command in {"status", "plan"}:\n    inspect_state()\n'
    )
    assert set(handlers) == {"status", "plan"}


def test_unbound_subcommand_is_absent_rather_than_defaulted():
    assert "a" not in _resolve('sub.add_parser("a")\n')


# --------------------------------------------------------------------------- #
# Write-effect analysis                                                       #
# --------------------------------------------------------------------------- #

def _effect(root: Path, name: str):
    index = qci.ModuleIndex(root)
    tree = ast.parse((root / f"scripts/{name}.py").read_text(encoding="utf-8"))
    handlers = qci.resolve_handlers(tree, qci.subcommands(tree))
    return {
        sub[0]: qci.write_effect(index, name, handlers.get(sub[0]))
        for sub in qci.subcommands(tree)
    }


def test_read_only_handler_is_no(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           'p = sub.add_parser("peek")\n'
           "p.set_defaults(func=cmd_peek)\n"
           "def cmd_peek(args):\n    print(args.path)\n")
    assert _effect(tree_root, "tool")["peek"] == ("no", [])


def test_direct_write_is_yes(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           'p = sub.add_parser("emit")\n'
           "p.set_defaults(func=cmd_emit)\n"
           "def cmd_emit(args):\n    args.out.write_text('x')\n")
    assert _effect(tree_root, "tool")["emit"] == ("yes", [])


def test_write_behind_an_args_flag_is_flag_gated_and_names_the_flag(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           'p = sub.add_parser("verify")\n'
           "p.set_defaults(func=cmd_verify)\n"
           "def cmd_verify(args):\n"
           "    if args.apply:\n"
           "        args.out.write_text('x')\n")
    assert _effect(tree_root, "tool")["verify"] == ("flag-gated", ["apply"])


def test_write_in_an_imported_module_is_still_found(tree_root: Path):
    """The regression that matters: `grant.py` writes via `grants.py`."""
    _write(tree_root / "scripts/store.py", "def save(x):\n    x.write_text('y')\n")
    _write(tree_root / "scripts/tool.py",
           "from store import save\n"
           'p = sub.add_parser("keep")\n'
           "p.set_defaults(func=cmd_keep)\n"
           "def cmd_keep(args):\n    save(args.out)\n")
    assert _effect(tree_root, "tool")["keep"] == ("yes", [])


def test_aliased_module_attribute_write_is_found(tree_root: Path):
    _write(tree_root / "scripts/store.py", "def save(x):\n    x.write_text('y')\n")
    _write(tree_root / "scripts/tool.py",
           "import store as st\n"
           'p = sub.add_parser("keep")\n'
           "p.set_defaults(func=cmd_keep)\n"
           "def cmd_keep(args):\n    st.save(args.out)\n")
    assert _effect(tree_root, "tool")["keep"] == ("yes", [])


def test_str_replace_is_not_mistaken_for_a_path_replace(tree_root: Path):
    """Counting `.replace` moved 12 real queries into the action table."""
    _write(tree_root / "scripts/tool.py",
           'p = sub.add_parser("peek")\n'
           "p.set_defaults(func=cmd_peek)\n"
           "def cmd_peek(args):\n    return args.text.replace('a', 'b')\n")
    assert _effect(tree_root, "tool")["peek"] == ("no", [])


def test_subprocess_is_not_a_write(tree_root: Path):
    """`git grep` / `git log` are reads; counting them moved 4 more."""
    _write(tree_root / "scripts/tool.py",
           "import subprocess\n"
           'p = sub.add_parser("peek")\n'
           "p.set_defaults(func=cmd_peek)\n"
           "def cmd_peek(args):\n    subprocess.run(['git', 'log'])\n")
    assert _effect(tree_root, "tool")["peek"] == ("no", [])


def test_open_for_reading_is_not_a_write(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           'p = sub.add_parser("peek")\n'
           "p.set_defaults(func=cmd_peek)\n"
           "def cmd_peek(args):\n    open(args.path, encoding='utf-8')\n")
    assert _effect(tree_root, "tool")["peek"] == ("no", [])


def test_open_for_writing_is_a_write(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           'p = sub.add_parser("emit")\n'
           "p.set_defaults(func=cmd_emit)\n"
           "def cmd_emit(args):\n    open(args.path, 'w')\n")
    assert _effect(tree_root, "tool")["emit"] == ("yes", [])


def test_unresolvable_handler_reports_unknown_not_no(tree_root: Path):
    _write(tree_root / "scripts/tool.py", 'sub.add_parser("mystery")\n')
    assert _effect(tree_root, "tool")["mystery"] == ("?", [])


# --------------------------------------------------------------------------- #
# Classification                                                              #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "name,effect,expected",
    [
        ("list", "yes", "action"),          # a found write wins
        ("prune", "no", "action"),          # verb may promote...
        ("show", "yes", "action"),          # ...but never demote
        ("validate", "flag-gated", "query"),
        ("frobnicate", "?", "unclassified"),
        ("show", "?", "query"),
    ],
)
def test_classification_is_monotone_toward_action(name, effect, expected):
    assert qci.classify(name, effect) == expected


# --------------------------------------------------------------------------- #
# Rendered index                                                              #
# --------------------------------------------------------------------------- #

def test_subcommand_row_carries_its_help_text(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           "import argparse\n"
           'p = sub.add_parser("for-path", help="Who owns this path?")\n'
           "p.set_defaults(func=cmd_for_path)\n"
           "def cmd_for_path(args):\n    print(1)\n")
    assert "| `scripts/tool.py for-path` | Who owns this path? | no |" in qci.build(tree_root)


def test_missing_help_is_shown_rather_than_omitted(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           "import argparse\n"
           'p = sub.add_parser("odd")\n'
           "p.set_defaults(func=cmd_odd)\n"
           "def cmd_odd(args):\n    print(1)\n")
    assert "(no help text)" in qci.build(tree_root)


def test_flat_cli_lands_in_the_single_command_section(tree_root: Path):
    _write(tree_root / "scripts/solo.py",
           '"""Do exactly one thing."""\nimport argparse\nargparse.ArgumentParser()\n')
    tail = qci.build(tree_root).partition("## Single-command scripts")[2]
    assert "| `scripts/solo.py` | Do exactly one thing. |" in tail


def test_module_without_a_cli_is_absent_entirely(tree_root: Path):
    _write(tree_root / "scripts/helpers.py", '"""Just a library."""\nX = 1\n')
    assert "scripts/helpers.py" not in qci.build(tree_root)


def test_skill_comply_fixtures_are_not_indexed(tree_root: Path):
    """They are deliberately defective; advertising them would be wrong."""
    _write(tree_root / "scripts/skill_comply/fixtures/defective/scripts/bad.py",
           '"""Broken on purpose."""\nimport argparse\nargparse.ArgumentParser()\n')
    assert "bad.py" not in qci.build(tree_root)


def test_excluded_subtrees_are_named_so_absence_is_not_silence(tree_root: Path):
    content = qci.build(tree_root)
    assert "`.claude/skills/*/scripts/`" in content
    assert "Out of scope, deliberately" in content


def test_pipe_in_help_text_does_not_break_the_table(tree_root: Path):
    _write(tree_root / "scripts/tool.py",
           "import argparse\n"
           'p = sub.add_parser("odd", help="split on | and print")\n'
           "p.set_defaults(func=cmd_odd)\n"
           "def cmd_odd(args):\n    print(1)\n")
    assert "split on \\| and print" in qci.build(tree_root)


def test_missing_scan_root_raises_rather_than_silently_shrinking(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        qci.build(tmp_path)


# --------------------------------------------------------------------------- #
# Real tree                                                                   #
# --------------------------------------------------------------------------- #

def test_subsystems_for_path_is_discoverable_as_a_query():
    content = qci.build(REPO_ROOT)
    query_section = content.partition("## Query subcommands")[2].partition("## Action")[0]
    assert "`scripts/subsystems.py for-path`" in query_section


def test_handler_bound_subcommand_is_classified_in_rendered_index(tree_root: Path):
    _write(
        tree_root / "scripts/tool.py",
        "import argparse\n"
        'p = sub.add_parser("scan", help="Inspect the project")\n'
        "p.set_defaults(handler=cmd_scan)\n"
        "def cmd_scan(args):\n    print(args.path)\n",
    )
    content = qci.build(tree_root)
    assert "| `scripts/tool.py scan` | Inspect the project | no |" in content


def test_two_runs_over_the_real_tree_are_byte_identical():
    assert qci.build(REPO_ROOT) == qci.build(REPO_ROOT)


def test_checked_in_artifact_matches_a_fresh_generation():
    out = REPO_ROOT / qci.OUT_PATH
    assert out.exists(), f"{qci.OUT_PATH} is not checked in"
    assert out.read_text(encoding="utf-8") == qci.build(REPO_ROOT), (
        "query-cli-index.md is stale. Run:\n"
        "  .venv/bin/python scripts/query_cli_index.py"
    )


def test_generated_banner_warns_against_hand_editing():
    out = REPO_ROOT / qci.OUT_PATH
    assert "do not edit by hand" in out.read_text(encoding="utf-8").splitlines()[0]
