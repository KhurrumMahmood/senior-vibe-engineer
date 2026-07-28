"""Final-artifact and copied-install oracles for adapt-project TypeScript v1."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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


def _install_stock_codex_skill(host: Path) -> Path:
    install = subprocess.run(
        [
            "npx",
            "--yes",
            "skills@1.5.19",
            "add",
            str(REPO_ROOT),
            "--skill",
            "adapt-project",
            "--agent",
            "codex",
            "--copy",
            "-y",
        ],
        cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "adapt-project"
    assert installed.is_dir()
    assert {path.name for path in (host / ".agents" / "skills").iterdir()} == {"adapt-project"}
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())
    return installed


def _documented_command(skill: Path, name: str) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        rf"\s*<!-- installed-command:{name}:start -->\n\s*```bash\n(.*?)\n\s*```\n"
        rf"\s*<!-- installed-command:{name}:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None, name
    return match.group(1)


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


def test_realistic_source_directory_establishes_typescript_and_setup(tmp_path: Path) -> None:
    host = tmp_path / "typescript-host"
    _write(
        host / "package.json",
        json.dumps({"scripts": {"test": "tsc --noEmit"}}),
    )
    _write(host / "tsconfig.json", "{}\n")
    _write(host / "source" / "client.ts", "export const client = true\n")
    _write(host / "test" / "client.test.ts", "export const covered = true\n")

    adapter, _ = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)

    roots = {row["path"]: row for row in adapter["source_roots"]}
    assert adapter["stack"]["languages"] == ["typescript"]
    assert roots["source"]["typescript_files"] == 1
    assert "test" not in roots
    assert adapter["commands"]["setup"] == ["npm install"]


def test_sensitive_surface_detection_excludes_documentation_only_migration_hits(
    tmp_path: Path,
) -> None:
    host = tmp_path / "typescript-host"
    _write(host / "package.json", json.dumps({"scripts": {"test": "tsc --noEmit"}}))
    _write(host / "source" / "strip-url-auth.ts", "export const safe = true\n")
    _write(host / "documentation" / "migration-guides" / "axios.md", "# Migrate\n")

    adapter, _ = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)

    paths = [row["path"] for row in adapter["sensitive_surfaces"]]
    assert paths == ["source/strip-url-auth.ts"]


def test_pyproject_pytest_commands_are_executable_in_order(tmp_path: Path) -> None:
    host = tmp_path / "python-host"
    _write(
        host / "pyproject.toml",
        "[build-system]\nrequires = ['setuptools']\n"
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
    )
    _write(host / "requirements-dev.txt", "pytest\n")
    _write(host / "src" / "library" / "__init__.py", "VALUE = 1\n")

    adapter, _ = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)

    assert adapter["commands"]["test"] == [".venv/bin/python -m pytest"]
    assert adapter["commands"]["setup"] == [
        "python3 -m venv .venv",
        ".venv/bin/python -m pip install -r requirements-dev.txt",
    ]


@pytest.mark.parametrize(
    "pyproject",
    (
        "[project]\ndependencies = ['pytest']\n",
        "[tool.pytest.ini_options\ntestpaths = ['tests']\n",
    ),
)
def test_pytest_command_requires_valid_structured_configuration(
    tmp_path: Path, pyproject: str
) -> None:
    host = tmp_path / "python-host"
    _write(host / "pyproject.toml", pyproject)
    _write(host / "src" / "library" / "__init__.py", "VALUE = 1\n")

    adapter, _ = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)

    assert adapter["commands"]["test"] == []


def test_copied_agents_install_is_isolated_and_writes_adapter_report_and_evidence(tmp_path: Path) -> None:
    host = tmp_path / "typescript-host"
    _seed_typescript_host(host, source_files=201, excluded_files=25)
    installed = _install_stock_codex_skill(host)
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


def test_installed_documented_pipeline_is_verbatim_shell_safe(tmp_path: Path) -> None:
    host = tmp_path / "typescript-host"
    _seed_typescript_host(host, source_files=201, excluded_files=25)
    installed = _install_stock_codex_skill(host)
    command = "\n".join((
        _documented_command(installed, "discover"),
        _documented_command(installed, "check-evidence"),
    ))

    result = subprocess.run(
        ["/bin/sh", "-c", command],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    scan_dir = host / "reports" / "adapt-project" / "latest"
    assert (scan_dir / "adapter.json").is_file()
    assert "adapt-project evidence OK" in result.stdout


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


def test_timestamp_cannot_escape_the_artifact_scan_directory(tmp_path: Path) -> None:
    host = tmp_path / "host"
    artifacts = tmp_path / "artifacts"
    _seed_typescript_host(host, source_files=1)

    result = _run(
        SKILL_ROOT / "scripts" / "discover.py",
        "--project-root",
        str(host),
        "--artifact-root",
        str(artifacts),
        "--no-host-write",
        "--timestamp",
        "scan-/../../../../host/escaped-scan",
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "timestamp" in result.stderr
    assert not (host / "escaped-scan").exists()

    overlong = _run(
        SKILL_ROOT / "scripts" / "discover.py",
        "--project-root",
        str(host),
        "--artifact-root",
        str(artifacts),
        "--no-host-write",
        "--timestamp",
        "x" * 65,
        cwd=tmp_path,
    )
    assert overlong.returncode == 2
    assert "timestamp" in overlong.stderr


def test_python_django_markers_remain_framework_facts(tmp_path: Path) -> None:
    host = tmp_path / "django-host"
    _seed_python_host(host, source_files=1)
    _write(host / "manage.py", "#!/usr/bin/env python3\n")

    adapter, _ = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)

    assert adapter["stack"]["frameworks"] == ["django"]

    for marker_name, contents in (("requirements.txt", "Django>=5.0\n"), ("pyproject.toml", "[project]\nname = 'Django host'\n")):
        marker_host = tmp_path / marker_name.replace(".", "-")
        _seed_python_host(marker_host, source_files=1)
        _write(marker_host / marker_name, contents)
        marker_adapter, _ = _discover(
            SKILL_ROOT, marker_host, tmp_path / f"{marker_name}-artifacts", cwd=tmp_path,
        )
        assert marker_adapter["stack"]["frameworks"] == ["django"]


def test_installed_documented_pipeline_canonicalizes_relative_host_and_missing_artifact_root(tmp_path: Path) -> None:
    host = tmp_path / "typescript-host"
    _seed_typescript_host(host, source_files=1)
    installed = _install_stock_codex_skill(host)
    command = "\n".join((
        _documented_command(installed, "discover"),
        _documented_command(installed, "check-evidence"),
    ))

    result = subprocess.run(
        ["/bin/sh", "-c", command],
        cwd=host,
        env={**os.environ, "PROJECT_ROOT": ".", "ARTIFACT_ROOT": "artifacts/missing"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    scan_dir = host / "artifacts" / "missing" / "reports" / "adapt-project" / "latest"
    assert (scan_dir / "adapter.json").is_file()
    assert not (installed / "reports").exists()


def test_source_roots_exclude_symlinked_candidate_and_file_escapes(tmp_path: Path) -> None:
    external = tmp_path / "external"
    _seed_typescript_host(external, source_files=201)
    symlinked_candidate_host = tmp_path / "symlinked-candidate-host"
    symlinked_candidate_host.mkdir()
    (symlinked_candidate_host / "src").symlink_to(external / "src", target_is_directory=True)

    candidate_adapter, _ = _discover(
        SKILL_ROOT, symlinked_candidate_host, tmp_path / "candidate-artifacts", cwd=tmp_path,
    )
    assert all(row["path"] != "src" for row in candidate_adapter["source_roots"])

    file_escape_host = tmp_path / "file-escape-host"
    (file_escape_host / "src").mkdir(parents=True)
    _write(external / "escaped.py", "VALUE = 1\n")
    _write(external / "escaped.ts", "export const value = 1;\n")
    _write(external / "escaped.tsx", "export function Panel(): null { return null; }\n")
    _write(external / "escaped.md", "# external\n")
    for name in ("escaped.py", "escaped.ts", "escaped.tsx", "escaped.md"):
        (file_escape_host / "src" / name).symlink_to(external / name)

    file_adapter, _ = _discover(SKILL_ROOT, file_escape_host, tmp_path / "file-artifacts", cwd=tmp_path)
    source_root = _source_root(file_adapter)
    assert source_root["python_files"] == 0
    assert source_root["typescript_files"] == 0
    assert source_root["markdown_files"] == 0


def test_artifact_report_and_latest_stay_within_artifact_root(tmp_path: Path) -> None:
    host = tmp_path / "host"
    artifact_root = tmp_path / "artifacts"
    external = tmp_path / "external"
    _seed_typescript_host(host, source_files=1)
    artifact_root.mkdir()
    external.mkdir()
    (artifact_root / "reports").symlink_to(external, target_is_directory=True)

    result = _run(
        SKILL_ROOT / "scripts" / "discover.py",
        "--project-root",
        str(host),
        "--artifact-root",
        str(artifact_root),
        "--no-host-write",
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "artifact report directory" in result.stderr
    assert not (external / "adapt-project").exists()

    (artifact_root / "reports").unlink()
    reports = artifact_root / "reports" / "adapt-project"
    reports.mkdir(parents=True)
    (reports / "latest").mkdir()
    latest_result = _run(
        SKILL_ROOT / "scripts" / "discover.py",
        "--project-root",
        str(host),
        "--artifact-root",
        str(artifact_root),
        "--no-host-write",
        cwd=tmp_path,
    )
    assert latest_result.returncode == 2
    assert "latest scan link" in latest_result.stderr


def test_evidence_paths_cannot_escape_the_scan_directory(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _seed_typescript_host(host, source_files=1)
    _, scan_dir = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)
    foreign = tmp_path / "foreign"
    _write(foreign / "adapter.yml", "foreign\n")
    _write(foreign / "report.md", "foreign\n")
    link = scan_dir / "linked-report.md"
    link.symlink_to(foreign / "report.md")

    cases = (
        {"adapter": "../foreign/adapter.yml", "report": "../foreign/report.md"},
        {"adapter": str(foreign / "adapter.yml"), "report": str(foreign / "report.md")},
        {"adapter": "adapter.yml", "report": "linked-report.md"},
    )
    for evidence in cases:
        (scan_dir / "evidence.json").write_text(
            json.dumps({"skill": "adapt-project", "evidence": evidence}), encoding="utf-8",
        )
        result = _run(SKILL_ROOT / "scripts" / "check_evidence.py", "--scan-dir", str(scan_dir), cwd=tmp_path)
        assert result.returncode == 1, result.stdout + result.stderr


def test_evidence_manifest_and_adapter_cannot_be_symlink_escapes(tmp_path: Path) -> None:
    host = tmp_path / "host"
    _seed_typescript_host(host, source_files=1)
    _, scan_dir = _discover(SKILL_ROOT, host, tmp_path / "artifacts", cwd=tmp_path)
    foreign = tmp_path / "foreign"
    manifest_path = scan_dir / "evidence.json"
    manifest_contents = manifest_path.read_text(encoding="utf-8")
    _write(foreign / "evidence.json", manifest_contents)
    _write(foreign / "adapter.json", "{}\n")

    manifest_path.unlink()
    manifest_path.symlink_to(foreign / "evidence.json")
    manifest_result = _run(
        SKILL_ROOT / "scripts" / "check_evidence.py", "--scan-dir", str(scan_dir), cwd=tmp_path,
    )
    assert manifest_result.returncode == 1
    assert "evidence.json" in manifest_result.stderr

    manifest_path.unlink()
    _write(manifest_path, manifest_contents)
    adapter_path = scan_dir / "adapter.json"
    adapter_path.unlink()
    adapter_path.symlink_to(foreign / "adapter.json")
    adapter_result = _run(
        SKILL_ROOT / "scripts" / "check_evidence.py", "--scan-dir", str(scan_dir), cwd=tmp_path,
    )
    assert adapter_result.returncode == 1
    assert "adapter.json" in adapter_result.stderr
