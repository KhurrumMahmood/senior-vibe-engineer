"""Bounded evidence harness for read-only on-demand portability journeys."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Mapping, Sequence

DeclaredOutcome = Literal["complete", "partial", "unsupported"]
FinalOutcome = Literal[
    "complete", "partial", "unsupported", "tool-missing", "syntax-error",
    "native-check-failure", "unexpected-source-mutation",
]


class ToolMissing(RuntimeError):
    """The closure cannot run because a named required tool is unavailable."""

    def __init__(self, tool: str) -> None:
        self.tool = tool
        super().__init__(f"required tool is unavailable: {tool}")


class SyntaxFailure(RuntimeError):
    """The selected source cannot be parsed by the closure's native analyzer."""


@dataclass(frozen=True)
class JourneyObservation:
    outcome: DeclaredOutcome
    summary: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeCheck:
    name: str
    argv: tuple[str, ...]
    cwd: Path | None = None


@dataclass(frozen=True)
class NativeResult:
    name: str
    argv: tuple[str, ...]
    status: Literal["passed", "failed", "tool-missing"]
    returncode: int | None
    stdout: str
    stderr: str


@dataclass(frozen=True)
class SourceChange:
    path: str
    stage: Literal["after_closure", "after_native"]
    kind: Literal["created", "modified", "deleted"]


@dataclass(frozen=True)
class ArtifactEvent:
    path: str
    stage: Literal["after_closure", "after_native"]
    event: Literal["created", "modified", "deleted"]


@dataclass(frozen=True)
class JourneyContext:
    project_root: Path
    library_root: Path
    guides: tuple[Path, ...]
    tool_roots: tuple[Path, ...]
    source_inventory_tool: Path


@dataclass(frozen=True)
class JourneyResult:
    outcome: FinalOutcome
    guide_hashes: Mapping[str, str]
    tool_hashes: Mapping[str, str]
    source_digests: Mapping[str, Mapping[str, str]]
    source_changes: tuple[SourceChange, ...]
    observation: JourneyObservation | None
    native_results: tuple[NativeResult, ...]
    artifact_hashes: Mapping[str, Mapping[str, str | None]]
    artifact_events: tuple[ArtifactEvent, ...]
    absolute_closure_paths: tuple[Path, ...]
    failure: str | None = None


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _member(
    raw: object, *, root: Path, label: str, kind: Literal["file", "directory"]
) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} is required")
    path = Path(raw).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within library root: {path}") from exc
    valid = path.is_file() if kind == "file" else path.is_dir()
    if not valid:
        raise ValueError(f"{label} must be an existing {kind}: {path}")
    return path


def _validate_handoff(handoff: Mapping[str, object]) -> JourneyContext:
    if handoff.get("mode") != "on_demand_library" or handoff.get("available") is not True:
        raise ValueError("journey requires an available on-demand library handoff")
    raw_root = handoff.get("library_root")
    if not isinstance(raw_root, str):
        raise ValueError("handoff library_root is required")
    library = Path(raw_root).resolve()
    if not library.is_dir():
        raise ValueError(f"library root must be an existing directory: {library}")
    raw_guides = handoff.get("guides")
    if not isinstance(raw_guides, list) or not raw_guides:
        raise ValueError("handoff guides must be a non-empty list")
    raw_skills = handoff.get("skills")
    if (
        not isinstance(raw_skills, list)
        or not raw_skills
        or any(not isinstance(skill, str) or not skill for skill in raw_skills)
    ):
        raise ValueError("handoff skills must be a non-empty string list")

    guides: list[Path] = []
    tool_roots: list[Path] = []
    guide_skills: list[str] = []
    for index, row in enumerate(raw_guides):
        if not isinstance(row, dict):
            raise ValueError(f"guide row {index} must be an object")
        if not isinstance(row.get("skill"), str) or not row["skill"]:
            raise ValueError(f"guide row {index} skill is required")
        guide_skills.append(row["skill"])
        _member(row.get("skill_root"), root=library,
                label=f"guide row {index} skill_root", kind="directory")
        guides.append(
            _member(row.get("guide"), root=library,
                    label=f"guide row {index} guide", kind="file")
        )
        if row.get("bundled_tooling") is not None:
            tool_roots.append(
                _member(row["bundled_tooling"], root=library,
                        label=f"guide row {index} bundled_tooling", kind="directory")
            )
    if guide_skills != raw_skills:
        raise ValueError("handoff guides must match the exact ordered skill closure")
    tool_roots.append(
        _member(handoff.get("shared_tooling"), root=library,
                label="shared_tooling", kind="directory")
    )
    inventory = _member(handoff.get("source_inventory_tool"), root=library,
                        label="source_inventory_tool", kind="file")
    return JourneyContext(
        Path(), library, tuple(guides), tuple(dict.fromkeys(tool_roots)), inventory
    )


def _hash_closure(context: JourneyContext) -> tuple[dict[str, str], dict[str, str]]:
    library = context.library_root
    guide_hashes = {
        path.relative_to(library).as_posix(): _digest(path) for path in context.guides
    }
    tool_hashes: dict[str, str] = {}
    for root in context.tool_roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                resolved.relative_to(library)
            except ValueError as exc:
                raise ValueError(f"tool must stay within library root: {path}") from exc
            tool_hashes[resolved.relative_to(library).as_posix()] = _digest(resolved)
    return guide_hashes, tool_hashes


def _source_snapshot(
    project: Path, inventory_tool: Path
) -> dict[str, str]:
    """Run the copied inventory in isolation so checkout imports cannot leak in."""
    completed = subprocess.run(
        (
            sys.executable,
            "-I",
            "-S",
            str(inventory_tool),
            "--project-root",
            str(project),
        ),
        cwd=project,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"on-demand source inventory failed: {detail or completed.returncode}")
    try:
        inventory = json.loads(completed.stdout)
        files = inventory["files"]
        if not isinstance(files, list):
            raise TypeError("files is not a list")
        paths = [row["path"] for row in files]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("on-demand source inventory emitted an invalid payload") from exc
    if any(not isinstance(path, str) for path in paths):
        raise ValueError("on-demand source inventory emitted an invalid file path")
    snapshot: dict[str, str] = {}
    for path in paths:
        candidate = (project / path).resolve(strict=False)
        try:
            candidate.relative_to(project)
        except ValueError as exc:
            raise ValueError(f"on-demand source inventory escaped project root: {path}") from exc
        snapshot[path] = _digest(candidate)
    return snapshot


def _changes(
    before: Mapping[str, str], after: Mapping[str, str], *, stage: str
) -> tuple[SourceChange, ...]:
    changes = []
    for path in sorted(before.keys() | after.keys()):
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        kind = "created" if old is None else "deleted" if new is None else "modified"
        changes.append(SourceChange(path, stage, kind))
    return tuple(changes)


def _artifact_snapshot(project: Path, paths: Sequence[Path]) -> dict[str, str | None]:
    snapshot: dict[str, str | None] = {}
    for raw in paths:
        path = raw if raw.is_absolute() else project / raw
        resolved = path.resolve(strict=False)
        try:
            relative = resolved.relative_to(project).as_posix()
        except ValueError as exc:
            raise ValueError(f"artifact must stay within project root: {path}") from exc
        if resolved.exists() and not resolved.is_file():
            raise ValueError(f"artifact must be a file or absent: {path}")
        snapshot[relative] = _digest(resolved) if resolved.is_file() else None
    return snapshot


def _artifact_events(
    snapshots: Mapping[str, Mapping[str, str | None]],
) -> tuple[ArtifactEvent, ...]:
    events = []
    stages = (("before", "after_closure"), ("after_closure", "after_native"))
    for previous, stage in stages:
        for path, old in snapshots[previous].items():
            new = snapshots[stage][path]
            if old == new:
                continue
            event = "created" if old is None else "deleted" if new is None else "modified"
            events.append(ArtifactEvent(path, stage, event))
    return tuple(events)


def run_read_only_journey(
    *,
    project_root: Path,
    handoff: Mapping[str, object],
    closure: Callable[[JourneyContext], JourneyObservation],
    native_checks: Sequence[NativeCheck] = (),
    artifact_paths: Sequence[Path] = (),
) -> JourneyResult:
    """Run one caller-owned closure and capture bounded, read-only evidence."""
    project = project_root.resolve()
    if not project.is_dir():
        raise ValueError(f"project root must be an existing directory: {project}")
    base_context = _validate_handoff(handoff)
    context = JourneyContext(
        project, base_context.library_root, base_context.guides, base_context.tool_roots,
        base_context.source_inventory_tool,
    )
    guide_hashes, tool_hashes = _hash_closure(context)
    source_digests = {"before": _source_snapshot(project, context.source_inventory_tool)}
    artifact_hashes = {"before": _artifact_snapshot(project, artifact_paths)}
    observation: JourneyObservation | None = None
    failure: str | None = None
    outcome: FinalOutcome = "complete"

    try:
        observation = closure(context)
        if not isinstance(observation, JourneyObservation):
            raise TypeError("closure must return JourneyObservation")
        if observation.outcome not in ("complete", "partial", "unsupported"):
            raise ValueError(f"invalid observation outcome: {observation.outcome}")
        outcome = observation.outcome
    except ToolMissing as exc:
        outcome, failure = "tool-missing", str(exc)
    except SyntaxFailure as exc:
        outcome, failure = "syntax-error", str(exc)
    source_digests["after_closure"] = _source_snapshot(project, context.source_inventory_tool)
    artifact_hashes["after_closure"] = _artifact_snapshot(project, artifact_paths)

    native_results: list[NativeResult] = []
    if failure is None:
        for check in native_checks:
            if not check.argv or any(not isinstance(arg, str) for arg in check.argv):
                raise ValueError(f"native check {check.name!r} requires literal argv")
            cwd = (check.cwd or project).resolve()
            try:
                cwd.relative_to(project)
            except ValueError as exc:
                raise ValueError("native check cwd must stay within project root") from exc
            if not cwd.is_dir():
                raise ValueError(f"native check cwd must be an existing directory: {cwd}")
            try:
                completed = subprocess.run(
                    check.argv, cwd=cwd, check=False, capture_output=True, text=True,
                    shell=False,
                )
            except FileNotFoundError:
                native_results.append(
                    NativeResult(check.name, check.argv, "tool-missing", None, "", "")
                )
                outcome, failure = "tool-missing", f"required tool is unavailable: {check.argv[0]}"
                break
            status = "passed" if completed.returncode == 0 else "failed"
            native_results.append(
                NativeResult(
                    check.name, check.argv, status, completed.returncode, completed.stdout,
                    completed.stderr,
                )
            )
            if completed.returncode != 0:
                outcome, failure = "native-check-failure", f"native check failed: {check.name}"
                break

    source_digests["after_native"] = _source_snapshot(project, context.source_inventory_tool)
    artifact_hashes["after_native"] = _artifact_snapshot(project, artifact_paths)
    source_changes = (
        *_changes(source_digests["before"], source_digests["after_closure"],
                  stage="after_closure"),
        *_changes(source_digests["after_closure"], source_digests["after_native"],
                  stage="after_native"),
    )
    if source_changes:
        outcome = "unexpected-source-mutation"

    absolute_paths = (*context.guides, *context.tool_roots, context.source_inventory_tool)
    return JourneyResult(
        outcome=outcome, guide_hashes=guide_hashes, tool_hashes=tool_hashes,
        source_digests=source_digests, source_changes=source_changes,
        observation=observation, native_results=tuple(native_results),
        artifact_hashes=artifact_hashes,
        artifact_events=_artifact_events(artifact_hashes),
        absolute_closure_paths=tuple(dict.fromkeys(absolute_paths)),
        failure=failure,
    )
