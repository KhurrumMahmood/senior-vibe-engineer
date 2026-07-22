"""Final-artifact and selected-install proof for TypeScript semantic duplication."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-semantic-duplication"
SCRIPT = SKILL / "scripts" / "detect_typescript.mjs"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-semantic-duplication-typescript" / "host"


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert install.returncode == 0, install.stdout + install.stderr
    native = _run("npm", "run", "typecheck", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    return host


def _scan(
    skill: Path,
    host: Path,
    target: str = "src",
    *,
    report_name: str = "typescript-scan",
    tsconfig: str = "tsconfig.json",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    report_dir = host / "reports" / "semantic-duplication" / report_name
    result = _run(
        "node",
        str(skill / "scripts" / "detect_typescript.mjs"),
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


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_digest(host: Path) -> str:
    digest = hashlib.sha256()
    for source in sorted((host / "src").rglob("*")):
        if source.is_file():
            digest.update(source.relative_to(host).as_posix().encode())
            digest.update(source.read_bytes())
    return digest.hexdigest()


def _documented_command(skill: Path, name: str) -> str:
    content = (skill / "SKILL.md").read_text(encoding="utf-8")
    start = f"<!-- installed-command:{name}:start -->"
    end = f"<!-- installed-command:{name}:end -->"
    return content.split(start, 1)[1].split(end, 1)[0].split("```bash", 1)[1].split("```", 1)[0].strip()


def test_typescript_semantic_triage_preserves_all_verdicts_and_source(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_digest(host)
    result, report_dir = _scan(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _load(report_dir / "findings.json")
    assert payload["capability_matrix"]["function_level_typed_candidates"] == "available"
    assert payload["capability_matrix"]["workflow_or_structural_analysis"] == "unavailable"
    assert [finding["finding_id"] for finding in payload["confirmed"]] == ["TS-SD-0001"]
    confirmed = payload["confirmed"][0]
    assert {member["qualified_name"] for member in confirmed["members"]} == {
        "summarizeByReduction",
        "summarizeByLoop",
    }
    assert all(member["line"] <= member["end_line"] for member in confirmed["members"])
    assert (report_dir / confirmed["matrix_path"]).is_file()
    assert "Capability comparison" in (report_dir / confirmed["matrix_path"]).read_text(encoding="utf-8")

    assert {item["reason_code"] for item in payload["uncertain"]} == {
        "direct_call_unresolved_or_dynamic",
    }
    assert {item["reason_code"] for item in payload["rejected"]} >= {
        "caller_callee",
        "token_similar_belongs_in_find_duplication",
        "load_bearing_divergence",
    }
    triage = (report_dir / "triage.md").read_text(encoding="utf-8")
    assert "## Confirmed findings" in triage
    assert "## Uncertain candidates" in triage
    assert "## Rejected candidates" in triage
    assert "/fix-workflow semantic:TS-SD-0001" in triage
    assert "WireFormatter.format" not in triage
    assert "fakeOne" not in triage
    assert "generatedOne" not in triage
    assert before == _source_digest(host)


def test_typescript_semantic_invalid_prerequisites_and_direct_exclusions(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "broken.ts").write_text(
        "export function broken(: string { return ''; }\n", encoding="utf-8"
    )
    invalid, _ = _scan(SKILL, host)
    assert invalid.returncode == 2
    assert "TypeScript syntax errors" in invalid.stderr

    missing_config, _ = _scan(SKILL, host, tsconfig="missing.json")
    assert missing_config.returncode == 2
    assert "project-local TypeScript requires tsconfig" in missing_config.stderr

    invalid_config_host = _copy_host(tmp_path, "invalid-config")
    (invalid_config_host / "tsconfig.json").write_text("{ invalid json", encoding="utf-8")
    invalid_config, _ = _scan(SKILL, invalid_config_host)
    assert invalid_config.returncode == 2
    assert "invalid tsconfig" in invalid_config.stderr

    no_typescript = tmp_path / "no-typescript"
    shutil.copytree(FIXTURE, no_typescript)
    missing_compiler, _ = _scan(SKILL, no_typescript)
    assert missing_compiler.returncode == 2
    assert "project-local TypeScript package is unavailable" in missing_compiler.stderr

    clean = _copy_host(tmp_path, "excluded")
    broad, broad_dir = _scan(SKILL, clean, "src", report_name="broad")
    assert broad.returncode == 0, broad.stdout + broad.stderr
    broad_payload = _load(broad_dir / "analysis.json")
    assert all("generated" not in file and "tests" not in file for file in broad_payload["eligible_files"])
    for index, target in enumerate(("src/generated", "tests/doubles.test.ts")):
        excluded, excluded_dir = _scan(SKILL, clean, target, report_name=f"excluded-{index}")
        assert excluded.returncode == 0, excluded.stdout + excluded.stderr
        assert _load(excluded_dir / "analysis.json")["target"]["exclusion"] == "excluded"


def test_typescript_semantic_rejects_symlinked_targets_and_unsafe_reports(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.ts").write_text("export const outside = true;\n", encoding="utf-8")
    os.symlink(external, host / "src" / "outside-link")

    broad, report_dir = _scan(SKILL, host, "src", report_name="broad")
    assert broad.returncode == 0, broad.stdout + broad.stderr
    assert all("outside-link" not in file for file in _load(report_dir / "analysis.json")["eligible_files"])

    linked_target, _ = _scan(SKILL, host, "src/outside-link", report_name="linked")
    assert linked_target.returncode == 2
    assert "symbolic link" in linked_target.stderr

    unsafe = _run(
        "node", str(SCRIPT), "--target", "src", "--project-root", str(host),
        "--tsconfig", "tsconfig.json", "--report-dir", "src/unsafe-report", cwd=host,
    )
    assert unsafe.returncode == 2
    assert "report directory must stay beneath" in unsafe.stderr

    shutil.rmtree(host / "reports")
    (host / "reports").mkdir()
    os.symlink(host / "src", host / "reports" / "semantic-duplication")
    symlinked_output = _run(
        "node", str(SCRIPT), "--target", "src", "--project-root", str(host),
        "--tsconfig", "tsconfig.json", "--report-dir", "reports/semantic-duplication/unsafe", cwd=host,
    )
    assert symlinked_output.returncode == 2
    assert "symbolic link" in symlinked_output.stderr


def test_stock_install_runs_the_documented_selected_skill_command(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    install = _run(
        "bash", "-c", _documented_command(SKILL, "stock-install"), cwd=host,
        env={**os.environ, "DO_NOT_TRACK": "1", "SEMANTIC_DUPLICATION_SOURCE": str(REPO_ROOT)},
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = host / ".agents" / "skills" / "find-semantic-duplication"
    assert installed.is_dir()
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())

    result = _run(
        "bash", "-c", _documented_command(installed, "typescript-scan"), cwd=host,
        env={**os.environ, "TARGET": "src"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _load(host / "reports" / "semantic-duplication" / "typescript-scan" / "findings.json")
    assert [item["finding_id"] for item in payload["confirmed"]] == ["TS-SD-0001"]
    assert str(REPO_ROOT) not in installed.joinpath("scripts", "detect_typescript.mjs").read_text(encoding="utf-8")
