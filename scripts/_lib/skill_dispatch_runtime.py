"""Protected local execution boundary for validated dispatch packs and results.

Deterministic selection and pack construction live in ``skill_dispatch``. This
module owns the stateful policy that must be shared by worker and parent lanes:
one project lock, one monotonic workflow budget, protected raw staging, exact
result/artifact verification, metadata-only journaling, and terminal cleanup.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import os
import re
import shutil
import stat
import time
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .distribution_contracts import (
    DistributionContractError,
    canonical_json_bytes,
    canonical_sha256,
    load_canonical_json,
    validate_distribution_contract,
)


MAX_WORKFLOW_MILLISECONDS = 1_200_000
MAX_TOTAL_TOKENS = 32_768
MAX_OUTPUT_TOKENS = 8_192
_JOURNAL_KEYS = {
    "schema_version",
    "blocked",
    "cleanup_state",
    "active_workflow",
    "last_dispatch",
}
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DispatchRuntimeError(RuntimeError):
    """A dispatch cannot cross the protected local execution boundary."""


@dataclass(frozen=True)
class VerifiedExecutorCapability:
    """Registry-bound enforcement facts for one worker or parent wrapper."""

    surface_id: str
    lane: str
    registry_sha256: str
    declaration_sha256: str
    inherited_conversation_turns: int
    selected_only: bool
    budget_accounting_enforced: bool
    cancellation_enforced: bool
    result_handoff_enforced: bool
    permits_child_spawn: bool
    permits_redispatch: bool
    permits_activation: bool
    permits_detached_work: bool

    @classmethod
    def from_verified_registry_declaration(
        cls,
        *,
        surface_id: str,
        lane: str,
        registry_sha256: str,
        inherited_conversation_turns: int,
        selected_only: bool,
        budget_accounting_enforced: bool,
        cancellation_enforced: bool,
        result_handoff_enforced: bool,
        permits_child_spawn: bool,
        permits_redispatch: bool,
        permits_activation: bool,
        permits_detached_work: bool,
    ) -> "VerifiedExecutorCapability":
        """Bind a declaration already selected through the trusted registry."""
        payload = {
            "surface_id": surface_id,
            "lane": lane,
            "registry_sha256": registry_sha256,
            "inherited_conversation_turns": inherited_conversation_turns,
            "selected_only": selected_only,
            "budget_accounting_enforced": budget_accounting_enforced,
            "cancellation_enforced": cancellation_enforced,
            "result_handoff_enforced": result_handoff_enforced,
            "permits_child_spawn": permits_child_spawn,
            "permits_redispatch": permits_redispatch,
            "permits_activation": permits_activation,
            "permits_detached_work": permits_detached_work,
        }
        return cls(
            **payload,
            declaration_sha256=canonical_sha256(payload),
        )

    def digest_payload(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "lane": self.lane,
            "registry_sha256": self.registry_sha256,
            "inherited_conversation_turns": self.inherited_conversation_turns,
            "selected_only": self.selected_only,
            "budget_accounting_enforced": self.budget_accounting_enforced,
            "cancellation_enforced": self.cancellation_enforced,
            "result_handoff_enforced": self.result_handoff_enforced,
            "permits_child_spawn": self.permits_child_spawn,
            "permits_redispatch": self.permits_redispatch,
            "permits_activation": self.permits_activation,
            "permits_detached_work": self.permits_detached_work,
        }


def _real_directory(
    path: Path, *, create: bool, required_mode: int | None
) -> Path:
    original = path.expanduser()
    if original.is_symlink():
        raise DispatchRuntimeError(f"protected root must not be a symlink: {original}")
    if create:
        old_umask = os.umask(0o077)
        try:
            original.mkdir(
                parents=True,
                exist_ok=True,
                mode=required_mode if required_mode is not None else 0o700,
            )
        finally:
            os.umask(old_umask)
    if not original.is_dir() or original.is_symlink():
        raise DispatchRuntimeError(f"protected root is not a real directory: {original}")
    resolved = original.resolve(strict=True)
    if required_mode is not None:
        os.chmod(resolved, required_mode)
    return resolved


def _write_protected(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise DispatchRuntimeError(f"protected temporary path already exists: {temporary}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


class DispatchRuntime:
    """Persist and enforce one bounded dispatch workflow for one project."""

    def __init__(
        self,
        project_root: Path,
        state_root: Path,
        *,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.project_root = _real_directory(
            project_root, create=False, required_mode=None
        )
        self.state_root = _real_directory(
            state_root, create=True, required_mode=0o700
        )
        self.raw_root = _real_directory(
            self.state_root / "raw", create=True, required_mode=0o700
        )
        self.lock_path = self.state_root / "dispatch.lock"
        self.journal_path = self.state_root / "dispatch-journal-v1.json"
        self._clock_ns = clock_ns
        self._ensure_lock_file()
        with self._project_lock():
            self._journal = self._load_or_initialize_journal()
            self._startup_cleanup()

    def _ensure_lock_file(self) -> None:
        if self.lock_path.is_symlink():
            raise DispatchRuntimeError("dispatch lock must not be a symlink")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.lock_path, flags, 0o600)
        metadata = os.fstat(descriptor)
        os.close(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise DispatchRuntimeError("dispatch lock must be one regular file")
        os.chmod(self.lock_path, 0o600)

    def _load_or_initialize_journal(self) -> dict[str, Any]:
        if not self.journal_path.exists():
            journal = {
                "schema_version": 1,
                "blocked": False,
                "cleanup_state": "clean",
                "active_workflow": None,
                "last_dispatch": None,
            }
            self._journal = journal
            self._persist_journal()
            return journal
        if self.journal_path.is_symlink():
            raise DispatchRuntimeError("dispatch journal must not be a symlink")
        metadata = self.journal_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise DispatchRuntimeError(
                "dispatch journal must be one mode-0600 regular file"
            )
        try:
            journal = load_canonical_json(self.journal_path)
        except (DistributionContractError, OSError, UnicodeError) as exc:
            raise DispatchRuntimeError("dispatch journal is invalid") from exc
        if not isinstance(journal, dict) or set(journal) != _JOURNAL_KEYS:
            raise DispatchRuntimeError("dispatch journal has unknown or missing fields")
        if journal["schema_version"] != 1 or type(journal["blocked"]) is not bool:
            raise DispatchRuntimeError("dispatch journal version or blocked state is invalid")
        if journal["cleanup_state"] not in {
            "clean",
            "pending",
            "failed",
            "startup-cleaned",
        }:
            raise DispatchRuntimeError("dispatch journal cleanup state is invalid")
        active = journal["active_workflow"]
        if active is not None:
            self._validate_active_state(active)
            if self._clock_ns() < active["deadline_started_monotonic_ns"]:
                journal["blocked"] = True
                journal["cleanup_state"] = "failed"
        self._validate_last_dispatch(journal["last_dispatch"])
        return journal

    def _validate_last_dispatch(self, value: object) -> None:
        if value is None:
            return
        success_fields = {
            "workflow_id",
            "dispatch_id",
            "status",
            "result_sha256",
            "result_size",
            "input_tokens",
            "output_tokens",
            "elapsed_milliseconds",
            "cleanup_state",
        }
        failure_fields = {
            "workflow_id",
            "dispatch_id",
            "status",
            "failure_class",
            "side_effect_disposition",
            "cleanup_state",
        }
        if not isinstance(value, dict) or frozenset(value) not in {
            frozenset(success_fields),
            frozenset(failure_fields),
        }:
            raise DispatchRuntimeError("last dispatch journal record is not closed metadata")
        for field in ("workflow_id", "dispatch_id"):
            if not isinstance(value[field], str) or _UUID4_RE.fullmatch(value[field]) is None:
                raise DispatchRuntimeError("last dispatch journal id is invalid")
        if set(value) == success_fields:
            if (
                value["status"]
                not in {"success", "needs_input", "needs_authority", "failed", "cancelled"}
                or _SHA256_RE.fullmatch(value["result_sha256"]) is None
                or value["cleanup_state"]
                not in {"pending", "clean", "startup-cleaned", "failed"}
            ):
                raise DispatchRuntimeError("last dispatch result digest is invalid")
            if any(
                type(value[field]) is not int or value[field] < 0
                for field in (
                    "result_size",
                    "input_tokens",
                    "output_tokens",
                    "elapsed_milliseconds",
                )
            ):
                raise DispatchRuntimeError("last dispatch counters are invalid")
        elif (
            value["status"] != "failed-untrusted-result"
            or value["side_effect_disposition"] != "unknown"
            or not isinstance(value["failure_class"], str)
            or not 1 <= len(value["failure_class"]) <= 128
            or value["cleanup_state"] not in {"clean", "startup-cleaned", "failed"}
        ):
            raise DispatchRuntimeError("untrusted last dispatch state is invalid")

    def _validate_active_state(self, active: object) -> None:
        fields = {
            "workflow_id",
            "deadline_started_monotonic_ns",
            "consumed_total_tokens",
            "consumed_output_tokens",
            "reported_elapsed_milliseconds",
            "dispatch_ids",
            "attempts",
        }
        if not isinstance(active, dict) or set(active) != fields:
            raise DispatchRuntimeError("active workflow journal state is invalid")
        if not isinstance(active["workflow_id"], str) or _UUID4_RE.fullmatch(
            active["workflow_id"]
        ) is None:
            raise DispatchRuntimeError("active workflow id is invalid")
        integers = (
            "deadline_started_monotonic_ns",
            "consumed_total_tokens",
            "consumed_output_tokens",
            "reported_elapsed_milliseconds",
        )
        if any(type(active[field]) is not int or active[field] < 0 for field in integers):
            raise DispatchRuntimeError("active workflow counters are invalid")
        if not isinstance(active["dispatch_ids"], list) or not isinstance(active["attempts"], dict):
            raise DispatchRuntimeError("active workflow dispatch state is invalid")
        dispatch_ids = active["dispatch_ids"]
        if (
            len(dispatch_ids) > 32
            or len(dispatch_ids) != len(set(dispatch_ids))
            or any(not isinstance(value, str) or _UUID4_RE.fullmatch(value) is None for value in dispatch_ids)
        ):
            raise DispatchRuntimeError("active workflow dispatch ids are invalid")
        flattened: list[str] = []
        attempt_keys = list(active["attempts"])
        if any(
            not isinstance(key, str)
            or not key.isdigit()
            or not 1 <= int(key) <= 16
            for key in attempt_keys
        ):
            raise DispatchRuntimeError("active workflow attempt keys are invalid")
        for key in sorted(attempt_keys, key=lambda value: int(value)):
            values = active["attempts"][key]
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 2
            ):
                raise DispatchRuntimeError("active workflow attempts are invalid")
            flattened.extend(values)
        if flattened != dispatch_ids:
            raise DispatchRuntimeError("active workflow attempt order differs from dispatch ids")
        if (
            active["consumed_total_tokens"] > MAX_TOTAL_TOKENS
            or active["consumed_output_tokens"] > MAX_OUTPUT_TOKENS
            or active["consumed_output_tokens"] > active["consumed_total_tokens"]
            or active["reported_elapsed_milliseconds"] > MAX_WORKFLOW_MILLISECONDS
        ):
            raise DispatchRuntimeError("active workflow token counters exceed policy")

    def _persist_journal(self) -> None:
        _write_protected(self.journal_path, canonical_json_bytes(self._journal))

    def _refresh_journal(self) -> None:
        """Reload canonical state after acquiring the cross-process lock."""
        self._journal = self._load_or_initialize_journal()
        if self._journal["blocked"]:
            self._persist_journal()

    def _startup_cleanup(self) -> None:
        stale = sorted(self.raw_root.iterdir(), key=lambda path: path.name)
        pending = self._journal["cleanup_state"] == "pending"
        if not stale and not pending:
            if self._journal.get("blocked"):
                self._persist_journal()
            return
        try:
            for path in stale:
                self._remove_raw_entry(path)
        except OSError as exc:
            self._journal["blocked"] = True
            self._journal["cleanup_state"] = "failed"
            self._set_last_cleanup_state("failed")
            self._persist_journal()
            raise DispatchRuntimeError("startup raw cleanup failed") from exc
        self._journal["cleanup_state"] = "startup-cleaned"
        self._set_last_cleanup_state("startup-cleaned")
        self._persist_journal()

    @contextmanager
    def _project_lock(self) -> Iterator[None]:
        with self.lock_path.open("a+b") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise DispatchRuntimeError("another active execution lane holds the project lock") from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def start_workflow(self, workflow_id: str) -> dict[str, int]:
        """Start the monotonic deadline before routing and return its exact budget."""
        with self._project_lock():
            self._refresh_journal()
            self._require_unblocked()
            active = self._journal["active_workflow"]
            if active is not None:
                if active["workflow_id"] != workflow_id:
                    raise DispatchRuntimeError("another workflow is already active")
                return self._remaining_budget()
            self._journal["active_workflow"] = {
                "workflow_id": workflow_id,
                "deadline_started_monotonic_ns": self._clock_ns(),
                "consumed_total_tokens": 0,
                "consumed_output_tokens": 0,
                "reported_elapsed_milliseconds": 0,
                "dispatch_ids": [],
                "attempts": {},
            }
            self._journal["cleanup_state"] = "clean"
            self._persist_journal()
            return self._remaining_budget()

    def finish_workflow(self) -> None:
        with self._project_lock():
            self._refresh_journal()
            self._require_unblocked()
            if list(self.raw_root.iterdir()):
                raise DispatchRuntimeError("cannot finish with raw invocation state present")
            self._journal["active_workflow"] = None
            self._persist_journal()

    def _require_unblocked(self) -> None:
        if self._journal["blocked"]:
            raise DispatchRuntimeError("dispatch runtime is blocked by cleanup or clock recovery")

    def _active(self) -> dict[str, Any]:
        self._require_unblocked()
        active = self._journal["active_workflow"]
        if active is None:
            raise DispatchRuntimeError("no active workflow")
        return active

    def _remaining_budget(self) -> dict[str, int]:
        active = self._active()
        monotonic_elapsed = (self._clock_ns() - active["deadline_started_monotonic_ns"]) // 1_000_000
        elapsed = max(monotonic_elapsed, active["reported_elapsed_milliseconds"])
        remaining_ms = MAX_WORKFLOW_MILLISECONDS - elapsed
        if remaining_ms < 0:
            raise DispatchRuntimeError("workflow deadline is exhausted")
        remaining_total = MAX_TOTAL_TOKENS - active["consumed_total_tokens"]
        remaining_output = MAX_OUTPUT_TOKENS - active["consumed_output_tokens"]
        if remaining_total < 0 or remaining_output < 0:
            raise DispatchRuntimeError("workflow token budget is exhausted")
        return {
            "deadline_started_monotonic_ns": active["deadline_started_monotonic_ns"],
            "remaining_milliseconds": remaining_ms,
            "remaining_total_tokens": remaining_total,
            "remaining_output_tokens": remaining_output,
        }

    def remaining_budget(self) -> dict[str, int]:
        with self._project_lock():
            self._refresh_journal()
            return self._remaining_budget()

    def journal_snapshot(self) -> dict[str, Any]:
        with self._project_lock():
            self._refresh_journal()
            return copy.deepcopy(self._journal)

    def _validate_capability(
        self, pack: Mapping[str, Any], capability: VerifiedExecutorCapability
    ) -> None:
        if not isinstance(capability, VerifiedExecutorCapability):
            raise DispatchRuntimeError("executor capability is not registry-bound")
        if (
            _SHA256_RE.fullmatch(capability.registry_sha256) is None
            or canonical_sha256(capability.digest_payload())
            != capability.declaration_sha256
        ):
            raise DispatchRuntimeError("executor capability declaration digest differs")
        if capability.lane != pack["execution_lane"]:
            raise DispatchRuntimeError("executor lane differs from dispatch pack")
        if not (
            capability.selected_only
            and capability.budget_accounting_enforced
            and capability.cancellation_enforced
            and capability.result_handoff_enforced
        ):
            raise DispatchRuntimeError("executor cannot enforce the selected-only bounded contract")
        if any(
            (
                capability.permits_child_spawn,
                capability.permits_redispatch,
                capability.permits_activation,
                capability.permits_detached_work,
            )
        ):
            raise DispatchRuntimeError("executor permits forbidden nested or detached behavior")
        if capability.lane == "fresh-worker" and capability.inherited_conversation_turns != 0:
            raise DispatchRuntimeError("fresh worker must inherit zero conversation turns")
        if capability.inherited_conversation_turns < 0:
            raise DispatchRuntimeError("inherited conversation count is invalid")

    def _validate_state_transition(
        self,
        pack: Mapping[str, Any],
        prior_result: Mapping[str, Any] | None,
    ) -> None:
        active = self._active()
        if pack["workflow_id"] != active["workflow_id"]:
            raise DispatchRuntimeError("pack workflow differs from active workflow")
        selected_roots = {row["project_root"] for row in pack["roots"]}
        if self.project_root.as_posix() not in selected_roots:
            raise DispatchRuntimeError("pack roots do not include the locked project root")
        if pack["dispatch_id"] in active["dispatch_ids"]:
            raise DispatchRuntimeError("dispatch id was already consumed")
        if pack["budget"] != self._remaining_budget():
            raise DispatchRuntimeError("pack budget does not equal the current cumulative budget")
        ordinal = pack["workflow_pack_ordinal"]
        attempt = pack["attempt_ordinal"]
        attempts = active["attempts"]
        existing = attempts.get(str(ordinal), [])
        used_ordinals = sorted(int(value) for value in attempts)
        if attempt == 1:
            expected = 1 if not used_ordinals else used_ordinals[-1] + 1
            if ordinal != expected or existing:
                raise DispatchRuntimeError("workflow pack ordinal is not the next serial pack")
        elif len(existing) != 1 or prior_result is None:
            raise DispatchRuntimeError("attempt two requires exactly one prior dispatch for its pack")
        if len(existing) >= 2:
            raise DispatchRuntimeError("workflow pack already consumed its two-dispatch limit")

    def execute(
        self,
        pack: dict[str, Any],
        *,
        capability: VerifiedExecutorCapability,
        executor: Callable[[dict[str, Any], Path], dict[str, Any]],
        prior_result: dict[str, Any] | None = None,
        artifact_handoff: Callable[[dict[str, Any], bytes], None] | None = None,
    ) -> dict[str, Any]:
        """Execute one exact pack under the shared lock and delete all raw state."""
        with self._project_lock():
            self._refresh_journal()
            self._require_unblocked()
            self._validate_capability(pack, capability)
            try:
                validate_distribution_contract(
                    "dispatch-pack-v1", pack, prior_result=prior_result
                )
            except DistributionContractError as exc:
                raise DispatchRuntimeError(f"dispatch pack is invalid: {exc}") from exc
            self._validate_state_transition(pack, prior_result)
            invocation = self.raw_root / f"invocation-{pack['dispatch_id']}"
            if invocation.exists() or invocation.is_symlink():
                raise DispatchRuntimeError("raw invocation path already exists")
            old_umask = os.umask(0o077)
            execution_error: Exception | None = None
            result: dict[str, Any] | None = None
            executor_started = False
            result_recorded = False
            try:
                invocation.mkdir(mode=0o700)
                _write_protected(
                    invocation / "dispatch-pack-v1.json", canonical_json_bytes(pack)
                )
                received = copy.deepcopy(pack)
                executor_started = True
                produced = executor(received, invocation)
                if not isinstance(produced, dict):
                    raise DispatchRuntimeError("executor result is not an object")
                result = produced
                self._remaining_budget()
                try:
                    validate_distribution_contract(
                        "dispatch-result-v1", result, pack=pack
                    )
                except DistributionContractError as exc:
                    raise DispatchRuntimeError(f"dispatch result is invalid: {exc}") from exc
                _write_protected(
                    invocation / "dispatch-result-v1.json",
                    canonical_json_bytes(result),
                )
                self._handoff_artifacts(invocation, result, artifact_handoff)
                self._record_result(pack, result)
                result_recorded = True
            except Exception as exc:  # noqa: BLE001 - normalize an injected executor boundary
                execution_error = exc
            finally:
                os.umask(old_umask)
                try:
                    if invocation.exists() or invocation.is_symlink():
                        self._remove_invocation(invocation)
                    if result_recorded:
                        self._mark_cleanup_complete()
                except OSError as exc:
                    self._journal["blocked"] = True
                    self._journal["cleanup_state"] = "failed"
                    self._set_last_cleanup_state("failed")
                    self._persist_journal()
                    raise DispatchRuntimeError("raw invocation cleanup failed; runtime is blocked") from exc
            if execution_error is not None:
                if executor_started and not result_recorded:
                    self._block_unknown_dispatch(pack, execution_error)
                if isinstance(execution_error, DispatchRuntimeError):
                    raise execution_error
                raise DispatchRuntimeError("executor failed; no fallback or retry was inferred") from execution_error
            assert result is not None
            return result

    def _block_unknown_dispatch(
        self, pack: Mapping[str, Any], failure: Exception
    ) -> None:
        """Prevent implicit retry when execution ended without a trusted result."""
        active = self._active()
        if pack["dispatch_id"] not in active["dispatch_ids"]:
            active["dispatch_ids"].append(pack["dispatch_id"])
            active["attempts"].setdefault(
                str(pack["workflow_pack_ordinal"]), []
            ).append(pack["dispatch_id"])
        self._journal["blocked"] = True
        self._journal["last_dispatch"] = {
            "workflow_id": pack["workflow_id"],
            "dispatch_id": pack["dispatch_id"],
            "status": "failed-untrusted-result",
            "failure_class": type(failure).__name__,
            "side_effect_disposition": "unknown",
            "cleanup_state": self._journal["cleanup_state"],
        }
        self._persist_journal()

    def _record_result(self, pack: Mapping[str, Any], result: Mapping[str, Any]) -> None:
        active = self._active()
        total = result["input_tokens"] + result["output_tokens"]
        active["consumed_total_tokens"] += total
        active["consumed_output_tokens"] += result["output_tokens"]
        active["reported_elapsed_milliseconds"] += result["elapsed_milliseconds"]
        active["dispatch_ids"].append(pack["dispatch_id"])
        active["attempts"].setdefault(str(pack["workflow_pack_ordinal"]), []).append(
            pack["dispatch_id"]
        )
        self._journal["last_dispatch"] = {
            "workflow_id": pack["workflow_id"],
            "dispatch_id": pack["dispatch_id"],
            "status": result["status"],
            "result_sha256": canonical_sha256(result),
            "result_size": len(canonical_json_bytes(result)),
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "elapsed_milliseconds": result["elapsed_milliseconds"],
            "cleanup_state": "pending",
        }
        self._journal["cleanup_state"] = "pending"
        self._persist_journal()

    def _set_last_cleanup_state(self, state: str) -> None:
        last = self._journal.get("last_dispatch")
        if isinstance(last, dict) and "cleanup_state" in last:
            last["cleanup_state"] = state

    def _mark_cleanup_complete(self) -> None:
        self._journal["cleanup_state"] = "clean"
        self._set_last_cleanup_state("clean")
        self._persist_journal()

    def _handoff_artifacts(
        self,
        invocation: Path,
        result: Mapping[str, Any],
        handoff: Callable[[dict[str, Any], bytes], None] | None,
    ) -> None:
        artifacts = result["artifacts"]
        if artifacts and handoff is None:
            raise DispatchRuntimeError("artifact result requires an explicit verified handoff")
        aggregate = 0
        for row in artifacts:
            path = invocation / "artifacts" / row["sha256"] / row["name"]
            content = self._verified_artifact(invocation, path, row)
            aggregate += len(content)
            if aggregate > 64 * 1024 * 1024:
                raise DispatchRuntimeError("artifact aggregate exceeds 64 MiB")
            assert handoff is not None
            handoff(dict(row), content)

    def _verified_artifact(
        self, invocation: Path, path: Path, row: Mapping[str, Any]
    ) -> bytes:
        try:
            metadata = path.lstat()
        except FileNotFoundError as exc:
            raise DispatchRuntimeError("artifact regular file is missing") from exc
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise DispatchRuntimeError("artifact must be a regular file with one link")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise DispatchRuntimeError("artifact raw file must have mode 0600")
        cursor = path.parent
        while cursor != invocation:
            ancestor = cursor.lstat()
            if (
                stat.S_ISLNK(ancestor.st_mode)
                or not stat.S_ISDIR(ancestor.st_mode)
                or stat.S_IMODE(ancestor.st_mode) != 0o700
            ):
                raise DispatchRuntimeError(
                    "artifact ancestor must be a real mode-0700 directory"
                )
            cursor = cursor.parent
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(invocation.resolve(strict=True))
        except ValueError as exc:
            raise DispatchRuntimeError("artifact escapes its invocation root") from exc
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            content = handle.read(16 * 1024 * 1024 + 1)
        if (
            len(content) != row["size"]
            or len(content) > 16 * 1024 * 1024
            or hashlib.sha256(content).hexdigest() != row["sha256"]
            or row["uri"] != f"artifact://sha256/{row['sha256']}"
        ):
            raise DispatchRuntimeError("artifact bytes, size, hash, or URI differ")
        return content

    def _remove_invocation(self, path: Path) -> None:
        if path.is_symlink():
            raise OSError("raw invocation root is a symlink")
        shutil.rmtree(path)

    def _remove_raw_entry(self, path: Path) -> None:
        """Delete one stale raw entry without ever following a link."""
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            shutil.rmtree(path)
        else:
            path.unlink()
