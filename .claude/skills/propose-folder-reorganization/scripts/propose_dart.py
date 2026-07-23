#!/usr/bin/env python3
"""Render one accepted, read-only Dart folder-reorganization proposal."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
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


SCHEMA_VERSION = "dart-folder-reorganization-proposal-v1"
CONVENTION = "folder_for_three_prefix_siblings"
NON_CLAIMS = [
    "one accepted direct-sibling cluster is planned; this is not a general move engine",
    "selected-configuration imports do not cover reflection, dynamic loading, or external consumers",
    "public package URI and semver compatibility outside the preserved barrel remain unresolved",
    "parts, generated code, conditional directives, symlinks, and cross-package moves are refused",
    "Flutter folder, route, widget, plugin, asset, and platform conventions are not inferred",
    "the artifact is read-only and grants no mutation authority",
]


class ProposalError(RuntimeError):
    """A typed refusal local to the Dart folder consumer."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def _validator() -> Any:
    candidates = [Path(__file__).with_name("dart_accepted_evidence.py")]
    candidates.extend(
        parent / "_dart" / "dart_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Dart accepted-evidence validator is missing")
    spec = importlib.util.spec_from_file_location("dart_folder_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Dart accepted-evidence validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ACCEPTED = _validator()


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


def _safe_output(root: Path, supplied: Path) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(raw))
    allowed = root / "reports" / "propose-folder-reorganization"
    if not _contained(allowed, output) or output == allowed:
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


def _safe_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProposalError("failed", "invalid_selection", f"{label} is missing")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ProposalError("failed", "invalid_selection", f"{label} is unsafe")
    return value


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


def _write_artifacts(
    inspection: Path, proposal: Path, payload: dict[str, Any], rendered: str
) -> None:
    if inspection.parent != proposal.parent or inspection.name == proposal.name:
        raise ProposalError(
            "failed",
            "unsafe_output_path",
            "inspection and proposal must be distinct files in one directory",
        )
    destination = inspection.parent
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_name(f".{destination.name}.staged-{uuid.uuid4().hex}")
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    staged.mkdir()
    try:
        _atomic(staged / inspection.name, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _atomic(staged / proposal.name, rendered)
        if destination.exists():
            destination.replace(backup)
        try:
            staged.replace(destination)
        except OSError:
            if backup.exists():
                backup.replace(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def _snapshot(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".git", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = _sha256(path)
    return rows


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is not an object")
    return payload


def _fact_pack(evidence: Path, artifact: str, expected_hash: str) -> dict[str, Any]:
    facts = _read_json(evidence / artifact, "D4 import-impact pack")
    supplied = facts.get("fact_pack_sha256")
    unhashed = dict(facts)
    unhashed.pop("fact_pack_sha256", None)
    if supplied != _canonical_hash(unhashed) or supplied != expected_hash:
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "D4 import-impact hash does not verify"
        )
    if facts.get("schema_version") != "dart-lsp-facts-v1" or facts.get("status") != "complete":
        raise ProposalError(
            "partial", "upstream_not_complete", "D4 import-impact evidence is incomplete"
        )
    return facts


def _d1_cluster(evidence: Path, d1_artifact: str, selected: dict[str, Any]) -> dict[str, Any]:
    d1 = _read_json(evidence / d1_artifact, "D1 topology artifact")
    if d1.get("status") != "complete" or d1.get("outcome") != "drift-found":
        raise ProposalError(
            "partial", "upstream_not_complete", "D1 topology artifact has no accepted cluster"
        )
    matches = [
        row
        for row in d1.get("findings", [])
        if _canonical_hash(row) == selected.get("d1_finding_sha256")
    ]
    if len(matches) != 1:
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "accepted D1 cluster does not verify"
        )
    finding = matches[0]
    if (
        finding.get("pattern") != "flat_prefix_cluster"
        or finding.get("language") != "dart"
        or finding.get("evidence_sha256") != selected.get("d1_evidence_sha256")
        or finding.get("file") != selected.get("parent")
        or finding.get("prefix") != selected.get("prefix")
        or finding.get("files") != selected.get("files")
    ):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "accepted D1 cluster lineage changed"
        )
    return finding


def _citation_index(envelope: dict[str, Any]) -> set[tuple[str, int, int]]:
    return {
        (row["path"], row["start_line"], row["start_column"]) for row in envelope["cited_spans"]
    }


def _citation(citations: set[tuple[str, int, int]], path: str, line: int, column: int) -> str:
    if (path, line, column) not in citations:
        raise ProposalError(
            "failed",
            "uncited_proposal_fact",
            f"accepted evidence does not cite {path}:{line}:{column}",
        )
    return f"{path}:{line}:{column}"


def _edge_citation(citations: set[tuple[str, int, int]], root: Path, edge: dict[str, Any]) -> str:
    path, line_number = edge["source"], edge["line"]
    try:
        line = (root / path).read_text(encoding="utf-8").splitlines()[line_number - 1]
        column = line.index(edge["specifier"]) + 1
    except (OSError, UnicodeDecodeError, IndexError, ValueError) as exc:
        raise ProposalError("failed", "stale_import_impact", f"cannot cite edge in {path}") from exc
    return _citation(citations, path, line_number, column)


def _native_commands(envelope: dict[str, Any], root: Path, dart: str) -> list[dict[str, Any]]:
    rows = envelope.get("native_obligations")
    if not isinstance(rows, list) or {row.get("name") for row in rows} != {
        "analyze",
        "format",
        "direct-test",
        "smoke",
    }:
        raise ProposalError("failed", "invalid_native_obligations", "exact D0 matrix is required")
    result: list[dict[str, Any]] = []
    for row in rows:
        name, raw = row.get("name"), row.get("argv")
        if (
            not isinstance(raw, list)
            or not raw
            or raw[0] != "dart"
            or row.get("expected_returncode") != 0
        ):
            raise ProposalError(
                "failed", "invalid_native_obligations", "native obligation is malformed"
            )
        if name == "analyze":
            if raw != ["dart", "analyze", "--fatal-infos", "--fatal-warnings", "."]:
                raise ProposalError(
                    "failed", "invalid_native_obligations", "analyze obligation is not D0-safe"
                )
        elif name == "format":
            if (
                raw[:4]
                != [
                    "dart",
                    "format",
                    "--output=none",
                    "--set-exit-if-changed",
                ]
                or len(raw) < 5
            ):
                raise ProposalError(
                    "failed", "invalid_native_obligations", "format obligation is not D0-safe"
                )
            for item in raw[4:]:
                relative = _safe_relative(item, "format root")
                if not (root / relative).is_dir():
                    raise ProposalError(
                        "failed", "invalid_native_obligations", "format root is unavailable"
                    )
        elif name in {"direct-test", "smoke"}:
            if len(raw) != 2 or not raw[1].endswith(".dart"):
                raise ProposalError(
                    "failed", "invalid_native_obligations", f"{name} obligation is not D0-safe"
                )
            relative = _safe_relative(raw[1], f"{name} entrypoint")
            if not (root / relative).is_file() or (root / relative).is_symlink():
                raise ProposalError(
                    "failed", "invalid_native_obligations", f"{name} entrypoint is unavailable"
                )
        result.append({**row, "argv": [dart, *raw[1:]]})
    return result


def _run_native(root: Path, envelope: dict[str, Any], dart: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for command in _native_commands(envelope, root, dart):
        try:
            completed = subprocess.run(
                command["argv"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProposalError(
                "failed", "native_verification_failed", f"{command['name']}: {exc}"
            ) from exc
        checks.append(
            {
                "name": command["name"],
                "argv": command["argv"],
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode != 0 or (
            command.get("expected_stdout") is not None
            and completed.stdout.strip() != command["expected_stdout"]
        ):
            raise ProposalError(
                "failed",
                "native_verification_failed",
                f"{command['name']} did not satisfy its accepted obligation",
            )
    return {"status": "passed", "checks": checks}


def _apply_plan(
    root: Path,
    moves: list[dict[str, str]],
    edits: list[dict[str, str]],
) -> None:
    for move in moves:
        source, destination = root / move["from"], root / move["to"]
        if not source.is_file() or destination.exists():
            raise ProposalError(
                "failed", "disposable_plan_mismatch", f"move cannot apply: {move['from']}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    for edit in edits:
        path = root / edit["path"]
        text = path.read_text(encoding="utf-8")
        if text.count(edit["before"]) != 1:
            raise ProposalError(
                "failed", "disposable_plan_mismatch", f"edit is not unique: {edit['path']}"
            )
        path.write_text(text.replace(edit["before"], edit["after"], 1), encoding="utf-8")


def _after_tree(
    root: Path,
    envelope: dict[str, Any],
    dart: str,
    moves: list[dict[str, str]],
    edits: list[dict[str, str]],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dart-folder-after-") as temporary:
        disposable = Path(temporary) / "host"
        shutil.copytree(
            root,
            disposable,
            ignore=shutil.ignore_patterns(".git", "reports"),
            symlinks=True,
        )
        _apply_plan(disposable, moves, edits)
        result = _run_native(disposable, envelope, dart)
        result["disposable"] = True
        result["after_tree"] = [row["to"] for row in moves]
        return result


def _terminal(status: str, kind: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-folder-reorganization",
        "language": "dart",
        "read_only": True,
        "status": status,
        "recommendation": "refuse_untrusted_evidence",
        "failure_kind": kind,
        "message": detail,
        "target": None,
        "current_tree": [],
        "proposed_tree": [],
        "exact_moves": [],
        "exact_edits": [],
        "import_impact": [],
        "test_surface": [],
        "human_review_required": True,
        "limits": NON_CLAIMS,
    }


def _build(
    root: Path, evidence: Path, acceptance: Path, dart: str, before: dict[str, str]
) -> dict[str, Any]:
    validated = ACCEPTED.validate_accepted_evidence(
        root,
        evidence,
        acceptance,
        expected_producer="find-folder-topology-drift",
        expected_kind="dart_folder_reorganization_cluster",
    )
    envelope, selected = validated["envelope"], validated["selected_evidence"]
    wrapper = _read_json(evidence / envelope["producer"]["artifact"], "accepted D1 cluster wrapper")
    d1_artifact = _safe_relative(wrapper.get("d1_artifact"), "D1 artifact")
    d4_artifact = _safe_relative(wrapper.get("d4_artifact"), "D4 artifact")
    if not {d1_artifact, d4_artifact}.issubset(validated["verified_artifacts"]):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "named D1/D4 artifacts are not hash-bound"
        )
    _d1_cluster(evidence, d1_artifact, selected)
    facts = _fact_pack(
        evidence,
        d4_artifact,
        selected.get("d4_fact_pack_sha256"),
    )
    decision = selected.get("decision")
    if decision not in {"split", "cohesive"}:
        raise ProposalError("failed", "invalid_selection", "cluster decision is unsupported")
    parent = _safe_relative(selected.get("parent"), "cluster parent")
    prefix = selected.get("prefix")
    if (
        not parent.startswith("lib/")
        or not (root / parent).is_dir()
        or (root / parent).is_symlink()
        or not isinstance(prefix, str)
        or re.fullmatch(r"[a-z][a-z0-9_]*", prefix) is None
    ):
        raise ProposalError("failed", "invalid_selection", "cluster target is unsafe")
    current_native = _run_native(root, envelope, dart)
    if _snapshot(root) != before:
        raise ProposalError(
            "failed",
            "source_mutation_detected",
            "current-tree native verification changed the host",
        )
    base = {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-folder-reorganization",
        "language": "dart",
        "read_only": True,
        "acceptance_hash": envelope["acceptance_hash"],
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "target": {"parent": parent, "prefix": prefix},
        "human_review_required": True,
        "limits": NON_CLAIMS,
        "native_verification": {"current_tree": current_native},
        "source_preservation": {"verified": True, "snapshot": before},
    }
    if decision == "cohesive":
        return {
            **base,
            "status": "deferred",
            "recommendation": "defer_cohesive_cluster",
            "failure_kind": None,
            "message": selected["rationale"],
            "current_tree": selected["files"],
            "proposed_tree": [],
            "exact_moves": [],
            "exact_edits": [],
            "import_impact": [],
            "test_surface": [],
            "public_compatibility": {"claim": "no_change_proposed"},
        }
    if selected.get("convention") != CONVENTION:
        return {
            **base,
            "status": "deferred",
            "recommendation": "defer_project_convention_required",
            "failure_kind": None,
            "message": "An explicit Dart folder convention was not accepted.",
            "current_tree": selected["files"],
            "proposed_tree": [],
            "exact_moves": [],
            "exact_edits": [],
            "import_impact": [],
            "test_surface": [],
            "public_compatibility": {"claim": "no_change_proposed"},
        }
    if (
        facts.get("boundaries")
        or facts.get("unresolved_requests")
        or facts.get("missing_capabilities")
        or any(row.get("severity") == 1 for row in facts.get("diagnostics", []))
    ):
        raise ProposalError(
            "partial", "unresolved_import_impact", "D4 import impact contains unresolved boundaries"
        )

    members = selected.get("files")
    if not isinstance(members, list) or len(members) < 3 or len(set(members)) != len(members):
        raise ProposalError(
            "failed", "invalid_selection", "cluster must contain three direct siblings"
        )
    roles = {row["path"]: row.get("role") for row in facts["source_inventory"]}
    citations = _citation_index(envelope)
    symbol_by_path = {
        row["source"]: row
        for row in facts["document_symbols"]
        if row.get("top_level") and row.get("source") in members
    }
    member_citations: dict[str, str] = {}
    moves: list[dict[str, str]] = []
    destination_by_source: dict[str, str] = {}
    for member in members:
        relative = _safe_relative(member, "cluster member")
        path = Path(relative)
        if (
            path.parent.as_posix() != parent
            or not path.name.startswith(f"{prefix}_")
            or path.suffix != ".dart"
            or roles.get(relative) != "production"
            or (root / relative).is_symlink()
        ):
            raise ProposalError(
                "failed", "invalid_selection", f"cluster member is ineligible: {relative}"
            )
        symbol = symbol_by_path.get(relative)
        if symbol is None:
            raise ProposalError(
                "partial", "member_identity_unresolved", f"no D4 declaration cites {relative}"
            )
        member_citations[relative] = _citation(
            citations, relative, symbol["line"], symbol["column"]
        )
        suffix = path.stem.removeprefix(f"{prefix}_")
        destination = f"{parent}/{prefix}/{suffix}.dart"
        if (root / destination).exists():
            raise ProposalError(
                "partial", "destination_exists", f"proposed path already exists: {destination}"
            )
        destination_by_source[relative] = destination
        moves.append(
            {
                "from": relative,
                "to": destination,
                "citation": member_citations[relative],
            }
        )
    moves.sort(key=lambda row: row["from"])
    cluster_set = set(members)
    impacts = [
        row
        for row in facts["module_edges"]
        if any(target["path"] in cluster_set for target in row.get("targets", []))
    ]
    if any(edge["specifier"].startswith("package:") for edge in impacts):
        raise ProposalError(
            "partial",
            "public_package_uri_uncertainty",
            "a selected member is reached through a package URI",
        )
    touched_targets = {
        target["path"]
        for edge in impacts
        for target in edge["targets"]
        if target["path"] in cluster_set
    }
    if touched_targets != cluster_set:
        raise ProposalError(
            "partial",
            "import_impact_incomplete",
            "not every cluster member has resolved import impact",
        )
    edits: list[dict[str, str]] = []
    impact_rows: list[dict[str, Any]] = []
    for edge in impacts:
        targets = [target["path"] for target in edge["targets"] if target["path"] in cluster_set]
        if len(targets) != 1:
            raise ProposalError(
                "partial",
                "import_impact_ambiguous",
                "one directive resolves to multiple cluster members",
            )
        source_after = destination_by_source.get(edge["source"], edge["source"])
        target_after = destination_by_source[targets[0]]
        new_specifier = os.path.relpath(
            target_after,
            start=Path(source_after).parent.as_posix(),
        )
        source_path = root / edge["source"]
        try:
            before_line = source_path.read_text(encoding="utf-8").splitlines()[edge["line"] - 1]
        except (OSError, UnicodeDecodeError, IndexError) as exc:
            raise ProposalError(
                "failed", "stale_import_impact", f"directive is stale: {edge['source']}"
            ) from exc
        if before_line.count(edge["specifier"]) != 1:
            raise ProposalError(
                "failed", "stale_import_impact", f"directive is ambiguous: {edge['source']}"
            )
        after_line = before_line.replace(edge["specifier"], new_specifier, 1)
        citation = _edge_citation(citations, root, edge)
        edit = {
            "path": source_after,
            "before": before_line,
            "after": after_line,
            "kind": f"rewrite_{edge['kind']}_specifier",
            "citation": citation,
        }
        edits.append(edit)
        impact_rows.append(
            {
                "source": edge["source"],
                "kind": edge["kind"],
                "before": edge["specifier"],
                "after": new_specifier,
                "target_before": targets[0],
                "target_after": target_after,
                "citation": citation,
            }
        )
    edits.sort(key=lambda row: (row["path"], row["before"]))
    impact_rows.sort(key=lambda row: (row["source"], row["before"]))
    barrel_candidates = [
        edge
        for edge in impacts
        if edge["kind"] == "export"
        and {target["path"] for target in edge["targets"] if target["path"] in cluster_set}
    ]
    by_barrel: dict[str, int] = {}
    for edge in barrel_candidates:
        by_barrel[edge["source"]] = by_barrel.get(edge["source"], 0) + 1
    barrel_path = next(
        (path for path, count in sorted(by_barrel.items()) if count == len(cluster_set)),
        None,
    )
    if barrel_path is None:
        raise ProposalError(
            "partial", "public_compatibility_unresolved", "no single barrel preserves all members"
        )
    root_barrel_edges = [
        edge
        for edge in facts["module_edges"]
        if edge["kind"] == "export"
        and any(target["path"] == barrel_path for target in edge.get("targets", []))
    ]
    if not root_barrel_edges:
        raise ProposalError(
            "partial",
            "public_compatibility_unresolved",
            "cluster barrel is not publicly re-exported",
        )
    root_barrels = [
        {
            "path": edge["source"],
            "citation": _edge_citation(citations, root, edge),
        }
        for edge in root_barrel_edges
    ]
    test_surface = sorted(
        [
            {
                "path": row["path"],
                "sha256": row["sha256"],
                "citation": f"{row['path']}:sha256:{row['sha256']}",
            }
            for row in facts["source_inventory"]
            if row.get("role") == "test-excluded"
            and row.get("path", "").endswith(".dart")
            and isinstance(row.get("sha256"), str)
        ],
        key=lambda row: row["path"],
    )
    if not test_surface:
        raise ProposalError(
            "partial", "characterization_surface_missing", "no Dart characterization test exists"
        )
    after_native = _after_tree(root, envelope, dart, moves, edits)
    if _snapshot(root) != before:
        raise ProposalError(
            "failed", "source_mutation_detected", "disposable verification changed the audited host"
        )
    return {
        **base,
        "status": "ready_for_human_review",
        "recommendation": "review_folder_plan",
        "failure_kind": None,
        "message": "One accepted Dart prefix cluster has a complete, natively verified move plan.",
        "current_tree": sorted(members),
        "proposed_tree": sorted(row["to"] for row in moves),
        "exact_moves": moves,
        "exact_edits": edits,
        "import_impact": impact_rows,
        "accounting": {
            "cluster_members": len(members),
            "planned_members": len(moves),
            "resolved_edges": len(impacts),
            "planned_edges": len(edits),
        },
        "test_surface": test_surface,
        "public_compatibility": {
            "barrel_path": barrel_path,
            "barrel_path_preserved": True,
            "root_barrels": root_barrels,
            "public_names_preserved": True,
            "direct_package_uri_consumers": "none_in_selected_graph",
        },
        "native_verification": {
            "current_tree": current_native,
            "disposable_after_tree": after_native,
        },
    }


def _render(payload: dict[str, Any]) -> str:
    target = payload.get("target") or {}
    lines = [
        f"# Dart folder proposal — {target.get('parent', 'refusal')}/{target.get('prefix', '')}",
        "",
        f"Status: `{payload['status']}`",
        f"Recommendation: `{payload['recommendation']}`",
        "",
        payload.get("message", ""),
        "",
    ]
    if payload["status"] in {"failed", "partial"}:
        lines.extend(
            [
                "## Refusal",
                "",
                f"The proposal stopped at `{payload.get('failure_kind')}`. No move plan was emitted.",
                "",
            ]
        )
    elif payload["status"] == "deferred":
        lines.extend(
            ["## Decision", "", "The accepted human judgment leaves this cluster in place.", ""]
        )
    else:
        lines.extend(["## Current and proposed trees", "", "```text"])
        lines.extend(payload["current_tree"])
        lines.extend(["=>", *payload["proposed_tree"], "```", "", "## Exact moves", ""])
        lines.extend(
            f"- `{row['from']}` → `{row['to']}` ({row['citation']})"
            for row in payload["exact_moves"]
        )
        lines.extend(["", "## Import and export impact", ""])
        lines.extend(
            f"- `{row['source']}`: `{row['before']}` → `{row['after']}` ({row['citation']})"
            for row in payload["import_impact"]
        )
        lines.extend(
            [
                "",
                "## Compatibility and tests",
                "",
                f"- Preserved barrel: `{payload['public_compatibility']['barrel_path']}`",
                "- Characterization tests: "
                + ", ".join(row["citation"] for row in payload["test_surface"]),
                "- Current and disposable after-trees passed the accepted D0 native matrix.",
                "",
            ]
        )
    lines.extend(["## Explicit limitations", ""])
    lines.extend(f"- {item}" for item in NON_CLAIMS)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--dart", default="dart")
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    try:
        inspection = _safe_output(root, args.inspection)
        proposal = _safe_output(root, args.proposal)
    except ProposalError as exc:
        parser.error(exc.detail)
    before = _snapshot(root)
    raw_evidence = (
        args.evidence_dir if args.evidence_dir.is_absolute() else root / args.evidence_dir
    )
    evidence = Path(os.path.realpath(raw_evidence.resolve(strict=False)))
    raw_acceptance = args.acceptance
    acceptance = raw_acceptance if raw_acceptance.is_absolute() else evidence / raw_acceptance
    try:
        payload = _build(root, evidence, acceptance, args.dart, before)
        exit_code = 0
    except ACCEPTED.AcceptedEvidenceError as exc:
        payload = _terminal(exc.status, exc.failure_kind, exc.detail)
        exit_code = 2
    except ProposalError as exc:
        payload = _terminal(exc.status, exc.failure_kind, exc.detail)
        exit_code = 2 if exc.status in {"failed", "partial"} else 0
    except (KeyError, TypeError, ValueError) as exc:
        payload = _terminal(
            "failed", "invalid_upstream_artifact", f"malformed accepted Dart evidence: {exc}"
        )
        exit_code = 2
    try:
        _write_artifacts(inspection, proposal, payload, _render(payload))
    except ProposalError as exc:
        parser.error(exc.detail)
    print(f"wrote Dart folder proposal artifacts: {inspection.parent}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
