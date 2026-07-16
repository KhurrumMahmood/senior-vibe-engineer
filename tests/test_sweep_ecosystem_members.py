"""Parser-backed ecosystem providers at the sweep manifest boundary."""

from __future__ import annotations

import copy
import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import replace
from pathlib import Path

import pytest

from sweep import ecosystem as ecosystem_module
from sweep import process as process_module
from sweep.ecosystem import (
    PARSER_ECOSYSTEM_LANGUAGES,
    run_complexity_provider,
    run_omnibus_provider,
)
from sweep.manifest import build_manifest
from sweep.process import capture_process
from sweep.schemas import SchemaValidationError, validate_manifest, validate_provider_observation


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests/fixtures/sweep/ecosystem"
COMPLEXITY_BAD = REPO_ROOT / ".claude/skills/find-complexity-hotspots/fixtures/bad"
COMPLEXITY_GOOD = REPO_ROOT / ".claude/skills/find-complexity-hotspots/fixtures/good"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
REVISION = "fixture-revision"


def _load_omnibus_detector():
    path = REPO_ROOT / ".claude/skills/find-omnibus/scripts/detect.py"
    spec = importlib.util.spec_from_file_location("sweep_omnibus_equivalence", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest(*runs, paths: list[str] | None = None):
    return build_manifest(
        capability_registry_version=1,
        paths=paths or ["tests/fixtures/sweep/ecosystem"],
        case_sensitive=True,
        roots=paths or ["tests/fixtures/sweep/ecosystem"],
        exclusions=[],
        source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=[run.observation for run in runs],
        findings=[finding for run in runs for finding in run.findings],
        repo_root=REPO_ROOT,
    )


def _native_observation(provider: str, language: str, path: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider": provider,
        "language": language,
        "provider_kind": "native-shim",
        "scope": {
            "paths": [path],
            "case_sensitive": True,
            "roots": ["."],
            "exclusions": [],
        },
        "command": {
            "executable": provider,
            "argv": [provider, "check"],
            "timeout_seconds": 30,
            "output_format": "json",
            "output_byte_limit": 1_048_576,
        },
        "tool_version": "fixture-1",
        "exit": {"code": 0, "classification": "clean"},
        "raw": {
            "stdout_sha256": EMPTY_SHA256,
            "stderr_sha256": EMPTY_SHA256,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
        },
        "status": "completed",
        "failure": None,
    }


def test_complexity_characterization_is_preserved_through_observation_contract() -> None:
    bad = run_complexity_provider(REPO_ROOT, [COMPLEXITY_BAD], observation_index=0)
    good = run_complexity_provider(REPO_ROOT, [COMPLEXITY_GOOD], observation_index=0)

    assert validate_provider_observation(bad.observation) == bad.observation
    assert bad.observation["status"] == "completed"
    assert bad.observation["exit"]["classification"] == "diagnostics"
    assert {finding.native_rule_id for finding in bad.findings} == {
        "django-query-in-loop",
        "high-branch-function",
        "membership-scan-in-loop",
        "nested-loop",
        "repeated-scan-in-loop",
        "sort-in-loop",
    }
    assert len(bad.findings) == 6
    assert all(finding.provider == "cx" for finding in bad.findings)
    assert all(finding.language == "python" for finding in bad.findings)

    assert validate_provider_observation(good.observation) == good.observation
    assert good.observation["status"] == "completed"
    assert good.observation["exit"]["classification"] == "clean"
    assert good.findings == ()


@pytest.mark.parametrize(
    ("language", "fixture"),
    [
        ("python", FIXTURES / "python"),
        ("typescript", FIXTURES / "typescript"),
    ],
)
def test_single_language_manifests_include_parser_backed_observations(
    language: str,
    fixture: Path,
) -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [fixture],
        language=language,
        observation_index=0,
    )
    manifest = validate_manifest(_manifest(run, paths=[fixture.relative_to(REPO_ROOT).as_posix()]))

    assert manifest["providers"][0]["provider"] == "omnibus"
    assert manifest["providers"][0]["language"] == language
    assert manifest["providers"][0]["provider_kind"] == "parser-backed-ecosystem"
    assert manifest["providers"][0]["status"] == "completed"
    assert manifest["counts"] == {"omnibus": 1}
    finding = manifest["findings"][0]
    assert finding["identity"]["language"] == language
    assert finding["native_rule_id"] == "omnibus"
    assert finding["metrics"]["clusters"] == 4
    assert finding["metrics"]["and_count"] == 3


def test_mixed_manifest_composes_parser_members_without_replacing_native_rust_go() -> None:
    complexity = run_complexity_provider(REPO_ROOT, [FIXTURES], observation_index=1)
    omnibus_python = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES],
        language="python",
        observation_index=3,
    )
    omnibus_typescript = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES],
        language="typescript",
        observation_index=4,
    )
    rust = _native_observation("clippy", "rust", "tests/fixtures/sweep/ecosystem")
    go = _native_observation("go-vet", "go", "tests/fixtures/sweep/ecosystem")
    manifest = build_manifest(
        capability_registry_version=1,
        paths=["tests/fixtures/sweep/ecosystem"],
        case_sensitive=True,
        roots=["tests/fixtures/sweep/ecosystem"],
        exclusions=[],
        source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=[
            rust,
            complexity.observation,
            go,
            omnibus_python.observation,
            omnibus_typescript.observation,
        ],
        findings=[
            *complexity.findings,
            *omnibus_python.findings,
            *omnibus_typescript.findings,
        ],
        repo_root=REPO_ROOT,
    )

    parser_rows = [
        (row["provider"], row["language"])
        for row in manifest["providers"]
        if row["provider_kind"] == "parser-backed-ecosystem"
    ]
    native_rows = [
        (row["provider"], row["language"])
        for row in manifest["providers"]
        if row["provider_kind"] == "native-shim"
    ]
    assert parser_rows == [("cx", "python"), ("omnibus", "python"), ("omnibus", "typescript")]
    assert native_rows == [("clippy", "rust"), ("go-vet", "go")]
    assert {row["identity"]["language"] for row in manifest["findings"]} == {
        "python",
        "typescript",
    }
    assert manifest["counts"] == {"cx": 6, "omnibus": 2}


def test_parser_failure_returns_failed_observation_and_cannot_publish_clean_zero(tmp_path: Path) -> None:
    broken = tmp_path / "src"
    broken.mkdir()
    (broken / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    complexity = run_complexity_provider(tmp_path, ["src"], observation_index=0)
    omnibus = run_omnibus_provider(
        tmp_path,
        ["src"],
        language="python",
        observation_index=0,
    )

    for run in (complexity, omnibus):
        assert validate_provider_observation(run.observation) == run.observation
        assert run.observation["status"] == "failed"
        assert run.observation["exit"]["classification"] == "tool_failure"
        assert run.observation["failure"]["kind"] == "parse_failure"
        assert run.findings == ()
        with pytest.raises(SchemaValidationError, match="publishable manifest requires"):
            _manifest(run)


def test_recorded_command_replays_exact_completed_artifacts(tmp_path: Path) -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "typescript"],
        language="typescript",
        observation_index=0,
    )
    replay = subprocess.run(
        run.observation["command"]["argv"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    assert run.observation["command"]["executable"] == run.observation["command"]["argv"][0]
    assert run.observation["command"]["argv"][1].endswith("scripts/sweep/provider_process.py")
    assert replay.returncode == run.observation["exit"]["code"]
    assert hashlib.sha256(replay.stdout).hexdigest() == run.observation["raw"]["stdout_sha256"]
    assert hashlib.sha256(replay.stderr).hexdigest() == run.observation["raw"]["stderr_sha256"]
    assert len(replay.stdout) == run.observation["raw"]["stdout_bytes"]
    assert len(replay.stderr) == run.observation["raw"]["stderr_bytes"]


def test_provider_timeout_and_overflow_retain_actual_artifact_provenance(monkeypatch) -> None:
    monkeypatch.setattr(ecosystem_module, "_TIMEOUT_SECONDS", 0.001)
    timed_out = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "typescript"],
        language="typescript",
        observation_index=0,
    )
    assert timed_out.observation["status"] == "failed"
    assert timed_out.observation["failure"]["kind"] == "timeout"
    assert timed_out.findings == ()

    monkeypatch.setattr(ecosystem_module, "_TIMEOUT_SECONDS", 300)
    monkeypatch.setattr(ecosystem_module, "_OUTPUT_BYTE_LIMIT", 32)
    overflow = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "typescript"],
        language="typescript",
        observation_index=0,
    )
    assert overflow.observation["status"] == "failed"
    assert overflow.observation["failure"]["kind"] == "output_overflow"
    assert overflow.observation["raw"]["stdout_bytes"] > 32
    assert overflow.observation["failure"]["details"]["stdout_sha256"] == (
        overflow.observation["raw"]["stdout_sha256"]
    )
    assert overflow.findings == ()

    false_clean = copy.deepcopy(overflow.observation)
    false_clean.update(status="completed", failure=None)
    false_clean["exit"] = {"code": 0, "classification": "diagnostics"}
    with pytest.raises(SchemaValidationError, match="artifact exceeds"):
        validate_provider_observation(false_clean)


def test_missing_complexity_scope_is_failed_and_never_publishable() -> None:
    missing = run_complexity_provider(
        REPO_ROOT,
        ["definitely-missing-scope"],
        observation_index=0,
    )

    assert missing.observation["status"] == "failed"
    assert missing.observation["exit"]["classification"] == "tool_failure"
    assert missing.observation["failure"]["kind"] == "schema_mismatch"
    assert missing.findings == ()
    with pytest.raises(SchemaValidationError, match="publishable manifest requires"):
        _manifest(missing)

    wrong_language = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="typescript",
        observation_index=0,
    )
    assert wrong_language.observation["status"] == "failed"
    assert wrong_language.observation["failure"]["kind"] == "schema_mismatch"
    assert wrong_language.findings == ()


def test_complexity_scope_excluded_by_exact_detector_selection_fails_loudly(
    tmp_path: Path,
) -> None:
    direct = tmp_path / "test_only.py"
    direct.write_text("def harmless():\n    return 1\n", encoding="utf-8")
    directory = tmp_path / "only-tests"
    directory.mkdir()
    (directory / "tests_helpers.py").write_text(
        "def harmless():\n    return 1\n",
        encoding="utf-8",
    )

    for scopes in ([direct], [directory]):
        run = run_complexity_provider(tmp_path, scopes, observation_index=0)

        assert run.observation["status"] == "failed"
        assert run.observation["failure"]["kind"] == "schema_mismatch"
        assert run.findings == ()


def test_manifest_rejects_out_of_scope_findings_and_unbound_observation_indexes() -> None:
    omnibus = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    declared = ["tests/fixtures/sweep/ecosystem/python"]
    outside = replace(omnibus.findings[0], path="outside/omnibus.py")
    with pytest.raises(SchemaValidationError, match="declared scope"):
        build_manifest(
            capability_registry_version=1,
            paths=declared,
            case_sensitive=True,
            roots=declared,
            exclusions=[],
            source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
            providers=[omnibus.observation],
            findings=[outside],
            repo_root=REPO_ROOT,
        )

    unbound = replace(omnibus.findings[0], observation_index=999)
    with pytest.raises(SchemaValidationError, match="observation_index"):
        build_manifest(
            capability_registry_version=1,
            paths=declared,
            case_sensitive=True,
            roots=declared,
            exclusions=[],
            source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
            providers=[omnibus.observation],
            findings=[unbound],
            repo_root=REPO_ROOT,
        )

    complexity = run_complexity_provider(REPO_ROOT, [FIXTURES], observation_index=0)
    bound_omnibus = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=1,
    )
    wrong_provider = replace(bound_omnibus.findings[0], observation_index=0)
    with pytest.raises(SchemaValidationError, match="expected .*omnibus.*python"):
        build_manifest(
            capability_registry_version=1,
            paths=["tests/fixtures/sweep/ecosystem"],
            case_sensitive=True,
            roots=["tests/fixtures/sweep/ecosystem"],
            exclusions=[],
            source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
            providers=[complexity.observation, bound_omnibus.observation],
            findings=[wrong_provider],
            repo_root=REPO_ROOT,
        )


def test_observation_scope_is_canonical_and_cannot_under_cover_manifest() -> None:
    narrow = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )

    assert narrow.observation["scope"] == {
        "paths": ["tests/fixtures/sweep/ecosystem/python"],
        "case_sensitive": True,
        "roots": ["."],
        "exclusions": [],
    }
    with pytest.raises(SchemaValidationError, match="does not cover manifest scope"):
        build_manifest(
            capability_registry_version=1,
            paths=["tests/fixtures/sweep/ecosystem"],
            case_sensitive=True,
            roots=["."],
            exclusions=[],
            source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
            providers=[narrow.observation],
            findings=[],
            repo_root=REPO_ROOT,
        )

    outside = replace(
        narrow.findings[0],
        path="tests/fixtures/sweep/ecosystem/typescript/omnibus.ts",
    )
    typescript_native = _native_observation(
        "tsc",
        "typescript",
        "tests/fixtures/sweep/ecosystem/typescript",
    )
    with pytest.raises(SchemaValidationError, match="observation scope"):
        build_manifest(
            capability_registry_version=1,
            paths=[
                "tests/fixtures/sweep/ecosystem/python",
                "tests/fixtures/sweep/ecosystem/typescript",
            ],
            case_sensitive=True,
            roots=["."],
            exclusions=[],
            source={"revision": REVISION, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
            providers=[narrow.observation, typescript_native],
            findings=[outside],
            repo_root=REPO_ROOT,
        )


def test_bounded_capture_retains_only_limit_plus_one_and_deadline_wins(monkeypatch) -> None:
    overflow = capture_process(
        [sys.executable, "-c", "import os; os.write(1, b'x' * 1048576)"],
        cwd=REPO_ROOT,
        env=None,
        timeout_seconds=30,
        output_byte_limit=31,
    )

    assert overflow.output_overflow is True
    assert overflow.raw["stdout_bytes"] == 32
    assert overflow.stdout == b"x" * 32
    assert overflow.fault == "output_overflow"

    class CompletedProcess:
        def __init__(self) -> None:
            stdout_read, stdout_write = os.pipe()
            stderr_read, stderr_write = os.pipe()
            os.close(stdout_write)
            os.close(stderr_write)
            self.stdout = os.fdopen(stdout_read, "rb", buffering=0)
            self.stderr = os.fdopen(stderr_read, "rb", buffering=0)
            self.pid = 1
            self.returncode = 0

        def poll(self) -> int:
            return self.returncode

        def wait(self) -> int:
            return self.returncode

        def kill(self) -> None:
            raise AssertionError("a completed process must not be killed")

    completed = CompletedProcess()
    monkeypatch.setattr(process_module.subprocess, "Popen", lambda *_args, **_kwargs: completed)
    ticks = iter((0.0, 2.0))
    expired = capture_process(
        ["already-completed"],
        cwd=REPO_ROOT,
        env=None,
        timeout_seconds=1,
        output_byte_limit=31,
        monotonic=lambda: next(ticks),
    )

    assert expired.timed_out is True
    assert expired.returncode == 0
    assert expired.fault == "timeout"


def test_complexity_uses_one_typed_parse_and_reuses_the_tree(monkeypatch) -> None:
    detector = ecosystem_module._load_detector(
        REPO_ROOT / ".claude/skills/find-complexity-hotspots/scripts/detect.py",
        "sweep_complexity_parse_count",
    )
    source = COMPLEXITY_BAD / "hotspots.py"
    adapter = detector.get_adapter(source, capability=detector.CAP_PYTHON_AST)
    original = adapter.parse
    calls = 0

    def counted(text: str):
        nonlocal calls
        calls += 1
        return original(text)

    monkeypatch.setattr(adapter, "parse", counted)
    records = detector.detect(REPO_ROOT, [source.as_posix()], max_findings=500)

    assert len(records) == 6
    assert calls == 1


def test_parser_members_are_deterministic_agent_free_and_reject_rust_go_claims(monkeypatch) -> None:
    def denied(*_args, **_kwargs):
        raise AssertionError("network/model boundary must not be reached")

    monkeypatch.setattr("socket.socket", denied)
    monkeypatch.setattr("socket.getaddrinfo", denied)
    monkeypatch.setattr(urllib.request, "urlopen", denied)

    complexity = run_complexity_provider(REPO_ROOT, [COMPLEXITY_BAD], observation_index=0)
    python = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    first = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "typescript"],
        language="typescript",
        observation_index=0,
    )
    second = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "typescript"],
        language="typescript",
        observation_index=0,
    )
    assert complexity.observation["status"] == "completed"
    assert python.observation["status"] == "completed"
    assert first == second
    assert PARSER_ECOSYSTEM_LANGUAGES == frozenset({"python", "typescript"})
    for unsupported in ("rust", "go"):
        with pytest.raises(ValueError, match="only python and typescript"):
            run_omnibus_provider(
                REPO_ROOT,
                [FIXTURES],
                language=unsupported,
                observation_index=0,
            )


def test_omnibus_cli_and_library_are_byte_equivalent_with_one_walk_each(
    monkeypatch,
    tmp_path: Path,
) -> None:
    detector = _load_omnibus_detector()
    calls = 0
    original = detector._walk_source_files

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(detector, "_walk_source_files", counted)
    expected = detector.detect(FIXTURES / "typescript", REPO_ROOT, languages={"typescript"})
    assert calls == 1

    output = tmp_path / "omnibus.jsonl"
    result = detector.main([
        "--target", str(FIXTURES / "typescript"),
        "--project-root", str(REPO_ROOT),
        "--output", str(output),
        "--language", "typescript",
    ])
    assert result == 0
    assert calls == 2
    expected_jsonl = "".join(json.dumps(row) + "\n" for row in expected)
    assert output.read_text(encoding="utf-8") == expected_jsonl
