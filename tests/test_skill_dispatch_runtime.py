from __future__ import annotations

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
    state = tmp_path / "state"
    return DispatchRuntime(project, state, clock_ns=clock or Clock())


def _capability(lane: str = "fresh-worker") -> VerifiedExecutorCapability:
    return VerifiedExecutorCapability.from_verified_registry_declaration(
        surface_id="codex",
        lane=lane,
        registry_sha256="c" * 64,
        inherited_conversation_turns=0 if lane == "fresh-worker" else 7,
        selected_only=True,
        budget_accounting_enforced=True,
        cancellation_enforced=True,
        result_handoff_enforced=True,
        permits_child_spawn=False,
        permits_redispatch=False,
        permits_activation=False,
        permits_detached_work=False,
    )


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
    runtime = DispatchRuntime(project, tmp_path / "state", clock_ns=clock)
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
    values = {**capability.digest_payload(), **change}
    capability = VerifiedExecutorCapability.from_verified_registry_declaration(**values)
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
    second = DispatchRuntime(first.project_root, first.state_root, clock_ns=Clock())
    first.start_workflow(WORKFLOW_ID)
    pack = _pack(first)

    second.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))

    assert first.remaining_budget()["remaining_total_tokens"] == 32753
    with pytest.raises(DispatchRuntimeError, match="dispatch id"):
        first.execute(pack, capability=_capability(), executor=lambda p, _r: _result(p))


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


def test_invalid_or_over_budget_result_is_rejected_and_still_cleans_raw_state(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)

    def execute(p: dict[str, object], _root: Path) -> dict[str, object]:
        result = _result(p)
        result["output_tokens"] = 9000
        return result

    with pytest.raises(DispatchRuntimeError, match="result"):
        runtime.execute(pack, capability=_capability(), executor=execute)
    assert not list(runtime.raw_root.glob("invocation-*"))
    assert runtime.journal_snapshot()["blocked"] is True
    assert runtime.journal_snapshot()["last_dispatch"]["side_effect_disposition"] == "unknown"


def test_executor_exception_or_actual_deadline_overrun_blocks_implicit_retry(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path / "exception")
    runtime.start_workflow(WORKFLOW_ID)
    pack = _pack(runtime)

    def explode(_pack: dict[str, object], _root: Path) -> dict[str, object]:
        raise RuntimeError("secret executor details")

    with pytest.raises(DispatchRuntimeError, match="no fallback or retry"):
        runtime.execute(pack, capability=_capability(), executor=explode)
    assert runtime.journal_snapshot()["blocked"] is True
    assert "secret executor details" not in str(runtime.journal_snapshot())

    clock = Clock()
    overrun = _runtime(tmp_path / "deadline", clock)
    overrun.start_workflow(WORKFLOW_ID)
    deadline_pack = _pack(overrun)

    def exceed_deadline(p: dict[str, object], _root: Path) -> dict[str, object]:
        clock.advance_ms(1_200_001)
        return _result(p)

    with pytest.raises(DispatchRuntimeError, match="deadline"):
        overrun.execute(deadline_pack, capability=_capability(), executor=exceed_deadline)
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

    with pytest.raises(DispatchRuntimeError, match="regular file"):
        runtime.execute(
            hostile_pack,
            capability=_capability(),
            executor=hostile,
            artifact_handoff=lambda _row, _content: None,
        )


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

    with pytest.raises(DispatchRuntimeError, match="one link"):
        runtime.execute(
            pack,
            capability=_capability(),
            executor=hard_linked,
            artifact_handoff=lambda _row, _content: None,
        )

    journal_runtime = _runtime(tmp_path / "journal")
    journal_alias = tmp_path / "journal-alias"
    os.link(journal_runtime.journal_path, journal_alias)
    with pytest.raises(DispatchRuntimeError, match="mode-0600 regular file"):
        DispatchRuntime(
            journal_runtime.project_root,
            journal_runtime.state_root,
            clock_ns=Clock(),
        )


def test_startup_recovery_removes_stale_raw_dirs_and_cleanup_failure_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    state = tmp_path / "state"
    raw = state / "raw"
    stale = raw / "invocation-stale"
    stale.mkdir(parents=True)
    (stale / "secret").write_text("do not retain", encoding="utf-8")

    runtime = DispatchRuntime(project, state, clock_ns=Clock())
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

    restarted = DispatchRuntime(runtime.project_root, runtime.state_root, clock_ns=Clock())

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

    restarted = DispatchRuntime(runtime.project_root, runtime.state_root, clock_ns=clock)
    assert restarted.start_workflow(WORKFLOW_ID)["remaining_total_tokens"] == 32753

    reset_clock = Clock(1)
    reset = DispatchRuntime(runtime.project_root, runtime.state_root, clock_ns=reset_clock)
    with pytest.raises(DispatchRuntimeError, match="blocked"):
        reset.remaining_budget()
