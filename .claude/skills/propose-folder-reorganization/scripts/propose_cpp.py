#!/usr/bin/env python3
"""Render one accepted C++20 folder plan without redetecting or mutating source."""

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


SCHEMA_VERSION = "cpp-folder-proposal-v1"
ACCEPTANCE_SCHEMA = "cpp-structure-accepted-evidence-v1"
CONVENTION = "group-three-private-cpp-translation-units"
SOURCE_SUFFIXES = {".cpp", ".cc", ".cxx"}
HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx", ".inc", ".tpp"}
UNCERTAINTY_KEYS = {
    "templates_specializations",
    "virtual_dynamic_dispatch",
    "function_pointers_callbacks",
    "header_exposure",
    "odr_abi",
    "external_consumers",
    "build_variants",
}
NONCLAIMS = [
    "a filename prefix does not establish a C++ namespace or ownership boundary",
    "the exact C++20 compile-command snapshot does not prove alternate build variants",
    "compiler-observed references do not resolve virtual dispatch, callbacks, or function pointers",
    "private-header ownership does not prove ODR, ABI, object-layout, or external-consumer compatibility",
    "the proposal, evidence, and scope artifacts are read-only and grant no source-mutation authority",
]


class ProposalError(RuntimeError):
    """A typed terminal refusal for the accepted-evidence consumer."""

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
            "artifacts must stay below reports/propose-folder-reorganization/",
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


def _scope(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "status",
        "outcome",
        "failure_kind",
        "message",
        "parent",
        "prefix",
        "project_convention",
        "declarations",
        "overload_sets",
        "caller_impact",
        "source_impact",
        "header_impact",
        "build_impact",
        "exact_moves",
        "exact_edits",
        "current_tree",
        "proposed_tree",
        "expected_translation_units_after",
        "test_surface",
        "nonclaims",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-folder-reorganization",
        "language": "cpp",
        "read_only": True,
        "mutation_authorized": False,
        **{key: payload[key] for key in keys if key in payload},
    }


def _replace_bundle(output: Path, payload: dict[str, Any], proposal: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.parent / f".{output.name}.stage-{uuid.uuid4().hex}"
    backup = output.parent / f".{output.name}.old-{uuid.uuid4().hex}"
    staged.mkdir()
    try:
        _atomic(staged / "evidence.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _atomic(staged / "scope.json", json.dumps(_scope(payload), indent=2, sort_keys=True) + "\n")
        _atomic(staged / "proposal.md", proposal)
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
        if any(part in {".git", "reports", ".native-build", ".engineering"} for part in relative.parts):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix in SOURCE_SUFFIXES | HEADER_SUFFIXES or path.name == "Makefile":
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
            "current C++ source/header/Make bytes differ from the accepted census",
        )
    return current


def _artifact_hashes(
    root: Path, acceptance: dict[str, Any], supplied: dict[str, Path]
) -> dict[str, str]:
    rows = acceptance.get("artifacts")
    if not isinstance(rows, list):
        raise ProposalError("failed", "invalid_accepted_evidence", "artifact hashes are missing")
    accepted = {
        row.get("kind"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("kind"), str)
    }
    if set(accepted) != set(supplied):
        raise ProposalError("failed", "invalid_accepted_evidence", "accepted artifact set changed")
    result: dict[str, str] = {}
    for kind, path in supplied.items():
        relative = _safe_relative(accepted[kind].get("path"), f"{kind} artifact path")
        expected = (root / relative).resolve()
        if expected != path.resolve() or not _contained(root, expected):
            raise ProposalError("failed", "invalid_accepted_evidence", f"{kind} path changed")
        digest = _sha256(path)
        if accepted[kind].get("sha256") != digest:
            raise ProposalError("failed", "stale_accepted_evidence", f"{kind} hash changed")
        result[kind] = digest
    return result


def _uncertainty_review(acceptance: dict[str, Any]) -> dict[str, Any]:
    review = acceptance.get("uncertainty_review")
    if not isinstance(review, dict) or set(review) != UNCERTAINTY_KEYS:
        raise ProposalError(
            "failed", "cpp_uncertainty_unresolved", "the exact C++ uncertainty review is required"
        )
    for key, row in review.items():
        if (
            not isinstance(row, dict)
            or row.get("status") != "resolved"
            or not isinstance(row.get("basis"), str)
            or not row["basis"].strip()
        ):
            raise ProposalError("failed", "cpp_uncertainty_unresolved", f"{key} is unresolved")
    return review


def _validate_inputs(
    root: Path, acceptance_path: Path, topology_path: Path, map_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str], dict[str, str]]:
    acceptance = _read_json(acceptance_path, "acceptance")
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
    if (
        not isinstance(verdict, dict)
        or verdict.get("status") != "accepted"
        or not isinstance(verdict.get("reviewer"), str)
        or not verdict["reviewer"].strip()
    ):
        raise ProposalError("failed", "human_acceptance_required", "human verdict is not accepted")
    _uncertainty_review(acceptance)
    hashes = _artifact_hashes(
        root, acceptance, {"lexical-topology": topology_path, "cpp-map": map_path}
    )
    sources = _validate_source_hashes(root, acceptance)
    topology = _read_json(topology_path, "C++ topology artifact")
    map_evidence = _read_json(map_path, "C++ map artifact")
    if topology.get("status") != "complete" or topology.get("outcome") != "drift-found":
        raise ProposalError("partial", "upstream_not_complete", "topology evidence is incomplete")
    if (
        map_evidence.get("status") != "complete"
        or map_evidence.get("language") != "cpp"
        or map_evidence.get("compile_database", {}).get("state")
        != "valid-current-complete-c++20-mode"
        or map_evidence.get("source_fingerprints", {}).get("unchanged") is not True
    ):
        raise ProposalError("partial", "upstream_not_complete", "C++ map evidence is incomplete")
    for key in (
        "compile_database",
        "translation_unit_inventory",
        "dependency_inventory",
        "declarations_public_surface_and_static_references",
    ):
        if map_evidence.get("completeness", {}).get(key) != "complete":
            raise ProposalError("partial", "upstream_not_complete", "C++ map completeness changed")
    return acceptance, topology, map_evidence, hashes, sources


def _finding(topology: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
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
        or finding.get("language") != "cpp"
        or finding.get("file") != selection.get("parent")
        or finding.get("prefix") != selection.get("prefix")
        or finding.get("files") != selection.get("files")
        or finding.get("count", 0) < 3
    ):
        raise ProposalError("failed", "invalid_selection", "accepted C++ cluster lineage changed")
    return finding


def _declaration_key(row: dict[str, Any]) -> tuple[str, str]:
    return row.get("qualified_name"), row.get("signature")


def _declaration_impact(
    files: list[str], map_evidence: dict[str, Any]
) -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    facts = map_evidence.get("declarations", [])
    definitions = [
        row
        for row in facts
        if row.get("file") in files
        and row.get("definition") is True
        and row.get("kind") == "function"
        and isinstance(row.get("line"), int)
        and row["line"] > 0
    ]
    if not definitions:
        raise ProposalError("failed", "ambiguous_declaration", "moved files lack exact functions")
    keys: set[tuple[str, str]] = set()
    normalized: list[dict[str, str]] = []
    owned = set(map_evidence.get("owned_headers", []))
    public = {_declaration_key(row) for row in map_evidence.get("public_surface", [])}
    for row in definitions:
        key = _declaration_key(row)
        if (
            row.get("template") is True
            or not isinstance(key[0], str)
            or "::" not in key[0]
            or not isinstance(key[1], str)
            or key in keys
        ):
            raise ProposalError("failed", "template_specialization_or_ambiguity_refused", str(key))
        if key in public:
            raise ProposalError("failed", "public_header_refused", key[0])
        declarations = [
            candidate
            for candidate in facts
            if _declaration_key(candidate) == key
            and candidate.get("file") in owned
            and not candidate.get("file", "").startswith("include/")
            and candidate.get("kind") == "function"
            and candidate.get("definition") is False
            and candidate.get("template") is not True
        ]
        if len(declarations) != 1:
            raise ProposalError("failed", "ambiguous_declaration", f"{key} header lineage changed")
        keys.add(key)
        normalized.append(
            {
                "qualified_name": key[0], "signature": key[1], "kind": "function",
                "definition_file": row["file"], "declaration_header": declarations[0]["file"],
            }
        )
    names = {row["qualified_name"] for row in normalized}
    observed = {
        _declaration_key(row)
        for row in facts
        if row.get("qualified_name") in names
        and row.get("kind") == "function"
        and row.get("definition") is True
        and row.get("file") in files
    }
    if observed != keys:
        raise ProposalError("failed", "ambiguous_overload_set", "moved overload inventory changed")
    overloads = {
        name: sorted(row["signature"] for row in normalized if row["qualified_name"] == name)
        for name in sorted(names)
    }
    return sorted(normalized, key=lambda row: (row["qualified_name"], row["signature"])), overloads


def _caller_impact(
    selection: dict[str, Any], declarations: list[dict[str, str]], map_evidence: dict[str, Any]
) -> list[dict[str, Any]]:
    selected = {_declaration_key(row) for row in declarations}
    expected = []
    for edge in map_evidence.get("reference_edges", []):
        if _declaration_key(edge.get("target", {})) not in selected:
            continue
        expected.append(
            {
                "path": edge.get("file"),
                "translation_unit": edge.get("translation_unit"),
                "direction": edge.get("direction"),
                "source": {
                    "qualified_name": edge.get("source", {}).get("qualified_name"),
                    "signature": edge.get("source", {}).get("signature"),
                },
                "target": {
                    "qualified_name": edge.get("target", {}).get("qualified_name"),
                    "signature": edge.get("target", {}).get("signature"),
                },
            }
        )
    supplied = selection.get("caller_impact")
    if not isinstance(supplied, list) or len(supplied) != len(expected):
        raise ProposalError("failed", "ambiguous_callers", "caller inventory is not exact")
    def identity(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            row.get("path"), row.get("translation_unit"), row.get("direction"),
            row.get("source", {}).get("qualified_name"), row.get("source", {}).get("signature"),
            row.get("target", {}).get("qualified_name"), row.get("target", {}).get("signature"),
        )
    if sorted(map(identity, supplied)) != sorted(map(identity, expected)):
        raise ProposalError("failed", "ambiguous_callers", "accepted callers changed")
    for row in supplied:
        if not isinstance(row.get("impact"), str) or not row["impact"].strip():
            raise ProposalError("failed", "invalid_selection", "caller impact is missing")
    return sorted(supplied, key=identity)


def _validated_plan(
    root: Path, selection: dict[str, Any], finding: dict[str, Any], map_evidence: dict[str, Any]
) -> dict[str, Any]:
    parent = _safe_relative(selection.get("parent"), "cluster parent")
    prefix, files = selection.get("prefix"), selection.get("files")
    if selection.get("project_convention") != CONVENTION:
        raise ProposalError("failed", "project_convention_required", "C++ convention is absent")
    if not isinstance(prefix, str) or not isinstance(files, list) or files != finding["files"]:
        raise ProposalError("failed", "invalid_selection", "cluster members changed")
    if not set(files).issubset(set(map_evidence.get("translation_units", []))):
        raise ProposalError("failed", "invalid_selection", "cluster lacks compile-database authority")
    moves = selection.get("exact_moves")
    if not isinstance(moves, list) or len(moves) < len(files):
        raise ProposalError("failed", "invalid_selection", "exact moves are incomplete")
    normalized_moves: list[dict[str, str]] = []
    destinations: set[str] = set()
    for row in moves:
        source = _safe_relative(row.get("from"), "move source")
        destination = _safe_relative(row.get("to"), "move destination")
        if not (root / source).is_file() or (root / destination).exists():
            raise ProposalError("failed", "stale_accepted_source", f"move changed: {source}")
        if Path(destination).parent.as_posix() != f"{parent}/{prefix}" or destination in destinations:
            raise ProposalError("failed", "invalid_selection", "move destination escaped cluster folder")
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
    owned = set(map_evidence.get("owned_headers", []))
    if any(
        row["from"] not in owned
        or row["from"].startswith("include/")
        or Path(row["from"]).parent.as_posix() != parent
        or Path(row["from"]).suffix not in HEADER_SUFFIXES
        for row in auxiliary
    ):
        raise ProposalError("failed", "ambiguous_or_public_header_refused", "header move is unsafe")
    facts = map_evidence.get("declarations", [])
    auxiliary_paths = {row["from"] for row in auxiliary}
    if any(
        row.get("file") in auxiliary_paths
        and row.get("definition") is True
        and row.get("kind") in {"function", "method", "constructor", "destructor"}
        for row in facts
    ):
        raise ProposalError("failed", "odr_header_definition_refused", "moved header defines a callable")
    declarations, overloads = _declaration_impact(files, map_evidence)
    callers = _caller_impact(selection, declarations, map_evidence)
    edits = selection.get("exact_edits")
    if not isinstance(edits, list) or not edits:
        raise ProposalError("failed", "invalid_selection", "exact edits are missing")
    moved_destinations = {row["to"] for row in normalized_moves}
    normalized_edits: list[dict[str, Any]] = []
    for row in edits:
        path = _safe_relative(row.get("path"), "edit path")
        before, after, count = row.get("before"), row.get("after"), row.get("expected_occurrences")
        if (
            not isinstance(before, str)
            or not before
            or not isinstance(after, str)
            or not isinstance(count, int)
            or count < 1
            or (not (root / path).is_file() and path not in moved_destinations)
        ):
            raise ProposalError("failed", "invalid_selection", f"edit is malformed: {path}")
        normalized_edits.append(
            {"path": path, "before": before, "after": after, "expected_occurrences": count}
        )
    edit_pairs = {(row["path"], row["before"], row["after"]) for row in normalized_edits}
    move_pairs = {(row["from"], row["to"]) for row in normalized_moves}
    impacts: dict[str, list[dict[str, Any]]] = {}
    for key in ("source_impact", "header_impact", "build_impact"):
        rows = selection.get(key)
        if not isinstance(rows, list) or not rows:
            raise ProposalError("failed", "invalid_selection", f"{key} is missing")
        for row in rows:
            if "from" in row:
                if (row.get("from"), row.get("to")) not in move_pairs:
                    raise ProposalError("failed", "invalid_selection", f"{key} move changed")
            elif (row.get("path"), row.get("before"), row.get("after")) not in edit_pairs:
                raise ProposalError("failed", "invalid_selection", f"{key} lacks exact edit")
            if not isinstance(row.get("impact"), str) or not row["impact"].strip():
                raise ProposalError("failed", "invalid_selection", f"{key} impact is missing")
        impacts[key] = rows
    if {(row["from"], row["to"]) for row in impacts["source_impact"]} != {
        (row["from"], row["to"]) for row in cluster_moves
    }:
        raise ProposalError("failed", "invalid_selection", "source move accounting is incomplete")
    expected_after = selection.get("expected_translation_units_after")
    current = set(map_evidence.get("translation_units", []))
    proposed = (current - set(files)) | {row["to"] for row in cluster_moves}
    if not isinstance(expected_after, list) or expected_after != sorted(proposed):
        raise ProposalError("failed", "invalid_selection", "after-tree TU census is not exact")
    return {
        "parent": parent,
        "prefix": prefix,
        "project_convention": CONVENTION,
        "current_tree": files,
        "proposed_tree": [row["to"] for row in cluster_moves],
        "declarations": declarations,
        "overload_sets": overloads,
        "caller_impact": callers,
        **impacts,
        "exact_moves": normalized_moves,
        "exact_edits": normalized_edits,
        "expected_translation_units_after": expected_after,
        "test_surface": selection.get("test_surface", []),
        "accounting": {
            "cluster_members": len(files),
            "planned_cluster_members": len(cluster_moves),
            "auxiliary_private_headers": len(auxiliary),
        },
    }


def _native_commands(
    root: Path, acceptance: dict[str, Any], make: str, clangxx: str
) -> list[dict[str, Any]]:
    rows = acceptance.get("native_obligations")
    if not isinstance(rows, list) or {row.get("name") for row in rows} != {
        "compile-database", "native-test", "smoke"
    }:
        raise ProposalError("failed", "invalid_native_obligations", "exact C++20 matrix is required")
    commands: list[dict[str, Any]] = []
    for row in rows:
        name, raw = row.get("name"), row.get("argv")
        if row.get("expected_returncode") != 0 or not isinstance(raw, list):
            raise ProposalError("failed", "invalid_native_obligations", "native row is malformed")
        if name == "compile-database":
            if raw != ["make", "clean", "compile-db", "CXX=clang++"]:
                raise ProposalError("failed", "invalid_native_obligations", "compile-db row changed")
            resolved = [make, "clean", "compile-db", f"CXX={clangxx}"]
        elif name == "native-test":
            if raw != ["make", "test", "CXX=clang++"]:
                raise ProposalError("failed", "invalid_native_obligations", "test row changed")
            resolved = [make, "test", f"CXX={clangxx}"]
        else:
            if len(raw) != 1:
                raise ProposalError("failed", "invalid_native_obligations", "smoke row changed")
            resolved = [str(root / _safe_relative(raw[0], "smoke executable"))]
        commands.append({**row, "resolved_argv": resolved})
    return commands


def _database_units(root: Path) -> list[str]:
    try:
        payload = json.loads((root / "compile_commands.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalError("failed", "native_verification_failed", f"compile database: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise ProposalError("failed", "native_verification_failed", "compile database is empty")
    units: list[str] = []
    canonical_root = root.resolve()
    for row in payload:
        try:
            if "-std=c++20" not in row["arguments"]:
                raise ValueError("non-C++20 command")
            raw = Path(row["file"])
            absolute = raw if raw.is_absolute() else root / raw
            units.append(absolute.resolve().relative_to(canonical_root).as_posix())
        except (KeyError, TypeError, ValueError) as exc:
            raise ProposalError("failed", "native_verification_failed", "compile database is foreign") from exc
    if len(units) != len(set(units)):
        raise ProposalError("failed", "native_verification_failed", "duplicate translation units")
    return sorted(units)


def _run_native(
    root: Path,
    acceptance: dict[str, Any],
    make: str,
    clangxx: str,
    expected_units: list[str],
) -> dict[str, Any]:
    results = []
    for command in _native_commands(root, acceptance, make, clangxx):
        try:
            completed = subprocess.run(
                command["resolved_argv"], cwd=root, capture_output=True, text=True,
                check=False, timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProposalError("failed", "native_verification_failed", f"{command['name']}: {exc}") from exc
        if completed.returncode != command["expected_returncode"]:
            raise ProposalError(
                "failed", "native_verification_failed",
                f"{command['name']} exited {completed.returncode}: {completed.stderr.strip()}",
            )
        expected_stdout, contains = command.get("expected_stdout"), command.get("expected_stdout_contains")
        if expected_stdout is not None and completed.stdout != expected_stdout:
            raise ProposalError("failed", "native_verification_failed", f"{command['name']} stdout changed")
        if contains is not None and contains not in completed.stdout:
            raise ProposalError("failed", "native_verification_failed", f"{command['name']} output changed")
        results.append(
            {"name": command["name"], "argv": command["argv"],
             "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
        )
    units = _database_units(root)
    if units != expected_units:
        raise ProposalError("failed", "native_verification_failed", "translation-unit census changed")
    return {
        "status": "passed", "commands": results, "compile_database_regenerated": True,
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
        text = path.read_text(encoding="utf-8")
        if text.count(row["before"]) != row["expected_occurrences"]:
            raise ProposalError("failed", "disposable_plan_mismatch", f"edit changed: {row['path']}")
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")


def _disposable_native(
    root: Path, acceptance: dict[str, Any], plan: dict[str, Any], make: str, clangxx: str
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cpp-folder-after-") as temporary:
        disposable = Path(temporary) / "host"
        shutil.copytree(
            root, disposable,
            ignore=shutil.ignore_patterns(".git", "reports", ".native-build", ".engineering"),
        )
        _apply_plan(disposable, plan)
        result = _run_native(
            disposable, acceptance, make, clangxx, plan["expected_translation_units_after"]
        )
        result["disposable"] = True
        result["after_tree"] = plan["proposed_tree"]
        return result


def _base(
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
        "language": "cpp",
        "status": status,
        "outcome": outcome,
        "recommendation": recommendation,
        "read_only": True,
        "source_mutations": 0,
        "accepted_evidence": {
            "acceptance_hash": acceptance["acceptance_hash"], "artifact_hashes": hashes
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
    clangxx: str,
    before: dict[str, str],
) -> dict[str, Any]:
    acceptance, topology, map_evidence, hashes, _sources = _validate_inputs(
        root, acceptance_path, topology_path, map_path
    )
    selection = acceptance.get("selection")
    if not isinstance(selection, dict):
        raise ProposalError("failed", "invalid_selection", "accepted selection is missing")
    finding = _finding(topology, selection)
    current = _run_native(
        root, acceptance, make, clangxx, sorted(map_evidence["translation_units"])
    )
    if _audited_files(root) != before:
        raise ProposalError("failed", "source_mutation_detected", "current native proof changed source")
    if acceptance.get("decision") in {"keep_flat", "defer_no_convention"}:
        recommendation = (
            "keep_flat" if acceptance["decision"] == "keep_flat"
            else "defer_project_convention_required"
        )
        payload = _base("complete", "safely_deferred", recommendation, acceptance, hashes, current)
        payload.update(
            parent=selection.get("parent"), prefix=selection.get("prefix"),
            message="No C++ folder move is proposed.",
            source_preservation={"verified": True, "source_manifest": _canonical_hash(before)},
        )
        return payload
    if acceptance.get("decision") != "reorganize":
        raise ProposalError("failed", "human_acceptance_required", "folder decision is unsupported")
    plan = _validated_plan(root, selection, finding, map_evidence)
    disposable = _disposable_native(root, acceptance, plan, make, clangxx)
    if _audited_files(root) != before:
        raise ProposalError("failed", "source_mutation_detected", "disposable proof changed host source")
    payload = _base(
        "ready_for_human_review", "folder_plan_ready", "review_folder_plan",
        acceptance, hashes, current,
    )
    payload.update(
        message="One accepted private C++20 prefix cluster has exact declaration, caller, header, source, and build accounting.",
        finding_evidence_sha256=finding["evidence_sha256"],
        map_snapshot={
            "analyzer": map_evidence["analyzer"],
            "compile_database": map_evidence["compile_database"],
            "completeness": map_evidence["completeness"],
        },
        **plan,
        native_verification={"current_tree": current, "disposable_after_tree": disposable},
        source_preservation={"verified": True, "source_manifest": _canonical_hash(before)},
    )
    return payload


def _render(payload: dict[str, Any]) -> str:
    if payload.get("outcome") == "refused":
        return (
            "# C++ folder reorganization proposal — refused\n\n"
            f"Status: `{payload['status']}`. `{payload['failure_kind']}`: {payload['message']}\n"
        )
    if payload["outcome"] == "safely_deferred":
        return "# C++ folder reorganization proposal\n\nStatus: `complete`; no move is proposed.\n"
    lines = [
        f"# C++ folder reorganization proposal — {payload['parent']}::{payload['prefix']}", "",
        "Status: `ready_for_human_review`; this artifact moves no files.", "",
        "## Accepted private C++20 project convention", "",
        f"`{payload['project_convention']}`", "", "## Current → proposed tree", "",
    ]
    lines.extend(f"- `{row['from']}` → `{row['to']}`" for row in payload["exact_moves"])
    lines.extend(["", "## Namespace-qualified declarations and overloads", ""])
    lines.extend(
        f"- `{row['qualified_name']}` — `{row['signature']}`"
        for row in payload["declarations"]
    )
    for heading, key in (
        ("Caller impact", "caller_impact"),
        ("Source impact", "source_impact"),
        ("Private-header impact", "header_impact"),
        ("Build and compile-database impact", "build_impact"),
    ):
        lines.extend(["", f"## {heading}", ""])
        for row in payload[key]:
            label = row.get("path") or f"{row.get('from')} → {row.get('to')}"
            lines.append(f"- `{label}` — {row['impact']}")
    lines.extend(["", "## Native obligations", ""])
    lines.append("- C++20 compile database, native test, and smoke passed on current and disposable after-trees.")
    lines.extend(["", "## Explicit non-claims", ""])
    lines.extend(f"- {item}" for item in payload["nonclaims"])
    return "\n".join(lines).rstrip() + "\n"


def _refusal(error: ProposalError) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-folder-reorganization",
        "language": "cpp",
        "status": error.status,
        "outcome": "refused",
        "recommendation": "defer_invalid_stale_or_uncertain_evidence",
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
    parser.add_argument("--clangxx", required=True)
    parser.add_argument("--make", required=True)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output: Path | None = None
    try:
        output = _safe_output(root, args.output_dir)
        before = _audited_files(root)
        payload = _build(
            root, args.topology.resolve(), args.map_evidence.resolve(),
            args.acceptance.resolve(), args.make, args.clangxx, before,
        )
        _replace_bundle(output, payload, _render(payload))
        return 0
    except ProposalError as exc:
        if output is not None:
            payload = _refusal(exc)
            _replace_bundle(output, payload, _render(payload))
        print(f"propose-folder-reorganization C++: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, TypeError, ValueError, KeyError) as exc:
        error = ProposalError("failed", "proposal_failed", str(exc))
        if output is not None:
            payload = _refusal(error)
            _replace_bundle(output, payload, _render(payload))
        print(f"propose-folder-reorganization C++: proposal_failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
