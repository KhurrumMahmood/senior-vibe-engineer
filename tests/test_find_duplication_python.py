from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-duplication"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-duplication-python"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.py"))
        if "reports" not in path.parts
    }


def _write_fake_npx(path: Path) -> None:
    report = FIXTURE / "expected-jscpd-report.json"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "output = pathlib.Path(args[args.index('--output') + 1])\n"
        f"payload = json.loads(pathlib.Path({report.as_posix()!r}).read_text())\n"
        "output.mkdir(parents=True, exist_ok=True)\n"
        "(output / 'jscpd-report.json').write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_copied_python_pipeline_preserves_legacy_scout_triage(tmp_path: Path) -> None:
    installed = tmp_path / "installed" / "find-duplication"
    shutil.copytree(SKILL, installed)
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    source_before = _source_hashes(host)
    fake_npx = tmp_path / "fake-npx"
    _write_fake_npx(fake_npx)
    report = host / "reports" / "duplication" / "python-installed"
    report.mkdir(parents=True)
    skill_text = (installed / "SKILL.md").read_text()
    assert "language: any" in skill_text
    assert "framework: any" in skill_text
    assert "scans: [python, javascript, typescript, go, java]" in skill_text
    assert "Python legacy triage branch" in skill_text
    assert "TypeScript lexical-evidence branch" in skill_text

    lexical = _run(
        "python3",
        "-I",
        "-S",
        str(installed / "scripts" / "run_jscpd_python.py"),
        "--target",
        str(host),
        "--output",
        str(report / "jscpd"),
        "--npx-bin",
        str(fake_npx),
        cwd=host,
    )
    assert lexical.returncode == 0, lexical.stdout + lexical.stderr
    ast_detect = _run(
        "python3",
        "-I",
        "-S",
        str(installed / "scripts" / "detect_python.py"),
        str(host),
        "--project-root",
        str(host),
        "--output",
        str(report / "ast-findings.json"),
        cwd=host,
    )
    assert ast_detect.returncode == 0, ast_detect.stdout + ast_detect.stderr
    collapse = _run(
        "python3",
        "-I",
        "-S",
        str(installed / "scripts" / "collapse.py"),
        "--jscpd-report",
        str(report / "jscpd" / "jscpd-report.json"),
        "--ast-findings",
        str(report / "ast-findings.json"),
        "--target",
        str(host),
        "--project-root",
        str(host),
        "--output",
        str(report / "collapsed.json"),
        cwd=host,
    )
    assert collapse.returncode == 0, collapse.stdout + collapse.stderr
    rank = _run(
        "python3",
        "-I",
        "-S",
        str(installed / "scripts" / "rank.py"),
        "--input",
        str(report / "collapsed.json"),
        "--output",
        str(report / "ranked.json"),
        cwd=host,
    )
    assert rank.returncode == 0, rank.stdout + rank.stderr
    render = _run(
        "python3",
        "-I",
        "-S",
        str(installed / "scripts" / "report.py"),
        "--input",
        str(report / "ranked.json"),
        "--classified",
        str(FIXTURE / "classified.json"),
        "--output-md",
        str(report / "triage.md"),
        "--output-json",
        str(report / "findings.json"),
        "--scan-id",
        "python-installed",
        cwd=host,
    )
    assert render.returncode == 0, render.stdout + render.stderr

    run_meta = json.loads((report / "jscpd" / "run.json").read_text())
    assert run_meta["eligible_sources"] == [
        str(host / "app" / "different.py"),
        str(host / "app" / "first.py"),
        str(host / "app" / "second.py"),
    ]
    ast_findings = json.loads((report / "ast-findings.json").read_text())
    assert all(
        "tests/" not in json.dumps(value) and "migrations/" not in json.dumps(value)
        for key, value in ast_findings.items()
        if key != "summary"
    )
    collapsed = json.loads((report / "collapsed.json").read_text())
    assert collapsed["scan_meta"]["jscpd_filtered_pair_count"] == 2
    assert len(collapsed["findings"]) == 1
    final = json.loads((report / "findings.json").read_text())
    assert len(final["findings"]) == 1
    finding = final["findings"][0]
    assert {site["file"] for site in finding["sites"]} == {
        "app/first.py",
        "app/second.py",
    }
    assert finding["classification"]["fix_shape"] == "extract_helper"
    assert final["dormant_candidates"] == []
    triage = (report / "triage.md").read_text()
    assert "**Recommended fix shape:** extract_helper" in triage
    assert f"/fix-workflow cluster:{finding['finding_id']}" in triage
    assert "different.py" not in triage
    assert "test_clone.py" not in triage
    assert "0001_clone.py" not in triage
    assert (installed / "agents" / "investigate.md").is_file()
    assert (installed / "knowledge" / "false-positives.md").is_file()
    assert _source_hashes(host) == source_before


def test_copied_python_runner_preserves_explicit_ast_only_fallback(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed" / "find-duplication"
    shutil.copytree(SKILL, installed)
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    output = tmp_path / "report" / "jscpd"

    result = _run(
        "python3",
        "-I",
        "-S",
        str(installed / "scripts" / "run_jscpd_python.py"),
        "--target",
        str(host),
        "--output",
        str(output),
        "--npx-bin",
        str(tmp_path / "missing-npx"),
        "--offline-ok",
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "jscpd-report.json").read_text())
    assert report["duplicates"] == []
    assert report["run"]["status"] == "skipped_lexical"
    assert (output / "skipped-lexical.json").is_file()
