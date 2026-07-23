#!/usr/bin/env python3
"""Render one accepted, read-only Dart library-boundary proposal."""

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


SCHEMA_VERSION = "dart-boundary-proposal-v1"
NON_CLAIMS = [
    "selected-configuration static evidence does not prove the runtime graph",
    "external consumers, semver compatibility, reflection, and dynamic invocation remain unresolved",
    "conditional imports/exports, parts, augmentations, and generated APIs are outside this ready shape",
    "Flutter routes, widgets, assets, plugins, and framework boundaries are not inferred",
    "the artifact proposes a plan and grants no source-mutation authority",
]


class ProposalError(RuntimeError):
    """A typed refusal local to the Dart boundary consumer."""

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
    spec = importlib.util.spec_from_file_location("dart_boundary_accepted_evidence", path)
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
    allowed = root / "reports" / "propose-boundary"
    if not _contained(allowed, output) or output == allowed:
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


def _load_fact_pack(evidence: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    artifact = envelope["producer"]["artifact"]
    facts = _read_json(evidence / artifact, "D4 query pack")
    supplied = facts.get("fact_pack_sha256")
    unhashed = dict(facts)
    unhashed.pop("fact_pack_sha256", None)
    if supplied != _canonical_hash(unhashed):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "D4 fact-pack hash does not verify"
        )
    if facts.get("schema_version") != "dart-lsp-facts-v1" or facts.get("status") != "complete":
        raise ProposalError("partial", "upstream_not_complete", "D4 query pack is not complete")
    return facts


def _safe_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProposalError("failed", "invalid_selection", f"{label} is missing")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ProposalError("failed", "invalid_selection", f"{label} is unsafe")
    return value


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
        raise ProposalError("failed", "stale_query_pack", f"cannot cite edge in {path}") from exc
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
    commands: list[dict[str, Any]] = []
    for row in rows:
        name, raw = row.get("name"), row.get("argv")
        if not isinstance(raw, list) or not raw or raw[0] != "dart":
            raise ProposalError(
                "failed", "invalid_native_obligations", "native command must invoke Dart"
            )
        if row.get("expected_returncode") != 0:
            raise ProposalError(
                "failed", "invalid_native_obligations", "native command must expect success"
            )
        expected: list[str]
        if name == "analyze":
            expected = ["dart", "analyze", "--fatal-infos", "--fatal-warnings", "."]
            if raw != expected:
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
        commands.append({**row, "argv": [dart, *raw[1:]]})
    return commands


def _run_native(root: Path, envelope: dict[str, Any], dart: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for command in _native_commands(envelope, root, dart):
        try:
            result = subprocess.run(
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
        check = {
            "name": command["name"],
            "argv": command["argv"],
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        checks.append(check)
        expected_stdout = command.get("expected_stdout")
        if result.returncode != 0 or (
            expected_stdout is not None and result.stdout.strip() != expected_stdout
        ):
            raise ProposalError(
                "failed",
                "native_verification_failed",
                f"{command['name']} did not satisfy its accepted obligation",
            )
    return {"status": "passed", "checks": checks}


def _apply_plan(root: Path, edits: list[dict[str, str]], creates: list[dict[str, str]]) -> None:
    for edit in edits:
        path = root / edit["path"]
        text = path.read_text(encoding="utf-8")
        if text.count(edit["before"]) != 1:
            raise ProposalError(
                "failed", "disposable_plan_mismatch", f"exact edit is not unique: {edit['path']}"
            )
        path.write_text(text.replace(edit["before"], edit["after"], 1), encoding="utf-8")
    for create in creates:
        path = root / create["path"]
        if path.exists():
            raise ProposalError(
                "failed", "disposable_plan_mismatch", f"create path exists: {create['path']}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(create["contents"], encoding="utf-8")


def _after_tree(
    root: Path,
    envelope: dict[str, Any],
    dart: str,
    edits: list[dict[str, str]],
    creates: list[dict[str, str]],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dart-boundary-after-") as temporary:
        disposable = Path(temporary) / "host"
        shutil.copytree(
            root,
            disposable,
            ignore=shutil.ignore_patterns(".git", "reports"),
            symlinks=True,
        )
        _apply_plan(disposable, edits, creates)
        result = _run_native(disposable, envelope, dart)
        result["disposable"] = True
        result["created_paths"] = [row["path"] for row in creates]
        return result


def _terminal(status: str, kind: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-boundary",
        "language": "dart",
        "read_only": True,
        "status": status,
        "recommendation": "refuse_untrusted_evidence",
        "failure_kind": kind,
        "message": detail,
        "target": None,
        "public_api": [],
        "caller_impact": [],
        "test_surface": [],
        "exact_edits": [],
        "create_files": [],
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
        expected_producer="map-subsystem",
        expected_kind="dart_boundary_proposal",
    )
    envelope = validated["envelope"]
    selection = validated["selected_evidence"]
    facts = _load_fact_pack(evidence, envelope)
    target = _safe_relative(selection.get("target"), "selected target")
    target_path = root / target
    if not target_path.is_dir() or target_path.is_symlink() or not target.startswith("lib/"):
        raise ProposalError(
            "failed", "invalid_selection", "selected target is not a Dart library directory"
        )
    name = selection.get("boundary_name")
    if not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_]*", name) is None:
        raise ProposalError(
            "failed", "invalid_selection", "boundary name is not a Dart library name"
        )
    decision = selection.get("decision")
    if decision not in {"extract", "defer_cohesive"}:
        raise ProposalError("failed", "invalid_selection", "boundary decision is unsupported")
    if (
        facts.get("boundaries")
        or facts.get("unresolved_requests")
        or facts.get("missing_capabilities")
        or any(row.get("severity") == 1 for row in facts.get("diagnostics", []))
    ):
        raise ProposalError(
            "partial",
            "unresolved_semantic_boundary",
            "the accepted selected-configuration graph contains unresolved or unsupported edges",
        )

    current_native = _run_native(root, envelope, dart)
    if _snapshot(root) != before:
        raise ProposalError(
            "failed",
            "source_mutation_detected",
            "current-tree native verification changed the host",
        )
    base = {
        "schema_version": SCHEMA_VERSION,
        "skill": "propose-boundary",
        "language": "dart",
        "read_only": True,
        "acceptance_hash": envelope["acceptance_hash"],
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "target": {"path": target, "boundary_name": name},
        "human_review_required": True,
        "limits": NON_CLAIMS,
        "native_verification": {"current_tree": current_native},
        "source_preservation": {"verified": True, "snapshot": before},
    }
    if decision == "defer_cohesive":
        return {
            **base,
            "status": "deferred",
            "recommendation": "defer_cohesive_target",
            "failure_kind": None,
            "message": selection["rationale"],
            "public_api": [],
            "caller_impact": [],
            "test_surface": [],
            "exact_edits": [],
            "create_files": [],
            "public_compatibility": {"claim": "no_change_proposed"},
        }

    production = {
        row["path"] for row in facts["source_inventory"] if row.get("role") == "production"
    }
    selected_files = {path for path in production if path.startswith(f"{target}/")}
    if len(selected_files) < 2:
        raise ProposalError(
            "partial", "cohesive_or_insufficient_target", "target has no useful multi-file seam"
        )
    citations = _citation_index(envelope)
    public_api = []
    for row in facts["document_symbols"]:
        if (
            row.get("top_level")
            and row.get("source") in selected_files
            and isinstance(row.get("name"), str)
            and not row["name"].startswith("_")
        ):
            public_api.append(
                {
                    "name": row["name"],
                    "kind": row["kind"],
                    "path": row["source"],
                    "line": row["line"],
                    "column": row["column"],
                    "citation": _citation(citations, row["source"], row["line"], row["column"]),
                }
            )
    public_api.sort(key=lambda row: (row["path"], row["line"], row["name"]))
    if not public_api:
        raise ProposalError("partial", "public_api_unresolved", "target public API is empty")

    inbound_edges = [
        row
        for row in facts["module_edges"]
        if row["source"] not in selected_files
        and any(target_row["path"] in selected_files for target_row in row["targets"])
    ]
    barrel_edges = [row for row in inbound_edges if row["kind"] == "export"]
    if not barrel_edges:
        raise ProposalError(
            "partial", "public_compatibility_unresolved", "no resolved public barrel reaches target"
        )
    barrel_edges.sort(key=lambda row: (len(Path(row["source"]).parts), row["source"], row["line"]))
    barrel = barrel_edges[0]
    barrel_citation = _edge_citation(citations, root, barrel)
    caller_paths: dict[str, list[str]] = {}
    for row in facts["reference_queries"]:
        if row.get("declaration", {}).get("path") not in selected_files:
            continue
        for ref in row.get("references", []):
            if ref["path"] in production and ref["path"] not in selected_files:
                caller_paths.setdefault(ref["path"], []).append(
                    _citation(citations, ref["path"], ref["line"], ref["column"])
                )
    if not caller_paths:
        raise ProposalError(
            "partial", "caller_impact_unresolved", "no resolved first-party caller cites target API"
        )
    caller_impact = [
        {"path": path, "citations": sorted(set(path_citations))}
        for path, path_citations in sorted(caller_paths.items())
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
            "partial",
            "characterization_surface_missing",
            "no Dart characterization test surface exists",
        )
    new_library = f"lib/{name}.dart"
    if (root / new_library).exists():
        raise ProposalError(
            "partial", "compatibility_library_exists", "proposed public library path already exists"
        )
    if len(barrel.get("targets", [])) != 1:
        raise ProposalError(
            "partial", "public_compatibility_unresolved", "public barrel target is ambiguous"
        )
    target_barrel = barrel["targets"][0]["path"]
    export_from_new = Path(target_barrel).relative_to("lib").as_posix()
    contents = f"export '{export_from_new}';\n"
    barrel_path = root / barrel["source"]
    line = barrel_path.read_text(encoding="utf-8").splitlines()[barrel["line"] - 1]
    before_line = line
    after_line = line.replace(barrel["specifier"], f"{name}.dart", 1)
    edits = [
        {
            "path": barrel["source"],
            "before": before_line,
            "after": after_line,
            "kind": "preserve_root_barrel_via_new_public_library",
            "citation": barrel_citation,
        }
    ]
    creates = [{"path": new_library, "contents": contents}]
    after_native = _after_tree(root, envelope, dart, edits, creates)
    if _snapshot(root) != before:
        raise ProposalError(
            "failed", "source_mutation_detected", "disposable verification changed the audited host"
        )
    return {
        **base,
        "status": "ready_for_human_review",
        "recommendation": "review_boundary",
        "failure_kind": None,
        "message": "One accepted Dart child domain has a cited, natively verified library seam.",
        "public_api": public_api,
        "caller_impact": caller_impact,
        "module_edges": [
            {
                "source": row["source"],
                "kind": row["kind"],
                "specifier": row["specifier"],
                "targets": row["targets"],
                "citation": _edge_citation(citations, root, row),
            }
            for row in inbound_edges
        ],
        "test_surface": test_surface,
        "exact_edits": edits,
        "create_files": creates,
        "public_compatibility": {
            "root_barrel": barrel["source"],
            "root_barrel_citation": barrel_citation,
            "root_barrel_preserved": True,
            "old_internal_paths_preserved": True,
            "new_public_library": new_library,
            "external_consumer_semver": "unresolved_human_review_required",
        },
        "native_verification": {
            "current_tree": current_native,
            "disposable_after_tree": after_native,
        },
    }


def _render(payload: dict[str, Any]) -> str:
    title = payload.get("target") or {}
    lines = [
        f"# Dart boundary proposal — {title.get('path', 'refusal')}",
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
                f"The proposal stopped at `{payload.get('failure_kind')}`. No extraction plan was emitted.",
                "",
            ]
        )
    elif payload["status"] == "deferred":
        lines.extend(
            [
                "## Decision",
                "",
                "The accepted human decision keeps this cohesive target in place.",
                "",
            ]
        )
    else:
        lines.extend(["## Public API", ""])
        lines.extend(f"- `{row['name']}` — {row['citation']}" for row in payload["public_api"])
        lines.extend(["", "## Caller impact", ""])
        lines.extend(
            f"- `{row['path']}` — {', '.join(row['citations'])}" for row in payload["caller_impact"]
        )
        lines.extend(["", "## Exact plan", ""])
        lines.extend(
            f"- Create `{row['path']}` with `{row['contents'].strip()}`"
            for row in payload["create_files"]
        )
        lines.extend(
            f"- Edit `{row['path']}`: `{row['before']}` → `{row['after']}` ({row['citation']})"
            for row in payload["exact_edits"]
        )
        lines.extend(
            [
                "",
                "## Compatibility and tests",
                "",
                f"- Root barrel preserved: `{payload['public_compatibility']['root_barrel']}`",
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
    print(f"wrote Dart boundary proposal artifacts: {inspection.parent}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
