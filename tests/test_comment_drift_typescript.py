from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-comment-drift"
FIXTURES = SKILL / "fixtures"
DETECT = SKILL / "scripts" / "detect.py"
REPORT = SKILL / "scripts" / "report.py"
GUARD = SKILL / "scripts" / "guard.py"
ROOT_GUARD = REPO_ROOT / "scripts" / "lint" / "no_comment_drift.py"
LINT_RUNNER = REPO_ROOT / "scripts" / "lint" / "run.py"
LINT_PATH_UTILS = REPO_ROOT / "scripts" / "lint" / "path_utils.py"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"


def _run(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _detect(tmp_path: Path, *paths: Path) -> list[dict]:
    output = tmp_path / "detections.jsonl"
    result = _run(
        sys.executable,
        str(DETECT),
        "--project-root",
        str(REPO_ROOT),
        "--output",
        str(output),
        *(str(path) for path in paths),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return [json.loads(line) for line in output.read_text().splitlines() if line]


def test_typescript_and_tsx_detector_contract(tmp_path: Path) -> None:
    bad = _detect(tmp_path, FIXTURES / "bad" / "bad.ts", FIXTURES / "bad" / "bad.tsx")
    patterns = {record["pattern"] for record in bad}
    files = {record["file"] for record in bad}

    assert {
        "jsdoc_candidate",
        "thin_jsdoc_comment",
        "obvious_narration_comment",
        "malformed_doc_reference",
    } <= patterns
    assert any(path.endswith("bad.ts") for path in files)
    assert any(path.endswith("bad.tsx") for path in files)

    good = _detect(tmp_path, FIXTURES / "good" / "good.ts", FIXTURES / "good" / "good.tsx")
    assert good == []


def test_bundled_guard_and_repository_wrapper_agree() -> None:
    bad = FIXTURES / "bad" / "bad.ts"
    good = FIXTURES / "good" / "good.ts"

    bundled_bad = _run(sys.executable, str(GUARD), "--project-root", str(REPO_ROOT), str(bad))
    root_bad = _run(sys.executable, str(ROOT_GUARD), str(bad))
    assert bundled_bad.returncode == root_bad.returncode == 1
    assert bundled_bad.stdout == root_bad.stdout

    bundled_good = _run(sys.executable, str(GUARD), "--project-root", str(REPO_ROOT), str(good))
    root_good = _run(sys.executable, str(ROOT_GUARD), str(good))
    assert bundled_good.returncode == root_good.returncode == 0
    assert bundled_good.stdout == root_good.stdout == ""


def test_repository_wrapper_keeps_repository_root_outside_checkout(
    tmp_path: Path,
) -> None:
    bad = FIXTURES / "bad" / "bad.ts"
    result = _run(sys.executable, str(ROOT_GUARD), str(bad), cwd=tmp_path)

    assert result.returncode == 1
    assert ".claude/skills/find-comment-drift/fixtures/bad/bad.ts" in result.stdout


def test_reasoned_typescript_allowlist(tmp_path: Path) -> None:
    source = tmp_path / "allowed.ts"
    source.write_text(
        "// Get the vendor payload // noqa: comment-drift: mirrors upstream terminology\n"
        "export const payload = vendor.payload;\n",
        encoding="utf-8",
    )
    result = _run(sys.executable, str(GUARD), "--project-root", str(tmp_path), str(source))
    assert result.returncode == 0, result.stdout + result.stderr


def test_normal_hook_and_all_runner_include_typescript(tmp_path: Path) -> None:
    config = PRE_COMMIT_CONFIG.read_text(encoding="utf-8")
    assert "types_or: [python, javascript, jsx, ts, tsx, html]" in config

    host = tmp_path / "host"
    lint_dir = host / "scripts" / "lint"
    lint_dir.mkdir(parents=True)
    shutil.copyfile(LINT_RUNNER, lint_dir / "run.py")
    shutil.copyfile(ROOT_GUARD, lint_dir / "no_comment_drift.py")
    shutil.copyfile(LINT_PATH_UTILS, lint_dir / "path_utils.py")
    shutil.copytree(SKILL, host / ".claude" / "skills" / "find-comment-drift")
    bad = host / "app" / "setup.ts"
    bad.parent.mkdir()
    shutil.copyfile(FIXTURES / "bad" / "bad.ts", bad)
    good = host / "src" / "UserCard.tsx"
    good.parent.mkdir()
    shutil.copyfile(FIXTURES / "good" / "good.tsx", good)

    result = _run(
        sys.executable,
        str(lint_dir / "run.py"),
        "--rule",
        "comment-drift",
        "--all",
        "--repo-root",
        str(host),
        cwd=host,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "[lint:comment-drift] 2 file(s)" in result.stdout
    assert "app/setup.ts" in result.stdout
    assert "src/UserCard.tsx" not in result.stdout


def test_copied_skill_is_self_contained(tmp_path: Path) -> None:
    installed = tmp_path / "installed" / "find-comment-drift"
    shutil.copytree(SKILL, installed)
    host = tmp_path / "host"
    source = host / "src" / "bad.ts"
    source.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "bad" / "bad.ts", source)
    report_dir = host / "reports" / "find-comment-drift" / "scan-test"
    detections = report_dir / "detections.jsonl"
    report = report_dir / "report.md"

    detect = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(detections),
        str(source.parent),
        cwd=host,
    )
    assert detect.returncode == 0, detect.stdout + detect.stderr

    render = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "report.py"),
        str(detections),
        "--output",
        str(report),
        "--target",
        "src",
        cwd=host,
    )
    assert render.returncode == 0, render.stdout + render.stderr
    assert report.exists()
    findings_path = report.with_name("findings.json")
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    assert findings["summary"]["findings_total"] == 4
    assert {
        record["pattern"] for record in findings["findings"]
    } == {
        "jsdoc_candidate",
        "malformed_doc_reference",
        "obvious_narration_comment",
        "thin_jsdoc_comment",
    }

    smoke = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "smoke.py"),
        cwd=host,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr

    guard = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "guard.py"),
        "--project-root",
        str(host),
        str(source),
        cwd=host,
    )
    assert guard.returncode == 1, guard.stdout + guard.stderr
    assert "obvious_narration_comment" in guard.stdout
