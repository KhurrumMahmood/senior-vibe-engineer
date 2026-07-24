"""JDK 17 final-artifact and copied-closure proof for the bounded Java package map."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "map-subsystem"
FIXTURE = ROOT / "tests" / "fixtures" / "map-subsystem-java" / "host"
SCRIPT = SKILL / "scripts" / "map_java.java"
JAVA = shutil.which("java")
JAVAC = shutil.which("javac")
pytestmark = pytest.mark.skipif(
    JAVA is None or JAVAC is None,
    reason="A JDK with java and javac is required",
)


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _native_compile(host: Path) -> subprocess.CompletedProcess[str]:
    classes = host / "classes"
    sources = sorted((host / "src" / "main" / "java").rglob("*.java"))
    return _run(JAVAC, "--release", "17", "-proc:none", "-d", str(classes), *map(str, sources), cwd=host)


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if ".claude" not in path.relative_to(host).parts
        and ".agents" not in path.relative_to(host).parts
        and "reports" not in path.relative_to(host).parts
    }


def _map(
    skill: Path,
    host: Path,
    *,
    name: str = "java-features",
    target: str = "src/main/java/example/features",
    output: Path | None = None,
    evidence: Path | None = None,
    minimum_jdk: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = output or host / ".engineering" / "docs" / "subsystems" / f"{name}.md"
    evidence = evidence or host / "reports" / "map" / name / "java-map.json"
    args = [
        JAVA,
        str(skill / "scripts" / "map_java.java"),
        "--name",
        name,
        "--target",
        target,
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--evidence",
        str(evidence),
    ]
    if minimum_jdk is not None:
        args.extend(["--minimum-jdk", minimum_jdk])
    return _run(*args, cwd=host), output, evidence


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documented_command(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:java-map:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:java-map:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_java_map_reaches_final_artifacts_with_compiler_resolved_edges(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    assert _native_compile(host).returncode == 0
    before = _fingerprints(host)

    result, output, evidence = _map(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(evidence)
    rendered = output.read_text(encoding="utf-8")
    assert payload["status"] == "complete"
    assert payload["language"] == "java"
    assert payload["analyzer"] == "jdk17-javactask-trees"
    assert payload["target"] == {
        "path": "src/main/java/example/features",
        "kind": "package_directory",
        "package": "example.features",
        "source_root": "src/main/java",
        "source_files": 2,
        "eligible_files": [
            "src/main/java/example/features/Panel.java",
            "src/main/java/example/features/Widget.java",
        ],
        "excluded_files": ["src/main/java/example/features/WireGenerated.java"],
    }
    assert payload["counts"] == {
        "source_files": 2,
        "public_symbols": 6,
        "outbound_imports": 1,
        "inbound_imports": 2,
        "external_imports": 0,
    }
    assert {item["name"] for item in payload["exported_surface"]} == {
        "Widget",
        "DEFAULT_NAME",
        "<init>",
        "label",
        "Panel",
        "title",
    }
    assert payload["outbound_imports"] == [{
        "from_package": "example.features",
        "file": "src/main/java/example/features/Widget.java",
        "line": 3,
        "target_package": "example.shared",
        "referenced_type": "example.shared.Labels",
        "style": "import",
        "resolution": "compiler_resolved_first_party",
    }]
    assert {edge["referenced_type"] for edge in payload["inbound_imports"]} == {
        "example.features.Widget",
        "example.features.Panel",
    }
    assert {edge["style"] for edge in payload["inbound_imports"]} == {"import", "fully_qualified"}
    assert "Status: **complete**" in rendered
    assert "Maven/Gradle" in rendered
    assert _native_compile(host).returncode == 0


def test_java_map_attributes_nested_types_to_their_package(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src/main/java/example/features/Outer.java").write_text(
        "package example.features;\n\n"
        "public final class Outer {\n"
        "    public static final class Inner {}\n"
        "}\n",
        encoding="utf-8",
    )
    (host / "src/main/java/example/app/NestedConsumer.java").write_text(
        "package example.app;\n\n"
        "import example.features.Outer.Inner;\n\n"
        "public final class NestedConsumer {\n"
        "    public Inner imported() { return new Inner(); }\n"
        "    public example.features.Outer.Inner qualified() {\n"
        "        return new example.features.Outer.Inner();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    assert _native_compile(host).returncode == 0

    result, _, evidence = _map(SKILL, host, name="nested")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(evidence)
    nested_edges = [
        edge
        for edge in payload["inbound_imports"]
        if edge["referenced_type"] == "example.features.Outer.Inner"
    ]
    assert {edge["style"] for edge in nested_edges} == {"import", "fully_qualified"}
    assert {edge["target_package"] for edge in nested_edges} == {"example.features"}


def test_java_map_preserves_partial_failed_and_unsupported_states(tmp_path: Path) -> None:
    partial_host = _copy_host(tmp_path, "partial")
    (partial_host / "src" / "main" / "java" / "example" / "features" / "Missing.java").write_text(
        "package example.features;\n\nimport missing.Dependency;\n\npublic final class Missing { Dependency value; }\n",
        encoding="utf-8",
    )
    partial, _, partial_evidence = _map(SKILL, partial_host, name="partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    partial_payload = _payload(partial_evidence)
    assert partial_payload["status"] == "partial"
    assert partial_payload["failure_kind"] == "unresolved_compilation"
    assert partial_payload["exported_surface"] == []
    assert "Incomplete compiler evidence" in (
        partial_host / ".engineering" / "docs" / "subsystems" / "partial.md"
    ).read_text(encoding="utf-8")

    malformed_host = _copy_host(tmp_path, "malformed")
    (malformed_host / "src" / "main" / "java" / "example" / "features" / "Broken.java").write_text(
        "package example.features; public final class Broken { void nope( { }\n",
        encoding="utf-8",
    )
    malformed, malformed_output, malformed_evidence = _map(SKILL, malformed_host, name="malformed")
    assert malformed.returncode == 2
    malformed_payload = _payload(malformed_evidence)
    assert malformed_payload["status"] == "failed"
    assert malformed_payload["failure_kind"] == "syntax_error"
    assert malformed_output.is_file()

    old_host = _copy_host(tmp_path, "old")
    old, _, old_evidence = _map(SKILL, old_host, name="old", minimum_jdk="99")
    assert old.returncode == 0, old.stdout + old.stderr
    old_payload = _payload(old_evidence)
    assert old_payload["status"] == "unsupported"
    assert old_payload["failure_kind"] == "jdk_version_too_old"

    excluded_host = _copy_host(tmp_path, "excluded")
    excluded, _, excluded_evidence = _map(
        SKILL,
        excluded_host,
        name="vendor",
        target="vendor/example/ignored",
    )
    assert excluded.returncode == 0, excluded.stdout + excluded.stderr
    assert _payload(excluded_evidence)["failure_kind"] == "excluded_target"


def test_java_map_refuses_symlinks_and_unsafe_artifact_paths(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    os.symlink(external, host / "src" / "main" / "java" / "example" / "linked")
    linked, _, linked_evidence = _map(SKILL, host, name="linked", target="src/main/java/example/linked")
    assert linked.returncode == 0, linked.stdout + linked.stderr
    assert _payload(linked_evidence)["failure_kind"] == "unsafe_target"

    outside = tmp_path / "Outside.java"
    outside.write_text("package example.features; final class Outside {}\n", encoding="utf-8")
    os.symlink(outside, host / "src" / "main" / "java" / "example" / "features" / "Outside.java")
    source_link, _, source_link_evidence = _map(SKILL, host, name="source-link")
    assert source_link.returncode == 0, source_link.stdout + source_link.stderr
    assert _payload(source_link_evidence)["failure_kind"] == "unsafe_source"
    (host / "src" / "main" / "java" / "example" / "features" / "Outside.java").unlink()

    victim = host / "src" / "main" / "java" / "example" / "features" / "Widget.java"
    before = victim.read_bytes()
    unsafe, _, _ = _map(
        SKILL,
        host,
        name="unsafe",
        output=victim,
        evidence=host / "reports" / "map" / "unsafe" / "java-map.json",
    )
    assert unsafe.returncode == 2
    assert "output must stay" in unsafe.stderr
    assert victim.read_bytes() == before

    reports = host / "reports"
    shutil.rmtree(reports)
    os.symlink(host / "src", reports)
    unsafe_report, _, _ = _map(SKILL, host, name="unsafe-report")
    assert unsafe_report.returncode == 2
    assert "symbolic link" in unsafe_report.stderr


def test_java_map_kotlin_boundary_and_documented_copied_closure(tmp_path: Path) -> None:
    kotlin_host = _copy_host(tmp_path, "kotlin")
    (kotlin_host / "src" / "main" / "java" / "example" / "features" / "Extra.kt").write_text(
        "package example.features\nclass Extra\n",
        encoding="utf-8",
    )
    partial, _, partial_evidence = _map(SKILL, kotlin_host, name="kotlin")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    payload = _payload(partial_evidence)
    assert payload["status"] == "partial"
    assert payload["completeness"]["kotlin_sources"] == "unavailable"

    host = _copy_host(tmp_path, "copied")
    before = _fingerprints(host)
    installed = host / ".agents" / "skills" / "map-subsystem"
    shutil.copytree(SKILL, installed)
    result = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=host,
        env={**os.environ, "MAP_NAME": "copied", "MAP_TARGET": "src/main/java/example/features"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    copied_payload = _payload(host / "reports" / "map" / "copied" / "java-map.json")
    assert copied_payload["status"] == "complete"
    closure = (installed / "scripts" / "map_java.java").read_text(encoding="utf-8")
    assert "scripts/_lib" not in closure
    assert "/_common" not in closure
    assert str(ROOT) not in closure
    assert _native_compile(host).returncode == 0
