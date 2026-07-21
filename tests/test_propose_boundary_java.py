"""End-to-end Java proposal, deferral, and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "propose-boundary"
SCRIPT = SKILL / "scripts" / "propose_java.java"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "propose-boundary-java"
JAVA = shutil.which("java")
JAVAC = shutil.which("javac")
pytestmark = pytest.mark.skipif(
    JAVA is None or JAVAC is None, reason="JDK 17 is required"
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if ".agents" not in path.relative_to(host).parts
    }


def _propose(
    host: Path,
    target: str,
    *,
    name: str,
    minimum_jdk: str = "17",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    inspection = host / "reports" / "propose-boundary" / name / "inspection.json"
    proposal = inspection.with_name("proposal.md")
    result = _run(
        JAVA,
        str(SCRIPT),
        "--target",
        target,
        "--project-root",
        str(host),
        "--minimum-jdk",
        minimum_jdk,
        "--candidates",
        "1",
        "--inspection",
        str(inspection),
        "--proposal",
        str(proposal),
        cwd=host,
    )
    return result, inspection, proposal


def test_java_proposal_reaches_final_artifact_from_resolved_package_evidence(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _fingerprints(host)
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    compiled = _run(JAVAC, "--release", "17", "-d", str(host / "classes"), *sources, cwd=host)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    shutil.rmtree(host / "classes")

    result, inspection, proposal = _propose(
        host, "src/main/java/example/legacy", name="positive"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    rendered = proposal.read_text(encoding="utf-8")
    assert payload["status"] == "complete"
    assert payload["recommendation"] == "refactor"
    assert payload["analyzer"] == "jdk-compiler-tree-api"
    assert payload["target"]["package"] == "example.legacy"
    assert payload["candidate_selection"] == {
        "requested": 1,
        "eligible": 2,
        "returned": 2,
        "cutoff_score": 2,
        "ties_included": True,
        "omitted_count": 0,
        "omitted": [],
    }
    assert {row["cluster_id"] for row in payload["candidate_seams"]} == {
        "quote",
        "settlement",
    }
    assert {row["style"] for row in payload["caller_impact"]} == {
        "import",
        "fully-qualified",
    }
    assert all(row["resolution"] == "compiler-resolved" for row in payload["caller_impact"])
    assert "javac --release 17" in rendered
    assert "human approval" in rendered
    assert "no edits applied" in rendered


def test_java_cohesive_excluded_malformed_and_old_jdk_outcomes_are_not_clean(
    tmp_path: Path,
) -> None:
    cohesive = _copy_host(tmp_path / "cohesive")
    for path in (cohesive / "src/main/java/example/legacy").glob("Settlement*.java"):
        path.unlink()
    controller = cohesive / "src/main/java/example/api/QuoteController.java"
    controller.write_text(
        controller.read_text(encoding="utf-8").replace(
            "\n    public int capture(int amount) {\n"
            "        return new example.legacy.SettlementLedger().capture(amount);\n"
            "    }\n",
            "",
        ),
        encoding="utf-8",
    )
    result, inspection, _ = _propose(
        cohesive, "src/main/java/example/legacy", name="cohesive"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert payload["recommendation"] == "defer_no_seam"

    excluded = _copy_host(tmp_path / "excluded")
    generated = excluded / "generated/example/legacy"
    generated.mkdir(parents=True)
    shutil.copy2(
        excluded / "src/main/java/example/legacy/QuotePlanner.java",
        generated / "QuotePlanner.java",
    )
    result, inspection, _ = _propose(excluded, "generated/example/legacy", name="excluded")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(inspection.read_text())["status"] == "unsupported"

    malformed = _copy_host(tmp_path / "malformed")
    (malformed / "src/main/java/example/legacy/Broken.java").write_text(
        "package example.legacy; public class Broken {", encoding="utf-8"
    )
    result, inspection, _ = _propose(
        malformed, "src/main/java/example/legacy", name="malformed"
    )
    assert result.returncode != 0
    assert json.loads(inspection.read_text())["status"] == "failed"

    old = _copy_host(tmp_path / "old")
    result, inspection, _ = _propose(
        old, "src/main/java/example/legacy", name="old", minimum_jdk="99"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    old_payload = json.loads(inspection.read_text())
    assert old_payload["status"] == "unsupported"
    assert old_payload["failure_kind"] == "jdk_version_too_old"


def test_java_copied_skill_is_self_contained_and_rejects_symlink_target(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    installed = host / ".agents/skills/propose-boundary"
    shutil.copytree(SKILL, installed)
    copied_script = installed / "scripts/propose_java.java"
    result = _run(
        JAVA,
        str(copied_script),
        "--target",
        "src/main/java/example/legacy",
        "--project-root",
        str(host),
        "--inspection",
        "reports/propose-boundary/copied/inspection.json",
        "--proposal",
        "reports/propose-boundary/copied/proposal.md",
        cwd=host,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(
        (host / "reports/propose-boundary/copied/inspection.json").read_text()
    )["recommendation"] == "refactor"
    source = copied_script.read_text(encoding="utf-8")
    assert str(REPO_ROOT) not in source
    assert "org.eclipse" not in source
    assert "com.github" not in source

    linked = host / "linked"
    linked.symlink_to("src/main/java/example/legacy", target_is_directory=True)
    result, inspection, _ = _propose(host, "linked", name="linked")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(inspection.read_text())["status"] == "unsupported"
