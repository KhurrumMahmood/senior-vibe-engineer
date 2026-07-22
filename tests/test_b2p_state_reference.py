"""B2P closed-state Python reference proof.

This test follows the reviewable outcome boundary: detector JSONL, collapsed
and reviewed findings, enum-extraction targets plus the reviewed proposal,
the before/after enum mutation, and the blocking stringly-status guard.
"""
from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "b2p_state_reference"
VENV_PYTHON = Path(sys.executable)
DETECT = REPO_ROOT / ".claude" / "skills" / "find-implicit-state" / "scripts" / "detect.py"
COLLAPSE = REPO_ROOT / ".claude" / "skills" / "find-implicit-state" / "scripts" / "collapse.py"
REPORT = REPO_ROOT / ".claude" / "skills" / "find-implicit-state" / "scripts" / "report.py"
COLLECT = REPO_ROOT / ".claude" / "skills" / "extract-enum" / "scripts" / "collect.py"
ROOT_GUARD = REPO_ROOT / "scripts" / "lint" / "no_stringly_typed_status.py"
BUNDLED_GUARD = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "prevent-regression"
    / "scripts"
    / "stringly_status_guard.py"
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, state: str) -> Path:
    host = tmp_path / f"host-{state}"
    shutil.copytree(FIXTURE / state, host)
    return host


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((host / "app").rglob("*"))
        if path.is_file()
    }


def _run_reference_pipeline(host: Path) -> tuple[Path, Path, dict]:
    report_dir = host / "reports" / "implicit-state" / "scan-b2p"
    scout_dir = report_dir / "scout"
    hits = report_dir / "hits.jsonl"
    candidates = report_dir / "candidates.jsonl"
    findings = report_dir / "findings.json"
    report = report_dir / "report.md"
    report_dir.mkdir(parents=True)

    detect = _run(
        str(VENV_PYTHON), str(DETECT), "--target", str(host / "app"),
        "--project-root", str(host), "--output", str(hits), cwd=host,
    )
    assert detect.returncode == 0, detect.stderr
    assert "[detect_implicit_state]" in detect.stderr

    collapse = _run(
        str(VENV_PYTHON), str(COLLAPSE), "--hits", str(hits),
        "--output", str(candidates), cwd=host,
    )
    assert collapse.returncode == 0, collapse.stderr
    assert "[collapse_implicit_state]" in collapse.stderr

    shutil.copytree(FIXTURE / "reviewed-scout", scout_dir)
    render = _run(
        str(VENV_PYTHON), str(REPORT), "--scout-dir", str(scout_dir),
        "--candidates", str(candidates), "--output-md", str(report),
        "--output-json", str(findings), "--scan-id", "scan-b2p",
        "--target", "app", cwd=host,
    )
    assert render.returncode == 0, render.stderr
    assert "[report_implicit_state]" in render.stderr

    enum_dir = host / "reports" / "extract-enum" / "job__status"
    targets = enum_dir / "targets.json"
    collect = _run(
        str(VENV_PYTHON), str(COLLECT), "--from-finding", "implicit-state-0002",
        "--findings", str(findings), "--project-root", str(host),
        "--output", str(targets), cwd=host,
    )
    assert collect.returncode == 0, collect.stderr
    assert "[collect_extract_enum]" in collect.stderr

    shutil.copyfile(FIXTURE / "reviewed-profile.md", enum_dir / "profile.md")
    shutil.copyfile(FIXTURE / "reviewed-proposal.md", enum_dir / "proposal.md")
    return hits, candidates, json.loads(targets.read_text(encoding="utf-8"))


def test_b2p_python_reference_pipeline_and_guard(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "before")
    before_sources = _source_hashes(host)
    hits_path, candidates_path, targets = _run_reference_pipeline(host)
    assert _source_hashes(host) == before_sources

    hits = _read_jsonl(hits_path)
    assert len(hits) == 5
    assert {hit["pattern"] for hit in hits} == {"stringly_compare", "stringly_field"}
    assert not any("open_text.py" in hit["file"] for hit in hits)
    assert not any("test_jobs.py" in hit["file"] for hit in hits)

    candidates = _read_jsonl(candidates_path)
    assert [candidate["candidate_id"] for candidate in candidates] == [
        "implicit-state-0001", "implicit-state-0002", "implicit-state-0003",
    ]
    assert [candidate["hit_count"] for candidate in candidates] == [1, 3, 1]

    findings = json.loads(
        (host / "reports" / "implicit-state" / "scan-b2p" / "findings.json").read_text()
    )
    assert findings["summary"]["bucket_counts"] == {
        "extract_enum_candidate": 2,
        "legacy_allow_list": 1,
    }
    assert "vendor-owned wire value" in (
        host / "reports" / "implicit-state" / "scan-b2p" / "report.md"
    ).read_text(encoding="utf-8")

    assert targets["field_symbol"] == "Job.status"
    assert targets["callers_by_file"] == {"app/services/jobs.py": 5}
    assert [item["value"] for item in targets["literals"]] == [
        "queued", "done", "running",
    ]
    assert len(targets["comparison_sites"]) == 4
    assert len(targets["assignment_sites"]) == 1
    assert (host / "reports" / "extract-enum" / "job__status" / "scope.json").is_file()

    proposal = (host / "reports" / "extract-enum" / "job__status" / "proposal.md").read_text()
    for literal in ("queued", "running", "done"):
        assert f'"{literal}"' in proposal
    assert "app/integrations/vendor.py" in proposal
    assert "JobStatus.QUEUED" in proposal

    before_root = _run(str(VENV_PYTHON), str(ROOT_GUARD), str(host / "app"), cwd=host)
    before_bundled = _run(str(VENV_PYTHON), str(BUNDLED_GUARD), str(host / "app"), cwd=host)
    assert before_root.returncode == before_bundled.returncode == 1
    assert before_root.stdout == before_bundled.stdout
    assert len(before_root.stdout.splitlines()) == 5
    assert "assignment to `.status`" in before_root.stdout

    after_host = _copy_host(tmp_path, "after")
    assert "default=\"queued\"" in (host / "app" / "models" / "jobs.py").read_text()
    assert "class JobStatus(models.TextChoices)" in (
        after_host / "app" / "models" / "jobs.py"
    ).read_text()
    assert "job.status = JobStatus.QUEUED" in (
        after_host / "app" / "services" / "jobs.py"
    ).read_text()
    after = _run(str(VENV_PYTHON), str(ROOT_GUARD), str(after_host / "app"), cwd=after_host)
    assert after.returncode == 0, after.stdout + after.stderr
    assert after.stdout == ""
    open_ended = _run(
        str(VENV_PYTHON), str(BUNDLED_GUARD),
        str(after_host / "app" / "services" / "open_text.py"), cwd=after_host,
    )
    vendor = _run(
        str(VENV_PYTHON), str(BUNDLED_GUARD),
        str(after_host / "app" / "integrations" / "vendor.py"), cwd=after_host,
    )
    assert open_ended.returncode == vendor.returncode == 0


def test_guard_errors_on_invalid_python_and_detects_chained_assignments(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(:\n", encoding="utf-8")
    path_result = _run(str(VENV_PYTHON), str(BUNDLED_GUARD), str(invalid), cwd=tmp_path)
    stdin_result = subprocess.run(
        [
            str(VENV_PYTHON),
            str(BUNDLED_GUARD),
            "--stdin",
            "--filename",
            "invalid.py",
        ],
        input="def broken(:\n",
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert path_result.returncode == stdin_result.returncode == 2
    assert "syntax error" in path_result.stderr
    assert "syntax error" in stdin_result.stderr

    chained = tmp_path / "chained.py"
    chained.write_text(
        "def queue(job, backup):\n"
        '    job.status = backup.status = "queued"\n',
        encoding="utf-8",
    )
    chained_result = _run(
        str(VENV_PYTHON), str(BUNDLED_GUARD), str(chained), cwd=tmp_path
    )
    assert chained_result.returncode == 1
    assert len(chained_result.stdout.splitlines()) == 2


def test_collector_detects_chained_assignments(tmp_path: Path) -> None:
    host = tmp_path / "host-chained"
    models = host / "app" / "models.py"
    service = host / "app" / "service.py"
    models.parent.mkdir(parents=True)
    models.write_text(
        "from django.db import models\n\n"
        "class Job(models.Model):\n"
        '    status = models.CharField(default="queued", max_length=20)\n',
        encoding="utf-8",
    )
    service.write_text(
        "from app.models import Job\n\n"
        "def queue(job: Job, backup: Job):\n"
        '    job.status = backup.status = "queued"\n',
        encoding="utf-8",
    )
    output = host / "reports" / "targets.json"
    result = _run(
        str(VENV_PYTHON),
        str(COLLECT),
        "--target",
        "app/models.py::status::Job",
        "--project-root",
        str(host),
        "--output",
        str(output),
        cwd=host,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    targets = json.loads(output.read_text(encoding="utf-8"))
    assert len(targets["assignment_sites"]) == 2
    assert targets["callers_by_file"] == {"app/service.py": 2}


def test_fallback_model_lookup_honors_repository_ignore(tmp_path: Path) -> None:
    host = tmp_path / "host-ignore"
    caller = host / "app" / "service.py"
    vendor_model = host / "vendor" / "models.py"
    ignore = host / ".engineering" / "docs" / "ignore.md"
    caller.parent.mkdir(parents=True)
    vendor_model.parent.mkdir(parents=True)
    ignore.parent.mkdir(parents=True)
    caller.write_text(
        "def queue(job: Job):\n"
        '    return job.status == "queued"\n',
        encoding="utf-8",
    )
    vendor_model.write_text(
        "from django.db import models\n\n"
        "class Job(models.Model):\n"
        '    status = models.CharField(default="queued", max_length=20)\n',
        encoding="utf-8",
    )
    ignore.write_text("## Ignore\n\n- `vendor/`\n", encoding="utf-8")
    findings = host / "findings.json"
    findings.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "candidate_id": "implicit-state-0001",
                        "recommendation_hint": "extract_enum_candidate",
                        "recommendation_hint_symbol": "Job",
                        "file": "app/service.py",
                        "fields_touched": ["status"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = _run(
        str(VENV_PYTHON),
        str(COLLECT),
        "--from-finding",
        "implicit-state-0001",
        "--findings",
        str(findings),
        "--project-root",
        str(host),
        "--output",
        str(host / "reports" / "targets.json"),
        cwd=host,
    )
    assert result.returncode == 2
    assert "no Model subclass in app/service.py" in result.stderr
    assert "vendor/models.py" not in result.stderr


def test_b2p_selected_skills_run_from_an_isolated_install(tmp_path: Path) -> None:
    installed = tmp_path / "installed"
    for skill in ("find-implicit-state", "extract-enum", "prevent-regression"):
        shutil.copytree(REPO_ROOT / ".claude" / "skills" / skill, installed / skill)
    host = _copy_host(tmp_path, "before")
    report_dir = host / "reports" / "implicit-state" / "scan-installed"
    scout_dir = report_dir / "scout"
    report_dir.mkdir(parents=True)
    hits = report_dir / "hits.jsonl"
    candidates = report_dir / "candidates.jsonl"
    findings = report_dir / "findings.json"
    targets = host / "reports" / "extract-enum" / "job__status" / "targets.json"
    isolated_python = shutil.which("python3")
    assert isolated_python is not None

    detect = _run(
        isolated_python, "-I", "-S", str(installed / "find-implicit-state" / "scripts" / "detect.py"),
        "--target", str(host / "app"), "--project-root", str(host), "--output", str(hits), cwd=host,
    )
    assert detect.returncode == 0, detect.stderr
    collapse = _run(
        isolated_python, "-I", "-S", str(installed / "find-implicit-state" / "scripts" / "collapse.py"),
        "--hits", str(hits), "--output", str(candidates), cwd=host,
    )
    assert collapse.returncode == 0, collapse.stderr
    shutil.copytree(FIXTURE / "reviewed-scout", scout_dir)
    render = _run(
        isolated_python, "-I", "-S", str(installed / "find-implicit-state" / "scripts" / "report.py"),
        "--scout-dir", str(scout_dir), "--candidates", str(candidates),
        "--output-md", str(report_dir / "report.md"), "--output-json", str(findings),
        "--scan-id", "scan-installed", "--target", "app", cwd=host,
    )
    assert render.returncode == 0, render.stderr
    collect = _run(
        isolated_python, "-I", "-S", str(installed / "extract-enum" / "scripts" / "collect.py"),
        "--from-finding", "implicit-state-0002", "--findings", str(findings),
        "--project-root", str(host), "--output", str(targets), cwd=host,
    )
    assert collect.returncode == 0, collect.stderr
    guard = _run(
        isolated_python, "-I", "-S", str(installed / "prevent-regression" / "scripts" / "stringly_status_guard.py"),
        str(host / "app"), cwd=host,
    )
    assert guard.returncode == 1
    assert len(guard.stdout.splitlines()) == 5
    assert json.loads(targets.read_text(encoding="utf-8"))["field_symbol"] == "Job.status"
