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
from types import MappingProxyType
from typing import Any, Iterator

from .distribution_contracts import (
    DistributionContractError,
    canonical_json_bytes,
    canonical_sha256,
    load_canonical_json,
    validate_distribution_contract,
)
from .skill_bundle import BundleTrustError, VerifiedBundle, verify_release_bundle


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
_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DispatchRuntimeError(RuntimeError):
    """A dispatch cannot cross the protected local execution boundary."""


@dataclass(frozen=True)
class VerifiedExecutorCapability:
    """Registry-bound enforcement facts for one worker or parent wrapper."""

    surface_id: str
    lane: str
    registry_sha256: str
    worker_declaration_sha256: str
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
    def _from_verified_surface_contract(
        cls,
        *,
        surface_contract: Mapping[str, Any],
        surface_contract_sha256: str,
        surface_id: str,
        lane: str,
        inherited_conversation_turns: int,
    ) -> "VerifiedExecutorCapability":
        """Derive enforcement facts from one externally rooted surface contract."""
        try:
            validate_distribution_contract("surface-activation-contract-v1", dict(surface_contract))
        except DistributionContractError as exc:
            raise DispatchRuntimeError("surface capability contract is invalid") from exc
        actual_sha256 = canonical_sha256(surface_contract)
        if actual_sha256 != surface_contract_sha256:
            raise DispatchRuntimeError("verified surface capability contract changed")
        rows = [row for row in surface_contract["surfaces"] if row["surface_id"] == surface_id]
        if len(rows) != 1:
            raise DispatchRuntimeError("surface capability declaration is absent or ambiguous")
        worker = rows[0]["worker"]
        if lane == "fresh-worker":
            if worker["fresh_worker"] != "verified":
                raise DispatchRuntimeError("surface has no verified fresh-worker capability")
            selected_only = bool(worker["selected_procedure_injection"])
            budget_enforced = bool(worker["budget_enforcement"])
            cancellation_enforced = bool(worker["cancellation"])
            result_enforced = bool(worker["result"])
        elif lane == "selected-only-parent":
            selected_only = True
            budget_enforced = True
            cancellation_enforced = True
            result_enforced = True
        else:
            raise DispatchRuntimeError("executor lane is unsupported")
        payload = {
            "surface_id": surface_id,
            "lane": lane,
            "registry_sha256": actual_sha256,
            "worker_declaration_sha256": canonical_sha256(worker),
            "inherited_conversation_turns": inherited_conversation_turns,
            "selected_only": selected_only,
            "budget_accounting_enforced": budget_enforced,
            "cancellation_enforced": cancellation_enforced,
            "result_handoff_enforced": result_enforced,
            "permits_child_spawn": False,
            "permits_redispatch": False,
            "permits_activation": False,
            "permits_detached_work": False,
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
            "worker_declaration_sha256": self.worker_declaration_sha256,
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


@dataclass(frozen=True)
class DispatchLauncherIdentity:
    """Exact repository adapter identity bound to one verified declaration."""

    surface_id: str
    lane: str
    launcher_id: str
    configuration_sha256: str
    capability_declaration_sha256: str
    inherited_conversation_turns: int


@dataclass(frozen=True)
class DispatchExecutionEvidence:
    """Accounting and result evidence emitted by a trusted wrapper."""

    result: Mapping[str, Any]
    input_tokens: int
    output_tokens: int
    elapsed_milliseconds: int
    capability_declaration_sha256: str
    launcher_configuration_sha256: str
    deadline_enforced: bool
    cancellation_enforced: bool
    result_handoff_enforced: bool


class RepositoryDispatchLauncher:
    """Base class for exact launcher adapters owned by this repository."""

    @property
    def identity(self) -> DispatchLauncherIdentity:
        raise NotImplementedError

    def launch(self, pack: Mapping[str, Any], invocation_root: Path) -> DispatchExecutionEvidence:
        raise NotImplementedError


# This registry is intentionally empty until a native wrapper has been implemented
# and independently verified. Tests replace the whole immutable mapping with a
# closed fixture adapter; the runtime exposes no adapter-registration API.
_REPOSITORY_LAUNCHER_TYPES: Mapping[tuple[str, str, str, str], type[RepositoryDispatchLauncher]] = (
    MappingProxyType({})
)
_PARENT_LAUNCHER_ID = "selected-only-parent-wrapper-v1"


def _real_directory(path: Path, *, create: bool, required_mode: int | None) -> Path:
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
        *,
        surface_id: str,
        verified_bundle: VerifiedBundle,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if not isinstance(verified_bundle, VerifiedBundle) or not verified_bundle.is_verified():
            raise DispatchRuntimeError("dispatch runtime requires an externally verified bundle")
        try:
            rooted_bundle = verify_release_bundle(
                verified_bundle.root, verified_bundle.release_root_sha256
            )
        except BundleTrustError as exc:
            raise DispatchRuntimeError(
                "dispatch bundle no longer matches its external root"
            ) from exc
        self.surface_contract = copy.deepcopy(rooted_bundle.surface_contract)
        self.verified_bundle = rooted_bundle
        self.surface_id = surface_id
        self.release_root_sha256 = rooted_bundle.release_root_sha256
        self.bundle_index_sha256 = rooted_bundle.bundle_index_sha256
        self.surface_contract_sha256 = canonical_sha256(self.surface_contract)
        VerifiedExecutorCapability._from_verified_surface_contract(
            surface_contract=self.surface_contract,
            surface_contract_sha256=self.surface_contract_sha256,
            surface_id=surface_id,
            lane="selected-only-parent",
            inherited_conversation_turns=0,
        )
        self.project_root = _real_directory(project_root, create=False, required_mode=None)
        self.state_root = _real_directory(
            self.project_root / ".engineering/local/dispatch-runtime-v1",
            create=True,
            required_mode=0o700,
        )
        self.raw_root = _real_directory(self.state_root / "raw", create=True, required_mode=0o700)
        self.lock_path = self.state_root / "dispatch.lock"
        self.journal_path = self.state_root / "dispatch-journal-v1.json"
        self._clock_ns = clock_ns
        self._ensure_lock_file()
        with self._project_lock():
            self._journal = self._load_or_initialize_journal()
            self._startup_cleanup()

    def _ensure_lock_file(self) -> None:
        self._ensure_lock_path(self.lock_path)

    @staticmethod
    def _ensure_lock_path(lock_path: Path) -> None:
        if lock_path.is_symlink():
            raise DispatchRuntimeError("dispatch lock must not be a symlink")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        metadata = os.fstat(descriptor)
        os.close(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise DispatchRuntimeError("dispatch lock must be one regular file")
        os.chmod(lock_path, 0o600)

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
            raise DispatchRuntimeError("dispatch journal must be one mode-0600 regular file")
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
            "failure_kind",
            "side_effect_disposition",
            "side_effect_ledger_sha256",
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
                or value["cleanup_state"] not in {"pending", "clean", "startup-cleaned", "failed"}
                or value["failure_kind"]
                not in {
                    None,
                    "spawn_failed",
                    "capacity_exhausted",
                    "timeout",
                    "budget_exhausted",
                    "worker_failed",
                    "cancelled",
                }
                or value["side_effect_disposition"]
                not in {"none", "rolled_back", "committed_known", "unknown"}
                or (
                    value["side_effect_ledger_sha256"] is not None
                    and (
                        not isinstance(value["side_effect_ledger_sha256"], str)
                        or _SHA256_RE.fullmatch(value["side_effect_ledger_sha256"]) is None
                    )
                )
            ):
                raise DispatchRuntimeError("last dispatch result digest is invalid")
            status = value["status"]
            failure_kind = value["failure_kind"]
            disposition = value["side_effect_disposition"]
            ledger = value["side_effect_ledger_sha256"]
            if (
                (
                    status in {"success", "needs_input", "needs_authority"}
                    and failure_kind is not None
                )
                or (
                    status == "failed"
                    and failure_kind
                    not in {
                        "spawn_failed",
                        "capacity_exhausted",
                        "timeout",
                        "budget_exhausted",
                        "worker_failed",
                    }
                )
                or (status == "cancelled" and failure_kind != "cancelled")
                or (disposition == "committed_known") != (ledger is not None)
            ):
                raise DispatchRuntimeError("last dispatch status metadata is inconsistent")
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
        if (
            not isinstance(active["workflow_id"], str)
            or _UUID4_RE.fullmatch(active["workflow_id"]) is None
        ):
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
            or any(
                not isinstance(value, str) or _UUID4_RE.fullmatch(value) is None
                for value in dispatch_ids
            )
        ):
            raise DispatchRuntimeError("active workflow dispatch ids are invalid")
        flattened: list[str] = []
        attempt_keys = list(active["attempts"])
        if any(
            not isinstance(key, str) or not key.isdigit() or not 1 <= int(key) <= 16
            for key in attempt_keys
        ):
            raise DispatchRuntimeError("active workflow attempt keys are invalid")
        for key in sorted(attempt_keys, key=lambda value: int(value)):
            values = active["attempts"][key]
            if not isinstance(values, list) or not 1 <= len(values) <= 2:
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
        with self._lock_paths((self.lock_path,)):
            yield

    @contextmanager
    def _lock_paths(self, paths: tuple[Path, ...]) -> Iterator[None]:
        handles = []
        try:
            for path in sorted(set(paths), key=lambda item: item.as_posix()):
                handle = path.open("a+b")
                handles.append(handle)
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise DispatchRuntimeError(
                        "another active execution lane holds a project lock"
                    ) from exc
            yield
        finally:
            for handle in reversed(handles):
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()

    @contextmanager
    def _execution_locks(self, pack: Mapping[str, Any]) -> Iterator[None]:
        lock_paths: list[Path] = []
        for row in pack["roots"]:
            root = _real_directory(Path(row["project_root"]), create=False, required_mode=None)
            state = _real_directory(
                root / ".engineering/local/dispatch-runtime-v1",
                create=True,
                required_mode=0o700,
            )
            lock_path = state / "dispatch.lock"
            self._ensure_lock_path(lock_path)
            lock_paths.append(lock_path)
        with self._lock_paths(tuple(lock_paths)):
            yield

    def start_workflow(self, workflow_id: str) -> dict[str, int]:
        """Start the monotonic deadline before routing and return its exact budget."""
        if not isinstance(workflow_id, str) or _UUID4_RE.fullmatch(workflow_id) is None:
            raise DispatchRuntimeError("workflow id must be a lowercase UUIDv4")
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
            self._journal["last_dispatch"] = None
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
        monotonic_elapsed = (
            self._clock_ns() - active["deadline_started_monotonic_ns"]
        ) // 1_000_000
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

    def _validate_launcher(
        self,
        pack: Mapping[str, Any],
        launcher: RepositoryDispatchLauncher,
    ) -> tuple[VerifiedExecutorCapability, DispatchLauncherIdentity]:
        if not isinstance(launcher, RepositoryDispatchLauncher):
            raise DispatchRuntimeError("executor is not a repository-owned launcher")
        if type(launcher) not in frozenset(_REPOSITORY_LAUNCHER_TYPES.values()):
            raise DispatchRuntimeError(
                "executor type is absent from the repository launcher registry"
            )
        identity = launcher.identity
        if not isinstance(identity, DispatchLauncherIdentity):
            raise DispatchRuntimeError("launcher identity is invalid")
        expected = VerifiedExecutorCapability._from_verified_surface_contract(
            surface_contract=self.surface_contract,
            surface_contract_sha256=self.surface_contract_sha256,
            surface_id=self.surface_id,
            lane=pack["execution_lane"],
            inherited_conversation_turns=identity.inherited_conversation_turns,
        )
        surface = next(
            row for row in self.surface_contract["surfaces"] if row["surface_id"] == self.surface_id
        )
        launcher_id = (
            surface["worker"]["launcher"]
            if expected.lane == "fresh-worker"
            else _PARENT_LAUNCHER_ID
        )
        if not isinstance(launcher_id, str):
            raise DispatchRuntimeError("verified surface has no launcher identity")
        configuration_sha256 = canonical_sha256(
            {
                "schema_version": 1,
                "release_root_sha256": self.release_root_sha256,
                "bundle_index_sha256": self.bundle_index_sha256,
                "surface_contract_sha256": self.surface_contract_sha256,
                "surface_id": self.surface_id,
                "lane": expected.lane,
                "launcher_id": launcher_id,
                "worker_declaration_sha256": expected.worker_declaration_sha256,
            }
        )
        expected_identity = DispatchLauncherIdentity(
            surface_id=self.surface_id,
            lane=expected.lane,
            launcher_id=launcher_id,
            configuration_sha256=configuration_sha256,
            capability_declaration_sha256=expected.declaration_sha256,
            inherited_conversation_turns=identity.inherited_conversation_turns,
        )
        if identity != expected_identity:
            raise DispatchRuntimeError("launcher identity differs from verified declaration")
        trusted_type = _REPOSITORY_LAUNCHER_TYPES.get(
            (
                self.surface_id,
                expected.lane,
                launcher_id,
                configuration_sha256,
            )
        )
        if trusted_type is None or type(launcher) is not trusted_type:
            raise DispatchRuntimeError("verified declaration has no repository-owned launcher")
        if not (
            expected.selected_only
            and expected.budget_accounting_enforced
            and expected.cancellation_enforced
            and expected.result_handoff_enforced
        ):
            raise DispatchRuntimeError("executor cannot enforce the selected-only bounded contract")
        if any(
            (
                expected.permits_child_spawn,
                expected.permits_redispatch,
                expected.permits_activation,
                expected.permits_detached_work,
            )
        ):
            raise DispatchRuntimeError("executor permits forbidden nested or detached behavior")
        if expected.lane == "fresh-worker" and expected.inherited_conversation_turns != 0:
            raise DispatchRuntimeError("fresh worker must inherit zero conversation turns")
        if expected.inherited_conversation_turns < 0:
            raise DispatchRuntimeError("inherited conversation count is invalid")
        return expected, expected_identity

    def _validate_state_transition(
        self,
        pack: Mapping[str, Any],
        prior_result: Mapping[str, Any] | None,
    ) -> None:
        active = self._active()
        if pack["workflow_id"] != active["workflow_id"]:
            raise DispatchRuntimeError("pack workflow differs from active workflow")
        if pack["roots"][0]["project_root"] != self.project_root.as_posix():
            raise DispatchRuntimeError(
                "the runtime project must be the pack's canonical first root"
            )
        if pack["dispatch_id"] in active["dispatch_ids"]:
            raise DispatchRuntimeError("dispatch id was already consumed")
        if pack["budget"] != self._remaining_budget():
            raise DispatchRuntimeError("pack budget does not equal the current cumulative budget")
        ordinal = pack["workflow_pack_ordinal"]
        attempt = pack["attempt_ordinal"]
        attempts = active["attempts"]
        existing = attempts.get(str(ordinal), [])
        used_ordinals = sorted(int(value) for value in attempts)
        last = self._journal["last_dispatch"]
        if (
            last is not None
            and last["status"] in {"failed", "cancelled"}
            and last["dispatch_id"] == active["dispatch_ids"][-1]
            and attempt != 2
        ):
            raise DispatchRuntimeError(
                "a terminal worker failure requires an exact confirmed attempt-two continuation"
            )
        if attempt == 1:
            expected = 1 if not used_ordinals else used_ordinals[-1] + 1
            if ordinal != expected or existing:
                raise DispatchRuntimeError("workflow pack ordinal is not the next serial pack")
        elif len(existing) != 1 or prior_result is None:
            raise DispatchRuntimeError(
                "attempt two requires exactly one prior dispatch for its pack"
            )
        elif (
            last is None
            or last["workflow_id"] != pack["workflow_id"]
            or last["dispatch_id"] != existing[0]
            or last["result_sha256"] != canonical_sha256(prior_result)
            or last["status"] not in {"failed", "cancelled"}
            or last["side_effect_disposition"] == "unknown"
        ):
            raise DispatchRuntimeError(
                "attempt-two prior result is not the exact retryable recorded terminal result"
            )
        if len(existing) >= 2:
            raise DispatchRuntimeError("workflow pack already consumed its two-dispatch limit")

    def execute(
        self,
        pack: dict[str, Any],
        *,
        launcher: RepositoryDispatchLauncher,
        prior_result: dict[str, Any] | None = None,
        artifact_handoff: Callable[[dict[str, Any], bytes], None] | None = None,
    ) -> dict[str, Any]:
        """Execute one exact pack under the shared lock and delete all raw state."""
        try:
            validate_distribution_contract("dispatch-pack-v1", pack, prior_result=prior_result)
        except DistributionContractError as exc:
            raise DispatchRuntimeError(f"dispatch pack is invalid: {exc}") from exc
        if pack["roots"][0]["project_root"] != self.project_root.as_posix():
            raise DispatchRuntimeError(
                "dispatch pack canonical root differs from the locked project root"
            )
        with self._execution_locks(pack):
            self._refresh_journal()
            self._require_unblocked()
            capability, launcher_identity = self._validate_launcher(pack, launcher)
            self._validate_state_transition(pack, prior_result)
            invocation = self.raw_root / f"invocation-{pack['dispatch_id']}"
            if invocation.exists() or invocation.is_symlink():
                raise DispatchRuntimeError("raw invocation path already exists")
            old_umask = os.umask(0o077)
            execution_error: Exception | None = None
            result: dict[str, Any] | None = None
            launcher_started = False
            result_recorded = False
            try:
                invocation.mkdir(mode=0o700)
                _write_protected(invocation / "dispatch-pack-v1.json", canonical_json_bytes(pack))
                received = copy.deepcopy(pack)
                launcher_started = True
                evidence = launcher.launch(received, invocation)
                if not isinstance(evidence, DispatchExecutionEvidence):
                    raise DispatchRuntimeError("launcher did not return execution evidence")
                if (
                    evidence.capability_declaration_sha256 != capability.declaration_sha256
                    or evidence.launcher_configuration_sha256
                    != launcher_identity.configuration_sha256
                    or not evidence.deadline_enforced
                    or not evidence.cancellation_enforced
                    or not evidence.result_handoff_enforced
                ):
                    raise DispatchRuntimeError(
                        "launcher evidence differs from the verified declaration"
                    )
                if any(
                    type(value) is not int or value < 0
                    for value in (
                        evidence.input_tokens,
                        evidence.output_tokens,
                        evidence.elapsed_milliseconds,
                    )
                ):
                    raise DispatchRuntimeError("launcher accounting evidence is invalid")
                if not isinstance(evidence.result, Mapping):
                    raise DispatchRuntimeError("launcher result is not an object")
                result = copy.deepcopy(dict(evidence.result))
                result["input_tokens"] = evidence.input_tokens
                result["output_tokens"] = evidence.output_tokens
                result["elapsed_milliseconds"] = evidence.elapsed_milliseconds
                self._remaining_budget()
                try:
                    validate_distribution_contract("dispatch-result-v1", result, pack=pack)
                except DistributionContractError as exc:
                    raise DispatchRuntimeError(f"dispatch result is invalid: {exc}") from exc
                if evidence.input_tokens + evidence.output_tokens == 0:
                    raise DispatchRuntimeError(
                        "launcher evidence lacks trusted nonzero usage accounting"
                    )
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
                    raise DispatchRuntimeError(
                        "raw invocation cleanup failed; runtime is blocked"
                    ) from exc
            if execution_error is not None:
                if launcher_started and not result_recorded:
                    result = self._minimal_failed_result(pack)
                    self._record_result(pack, result)
                    self._journal["blocked"] = True
                    self._mark_cleanup_complete()
                    self._persist_journal()
                    return result
                if isinstance(execution_error, DispatchRuntimeError):
                    raise execution_error
                raise DispatchRuntimeError("launcher failed before launch") from execution_error
            assert result is not None
            return result

    def _block_unknown_dispatch(self, pack: Mapping[str, Any], failure: Exception) -> None:
        """Prevent implicit retry when execution ended without a trusted result."""
        active = self._active()
        if pack["dispatch_id"] not in active["dispatch_ids"]:
            active["dispatch_ids"].append(pack["dispatch_id"])
            active["attempts"].setdefault(str(pack["workflow_pack_ordinal"]), []).append(
                pack["dispatch_id"]
            )
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
            "failure_kind": result["failure_kind"],
            "side_effect_disposition": result["side_effect_disposition"],
            "side_effect_ledger_sha256": result["side_effect_ledger_sha256"],
            "cleanup_state": "pending",
        }
        if (
            result["status"] in {"failed", "cancelled"}
            and result["side_effect_disposition"] == "unknown"
        ):
            self._journal["blocked"] = True
        self._journal["cleanup_state"] = "pending"
        self._persist_journal()

    def _minimal_failed_result(self, pack: Mapping[str, Any]) -> dict[str, Any]:
        """Return a closed conservative result without trusting worker output."""
        budget = pack["budget"]
        output_tokens = min(budget["remaining_output_tokens"], budget["remaining_total_tokens"])
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
            "status": "failed",
            "summary": "Worker output was invalid or unavailable.",
            "error_code": "invalid_worker_result",
            "error_message": "The selected executor did not return a trusted result.",
            "failure_kind": "worker_failed",
            "side_effect_disposition": "unknown",
            "side_effect_ledger_sha256": None,
            "elapsed_milliseconds": budget["remaining_milliseconds"],
            "input_tokens": budget["remaining_total_tokens"] - output_tokens,
            "output_tokens": output_tokens,
            "artifacts": [],
        }

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

    def _verified_artifact(self, invocation: Path, path: Path, row: Mapping[str, Any]) -> bytes:
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
                raise DispatchRuntimeError("artifact ancestor must be a real mode-0700 directory")
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
