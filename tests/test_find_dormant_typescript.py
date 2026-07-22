"""TypeScript find-dormant final-report, containment, and closure proof."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-dormant"
SCRIPT = SKILL / "scripts" / "detect_typescript_dormant.mjs"
PYTHON_DETECTOR = SKILL / "scripts" / "detect_unreferenced.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-dormant-typescript"


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


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
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
    *,
    target: str = "src",
    report_name: str = "typescript-scan",
    tsconfig: str = "tsconfig.json",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    report_dir = host / "reports" / "find-dormant" / report_name
    result = _run(
        "node",
        str(skill / "scripts" / "detect_typescript_dormant.mjs"),
        "--target",
        target,
        "--project-root",
        str(host),
        "--tsconfig",
        tsconfig,
        "--report-dir",
        str(report_dir),
        cwd=host,
    )
    return result, report_dir


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


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        str(path.relative_to(host)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((host / "src").rglob("*.ts*"))
    }


def test_python_detector_oracle_retains_positive_negative_and_dynamic_boundaries(tmp_path: Path) -> None:
    host = tmp_path / "python-host"
    source = host / "src" / "sample.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def unused():\n"
        "    return 1\n\n"
        "def used():\n"
        "    return 2\n\n"
        "value = used()\n\n"
        "@receiver\n"
        "def framework_callback():\n"
        "    return 3\n",
        encoding="utf-8",
    )
    init = _run("git", "init", cwd=host)
    assert init.returncode == 0, init.stdout + init.stderr
    add = _run("git", "add", "src/sample.py", cwd=host)
    assert add.returncode == 0, add.stdout + add.stderr
    output = host / "report.jsonl"

    result = _run(
        sys.executable,
        str(PYTHON_DETECTOR),
        "--target",
        str(host / "src"),
        "--project-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert records == [{
        "type": "unreferenced_def",
        "file": "src/sample.py",
        "line": 1,
        "name": "unused",
        "qualified_name": "unused",
        "kind": "function",
        "url_wired_hint": False,
        "url_wire_files": [],
    }]


def test_typescript_final_report_is_conservative_and_reaches_the_output_boundary(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_hashes(host)
    result, report_dir = _scan(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    report = report_dir / "report.md"
    evidence = report_dir / "findings.json"
    assert report.is_file()
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert payload["language"] == "typescript"
    assert payload["analyzer"] == "typescript-compiler-api"
    assert payload["summary"] == {
        "review_required": 1,
        "uncertain": 1,
        "certain_delete": 0,
    }
    assert payload["candidates"] == [{
        "id": "src-dormant-ts-unusedPrivate-1",
        "file": "src/dormant.ts",
        "line": 1,
        "name": "unusedPrivate",
        "kind": "function",
        "static_references": 0,
        "verdict": "review_required",
        "recommendation": "human_review_only",
        "uncertainty": [
            "Static analysis cannot establish dynamic, external, registry, event, or framework reachability.",
        ],
    }]
    assert payload["uncertain_symbols"] == [{
        "file": "src/dormant.ts",
        "line": 18,
        "name": "dynamicByName",
        "kind": "variable_function",
        "reason": "A matching string literal may be dynamic reachability; static analysis cannot resolve it.",
        "verdict": "uncertain",
    }]
    assert "unusedPrivate" in report.read_text(encoding="utf-8")
    assert "Never safe deletion" in report.read_text(encoding="utf-8")
    assert _source_hashes(host) == before


def test_typescript_missing_invalid_and_unresolved_project_states_are_explicit(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "unresolved.ts").write_text(
        'import { missing } from "@app/missing";\nexport const value = missing;\n',
        encoding="utf-8",
    )
    partial, report_dir = _scan(SKILL, host, report_name="partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    payload = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["project_resolution"]["state"] == "partial"
    assert payload["project_resolution"]["unresolved_modules"] == [{
        "file": "src/unresolved.ts",
        "specifier": "@app/missing",
    }]
    assert payload["summary"]["certain_delete"] == 0

    (host / "src" / "broken.ts").write_text(
        "function broken(: string { return ''; }\n", encoding="utf-8"
    )
    syntax, _ = _scan(SKILL, host, target="src/broken.ts", report_name="syntax")
    assert syntax.returncode == 2
    assert "TypeScript syntax errors" in syntax.stderr

    missing_config, _ = _scan(SKILL, host, tsconfig="missing.json", report_name="missing-config")
    assert missing_config.returncode == 2
    assert "project-local TypeScript requires tsconfig" in missing_config.stderr

    no_compiler = tmp_path / "no-compiler"
    shutil.copytree(FIXTURE / "host", no_compiler, ignore=shutil.ignore_patterns("node_modules"))
    missing_compiler, _ = _scan(SKILL, no_compiler, report_name="missing-compiler")
    assert missing_compiler.returncode == 2
    assert "project-local TypeScript package is unavailable" in missing_compiler.stderr


def test_typescript_exclusions_and_symlinks_are_project_relative_and_safe(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    source = host / "src" / "dormant.ts"
    excluded_targets = ("src/generated", "src/vendor", "src/dormant.spec.ts")

    for index, target in enumerate(excluded_targets):
        result, report_dir = _scan(SKILL, host, target=target, report_name=f"excluded-{index}")
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
        assert payload["target"]["exclusion"] == "excluded"
        assert payload["candidates"] == []

    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.ts").write_text("function outside(): void {}\n", encoding="utf-8")
    os.symlink(external, host / "src" / "external-link")
    os.symlink(host / "src" / "vendor", host / "src" / "internal-link")

    broad, broad_dir = _scan(SKILL, host, report_name="symlink-broad")
    assert broad.returncode == 0, broad.stdout + broad.stderr
    broad_payload = json.loads((broad_dir / "findings.json").read_text(encoding="utf-8"))
    assert {candidate["name"] for candidate in broad_payload["candidates"]} == {"unusedPrivate"}

    for index, target in enumerate(("src/external-link", "src/internal-link")):
        direct, _ = _scan(SKILL, host, target=target, report_name=f"symlink-direct-{index}")
        assert direct.returncode == 2
        assert "symbolic link" in direct.stderr

    before = _source_hashes(host)
    shutil.rmtree(host / "reports")
    os.symlink(host / "src", host / "reports")
    unsafe, _ = _scan(SKILL, host, report_name="unsafe-artifact")
    assert unsafe.returncode == 2
    assert "symbolic link" in unsafe.stderr
    assert _source_hashes(host) == before
    assert source.read_bytes() == (FIXTURE / "host" / "src" / "dormant.ts").read_bytes()


def test_copied_typescript_skill_and_stock_install_have_no_checkout_runtime(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_hashes(host)
    copied = tmp_path / "installed" / "find-dormant"
    shutil.copytree(SKILL, copied)

    copied_result, copied_dir = _scan(copied, host, report_name="copied")
    assert copied_result.returncode == 0, copied_result.stdout + copied_result.stderr
    assert json.loads((copied_dir / "findings.json").read_text(encoding="utf-8"))["summary"]["certain_delete"] == 0
    copied_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (copied / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in copied_runtime
    assert "/_common" not in copied_runtime
    assert _source_hashes(host) == before

    install = _run(
        "bash",
        "-c",
        _documented_command(SKILL, "stock-install"),
        cwd=host,
        env={
            **os.environ,
            "DO_NOT_TRACK": "1",
            "FIND_DORMANT_SOURCE": str(REPO_ROOT),
        },
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "find-dormant"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    command = _documented_command(installed, "typescript-scan")
    stock = _run(
        "bash",
        "-c",
        command,
        cwd=host,
        env={**os.environ, "TARGET": "src", "REPORT_NAME": "stock"},
    )
    assert stock.returncode == 0, stock.stdout + stock.stderr
    payload = json.loads((host / "reports" / "find-dormant" / "stock" / "findings.json").read_text(encoding="utf-8"))
    assert payload["summary"]["certain_delete"] == 0
    assert str(REPO_ROOT) not in installed.joinpath("scripts", "detect_typescript_dormant.mjs").read_text(encoding="utf-8")
    typecheck = _run("npm", "run", "typecheck", cwd=host)
    native = _run("npm", "test", cwd=host)
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    assert native.returncode == 0, native.stdout + native.stderr
    assert _source_hashes(host) == before


def test_frontmatter_and_docs_state_the_narrow_typescript_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "language: any" in text
    assert "framework: any" in text
    assert "scans: [python, typescript]" in text
    assert "never infer safe deletion" in text
    assert "registry, event, and framework" in text
