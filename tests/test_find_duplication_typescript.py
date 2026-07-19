from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-duplication"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "find-duplication-typescript"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _load_typescript_collapse():
    script = SKILL / "scripts" / "collapse_typescript.py"
    spec = importlib.util.spec_from_file_location("collapse_typescript_under_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "typescript-host", host)
    return host


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_fake_npx(path: Path, report: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "pathlib.Path(sys.argv[0] + '.args').write_text(json.dumps(args))\n"
        "output = pathlib.Path(args[args.index('--output') + 1])\n"
        "output.mkdir(parents=True, exist_ok=True)\n"
        f"payload = json.loads(pathlib.Path({report.as_posix()!r}).read_text())\n"
        "for duplicate in payload.get('duplicates', []):\n"
        "    for key in ('firstFile', 'secondFile'):\n"
        "        duplicate[key]['name'] = duplicate[key]['name'].removeprefix('src/')\n"
        "(output / 'jscpd-report.json').write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_python_reference_oracle_is_stable_and_keeps_different_code_clean(tmp_path: Path) -> None:
    installed = tmp_path / "installed" / "find-duplication"
    shutil.copytree(SKILL, installed)
    report = FIXTURES / "python-oracle" / "jscpd-report.json"
    result = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "collapse.py"),
        "--jscpd-report",
        str(report),
        "--ast-findings",
        str(FIXTURES / "python-oracle" / "empty-ast-findings.json"),
        "--target",
        str(FIXTURES / "python-oracle"),
        "--project-root",
        str(FIXTURES / "python-oracle"),
        "--output",
        str(tmp_path / "collapsed.json"),
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    findings = json.loads((tmp_path / "collapsed.json").read_text())
    assert len(findings["findings"]) == 1
    assert {site["method"] for site in findings["findings"][0]["sites"]} == {
        "summarize_queued_entries",
        "summarize_pending_entries",
    }
    assert all("different.py" not in site["file"] for site in findings["findings"][0]["sites"])


def test_span_mapper_keeps_object_return_type_out_of_the_function_body_boundary() -> None:
    collapse = _load_typescript_collapse()
    spans = collapse.symbols_in_source(
        """\
export function buildQueue(value: string): { labels: string[] } {
    return { labels: [value] };
}

export function toKey(value: string): string;
export function toKey(value: number): string;
export function toKey(value: string | number): string {
    return String(value);
}
"""
    )
    assert [(span.symbol, span.start_line, span.end_line, span.overload_signature) for span in spans] == [
        ("buildQueue", 1, 3, False),
        ("toKey", 5, 5, True),
        ("toKey", 6, 6, True),
        ("toKey", 7, 9, False),
    ]


def test_typescript_final_triage_is_read_only_and_filters_known_boundaries(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    source_before = _tree_hashes(host)
    jscpd_report = FIXTURES / "typescript-host" / "expected-jscpd-report.json"
    collapsed = tmp_path / "collapsed.json"
    ranked = tmp_path / "ranked.json"
    triage = tmp_path / "triage.md"
    findings_json = tmp_path / "findings.json"

    detect = _run(
        sys.executable,
        str(SKILL / "scripts" / "collapse_typescript.py"),
        "--jscpd-report",
        str(jscpd_report),
        "--target",
        str(host / "src"),
        "--project-root",
        str(host),
        "--output",
        str(collapsed),
        cwd=host,
    )
    assert detect.returncode == 0, detect.stdout + detect.stderr
    rank = _run(
        sys.executable,
        str(SKILL / "scripts" / "rank.py"),
        "--input",
        str(collapsed),
        "--output",
        str(ranked),
        cwd=host,
    )
    assert rank.returncode == 0, rank.stdout + rank.stderr
    render = _run(
        sys.executable,
        str(SKILL / "scripts" / "report.py"),
        "--input",
        str(ranked),
        "--output-md",
        str(triage),
        "--output-json",
        str(findings_json),
        "--scan-id",
        "typescript-fixture",
        cwd=host,
    )
    assert render.returncode == 0, render.stdout + render.stderr

    findings = json.loads(findings_json.read_text(encoding="utf-8"))
    assert findings["scan_meta"]["language"] == "typescript"
    assert findings["scan_meta"]["filter_reasons"] == {
        "excluded_path": 3,
        "overload_signature": 1,
    }
    assert len(findings["findings"]) == 1
    finding = findings["findings"][0]
    assert finding["source"] == "jscpd-typescript"
    assert {site["symbol"] for site in finding["sites"]} == {
        "summarizeQueuedEntries",
        "summarizePendingEntries",
    }
    assert {site["file"] for site in finding["sites"]} == {
        "src/queue_one.ts",
        "src/queue_two.ts",
    }
    assert all(site["start_line"] <= site["end_line"] for site in finding["sites"])
    assert "Do not consolidate automatically" in triage.read_text(encoding="utf-8")
    assert _tree_hashes(host) == source_before


def test_family_local_offline_runner_and_copied_install_closure(tmp_path: Path) -> None:
    installed = tmp_path / "installed" / "find-duplication"
    shutil.copytree(SKILL, installed)
    host = _copy_host(tmp_path)
    fake_npx = tmp_path / "fake-npx"
    _write_fake_npx(fake_npx, FIXTURES / "typescript-host" / "expected-jscpd-report.json")
    report_dir = tmp_path / "report"

    runner = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "run_jscpd.py"),
        "--target",
        str(host / "src"),
        "--output",
        str(report_dir / "jscpd"),
        "--npx-bin",
        str(fake_npx),
        cwd=host,
    )
    assert runner.returncode == 0, runner.stdout + runner.stderr
    invoked = json.loads((Path(f"{fake_npx}.args")).read_text(encoding="utf-8"))
    assert "--offline" in invoked
    assert "jscpd@4.0.5" in invoked

    collapse = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "collapse_typescript.py"),
        "--jscpd-report",
        str(report_dir / "jscpd" / "jscpd-report.json"),
        "--target",
        str(host / "src"),
        "--project-root",
        str(host),
        "--output",
        str(report_dir / "collapsed.json"),
        cwd=host,
    )
    assert collapse.returncode == 0, collapse.stdout + collapse.stderr
    rank = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "rank.py"),
        "--input",
        str(report_dir / "collapsed.json"),
        "--output",
        str(report_dir / "ranked.json"),
        cwd=host,
    )
    assert rank.returncode == 0, rank.stdout + rank.stderr
    report = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "report.py"),
        "--input",
        str(report_dir / "ranked.json"),
        "--output-md",
        str(report_dir / "triage.md"),
        "--output-json",
        str(report_dir / "findings.json"),
        "--scan-id",
        "installed",
        cwd=host,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    assert json.loads((report_dir / "findings.json").read_text())["findings"]


def test_offline_runner_fails_clearly_without_the_pinned_cache(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "run_jscpd.py"),
        "--target",
        str(host / "src"),
        "--output",
        str(tmp_path / "output"),
        "--npx-bin",
        str(tmp_path / "missing-npx"),
        cwd=host,
    )
    assert result.returncode == 3
    assert "pinned jscpd@4.0.5 is unavailable offline" in result.stderr
