#!/usr/bin/env python3
"""Render one accepted, read-only C folder plan and prove it disposably."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "c-folder-reorganization-proposal-v1"
ACCEPTANCE_SCHEMA = "c-structure-accepted-evidence-v1"
CONVENTION = "group-three-prefix-translation-units"
NONCLAIMS = [
    "the accepted direct-sibling cluster is not a general C folder convention",
    "filename and compiler-dependency evidence does not prove conceptual ownership",
    "function-pointer, callback, alias, dynamic, and alternate-build consumers remain unresolved",
    "ABI, object layout, linkage compatibility, undefined behavior, and external consumers remain unresolved",
    "the artifact is read-only and grants no source-mutation authority",
]


class ProposalError(RuntimeError):
    """A typed refusal local to the C folder consumer."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contained(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProposalError("failed", "invalid_selection", f"{label} is missing")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ProposalError("failed", "invalid_selection", f"{label} is unsafe")
    return value


def _safe_output(root: Path, supplied: Path) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(raw))
    allowed = root / "reports/propose-folder-reorganization"
    if output == allowed or not _contained(allowed, output):
        raise ProposalError(
            "failed",
            "unsafe_output_path",
            "artifacts must stay beneath reports/propose-folder-reorganization/",
        )
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ProposalError(
                "failed", "unsafe_output_path", "artifact path traverses a symbolic link"
            )
    return output


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is not an object")
    return payload


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _replace_bundle(output: Path, payload: dict[str, Any], rendered: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    staged.mkdir()
    try:
        _atomic(staged / "inspection.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _atomic(staged / "proposal.md", rendered)
        if output.exists():
            output.replace(backup)
        try:
            staged.replace(output)
        except OSError:
            if backup.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def _audited_files(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".git", "reports", ".native-build"} for part in relative.parts):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix in {".c", ".i", ".h", ".inc"} or path.name == "Makefile":
            rows[relative.as_posix()] = _sha256(path)
    return rows


def _validate_source_hashes(root: Path, acceptance: dict[str, Any]) -> None:
    rows = acceptance.get("source_hashes")
    if not isinstance(rows, list) or not rows:
        raise ProposalError("failed", "invalid_accepted_evidence", "source hashes are missing")
    accepted: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ProposalError("failed", "invalid_accepted_evidence", "source hash row is invalid")
        path = _safe_relative(row.get("path"), "accepted source path")
        digest = row.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or path in accepted:
            raise ProposalError("failed", "invalid_accepted_evidence", "source hash is invalid")
        accepted[path] = digest
    if _audited_files(root) != accepted:
        raise ProposalError(
            "failed",
            "stale_accepted_source",
            "current C/header/Make bytes differ from the accepted source census",
        )


def _artifact_hashes(
    root: Path, acceptance: dict[str, Any], supplied: dict[str, Path]
) -> dict[str, str]:
    rows = acceptance.get("artifacts")
    if not isinstance(rows, list):
        raise ProposalError("failed", "invalid_accepted_evidence", "artifact hashes are missing")
    accepted = {
        row.get("kind"): row for row in rows if isinstance(row, dict) and row.get("kind")
    }
    if set(accepted) != set(supplied):
        raise ProposalError("failed", "invalid_accepted_evidence", "accepted artifact set changed")
    result = {}
    for kind, path in supplied.items():
        row = accepted[kind]
        relative = _safe_relative(row.get("path"), f"{kind} artifact path")
        if (root / relative).resolve() != path.resolve() or not _contained(root, path.resolve()):
            raise ProposalError("failed", "invalid_accepted_evidence", f"{kind} artifact path changed")
        digest = _sha256(path)
        if row.get("sha256") != digest:
            raise ProposalError("failed", "stale_accepted_evidence", f"{kind} artifact hash changed")
        result[kind] = digest
    return result


def _validate_inputs(
    root: Path,
    acceptance_path: Path,
    topology_path: Path,
    map_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    acceptance = _read_object(acceptance_path, "acceptance")
    supplied_hash = acceptance.get("acceptance_hash")
    unhashed = dict(acceptance)
    unhashed.pop("acceptance_hash", None)
    if supplied_hash != _canonical_hash(unhashed):
        raise ProposalError("failed", "invalid_accepted_evidence", "acceptance hash does not verify")
    if (
        acceptance.get("schema_version") != ACCEPTANCE_SCHEMA
        or acceptance.get("consumer") != "propose-folder-reorganization"
    ):
        raise ProposalError("failed", "invalid_accepted_evidence", "acceptance contract is wrong")
    verdict = acceptance.get("human_verdict")
    if not isinstance(verdict, dict) or verdict.get("status") != "accepted":
        raise ProposalError("failed", "human_acceptance_required", "human verdict is not accepted")
    boundaries = verdict.get("reviewed_boundaries")
    if not isinstance(boundaries, list) or len(boundaries) < 3:
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "required C uncertainty review is missing"
        )
    hashes = _artifact_hashes(
        root,
        acceptance,
        {"lexical-topology": topology_path, "c-map": map_path},
    )
    _validate_source_hashes(root, acceptance)
    topology = _read_object(topology_path, "C topology artifact")
    map_evidence = _read_object(map_path, "C map artifact")
    if topology.get("status") != "complete" or topology.get("outcome") != "drift-found":
        raise ProposalError("partial", "upstream_not_complete", "topology evidence is incomplete")
    if (
        map_evidence.get("status") != "complete"
        or map_evidence.get("language") != "c"
        or map_evidence.get("compile_database", {}).get("state")
        != "valid-current-complete-c-mode"
        or map_evidence.get("source_fingerprints", {}).get("unchanged") is not True
    ):
        raise ProposalError("partial", "upstream_not_complete", "C map evidence is incomplete")
    for key in (
        "compile_database",
        "translation_unit_inventory",
        "dependency_inventory",
        "declarations_and_public_surface",
        "cross_translation_unit_edges",
    ):
        if map_evidence.get("completeness", {}).get(key) != "complete":
            raise ProposalError("partial", "upstream_not_complete", "C map completeness changed")
    return acceptance, topology, map_evidence, hashes


def _selected_finding(topology: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in topology.get("findings", [])
        if isinstance(row, dict)
        and row.get("evidence_sha256") == selection.get("finding_evidence_sha256")
    ]
    if len(matches) != 1:
        raise ProposalError("failed", "invalid_selection", "accepted topology finding changed")
    finding = matches[0]
    if (
        finding.get("pattern") != "flat_prefix_cluster"
        or finding.get("language") != "c"
        or finding.get("file") != selection.get("parent")
        or finding.get("prefix") != selection.get("prefix")
        or finding.get("files") != selection.get("files")
        or finding.get("count", 0) < 3
    ):
        raise ProposalError("failed", "invalid_selection", "accepted C cluster lineage changed")
    return finding


def _validated_plan(
    root: Path,
    selection: dict[str, Any],
    finding: dict[str, Any],
    map_evidence: dict[str, Any],
) -> dict[str, Any]:
    parent = _safe_relative(selection.get("parent"), "cluster parent")
    prefix = selection.get("prefix")
    files = selection.get("files")
    if selection.get("project_convention") != CONVENTION:
        raise ProposalError("failed", "project_convention_required", "project convention changed")
    if not isinstance(prefix, str) or not isinstance(files, list) or files != finding["files"]:
        raise ProposalError("failed", "invalid_selection", "cluster members changed")
    map_units = set(map_evidence.get("translation_units", []))
    if not set(files).issubset(map_units):
        raise ProposalError("failed", "invalid_selection", "cluster lacks compile-database authority")
    moves = selection.get("exact_moves")
    if not isinstance(moves, list) or len(moves) < len(files):
        raise ProposalError("failed", "invalid_selection", "exact move plan is incomplete")
    normalized_moves: list[dict[str, str]] = []
    destinations: set[str] = set()
    for row in moves:
        source = _safe_relative(row.get("from"), "move source")
        destination = _safe_relative(row.get("to"), "move destination")
        if not (root / source).is_file() or (root / destination).exists():
            raise ProposalError("failed", "stale_accepted_source", f"move no longer applies: {source}")
        destination_parent = Path(destination).parent.as_posix()
        if destination_parent != f"{parent}/{prefix}" or destination in destinations:
            raise ProposalError("failed", "invalid_selection", "move destination is outside cluster folder")
        destinations.add(destination)
        normalized_moves.append({"from": source, "to": destination})
    cluster_moves = [row for row in normalized_moves if row["from"] in files]
    if {row["from"] for row in cluster_moves} != set(files):
        raise ProposalError("failed", "invalid_selection", "not every cluster member is moved once")
    for row in cluster_moves:
        source = Path(row["from"])
        suffix = source.stem.removeprefix(f"{prefix}_")
        if row["to"] != f"{parent}/{prefix}/{suffix}{source.suffix}":
            raise ProposalError("failed", "invalid_selection", "cluster destination spelling changed")
    auxiliary = [row for row in normalized_moves if row["from"] not in files]
    owned_headers = set(map_evidence.get("owned_headers", []))
    if any(
        row["from"] not in owned_headers
        or Path(row["from"]).parent.as_posix() != parent
        or Path(row["from"]).suffix not in {".h", ".inc"}
        for row in auxiliary
    ):
        raise ProposalError("failed", "invalid_selection", "auxiliary move lacks header ownership")
    edits = selection.get("exact_edits")
    if not isinstance(edits, list) or not edits:
        raise ProposalError("failed", "invalid_selection", "exact edits are missing")
    normalized_edits: list[dict[str, Any]] = []
    moved_destinations = {row["to"] for row in normalized_moves}
    for row in edits:
        path = _safe_relative(row.get("path"), "edit path")
        before, after, count = row.get("before"), row.get("after"), row.get("expected_occurrences")
        if not isinstance(before, str) or not before or not isinstance(after, str) or not isinstance(count, int) or count < 1:
            raise ProposalError("failed", "invalid_selection", f"edit is malformed: {path}")
        if not (root / path).is_file() and path not in moved_destinations:
            raise ProposalError("failed", "invalid_selection", f"edit path is unavailable: {path}")
        normalized_edits.append(
            {"path": path, "before": before, "after": after, "expected_occurrences": count}
        )
    include_impact = selection.get("include_impact")
    make_impact = selection.get("make_impact")
    if not isinstance(include_impact, list) or not include_impact:
        raise ProposalError("failed", "invalid_selection", "include impact is incomplete")
    if not isinstance(make_impact, list) or not make_impact:
        raise ProposalError("failed", "invalid_selection", "Make impact is incomplete")
    edit_pairs = {(row["path"], row["before"], row["after"]) for row in normalized_edits}
    for row in (*include_impact, *make_impact):
        if (row.get("path"), row.get("before"), row.get("after")) not in edit_pairs:
            raise ProposalError("failed", "invalid_selection", "impact row lacks an exact edit")
    callers = selection.get("caller_impact")
    if not isinstance(callers, list) or not callers:
        raise ProposalError("failed", "invalid_selection", "caller impact is missing")
    for row in callers:
        path = _safe_relative(row.get("path"), "caller path")
        if not (root / path).is_file() or not isinstance(row.get("impact"), str):
            raise ProposalError("failed", "invalid_selection", "caller impact is invalid")
    expected_after = selection.get("expected_translation_units_after")
    if not isinstance(expected_after, list) or expected_after != sorted(set(expected_after)):
        raise ProposalError("failed", "invalid_selection", "after-tree TU census is invalid")
    if {row["to"] for row in cluster_moves} - set(expected_after):
        raise ProposalError("failed", "invalid_selection", "moved TUs are absent from after census")
    return {
        "parent": parent,
        "prefix": prefix,
        "project_convention": CONVENTION,
        "current_tree": files,
        "proposed_tree": [row["to"] for row in cluster_moves],
        "exact_moves": normalized_moves,
        "exact_edits": normalized_edits,
        "include_impact": include_impact,
        "make_impact": make_impact,
        "caller_impact": callers,
        "expected_translation_units_after": expected_after,
        "test_surface": selection.get("test_surface", []),
        "accounting": {
            "cluster_members": len(files),
            "planned_cluster_members": len(cluster_moves),
            "auxiliary_owned_headers": len(auxiliary),
        },
    }


def _native_commands(
    root: Path, acceptance: dict[str, Any], make: str, clang: str
) -> list[dict[str, Any]]:
    rows = acceptance.get("native_obligations")
    if not isinstance(rows, list) or {row.get("name") for row in rows} != {
        "compile-database",
        "native-test",
        "smoke",
    }:
        raise ProposalError("failed", "invalid_native_obligations", "exact C matrix is required")
    commands = []
    for row in rows:
        name, raw = row.get("name"), row.get("argv")
        if row.get("expected_returncode") != 0 or not isinstance(raw, list):
            raise ProposalError("failed", "invalid_native_obligations", "native row is malformed")
        if name == "compile-database":
            if raw != ["make", "clean", "compile-db", "CC=clang"]:
                raise ProposalError("failed", "invalid_native_obligations", "compile-db row changed")
            argv = [make, "clean", "compile-db", f"CC={clang}"]
        elif name == "native-test":
            if raw != ["make", "test", "CC=clang"]:
                raise ProposalError("failed", "invalid_native_obligations", "test row changed")
            argv = [make, "test", f"CC={clang}"]
        else:
            if len(raw) != 1:
                raise ProposalError("failed", "invalid_native_obligations", "smoke row changed")
            argv = [str(root / _safe_relative(raw[0], "smoke executable"))]
        commands.append({**row, "resolved_argv": argv})
    return commands


def _database_units(root: Path) -> list[str]:
    try:
        payload = json.loads((root / "compile_commands.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalError(
            "failed", "native_verification_failed", f"regenerated compile database: {exc}"
        ) from exc
    if not isinstance(payload, list) or not payload:
        raise ProposalError("failed", "native_verification_failed", "compile database is empty")
    canonical_root = root.resolve()
    rows = []
    for row in payload:
        try:
            raw = Path(row["file"])
            absolute = raw if raw.is_absolute() else root / raw
            rows.append(absolute.resolve().relative_to(canonical_root).as_posix())
        except (KeyError, TypeError, ValueError) as exc:
            raise ProposalError(
                "failed", "native_verification_failed", "compile database path is foreign"
            ) from exc
    return sorted(rows)


def _run_native(
    root: Path,
    acceptance: dict[str, Any],
    make: str,
    clang: str,
    expected_units: list[str],
) -> dict[str, Any]:
    results = []
    for command in _native_commands(root, acceptance, make, clang):
        try:
            completed = subprocess.run(
                command["resolved_argv"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProposalError(
                "failed", "native_verification_failed", f"{command['name']}: {exc}"
            ) from exc
        if completed.returncode != command["expected_returncode"]:
            raise ProposalError(
                "failed",
                "native_verification_failed",
                f"{command['name']} exited {completed.returncode}: {completed.stderr.strip()}",
            )
        expected_stdout = command.get("expected_stdout")
        contains = command.get("expected_stdout_contains")
        if expected_stdout is not None and completed.stdout != expected_stdout:
            raise ProposalError(
                "failed", "native_verification_failed", f"{command['name']} stdout changed"
            )
        if contains is not None and contains not in completed.stdout:
            raise ProposalError(
                "failed", "native_verification_failed", f"{command['name']} output is incomplete"
            )
        results.append(
            {
                "name": command["name"],
                "argv": command["argv"],
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
    units = _database_units(root)
    if units != expected_units:
        raise ProposalError(
            "failed", "native_verification_failed", "regenerated compile-database TU census changed"
        )
    return {
        "status": "passed",
        "commands": results,
        "compile_database_regenerated": True,
        "compile_database_translation_units": units,
    }


def _apply_plan(root: Path, plan: dict[str, Any]) -> None:
    for row in plan["exact_moves"]:
        source, destination = root / row["from"], root / row["to"]
        if not source.is_file() or destination.exists():
            raise ProposalError("failed", "disposable_plan_mismatch", f"move changed: {row['from']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    for row in plan["exact_edits"]:
        path = root / row["path"]
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ProposalError("failed", "disposable_plan_mismatch", f"edit {row['path']}: {exc}") from exc
        if text.count(row["before"]) != row["expected_occurrences"]:
            raise ProposalError("failed", "disposable_plan_mismatch", f"edit changed: {row['path']}")
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")


def _disposable_native(
    root: Path,
    acceptance: dict[str, Any],
    plan: dict[str, Any],
    make: str,
    clang: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c-folder-after-") as temporary:
        disposable = Path(temporary) / "host"
        shutil.copytree(
            root,
            disposable,
            ignore=shutil.ignore_patterns(".git", "reports", ".native-build"),
        )
        _apply_plan(disposable, plan)
        result = _run_native(
            disposable,
            acceptance,
            make,
            clang,
            plan["expected_translation_units_after"],
        )
        result["disposable"] = True
        result["after_tree"] = plan["proposed_tree"]
        return result


def _base_payload(
    status: str,
    outcome: str,
    recommendation: str,
    acceptance: dict[str, Any],
    hashes: dict[str, str],
    current_native: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-folder-reorganization",
        "language": "c",
        "status": status,
        "outcome": outcome,
        "recommendation": recommendation,
        "read_only": True,
        "source_mutations": 0,
        "accepted_evidence": {
            "acceptance_hash": acceptance["acceptance_hash"],
            "artifact_hashes": hashes,
        },
        "native_verification": {"current_tree": current_native},
        "nonclaims": NONCLAIMS,
    }


def _build(
    root: Path,
    topology_path: Path,
    map_path: Path,
    acceptance_path: Path,
    make: str,
    clang: str,
    before: dict[str, str],
) -> dict[str, Any]:
    acceptance, topology, map_evidence, hashes = _validate_inputs(
        root, acceptance_path, topology_path, map_path
    )
    selection = acceptance.get("selection")
    if not isinstance(selection, dict):
        raise ProposalError("failed", "invalid_selection", "accepted selection is missing")
    finding = _selected_finding(topology, selection)
    current_native = _run_native(
        root, acceptance, make, clang, sorted(map_evidence["translation_units"])
    )
    if _audited_files(root) != before:
        raise ProposalError(
            "failed", "source_mutation_detected", "current-tree native verification changed source"
        )
    decision = acceptance.get("decision")
    if decision in {"keep_flat", "defer_no_convention"}:
        recommendation = (
            "keep_flat" if decision == "keep_flat" else "defer_project_convention_required"
        )
        payload = _base_payload(
            "complete", "safely_deferred", recommendation, acceptance, hashes, current_native
        )
        payload.update(
            parent=selection.get("parent"),
            prefix=selection.get("prefix"),
            message=(
                "Human review chose to keep this C cluster flat."
                if decision == "keep_flat"
                else "No explicit C project convention authorizes a folder plan."
            ),
            source_preservation={"verified": True, "source_manifest": _canonical_hash(before)},
        )
        return payload
    if decision != "reorganize":
        raise ProposalError("failed", "human_acceptance_required", "folder decision is unsupported")
    plan = _validated_plan(root, selection, finding, map_evidence)
    disposable = _disposable_native(root, acceptance, plan, make, clang)
    if _audited_files(root) != before:
        raise ProposalError(
            "failed", "source_mutation_detected", "disposable verification changed audited source"
        )
    payload = _base_payload(
        "ready_for_human_review",
        "folder_plan_ready",
        "review_folder_plan",
        acceptance,
        hashes,
        current_native,
    )
    payload.update(
        message="One accepted C prefix cluster has an exact, natively verified folder plan.",
        finding_evidence_sha256=finding["evidence_sha256"],
        map_snapshot={
            "analyzer": map_evidence["analyzer"],
            "compile_database": map_evidence["compile_database"],
            "owned_headers": map_evidence["owned_headers"],
        },
        **plan,
        native_verification={
            "current_tree": current_native,
            "disposable_after_tree": disposable,
        },
        source_preservation={"verified": True, "source_manifest": _canonical_hash(before)},
    )
    return payload


def _render(payload: dict[str, Any]) -> str:
    if payload.get("outcome") == "refused":
        return (
            "# C folder reorganization proposal — refused\n\n"
            f"Status: `{payload['status']}`. `{payload['failure_kind']}`: {payload['message']}\n"
        )
    if payload["outcome"] == "safely_deferred":
        return (
            "# C folder reorganization proposal\n\n"
            f"Status: `complete`. {payload['message']} No file move or source edit is proposed.\n"
        )
    lines = [
        f"# C folder reorganization proposal — {payload['parent']}::{payload['prefix']}",
        "",
        "Status: `ready_for_human_review`; this artifact moves no files.",
        "",
        "## Accepted project convention",
        "",
        f"`{payload['project_convention']}` applies to this human-reviewed cluster only.",
        "",
        "## Current → proposed tree",
        "",
    ]
    lines.extend(f"- `{row['from']}` → `{row['to']}`" for row in payload["exact_moves"])
    lines.extend(["", "## Include impact", ""])
    lines.extend(
        f"- `{row['path']}`: `{row['before']}` → `{row['after']}`"
        for row in payload["include_impact"]
    )
    lines.extend(["", "## Make and compile-database regeneration", ""])
    lines.extend(
        f"- `{row['path']}`: `{row['before']}` → `{row['after']}`"
        for row in payload["make_impact"]
    )
    lines.append(
        "- Regenerated translation units: "
        + ", ".join(f"`{path}`" for path in payload["expected_translation_units_after"])
        + "."
    )
    lines.extend(["", "## Caller impact", ""])
    lines.extend(f"- `{row['path']}`: {row['impact']}" for row in payload["caller_impact"])
    lines.extend(["", "## Disposable after-tree proof", ""])
    lines.append("- Compile-database regeneration, Make test, and smoke passed in a temporary copy.")
    lines.extend(["", "## Explicit non-claims", ""])
    lines.extend(f"- {item}" for item in payload["nonclaims"])
    return "\n".join(lines).rstrip() + "\n"


def _refusal(error: ProposalError) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-folder-reorganization",
        "language": "c",
        "status": error.status,
        "outcome": "refused",
        "recommendation": "defer_invalid_or_stale_evidence",
        "failure_kind": error.failure_kind,
        "message": error.detail,
        "read_only": True,
        "source_mutations": 0,
        "nonclaims": NONCLAIMS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--map-evidence", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--make", required=True)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output: Path | None = None
    try:
        output = _safe_output(root, args.output_dir)
        before = _audited_files(root)
        payload = _build(
            root,
            args.topology.resolve(),
            args.map_evidence.resolve(),
            args.acceptance.resolve(),
            args.make,
            args.clang,
            before,
        )
        _replace_bundle(output, payload, _render(payload))
        return 0
    except ProposalError as exc:
        if output is not None:
            payload = _refusal(exc)
            _replace_bundle(output, payload, _render(payload))
        print(
            f"propose-folder-reorganization C: {exc.failure_kind}: {exc.detail}",
            file=sys.stderr,
        )
        return 2
    except (OSError, UnicodeError, TypeError, ValueError, KeyError) as exc:
        error = ProposalError("failed", "proposal_failed", str(exc))
        if output is not None:
            payload = _refusal(error)
            _replace_bundle(output, payload, _render(payload))
        print(f"propose-folder-reorganization C: proposal_failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
