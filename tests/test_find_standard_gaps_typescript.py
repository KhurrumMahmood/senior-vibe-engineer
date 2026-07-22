"""TypeScript outcome, boundaries, and installed-closure proof for standard gaps."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-standard-gaps"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-standard-gaps-typescript"


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    typecheck = _run("npm", "run", "typecheck", cwd=host)
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    native = _run("npm", "test", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    return host


def _scan(
    skill: Path,
    host: Path,
    ideas: Path,
    output: Path,
    *,
    isolated: bool = False,
) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    return _run(
        *prefix,
        str(skill / "scripts" / "scan_coverage.py"),
        "--ideas",
        str(ideas),
        "--project-root",
        str(host),
        "--output-dir",
        str(output),
        cwd=host,
    )


def _result(output: Path) -> dict:
    payload = json.loads((output / "coverage.json").read_text(encoding="utf-8"))
    assert len(payload["results"]) == 1
    return payload["results"][0]


def _write_ideas(host: Path, detector: dict, name: str = "ideas.json") -> Path:
    ideas = {
        "ideas": [{
            "id": "idea-test",
            "label": "test standard",
            "activation": {"baseline": True},
            "contract": {"detector": detector},
        }],
    }
    path = host / name
    path.write_text(json.dumps(ideas), encoding="utf-8")
    return path


def _documented_command(skill: Path, name: str) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- installed-command:{name}:start -->\n```bash\n(.*?)\n```\n"
        rf"<!-- installed-command:{name}:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None, name
    return match.group(1)


def test_typescript_and_tsx_try_standard_reaches_final_coverage_artifacts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    output = host / "reports" / "typescript"

    result = _scan(SKILL, host, host / "standards.json", output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "scanned"
    assert finding["scanned_files"] == 2
    assert finding["skipped_files"] == 0
    assert finding["situation_sites"] == 4
    assert {(gap["file"], gap["line"]) for gap in finding["gaps"]} == {
        ("src/json.ts", 2),
        ("src/json.ts", 16),
        ("src/panel.tsx", 4),
    }
    assert finding["coverage"] == 0.25
    report = (output / "coverage.md").read_text(encoding="utf-8")
    assert "3 gap(s)" in report
    assert "src/panel.tsx:4" in report


def test_mixed_python_and_typescript_sources_are_scanned_together(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "legacy.py").write_text(
        "import json\n\ndef unsafe(value):\n    return json.loads(value)\n",
        encoding="utf-8",
    )
    (host / "src" / "legacy.js").write_text(
        "export const unsafe = (value) => JSON.parse(value);\n",
        encoding="utf-8",
    )
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^(JSON\.parse|json\.loads)$",
            "enclosed_by": "try",
            "paths": ["src/**/*"],
        },
    )
    output = host / "reports" / "mixed"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "scanned"
    assert finding["scanned_files"] == 4
    assert finding["skipped_files"] == 0
    assert {(gap["file"], gap["line"]) for gap in finding["gaps"]} == {
        ("src/json.ts", 2),
        ("src/json.ts", 16),
        ("src/panel.tsx", 4),
        ("src/legacy.py", 4),
        ("src/legacy.js", 1),
    }
    report = (output / "coverage.md").read_text(encoding="utf-8")
    assert "src/legacy.js:1" in report


def test_direct_mixed_directory_target_never_marks_protected_python_plus_js_clean(
    tmp_path: Path,
) -> None:
    host = tmp_path / "python-js-host"
    source = host / "app"
    source.mkdir(parents=True)
    (source / "protected.py").write_text(
        "import json\n\ndef safe(value):\n    try:\n        return json.loads(value)\n"
        "    except ValueError:\n        return None\n",
        encoding="utf-8",
    )
    (source / "unsafe.js").write_text(
        "export const unsafe = (value) => JSON.parse(value);\n",
        encoding="utf-8",
    )
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^(JSON\.parse|json\.loads)$",
            "enclosed_by": "try",
            "paths": ["app"],
        },
    )
    output = host / "reports" / "direct-mixed-directory"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "partial"
    assert finding["scanned_files"] == 1
    assert finding["skipped_files"] == 0
    assert finding["unsupported_files"] == 1
    assert finding["unsupported_extensions"] == [".js"]
    assert finding["situation_sites"] == 1
    assert finding["gaps"] == []
    assert finding["coverage"] == 1.0
    report = (output / "coverage.md").read_text(encoding="utf-8")
    assert "1 unsupported (.js)" in report
    assert "not clean/compliant" in report
    assert "PARTIAL" in result.stdout


def test_unsupported_extension_without_supported_files_is_language_unsupported(
    tmp_path: Path,
) -> None:
    host = tmp_path / "javascript-host"
    source = host / "app"
    source.mkdir(parents=True)
    (source / "unsafe.js").write_text(
        "export const unsafe = (value) => JSON.parse(value);\n",
        encoding="utf-8",
    )
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "enclosed_by": "try",
            "paths": ["app"],
        },
    )
    output = host / "reports" / "javascript-only"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "language_unsupported"
    assert finding["matched"] == 1
    assert finding["extensions"] == [".js"]
    report = (output / "coverage.md").read_text(encoding="utf-8")
    assert "language-unsupported" in report
    assert "LANGUAGE-UNSUPPORTED" in result.stdout


def test_python_requires_kwarg_behavior_stays_available_without_node(tmp_path: Path) -> None:
    host = tmp_path / "python-host"
    (host / "app").mkdir(parents=True)
    (host / "app" / "client.py").write_text(
        "import requests\n\nrequests.get('https://example.test')\n"
        "requests.get('https://example.test', timeout=1)\n",
        encoding="utf-8",
    )
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^requests\.get$",
            "requires_kwarg": "timeout",
            "paths": ["app/**/*.py"],
        },
    )
    output = host / "reports" / "python"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "scanned"
    assert finding["situation_sites"] == 2
    assert [(gap["file"], gap["line"]) for gap in finding["gaps"]] == [
        ("app/client.py", 3),
    ]


def test_typescript_python_specific_condition_is_not_misreported_as_clean(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "requires_kwarg": "timeout",
            "paths": ["src/**/*.ts", "src/**/*.tsx"],
        },
    )
    output = host / "reports" / "unsupported-condition"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "language_unsupported"
    assert "requires_kwarg" in finding["error"]
    assert "0 gap(s)" not in result.stdout


def test_typescript_preflight_failure_is_not_misreported_as_clean(tmp_path: Path) -> None:
    host = tmp_path / "missing-typescript"
    (host / "src").mkdir(parents=True)
    (host / "package.json").write_text('{"name":"missing-typescript"}\n', encoding="utf-8")
    (host / "src" / "example.ts").write_text(
        "export const parse = (value: string) => JSON.parse(value);\n",
        encoding="utf-8",
    )
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "enclosed_by": "try",
            "paths": ["src/**/*.ts"],
        },
    )
    output = host / "reports" / "missing-typescript"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "language_unsupported"
    assert "project-local TypeScript package is unavailable" in finding["error"]
    assert "0 gap(s)" not in result.stdout


def test_typescript_syntax_failure_is_explicitly_partial_not_clean(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "broken.ts").write_text(
        "export function broken(: string) { return JSON.parse('bad'); }\n",
        encoding="utf-8",
    )
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "enclosed_by": "try",
            "paths": ["src/broken.ts"],
        },
    )
    output = host / "reports" / "broken"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    finding = _result(output)
    assert finding["status"] == "partial"
    assert finding["scanned_files"] == 0
    assert finding["skipped_files"] == 1
    assert finding["situation_sites"] == 0
    assert finding["gaps"] == []
    report = (output / "coverage.md").read_text(encoding="utf-8")
    assert "1 skipped" in report
    assert "not clean/compliant" in report
    assert "PARTIAL" in result.stdout


def test_typescript_exclusions_and_external_symlink_escapes_are_project_relative(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    source = host / "src" / "json.ts"
    excluded_directory = host / "src" / "vendor" / "nested"
    excluded_directory.mkdir(parents=True)
    excluded_file = excluded_directory / "copied.ts"
    shutil.copy2(source, excluded_file)

    direct_directory = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "enclosed_by": "try",
            "paths": ["src/vendor"],
        },
        "direct-directory.json",
    )
    direct_file = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "enclosed_by": "try",
            "paths": ["src/vendor/nested/copied.ts"],
        },
        "direct-file.json",
    )

    for name, ideas in (("directory", direct_directory), ("file", direct_file)):
        output = host / "reports" / name
        result = _scan(SKILL, host, ideas, output)
        assert result.returncode == 0, result.stdout + result.stderr
        finding = _result(output)
        assert finding["status"] == "no_files_matched"
        assert "All matched TypeScript/TSX files were excluded" in finding["error"]

    outside = tmp_path / "outside.ts"
    shutil.copy2(source, outside)
    escape = host / "src" / "external-escape.ts"
    escape.symlink_to(outside)
    escaped_ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "enclosed_by": "try",
            "paths": ["src/external-escape.ts"],
        },
        "external-escape.json",
    )
    output = host / "reports" / "external-escape"

    result = _scan(SKILL, host, escaped_ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _result(output)["status"] == "no_files_matched"


def test_typescript_test_file_exclusions_are_case_insensitive(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    excluded = host / "src" / "CAPS.TEST.TS"
    excluded.write_text("export const ignored = JSON.parse('ignored');\n", encoding="utf-8")
    ideas = _write_ideas(
        host,
        {
            "kind": "ast",
            "call_matches": r"^JSON\.parse$",
            "enclosed_by": "try",
            "paths": ["src/CAPS.TEST.TS"],
        },
        "uppercase-test-file.json",
    )
    output = host / "reports" / "uppercase-test-file"

    result = _scan(SKILL, host, ideas, output)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _result(output)["status"] == "no_files_matched"


def test_copied_skill_runs_isolated_without_toolkit_or_sibling_runtime(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    installed = tmp_path / "installed" / "find-standard-gaps"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "isolated"

    result = _scan(installed, host, host / "standards.json", output, isolated=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _result(output)["status"] == "scanned"
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in closure
    assert "/_common" not in closure


def test_stock_install_runs_documented_commands_verbatim_under_host_python(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = _run(
        "npx",
        "--yes",
        "skills@1.5.19",
        "add",
        str(REPO_ROOT),
        "--skill",
        "find-standard-gaps",
        "--agent",
        "codex",
        "--copy",
        "-y",
        cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1"},
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "find-standard-gaps"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    resolver = _documented_command(installed, "resolve")
    run = _documented_command(installed, "run")
    result = _run(
        "bash",
        "-c",
        f"{resolver}\n{run}",
        cwd=host,
        env={**os.environ, "STANDARDS": "standards.json", "DO_NOT_TRACK": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "HOST_PYTHON=\"python3\"" in resolver
    latest = sorted((host / "reports" / "standard-gaps").glob("scan-*"))[-1]
    finding = _result(latest)
    assert finding["status"] == "scanned"
    assert len(finding["gaps"]) == 3


def test_frontmatter_and_docs_name_the_narrow_typescript_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "language: any" in text
    assert "scans: [python, javascript, typescript, go, java]" in text
    assert "TypeScript Compiler API" in text
    assert "does not resolve aliases, types, receivers, or frameworks" in text
