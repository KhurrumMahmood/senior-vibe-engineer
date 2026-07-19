from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "audit-decisions"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "audit-decisions-typescript" / "host"


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    excluded_node_module = host / "node_modules" / "pkg" / "direct.ts"
    excluded_node_module.parent.mkdir(parents=True, exist_ok=True)
    excluded_node_module.write_text("// decision:9996\n", encoding="utf-8")
    typecheck = _run("npm", "run", "typecheck", cwd=host)
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    return host


def _audit(skill: Path, host: Path, output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "audit.py"),
        "--project-root",
        str(host),
        "--output-dir",
        str(output),
        *extra,
        cwd=host,
    )


def _raw(output: Path) -> dict:
    return json.loads((output / "raw-drift.json").read_text(encoding="utf-8"))


def test_typescript_and_existing_reference_forms_reach_final_drift_artifacts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    output = host / "reports" / "audit-decisions" / "scan-typescript"

    result = _audit(SKILL, host, output)

    assert result.returncode == 1, result.stdout + result.stderr
    raw = _raw(output)
    references = raw["references"]
    ts_refs = [ref for ref in references if ref["language"] == "typescript"]
    assert {ref["comment_form"] for ref in ts_refs} == {"line", "block", "jsdoc"}
    assert {ref["id"] for ref in ts_refs if ref["resolved"]} == {"0001", "0002", "0003"}
    assert any(ref["path"] == "src/decision_refs.tsx" and ref["id"] == "0001" for ref in ts_refs)
    assert {ref["language"] for ref in references} >= {"python", "markdown", "html", "typescript"}

    orphan_rows = [row for row in raw["drift"] if row["symptom"] == "code-ref-orphan"]
    assert [(row["evidence"]["path"], row["adr_id"]) for row in orphan_rows] == [
        ("src/decision_refs.ts", "9999"),
    ]
    assert "TS/TSX comment references: 18 total" in (output / "drift.md").read_text(encoding="utf-8")


def test_typescript_literals_jsx_text_and_regexes_never_create_references(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    output = host / "reports" / "audit-decisions" / "literal-boundary"

    result = _audit(SKILL, host, output)

    assert result.returncode == 1, result.stdout + result.stderr
    ids = {ref["id"] for ref in _raw(output)["references"]}
    assert not ids & {
        "9001", "9002", "9003", "9004", "9005", "9006", "9007", "9204",
        "9441", "9442", "9443", "9444", "9445", "9446", "9450",
    }


def test_tsx_fragment_expression_comment_remains_a_real_reference(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    output = host / "reports" / "audit-decisions" / "tsx-fragment-expression"

    result = _audit(SKILL, host, output)

    assert result.returncode == 1, result.stdout + result.stderr
    fragment_refs = [
        ref
        for ref in _raw(output)["references"]
        if (
            ref["path"] == "src/decision_refs.tsx"
            and ref["id"] == "0001"
            and ref["comment_form"] == "block"
            and ref["line"] in {4, 11}
        )
    ]
    assert [ref["line"] for ref in fragment_refs] == [4, 11]

    tsx_refs = [
        ref
        for ref in _raw(output)["references"]
        if ref["path"] == "src/decision_refs.tsx"
    ]
    assert {(ref["id"], ref["comment_form"]) for ref in tsx_refs} == {
        ("0001", "block"),
        ("0001", "jsdoc"),
        ("0002", "block"),
        ("0002", "line"),
        ("0003", "line"),
        ("0003", "jsdoc"),
    }


def test_generic_jsx_tag_arguments_do_not_consume_following_comments(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    output = host / "reports" / "audit-decisions" / "generic-jsx-boundary"

    result = _audit(SKILL, host, output)

    assert result.returncode == 1, result.stdout + result.stderr
    refs = [
        (ref["line"], ref["id"], ref["comment_form"])
        for ref in _raw(output)["references"]
        if ref["path"] == "src/decision_refs.tsx" and 23 <= ref["line"] <= 27
    ]
    assert refs == [
        (23, "0002", "block"),
        (24, "0003", "line"),
        (25, "0001", "jsdoc"),
        (26, "0003", "line"),
        (27, "0002", "line"),
    ]


def test_compiler_valid_jsx_type_arguments_keep_comment_references(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    output = host / "reports" / "audit-decisions" / "jsx-type-argument-comments"

    result = _audit(SKILL, host, output)

    assert result.returncode == 1, result.stdout + result.stderr
    refs = {
        (ref["line"], ref["id"], ref["comment_form"])
        for ref in _raw(output)["references"]
        if ref["path"] == "src/decision_refs.tsx"
    }
    assert {
        (41, "0001", "block"),
        (41, "0002", "line"),
        (42, "0003", "jsdoc"),
    } <= refs


def test_typescript_parser_rejects_invalid_source_instead_of_returning_partial_results(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "broken.ts").write_text("export function broken(: number { return 1; }\n", encoding="utf-8")
    output = host / "reports" / "audit-decisions" / "parse-error"

    result = _audit(SKILL, host, output)

    assert result.returncode == 2
    assert "syntax error" in result.stderr
    assert not output.exists()


def test_typescript_sources_require_a_host_local_compiler_api_dependency(tmp_path: Path) -> None:
    host = tmp_path / "missing-typescript"
    (host / "ai-docs" / "decisions").mkdir(parents=True)
    (host / "src").mkdir()
    shutil.copy2(FIXTURE / "ai-docs" / "decisions" / "0001-runtime-boundary.md", host / "ai-docs" / "decisions")
    (host / "package.json").write_text('{"name":"missing-typescript","private":true}\n', encoding="utf-8")
    (host / "src" / "reference.ts").write_text("// decision:0001\n", encoding="utf-8")
    output = host / "reports" / "audit-decisions" / "missing-typescript"

    result = _audit(SKILL, host, output)

    assert result.returncode == 2
    assert "project-local TypeScript package is unavailable" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "target",
    [
        "generated",
        "vendor",
        "node_modules",
        "build",
        "tests",
        "generated/direct.ts",
        "vendor/direct.ts",
        "node_modules/pkg/direct.ts",
        "build/direct.ts",
        "tests/direct.ts",
    ],
)
def test_project_relative_exclusions_hold_when_targeting_excluded_dir_or_file(
    tmp_path: Path,
    target: str,
) -> None:
    host = _copy_host(tmp_path)
    output = host / "reports" / "audit-decisions" / target.replace("/", "-")

    result = _audit(SKILL, host, output, "--target", target)

    assert result.returncode == 0, result.stdout + result.stderr
    raw = _raw(output)
    assert raw["references"] == []
    assert raw["drift"] == []


def test_copied_selected_skill_runs_with_host_python_outside_source_checkout(tmp_path: Path) -> None:
    installed = tmp_path / "host" / ".agents" / "skills" / "audit-decisions"
    installed.parent.mkdir(parents=True)
    shutil.copytree(SKILL, installed)
    host = _copy_host(tmp_path / "fixture")
    output = host / "reports" / "audit-decisions" / "installed"

    result = _audit(installed, host, output)

    assert result.returncode == 1, result.stdout + result.stderr
    raw = _raw(output)
    assert any(ref["language"] == "typescript" and ref["resolved"] for ref in raw["references"])
    assert (output / "registry-audit.json").is_file()
    assert (output / "link-check.txt").is_file()
    assert (installed / "scripts" / "detect_typescript_comments.mjs").is_file()
    assert all(
        "_common" not in path.read_text(encoding="utf-8")
        for path in installed.rglob("*")
        if path.suffix in {".py", ".mjs"}
    )


def test_stock_codex_install_copies_only_audit_decisions_and_runs_with_python3(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = _run(
        "npx",
        "--yes",
        "skills@1.5.19",
        "add",
        str(REPO_ROOT),
        "--skill",
        "audit-decisions",
        "--agent",
        "codex",
        "--copy",
        "-y",
        cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1"},
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "audit-decisions"
    assert installed.is_dir()
    assert {path.name for path in installed.parent.iterdir()} == {"audit-decisions"}

    output = host / "reports" / "audit-decisions" / "stock-installed"
    result = _run(
        "python3",
        "-I",
        "-S",
        str(installed / "scripts" / "audit.py"),
        "--project-root",
        str(host),
        "--output-dir",
        str(output),
        cwd=tmp_path,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert any(ref["language"] == "typescript" for ref in _raw(output)["references"])


def test_installed_documentation_declares_the_stock_location_and_typescript_prerequisite() -> None:
    instructions = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert ".agents/skills/audit-decisions" in instructions
    assert ".claude/skills/audit-decisions" not in instructions
    assert "python3 -I -S" in instructions
    assert "Node.js" in instructions
    assert "project-local `typescript`" in instructions
    assert "scripts/decisions.py" not in instructions
