#!/usr/bin/env python3
"""Emit one bounded, read-only Rust module-boundary proposal."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


NON_CLAIMS = [
    "macros and procedural macro expansion",
    "build scripts, generated code, and include inputs",
    "cfg/feature/target variants beyond the checked all-features host target",
    "traits, blanket implementations, generics, and monomorphization",
    "unsafe invariants and FFI contracts",
    "public or semver compatibility for external consumers",
]


def _load_evidence() -> Any:
    candidates = [
        Path(__file__).with_name("rust_project_evidence.py"),
        Path(__file__).resolve().parents[2] / "_common/scripts/rust_proposal_evidence.py",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("rust_project_evidence", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    raise RuntimeError("rust_project_evidence.py copied dependency was not found")


EVIDENCE = _load_evidence()


def _terminal(
    args: argparse.Namespace,
    status: str,
    recommendation: str,
    kind: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "skill": "propose-boundary",
        "language": "rust",
        "analyzer": "cargo-locked-offline-plus-bounded-rust-source-evidence",
        "status": status,
        "recommendation": recommendation,
        "failure_kind": kind,
        "message": message,
        "target": {"path": args.target},
        "candidate_seams": [],
        "caller_impact": [],
        "defer_signals": [kind],
        "human_review_required": True,
        "explicit_non_claims": NON_CLAIMS,
    }


def _render(payload: dict[str, Any]) -> str:
    lines = [
        f"# Rust boundary proposal — {payload['target']['path']}",
        "",
        f"Status: {payload['status']}",
        f"Recommendation: {payload['recommendation']}",
        "",
        payload.get("message", ""),
        "",
    ]
    seams = payload.get("candidate_seams", [])
    if seams:
        lines.extend(["## Candidate boundary", ""])
        for seam in seams:
            lines.extend(
                [
                    f"### {seam['cluster_id']}",
                    "",
                    f"- Module: {seam['module_path']}",
                    f"- Members: {', '.join(seam['members'])}",
                    f"- Proposed public API: {', '.join(seam['proposed_public_api']) or 'none'}",
                    f"- Cross-domain references: {len(seam['cross_domain_references'])}",
                    "",
                ]
            )
    lines.extend(["## Caller impact", ""])
    impacts = payload.get("caller_impact", [])
    if impacts:
        lines.extend(["| Caller | Module path |", "|---|---|"])
        lines.extend(f"| {row['file']} | {row['path']} |" for row in impacts)
    else:
        lines.append("No bounded first-party path impacts were found.")
    lines.extend(
        [
            "",
            "## Human review boundary",
            "",
            "This artifact is evidence for a human boundary decision. It does not authorize extraction or source edits.",
            "Review ownership, cohesion, private cross-domain calls, external callers, and compatibility before approving work.",
            "",
            "## Native verification",
            "",
        ]
    )
    native = payload.get("native_verification")
    if native:
        lines.append(f"- Current tree: {native['status']}")
        lines.extend(f"- {command}" for command in native["commands"])
    else:
        lines.append("Native verification did not reach a trusted result.")
    lines.extend(["", "## Explicit non-claims", ""])
    lines.extend(f"- {item}" for item in NON_CLAIMS)
    return "\n".join(lines).rstrip() + "\n"


def _direct_modules(
    root: Path, target: Path, project: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    by_path = {row["path"]: row for row in project["files"]}
    if target.is_file():
        relative = target.relative_to(root).as_posix()
        row = by_path.get(relative)
        if row is None or row["generated"] or row["test_like"]:
            return [], ["excluded_target"]
        return [row], row["unsupported"]
    module_file = target / "mod.rs"
    declarations: set[str] = set()
    if module_file.is_file():
        facts = by_path.get(module_file.relative_to(root).as_posix())
        declarations = {row["name"] for row in (facts or {}).get("module_declarations", [])}
    rows = []
    unsupported = []
    for path in sorted(target.glob("*.rs")):
        if path.name == "mod.rs":
            continue
        facts = by_path.get(path.relative_to(root).as_posix())
        if facts is None or facts["generated"] or facts["test_like"]:
            continue
        if declarations and path.stem not in declarations:
            continue
        rows.append(facts)
        unsupported.extend(facts["unsupported"])
    return rows, sorted(set(unsupported))


def build(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = Path(args.project_root).resolve()
    try:
        target = EVIDENCE.safe_project_path(root, args.target)
        project = EVIDENCE.collect_project(root)
        modules, unsupported = _direct_modules(root, target, project)
        if not modules:
            kind = "excluded_target" if target.is_file() else "no_eligible_rust_modules"
            recommendation = "defer_excluded_target" if target.is_file() else "defer_no_seam"
            return (
                _terminal(
                    args,
                    "complete",
                    recommendation,
                    kind,
                    "No eligible production Rust modules were selected.",
                ),
                0,
            )
        if unsupported:
            payload = _terminal(
                args,
                "partial",
                "defer_unsupported_rust_shape",
                unsupported[0],
                "Relevant Rust source uses a shape this bounded proposal does not resolve.",
            )
            payload["defer_signals"] = unsupported
            payload["project_evidence"] = {
                key: project[key]
                for key in (
                    "schema_version",
                    "tools",
                    "packages",
                    "source_fingerprints",
                )
            }
            return payload, 0
        native = EVIDENCE.run_native(
            root,
            smoke_package=args.smoke_package,
            smoke_expected=args.smoke_expected,
        )
        if len(modules) < 2:
            payload = _terminal(
                args,
                "complete",
                "defer_no_seam",
                "single_cluster_no_seam",
                "The target has one eligible module domain; no extraction seam is supported.",
            )
            payload["failure_kind"] = None
            payload["native_verification"] = native
            payload["defer_signals"] = ["single_cluster_no_seam"]
            return payload, 0
        candidates = []
        for module in modules:
            symbols = [row for row in module["declarations"] if row["kind"] != "mod"]
            if len(symbols) < 3:
                continue
            name = Path(module["path"]).stem
            references = []
            for other in modules:
                if other["path"] == module["path"]:
                    continue
                pattern = f"super::{name}::"
                if pattern in other["semantic_text"]:
                    references.append({"file": other["path"], "path": pattern.rstrip(":")})
            candidates.append(
                {
                    "cluster_id": name,
                    "module_path": module["path"],
                    "members": [row["name"] for row in symbols],
                    "proposed_public_api": [row["name"] for row in symbols if row["public"]],
                    "cross_domain_references": references,
                    "score": len(symbols) + (4 * len(references)),
                }
            )
        candidates.sort(key=lambda row: (-row["score"], row["cluster_id"]))
        if not candidates:
            payload = _terminal(
                args,
                "complete",
                "defer_no_seam",
                "insufficient_domain_evidence",
                "No module has enough named declarations for a useful boundary proposal.",
            )
            payload["native_verification"] = native
            return payload, 0
        selected = candidates[:1]
        caller_impact = []
        for file in project["files"]:
            if file["generated"] or file["test_like"]:
                continue
            for candidate in selected:
                name = candidate["cluster_id"]
                for token in (f"legacy::{name}", f"::{name}::"):
                    if token in file["semantic_text"] and file["path"] != candidate["module_path"]:
                        caller_impact.append({"file": file["path"], "path": token.strip(":")})
                        break
        return (
            {
                "schema_version": 1,
                "skill": "propose-boundary",
                "language": "rust",
                "analyzer": "cargo-locked-offline-plus-bounded-rust-source-evidence",
                "status": "complete",
                "recommendation": "review_boundary",
                "message": "One bounded module-domain candidate is ready for human review.",
                "target": {
                    "path": target.relative_to(root).as_posix(),
                    "module_count": len(modules),
                },
                "candidate_seams": selected,
                "caller_impact": caller_impact,
                "defer_signals": [],
                "human_review_required": True,
                "project_evidence": {
                    key: project[key]
                    for key in (
                        "schema_version",
                        "tools",
                        "packages",
                        "source_fingerprints",
                    )
                },
                "native_verification": native,
                "explicit_non_claims": NON_CLAIMS,
            },
            0,
        )
    except EVIDENCE.EvidenceFailure as exc:
        recommendation = (
            "defer_incomplete_evidence" if exc.status == "partial" else "defer_failed_evidence"
        )
        return (
            _terminal(args, exc.status, recommendation, exc.kind, exc.message),
            exc.exit_code,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--target", required=True)
    parser.add_argument("--inspection", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--smoke-package")
    parser.add_argument("--smoke-expected")
    args = parser.parse_args()
    payload, exit_code = build(args)
    root = Path(args.project_root).resolve()
    try:
        EVIDENCE.write_artifacts(root, args.inspection, args.proposal, payload, _render(payload))
    except EVIDENCE.EvidenceFailure as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if exit_code:
        print(payload["message"], file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
