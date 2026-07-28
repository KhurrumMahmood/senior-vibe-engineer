"""B4 TypeScript omnibus outcome and copied-install closure proof."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-omnibus"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "b4_typescript_omnibus"


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


def _write_scouts(candidates: Path, scout_dir: Path) -> None:
    scout_dir.mkdir(exist_ok=True)
    for candidate in _records(candidates):
        (scout_dir / f"{candidate['candidate_id']}.json").write_text(
            json.dumps({
                "candidate_id": candidate["candidate_id"],
                "file": candidate["file"],
                "bucket": "confirmed_omnibus",
                "domains_confirmed": ["invoice", "shipment", "customer", "inventory"],
                "facets_collapsed": [],
                "srp_rewrite": "This module handles four independent record domains.",
                "decomposition_sketch": [],
                "decomposition_depth_note": "Each domain has a separate public surface.",
                "false_positive_reason": None,
                "notes": "Locked TypeScript outcome fixture.",
                "recommendation": "decompose",
            }),
            encoding="utf-8",
        )


def _run_pipeline(skill: Path, host: Path, artifacts: Path, *, isolated: bool) -> list[dict]:
    detections = artifacts / "omnibus.jsonl"
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    detect = _run(
        *prefix,
        str(skill / "scripts" / "detect.py"),
        "--target", str(host),
        "--project-root", str(host),
        "--output", str(detections),
        "--language", "typescript",
        cwd=host,
    )
    assert detect.returncode == 0, detect.stdout + detect.stderr
    records = _records(detections)

    candidates = artifacts / "candidates.jsonl"
    collapse = _run(
        *prefix,
        str(skill / "scripts" / "collapse.py"),
        "--detections", str(detections),
        "--output", str(candidates),
        cwd=host,
    )
    assert collapse.returncode == 0, collapse.stdout + collapse.stderr
    scout_dir = artifacts / "scout"
    _write_scouts(candidates, scout_dir)
    report = _run(
        *prefix,
        str(skill / "scripts" / "report.py"),
        "--candidates", str(candidates),
        "--scout-dir", str(scout_dir),
        "--output-md", str(artifacts / "report.md"),
        "--output-json", str(artifacts / "findings.json"),
        "--scan-id", "b4-typescript",
        "--target", "src",
        cwd=host,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    findings = json.loads((artifacts / "findings.json").read_text(encoding="utf-8"))
    assert findings["summary"]["bucket_counts"]["confirmed_omnibus"] == 2
    return records


def _assert_typescript_outcome(records: list[dict]) -> None:
    assert {record["file"] for record in records} == {"src/omnibus.ts", "src/omnibus.tsx"}
    assert {record["language"] for record in records} == {"typescript"}
    assert {record["analyzer"] for record in records} == {"typescript-compiler-api"}
    assert {record["and_count"] for record in records} == {3}
    for record in records:
        clusters = {cluster["name"]: cluster["symbols"] for cluster in record["clusters"]}
        assert set(clusters) == {"invoice", "shipment", "customer", "inventory"}
        assert "saveInvoiceRecord" in clusters["invoice"]
        assert "InvoiceService" in clusters["invoice"]


def test_typescript_esm_outcome_and_explicit_skip_policy(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    records = _run_pipeline(SKILL, host, host / "reports" / "find-omnibus", isolated=False)

    _assert_typescript_outcome(records)


def test_typescript_syntax_errors_fail_clearly(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    broken = host / "src" / "broken.ts"
    broken.write_text("export function broken(: string { return ''; }\n", encoding="utf-8")
    output = host / "out.jsonl"
    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--target", str(host / "src"),
        "--project-root", str(host),
        "--output", str(output),
        "--language", "typescript",
        cwd=host,
    )

    assert result.returncode == 2
    assert "syntax error" in result.stderr


def test_copied_skill_is_self_contained_for_typescript_pipeline(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    installed = tmp_path / "installed" / "find-omnibus"
    shutil.copytree(SKILL, installed)

    records = _run_pipeline(installed, host, host / "reports" / "copied", isolated=True)

    _assert_typescript_outcome(records)
    assert "scripts/_lib" not in (installed / "scripts" / "detect.py").read_text(encoding="utf-8")


def test_frontmatter_truthfully_declares_all_supported_scanners() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    scans = set(text.split("scans: [", 1)[1].split("]", 1)[0].split(", "))

    assert "language: any" in text
    assert {
        "python", "javascript", "typescript", "go", "java", "php", "ruby",
        "rust", "dart", "swift",
    } <= scans
    assert "JavaScript/TypeScript" in text


def test_documented_resolver_supports_source_tree_without_path_translation() -> None:
    resolver = _documented_command(SKILL, "resolve")
    result = _run(
        "bash",
        "-c",
        f'{resolver}\nprintf "%s\\n" "$SKILL_ROOT"',
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[-1] == str(SKILL.resolve())


def test_selected_skill_scout_context_has_no_external_runtime_dependency() -> None:
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            SKILL / "SKILL.md",
            SKILL / "agents" / "verify.md",
            SKILL / "knowledge" / "verification.md",
        )
    )

    for forbidden in (
        "dispatch_scout_cheap",
        "tools/code_agent",
        "../_common",
        ".claude/skills/find-omnibus/scripts/",
        "subagent_type=",
    ):
        assert forbidden not in closure
    assert "standard sub-agent capability" in closure
    assert "complete bundled false-positive list" in closure


def test_selected_skill_installs_with_pinned_stock_cli(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = subprocess.run(
        [
            "npx", "--yes", "skills@1.5.19", "add", str(REPO_ROOT),
            "--skill", "find-omnibus", "--agent", "codex", "--copy", "-y",
        ],
        cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "find-omnibus"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    commands = {
        name: _documented_command(installed, name)
        for name in ("resolve", "setup", "detect", "collapse", "report")
    }
    command_env = {
        **os.environ,
        "TARGET": "src",
        "ENGINEERING_SKILLS_PYTHON": sys.executable,
    }
    for stage in ("setup", "detect", "collapse"):
        result = _run(
            "bash",
            "-c",
            f"{commands['resolve']}\n{commands[stage]}",
            cwd=host,
            env=command_env,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    report_dir = (host / "reports" / "omnibus" / "latest").resolve()
    candidates = report_dir / "candidates.jsonl"
    _write_scouts(candidates, report_dir / "scout")
    render = _run(
        "bash",
        "-c",
        f"{commands['resolve']}\n{commands['report']}",
        cwd=host,
        env=command_env,
    )
    assert render.returncode == 0, render.stdout + render.stderr

    records = _records(report_dir / "omnibus.jsonl")
    findings = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))

    _assert_typescript_outcome(records)
    assert findings["summary"]["bucket_counts"]["confirmed_omnibus"] == 2
    assert (report_dir / "report.md").is_file()
    assert len(list((report_dir / "scout").glob("*.json"))) == 2
    assert ".agents/skills/find-omnibus" in commands["resolve"]
