"""Final-artifact and copied-install oracles for adapt-project TypeScript v1."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / ".claude" / "skills" / "adapt-project"
SEED_HOST = REPO_ROOT / "tests" / "fixtures" / "adapt-project-typescript" / "seed_host.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_typescript_host(root: Path, *, source_files: int, excluded_files: int = 0) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SEED_HOST),
            "--destination",
            str(root),
            "--source-files",
            str(source_files),
            "--excluded-files",
            str(excluded_files),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _seed_python_host(root: Path, *, source_files: int) -> None:
    for index in range(source_files):
        _write(root / "src" / "services" / f"source_{index:03d}.py", "VALUE = 1\n")


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_native_package_checks(host: Path) -> None:
    install = subprocess.run(
        ["npm", "ci", "--offline", "--ignore-scripts"],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    typecheck = subprocess.run(
        ["npm", "run", "typecheck"], cwd=host, capture_output=True, text=True, check=False,
    )
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    native_test = subprocess.run(
        ["npm", "test"], cwd=host, capture_output=True, text=True, check=False,
    )
    assert native_test.returncode == 0, native_test.stdout + native_test.stderr


def _discover(skill_root: Path, host: Path, artifacts: Path, *, cwd: Path) -> tuple[dict, Path]:
    result = _run(
        skill_root / "scripts" / "discover.py",
        "--project-root",
        str(host),
        "--artifact-root",
        str(artifacts),
        "--no-host-write",
        "--timestamp",
        "20260719-120000",
        cwd=cwd,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    scan_dir = Path(result.stdout.strip())
    return json.loads((scan_dir / "adapter.json").read_text(encoding="utf-8")), scan_dir


def _source_root(adapter: dict, name: str = "src") -> dict:
    return next(row for row in adapter["source_roots"] if row["path"] == name)


def test_python_reference_size_caution_is_preserved_in_final_adapter_and_report(tmp_path: Path) -> None:
    host = tmp_path / "python-host"
    _seed_python_host(host, source_files=201)

    adapter, scan_dir = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)

    source_root = _source_root(adapter)
    assert source_root["python_files"] == 201
    assert source_root["typescript_files"] == 0
    assert source_root["source_languages"] == ["python"]
    assert adapter["stack"]["languages"] == []
    assert "Large source roots may contain mixed-quality legacy code; extract exemplars selectively." in (
        adapter["standardization"]["cautions"]
    )
    assert "src — Python: 201; TypeScript: 0" in (scan_dir / "report.md").read_text(encoding="utf-8")


def test_python_reference_boundary_and_common_ignored_tree_stay_out_of_caution(tmp_path: Path) -> None:
    boundary_host = tmp_path / "python-boundary-host"
    _seed_python_host(boundary_host, source_files=200)
    boundary_adapter, _ = _discover(SKILL_ROOT, boundary_host, tmp_path / "boundary-artifacts", cwd=tmp_path)
    assert "Large source roots may contain mixed-quality legacy code; extract exemplars selectively." not in (
        boundary_adapter["standardization"]["cautions"]
    )

    ignored_host = tmp_path / "python-ignored-host"
    for index in range(250):
        _write(ignored_host / "src" / "node_modules" / "dependency" / f"ignored_{index:03d}.py", "VALUE = 1\n")
    ignored_adapter, _ = _discover(SKILL_ROOT, ignored_host, tmp_path / "ignored-artifacts", cwd=tmp_path)
    source_root = _source_root(ignored_adapter)
    assert source_root["python_files"] == 0
    assert source_root["source_languages"] == []
    assert "Large source roots may contain mixed-quality legacy code; extract exemplars selectively." not in (
        ignored_adapter["standardization"]["cautions"]
    )


def test_large_ts_and_tsx_root_triggers_same_caution_and_excludes_non_source_trees(tmp_path: Path) -> None:
    host = tmp_path / "typescript-host"
    _seed_typescript_host(host, source_files=201, excluded_files=75)
    _run_native_package_checks(host)

    adapter, scan_dir = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)

    source_root = _source_root(adapter)
    assert source_root == {
        "path": "src",
        "python_files": 0,
        "typescript_files": 201,
        "typescript_file_kinds": {"ts": 101, "tsx": 100},
        "markdown_files": 0,
        "source_languages": ["typescript"],
    }
    assert adapter["stack"]["languages"] == ["typescript"]
    assert adapter["stack"]["frameworks"] == []
    assert "Large source roots may contain mixed-quality legacy code; extract exemplars selectively." in (
        adapter["standardization"]["cautions"]
    )
    report = (scan_dir / "report.md").read_text(encoding="utf-8")
    assert "src — Python: 0; TypeScript: 201 (101 .ts, 100 .tsx)" in report
    assert "node_modules" not in report


def test_type_script_size_boundary_and_exclusion_only_root_do_not_raise_large_source_caution(tmp_path: Path) -> None:
    boundary_host = tmp_path / "boundary-host"
    _seed_typescript_host(boundary_host, source_files=200)
    boundary_adapter, _ = _discover(SKILL_ROOT, boundary_host, tmp_path / "boundary-artifacts", cwd=tmp_path)
    assert "Large source roots may contain mixed-quality legacy code; extract exemplars selectively." not in (
        boundary_adapter["standardization"]["cautions"]
    )

    excluded_only_host = tmp_path / "excluded-only-host"
    _seed_typescript_host(excluded_only_host, source_files=0, excluded_files=250)
    excluded_adapter, _ = _discover(SKILL_ROOT, excluded_only_host, tmp_path / "excluded-artifacts", cwd=tmp_path)
    source_root = _source_root(excluded_adapter)
    assert source_root["typescript_files"] == 0
    assert source_root["source_languages"] == []
    assert "Large source roots may contain mixed-quality legacy code; extract exemplars selectively." not in (
        excluded_adapter["standardization"]["cautions"]
    )


def test_copied_agents_install_is_isolated_and_writes_adapter_report_and_evidence(tmp_path: Path) -> None:
    host = tmp_path / "typescript-host"
    _seed_typescript_host(host, source_files=201, excluded_files=25)
    installed = host / ".agents" / "skills" / "adapt-project"
    shutil.copytree(SKILL_ROOT, installed)
    artifacts = tmp_path / "artifacts"

    adapter, scan_dir = _discover(installed, host, artifacts, cwd=tmp_path)
    check = _run(installed / "scripts" / "check_evidence.py", "--scan-dir", str(scan_dir), cwd=tmp_path)

    assert check.returncode == 0, check.stdout + check.stderr
    assert (scan_dir / "adapter.yml").is_file()
    assert (scan_dir / "adapter.json").is_file()
    assert (scan_dir / "report.md").is_file()
    assert (scan_dir / "evidence.json").is_file()
    assert adapter["stack"]["frameworks"] == []
    assert not (host / ".engineering" / "project" / "adapter.yml").exists()


def test_default_artifact_root_is_the_requested_host_not_the_installed_skill_directory(tmp_path: Path) -> None:
    host = tmp_path / "typescript-host"
    _seed_typescript_host(host, source_files=1)
    installed = host / ".agents" / "skills" / "adapt-project"
    shutil.copytree(SKILL_ROOT, installed)

    result = _run(
        installed / "scripts" / "discover.py",
        "--project-root",
        str(host),
        "--timestamp",
        "20260719-121501",
        cwd=installed,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    scan_dir = Path(result.stdout.strip())
    assert scan_dir == host / "reports" / "adapt-project" / "scan-20260719-121501"
    assert (scan_dir / "report.md").is_file()
    assert not (installed / "reports").exists()
