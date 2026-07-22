"""Locked Java 17 outcome proof for the state-maintenance chain."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "find-implicit-state-java"
FIND = ROOT / ".claude" / "skills" / "find-implicit-state"
EXTRACT = ROOT / ".claude" / "skills" / "extract-enum"
GUARD = ROOT / ".claude" / "skills" / "prevent-regression"
AFTER_FIXTURE = ROOT / "tests" / "fixtures" / "find-implicit-state-java-after"


def _jdk() -> Path:
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java is None or javac is None:
        pytest.skip("JDK 17 is unavailable")
    result = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
    rendered = result.stdout + result.stderr
    if result.returncode or not rendered.startswith("javac 17"):
        pytest.skip("JDK 17 is unavailable")
    return Path(java).parent


def _env(*, path: str | None = None) -> dict[str, str]:
    jdk = _jdk()
    return {**os.environ, "PATH": path if path is not None else f"{jdk}{os.pathsep}{os.environ.get('PATH', '')}"}


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    native = _run(
        "javac", "--release", "17", "-proc:none", "-d", str(host / "classes"), *sources,
        cwd=host, env=_env(),
    )
    assert native.returncode == 0, native.stdout + native.stderr
    shutil.rmtree(host / "classes")
    return host


def _after_host(tmp_path: Path) -> Path:
    host = tmp_path / "after"
    shutil.copytree(AFTER_FIXTURE, host)
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    native = _run(
        "javac", "--release", "17", "-proc:none", "-d", str(host / "classes"), *sources,
        cwd=host, env=_env(),
    )
    assert native.returncode == 0, native.stdout + native.stderr
    shutil.rmtree(host / "classes")
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _detect(
    skill: Path,
    host: Path,
    output: Path,
    *,
    target: Path | None = None,
    isolated: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    return _run(
        *prefix,
        str(skill / "scripts" / "detect_java_state.py"),
        "--target", str(target or host),
        "--project-root", str(host),
        "--output", str(output / "hits.jsonl"),
        "--findings", str(output / "findings.json"),
        "--report", str(output / "report.md"),
        "--scan-id", "java-state-fixture",
        cwd=host,
        env=env or _env(),
    )


def _collect(skill: Path, host: Path, findings: Path, output: Path, finding: str, *, isolated: bool = False) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    return _run(
        *prefix,
        str(skill / "scripts" / "collect_java_state.py"),
        "--finding", finding,
        "--findings", str(findings),
        "--project-root", str(host),
        "--output", str(output / "targets.json"),
        "--proposal", str(output / "proposal.md"),
        cwd=host,
        env=_env(),
    )


def _generate_guard(skill: Path, host: Path, targets: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable, "-I", "-S", str(skill / "scripts" / "generate_java_state_guard.py"),
        "--targets", str(targets), "--project-root", str(host), "--output-root", str(output),
        cwd=host, env=_env(),
    )


def test_java_state_detector_reaches_final_review_artifacts_from_copied_closure(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = tmp_path / "installed" / "find-implicit-state"
    shutil.copytree(FIND, installed)
    before = _fingerprints(host)
    report = host / "reports" / "implicit-state" / "java-state"

    result = _detect(installed, host, report, isolated=True)

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(report / "hits.jsonl")
    status = records[0]
    assert status == {
        "record_kind": "analysis_status",
        "status": "complete",
        "analyzer": "jdk-compiler-tree-type-api",
        "unavailable_files": [],
    }
    candidate_operations = [row for row in records if row.get("classification") == "first_party_state_operation"]
    assert len(candidate_operations) == 4
    assert {row["literal"] for row in candidate_operations} == {"queued", "running", "done"}
    assert {row["operation"] for row in candidate_operations} == {"assignment", "string_equals", "objects_equals"}
    assert {row["field_owner"] for row in candidate_operations} == {"example.Job"}
    unsafe = [row for row in records if row.get("classification") == "unsafe_string_comparison"]
    assert len(unsafe) == 1
    assert unsafe[0]["field_owner"] == "example.UnsafeJob"
    assert unsafe[0]["evidence_strength"] == "correctness_finding_not_enum_evidence"
    assert {row["role"] for row in records if row["record_kind"] == "source_inventory"} >= {
        "excluded_generated", "excluded_test", "excluded_vendor", "first_party",
    }
    assert any(row.get("field_owner") == "example.VendorJobPayload" and row.get("classification") == "vendor_wire_boundary" for row in records)
    assert any(row.get("field_owner") == "example.OneShot" and row.get("classification") == "insufficient_closed_state_evidence" for row in records)
    assert any(row.get("field_owner") == "example.Label" and row.get("classification") == "unrelated_string_field" for row in records)
    assert not any(row.get("field_owner") == "example.CleanJob" for row in records)

    findings = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert findings["status"] == "complete"
    assert findings["analysis"]["analyzer"] == "jdk-compiler-tree-type-api"
    assert findings["source_manifest"]["algorithm"] == "sha256"
    assert findings["source_manifest"]["files"][
        "src/main/java/example/Job.java"
    ] == hashlib.sha256(
        (host / "src/main/java/example/Job.java").read_bytes()
    ).hexdigest()
    accepted = [row for row in findings["findings"] if row["bucket"] == "extract_enum_candidate"]
    assert len(accepted) == 1
    assert accepted[0]["finding_id"] == "java-implicit-state-0001"
    assert accepted[0]["authority"]["qualified_owner"] == "example.Job"
    assert accepted[0]["authority"]["field"] == "status"
    unsafe_findings = [row for row in findings["findings"] if row["bucket"] == "unsafe_string_comparison"]
    assert len(unsafe_findings) == 1
    assert unsafe_findings[0]["not_enum_evidence"] is True
    rendered = (report / "report.md").read_text(encoding="utf-8")
    assert "Accepted enum-review candidates" in rendered
    assert "not evidence that an enum is appropriate" in rendered
    assert before == _fingerprints(host)


def test_java_state_detector_rejects_malformed_and_missing_or_old_jdk_without_artifacts(tmp_path: Path) -> None:
    host = _host(tmp_path)
    output = host / "reports" / "implicit-state" / "broken"
    (host / "src" / "main" / "java" / "example" / "Broken.java").write_text(
        "package example; public final class Broken { void bad( { }\n", encoding="utf-8"
    )
    malformed = _detect(FIND, host, output)
    assert malformed.returncode == 2
    assert "syntax error" in malformed.stderr.lower()
    assert not output.exists()
    (host / "src" / "main" / "java" / "example" / "Broken.java").unlink()

    missing = _detect(FIND, host, output, env=_env(path=""))
    assert missing.returncode == 2
    assert "jdk is unavailable" in missing.stderr.lower()
    assert not output.exists()

    fake = tmp_path / "old-java"
    fake.write_text("#!/bin/sh\necho 'openjdk version \"11.0.22\"' >&2\n", encoding="utf-8")
    fake.chmod(0o755)
    old = _run(
        sys.executable, str(FIND / "scripts" / "detect_java_state.py"),
        "--target", str(host), "--project-root", str(host),
        "--output", str(output / "hits.jsonl"), "--findings", str(output / "findings.json"),
        "--report", str(output / "report.md"), "--java-executable", str(fake),
        "--javac-executable", shutil.which("javac") or "javac", cwd=host, env=_env(),
    )
    assert old.returncode == 2
    assert "requires jdk >= 17" in old.stderr.lower()
    assert not output.exists()


@pytest.mark.parametrize("build_part", ("build", "target", "out"))
@pytest.mark.parametrize("target_kind", ("directory", "file"))
def test_java_state_detector_excludes_direct_build_output_targets(
    tmp_path: Path,
    build_part: str,
    target_kind: str,
) -> None:
    host = _host(tmp_path)
    excluded = host / build_part / "example/GeneratedJob.java"
    excluded.parent.mkdir(parents=True)
    excluded.write_text(
        (host / "src/main/java/example/Job.java").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    target = host / build_part if target_kind == "directory" else excluded
    report = host / "reports/implicit-state" / f"{build_part}-{target_kind}"

    result = _detect(FIND, host, report, target=target)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert not any(
        item.get("bucket") == "extract_enum_candidate"
        for item in payload["findings"]
    )
    inventory = payload["boundaries"]["source_inventory"]
    assert inventory == [
        {
            "record_kind": "source_inventory",
            "file": f"{build_part}/example/GeneratedJob.java",
            "role": "excluded_build_output",
        }
    ]


def test_java_enum_proposal_consumes_one_complete_accepted_authority_without_redetection(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _fingerprints(host)
    implicit = host / "reports" / "implicit-state" / "java-state"
    detected = _detect(FIND, host, implicit)
    assert detected.returncode == 0, detected.stdout + detected.stderr
    installed = tmp_path / "installed" / "extract-enum"
    shutil.copytree(EXTRACT, installed)
    enum_dir = host / "reports" / "extract-enum" / "job-status"

    collected = _collect(
        installed, host, implicit / "findings.json", enum_dir,
        "java-implicit-state-0001", isolated=True,
    )

    assert collected.returncode == 0, collected.stdout + collected.stderr
    targets = json.loads((enum_dir / "targets.json").read_text(encoding="utf-8"))
    assert targets["status"] == "review_required"
    assert targets["detector_finding_id"] == "java-implicit-state-0001"
    assert targets["accepted_authority"]["qualified_owner"] == "example.Job"
    assert targets["accepted_authority"]["field"] == "status"
    assert targets["proposed_enum"] == "JobStatus"
    assert [(row["value"], row["enum_member"]) for row in targets["literals"]] == [
        ("done", "DONE"), ("queued", "QUEUED"), ("running", "RUNNING"),
    ]
    proposal = (enum_dir / "proposal.md").read_text(encoding="utf-8")
    assert "public enum JobStatus" in proposal
    assert 'QUEUED("queued")' in proposal
    assert "This skill did not\nre-detect or edit source" in proposal
    assert "javac --release 17 -proc:none" in proposal
    assert before == _fingerprints(host)

    unsafe_output = host / "reports" / "extract-enum" / "unsafe"
    unsafe = _collect(installed, host, implicit / "findings.json", unsafe_output, "java-unsafe-string-comparison-0001")
    assert unsafe.returncode == 2
    assert "not an accepted enum candidate" in unsafe.stderr
    assert not unsafe_output.exists()

    job = host / "src" / "main" / "java" / "example" / "Job.java"
    job.write_text(job.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    stale_output = host / "reports" / "extract-enum" / "stale"
    stale = _collect(installed, host, implicit / "findings.json", stale_output, "java-implicit-state-0001")
    assert stale.returncode == 2
    assert "authority is stale" in stale.stderr
    assert not stale_output.exists()


def test_java_enum_proposal_rejects_stale_caller_from_detector_manifest(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    caller = host / "src/main/java/example/JobConsumer.java"
    caller.write_text(
        """package example;

public final class JobConsumer {
    public static boolean isQueued(Job job) {
        return job.status.equals("queued");
    }
}
""",
        encoding="utf-8",
    )
    implicit = host / "reports/implicit-state/java-state"
    detected = _detect(FIND, host, implicit)
    assert detected.returncode == 0, detected.stdout + detected.stderr
    payload = json.loads((implicit / "findings.json").read_text(encoding="utf-8"))
    assert payload["source_manifest"]["files"][
        "src/main/java/example/JobConsumer.java"
    ] == hashlib.sha256(caller.read_bytes()).hexdigest()
    caller.write_text(caller.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    output = host / "reports/extract-enum/stale-caller"

    result = _collect(
        EXTRACT,
        host,
        implicit / "findings.json",
        output,
        "java-implicit-state-0001",
    )

    assert result.returncode == 2
    assert "caller evidence is stale" in result.stderr
    assert not output.exists()


def test_copied_java_state_runbook_preserves_detector_failure(tmp_path: Path) -> None:
    host = tmp_path / "host"
    installed = host / ".claude/skills/find-implicit-state"
    shutil.copytree(FIND, installed)
    detector = installed / "scripts/detect_java_state.py"
    detector.write_text(
        """import pathlib
import sys

output = pathlib.Path(sys.argv[sys.argv.index("--output") + 1])
output.parent.mkdir(parents=True, exist_ok=True)
raise SystemExit(7)
""",
        encoding="utf-8",
    )
    text = (installed / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:java-state:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:java-state:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None

    result = _run(
        "/bin/sh",
        "-c",
        match.group(1),
        cwd=host,
        env={**_env(), "TARGET": "."},
    )

    assert result.returncode == 7
    assert not (host / "reports/implicit-state/latest").exists()


def test_java_state_guard_stages_only_exact_authority_and_verifies_native_fixtures(tmp_path: Path) -> None:
    host = _host(tmp_path / "before")
    before = _fingerprints(host)
    installed = tmp_path / "installed"
    installed_find = installed / "find-implicit-state"
    installed_extract = installed / "extract-enum"
    installed_guard = installed / "prevent-regression"
    shutil.copytree(FIND, installed_find)
    shutil.copytree(EXTRACT, installed_extract)
    shutil.copytree(GUARD, installed_guard)
    implicit = host / "reports" / "implicit-state" / "java-state"
    assert _detect(installed_find, host, implicit, isolated=True).returncode == 0
    enum_dir = host / "reports" / "extract-enum" / "job-status"
    assert _collect(
        installed_extract, host, implicit / "findings.json", enum_dir,
        "java-implicit-state-0001", isolated=True,
    ).returncode == 0
    stage = host / "reports" / "prevent-regression" / "job-status"

    generated = _generate_guard(installed_guard, host, enum_dir / "targets.json", stage)

    assert generated.returncode == 0, generated.stdout + generated.stderr
    rule = stage / "scripts" / "lint" / "no_stringly_state.py"
    helper = stage / "scripts" / "lint" / "detect_java_state.java"
    authority = stage / "authority.json"
    bad = stage / "tests" / "lint" / "bad" / "Job.java"
    good = stage / "tests" / "lint" / "good" / "Job.java"
    assert rule.is_file() and helper.is_file() and authority.is_file()
    assert bad.is_file() and good.is_file() and (stage / "host-wiring.diff").is_file()
    assert helper.read_text(encoding="utf-8") == (installed_find / "scripts" / "detect_java_state.java").read_text(encoding="utf-8")
    assert str(ROOT) not in rule.read_text(encoding="utf-8")
    copied_authority = json.loads(authority.read_text(encoding="utf-8"))
    targets = json.loads((enum_dir / "targets.json").read_text(encoding="utf-8"))
    assert copied_authority["accepted_authority"] == targets["accepted_authority"]
    assert not (host / "scripts" / "lint" / "no_stringly_state.py").exists()

    historical = _run(
        sys.executable, str(rule), "--project-root", str(host),
        str(host / "src" / "main" / "java" / "example" / "Job.java"), cwd=host, env=_env(),
    )
    assert historical.returncode == 1, historical.stdout + historical.stderr
    assert len(historical.stdout.splitlines()) == 4
    assert all("example.Job.status" in line for line in historical.stdout.splitlines())

    after = _after_host(tmp_path)
    after_before = _fingerprints(after)
    clean = _run(
        sys.executable, str(rule), "--project-root", str(after),
        str(after / "src" / "main" / "java" / "example" / "Job.java"), cwd=after, env=_env(),
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert after_before == _fingerprints(after)

    verify = _run(
        sys.executable, "-I", "-S", str(installed_guard / "scripts" / "verify_java_state_guard.py"),
        "--rule", str(rule), "--authority", str(authority), "--bad", str(bad), "--good", str(good),
        "--project-root", str(host), cwd=host, env=_env(),
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "PASS: BAD_RC=1, GOOD_RC=0, native Java fixtures compile" in verify.stdout

    missing = _run(
        sys.executable, str(rule), "--project-root", str(host),
        str(host / "src" / "main" / "java" / "example" / "Job.java"), cwd=host, env=_env(path=""),
    )
    assert missing.returncode == 2
    assert "jdk is unavailable" in missing.stderr.lower()

    old_bin = tmp_path / "old-bin"
    old_bin.mkdir()
    for name, version in (("java", 'openjdk version "11.0.22"'), ("javac", "javac 11.0.22")):
        executable = old_bin / name
        executable.write_text(f"#!/bin/sh\necho '{version}' >&2\n", encoding="utf-8")
        executable.chmod(0o755)
    old = _run(
        sys.executable, str(rule), "--project-root", str(host),
        str(host / "src" / "main" / "java" / "example" / "Job.java"), cwd=host, env=_env(path=str(old_bin)),
    )
    assert old.returncode == 2
    assert "jdk >= 17" in old.stderr.lower()
    assert before == _fingerprints(host)
