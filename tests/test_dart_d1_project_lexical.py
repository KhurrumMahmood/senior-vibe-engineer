"""Dart D1 project/lexical consumers over one copied project snapshot."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "dart-d1-project-lexical"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
DART = Path("/opt/homebrew/bin/dart")  # host-ref-allow: required frozen P7 runtime
COMMON = ROOT / ".claude" / "skills" / "_dart" / "dart_project_snapshot.py"
SCRIPTS = {
    "adapt-project": ROOT
    / ".claude"
    / "skills"
    / "adapt-project"
    / "scripts"
    / "discover_dart.py",
    "find-concept-divergence": ROOT
    / ".claude"
    / "skills"
    / "find-concept-divergence"
    / "scripts"
    / "scan_dart.py",
    "find-folder-topology-drift": ROOT
    / ".claude"
    / "skills"
    / "find-folder-topology-drift"
    / "scripts"
    / "detect_dart.py",
}
pytestmark = pytest.mark.skipif(
    not DART.is_file(), reason="Dart 3.12.2 pilot toolchain is required"
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    (host / "linked-external").symlink_to(
        FIXTURE / "symlink-target", target_is_directory=True
    )
    return host


def _host_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and "reports" not in path.relative_to(host).parts
    }


def _install_closures(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    install = tmp_path / "installed" / ".agents" / "skills"
    helper = install / "_dart" / COMMON.name
    helper.parent.mkdir(parents=True)
    shutil.copy2(COMMON, helper)
    copied: dict[str, Path] = {}
    for skill, source in SCRIPTS.items():
        destination = install / skill / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        copied[skill] = destination
    return helper, copied


def _tool_args(dart: Path = DART) -> tuple[str, ...]:
    return (
        "--dart",
        str(dart),
        "--direct-test",
        "test/dart_d1_test.dart",
        "--smoke-entrypoint",
        "bin/dart_d1_smoke.dart",
        "--expected-smoke",
        "dart-d1-ok",
    )


def _invoke(
    skill: str,
    script: Path,
    host: Path,
    *,
    dart: Path = DART,
    allow_folder: str | None = None,
) -> subprocess.CompletedProcess[str]:
    base = (
        str(PYTHON),
        "-I",
        "-S",
        str(script),
        "--project-root",
        str(host),
        *_tool_args(dart),
    )
    if skill == "adapt-project":
        args = (*base, "--output-dir", str(host / "reports" / "adapt"))
    elif skill == "find-concept-divergence":
        args = (
            *base,
            "--glossary",
            str(host / ".claude" / "contracts" / "concepts.yaml"),
            "--dart-root",
            "lib",
            "--output",
            str(host / "reports" / "concept" / "findings.jsonl"),
            "--report",
            str(host / "reports" / "concept" / "report.md"),
        )
    else:
        args = (
            *base,
            "--dart-root",
            "lib/src",
            "--output",
            str(host / "reports" / "folder" / "detections.jsonl"),
            *(('--allow-folder', allow_folder) if allow_folder else ()),
        )
    return _run(*args, cwd=host)


def _artifact(skill: str, host: Path) -> dict:
    paths = {
        "adapt-project": host / "reports" / "adapt" / "adapter.json",
        "find-concept-divergence": host / "reports" / "concept" / "findings.json",
        "find-folder-topology-drift": host / "reports" / "folder" / "findings.json",
    }
    return json.loads(paths[skill].read_text(encoding="utf-8"))


def _analysis(skill: str, payload: dict) -> dict:
    if skill == "adapt-project":
        return payload["analysis"]["dart"]
    return payload["analysis"]["dart"]


def _fake_dart(
    path: Path, *, version: str = "3.12.2", version_exit: int = 0
) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'Dart SDK version: {version} (stable) (fixture)' >&2\n"
        f"  exit {version_exit}\n"
        "fi\n"
        "exit 9\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_three_copied_outcomes_roles_hashes_native_and_no_host_mutation(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _host_hashes(host)
    report_decoy = host / "reports" / "decoys" / "billing_alpha.dart"
    report_decoy_before = hashlib.sha256(report_decoy.read_bytes()).hexdigest()
    helper, copied = _install_closures(tmp_path)

    results = {skill: _invoke(skill, script, host) for skill, script in copied.items()}
    assert all(result.returncode == 0 for result in results.values()), {
        skill: result.stdout + result.stderr for skill, result in results.items()
    }

    adapter = _artifact("adapt-project", host)
    assert adapter["status"] == "complete"
    assert adapter["stack"] == {
        "frameworks": [],
        "languages": ["dart"],
        "package_managers": ["pub"],
    }
    assert adapter["project"]["markers"] == ["pubspec.yaml"]
    assert adapter["source_roots"] == [
        {"dart_files": 9, "path": "lib", "source_languages": ["dart"]}
    ]
    assert adapter["commands"]["check"] == [
        "dart analyze --fatal-infos --fatal-warnings ."
    ]
    assert adapter["commands"]["test"] == ["dart test/dart_d1_test.dart"]
    assert adapter["commands"]["smoke"] == ["dart bin/dart_d1_smoke.dart"]
    assert adapter["commands"]["format"] == [
        "dart format --output=none --set-exit-if-changed "
        "lib bin test integration_test tool example"
    ]
    assert adapter["standardization"]["cautions"] == []
    assert (host / "reports" / "adapt" / "adapter.yml").is_file()
    evidence = json.loads((host / "reports" / "adapt" / "evidence.json").read_text())
    assert evidence["evidence"] == {"adapter": "adapter.yml", "report": "report.md"}

    concept = _artifact("find-concept-divergence", host)
    assert concept["status"] == "complete"
    assert concept["outcome"] == "drift-found"
    assert len(concept["findings"]) == 1
    hit = concept["findings"][0]
    assert hit["band"] == "avoid_term_hit"
    assert hit["term"] == "cancelled_order"
    assert hit["file"] == "lib/src/billing_parser.dart"
    source = (host / hit["file"]).read_bytes()
    spelling = source[hit["span"]["start_byte"] : hit["span"]["end_byte"]]
    assert spelling == b"cancelled_order"
    assert hashlib.sha256(spelling).hexdigest() == hit["spelling_sha256"]
    glossary_sha256 = hashlib.sha256(
        (host / ".claude" / "contracts" / "concepts.yaml").read_bytes()
    ).hexdigest()
    assert concept["glossary_sha256"] == glossary_sha256
    assert concept["analysis"]["dart"]["consumer_configuration"]["sha256"] == glossary_sha256

    folder = _artifact("find-folder-topology-drift", host)
    assert folder["status"] == "complete"
    assert folder["outcome"] == "drift-found"
    assert len(folder["findings"]) == 1
    assert folder["findings"][0]["prefix"] == "billing"
    assert set(folder["findings"][0]["files"]) == {
        "lib/src/billing_parser.dart",
        "lib/src/billing_types.dart",
        "lib/src/billing_validator.dart",
    }

    payloads = {
        "adapt-project": adapter,
        "find-concept-divergence": concept,
        "find-folder-topology-drift": folder,
    }
    analyses = [_analysis(skill, payload) for skill, payload in payloads.items()]
    assert len({analysis["snapshot_sha256"] for analysis in analyses}) == 1
    assert all(analysis["status"] == "complete" for analysis in analyses)
    assert all(analysis["source_preserved"] for analysis in analyses)
    assert all(analysis["host_state_preserved"] for analysis in analyses)
    assert all(analysis["tool"]["version"] == "3.12.2" for analysis in analyses)
    for analysis in analyses:
        assert [check["id"] for check in analysis["native_checks"]] == [
            "dart-analyze",
            "format-check",
            "direct-test",
            "executable-smoke",
        ]
        assert all(check["returncode"] == 0 for check in analysis["native_checks"])
        assert analysis["native_checks"][-1]["stdout"].strip() == "dart-d1-ok"
        config = {row["file"]: row["sha256"] for row in analysis["configuration_manifest"]}
        assert config["pubspec.yaml"] == hashlib.sha256(
            (host / "pubspec.yaml").read_bytes()
        ).hexdigest()
        for row in analysis["source_manifest"]:
            assert row["sha256"] == hashlib.sha256((host / row["file"]).read_bytes()).hexdigest()

    roles = {
        row["file"]: row.get("reason", row["role"])
        for row in analyses[0]["inventory"]
    }
    assert roles["lib/src/billing_parser.dart"] == "library"
    assert roles["lib/src/billing_part.dart"] == "part-file"
    assert roles["lib/src/billing_generated.g.dart"] == "generated-file"
    assert roles["lib/src/billing_generated.freezed.dart"] == "generated-file"
    assert roles["lib/src/billing_generated.mocks.dart"] == "generated-file"
    assert roles["lib/src/generated_header.dart"] == "generated-marker"
    assert roles["test/dart_d1_test.dart"] == "test"
    assert roles["integration_test/billing_alpha.dart"] == "test"
    assert roles["bin/billing_alpha.dart"] == "executable"
    assert roles["tool/billing_alpha.dart"] == "tooling"
    assert roles["example/billing_alpha.dart"] == "example"
    assert roles["generated/billing_alpha.dart"] == "generated-tree"
    assert roles["vendor/package/billing_alpha.dart"] == "vendor"
    assert roles["build/billing_alpha.dart"] == "build"
    assert roles["reports/decoys/billing_alpha.dart"] == "report"
    assert roles["linked-external"] == "symlink"
    assert _host_hashes(host) == before
    assert hashlib.sha256(report_decoy.read_bytes()).hexdigest() == report_decoy_before
    assert not (host / ".dart_tool").exists()
    assert not (host / "pubspec.lock").exists()
    assert helper.is_file()
    for script in copied.values():
        text = script.read_text(encoding="utf-8")
        assert "dart_project_snapshot" in text
        assert str(ROOT) not in text


def test_clean_cases_and_must_not_fire_boundaries(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    helper, copied = _install_closures(tmp_path)
    parser = host / "lib" / "src" / "billing_parser.dart"
    parser.write_text(
        parser.read_text(encoding="utf-8").replace("cancelled_order", "canceled_order", 1),
        encoding="utf-8",
    )

    concept = _invoke("find-concept-divergence", copied["find-concept-divergence"], host)
    assert concept.returncode == 0, concept.stdout + concept.stderr
    concept_payload = _artifact("find-concept-divergence", host)
    assert concept_payload["outcome"] == "clean"
    assert concept_payload["findings"] == []

    allowed = _invoke(
        "find-folder-topology-drift",
        copied["find-folder-topology-drift"],
        host,
        allow_folder="lib/src",
    )
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    allowed_payload = _artifact("find-folder-topology-drift", host)
    assert allowed_payload["outcome"] == "clean"
    assert allowed_payload["findings"] == []

    (host / "lib" / "src" / "billing_validator.dart").unlink()
    barrel = host / "lib" / "src" / "billing.dart"
    barrel.write_text(
        barrel.read_text(encoding="utf-8").replace("export 'billing_validator.dart';\n", ""),
        encoding="utf-8",
    )
    below = _invoke("find-folder-topology-drift", copied["find-folder-topology-drift"], host)
    assert below.returncode == 0, below.stdout + below.stderr
    below_payload = _artifact("find-folder-topology-drift", host)
    assert below_payload["outcome"] == "clean"
    assert below_payload["findings"] == []
    assert helper.is_file()


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_valid_failed_valid_same_destination_clears_stale(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    valid = _invoke(skill, copied[skill], host)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert _artifact(skill, host)["status"] == "complete"

    broken = _fake_dart(tmp_path / "broken-dart", version_exit=9)
    failed = _invoke(skill, copied[skill], host, dart=broken)
    assert failed.returncode == 1
    failed_payload = _artifact(skill, host)
    assert failed_payload["status"] == "failed"
    assert failed_payload.get("findings", []) == []
    reports = {
        "adapt-project": host / "reports" / "adapt" / "report.md",
        "find-concept-divergence": host / "reports" / "concept" / "report.md",
        "find-folder-topology-drift": host / "reports" / "folder" / "report.md",
    }
    failed_report = reports[skill].read_text(encoding="utf-8").casefold()
    assert "status:** `failed`" in failed_report
    assert "outcome:** `clean" not in failed_report

    recovered = _invoke(skill, copied[skill], host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _artifact(skill, host)["status"] == "complete"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
@pytest.mark.parametrize("tool_state", ["missing", "old", "broken"])
def test_missing_old_and_broken_tools_are_visible_terminal_states(
    skill: str, tool_state: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    tools = {
        "missing": tmp_path / "missing-dart",
        "old": _fake_dart(tmp_path / "old-dart", version="3.11.9"),
        "broken": _fake_dart(tmp_path / "broken-dart", version_exit=9),
    }
    result = _invoke(skill, copied[skill], host, dart=tools[tool_state])
    payload = _artifact(skill, host)
    expected = (2, "partial") if tool_state != "broken" else (1, "failed")
    assert (result.returncode, payload["status"]) == expected
    assert payload.get("findings", []) == []


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_malformed_source_fails_without_source_mutation(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    shutil.copy2(FIXTURE / "malformed" / "Broken.dart", host / "lib" / "broken.dart")
    before = _host_hashes(host)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 1
    payload = _artifact(skill, host)
    assert payload["status"] == "failed"
    assert _analysis(skill, payload)["failure_kind"] == "syntax-error"
    assert payload.get("findings", []) == []
    assert _host_hashes(host) == before


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_unreadable_utf8_authored_source_fails_atomically(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    unreadable = host / "lib" / "unreadable.dart"
    unreadable.write_bytes(b"\xff\xfe")
    before = _host_hashes(host)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 1
    payload = _artifact(skill, host)
    assert payload["status"] == "failed"
    assert _analysis(skill, payload)["failure_kind"] == "unreadable-source"
    assert payload.get("findings", []) == []
    assert _host_hashes(host) == before


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_symlinked_report_directory_is_rejected(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    report_link = host / "reports" / {  # type: ignore[index]
        "adapt-project": "adapt",
        "find-concept-divergence": "concept",
        "find-folder-topology-drift": "folder",
    }[skill]
    report_link.symlink_to(outside, target_is_directory=True)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 2
    assert list(outside.iterdir()) == []


def test_shared_snapshot_deletion_and_caller_knowledge_boundary() -> None:
    helper = COMMON.read_text(encoding="utf-8")
    for policy in (
        "dart-analyze",
        "format-check",
        "source_manifest",
        "configuration_manifest",
        "generated-file",
        "part-file",
        "unexpected-source-mutation",
        "symlink",
    ):
        assert policy in helper
    for script in SCRIPTS.values():
        text = script.read_text(encoding="utf-8")
        assert "collect_snapshot" in text
        assert "subprocess" not in text
        assert "_native_check" not in text
        assert "generated-file" not in text
        assert "pubspec.lock" not in text
