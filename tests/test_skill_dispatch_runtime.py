from __future__ import annotations

import copy
import fcntl
import hashlib
import os
import stat
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import pytest

import _lib.skill_dispatch_runtime as runtime_module
from _lib.distribution_contracts import canonical_json_bytes, canonical_sha256
from _lib.skill_bundle import (
    INSTALLED_MANIFEST_PATH,
    BlobSource,
    VerifiedBundle,
    build_release_bundle,
    verify_release_bundle,
)
from _lib.skill_dispatch_runtime import (
    DispatchExecutionEvidence,
    DispatchLauncherIdentity,
    DispatchRuntime,
    DispatchRuntimeError,
    RepositoryDispatchLauncher,
    VerifiedExecutorCapability,
)


WORKFLOW_ID = "123e4567-e89b-42d3-a456-426614174000"
DISPATCH_ID = "123e4567-e89b-42d3-a456-426614174001"
SECOND_DISPATCH_ID = "123e4567-e89b-42d3-a456-426614174002"
PROFILE_HASH = "a" * 64
BODY = "Do only the selected work."
BODY_HASH = hashlib.sha256(BODY.encode()).hexdigest()
SURFACE_CONTRACT = {
    "schema_version": 1,
    "contract_version": 1,
    "surfaces": [
        {
            "surface_id": "codex",
            "runtime_version": {"lower": "0.144.1", "upper": "0.144.1"},
            "projection_format": "codex-projection-v1",
            "public_identity": {
                "which_shape": "$engineering-skills:which-shape",
                "which_skill": "$engineering-skills:which-skill",
                "alias_template": "$engineering-skills:{public-name}",
            },
            "generated_identity": {
                "which_shape": "skills/which-shape/SKILL.md",
                "which_skill": "skills/which-skill/SKILL.md",
                "alias_template": "skills/{public-name}/SKILL.md",
            },
            "discovery": {
                "command": ["codex", "debug", "prompt-input"],
                "parser_id": "codex-debug-prompt-input-v1",
                "offline_non_model": True,
            },
            "activation": {
                "operation": "codex-projection-v1",
                "temporary_activation": "unsupported",
                "terminal_wrapper": None,
                "startup_cleanup": None,
            },
            "worker": {
                # Fixture-only adapter contract; this is not native Codex evidence.
                "fresh_worker": "verified",
                "launcher": "repository-fixture-wrapper-v1",
                "version_range": {"lower": "0.144.1", "upper": "0.144.1"},
                "selected_procedure_injection": "dispatch-pack-stdin-v1",
                "cancellation": "process-group-cancel-v1",
                "result": "dispatch-result-stdout-v1",
                "zero_conversation_turns_proof": "fresh-process-v1",
                "budget_enforcement": "trusted-wrapper-counters-v1",
            },
        }
    ],
}
for _surface_id, _version in (
    ("claude-code", "2.1.211"),
    ("augment", "imported-rules-v1"),
    ("cursor", "project-rules-v1"),
    ("gemini", "0.45.0"),
):
    _surface = copy.deepcopy(SURFACE_CONTRACT["surfaces"][0])
    _surface["surface_id"] = _surface_id
    _surface["runtime_version"] = {"lower": _version, "upper": _version}
    if _surface_id == "claude-code":
        _surface["public_identity"] = {
            "which_shape": "/which-shape",
            "which_skill": "/which-skill",
            "alias_template": "/{public-name}",
        }
        _surface["generated_identity"] = {
            "which_shape": ".claude/skills/which-shape/SKILL.md",
            "which_skill": ".claude/skills/which-skill/SKILL.md",
            "alias_template": ".claude/skills/{public-name}/SKILL.md",
        }
    elif _surface_id == "augment":
        _surface["public_identity"] = {
            "which_shape": "use skill which-shape",
            "which_skill": "use skill which-skill",
            "alias_template": "use skill {public-name}",
        }
        _surface["generated_identity"] = {
            "which_shape": ".augment/rules/imported/which-shape/SKILL.md",
            "which_skill": ".augment/rules/imported/which-skill/SKILL.md",
            "alias_template": ".augment/rules/imported/{public-name}/SKILL.md",
        }
    elif _surface_id == "cursor":
        _surface["public_identity"] = {
            "which_shape": "use skill which-shape",
            "which_skill": "use skill which-skill",
            "alias_template": "use skill {public-name}",
        }
        _surface["generated_identity"] = {
            "which_shape": ".cursor/rules/which-shape/SKILL.mdc",
            "which_skill": ".cursor/rules/which-skill/SKILL.mdc",
            "alias_template": ".cursor/rules/{public-name}/SKILL.mdc",
        }
    else:
        _surface["public_identity"] = {
            "which_shape": "use skill which-shape",
            "which_skill": "use skill which-skill",
            "alias_template": "use skill {public-name}",
        }
        _surface["generated_identity"] = {
            "which_shape": ".gemini/skills/which-shape/SKILL.md",
            "which_skill": ".gemini/skills/which-skill/SKILL.md",
            "alias_template": ".gemini/skills/{public-name}/SKILL.md",
        }
    _surface["worker"] = {
        "fresh_worker": "unsupported",
        "launcher": None,
        "version_range": None,
        "selected_procedure_injection": None,
        "cancellation": None,
        "result": None,
        "zero_conversation_turns_proof": None,
        "budget_enforcement": None,
    }
    SURFACE_CONTRACT["surfaces"].append(_surface)
SURFACE_CONTRACT_SHA256 = canonical_sha256(SURFACE_CONTRACT)


@pytest.fixture(autouse=True)
def _closed_fixture_launcher_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime_module, "_REPOSITORY_LAUNCHER_TYPES", {})


class Clock:
    def __init__(self, value: int = 10_000_000_000) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value

    def advance_ms(self, milliseconds: int) -> None:
        self.value += milliseconds * 1_000_000


def _verified_bundle(
    root: Path,
    *,
    surface_contract: dict[str, Any] = SURFACE_CONTRACT,
    name: str = "bundle",
) -> VerifiedBundle:
    source = root / f"{name}-source"
    bundle = root / name
    if not bundle.exists():
        source.mkdir(parents=True)
        files = {
            "catalog.json": b'{"schema_version":1,"skills":[]}',
            "registry.json": b'{"contract_version":1,"schema_version":1}',
            "profile.json": b'{"schema_version":1}',
            "which-shape.md": b"---\nname: which-shape\n---\nShape router.\n",
            "which-skill.md": b"---\nname: which-skill\n---\nSkill router.\n",
            "runtime.py": b"def verify_locator():\n    return True\n",
            "installer.py": b"raise SystemExit('fixture installer')\n",
        }
        for path, content in files.items():
            source.joinpath(path).write_bytes(content)
        source.joinpath("surface-contract.json").write_bytes(canonical_json_bytes(surface_contract))
        recipe = {
            "schema_version": 1,
            "surface_id": "codex",
            "manifest_locator": INSTALLED_MANIFEST_PATH,
            "bootstrap_metadata_path": ".engineering/bootstrap/codex/bootstrap-v1.json",
            "routers": [
                {
                    "canonical_name": "which-shape",
                    "blob_id": "which-shape",
                    "path": "skills/which-shape/SKILL.md",
                },
                {
                    "canonical_name": "which-skill",
                    "blob_id": "which-skill",
                    "path": "skills/which-skill/SKILL.md",
                },
            ],
            "runtime_files": [
                {
                    "blob_id": "router-runtime",
                    "path": ".engineering/bootstrap/codex/runtime.py",
                }
            ],
        }
        source.joinpath("recipe.json").write_bytes(canonical_json_bytes(recipe))
        blobs = [
            BlobSource("catalog", "catalog", "catalog.json", "application/json"),
            BlobSource("registry", "registry", "registry.json", "application/json"),
            BlobSource("profile", "required-profile", "profile.json", "application/json"),
            BlobSource("router", "which-shape", "which-shape.md", "text/markdown"),
            BlobSource("router", "which-skill", "which-skill.md", "text/markdown"),
            BlobSource("asset", "router-runtime", "runtime.py", "text/x-python"),
            BlobSource("projection-recipe", "codex-bootstrap", "recipe.json", "application/json"),
        ]
        digest = build_release_bundle(
            source,
            bundle,
            bundle_version="fixture-1",
            blobs=blobs,
            installer="installer.py",
            surface_activation_contract="surface-contract.json",
        )
    else:
        digest = hashlib.sha256(bundle.joinpath("release-root-v1.json").read_bytes()).hexdigest()
    return verify_release_bundle(bundle, digest)


def _runtime(tmp_path: Path, clock: Clock | None = None) -> DispatchRuntime:
    project = tmp_path / "project"
    project.mkdir(parents=True)
    return DispatchRuntime(
        project,
        surface_id="codex",
        verified_bundle=_verified_bundle(tmp_path),
        clock_ns=clock or Clock(),
    )


class FixtureDispatchLauncher(RepositoryDispatchLauncher):
    def __init__(
        self,
        identity: DispatchLauncherIdentity,
        execute: Callable[[dict[str, object], Path], dict[str, object]],
        accounting: tuple[int, int, int] | None = None,
    ) -> None:
        self._identity = identity
        self._execute = execute
        self._accounting = accounting

    @property
    def identity(self) -> DispatchLauncherIdentity:
        return self._identity

    def launch(self, pack: dict[str, object], invocation_root: Path) -> DispatchExecutionEvidence:
        result = self._execute(pack, invocation_root)
        input_tokens, output_tokens, elapsed_milliseconds = self._accounting or (
            result["input_tokens"],
            result["output_tokens"],
            result["elapsed_milliseconds"],
        )
        return DispatchExecutionEvidence(
            result=result,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_milliseconds=elapsed_milliseconds,
            capability_declaration_sha256=self.identity.capability_declaration_sha256,
            launcher_configuration_sha256=self.identity.configuration_sha256,
            deadline_enforced=True,
            cancellation_enforced=True,
            result_handoff_enforced=True,
        )


def _launcher(
    runtime: DispatchRuntime,
    execute: Callable[[dict[str, object], Path], dict[str, object]],
    *,
    lane: str = "fresh-worker",
    inherited_conversation_turns: int | None = None,
    accounting: tuple[int, int, int] | None = None,
) -> FixtureDispatchLauncher:
    inherited = (
        inherited_conversation_turns
        if inherited_conversation_turns is not None
        else (0 if lane == "fresh-worker" else 7)
    )
    capability = VerifiedExecutorCapability._from_verified_surface_contract(
        surface_contract=runtime.surface_contract,
        surface_contract_sha256=runtime.surface_contract_sha256,
        surface_id=runtime.surface_id,
        lane=lane,
        inherited_conversation_turns=inherited,
    )
    surface = next(
        row
        for row in runtime.surface_contract["surfaces"]
        if row["surface_id"] == runtime.surface_id
    )
    launcher_id = (
        surface["worker"]["launcher"]
        if lane == "fresh-worker"
        else runtime_module._PARENT_LAUNCHER_ID
    )
    configuration_sha256 = canonical_sha256(
        {
            "schema_version": 1,
            "release_root_sha256": runtime.release_root_sha256,
            "bundle_index_sha256": runtime.bundle_index_sha256,
            "surface_contract_sha256": runtime.surface_contract_sha256,
            "surface_id": runtime.surface_id,
            "lane": lane,
            "launcher_id": launcher_id,
            "worker_declaration_sha256": capability.worker_declaration_sha256,
        }
    )
    identity = DispatchLauncherIdentity(
        surface_id=runtime.surface_id,
        lane=lane,
        launcher_id=launcher_id,
        configuration_sha256=configuration_sha256,
        capability_declaration_sha256=capability.declaration_sha256,
        inherited_conversation_turns=inherited,
    )
    runtime_module._REPOSITORY_LAUNCHER_TYPES[
        (runtime.surface_id, lane, launcher_id, configuration_sha256)
    ] = FixtureDispatchLauncher
    return FixtureDispatchLauncher(identity, execute, accounting)


def _capability(lane: str = "fresh-worker") -> VerifiedExecutorCapability:
    return VerifiedExecutorCapability._from_verified_surface_contract(
        surface_contract=SURFACE_CONTRACT,
        surface_contract_sha256=SURFACE_CONTRACT_SHA256,
        surface_id="codex",
        lane=lane,
        inherited_conversation_turns=0 if lane == "fresh-worker" else 7,
    )


def _execute(
    runtime: DispatchRuntime,
    pack: dict[str, Any],
    *,
    capability: VerifiedExecutorCapability,
    executor: Callable[[dict[str, object], Path], dict[str, object]],
    prior_result: dict[str, Any] | None = None,
    artifact_handoff: Callable[[dict[str, Any], bytes], None] | None = None,
) -> dict[str, Any]:
    launcher = _launcher(
        runtime,
        executor,
        lane=pack["execution_lane"],
        inherited_conversation_turns=capability.inherited_conversation_turns,
    )
    return runtime.execute(
        pack,
        launcher=launcher,
        prior_result=prior_result,
        artifact_handoff=artifact_handoff,
    )


def _runtime_arguments(runtime: DispatchRuntime) -> dict[str, object]:
    return {
        "surface_id": "codex",
        "verified_bundle": runtime.verified_bundle,
    }


def _pack(
    runtime: DispatchRuntime,
    *,
    dispatch_id: str = DISPATCH_ID,
    ordinal: int = 1,
    attempt: int = 1,
    lane: str = "fresh-worker",
    prior_result: dict[str, object] | None = None,
) -> dict[str, object]:
    fallback = None
    reason = "initial_selection" if ordinal == 1 else "confirmed_sequence_step"
    prior_dispatch_id = None
    prior_result_sha256 = None
    continuation_plan_sha256 = None
    if attempt == 2:
        assert prior_result is not None
        prior_dispatch_id = prior_result["dispatch_id"]
        prior_result_sha256 = canonical_sha256(prior_result)
        continuation_plan_sha256 = "b" * 64
        if lane == "fresh-worker":
            reason = "user_confirmed_worker_retry"
        else:
            reason = "user_confirmed_parent_continuation"
            fallback = "user_confirmed_after_worker_failure"
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "dispatch_id": dispatch_id,
        "prior_dispatch_id": prior_dispatch_id,
        "invocation_id": None,
        "clarification_id": None,
        "workflow_pack_ordinal": ordinal,
        "attempt_ordinal": attempt,
        "execution_lane": lane,
        "continuation_reason": reason,
        "fallback_reason": fallback,
        "selection": {
            "canonical_name": "plan-feature",
            "public_name": "plan-feature",
            "selection_basis": "unique_winner",
            "source_sha256": BODY_HASH,
            "rendered_sha256": BODY_HASH,
        },
        "roots": [
            {
                "project_root": runtime.project_root.as_posix(),
                "profile_sha256": PROFILE_HASH,
                "bindings": [],
            }
        ],
        "task": {
            "arguments": "plan the feature",
            "sha256": canonical_sha256("plan the feature"),
        },
        "procedure": {
            "body": BODY,
            "raw_sha256": BODY_HASH,
            "rendered_sha256": BODY_HASH,
        },
        "dependencies": [],
        "prior_result_sha256": prior_result_sha256,
        "continuation_plan_sha256": continuation_plan_sha256,
        "side_effect_ledger_sha256": None,
        "budget": runtime.remaining_budget(),
    }


def _result(
    pack: dict[str, object],
    *,
    status: str = "success",
    input_tokens: int = 10,
    output_tokens: int = 5,
    elapsed_milliseconds: int = 10,
) -> dict[str, object]:
    failed = status == "failed"
    return {
        "schema_version": 1,
        **{
            field: pack[field]
            for field in (
                "workflow_id",
                "dispatch_id",
                "prior_dispatch_id",
                "workflow_pack_ordinal",
                "attempt_ordinal",
                "execution_lane",
                "continuation_reason",
                "fallback_reason",
            )
        },
        "status": status,
        "summary": "completed" if not failed else "worker failed",
        "error_code": "worker_failed" if failed else None,
        "error_message": "worker failed" if failed else None,
        "failure_kind": "worker_failed" if failed else None,
        "side_effect_disposition": "rolled_back" if failed else "none",
        "side_effect_ledger_sha256": None,
        "elapsed_milliseconds": elapsed_milliseconds,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "artifacts": [],
    }


def test_runtime_enforces_protected_journal_selected_capability_and_raw_cleanup(
    tmp_path: Path,
) -> None:
    # spec:portable-skill-layer-distribution::IM-14
    clock = Clock()
    project = tmp_path / "project"
    project.mkdir(mode=0o755)
    before_mode = stat.S_IMODE(project.stat().st_mode)
    runtime = DispatchRuntime(
        project,
        surface_id="codex",
        verified_bundle=_verified_bundle(tmp_path),
        clock_ns=clock,
    )
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)

    def execute(received: dict[str, object], invocation_root: Path) -> dict[str, object]:
        assert received == pack
        assert stat.S_IMODE(invocation_root.stat().st_mode) == 0o700
        assert stat.S_IMODE((invocation_root / "dispatch-pack-v1.json").stat().st_mode) == 0o600
        clock.advance_ms(10)
        return _result(pack)

    result = _execute(runtime, pack, capability=_capability(), executor=execute)

    assert result["status"] == "success"
    assert runtime.remaining_budget()["remaining_total_tokens"] == 32753
    assert runtime.remaining_budget()["remaining_output_tokens"] == 8187
    assert not list(runtime.raw_root.glob("invocation-*"))
    assert stat.S_IMODE(runtime.state_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(runtime.journal_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(project.stat().st_mode) == before_mode
    journal = runtime.journal_snapshot()
    assert "plan the feature" not in str(journal)
    assert BODY not in str(journal)
    assert journal["active_workflow"]["consumed_total_tokens"] == 15
    assert journal["cleanup_state"] == "clean"
    assert journal["last_dispatch"]["cleanup_state"] == "clean"


@pytest.mark.parametrize(
    "change",
    (
        {"surface_id": "cursor"},
        {"lane": "selected-only-parent"},
        {"launcher_id": "invented-launcher-v1"},
        {"configuration_sha256": "0" * 64},
        {"capability_declaration_sha256": "0" * 64},
        {"inherited_conversation_turns": 1},
    ),
)
def test_unverified_or_mismatched_launcher_fails_before_raw_execution(
    tmp_path: Path, change: dict[str, object]
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    called = False

    def execute(_pack: dict[str, object], _root: Path) -> dict[str, object]:
        nonlocal called
        called = True
        return _result(pack)

    launcher = _launcher(runtime, execute)
    launcher._identity = replace(launcher.identity, **change)
    with pytest.raises(DispatchRuntimeError):
        runtime.execute(pack, launcher=launcher)
    assert called is False
    assert not list(runtime.raw_root.glob("invocation-*"))


def test_arbitrary_lambda_with_fake_nonzero_accounting_is_never_executed(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    called = False

    def execute(p: dict[str, object], _root: Path) -> dict[str, object]:
        nonlocal called
        called = True
        return _result(p)

    with pytest.raises(DispatchRuntimeError, match="repository-owned launcher"):
        runtime.execute(pack, launcher=execute)  # type: ignore[arg-type]
    assert called is False


def test_registered_wrapper_owns_accounting_and_replaces_worker_claims(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    launcher = _launcher(
        runtime,
        lambda p, _root: _result(
            p,
            input_tokens=1_000,
            output_tokens=500,
            elapsed_milliseconds=900,
        ),
        accounting=(3, 2, 7),
    )

    result = runtime.execute(pack, launcher=launcher)

    assert result["input_tokens"] == 3
    assert result["output_tokens"] == 2
    assert result["elapsed_milliseconds"] == 7
    assert runtime.remaining_budget()["remaining_total_tokens"] == 32_763


def test_verified_fixture_declaration_without_registered_adapter_is_unsupported(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    called = False

    def execute(p: dict[str, object], _root: Path) -> dict[str, object]:
        nonlocal called
        called = True
        return _result(p)

    launcher = _launcher(runtime, execute)
    runtime_module._REPOSITORY_LAUNCHER_TYPES.clear()
    with pytest.raises(DispatchRuntimeError, match="absent from.*registry"):
        runtime.execute(pack, launcher=launcher)
    assert called is False


def test_surface_declared_unsupported_fails_closed_before_launcher(
    tmp_path: Path,
) -> None:
    unsupported = copy.deepcopy(SURFACE_CONTRACT)
    codex = next(row for row in unsupported["surfaces"] if row["surface_id"] == "codex")
    codex["worker"] = {
        "fresh_worker": "unsupported",
        "launcher": None,
        "version_range": None,
        "selected_procedure_injection": None,
        "cancellation": None,
        "result": None,
        "zero_conversation_turns_proof": None,
        "budget_enforcement": None,
    }
    project = tmp_path / "unsupported-project"
    project.mkdir()
    runtime = DispatchRuntime(
        project,
        surface_id="codex",
        verified_bundle=_verified_bundle(
            tmp_path,
            surface_contract=unsupported,
            name="unsupported-bundle",
        ),
    )
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    called = False

    def execute(p: dict[str, object], _root: Path) -> dict[str, object]:
        nonlocal called
        called = True
        return _result(p)

    identity = DispatchLauncherIdentity(
        surface_id="codex",
        lane="fresh-worker",
        launcher_id="invented-launcher-v1",
        configuration_sha256="0" * 64,
        capability_declaration_sha256="0" * 64,
        inherited_conversation_turns=0,
    )
    runtime_module._REPOSITORY_LAUNCHER_TYPES[("fixture", "fixture", "fixture", "0" * 64)] = (
        FixtureDispatchLauncher
    )
    with pytest.raises(DispatchRuntimeError, match="no verified fresh-worker"):
        runtime.execute(pack, launcher=FixtureDispatchLauncher(identity, execute))
    assert called is False


def test_wrong_project_root_fails_before_trusted_launcher(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    called = False

    def execute(p: dict[str, object], _root: Path) -> dict[str, object]:
        nonlocal called
        called = True
        return _result(p)

    hostile_root = {
        **pack,
        "roots": [{**pack["roots"][0], "project_root": "/other"}],
    }
    with pytest.raises(DispatchRuntimeError, match="locked project root"):
        runtime.execute(hostile_root, launcher=_launcher(runtime, execute))
    assert called is False


def test_forged_contract_and_recomputed_digest_cannot_mint_runtime_trust(
    tmp_path: Path,
) -> None:
    bundle = _verified_bundle(tmp_path)
    alternate = copy.deepcopy(SURFACE_CONTRACT)
    codex = next(row for row in alternate["surfaces"] if row["surface_id"] == "codex")
    codex["worker"]["launcher"] = "invented-launcher-v1"
    alternate_digest = canonical_sha256(alternate)
    project = tmp_path / "other-project"
    project.mkdir()
    with pytest.raises(TypeError):
        DispatchRuntime(  # type: ignore[call-arg]
            project,
            surface_id="codex",
            surface_contract=alternate,
            expected_surface_contract_sha256=alternate_digest,
        )

    bundle.surface_contract.clear()
    bundle.surface_contract.update(alternate)
    runtime = DispatchRuntime(
        project,
        surface_id="codex",
        verified_bundle=bundle,
    )
    assert canonical_sha256(runtime.surface_contract) == SURFACE_CONTRACT_SHA256


def test_project_lock_and_duplicate_dispatch_fail_closed(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    _execute(runtime, pack, capability=_capability(), executor=lambda p, _r: _result(p))

    with pytest.raises(DispatchRuntimeError, match="dispatch id"):
        _execute(runtime, pack, capability=_capability(), executor=lambda p, _r: _result(p))

    next_pack = _pack(runtime, dispatch_id=SECOND_DISPATCH_ID, ordinal=2)
    with runtime.lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(DispatchRuntimeError, match="active execution lane"):
            _execute(
                runtime,
                next_pack,
                capability=_capability(),
                executor=lambda p, _r: _result(p),
            )


def test_separate_runtime_instances_reload_journal_under_shared_lock(
    tmp_path: Path,
) -> None:
    first = _runtime(tmp_path)
    second = DispatchRuntime(first.project_root, **_runtime_arguments(first), clock_ns=Clock())
    first.start_workflow(WORKFLOW_ID)
    pack = _pack(first)

    _execute(second, pack, capability=_capability(), executor=lambda p, _r: _result(p))

    assert first.remaining_budget()["remaining_total_tokens"] == 32753
    with pytest.raises(DispatchRuntimeError, match="dispatch id"):
        _execute(first, pack, capability=_capability(), executor=lambda p, _r: _result(p))


def test_state_root_is_canonical_and_cannot_be_selected_by_the_caller(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    assert runtime.state_root == (runtime.project_root / ".engineering/local/dispatch-runtime-v1")
    with pytest.raises(TypeError):
        DispatchRuntime(  # type: ignore[misc]
            runtime.project_root,
            tmp_path / "alternate-state",
            **_runtime_arguments(runtime),
        )


def test_multi_root_pack_locks_every_root_and_has_one_canonical_owner(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path / "primary")
    secondary = tmp_path / "secondary"
    secondary.mkdir()
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    pack["roots"].append(
        {
            "project_root": secondary.resolve().as_posix(),
            "profile_sha256": "d" * 64,
            "bindings": [],
        }
    )
    state = secondary / ".engineering/local/dispatch-runtime-v1"
    state.mkdir(parents=True, mode=0o700)
    lock_path = state / "dispatch.lock"
    lock_path.touch(mode=0o600)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(DispatchRuntimeError, match="project lock"):
            _execute(
                runtime,
                pack,
                capability=_capability(),
                executor=lambda p, _r: _result(p),
            )

    secondary_runtime = DispatchRuntime(secondary, **_runtime_arguments(runtime), clock_ns=Clock())
    secondary_runtime.start_workflow(WORKFLOW_ID)
    with pytest.raises(DispatchRuntimeError, match="canonical root"):
        _execute(
            secondary_runtime,
            pack,
            capability=_capability(),
            executor=lambda p, _r: _result(p),
        )


def test_cumulative_budget_deadline_serial_order_and_confirmed_retry(tmp_path: Path) -> None:
    clock = Clock()
    runtime = _runtime(tmp_path, clock)
    runtime.start_workflow(WORKFLOW_ID)
    first = _pack(runtime)
    failed = _execute(
        runtime,
        first,
        capability=_capability(),
        executor=lambda p, _r: _result(
            p, status="failed", input_tokens=100, output_tokens=20, elapsed_milliseconds=40
        ),
    )

    skipped_continuation = _pack(
        runtime,
        dispatch_id="123e4567-e89b-42d3-a456-426614174009",
        ordinal=2,
    )
    with pytest.raises(DispatchRuntimeError, match="attempt-two continuation"):
        _execute(
            runtime,
            skipped_continuation,
            capability=_capability(),
            executor=lambda p, _r: _result(p),
        )

    retry = _pack(
        runtime,
        dispatch_id=SECOND_DISPATCH_ID,
        attempt=2,
        prior_result=failed,
    )
    _execute(
        runtime,
        retry,
        capability=_capability(),
        executor=lambda p, _r: _result(p, input_tokens=50, output_tokens=10),
        prior_result=failed,
    )
    assert runtime.remaining_budget()["remaining_total_tokens"] == 32588
    assert runtime.remaining_budget()["remaining_output_tokens"] == 8162

    third = _pack(runtime, dispatch_id="123e4567-e89b-42d3-a456-426614174003", ordinal=2)
    _execute(runtime, third, capability=_capability(), executor=lambda p, _r: _result(p))
    out_of_order = _pack(
        runtime,
        dispatch_id="123e4567-e89b-42d3-a456-426614174004",
        ordinal=4,
    )
    with pytest.raises(DispatchRuntimeError, match="pack ordinal"):
        _execute(
            runtime,
            out_of_order,
            capability=_capability(),
            executor=lambda p, _r: _result(p),
        )

    clock.advance_ms(1_200_001)
    with pytest.raises(DispatchRuntimeError, match="deadline"):
        runtime.remaining_budget()


def test_retry_binds_exact_recorded_terminal_result_and_unknown_stops(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path / "forged")
    runtime.start_workflow(WORKFLOW_ID)
    first = _pack(runtime)
    success = _execute(runtime, first, capability=_capability(), executor=lambda p, _r: _result(p))
    forged = {
        **success,
        "status": "failed",
        "summary": "forged",
        "error_code": "worker_failed",
        "error_message": "forged",
        "failure_kind": "worker_failed",
        "side_effect_disposition": "rolled_back",
    }
    retry = _pack(
        runtime,
        dispatch_id=SECOND_DISPATCH_ID,
        attempt=2,
        prior_result=forged,
    )
    with pytest.raises(DispatchRuntimeError, match="exact retryable recorded"):
        _execute(
            runtime,
            retry,
            capability=_capability(),
            executor=lambda p, _r: _result(p),
            prior_result=forged,
        )

    unknown = _runtime(tmp_path / "unknown")
    unknown.start_workflow(WORKFLOW_ID)
    unknown_pack = _pack(unknown)
    terminal = _result(unknown_pack, status="failed")
    terminal["side_effect_disposition"] = "unknown"
    result = _execute(
        unknown,
        unknown_pack,
        capability=_capability(),
        executor=lambda _p, _r: terminal,
    )
    assert result["side_effect_disposition"] == "unknown"
    with pytest.raises(DispatchRuntimeError, match="blocked"):
        unknown.remaining_budget()


def test_invalid_or_over_budget_result_becomes_minimal_failed_result_and_cleans(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)

    def execute(p: dict[str, object], _root: Path) -> dict[str, object]:
        result = _result(p)
        result["output_tokens"] = 9000
        return result

    result = _execute(runtime, pack, capability=_capability(), executor=execute)
    assert result["status"] == "failed"
    assert result["failure_kind"] == "worker_failed"
    assert result["side_effect_disposition"] == "unknown"
    assert result["input_tokens"] + result["output_tokens"] == 32768
    assert not list(runtime.raw_root.glob("invocation-*"))
    assert runtime.journal_snapshot()["blocked"] is True
    assert runtime.journal_snapshot()["last_dispatch"]["side_effect_disposition"] == "unknown"


def test_zero_usage_self_attestation_becomes_untrusted_failed_result(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    result = _execute(
        runtime,
        pack,
        capability=_capability(),
        executor=lambda p, _r: _result(p, input_tokens=0, output_tokens=0),
    )
    assert result["status"] == "failed"
    assert result["side_effect_disposition"] == "unknown"
    assert result["input_tokens"] + result["output_tokens"] == 32768


def test_executor_exception_or_actual_deadline_overrun_blocks_implicit_retry(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path / "exception")
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)

    def explode(_pack: dict[str, object], _root: Path) -> dict[str, object]:
        raise RuntimeError("secret executor details")

    result = _execute(runtime, pack, capability=_capability(), executor=explode)
    assert result["status"] == "failed"
    assert result["side_effect_disposition"] == "unknown"
    assert runtime.journal_snapshot()["blocked"] is True
    assert "secret executor details" not in str(runtime.journal_snapshot())

    clock = Clock()
    overrun = _runtime(tmp_path / "deadline", clock)
    overrun.start_workflow(WORKFLOW_ID)
    deadline_pack = _pack(overrun)

    def exceed_deadline(p: dict[str, object], _root: Path) -> dict[str, object]:
        clock.advance_ms(1_200_001)
        return _result(p)

    result = _execute(overrun, deadline_pack, capability=_capability(), executor=exceed_deadline)
    assert result["status"] == "failed"
    assert overrun.journal_snapshot()["blocked"] is True


def test_artifact_handoff_verifies_regular_contained_single_link_bytes(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    payload = b"verified artifact"
    digest = hashlib.sha256(payload).hexdigest()
    handed: list[bytes] = []

    def execute(p: dict[str, object], root: Path) -> dict[str, object]:
        artifact = root / "artifacts" / digest / "report.txt"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(payload)
        result = _result(p)
        result["artifacts"] = [
            {
                "uri": f"artifact://sha256/{digest}",
                "name": "report.txt",
                "media_type": "text/plain",
                "size": len(payload),
                "sha256": digest,
            }
        ]
        return result

    _execute(
        runtime,
        pack,
        capability=_capability(),
        executor=execute,
        artifact_handoff=lambda _row, content: handed.append(content),
    )
    assert handed == [payload]
    assert not list(runtime.raw_root.glob("invocation-*"))

    runtime.finish_workflow()
    runtime.start_workflow("123e4567-e89b-42d3-a456-426614174005")
    hostile_pack = _pack(runtime)
    hostile_pack["workflow_id"] = "123e4567-e89b-42d3-a456-426614174005"

    def hostile(p: dict[str, object], root: Path) -> dict[str, object]:
        artifact = root / "artifacts" / digest / "report.txt"
        artifact.parent.mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.write_bytes(payload)
        artifact.symlink_to(outside)
        result = _result(p)
        result["artifacts"] = [
            {
                "uri": f"artifact://sha256/{digest}",
                "name": "report.txt",
                "media_type": "text/plain",
                "size": len(payload),
                "sha256": digest,
            }
        ]
        return result

    failed = _execute(
        runtime,
        hostile_pack,
        capability=_capability(),
        executor=hostile,
        artifact_handoff=lambda _row, _content: None,
    )
    assert failed["status"] == "failed"
    assert failed["side_effect_disposition"] == "unknown"


def test_artifact_hard_link_and_journal_hard_link_fail_closed(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path / "artifact")
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    payload = b"hard-linked artifact"
    digest = hashlib.sha256(payload).hexdigest()

    def hard_linked(p: dict[str, object], root: Path) -> dict[str, object]:
        outside = tmp_path / "artifact-source"
        outside.write_bytes(payload)
        artifact = root / "artifacts" / digest / "report.txt"
        artifact.parent.mkdir(parents=True)
        os.link(outside, artifact)
        result = _result(p)
        result["artifacts"] = [
            {
                "uri": f"artifact://sha256/{digest}",
                "name": "report.txt",
                "media_type": "text/plain",
                "size": len(payload),
                "sha256": digest,
            }
        ]
        return result

    failed = _execute(
        runtime,
        pack,
        capability=_capability(),
        executor=hard_linked,
        artifact_handoff=lambda _row, _content: None,
    )
    assert failed["status"] == "failed"
    assert failed["side_effect_disposition"] == "unknown"

    journal_runtime = _runtime(tmp_path / "journal")
    journal_alias = tmp_path / "journal-alias"
    os.link(journal_runtime.journal_path, journal_alias)
    with pytest.raises(DispatchRuntimeError, match="mode-0600 regular file"):
        DispatchRuntime(
            journal_runtime.project_root,
            **_runtime_arguments(journal_runtime),
            clock_ns=Clock(),
        )


def test_startup_recovery_removes_stale_raw_dirs_and_cleanup_failure_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    state = project / ".engineering/local/dispatch-runtime-v1"
    raw = state / "raw"
    stale = raw / "invocation-stale"
    stale.mkdir(parents=True)
    (stale / "secret").write_text("do not retain", encoding="utf-8")

    runtime = DispatchRuntime(
        project,
        surface_id="codex",
        verified_bundle=_verified_bundle(tmp_path),
        clock_ns=Clock(),
    )
    assert not stale.exists()

    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    original = runtime._remove_invocation

    def fail_cleanup(_path: Path) -> None:
        raise OSError("cleanup denied")

    monkeypatch.setattr(runtime, "_remove_invocation", fail_cleanup)
    with pytest.raises(DispatchRuntimeError, match="cleanup"):
        _execute(runtime, pack, capability=_capability(), executor=lambda p, _r: _result(p))
    monkeypatch.setattr(runtime, "_remove_invocation", original)
    with pytest.raises(DispatchRuntimeError, match="blocked"):
        runtime.remaining_budget()


def test_startup_recovery_cleans_every_raw_entry_and_pending_journal(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    runtime._record_result(pack, _result(pack))
    assert runtime.journal_snapshot()["cleanup_state"] == "pending"
    (runtime.raw_root / "unexpected-secret").write_text("secret", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.write_text("preserve", encoding="utf-8")
    (runtime.raw_root / "hostile-link").symlink_to(outside)

    restarted = DispatchRuntime(
        runtime.project_root, **_runtime_arguments(runtime), clock_ns=Clock()
    )

    assert not list(restarted.raw_root.iterdir())
    assert outside.read_text(encoding="utf-8") == "preserve"
    journal = restarted.journal_snapshot()
    assert journal["cleanup_state"] == "startup-cleaned"
    assert journal["last_dispatch"]["cleanup_state"] == "startup-cleaned"


def test_parent_lane_uses_same_accounting_but_allows_inherited_context(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime, lane="selected-only-parent")
    pack["fallback_reason"] = "conversation_state_required"

    result = _execute(
        runtime,
        pack,
        capability=_capability("selected-only-parent"),
        executor=lambda p, _r: _result(p),
    )

    assert result["execution_lane"] == "selected-only-parent"
    assert runtime.remaining_budget()["remaining_total_tokens"] == 32753


def test_restart_preserves_cumulative_budget_and_rejects_monotonic_clock_reset(
    tmp_path: Path,
) -> None:
    clock = Clock()
    runtime = _runtime(tmp_path, clock)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    _execute(runtime, pack, capability=_capability(), executor=lambda p, _r: _result(p))

    restarted = DispatchRuntime(runtime.project_root, **_runtime_arguments(runtime), clock_ns=clock)
    assert restarted.start_workflow(WORKFLOW_ID)["remaining_total_tokens"] == 32753

    reset_clock = Clock(1)
    reset = DispatchRuntime(
        runtime.project_root, **_runtime_arguments(runtime), clock_ns=reset_clock
    )
    with pytest.raises(DispatchRuntimeError, match="blocked"):
        reset.remaining_budget()


def test_invalid_workflow_id_fails_before_journal_mutation(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    before = runtime.journal_snapshot()
    with pytest.raises(DispatchRuntimeError, match="UUIDv4"):
        runtime.start_workflow("not-a-uuid")
    assert runtime.journal_snapshot() == before
    restarted = DispatchRuntime(
        runtime.project_root, **_runtime_arguments(runtime), clock_ns=Clock()
    )
    assert restarted.journal_snapshot() == before
