from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MOVE_PATH = REPO_ROOT / ".claude" / "skills" / "move-path" / "scripts" / "move_path.py"
AUDIT_PATH_RESIDUE = REPO_ROOT / ".claude" / "skills" / "move-path" / "scripts" / "audit_path_residue.py"


def _load_move_path():
    spec = importlib.util.spec_from_file_location("move_path_under_test", MOVE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_audit_path_residue():
    script_dir = str(AUDIT_PATH_RESIDUE.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("audit_path_residue_under_test", AUDIT_PATH_RESIDUE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, indent=2) + "\n")


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
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
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
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
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
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
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
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
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
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
    )

    rewrites = {(r["old"], r["new"]) for r in report["auto_rewrites"] if r["kind"] == "exact_text_path"}
    assert ("inputs-1/kb", "source-materials/input-bundles/inputs-1/kb") in rewrites
    assert (
        "/inputs-1/kb/glossary.md#term",
        "/source-materials/input-bundles/inputs-1/kb/glossary.md#term",
    ) in rewrites


def test_check_residue_ignores_bare_root_directory_words(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "source-materials" / "extraction-outputs" / "run.json", "{}\n")
    _write(
        tmp_path / "README.md",
        "outputs are produced by scorers.\n"
        "Use outputs/run.json only in old instructions.\n"
        "The new path source-materials/extraction-outputs/run.json is fine.\n",
    )
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: outputs/
    to: source-materials/extraction-outputs/
    mode: directory
reference_scope:
  include: ["**/*.md"]
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="check",
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
    )

    tokens = [s["token"] for s in report["suggestions"]]
    assert "outputs" not in tokens
    assert "outputs/run.json" in tokens
    assert report["blocked"] == []


def test_check_residue_flags_absolute_manifest_paths(tmp_path):
    move_path = _load_move_path()
    old_abs = (tmp_path / "claude-logs" / "snapshot" / "raw" / "session.jsonl").as_posix()
    _write(tmp_path / "source-materials" / "claude-logs" / "snapshot" / "raw" / "session.jsonl", "{}\n")
    _write(tmp_path / "source-materials" / "claude-logs" / "snapshot" / "manifest.json", f'{{"destination": "{old_abs}"}}\n')
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: claude-logs/
    to: source-materials/claude-logs/
    mode: directory
reference_scope:
  include: ["**/*.json"]
""".lstrip(),
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="check",
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
    )

    assert any(
        s["kind"] == "old_path_residue"
        and s["token"] == old_abs
        and s["target_after"].endswith("/source-materials/claude-logs/snapshot/raw/session.jsonl")
        for s in report["suggestions"]
    )
    assert report["blocked"] == []


def test_path_residue_audit_reports_assumptions_and_samples(tmp_path):
    audit_path_residue = _load_audit_path_residue()
    old_abs = (tmp_path / "claude-logs" / "snapshot" / "raw" / "session.jsonl").as_posix()
    _write(tmp_path / "source-materials" / "claude-logs" / "snapshot" / "raw" / "session.jsonl", "{}\n")
    _write(tmp_path / "source-materials" / "claude-logs" / "snapshot" / "manifest.json", f'{{"destination": "{old_abs}"}}\n')
    plan = tmp_path / "moves.yml"
    _write(
        plan,
        """
moves:
  - from: claude-logs/
    to: source-materials/claude-logs/
    mode: directory
reference_scope:
  include: ["**/*.json"]
""".lstrip(),
    )

    payload = audit_path_residue.audit(plan_path=plan, project_root=tmp_path, max_samples=5)

    assert payload["assumptions"]
    assert payload["summary"]["findings"] == 1
    assert payload["samples"][0]["old"] == old_abs
    assert old_abs in payload["samples"][0]["excerpt"]
    assert payload["spot_checks"][0]["old_exists"] is False
    assert payload["spot_checks"][0]["new_exists"] is True

    filtered = audit_path_residue.audit(
        plan_path=plan,
        project_root=tmp_path,
        max_samples=5,
        extra_excludes=["source-materials/**"],
    )
    assert filtered["summary"]["findings"] == 0


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
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
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
            report_dir=tmp_path / ".engineering" / "local" / "move-path",
        )
    except SystemExit as exc:
        assert "broken links" in str(exc)
    else:
        raise AssertionError("apply should have been blocked by an existing broken link")
    assert (tmp_path / "docs" / "old.md").exists()


def test_typescript_move_json_plan_rewrites_references_but_reports_ignored_import_risk(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "src" / "old.ts", "export const oldValue: number = 1;\n")
    _write(
        tmp_path / "src" / "consumer.ts",
        'import { oldValue } from "./old";\nexport const consumed = oldValue;\n',
    )
    _write(tmp_path / "src" / "stable.ts", "export const stableValue: number = 2;\n")
    _write(
        tmp_path / "src" / "moved.ts",
        'import { stableValue } from "./stable";\nexport const moved = stableValue;\n',
    )
    _write(tmp_path / "src" / "Card.tsx", "export const Card = () => <div />;\n")
    _write(tmp_path / "docs" / "index.md", "[Old source](../src/old.ts)\n[Card](../src/Card.tsx)\n")
    _write(tmp_path / "docs" / "page.html", '<script src="../src/old.ts"></script>\n')
    _write(tmp_path / "README.md", "Use `src/old.ts`. https://example.com/src/old.ts is external prose.\n")
    _write_json(tmp_path / "config" / "entry.json", {"entry": "src/old.ts"})
    plan = tmp_path / "moves.json"
    _write_json(
        plan,
        {
            "version": 1,
            "moves": [
                {"id": "typescript-source", "from": "src/old.ts", "to": "lib/new.ts"},
                {"id": "typescript-referrer", "from": "src/moved.ts", "to": "lib/moved.ts"},
                {"id": "typescript-tsx", "from": "src/Card.tsx", "to": "lib/Card.tsx"},
            ],
            "reference_scope": {"include": ["**/*.md", "**/*.html", "**/*.json", "**/*.ts", "**/*.tsx"]},
            "rewrite": {
                "markdown_links": "update",
                "html_href_src": "update",
                "backtick_paths": "update",
                "exact_text_paths": "update",
                "code_imports": "ignore",
            },
        },
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
    )

    rewrites = {(row["file_before"], row["kind"], row["old"], row["new"]) for row in report["auto_rewrites"]}
    assert ("docs/index.md", "markdown_link", "../src/old.ts", "../lib/new.ts") in rewrites
    assert ("docs/index.md", "markdown_link", "../src/Card.tsx", "../lib/Card.tsx") in rewrites
    assert ("docs/page.html", "html_href_src", "../src/old.ts", "../lib/new.ts") in rewrites
    assert ("README.md", "backtick_path", "src/old.ts", "lib/new.ts") in rewrites
    assert ("config/entry.json", "exact_text_path", "src/old.ts", "lib/new.ts") in rewrites
    assert not any(row["file_before"] == "src/consumer.ts" for row in report["auto_rewrites"])
    assert (tmp_path / "src" / "consumer.ts").read_text(encoding="utf-8").startswith(
        'import { oldValue } from "./old";'
    )
    assert "https://example.com/src/old.ts" in (tmp_path / "README.md").read_text(encoding="utf-8")
    assert report["code_imports"]["mode"] == "ignore"
    assert any(
        item["file"] == "src/consumer.ts"
        and item["specifier"] == "./old"
        and item["expected_specifier"] is None
        and item["remediation"] == "unknown_without_typescript_module_resolution"
        and item["target_before"] == "src/old.ts"
        and item["target_after"] == "lib/new.ts"
        for item in report["code_imports"]["ignored"]
    )
    assert any(
        item["file"] == "src/moved.ts"
        and item["specifier"] == "./stable"
        and item["expected_specifier"] is None
        and item["remediation"] == "unknown_without_typescript_module_resolution"
        and item["target_before"] == "src/stable.ts"
        and item["target_after"] == "src/stable.ts"
        for item in report["code_imports"]["ignored"]
    )
    rendered = (tmp_path / ".engineering" / "local" / "move-path" / "report.md").read_text(encoding="utf-8")
    assert "Ignored TypeScript Imports" in rendered
    assert "not rewritten" in rendered

    applied = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="apply",
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
    )
    assert (tmp_path / "lib" / "Card.tsx").is_file()
    assert any(
        item["file"] == "src/consumer.ts"
        and item["specifier"] == "./old"
        and item["expected_specifier"] is None
        and item["target_before"] == "src/old.ts"
        and item["target_after"] == "lib/new.ts"
        for item in applied["code_imports"]["ignored"]
    )
    assert any(
        item["file"] == "src/moved.ts"
        and item["specifier"] == "./stable"
        and item["expected_specifier"] is None
        for item in applied["code_imports"]["ignored"]
    )


def test_in_root_json_plan_is_not_rewritten_by_its_own_reference_scope(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "src" / "old.ts", "export const value = 1;\n")
    _write(tmp_path / "docs" / "index.md", "[Source](../src/old.ts)\n")
    _write_json(tmp_path / "config.json", {"entry": "src/old.ts"})
    plan = tmp_path / "move-plan.json"
    _write_json(
        plan,
        {
            "version": 1,
            "moves": [{"from": "src/old.ts", "to": "lib/new.ts"}],
            "reference_scope": {"include": ["**/*.md", "**/*.json"]},
            "rewrite": {
                "markdown_links": "update",
                "exact_text_paths": "update",
                "code_imports": "ignore",
            },
        },
    )
    plan_before = plan.read_bytes()
    report_dir = tmp_path / ".engineering" / "local" / "move-path"

    dry_run = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=report_dir,
    )
    assert plan.read_bytes() == plan_before
    assert not any(row["file_before"] == "move-plan.json" for row in dry_run["auto_rewrites"])

    applied = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="apply",
        report_dir=report_dir,
    )
    assert plan.read_bytes() == plan_before
    assert applied["mode"] == "check"
    assert applied["blocked"] == []
    assert applied["summary"]["post_broken_links"] == 0
    assert (tmp_path / "lib" / "new.ts").is_file()
    assert (tmp_path / "docs" / "index.md").read_text(encoding="utf-8") == "[Source](../lib/new.ts)\n"
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["entry"] == "lib/new.ts"

    repeated = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=report_dir,
    )
    assert plan.read_bytes() == plan_before
    assert any(item["kind"] == "missing_source" and item["path"] == "src/old.ts" for item in repeated["blocked"])


def test_ignored_import_risk_does_not_invent_a_module_specifier(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "src" / "legacy.ts", "export const value = 1;\n")
    _write(
        tmp_path / "src" / "consumer.ts",
        'import { value } from "./legacy";\nimport { packageValue } from "legacy";\n',
    )
    plan = tmp_path / "moves.json"
    _write_json(
        plan,
        {
            "moves": [{"from": "src/legacy.ts", "to": "src/workflow.ts"}],
            "rewrite": {"code_imports": "ignore"},
        },
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / "reports",
    )

    assert len(report["code_imports"]["ignored"]) == 1
    risk = report["code_imports"]["ignored"][0]
    assert risk["specifier"] == "./legacy"
    assert risk["expected_specifier"] is None
    assert risk["remediation"] == "unknown_without_typescript_module_resolution"
    rendered = (tmp_path / "reports" / "report.md").read_text(encoding="utf-8")
    assert "expected `workflow.ts`" not in rendered
    assert "remediation unknown without TypeScript module resolution" in rendered


def test_multiline_static_import_to_moved_typescript_file_is_reported(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "src" / "old.ts", "export const first = 1;\nexport const second = 2;\n")
    _write(
        tmp_path / "src" / "consumer.ts",
        'import {\n  first,\n  second,\n} from "./old";\nexport const total = first + second;\n',
    )
    plan = tmp_path / "moves.json"
    _write_json(
        plan,
        {
            "moves": [{"from": "src/old.ts", "to": "lib/new.ts"}],
            "rewrite": {"code_imports": "ignore"},
        },
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / "reports",
    )

    assert any(
        item["file"] == "src/consumer.ts"
        and item["lineno"] == 4
        and item["specifier"] == "./old"
        and item["target_before"] == "src/old.ts"
        and item["target_after"] == "lib/new.ts"
        for item in report["code_imports"]["ignored"]
    )


def test_nodenext_emitted_specifiers_resolve_to_moved_typescript_sources_conservatively(tmp_path):
    move_path = _load_move_path()
    _write(tmp_path / "src" / "legacy.ts", "export const legacy = 1;\n")
    _write(tmp_path / "src" / "view.tsx", "export const View = () => <div />;\n")
    _write(tmp_path / "src" / "module.mts", "export const moduleValue = 2;\n")
    _write(tmp_path / "src" / "common.cts", "export const commonValue = 3;\n")
    _write(tmp_path / "src" / "wrong.cts", "export const wrongValue = 4;\n")
    _write(tmp_path / "src" / "shadow.js", "export const runtimeValue = 5;\n")
    _write(tmp_path / "src" / "shadow.ts", "export const sourceValue = 6;\n")
    _write(tmp_path / "src" / "decl.js", "export const runtimeDeclValue = 7;\n")
    _write(tmp_path / "src" / "decl.d.ts", "export declare const declaredValue: number;\n")
    _write(tmp_path / "src" / "module-decl.mjs", "export const runtimeModuleDeclValue = 8;\n")
    _write(tmp_path / "src" / "module-decl.d.mts", "export declare const moduleDeclaredValue: number;\n")
    _write(tmp_path / "src" / "common-decl.cjs", "exports.runtimeCommonDeclValue = 9;\n")
    _write(tmp_path / "src" / "common-decl.d.cts", "export declare const commonDeclaredValue: number;\n")
    _write(
        tmp_path / "src" / "consumer.ts",
        'import { legacy } from "./legacy.js";\n'
        'import { View } from "./view.js";\n'
        'import { moduleValue } from "./module.mjs";\n'
        'import { commonValue } from "./common.cjs";\n'
        'import { wrongValue } from "./wrong.mjs";\n'
        'import { sourceValue } from "./shadow.js";\n'
        'import { declaredValue } from "./decl.js";\n'
        'import { moduleDeclaredValue } from "./module-decl.mjs";\n'
        'import { commonDeclaredValue } from "./common-decl.cjs";\n',
    )
    plan = tmp_path / "moves.json"
    _write_json(
        plan,
        {
            "moves": [
                {"from": "src/legacy.ts", "to": "lib/legacy.ts"},
                {"from": "src/view.tsx", "to": "lib/view.tsx"},
                {"from": "src/module.mts", "to": "lib/module.mts"},
                {"from": "src/common.cts", "to": "lib/common.cts"},
                {"from": "src/wrong.cts", "to": "lib/wrong.cts"},
                {"from": "src/shadow.ts", "to": "lib/shadow.ts"},
                {"from": "src/decl.d.ts", "to": "lib/decl.d.ts"},
                {"from": "src/module-decl.d.mts", "to": "lib/module-decl.d.mts"},
                {"from": "src/common-decl.d.cts", "to": "lib/common-decl.d.cts"},
            ],
            "rewrite": {"code_imports": "ignore"},
        },
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="dry-run",
        report_dir=tmp_path / "reports",
    )

    risks = {item["specifier"]: item for item in report["code_imports"]["ignored"]}
    assert risks["./legacy.js"]["target_before"] == "src/legacy.ts"
    assert risks["./legacy.js"]["target_after"] == "lib/legacy.ts"
    assert risks["./view.js"]["target_before"] == "src/view.tsx"
    assert risks["./view.js"]["target_after"] == "lib/view.tsx"
    assert risks["./module.mjs"]["target_before"] == "src/module.mts"
    assert risks["./module.mjs"]["target_after"] == "lib/module.mts"
    assert risks["./common.cjs"]["target_before"] == "src/common.cts"
    assert risks["./common.cjs"]["target_after"] == "lib/common.cts"
    assert risks["./shadow.js"]["target_before"] == "src/shadow.ts"
    assert risks["./shadow.js"]["target_after"] == "lib/shadow.ts"
    assert risks["./decl.js"]["target_before"] == "src/decl.d.ts"
    assert risks["./decl.js"]["target_after"] == "lib/decl.d.ts"
    assert risks["./module-decl.mjs"]["target_before"] == "src/module-decl.d.mts"
    assert risks["./module-decl.mjs"]["target_after"] == "lib/module-decl.d.mts"
    assert risks["./common-decl.cjs"]["target_before"] == "src/common-decl.d.cts"
    assert risks["./common-decl.cjs"]["target_after"] == "lib/common-decl.d.cts"
    assert all(item["expected_specifier"] is None for item in risks.values())
    assert "./wrong.mjs" not in risks


def test_residue_audit_excludes_the_plan_authority_file(tmp_path):
    audit_path_residue = _load_audit_path_residue()
    _write(tmp_path / "lib" / "new.ts", "export const value = 1;\n")
    _write_json(tmp_path / "config.json", {"entry": "lib/new.ts"})
    plan = tmp_path / "move-plan.json"
    _write_json(
        plan,
        {
            "moves": [{"from": "src/old.ts", "to": "lib/new.ts"}],
            "reference_scope": {"include": ["**/*.json"]},
            "rewrite": {"exact_text_paths": "update", "code_imports": "ignore"},
        },
    )

    payload = audit_path_residue.audit(
        plan_path=plan,
        project_root=tmp_path,
        max_samples=10,
    )

    assert payload["summary"]["findings"] == 0
    assert not any(item["file"] == "move-plan.json" for item in payload["findings"])


def test_json_plan_is_stdlib_only_when_the_selected_skill_is_copied(tmp_path):
    install_root = tmp_path / "installed"
    copied_skill = install_root / "move-path"
    shutil.copytree(MOVE_PATH.parent.parent, copied_skill)
    host = tmp_path / "host"
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()
    _write(host / "src" / "old.ts", "export const oldValue: number = 1;\n")
    _write(host / "docs" / "index.md", "[Old source](../src/old.ts)\n")
    plan = host / "moves.json"
    _write_json(
        plan,
        {
            "version": 1,
            "moves": [{"from": "src/old.ts", "to": "lib/new.ts"}],
            "reference_scope": {"include": ["**/*.md"]},
            "rewrite": {"markdown_links": "update", "code_imports": "ignore"},
        },
    )
    command = [
        sys.executable,
        "-I",
        "-S",
        str(copied_skill / "scripts" / "move_path.py"),
        "--plan",
        str(plan),
        "--project-root",
        str(host),
        "--report-dir",
        str(host / "reports"),
        "--dry-run",
        "--json",
    ]
    result = subprocess.run(command, cwd=outside_cwd, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["summary"]["auto_rewrites"] == 1

    audit = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(copied_skill / "scripts" / "audit_path_residue.py"),
            "--plan",
            str(plan),
            "--project-root",
            str(host),
            "--report-dir",
            str(host / "reports"),
            "--json",
        ],
        cwd=outside_cwd,
        text=True,
        capture_output=True,
    )
    assert audit.returncode == 0, audit.stderr
    assert json.loads(audit.stdout)["summary"]["moves"] == 1


def test_yaml_plans_are_optional_and_import_rewrites_fail_clearly(tmp_path, monkeypatch):
    move_path = _load_move_path()
    yaml_plan = tmp_path / "moves.yml"
    _write(yaml_plan, "moves:\n  - from: src/old.ts\n    to: lib/new.ts\n")
    monkeypatch.setattr(move_path, "yaml", None)

    with pytest.raises(SystemExit, match="YAML plans require optional PyYAML"):
        move_path.load_plan(yaml_plan, tmp_path)

    _write(tmp_path / "src" / "old.ts", "export const oldValue = 1;\n")
    json_plan = tmp_path / "moves.json"
    _write_json(
        json_plan,
        {
            "moves": [{"from": "src/old.ts", "to": "lib/new.ts"}],
            "rewrite": {"code_imports": "update"},
        },
    )
    with pytest.raises(SystemExit, match="only supports ignore"):
        move_path.run_plan(
            plan_path=json_plan,
            project_root=tmp_path,
            mode="dry-run",
            report_dir=tmp_path / "reports",
        )


def test_standalone_typescript_fixture_typechecks_after_an_import_safe_move(tmp_path):
    move_path = _load_move_path()
    _write_json(
        tmp_path / "tsconfig.json",
        {
            "compilerOptions": {"target": "ES2020", "module": "commonjs", "strict": True},
            "include": ["src/**/*.ts", "lib/**/*.ts"],
        },
    )
    _write(tmp_path / "src" / "stable.ts", "export type Stable = { label: string };\n")
    _write(tmp_path / "src" / "old.ts", "export const oldValue: number = 1;\n")
    _write(
        tmp_path / "src" / "consumer.ts",
        'import type { Stable } from "./stable";\nexport const label = (value: Stable) => value.label;\n',
    )
    _write(tmp_path / "docs" / "index.md", "[Old source](../src/old.ts)\n")
    plan = tmp_path / "moves.json"
    _write_json(
        plan,
        {
            "moves": [{"from": "src/old.ts", "to": "lib/new.ts"}],
            "reference_scope": {"include": ["**/*.md", "**/*.ts"]},
            "rewrite": {"markdown_links": "update", "code_imports": "ignore"},
        },
    )

    report = move_path.run_plan(
        plan_path=plan,
        project_root=tmp_path,
        mode="apply",
        report_dir=tmp_path / ".engineering" / "local" / "move-path",
    )
    assert (tmp_path / "lib" / "new.ts").is_file()
    assert not (tmp_path / "src" / "old.ts").exists()
    assert (tmp_path / "docs" / "index.md").read_text(encoding="utf-8") == "[Old source](../lib/new.ts)\n"
    assert (tmp_path / "src" / "consumer.ts").read_text(encoding="utf-8").startswith(
        'import type { Stable } from "./stable";'
    )
    assert report["code_imports"]["mode"] == "ignore"

    tsc = shutil.which("tsc")
    if tsc is None:
        pytest.skip("standalone native typecheck requires tsc on PATH")
    result = subprocess.run([tsc, "--noEmit", "--project", "tsconfig.json"], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
