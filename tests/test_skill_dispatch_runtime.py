from __future__ import annotations

import copy
import fcntl
import hashlib
import os
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from _lib.distribution_contracts import canonical_sha256
from _lib.skill_dispatch_runtime import (
    DispatchRuntime,
    DispatchRuntimeError,
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
                "fresh_worker": "verified",
                "launcher": "codex-fresh-worker-v1",
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


class Clock:
    def __init__(self, value: int = 10_000_000_000) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value

    def advance_ms(self, milliseconds: int) -> None:
        self.value += milliseconds * 1_000_000


def _runtime(tmp_path: Path, clock: Clock | None = None) -> DispatchRuntime:
    project = tmp_path / "project"
    project.mkdir(parents=True)
    return DispatchRuntime(
        project,
        surface_id="codex",
        surface_contract=SURFACE_CONTRACT,
        expected_surface_contract_sha256=SURFACE_CONTRACT_SHA256,
        clock_ns=clock or Clock(),
    )


def _capability(lane: str = "fresh-worker") -> VerifiedExecutorCapability:
    return VerifiedExecutorCapability.from_trusted_surface_contract(
        surface_contract=SURFACE_CONTRACT,
        expected_contract_sha256=SURFACE_CONTRACT_SHA256,
        surface_id="codex",
        lane=lane,
        inherited_conversation_turns=0 if lane == "fresh-worker" else 7,
    )


def _runtime_arguments() -> dict[str, object]:
    return {
        "surface_id": "codex",
        "surface_contract": SURFACE_CONTRACT,
        "expected_surface_contract_sha256": SURFACE_CONTRACT_SHA256,
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
    runtime = DispatchRuntime(project, **_runtime_arguments(), clock_ns=clock)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)

    def execute(received: dict[str, object], invocation_root: Path) -> dict[str, object]:
        assert received == pack
        assert stat.S_IMODE(invocation_root.stat().st_mode) == 0o700
        assert stat.S_IMODE((invocation_root / "dispatch-pack-v1.json").stat().st_mode) == 0o600
        clock.advance_ms(10)
        return _result(pack)

    result = runtime.execute(pack, capability=_capability(), executor=execute)

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
        {"selected_only": False},
        {"budget_accounting_enforced": False},
        {"permits_child_spawn": True},
        {"permits_redispatch": True},
        {"permits_activation": True},
        {"permits_detached_work": True},
        {"inherited_conversation_turns": 1},
    ),
)
def test_unverified_or_broad_worker_capability_fails_before_raw_execution(
    tmp_path: Path, change: dict[str, object]
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    capability = _capability()
    capability = replace(capability, **change)
    called = False

    def execute(_pack: dict[str, object], _root: Path) -> dict[str, object]:
        nonlocal called
        called = True
        return _result(pack)

    with pytest.raises(DispatchRuntimeError):
        runtime.execute(pack, capability=capability, executor=execute)
    assert called is False
    assert not list(runtime.raw_root.glob("invocation-*"))


def test_forged_capability_digest_and_wrong_project_root_fail_before_execution(
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

    forged = replace(_capability(), declaration_sha256="0" * 64)
    with pytest.raises(DispatchRuntimeError, match="declaration digest"):
        runtime.execute(pack, capability=forged, executor=execute)
    hostile_root = {
        **pack,
        "roots": [{**pack["roots"][0], "project_root": "/other"}],
    }
    with pytest.raises(DispatchRuntimeError, match="locked project root"):
        runtime.execute(hostile_root, capability=_capability(), executor=execute)
    assert called is False


def test_capability_must_resolve_from_runtime_trusted_surface_contract(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    alternate = copy.deepcopy(SURFACE_CONTRACT)
    codex = next(
        row for row in alternate["surfaces"] if row["surface_id"] == "codex"
    )
    codex["worker"]["launcher"] = "invented-launcher-v1"
    alternate_digest = canonical_sha256(alternate)
    invented = VerifiedExecutorCapability.from_trusted_surface_contract(
        surface_contract=alternate,
        expected_contract_sha256=alternate_digest,
        surface_id="codex",
        lane="fresh-worker",
        inherited_conversation_turns=0,
    )
    with pytest.raises(DispatchRuntimeError, match="trusted surface declaration"):
        runtime.execute(
            pack,
            capability=invented,
            executor=lambda p, _r: _result(p),
        )

    tampered = copy.deepcopy(SURFACE_CONTRACT)
    tampered["surfaces"][0]["projection_format"] = "tampered-v1"
    with pytest.raises(DispatchRuntimeError, match="digest differs"):
        DispatchRuntime(
            tmp_path / "other-project",
            surface_id="codex",
            surface_contract=tampered,
            expected_surface_contract_sha256=SURFACE_CONTRACT_SHA256,
        )


def test_project_lock_and_duplicate_dispatch_fail_closed(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    runtime.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))

    with pytest.raises(DispatchRuntimeError, match="dispatch id"):
        runtime.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))

    next_pack = _pack(runtime, dispatch_id=SECOND_DISPATCH_ID, ordinal=2)
    with runtime.lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(DispatchRuntimeError, match="active execution lane"):
            runtime.execute(
                next_pack,
                capability=_capability(),
                executor=lambda p, _r: _result(p),
            )


def test_separate_runtime_instances_reload_journal_under_shared_lock(
    tmp_path: Path,
) -> None:
    first = _runtime(tmp_path)
    second = DispatchRuntime(
        first.project_root, **_runtime_arguments(), clock_ns=Clock()
    )
    first.start_workflow(WORKFLOW_ID)
    pack = _pack(first)

    second.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))

    assert first.remaining_budget()["remaining_total_tokens"] == 32753
    with pytest.raises(DispatchRuntimeError, match="dispatch id"):
        first.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))


def test_state_root_is_canonical_and_cannot_be_selected_by_the_caller(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    assert runtime.state_root == (
        runtime.project_root / ".engineering/local/dispatch-runtime-v1"
    )
    with pytest.raises(TypeError):
        DispatchRuntime(  # type: ignore[misc]
            runtime.project_root,
            tmp_path / "alternate-state",
            **_runtime_arguments(),
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
            runtime.execute(
                pack,
                capability=_capability(),
                executor=lambda p, _r: _result(p),
            )

    secondary_runtime = DispatchRuntime(
        secondary, **_runtime_arguments(), clock_ns=Clock()
    )
    secondary_runtime.start_workflow(WORKFLOW_ID)
    with pytest.raises(DispatchRuntimeError, match="canonical root"):
        secondary_runtime.execute(
            pack,
            capability=_capability(),
            executor=lambda p, _r: _result(p),
        )


def test_cumulative_budget_deadline_serial_order_and_confirmed_retry(tmp_path: Path) -> None:
    clock = Clock()
    runtime = _runtime(tmp_path, clock)
    runtime.start_workflow(WORKFLOW_ID)
    first = _pack(runtime)
    failed = runtime.execute(
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
        runtime.execute(
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
    runtime.execute(
        retry,
        capability=_capability(),
        executor=lambda p, _r: _result(p, input_tokens=50, output_tokens=10),
        prior_result=failed,
    )
    assert runtime.remaining_budget()["remaining_total_tokens"] == 32588
    assert runtime.remaining_budget()["remaining_output_tokens"] == 8162

    third = _pack(runtime, dispatch_id="123e4567-e89b-42d3-a456-426614174003", ordinal=2)
    runtime.execute(third, capability=_capability(), executor=lambda p, _r: _result(p))
    out_of_order = _pack(
        runtime,
        dispatch_id="123e4567-e89b-42d3-a456-426614174004",
        ordinal=4,
    )
    with pytest.raises(DispatchRuntimeError, match="pack ordinal"):
        runtime.execute(
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
    success = runtime.execute(
        first, capability=_capability(), executor=lambda p, _r: _result(p)
    )
    forged = {**success, "status": "failed", "summary": "forged", "error_code": "worker_failed", "error_message": "forged", "failure_kind": "worker_failed", "side_effect_disposition": "rolled_back"}
    retry = _pack(
        runtime,
        dispatch_id=SECOND_DISPATCH_ID,
        attempt=2,
        prior_result=forged,
    )
    with pytest.raises(DispatchRuntimeError, match="exact retryable recorded"):
        runtime.execute(
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
    result = unknown.execute(
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

    result = runtime.execute(pack, capability=_capability(), executor=execute)
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
    result = runtime.execute(
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

    result = runtime.execute(pack, capability=_capability(), executor=explode)
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

    result = overrun.execute(
        deadline_pack, capability=_capability(), executor=exceed_deadline
    )
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

    runtime.execute(
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

    failed = runtime.execute(
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

    failed = runtime.execute(
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
            journal_runtime.project_root, **_runtime_arguments(), clock_ns=Clock()
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

    runtime = DispatchRuntime(project, **_runtime_arguments(), clock_ns=Clock())
    assert not stale.exists()

    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)
    original = runtime._remove_invocation

    def fail_cleanup(_path: Path) -> None:
        raise OSError("cleanup denied")

    monkeypatch.setattr(runtime, "_remove_invocation", fail_cleanup)
    with pytest.raises(DispatchRuntimeError, match="cleanup"):
        runtime.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))
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
        runtime.project_root, **_runtime_arguments(), clock_ns=Clock()
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

    result = runtime.execute(
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
    runtime.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))

    restarted = DispatchRuntime(
        runtime.project_root, **_runtime_arguments(), clock_ns=clock
    )
    assert restarted.start_workflow(WORKFLOW_ID)["remaining_total_tokens"] == 32753

    reset_clock = Clock(1)
    reset = DispatchRuntime(
        runtime.project_root, **_runtime_arguments(), clock_ns=reset_clock
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
        runtime.project_root, **_runtime_arguments(), clock_ns=Clock()
    )
    assert restarted.journal_snapshot() == before
