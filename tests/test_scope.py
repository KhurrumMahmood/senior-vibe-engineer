"""Tests for the per-skill scope mechanism (.claude/skills/_common/scope.py).

Covers the pure parser (``parse_scope``), the descriptor loader
(``load_scope`` against a tmp ``.engineering/docs/`` tree), and the ignore-first
file walker (``iter_paths`` / ``scan``): builtin skip dirs, the
``.claude/worktrees`` subtree prune, ignore globs, the gitignore-style
directory-subtree rule, optional roots narrowing, and extension filtering.
Deterministic and disk-isolated — every walk runs against ``tmp_path``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# scope.py lives in _common, not scripts/ (which conftest puts on the path).
_COMMON = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

import scope  # noqa: E402


def _touch(root: Path, relpath: str, content: str = "x\n") -> Path:
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _rel(paths: list[Path], root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in paths}


# ---- parse_scope (pure) --------------------------------------------------

def test_parse_scope_ignore_and_roots():
    text = (
        "# scope\n\n"
        "## Ignore\n"
        "- `**/migrations/**` — generated\n"
        "- `app/legacy/` — frozen\n\n"
        "## Roots\n"
        "- app/\n"
        "- scripts/\n"
    )
    roots, ignore = scope.parse_scope(text)
    assert ignore == ["**/migrations/**", "app/legacy/"]
    assert roots == ["app", "scripts"]  # trailing slash stripped


def test_parse_scope_scan_is_roots_alias():
    roots, ignore = scope.parse_scope("## Scan\n- app/\n")
    assert roots == ["app"]
    assert ignore == []


def test_parse_scope_no_roots_section_is_none():
    roots, ignore = scope.parse_scope("## Ignore\n- `build/`\n")
    assert roots is None
    assert ignore == ["build/"]


def test_parse_scope_empty_roots_section_is_none():
    # A Roots heading with no bullets is no narrowing, not an empty whitelist.
    roots, _ = scope.parse_scope("## Roots\n\n## Ignore\n- `x/`\n")
    assert roots is None


def test_parse_scope_bare_token_without_backticks():
    roots, ignore = scope.parse_scope("## Ignore\n- vendor/ — third-party\n")
    assert ignore == ["vendor/"]
    assert roots is None


def test_parse_scope_empty_text():
    assert scope.parse_scope("") == (None, [])


# ---- load_scope (descriptor on disk) -------------------------------------

def test_load_scope_absent_is_ignore_first_empty(tmp_path):
    s = scope.load_scope(tmp_path, "find-anything")
    assert s.roots is None
    assert s.ignore == []
    assert s.source is None


def test_load_scope_reads_engineering_docs(tmp_path):
    _touch(
        tmp_path,
        ".engineering/docs/find-route-sprawl-scope.md",
        "## Ignore\n- `**/tests/**`\n\n## Roots\n- app/\n",
    )
    s = scope.load_scope(tmp_path, "find-route-sprawl")
    assert s.roots == ["app"]
    assert s.ignore == ["**/tests/**"]
    assert s.source is not None
    assert s.source.name == "find-route-sprawl-scope.md"


# ---- iter_paths: ignore-first walk ---------------------------------------

def test_iter_paths_default_universe_prunes_builtin_dirs(tmp_path):
    _touch(tmp_path, "app/foo.py")
    _touch(tmp_path, "scripts/bar.py")
    _touch(tmp_path, ".git/config")
    _touch(tmp_path, "node_modules/dep/index.js")
    _touch(tmp_path, "app/migrations/0001_initial.py")
    _touch(tmp_path, "app/__pycache__/foo.cpython.pyc")

    got = _rel(scope.iter_paths(tmp_path, scope.Scope()), tmp_path)
    assert got == {"app/foo.py", "scripts/bar.py"}


def test_iter_paths_prunes_claude_worktrees_subtree(tmp_path):
    _touch(tmp_path, ".claude/skills/keep.py")
    _touch(tmp_path, ".claude/worktrees/wt1/app/copy.py")

    got = _rel(scope.iter_paths(tmp_path, scope.Scope()), tmp_path)
    assert got == {".claude/skills/keep.py"}


def test_iter_paths_ignore_glob_removes_matches(tmp_path):
    _touch(tmp_path, "app/foo.py")
    _touch(tmp_path, "app/foo_test.py")
    s = scope.Scope(ignore=["**/*_test.py"])
    got = _rel(scope.iter_paths(tmp_path, s), tmp_path)
    assert got == {"app/foo.py"}


def test_iter_paths_ignore_directory_subtree(tmp_path):
    # A pattern naming a directory ignores everything beneath it (gitignore-style).
    _touch(tmp_path, "app/keep.py")
    _touch(tmp_path, "app/legacy/old.py")
    _touch(tmp_path, "app/legacy/deeper/older.py")
    s = scope.Scope(ignore=["app/legacy/"])
    got = _rel(scope.iter_paths(tmp_path, s), tmp_path)
    assert got == {"app/keep.py"}


def test_iter_paths_roots_narrowing(tmp_path):
    _touch(tmp_path, "app/foo.py")
    _touch(tmp_path, "scripts/bar.py")
    _touch(tmp_path, "docs/readme.md")
    s = scope.Scope(roots=["app"])
    got = _rel(scope.iter_paths(tmp_path, s), tmp_path)
    assert got == {"app/foo.py"}


def test_iter_paths_root_prefix_is_segment_anchored(tmp_path):
    # Root "app" must not match a sibling file like "application.py".
    _touch(tmp_path, "app/foo.py")
    _touch(tmp_path, "application.py")
    s = scope.Scope(roots=["app"])
    got = _rel(scope.iter_paths(tmp_path, s), tmp_path)
    assert got == {"app/foo.py"}


def test_iter_paths_extensions_filter(tmp_path):
    _touch(tmp_path, "app/foo.py")
    _touch(tmp_path, "app/note.md")
    _touch(tmp_path, "app/bar.js")
    got = _rel(scope.iter_paths(tmp_path, scope.Scope(), extensions=frozenset({".py"})), tmp_path)
    assert got == {"app/foo.py"}


def test_iter_paths_sorted_deterministic(tmp_path):
    for name in ("c.py", "a.py", "b.py"):
        _touch(tmp_path, f"app/{name}")
    paths = scope.iter_paths(tmp_path, scope.Scope())
    assert paths == sorted(paths)


def test_iter_paths_ignore_then_roots_compose(tmp_path):
    _touch(tmp_path, "app/foo.py")
    _touch(tmp_path, "app/foo_test.py")
    _touch(tmp_path, "scripts/bar.py")
    s = scope.Scope(roots=["app"], ignore=["**/*_test.py"])
    got = _rel(scope.iter_paths(tmp_path, s), tmp_path)
    assert got == {"app/foo.py"}


# ---- parse_sections (pure, skill-specific glob sections) -----------------

def test_parse_sections_fills_each_key():
    text = (
        "## Views\n"
        "- `app/pages/`\n"
        "- `app/api/`\n\n"
        "## Tasks\n"
        "- app/jobs/ — async layer\n"
    )
    out = scope.parse_sections(text, {"view": {"views", "view"}, "task": {"tasks", "task"}})
    assert out == {"view": ["app/pages/", "app/api/"], "task": ["app/jobs/"]}


def test_parse_sections_absent_section_is_empty_list():
    out = scope.parse_sections("## Views\n- `a/`\n", {"view": {"views"}, "task": {"tasks"}})
    assert out["view"] == ["a/"]
    assert out["task"] == []  # every key present, empty when its heading is absent


def test_parse_sections_ignores_unmapped_headings():
    out = scope.parse_sections("## Other\n- `x/`\n", {"view": {"views"}})
    assert out == {"view": []}


# ---- descriptor_text -----------------------------------------------------

def test_descriptor_text_reads_and_absent(tmp_path):
    assert scope.descriptor_text(tmp_path, "find-layer-violation") is None
    _touch(tmp_path, ".engineering/docs/find-layer-violation-scope.md", "## Views\n- `app/`\n")
    text = scope.descriptor_text(tmp_path, "find-layer-violation")
    assert text is not None and "## Views" in text


# ---- scan convenience ----------------------------------------------------

def test_scan_reads_descriptor_and_filters(tmp_path):
    _touch(tmp_path, "app/foo.py")
    _touch(tmp_path, "app/legacy/old.py")
    _touch(tmp_path, "scripts/bar.py")
    _touch(
        tmp_path,
        ".engineering/docs/find-omnibus-scope.md",
        "## Roots\n- app/\n\n## Ignore\n- `app/legacy/`\n",
    )
    got = _rel(scope.scan(tmp_path, "find-omnibus"), tmp_path)
    assert got == {"app/foo.py"}
