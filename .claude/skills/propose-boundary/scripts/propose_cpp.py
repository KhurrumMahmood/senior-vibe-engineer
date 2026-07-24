#!/usr/bin/env python3
"""Render one accepted C++20 boundary plan without redetecting or mutating source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "cpp-boundary-proposal-v1"
ACCEPTANCE_SCHEMA = "cpp-structure-accepted-evidence-v1"
SOURCE_SUFFIXES = {".cpp", ".cc", ".cxx"}
HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx", ".inc", ".tpp"}
CALLABLE_KINDS = {"function", "method", "constructor", "destructor"}
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
    "the exact C++20 compile-command snapshot does not prove alternate build variants",
    "compiler-observed static references do not resolve virtual or dynamic dispatch",
    "templates, specializations, callbacks, function pointers, and runtime registrations require refusal unless explicitly resolved",
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
    allowed = root / "reports/propose-boundary"
    if output == allowed or not _contained(allowed, output):
        raise ProposalError(
            "failed", "unsafe_output_path", "artifacts must stay below reports/propose-boundary/"
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
        "target",
        "domain",
        "declarations",
        "overload_sets",
        "caller_impact",
        "source_impact",
        "header_impact",
        "build_impact",
        "exact_edits",
        "create_files",
        "expected_translation_units_after",
        "test_surface",
        "nonclaims",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-boundary",
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
    root: Path, acceptance_path: Path, omnibus_path: Path, map_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str], dict[str, str]]:
    acceptance = _read_json(acceptance_path, "acceptance")
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
    if (
        not isinstance(verdict, dict)
        or verdict.get("status") != "accepted"
        or not isinstance(verdict.get("reviewer"), str)
        or not verdict["reviewer"].strip()
    ):
        raise ProposalError("failed", "human_acceptance_required", "human verdict is not accepted")
    _uncertainty_review(acceptance)
    hashes = _artifact_hashes(
        root, acceptance, {"confirmed-omnibus": omnibus_path, "cpp-map": map_path}
    )
    sources = _validate_source_hashes(root, acceptance)
    omnibus = _read_json(omnibus_path, "confirmed C++ omnibus artifact")
    map_evidence = _read_json(map_path, "C++ map artifact")
    if omnibus.get("status") != "complete" or omnibus.get("failure_kind") not in {"none", None}:
        raise ProposalError("partial", "upstream_not_complete", "omnibus evidence is incomplete")
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
    return acceptance, omnibus, map_evidence, hashes, sources


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
        raise ProposalError("failed", "invalid_selection", "candidate lacks explicit scout authority")
    return candidate


def _declaration_key(row: dict[str, Any]) -> tuple[str, str]:
    return row.get("qualified_name"), row.get("signature")


def _declarations(
    selection: dict[str, Any], candidate: dict[str, Any], map_evidence: dict[str, Any]
) -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    rows = selection.get("declarations")
    domain = selection.get("domain")
    if not isinstance(rows, list) or len(rows) < 2 or not isinstance(domain, str):
        raise ProposalError("failed", "invalid_selection", "exact selected declarations are missing")
    normalized: list[dict[str, str]] = []
    keys: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ProposalError("failed", "invalid_selection", "declaration row is invalid")
        qualified, signature, kind = (
            row.get("qualified_name"),
            row.get("signature"),
            row.get("kind"),
        )
        if (
            not isinstance(qualified, str)
            or "::" not in qualified
            or not isinstance(signature, str)
            or not signature
            or kind != "function"
            or (qualified, signature) in keys
        ):
            raise ProposalError("failed", "invalid_selection", "declaration identity is ambiguous")
        keys.add((qualified, signature))
        normalized.append(
            {"qualified_name": qualified, "signature": signature, "kind": kind}
        )
    cluster = candidate.get("clusters", {}).get(domain)
    if not isinstance(cluster, list) or sorted(cluster) != sorted(row["qualified_name"] for row in normalized):
        raise ProposalError("failed", "invalid_selection", "accepted domain cluster changed")
    target = selection.get("target")
    header = selection.get("private_header")
    facts = map_evidence.get("declarations", [])
    for item in normalized:
        key = _declaration_key(item)
        definitions = [
            row
            for row in facts
            if _declaration_key(row) == key
            and row.get("file") == target
            and row.get("kind") == "function"
            and row.get("definition") is True
        ]
        declarations = [
            row
            for row in facts
            if _declaration_key(row) == key
            and row.get("file") == header
            and row.get("kind") == "function"
            and row.get("definition") is False
        ]
        if len(definitions) != 1 or len(declarations) != 1:
            raise ProposalError(
                "failed", "ambiguous_declaration", f"{key[0]} {key[1]} lacks exact definition lineage"
            )
        if definitions[0].get("template") or declarations[0].get("template"):
            raise ProposalError("failed", "template_or_specialization_refused", key[0])
    qnames = {row["qualified_name"] for row in normalized}
    observed = {
        _declaration_key(row)
        for row in facts
        if row.get("qualified_name") in qnames
        and row.get("kind") == "function"
        and row.get("file") in {target, header}
        and ((row.get("file") == target and row.get("definition") is True)
             or (row.get("file") == header and row.get("definition") is False))
    }
    if observed != keys:
        raise ProposalError("failed", "ambiguous_overload_set", "selected overload inventory is incomplete")
    public = {_declaration_key(row) for row in map_evidence.get("public_surface", [])}
    if keys & public:
        raise ProposalError("failed", "public_header_refused", "selected declaration is public")
    overloads = {
        name: sorted(row["signature"] for row in normalized if row["qualified_name"] == name)
        for name in sorted(qnames)
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
    root: Path, selection: dict[str, Any], candidate: dict[str, Any], map_evidence: dict[str, Any]
) -> dict[str, Any]:
    target = _safe_relative(selection.get("target"), "target translation unit")
    header = _safe_relative(selection.get("private_header"), "private header")
    new_header = _safe_relative(selection.get("new_private_header"), "new private header")
    new_unit = _safe_relative(selection.get("new_translation_unit"), "new translation unit")
    if target not in map_evidence.get("translation_units", []):
        raise ProposalError("failed", "invalid_selection", "target lacks compile-database authority")
    if header not in map_evidence.get("owned_headers", []) or header.startswith("include/"):
        raise ProposalError("failed", "ambiguous_or_public_header_refused", "header is not private-owned")
    inventory = {row.get("path"): row for row in map_evidence.get("source_inventory", [])}
    if (
        inventory.get(header, {}).get("role") != "private-header"
        or inventory.get(header, {}).get("included") is not True
    ):
        raise ProposalError("failed", "ambiguous_or_public_header_refused", "header ownership changed")
    declarations, overloads = _declarations(selection, candidate, map_evidence)
    callers = _caller_impact(selection, declarations, map_evidence)
    exact_edits = selection.get("exact_edits")
    creates = selection.get("create_files")
    if not isinstance(exact_edits, list) or not exact_edits or not isinstance(creates, list):
        raise ProposalError("failed", "invalid_selection", "exact source/header/build plan is missing")
    normalized_edits: list[dict[str, Any]] = []
    for row in exact_edits:
        path = _safe_relative(row.get("path"), "edit path")
        before, after, count = row.get("before"), row.get("after"), row.get("expected_occurrences")
        if (
            not isinstance(before, str)
            or not before
            or not isinstance(after, str)
            or not isinstance(count, int)
            or count < 1
        ):
            raise ProposalError("failed", "invalid_selection", f"edit is malformed: {path}")
        try:
            current = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ProposalError("failed", "stale_accepted_source", f"edit {path}: {exc}") from exc
        if current.count(before) != count:
            raise ProposalError("failed", "stale_accepted_source", f"edit changed: {path}")
        normalized_edits.append(
            {"path": path, "before": before, "after": after, "expected_occurrences": count}
        )
    normalized_creates: list[dict[str, str]] = []
    for row in creates:
        path = _safe_relative(row.get("path"), "create path")
        contents = row.get("contents")
        if not isinstance(contents, str) or not contents or (root / path).exists():
            raise ProposalError("failed", "invalid_selection", f"create is invalid: {path}")
        if re.search(r"\btemplate\s*<|\bvirtual\b|std::function|\(\s*\*", contents):
            raise ProposalError("failed", "cpp_dynamic_or_template_surface_refused", path)
        normalized_creates.append({"path": path, "contents": contents})
    if {row["path"] for row in normalized_creates} != {new_header, new_unit}:
        raise ProposalError("failed", "invalid_selection", "created C++ seam paths changed")
    edit_pairs = {(row["path"], row["before"], row["after"]) for row in normalized_edits}
    create_map = {row["path"]: row["contents"] for row in normalized_creates}
    impacts: dict[str, list[dict[str, Any]]] = {}
    for key in ("source_impact", "header_impact", "build_impact"):
        rows = selection.get(key)
        if not isinstance(rows, list) or not rows:
            raise ProposalError("failed", "invalid_selection", f"{key} is missing")
        for row in rows:
            path, before, after = row.get("path"), row.get("before"), row.get("after")
            if before is None:
                if path not in create_map or not isinstance(after, str) or after not in create_map[path]:
                    raise ProposalError("failed", "invalid_selection", f"{key} create impact changed")
            elif (path, before, after) not in edit_pairs:
                raise ProposalError("failed", "invalid_selection", f"{key} lacks exact edit")
        impacts[key] = rows
    expected_after = selection.get("expected_translation_units_after")
    current_units = set(map_evidence.get("translation_units", []))
    if (
        not isinstance(expected_after, list)
        or expected_after != sorted(current_units | {new_unit})
    ):
        raise ProposalError("failed", "invalid_selection", "after-tree TU census is not exact")
    return {
        "target": target,
        "domain": selection["domain"],
        "declarations": declarations,
        "overload_sets": overloads,
        "private_header": header,
        "new_private_header": new_header,
        "new_translation_unit": new_unit,
        "caller_impact": callers,
        **impacts,
        "exact_edits": normalized_edits,
        "create_files": normalized_creates,
        "expected_translation_units_after": expected_after,
        "test_surface": selection.get("test_surface", []),
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
            arguments = row["arguments"]
            if "-std=c++20" not in arguments:
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
    root: Path, acceptance: dict[str, Any], plan: dict[str, Any], make: str, clangxx: str
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cpp-boundary-after-") as temporary:
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
        "skill": "propose-boundary",
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
    omnibus_path: Path,
    map_path: Path,
    acceptance_path: Path,
    make: str,
    clangxx: str,
    before: dict[str, str],
) -> dict[str, Any]:
    acceptance, omnibus, map_evidence, hashes, _sources = _validate_inputs(
        root, acceptance_path, omnibus_path, map_path
    )
    selection = acceptance.get("selection")
    if not isinstance(selection, dict):
        raise ProposalError("failed", "invalid_selection", "accepted selection is missing")
    candidate = _candidate(omnibus, selection)
    current = _run_native(
        root, acceptance, make, clangxx, sorted(map_evidence["translation_units"])
    )
    if _audited_files(root) != before:
        raise ProposalError("failed", "source_mutation_detected", "current native proof changed source")
    if acceptance.get("decision") == "keep_cohesive":
        payload = _base(
            "complete", "safely_deferred", "defer_cohesive_target",
            acceptance, hashes, current,
        )
        payload.update(
            target=selection.get("target"), candidate_id=candidate["candidate_id"],
            message="Human review kept the confirmed C++ target cohesive.",
            source_preservation={"verified": True, "source_manifest": _canonical_hash(before)},
        )
        return payload
    if acceptance.get("decision") != "extract_boundary":
        raise ProposalError("failed", "human_acceptance_required", "boundary decision is unsupported")
    plan = _validated_plan(root, selection, candidate, map_evidence)
    disposable = _disposable_native(root, acceptance, plan, make, clangxx)
    if _audited_files(root) != before:
        raise ProposalError("failed", "source_mutation_detected", "disposable proof changed host source")
    payload = _base(
        "ready_for_human_review", "boundary_plan_ready", "review_boundary",
        acceptance, hashes, current,
    )
    payload.update(
        message="One accepted private C++20 free-function seam has exact overload, caller, header, source, and build accounting.",
        candidate_id=candidate["candidate_id"],
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
            "# C++ boundary proposal — refused\n\n"
            f"Status: `{payload['status']}`. `{payload['failure_kind']}`: {payload['message']}\n"
        )
    if payload["outcome"] == "safely_deferred":
        return "# C++ boundary proposal\n\nStatus: `complete`; no extraction is proposed.\n"
    lines = [
        f"# C++ boundary proposal — {payload['target']}::{payload['domain']}", "",
        "Status: `ready_for_human_review`; this artifact is read-only.", "",
        "## Accepted private C++20 seam", "",
        f"Extract into `{payload['new_translation_unit']}` and `{payload['new_private_header']}`.", "",
        "## Namespace-qualified declarations and overloads", "",
    ]
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
            lines.append(f"- `{row['path']}` — {row['impact']}")
    lines.extend(["", "## Native obligations", ""])
    lines.append("- C++20 compile database, native test, and smoke passed on current and disposable after-trees.")
    lines.extend(["", "## Explicit non-claims", ""])
    lines.extend(f"- {item}" for item in payload["nonclaims"])
    return "\n".join(lines).rstrip() + "\n"


def _refusal(error: ProposalError) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-boundary",
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
    parser.add_argument("--omnibus", type=Path, required=True)
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
            root, args.omnibus.resolve(), args.map_evidence.resolve(),
            args.acceptance.resolve(), args.make, args.clangxx, before,
        )
        _replace_bundle(output, payload, _render(payload))
        return 0
    except ProposalError as exc:
        if output is not None:
            payload = _refusal(exc)
            _replace_bundle(output, payload, _render(payload))
        print(f"propose-boundary C++: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, TypeError, ValueError, KeyError) as exc:
        error = ProposalError("failed", "proposal_failed", str(exc))
        if output is not None:
            payload = _refusal(error)
            _replace_bundle(output, payload, _render(payload))
        print(f"propose-boundary C++: proposal_failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
