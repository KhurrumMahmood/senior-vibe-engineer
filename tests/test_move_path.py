from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MOVE_PATH = REPO_ROOT / ".claude" / "skills" / "move-path" / "scripts" / "move_path.py"


def _load_move_path():
    spec = importlib.util.spec_from_file_location("move_path_under_test", MOVE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_dry_run_rewrites_markdown_against_virtual_after_tree(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "kb" / "index.md", "[Eval](evals/eval.md)\n[Schema](schemas/v0.md#thing)\n")
    _write(tmp_path / "kb" / "evals" / "eval.md", "[Schema](../schemas/v0.md#thing)\n")
    _write(tmp_path / "kb" / "schemas" / "v0.md", "# Thing\n")
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: kb/evals/eval.md
    to: specs/contracts/reliability/eval.md
  - from: kb/schemas/
    to: specs/contracts/schemas/
reference_scope:
  include: ["**/*.md"]
rewrite:
  markdown_links: update
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / ".move-path",
    )

    rewrites = {(r["file_before"], r["old"], r["new"]) for r in report["auto_rewrites"]}
    assert ("kb/index.md", "evals/eval.md", "../specs/contracts/reliability/eval.md") in rewrites
    assert ("kb/index.md", "schemas/v0.md#thing", "../specs/contracts/schemas/v0.md#thing") in rewrites
    assert (
        "kb/evals/eval.md",
        "../schemas/v0.md#thing",
        "../schemas/v0.md#thing",
    ) not in rewrites
    # The moved eval file's link text is already correct relative to its
    # future location, so the deterministic pass should not churn it.
    assert not any(r["file_before"] == "kb/evals/eval.md" for r in report["auto_rewrites"])
    assert report["blocked"] == []


def test_moved_file_rewrites_links_to_unmoved_targets(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "kb" / "page.md", "[Synthesis](synthesis/thing.md)\n")
    _write(tmp_path / "kb" / "synthesis" / "thing.md", "# Thing\n")
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: kb/page.md
    to: specs/product/page.md
reference_scope:
  include: ["**/*.md"]
rewrite:
  markdown_links: update
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / ".move-path",
    )

    assert any(
        r["file_before"] == "kb/page.md"
        and r["old"] == "synthesis/thing.md"
        and r["new"] == "../../kb/synthesis/thing.md"
        for r in report["auto_rewrites"]
    )
    assert report["summary"]["post_broken_links"] == 0


def test_apply_moves_files_and_updates_links(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "docs" / "index.md", "[Old](old.md)\n")
    _write(tmp_path / "docs" / "old.md", "# Old\n")
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: docs/old.md
    to: specs/new.md
reference_scope:
  include: ["**/*.md"]
rewrite:
  markdown_links: update
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="apply",
        report_dir=tmp_path / ".move-path",
    )

    assert not (tmp_path / "docs" / "old.md").exists()
    assert (tmp_path / "specs" / "new.md").is_file()
    assert (tmp_path / "docs" / "index.md").read_text(encoding="utf-8") == "[Old](../specs/new.md)\n"
    assert report["summary"]["post_broken_links"] == 0


def test_backtick_paths_update_but_exact_text_defaults_to_suggest(tmp_path):
    move_path = _load_move_path()
    _write(
        tmp_path / "README.md",
        "Use `kb/evals/eval.md`.\nPlain kb/evals/eval.md should be reviewed.\n",
    )
    _write(tmp_path / "kb" / "evals" / "eval.md", "# Eval\n")
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: kb/evals/eval.md
    to: specs/eval.md
reference_scope:
  include: ["**/*.md"]
rewrite:
  backtick_paths: update
  exact_text_paths: suggest
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / ".move-path",
    )

    assert any(r["kind"] == "backtick_path" and r["new"] == "specs/eval.md" for r in report["auto_rewrites"])
    assert any(s["kind"] == "exact_text_path" and s["token"] == "kb/evals/eval.md" for s in report["suggestions"])


def test_exact_text_directory_move_updates_nested_path_tokens(tmp_path):
    move_path = _load_move_path()
    _write(
        tmp_path / "README.md",
        "Preserve inputs-1/kb and /inputs-1/kb/glossary.md#term.\n",
    )
    _write(tmp_path / "inputs-1" / "kb" / "glossary.md", "# Glossary\n")
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: inputs-1/
    to: source-materials/input-bundles/inputs-1/
    mode: directory
reference_scope:
  include: ["**/*.md"]
rewrite:
  exact_text_paths: update
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / ".move-path",
    )

    rewrites = {(r["old"], r["new"]) for r in report["auto_rewrites"] if r["kind"] == "exact_text_path"}
    assert ("inputs-1/kb", "source-materials/input-bundles/inputs-1/kb") in rewrites
    assert (
        "/inputs-1/kb/glossary.md#term",
        "/source-materials/input-bundles/inputs-1/kb/glossary.md#term",
    ) in rewrites


def test_nested_backtick_path_can_be_repo_root_relative(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "kb" / "index.md", "Use `kb/evals/eval.md` from here.\n")
    _write(tmp_path / "kb" / "evals" / "eval.md", "# Eval\n")
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: kb/evals/eval.md
    to: specs/eval.md
reference_scope:
  include: ["**/*.md"]
rewrite:
  backtick_paths: update
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / ".move-path",
    )

    assert any(
        r["kind"] == "backtick_path" and r["old"] == "kb/evals/eval.md" and r["new"] == "specs/eval.md"
        for r in report["auto_rewrites"]
    )


def test_windows_style_markdown_reference_preserves_backslashes(tmp_path):
    move_path = _load_move_path()
    assert (
        move_path.format_reference("docs/old.md", "specs/new.md", "docs/index.md", "old.md")
        == "../specs/new.md"
    )
    assert (
        move_path.format_reference("docs/old.md", "specs/new.md", "docs/index.md", r"old\doc.md")
        == r"..\specs\new.md"
    )


def test_post_apply_broken_link_blocks_apply(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "docs" / "index.md", "[Missing](missing.md)\n[Old](old.md)\n")
    _write(tmp_path / "docs" / "old.md", "# Old\n")
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: docs/old.md
    to: specs/new.md
reference_scope:
  include: ["**/*.md"]
rewrite:
  markdown_links: update
safety:
  fail_on_broken_links: true
""".lstrip(),
    )

    try:
        move_path.run_plan(
            plan_path=plan,
            project_root=tmp_path,
            mode="apply",
            report_dir=tmp_path / ".move-path",
        )
    except SystemExit as exc:
        assert "broken links" in str(exc)
    else:
        raise AssertionError("apply should have been blocked by an existing broken link")
    assert (tmp_path / "docs" / "old.md").exists()
