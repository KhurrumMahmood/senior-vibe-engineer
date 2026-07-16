from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from sweep import build_manifest
from sweep.native import (
    ProviderExecutionError,
    discover_executable,
    execute_provider,
    normalize_provider_output,
)
from sweep.schemas import validate_provider_observation
from sweep_shims import resolve_native_providers, resolve_shims


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "sweep"
RAW = FIXTURES / "raw"
HOSTS = FIXTURES / "hosts"


def _contract(language: str, provider: str):
    contracts = resolve_native_providers([language])[language]
    return next(contract for contract in contracts if contract.provider == provider)


def _bytes(relative: str) -> bytes:
    return RAW.joinpath(relative).read_bytes()


def test_im_5_registry_resolves_every_native_provider_without_local_enums():
    resolved = resolve_native_providers(["python", "typescript", "rust", "go"])
    compatibility = resolve_shims(["python", "typescript", "rust", "go"])

    assert [row.provider for row in resolved["python"]] == ["ruff"]
    assert [row.provider for row in resolved["typescript"]] == [
        "eslint",
        "typescript-compiler",
    ]
    assert [row.provider for row in resolved["rust"]] == ["clippy"]
    assert [row.provider for row in resolved["go"]] == ["go-vet"]
    assert compatibility["typescript"]["native_providers"] == [
        "eslint",
        "typescript-compiler",
    ]
    assert all(row.provider_kind == "native" for rows in resolved.values() for row in rows)


@pytest.mark.parametrize(
    ("language", "provider", "stdout_fixture", "stderr_fixture", "exit_code", "version", "rule", "path"),
    [
        ("python", "ruff", "ruff/valid.json", None, 1, "ruff 0.6.9", "F401", "src/sample.py"),
        (
            "typescript",
            "eslint",
            "eslint/valid.json",
            None,
            1,
            "v9.38.0",
            "no-unused-vars",
            "src/lint.js",
        ),
        (
            "typescript",
            "typescript-compiler",
            "typescript-compiler/valid.txt",
            None,
            2,
            "Version 5.9.3",
            "TS2322",
            "src/index.ts",
        ),
        (
            "rust",
            "clippy",
            "clippy/valid.jsonl",
            None,
            0,
            "clippy 0.1.89 (29483883e 2025-08-04)",
            "clippy::ptr_arg",
            "src/lib.rs",
        ),
        (
            "go",
            "go-vet",
            None,
            "go-vet/valid.json",
            1,
            "vet version go1.24.6",
            "printf",
            "main.go",
        ),
    ],
)
# spec:portable-batch-sweep::IM-6
def test_im_6_saved_native_outputs_retain_ids_locations_versions_and_raw_provenance(
    language,
    provider,
    stdout_fixture,
    stderr_fixture,
    exit_code,
    version,
    rule,
    path,
):
    stdout = _bytes(stdout_fixture) if stdout_fixture else b""
    stderr = _bytes(stderr_fixture) if stderr_fixture else b""

    result = normalize_provider_output(
        _contract(language, provider),
        root=HOSTS / language / "before",
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        tool_version=version,
        executable=f"/saved/{provider}",
    )

    observation = validate_provider_observation(result.observation)
    finding = result.findings[0]
    assert observation["tool_version"] == version
    assert observation["exit"]["classification"] == "diagnostics"
    assert observation["raw"] == {
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
    }
    assert finding.native_rule_id == rule
    assert finding.path == path
    assert finding.line is not None
    assert finding.column is not None
    assert finding.native_severity
    assert finding.rule_semantic_key.endswith(":v1")


def test_im_6_all_saved_native_results_compose_at_the_shared_manifest_boundary():
    cases = (
        ("rust", "clippy", "clippy/valid.jsonl", None, 0, "clippy 0.1.89"),
        ("typescript", "eslint", "eslint/valid.json", None, 1, "v9.38.0"),
        ("go", "go-vet", None, "go-vet/valid.json", 1, "vet version go1.24.6"),
        ("python", "ruff", "ruff/valid.json", None, 1, "ruff 0.6.9"),
        (
            "typescript",
            "typescript-compiler",
            "typescript-compiler/valid.txt",
            None,
            2,
            "Version 5.9.3",
        ),
    )
    results = [
        normalize_provider_output(
            _contract(language, provider),
            root=HOSTS / language / "before",
            stdout=_bytes(stdout_fixture) if stdout_fixture else b"",
            stderr=_bytes(stderr_fixture) if stderr_fixture else b"",
            exit_code=exit_code,
            tool_version=version,
            executable=f"/saved/{provider}",
            observation_index=index,
        )
        for index, (
            language,
            provider,
            stdout_fixture,
            stderr_fixture,
            exit_code,
            version,
        ) in enumerate(cases)
    ]

    manifest = build_manifest(
        capability_registry_version=1,
        paths=(".",),
        case_sensitive=True,
        roots=(".",),
        exclusions=(),
        source={
            "revision": "0" * 40,
            "dirty": False,
            "dirty_state_hash": hashlib.sha256(b"").hexdigest(),
        },
        providers=tuple(result.observation for result in results),
        findings=tuple(finding for result in results for finding in result.findings),
    )

    assert manifest["status"] == "complete"
    assert manifest["total"] == 5
    assert manifest["counts"] == {
        "clippy": 1,
        "eslint": 1,
        "go-vet": 1,
        "ruff": 1,
        "typescript-compiler": 1,
    }
    assert {row["native_rule_id"] for row in manifest["findings"]} == {
        "F401",
        "TS2322",
        "clippy::ptr_arg",
        "no-unused-vars",
        "printf",
    }


@pytest.mark.parametrize(
    ("language", "provider", "stdout_fixture", "stderr_fixture"),
    [
        ("python", "ruff", "ruff/empty.json", None),
        ("typescript", "eslint", "eslint/empty.json", None),
        ("typescript", "typescript-compiler", "typescript-compiler/empty.txt", None),
        ("rust", "clippy", "clippy/empty.jsonl", None),
        ("go", "go-vet", None, "go-vet/empty.json"),
    ],
)
def test_im_6_saved_clean_output_is_completed_zero_not_failure(
    language, provider, stdout_fixture, stderr_fixture
):
    result = normalize_provider_output(
        _contract(language, provider),
        root=HOSTS / language / "clean",
        stdout=_bytes(stdout_fixture) if stdout_fixture else b"",
        stderr=_bytes(stderr_fixture) if stderr_fixture else b"",
        exit_code=0,
        tool_version="saved-version",
        executable=f"/saved/{provider}",
    )

    assert result.findings == ()
    assert result.observation["status"] == "completed"
    assert result.observation["exit"]["classification"] == "clean"


def _failure_kind(call) -> str:
    with pytest.raises(ProviderExecutionError) as caught:
        call()
    assert validate_provider_observation(caught.value.observation)["status"] == "failed"
    return caught.value.failure["kind"]


def test_im_6_fault_injection_covers_every_loud_failure_class(tmp_path):
    ruff = _contract("python", "ruff")
    missing = replace(ruff, executable_candidates=("definitely-not-a-sweep-binary",))
    timeout = replace(
        ruff,
        executable_candidates=(sys.executable,),
        argv=("-c", "import time; time.sleep(2)"),
        timeout_seconds=0.05,
    )
    overflow = replace(ruff, output_byte_limit=8)

    calls = {
        "missing_executable": lambda: execute_provider(missing, root=tmp_path),
        "unexpected_exit": lambda: normalize_provider_output(
            ruff,
            root=tmp_path,
            stdout=_bytes("ruff/valid.json"),
            stderr=b"",
            exit_code=99,
            tool_version="ruff 0.6.9",
            executable="/saved/ruff",
        ),
        "parse_failure": lambda: normalize_provider_output(
            ruff,
            root=tmp_path,
            stdout=_bytes("faults/malformed.json"),
            stderr=b"",
            exit_code=1,
            tool_version="ruff 0.6.9",
            executable="/saved/ruff",
        ),
        "timeout": lambda: execute_provider(
            timeout,
            root=tmp_path,
            tool_version="ruff 0.6.9",
        ),
        "truncated_output": lambda: normalize_provider_output(
            ruff,
            root=tmp_path,
            stdout=_bytes("faults/truncated.json"),
            stderr=b"",
            exit_code=1,
            tool_version="ruff 0.6.9",
            executable="/saved/ruff",
        ),
        "output_overflow": lambda: normalize_provider_output(
            overflow,
            root=tmp_path,
            stdout=_bytes("faults/oversized.txt"),
            stderr=b"",
            exit_code=1,
            tool_version="ruff 0.6.9",
            executable="/saved/ruff",
        ),
        "output_corruption": lambda: normalize_provider_output(
            ruff,
            root=tmp_path,
            stdout=bytes.fromhex(_bytes("faults/corrupt.hex").decode().strip()),
            stderr=b"",
            exit_code=1,
            tool_version="ruff 0.6.9",
            executable="/saved/ruff",
        ),
        "schema_mismatch": lambda: normalize_provider_output(
            ruff,
            root=tmp_path,
            stdout=_bytes("faults/schema-mismatch.json"),
            stderr=b"",
            exit_code=1,
            tool_version="ruff 0.6.9",
            executable="/saved/ruff",
        ),
        "missing_completion": lambda: normalize_provider_output(
            _contract("rust", "clippy"),
            root=tmp_path,
            stdout=_bytes("clippy/valid.jsonl").splitlines(keepends=True)[0],
            stderr=b"",
            exit_code=0,
            tool_version="clippy 0.1.89",
            executable="/saved/cargo",
        ),
    }

    assert {name: _failure_kind(call) for name, call in calls.items()} == {
        name: name for name in calls
    }


@pytest.mark.sweep_live
@pytest.mark.parametrize(
    ("language", "provider", "expected_rule"),
    [
        ("python", "ruff", "F401"),
        ("typescript", "eslint", "no-unused-vars"),
        ("typescript", "typescript-compiler", "TS2322"),
        ("rust", "clippy", "clippy::"),
        ("go", "go-vet", "printf"),
    ],
)
def test_im_6_live_minimal_project_reaches_native_output_boundary(
    language, provider, expected_rule, tmp_path
):
    contract = _contract(language, provider)
    if discover_executable(contract, root=HOSTS / language / "before") is None:
        pytest.skip(f"{provider} executable is not installed")

    before = execute_provider(
        contract,
        root=HOSTS / language / "before",
        artifact_dir=tmp_path / "before",
    )
    clean = execute_provider(
        contract,
        root=HOSTS / language / "clean",
        artifact_dir=tmp_path / "clean",
    )

    assert any(expected_rule in finding.native_rule_id for finding in before.findings)
    assert clean.findings == ()
    for result, artifact_dir in ((before, tmp_path / "before"), (clean, tmp_path / "clean")):
        assert result.observation["status"] == "completed"
        stdout = artifact_dir.joinpath(f"{provider}.stdout")
        stderr = artifact_dir.joinpath(f"{provider}.stderr")
        assert stdout.exists()
        assert stderr.exists()
        assert hashlib.sha256(stdout.read_bytes()).hexdigest() == result.observation["raw"][
            "stdout_sha256"
        ]
        assert hashlib.sha256(stderr.read_bytes()).hexdigest() == result.observation["raw"][
            "stderr_sha256"
        ]
