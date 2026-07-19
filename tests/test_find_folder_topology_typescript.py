from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-folder-topology-drift"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "find-folder-topology-typescript"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURES / "typescript-host", host)
    return host


def _detect(
    script_root: Path,
    host: Path,
    output: Path,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(script_root / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(output),
        *extra,
        cwd=host,
    )


def test_python_bands_survive_the_self_contained_detector(tmp_path: Path) -> None:
    host = tmp_path / "python-host"
    shutil.copytree(FIXTURES / "python-reference" / "positive", host)

    detections = host / "reports" / "python.jsonl"
    result = _detect(SKILL, host, detections, "--root", "src")

    assert result.returncode == 0, result.stdout + result.stderr
    records = _read_jsonl(detections)
    assert {record["pattern"] for record in records} == {
        "flat_prefix_cluster",
        "tests_by_prefix",
        "sparse_folder_package",
        "pages_route_mirror",
    }
    assert all(record.get("language", "python") == "python" for record in records)


def test_python_negative_and_framework_must_not_fire_fixture_stays_clean(tmp_path: Path) -> None:
    host = tmp_path / "python-clean-host"
    shutil.copytree(FIXTURES / "python-reference" / "clean", host)
    detections = host / "reports" / "python-clean.jsonl"

    result = _detect(SKILL, host, detections, "--root", "src")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _read_jsonl(detections) == []


def test_typescript_flat_prefix_final_artifacts_are_narrow_and_read_only(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    source_before = _tree_hashes(host / "src")
    report_dir = host / "reports" / "find-folder-topology-drift" / "typescript-fixture"
    detections = report_dir / "detections.jsonl"
    report = report_dir / "report.md"
    findings_path = report_dir / "findings.json"

    no_typescript_root = _detect(SKILL, host, report_dir / "python-only.jsonl", "--root", "src")
    assert no_typescript_root.returncode == 0, no_typescript_root.stdout + no_typescript_root.stderr
    assert _read_jsonl(report_dir / "python-only.jsonl") == []

    detect = _detect(SKILL, host, detections, "--typescript-root", "src")
    assert detect.returncode == 0, detect.stdout + detect.stderr
    records = _read_jsonl(detections)
    assert len(records) == 1
    assert records[0]["language"] == "typescript"
    assert records[0]["pattern"] == "flat_prefix_cluster"
    assert records[0]["prefix"] == "billing"
    assert records[0]["files"] == [
        "src/billing/billing-types.ts",
        "src/billing/billing-validator.ts",
        "src/billing/billing_parser.ts",
    ]

    render = _run(
        sys.executable,
        "-I",
        "-S",
        str(SKILL / "scripts" / "report.py"),
        "--detections",
        str(detections),
        "--output-md",
        str(report),
        "--output-json",
        str(findings_path),
        "--target",
        "src",
        "--language",
        "typescript",
        cwd=host,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    assert "**Language:** `typescript`" in report.read_text(encoding="utf-8")
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    assert findings["scan_meta"] == {
        "language": "typescript",
        "supported_patterns": ["flat_prefix_cluster"],
        "target": "src",
    }
    assert findings["summary"]["findings_total"] == 1
    assert findings["findings"] == records
    assert _tree_hashes(host / "src") == source_before


def test_typescript_excludes_and_declared_additive_excludes_stay_clean(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    ignored = host / "src" / "ignored"
    ignored.mkdir()
    for name in ("legacy_a.ts", "legacy-b.ts", "legacy-c.ts"):
        (ignored / name).write_text("export {};\n", encoding="utf-8")

    detections = host / "detections.jsonl"
    result = _detect(
        SKILL,
        host,
        detections,
        "--typescript-root",
        "src",
        "--exclude",
        "src/ignored",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    records = _read_jsonl(detections)
    assert len(records) == 1
    assert records[0]["file"] == "src/billing"
    assert all("ignored" not in file for file in records[0]["files"])


def test_copied_stock_skill_runs_from_an_unrelated_cwd_without_common_helpers(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed" / "find-folder-topology-drift"
    shutil.copytree(SKILL, installed)
    host = _copy_host(tmp_path)
    report_dir = host / "reports" / "folder-topology" / "installed"
    detections = report_dir / "detections.jsonl"
    report = report_dir / "report.md"
    findings_path = report_dir / "findings.json"

    detect = _detect(installed, host, detections, "--typescript-root", "src")
    assert detect.returncode == 0, detect.stdout + detect.stderr
    render = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "report.py"),
        "--detections",
        str(detections),
        "--output-md",
        str(report),
        "--output-json",
        str(findings_path),
        "--target",
        "src",
        "--language",
        "typescript",
        cwd=tmp_path,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    assert json.loads(findings_path.read_text(encoding="utf-8"))["findings"][0]["language"] == "typescript"
    assert all("_common" not in path.read_text(encoding="utf-8") for path in installed.rglob("*.py"))
