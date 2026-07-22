"""Java subpackage proposal, blocker, and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "propose-folder-reorganization"
FIXTURE = ROOT / "tests" / "fixtures" / "propose-folder-reorganization-java" / "host"
JAVA = shutil.which("java")
JAVAC = shutil.which("javac")
pytestmark = pytest.mark.skipif(
    JAVA is None or JAVAC is None, reason="JDK 17 is required"
)


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts
    }


def _native(host: Path) -> None:
    classes = host / ".classes"
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    compiled = _run(
        JAVAC,
        "--release",
        "17",
        "-proc:none",
        "-d",
        str(classes),
        *sources,
        cwd=host,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    tested = _run(
        JAVA,
        "-ea",
        "-cp",
        str(classes),
        "example.test.NativeSmoke",
        cwd=host,
    )
    shutil.rmtree(classes, ignore_errors=True)
    assert tested.returncode == 0, tested.stdout + tested.stderr


def _propose(
    host: Path,
    name: str,
    *,
    skill: Path = SKILL,
    prefix: str = "billing",
    cluster_judgment: str = "split",
    convention_judgment: str = "approve-subpackage",
    minimum_jdk: str = "17",
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    inspection = host / "reports/propose-folder-reorganization" / name / "inspection.json"
    proposal = inspection.with_name("proposal.md")
    result = _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts/propose_java.py"),
        "--parent",
        "src/main/java/example/legacy",
        "--prefix",
        prefix,
        "--cluster-judgment",
        cluster_judgment,
        "--convention-judgment",
        convention_judgment,
        "--project-root",
        str(host),
        "--minimum-jdk",
        minimum_jdk,
        "--inspection",
        str(inspection),
        "--proposal",
        str(proposal),
        cwd=host,
        env=env,
    )
    return result, inspection, proposal


def _documented_command(skill: Path) -> str:
    text = (skill / "knowledge/java-v1.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:java-proposal:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:java-proposal:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_java_ready_plan_has_complete_current_source_root_impacts_and_no_mutation(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    _native(host)
    before = _fingerprints(host)

    result, inspection, proposal = _propose(host, "ready")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["recommendation"] == "refactor"
    assert payload["analyzer"] == "jdk-compiler-tree-type-api"
    assert payload["judgment"] == {
        "cluster": "split",
        "project_convention": "approve-subpackage",
        "framework_convention_inferred": False,
    }
    assert payload["source_root"] == "src/main/java"
    assert payload["old_package"] == "example.legacy"
    assert payload["new_package"] == "example.legacy.billing"
    assert {row["current"] for row in payload["moves"]} == {
        "src/main/java/example/legacy/BillingParser.java",
        "src/main/java/example/legacy/BillingRules.java",
        "src/main/java/example/legacy/BillingSummary.java",
    }
    kinds = {row["kind"] for row in payload["impacts"]}
    assert kinds >= {
        "package_declaration",
        "type_import",
        "static_import",
        "wildcard_import",
        "fully_qualified_type",
        "add_import_from_old_package",
        "add_import_to_new_package",
    }
    assert all(row["resolution"] == "compiler-resolved" for row in payload["impacts"])
    assert payload["blockers"] == []
    rendered = proposal.read_text(encoding="utf-8")
    assert "Explicit human judgments" in rendered
    assert "No Java framework convention was inferred" in rendered
    assert "javac --release 17 -proc:none" in rendered
    assert "native test" in rendered
    assert "no source edits" in rendered


def test_java_human_judgment_and_threshold_deferrals_are_explicit(tmp_path: Path) -> None:
    cohesive = _host(tmp_path / "cohesive")
    result, inspection, proposal = _propose(
        cohesive, "cohesive", cluster_judgment="cohesive"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["status"] == "deferred"
    assert payload["recommendation"] == "defer_cohesive_cluster"
    assert "No move plan" in proposal.read_text(encoding="utf-8")

    denied = _host(tmp_path / "denied")
    result, inspection, _ = _propose(
        denied, "denied", convention_judgment="deny-subpackage"
    )
    assert result.returncode == 0
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["recommendation"] == "defer_project_convention"

    below = _host(tmp_path / "below")
    (below / "src/main/java/example/legacy/BillingSummary.java").unlink()
    result, inspection, _ = _propose(below, "below")
    assert result.returncode == 0
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["recommendation"] == "defer_below_threshold"


def test_java_package_private_generated_test_vendor_build_and_symlink_blockers(
    tmp_path: Path,
) -> None:
    package_private = _host(tmp_path / "private")
    other = package_private / "src/main/java/example/legacy/OtherPolicy.java"
    other.write_text(
        other.read_text(encoding="utf-8").replace(
            "public final class OtherPolicy", "final class OtherPolicy"
        ),
        encoding="utf-8",
    )
    result, inspection, _ = _propose(package_private, "private")
    assert result.returncode == 0, result.stdout + result.stderr
    private_payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert private_payload["status"] == "blocked"
    assert any(row["kind"] == "package_private_cross_boundary" for row in private_payload["blockers"])

    cases = {
        "generated": (
            "generated/src/main/java/example/generated/NeutralGenerated.java",
            "package example.generated; public final class NeutralGenerated { "
            'String value = "example.legacy.BillingParser"; }\n',
            "generated_source_ambiguity",
        ),
        "test": (
            "src/test/java/example/test/NativeSmoke.java",
            "package example.test; import example.legacy.BillingParser; "
            "public final class NativeSmoke { public static void main(String[] args) { "
            "assert new BillingParser().parse(\"1\") == 1; } }\n",
            "test_source_ambiguity",
        ),
        "vendor": (
            "vendor/example/vendor/NeutralVendor.java",
            "package example.vendor; public final class NeutralVendor { "
            'String value = "example.legacy.BillingParser"; }\n',
            "vendor_source_ambiguity",
        ),
        "build": (
            "build/generated/example/build/NeutralBuild.java",
            "package example.build; public final class NeutralBuild { "
            'String value = "example.legacy.BillingParser"; }\n',
            "build_source_ambiguity",
        ),
    }
    for name, (relative, source, kind) in cases.items():
        host = _host(tmp_path / name)
        (host / relative).write_text(source, encoding="utf-8")
        result, inspection, _ = _propose(host, name)
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(inspection.read_text(encoding="utf-8"))
        assert payload["status"] == "blocked"
        assert any(row["kind"] == kind for row in payload["blockers"])

    linked = _host(tmp_path / "linked")
    external = tmp_path / "External.java"
    external.write_text("package example.legacy; final class External {}\n", encoding="utf-8")
    (linked / "src/main/java/example/legacy/External.java").symlink_to(external)
    result, inspection, _ = _propose(linked, "linked")
    assert result.returncode == 0
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert any(row["kind"] == "symlink_source_ambiguity" for row in payload["blockers"])


def test_java_malformed_destination_missing_and_old_jdk_are_honest(tmp_path: Path) -> None:
    malformed = _host(tmp_path / "malformed")
    (malformed / "src/main/java/example/app/Broken.java").write_text(
        "package example.app; public final class Broken {",
        encoding="utf-8",
    )
    result, inspection, _ = _propose(malformed, "malformed")
    assert result.returncode == 2
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["failure_kind"] == "syntax_error"

    destination = _host(tmp_path / "destination")
    (destination / "src/main/java/example/legacy/billing").mkdir()
    result, inspection, _ = _propose(destination, "destination")
    assert result.returncode == 0
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert any(row["kind"] == "destination_exists" for row in payload["blockers"])

    missing = _host(tmp_path / "missing")
    missing_bin = tmp_path / "missing-bin"
    missing_bin.mkdir()
    result, inspection, _ = _propose(
        missing, "missing", env={**os.environ, "PATH": str(missing_bin)}
    )
    assert result.returncode == 0
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["status"] == "unsupported"
    assert payload["failure_kind"] == "jdk_tool_missing"

    old = _host(tmp_path / "old")
    result, inspection, _ = _propose(old, "old", minimum_jdk="99")
    assert result.returncode == 0
    payload = json.loads(inspection.read_text(encoding="utf-8"))
    assert payload["status"] == "unsupported"
    assert payload["failure_kind"] == "jdk_version_too_old"


def test_java_copied_skill_documented_command_is_self_contained(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = host / ".agents/skills/propose-folder-reorganization"
    shutil.copytree(SKILL, installed)
    before = _fingerprints(host)

    result = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=host,
        env={
            **os.environ,
            "PFR_PARENT": "src/main/java/example/legacy",
            "PFR_PREFIX": "billing",
            "PFR_CLUSTER_JUDGMENT": "split",
            "PFR_CONVENTION_JUDGMENT": "approve-subpackage",
            "PFR_NAME": "copied",
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(
        (host / "reports/propose-folder-reorganization/copied/inspection.json").read_text()
    )
    assert payload["status"] == "ready"
    assert _fingerprints(host) == before
    assert (installed / "scripts/propose_java.java").is_file()
    assert (installed / "scripts/propose_java.py").is_file()
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in installed.rglob("*")
        if path.is_file()
    )
    assert str(ROOT) not in closure
    assert "scripts/_lib" not in closure
    assert "org.eclipse" not in closure
