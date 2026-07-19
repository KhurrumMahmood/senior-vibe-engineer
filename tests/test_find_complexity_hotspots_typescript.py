"""TypeScript outcome, boundary, and installed-closure proof for complexity hotspots."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-complexity-hotspots"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-complexity-hotspots-typescript"


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


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


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


def _run_pipeline(skill: Path, host: Path, *, isolated: bool) -> list[dict]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    result = _run(
        *prefix,
        str(skill / "scripts" / "run.py"),
        "--project-root",
        str(host),
        "--language",
        "typescript",
        "--skip-effectiveness-log",
        ".",
        cwd=host,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report_dir = (host / "reports" / "find-complexity-hotspots" / "latest").resolve()
    findings = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    assert findings["summary"]["findings_total"] == 3
    assert "typescript" in (report_dir / "report.md").read_text(encoding="utf-8")
    return _records(report_dir / "detections.jsonl")


def _assert_typescript_outcome(records: list[dict]) -> None:
    assert {record["file"] for record in records} == {"src/complexity.ts"}
    assert {record["symbol"] for record in records} == {
        "declaredHotspot",
        "ComplexityService.methodHotspot",
        "arrowHotspot",
    }
    assert {record["pattern"] for record in records} == {"high-branch-function"}
    assert {record["language"] for record in records} == {"typescript"}
    assert {record["analyzer"] for record in records} == {"typescript-compiler-api"}
    assert {record["branch_score"] for record in records} == {18}
    for record in records:
        assert record["loc"] >= 20
        assert record["end_lineno"] > record["lineno"]
        source = (FIXTURE / record["file"]).read_text(encoding="utf-8").splitlines()
        assert record["symbol"].split(".")[-1] in source[record["lineno"] - 1]
        assert source[record["end_lineno"] - 1].strip().startswith("}")


def test_python_six_band_oracle_stays_green() -> None:
    result = _run(sys.executable, str(SKILL / "scripts" / "smoke.py"), cwd=REPO_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "6 bad fixture findings, good fixture clean" in result.stdout


def test_typescript_outcome_reaches_final_report_with_provenance_and_spans(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)

    records = _run_pipeline(SKILL, host, isolated=False)

    _assert_typescript_outcome(records)


def test_typescript_syntax_and_prerequisite_failures_are_clear(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    broken = host / "src" / "broken.ts"
    broken.write_text("export function broken(: number { return 1; }\n", encoding="utf-8")
    output = host / "broken.jsonl"
    syntax = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--language",
        "typescript",
        "src",
        cwd=host,
    )
    assert syntax.returncode == 2
    assert "syntax error" in syntax.stderr

    missing_ts = tmp_path / "missing-typescript"
    (missing_ts / "src").mkdir(parents=True)
    (missing_ts / "package.json").write_text('{"name":"missing-typescript"}\n', encoding="utf-8")
    (missing_ts / "src" / "sample.ts").write_text("export const sample = () => {};\n", encoding="utf-8")
    missing_package = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(missing_ts),
        "--output",
        str(missing_ts / "out.jsonl"),
        "--language",
        "typescript",
        "src",
        cwd=missing_ts,
    )
    assert missing_package.returncode == 2
    assert "project-local TypeScript package is unavailable" in missing_package.stderr

    missing_node = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(host / "missing-node.jsonl"),
        "--language",
        "typescript",
        "src/complexity.ts",
        cwd=host,
        env={**os.environ, "PATH": ""},
    )
    assert missing_node.returncode == 2
    assert "cannot run bundled TypeScript parser" in missing_node.stderr


def test_copied_skill_runs_without_toolkit_or_sibling_runtime(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    installed = tmp_path / "installed" / "find-complexity-hotspots"
    shutil.copytree(SKILL, installed)

    records = _run_pipeline(installed, host, isolated=True)

    _assert_typescript_outcome(records)
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
        "find-complexity-hotspots",
        "--agent",
        "codex",
        "--copy",
        "-y",
        cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1"},
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "find-complexity-hotspots"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    resolver = _documented_command(installed, "resolve")
    run = _documented_command(installed, "run")
    result = _run(
        "bash",
        "-c",
        f"{resolver}\n{run}",
        cwd=host,
        env={**os.environ, "TARGET": "src"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HOST_PYTHON=\"python3\"" in resolver

    report_dir = (host / "reports" / "find-complexity-hotspots" / "latest").resolve()
    records = _records(report_dir / "detections.jsonl")
    _assert_typescript_outcome(records)
    assert "typescript-compiler-api" in (report_dir / "report.md").read_text(encoding="utf-8")


def test_frontmatter_and_docs_name_the_narrow_typescript_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "language: any" in text
    assert "framework: any" in text
    assert "scans: [python, typescript]" in text
    assert "block-bodied arrows" in text
    assert "React/Node/ORM" in text
    assert "expression-bodied arrows" in text
