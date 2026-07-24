#!/usr/bin/env python3
"""Render one accepted, read-only C boundary plan and prove it disposably."""

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


SCHEMA_VERSION = "c-boundary-proposal-v1"
ACCEPTANCE_SCHEMA = "c-structure-accepted-evidence-v1"
NONCLAIMS = [
    "direct source spelling does not resolve function-pointer, callback, alias, or runtime call targets",
    "the selected C17 compile-command snapshot does not cover alternate build variants",
    "ABI, object layout, linkage compatibility, undefined behavior, and external consumers remain unresolved",
    "the legacy header plan is not public or semver compatibility certainty",
    "the artifact is read-only and grants no source-mutation authority",
]


class ProposalError(RuntimeError):
    """A typed refusal local to the C proposal consumer."""

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
    allowed = root / "reports/propose-boundary"
    if output == allowed or not _contained(allowed, output):
        raise ProposalError(
            "failed",
            "unsafe_output_path",
            "artifacts must stay beneath reports/propose-boundary/",
        )
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ProposalError(
                "failed", "unsafe_output_path", "artifact path traverses a symbolic link"
            )
    return output


def _read_json(path: Path, label: str) -> dict[str, Any]:
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


def _validate_source_hashes(root: Path, acceptance: dict[str, Any]) -> dict[str, str]:
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
    current = _audited_files(root)
    if current != accepted:
        raise ProposalError(
            "failed",
            "stale_accepted_source",
            "current C/header/Make bytes differ from the accepted source census",
        )
    return current


def _artifact_index(
    root: Path, acceptance: dict[str, Any], supplied: dict[str, Path]
) -> dict[str, str]:
    rows = acceptance.get("artifacts")
    if not isinstance(rows, list):
        raise ProposalError("failed", "invalid_accepted_evidence", "artifact hashes are missing")
    accepted: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("kind"), str):
            raise ProposalError("failed", "invalid_accepted_evidence", "artifact row is invalid")
        accepted[row["kind"]] = row
    if set(accepted) != set(supplied):
        raise ProposalError("failed", "invalid_accepted_evidence", "accepted artifact set changed")
    hashes: dict[str, str] = {}
    for kind, path in supplied.items():
        row = accepted[kind]
        relative = _safe_relative(row.get("path"), f"{kind} artifact path")
        expected_path = (root / relative).resolve()
        if expected_path != path.resolve() or not _contained(root, expected_path):
            raise ProposalError("failed", "invalid_accepted_evidence", f"{kind} artifact path changed")
        digest = _sha256(path)
        if row.get("sha256") != digest:
            raise ProposalError("failed", "stale_accepted_evidence", f"{kind} artifact hash changed")
        hashes[kind] = digest
    return hashes


def _validate_acceptance(
    root: Path,
    path: Path,
    omnibus_path: Path,
    map_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    acceptance = _read_json(path, "acceptance")
    supplied_hash = acceptance.get("acceptance_hash")
    unhashed = dict(acceptance)
    unhashed.pop("acceptance_hash", None)
    if supplied_hash != _canonical_hash(unhashed):
        raise ProposalError("failed", "invalid_accepted_evidence", "acceptance hash does not verify")
    if (
        acceptance.get("schema_version") != ACCEPTANCE_SCHEMA
        or acceptance.get("consumer") != "propose-boundary"
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
    artifact_hashes = _artifact_index(
        root,
        acceptance,
        {"confirmed-omnibus": omnibus_path, "c-map": map_path},
    )
    _validate_source_hashes(root, acceptance)
    omnibus = _read_json(omnibus_path, "confirmed omnibus artifact")
    map_evidence = _read_json(map_path, "C map artifact")
    if omnibus.get("status") != "complete" or omnibus.get("failure_kind") not in {
        "none",
        None,
    }:
        raise ProposalError("partial", "upstream_not_complete", "omnibus evidence is incomplete")
    if (
        map_evidence.get("status") != "complete"
        or map_evidence.get("language") != "c"
        or map_evidence.get("compile_database", {}).get("state")
        != "valid-current-complete-c-mode"
        or map_evidence.get("source_fingerprints", {}).get("unchanged") is not True
    ):
        raise ProposalError("partial", "upstream_not_complete", "C map evidence is incomplete")
    expected_completeness = {
        "compile_database",
        "translation_unit_inventory",
        "dependency_inventory",
        "declarations_and_public_surface",
        "cross_translation_unit_edges",
    }
    completeness = map_evidence.get("completeness", {})
    if any(completeness.get(key) != "complete" for key in expected_completeness):
        raise ProposalError("partial", "upstream_not_complete", "C map completeness changed")
    return acceptance, omnibus, map_evidence, artifact_hashes


def _selection(acceptance: dict[str, Any]) -> dict[str, Any]:
    selection = acceptance.get("selection")
    if not isinstance(selection, dict):
        raise ProposalError("failed", "invalid_selection", "accepted selection is missing")
    return selection


def _candidate(omnibus: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in omnibus.get("findings", [])
        if isinstance(row, dict) and row.get("candidate_id") == selection.get("candidate_id")
    ]
    if len(matches) != 1:
        raise ProposalError("failed", "invalid_selection", "accepted omnibus candidate changed")
    candidate = matches[0]
    if (
        candidate.get("bucket") != "confirmed_omnibus"
        or candidate.get("scout_verdict") != "explicit"
        or candidate.get("file") != selection.get("target")
    ):
        raise ProposalError("failed", "invalid_selection", "candidate lacks confirmed scout authority")
    return candidate


def _validated_plan(
    root: Path,
    selection: dict[str, Any],
    candidate: dict[str, Any],
    map_evidence: dict[str, Any],
) -> dict[str, Any]:
    target = _safe_relative(selection.get("target"), "target translation unit")
    public_header = _safe_relative(selection.get("public_header"), "public header")
    new_header = _safe_relative(selection.get("new_public_header"), "new public header")
    new_unit = _safe_relative(selection.get("new_translation_unit"), "new translation unit")
    domain = selection.get("domain")
    declarations = selection.get("declarations")
    clusters = candidate.get("clusters", {})
    if (
        not isinstance(domain, str)
        or not isinstance(declarations, list)
        or len(declarations) < 2
        or declarations != clusters.get(domain)
        or len(set(declarations)) != len(declarations)
    ):
        raise ProposalError("failed", "invalid_selection", "accepted domain declarations changed")
    if target not in map_evidence.get("translation_units", []):
        raise ProposalError("failed", "invalid_selection", "target lacks compile-database authority")
    if public_header not in map_evidence.get("owned_headers", []):
        raise ProposalError("failed", "invalid_selection", "public header is not compiler-owned")
    facts = map_evidence.get("declarations", [])
    for name in declarations:
        definitions = [
            row
            for row in facts
            if row.get("name") == name
            and row.get("file") == target
            and row.get("kind") == "function"
            and row.get("definition") is True
        ]
        header_rows = [
            row
            for row in facts
            if row.get("name") == name
            and row.get("file") == public_header
            and row.get("kind") == "function"
            and row.get("definition") is False
        ]
        if len(definitions) != 1 or len(header_rows) != 1:
            raise ProposalError(
                "failed", "invalid_selection", f"{name} lacks exact definition/header lineage"
            )
    caller_impact = selection.get("caller_impact")
    if not isinstance(caller_impact, list) or not caller_impact:
        raise ProposalError("failed", "invalid_selection", "caller impact is missing")
    for row in caller_impact:
        path = _safe_relative(row.get("path"), "caller path")
        symbol = row.get("symbol")
        if symbol not in declarations or not isinstance(row.get("impact"), str):
            raise ProposalError("failed", "invalid_selection", "caller impact is invalid")
        try:
            text = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ProposalError("failed", "stale_accepted_source", f"caller {path}: {exc}") from exc
        if symbol not in text:
            raise ProposalError("failed", "stale_accepted_source", f"caller spelling changed: {path}")
    exact_edits = selection.get("exact_edits")
    creates = selection.get("create_files")
    if not isinstance(exact_edits, list) or not exact_edits or not isinstance(creates, list):
        raise ProposalError("failed", "invalid_selection", "exact seam edits are missing")
    normalized_edits: list[dict[str, Any]] = []
    for row in exact_edits:
        path = _safe_relative(row.get("path"), "edit path")
        before, after, count = row.get("before"), row.get("after"), row.get("expected_occurrences")
        if not isinstance(before, str) or not before or not isinstance(after, str) or not isinstance(count, int) or count < 1:
            raise ProposalError("failed", "invalid_selection", f"edit is malformed: {path}")
        try:
            current = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ProposalError("failed", "stale_accepted_source", f"edit {path}: {exc}") from exc
        if current.count(before) != count:
            raise ProposalError("failed", "stale_accepted_source", f"edit no longer applies: {path}")
        normalized_edits.append(
            {"path": path, "before": before, "after": after, "expected_occurrences": count}
        )
    normalized_creates: list[dict[str, str]] = []
    for row in creates:
        path = _safe_relative(row.get("path"), "create path")
        contents = row.get("contents")
        if not isinstance(contents, str) or not contents or (root / path).exists():
            raise ProposalError("failed", "invalid_selection", f"create is invalid: {path}")
        normalized_creates.append({"path": path, "contents": contents})
    if {row["path"] for row in normalized_creates} != {new_header, new_unit}:
        raise ProposalError("failed", "invalid_selection", "created C/header seam paths changed")
    include_impact = selection.get("include_impact")
    make_impact = selection.get("make_impact")
    if not isinstance(include_impact, list) or len(include_impact) < 2:
        raise ProposalError("failed", "invalid_selection", "include impact is incomplete")
    if not isinstance(make_impact, list) or not make_impact:
        raise ProposalError("failed", "invalid_selection", "Make impact is incomplete")
    edit_pairs = {(row["path"], row["before"], row["after"]) for row in normalized_edits}
    for row in make_impact:
        if (row.get("path"), row.get("before"), row.get("after")) not in edit_pairs:
            raise ProposalError("failed", "invalid_selection", "Make impact lacks an exact edit")
    expected_after = selection.get("expected_translation_units_after")
    if (
        not isinstance(expected_after, list)
        or expected_after != sorted(set(expected_after))
        or new_unit not in expected_after
    ):
        raise ProposalError("failed", "invalid_selection", "after-tree TU census is invalid")
    return {
        "target": target,
        "domain": domain,
        "declarations": declarations,
        "public_header": public_header,
        "new_public_header": new_header,
        "new_translation_unit": new_unit,
        "caller_impact": caller_impact,
        "include_impact": include_impact,
        "make_impact": make_impact,
        "exact_edits": normalized_edits,
        "create_files": normalized_creates,
        "expected_translation_units_after": expected_after,
        "test_surface": selection.get("test_surface", []),
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
    commands: list[dict[str, Any]] = []
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
            smoke = _safe_relative(raw[0], "smoke executable")
            argv = [str(root / smoke)]
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
    rows = []
    canonical_root = root.resolve()
    for row in payload:
        try:
            raw_path = Path(row["file"])
            absolute = raw_path if raw_path.is_absolute() else root / raw_path
            path = absolute.resolve().relative_to(canonical_root).as_posix()
        except (KeyError, TypeError, ValueError) as exc:
            raise ProposalError(
                "failed",
                "native_verification_failed",
                f"compile database path is foreign to {root}: {row!r}",
            ) from exc
        rows.append(path)
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
    for row in plan["exact_edits"]:
        path = root / row["path"]
        text = path.read_text(encoding="utf-8")
        if text.count(row["before"]) != row["expected_occurrences"]:
            raise ProposalError("failed", "disposable_plan_mismatch", f"edit changed: {row['path']}")
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")
    for row in plan["create_files"]:
        path = root / row["path"]
        if path.exists():
            raise ProposalError("failed", "disposable_plan_mismatch", f"create exists: {row['path']}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["contents"], encoding="utf-8")


def _disposable_native(
    root: Path,
    acceptance: dict[str, Any],
    plan: dict[str, Any],
    make: str,
    clang: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c-boundary-after-") as temporary:
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
        return result


def _base_payload(
    *,
    status: str,
    outcome: str,
    recommendation: str,
    acceptance: dict[str, Any],
    artifact_hashes: dict[str, str],
    current_native: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-boundary",
        "language": "c",
        "status": status,
        "outcome": outcome,
        "recommendation": recommendation,
        "read_only": True,
        "source_mutations": 0,
        "accepted_evidence": {
            "acceptance_hash": acceptance["acceptance_hash"],
            "artifact_hashes": artifact_hashes,
        },
        "native_verification": {"current_tree": current_native},
        "nonclaims": NONCLAIMS,
    }


def _build(
    root: Path,
    omnibus_path: Path,
    map_path: Path,
    acceptance_path: Path,
    make: str,
    clang: str,
    before: dict[str, str],
) -> dict[str, Any]:
    acceptance, omnibus, map_evidence, artifact_hashes = _validate_acceptance(
        root, acceptance_path, omnibus_path, map_path
    )
    selection = _selection(acceptance)
    candidate = _candidate(omnibus, selection)
    current_native = _run_native(
        root,
        acceptance,
        make,
        clang,
        sorted(map_evidence["translation_units"]),
    )
    if _audited_files(root) != before:
        raise ProposalError(
            "failed", "source_mutation_detected", "current-tree native verification changed source"
        )
    decision = acceptance.get("decision")
    if decision == "keep_cohesive":
        payload = _base_payload(
            status="complete",
            outcome="safely_deferred",
            recommendation="defer_cohesive_target",
            acceptance=acceptance,
            artifact_hashes=artifact_hashes,
            current_native=current_native,
        )
        payload.update(
            target=selection.get("target"),
            candidate_id=candidate["candidate_id"],
            message="Human review judged the confirmed C target cohesive; no seam plan was emitted.",
            source_preservation={"verified": True, "source_manifest": _canonical_hash(before)},
        )
        return payload
    if decision != "extract_boundary":
        raise ProposalError("failed", "human_acceptance_required", "boundary decision is unsupported")
    plan = _validated_plan(root, selection, candidate, map_evidence)
    disposable = _disposable_native(root, acceptance, plan, make, clang)
    if _audited_files(root) != before:
        raise ProposalError(
            "failed", "source_mutation_detected", "disposable verification changed audited source"
        )
    payload = _base_payload(
        status="ready_for_human_review",
        outcome="boundary_plan_ready",
        recommendation="review_boundary",
        acceptance=acceptance,
        artifact_hashes=artifact_hashes,
        current_native=current_native,
    )
    payload.update(
        message="One accepted C domain has an exact, natively verified .c/.h seam plan.",
        candidate_id=candidate["candidate_id"],
        scout_verdict="explicit",
        map_snapshot={
            "analyzer": map_evidence["analyzer"],
            "compile_database": map_evidence["compile_database"],
            "function_pointer_call_resolution": map_evidence["completeness"].get(
                "function_pointer_call_resolution"
            ),
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
            "# C boundary proposal — refused\n\n"
            f"Status: `{payload['status']}`. `{payload['failure_kind']}`: {payload['message']}\n"
        )
    if payload["outcome"] == "safely_deferred":
        return (
            "# C boundary proposal\n\n"
            "Status: `complete`. The accepted human judgment keeps this confirmed target cohesive. "
            "No extraction or source edit is proposed.\n"
        )
    lines = [
        f"# C boundary proposal — {payload['target']}::{payload['domain']}",
        "",
        "Status: `ready_for_human_review`; this artifact is read-only.",
        "",
        "## Accepted C seam",
        "",
        f"Extract `{payload['domain']}` from `{payload['target']}` into "
        f"`{payload['new_translation_unit']}` and `{payload['new_public_header']}`.",
        "",
        "## Declarations and public header",
        "",
    ]
    lines.extend(f"- `{name}`" for name in payload["declarations"])
    lines.extend(["", "## Caller impact", ""])
    lines.extend(
        f"- `{row['path']}` — `{row['symbol']}`: {row['impact']}"
        for row in payload["caller_impact"]
    )
    lines.extend(["", "## Include impact", ""])
    lines.extend(
        f"- `{row['path']}`: `{row.get('before', '(new file)')}` → `{row['after']}`"
        for row in payload["include_impact"]
    )
    lines.extend(["", "## Make and compile-database impact", ""])
    lines.extend(
        f"- `{row['path']}`: `{row['before']}` → `{row['after']}`"
        for row in payload["make_impact"]
    )
    lines.append(
        "- Regenerate `compile_commands.json`; expected translation units: "
        + ", ".join(f"`{path}`" for path in payload["expected_translation_units_after"])
        + "."
    )
    lines.extend(["", "## Native obligations", ""])
    lines.extend(
        f"- `{row['name']}` passed on the current tree and disposable after-tree."
        for row in payload["native_verification"]["current_tree"]["commands"]
    )
    lines.extend(["", "## Explicit non-claims", ""])
    lines.extend(f"- {item}" for item in payload["nonclaims"])
    return "\n".join(lines).rstrip() + "\n"


def _refusal(error: ProposalError) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-boundary",
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
    parser.add_argument("--omnibus", type=Path, required=True)
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
            args.omnibus.resolve(),
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
        print(f"propose-boundary C: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, TypeError, ValueError, KeyError) as exc:
        error = ProposalError("failed", "proposal_failed", str(exc))
        if output is not None:
            payload = _refusal(error)
            _replace_bundle(output, payload, _render(payload))
        print(f"propose-boundary C: proposal_failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
