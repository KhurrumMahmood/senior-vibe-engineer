"""Adversarial trust-boundary tests for parser-backed provider observations."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from sweep.ecosystem import run_complexity_provider, run_omnibus_provider
from sweep.manifest import build_manifest
from sweep.schemas import SchemaValidationError, validate_provider_observation


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests/fixtures/sweep/ecosystem"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _build(observation, findings, *, repo_root: Path = REPO_ROOT):
    scope = observation["scope"]
    return build_manifest(
        capability_registry_version=1,
        paths=scope["paths"],
        case_sensitive=scope["case_sensitive"],
        roots=scope["roots"],
        exclusions=scope["exclusions"],
        source={"revision": "fixture", "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=[observation],
        findings=findings,
        repo_root=repo_root,
    )


def _filtered_complexity(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    nested = (
        "def nested(rows):\n"
        "    for outer in rows:\n"
        "        for inner in rows:\n"
        "            print(outer, inner)\n"
    )
    (source / "included.py").write_text(nested, encoding="utf-8")
    (source / "excluded.py").write_text(nested, encoding="utf-8")
    return run_complexity_provider(
        tmp_path,
        ["src"],
        roots=["src"],
        exclusions=["src/excluded.py"],
        observation_index=0,
    )


@pytest.mark.parametrize(
    "attack",
    [
        "broaden-paths",
        "narrow-paths",
        "broaden-roots",
        "narrow-roots",
        "remove-exclusion",
        "add-exclusion",
        "case-policy",
        "provider",
        "language",
    ],
)
def test_scope_and_identity_are_bound_to_recorded_argv(tmp_path: Path, attack: str) -> None:
    forged = copy.deepcopy(_filtered_complexity(tmp_path).observation)
    mutations = {
        "broaden-paths": ("scope", "paths", ["."]),
        "narrow-paths": ("scope", "paths", ["src/included.py"]),
        "broaden-roots": ("scope", "roots", ["."]),
        "narrow-roots": ("scope", "roots", ["src/nested"]),
        "remove-exclusion": ("scope", "exclusions", []),
        "add-exclusion": (
            "scope",
            "exclusions",
            ["src/excluded.py", "src/other.py"],
        ),
        "case-policy": ("scope", "case_sensitive", False),
    }
    if attack in mutations:
        parent, field, value = mutations[attack]
        forged[parent][field] = value
    else:
        forged[attack] = "omnibus" if attack == "provider" else "typescript"
    with pytest.raises(SchemaValidationError, match="command.*argv"):
        validate_provider_observation(forged)


def test_manifest_rejects_scope_relabel_with_unchanged_command_and_artifacts() -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    forged = copy.deepcopy(run.observation)
    forged["scope"]["paths"] = ["tests/fixtures/sweep/ecosystem"]
    forged["scope"]["roots"] = ["tests/fixtures/sweep/ecosystem"]
    with pytest.raises(SchemaValidationError, match="command.*argv"):
        _build(forged, run.findings)


@pytest.mark.parametrize(
    "attack",
    ["duplicate", "missing", "misordered", "unknown", "project-root"],
)
def test_command_parser_rejects_noncanonical_argv(attack: str) -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    forged = copy.deepcopy(run.observation)
    argv = forged["command"]["argv"]
    if attack == "duplicate":
        index = argv.index("--root")
        argv[index:index] = ["--path", forged["scope"]["paths"][0]]
    elif attack == "missing":
        index = argv.index("--language")
        del argv[index : index + 2]
    elif attack == "misordered":
        path_index, root_index = argv.index("--path"), argv.index("--root")
        path_pair, root_pair = argv[path_index : path_index + 2], argv[root_index : root_index + 2]
        argv[path_index : root_index + 2] = [*root_pair, *path_pair]
    elif attack == "unknown":
        index = argv.index("--case-sensitive")
        argv[index:index] = ["--mystery", "value"]
    else:
        argv[argv.index("--project-root") + 1] = "/different/project-root"
    with pytest.raises(SchemaValidationError):
        validate_provider_observation(forged)


def test_failed_artifact_cannot_be_relabelled_complete_by_three_field_edit() -> None:
    failed = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="typescript",
        observation_index=0,
    )
    assert failed.observation["raw"]["stderr_bytes"] > 0
    forged = copy.deepcopy(failed.observation)
    forged["status"] = "completed"
    forged["failure"] = None
    forged["exit"] = {"code": 0, "classification": "clean"}
    with pytest.raises(SchemaValidationError, match="completion"):
        _build(forged, [])


def test_completion_cannot_be_removed_or_fabricated() -> None:
    completed = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    missing = copy.deepcopy(completed.observation)
    missing["completion"] = None
    with pytest.raises(SchemaValidationError, match="completion"):
        validate_provider_observation(missing)

    failed = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="typescript",
        observation_index=0,
    )
    fabricated = copy.deepcopy(failed.observation)
    fabricated["completion"] = copy.deepcopy(completed.observation["completion"])
    with pytest.raises(SchemaValidationError, match="must not carry completion"):
        validate_provider_observation(fabricated)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "not-completion"),
        ("provider", "cx"),
        ("language", "typescript"),
        ("stdout_sha256", "0" * 64),
        ("stdout_bytes", 1),
        ("stderr_sha256", "0" * 64),
        ("stderr_bytes", 1),
        ("command_scope_sha256", "0" * 64),
    ],
)
def test_completion_attestation_rejects_tampering(field: str, value: object) -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    forged = copy.deepcopy(run.observation)
    forged["completion"][field] = value
    with pytest.raises(SchemaValidationError):
        validate_provider_observation(forged)


@pytest.mark.parametrize("field", ["stdout_sha256", "stdout_bytes"])
def test_completion_attestation_binds_raw_stdout(field: str) -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    forged = copy.deepcopy(run.observation)
    forged["raw"][field] = "0" * 64 if field.endswith("sha256") else 1
    with pytest.raises(SchemaValidationError, match="completion"):
        validate_provider_observation(forged)


def test_completion_requires_empty_stderr_even_if_attestation_agrees() -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    forged = copy.deepcopy(run.observation)
    for envelope in (forged["raw"], forged["completion"]):
        envelope["stderr_sha256"] = "0" * 64
        envelope["stderr_bytes"] = 1
    with pytest.raises(SchemaValidationError, match="empty stderr"):
        validate_provider_observation(forged)


def test_manifest_reconciles_completion_count_with_finding_provenance() -> None:
    run = run_omnibus_provider(
        REPO_ROOT,
        [FIXTURES / "python"],
        language="python",
        observation_index=0,
    )
    forged = copy.deepcopy(run.observation)
    forged["completion"]["finding_count"] = 2
    assert validate_provider_observation(forged) == forged
    with pytest.raises(SchemaValidationError, match="completion.finding_count"):
        _build(forged, run.findings)
