#!/usr/bin/env python3
"""Emit one bounded, read-only Rust module-folder proposal."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


NON_CLAIMS = [
    "macros, procedural macros, build scripts, generated code, and include inputs",
    "cfg/feature/target variants beyond the checked all-features host target",
    "traits, generics, unsafe invariants, and FFI contracts",
    "external consumer paths, public API compatibility, or semver compatibility",
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
        "skill": "propose-folder-reorganization",
        "language": "rust",
        "analyzer": "cargo-locked-offline-plus-bounded-rust-source-evidence",
        "status": status,
        "recommendation": recommendation,
        "failure_kind": kind,
        "message": message,
        "target": {"parent": args.parent, "prefix": args.prefix},
        "cluster_files": [],
        "exact_source_edits": [],
        "new_module_file": None,
        "defer_signals": [kind],
        "human_review_required": True,
        "public_compatibility": {"claim": "not_proved"},
        "explicit_non_claims": NON_CLAIMS,
    }


def _render(payload: dict[str, Any]) -> str:
    target = payload["target"]
    lines = [
        f"# Rust folder reorganization proposal — {target['parent']}::{target['prefix']}",
        "",
        f"Status: {payload['status']}",
        f"Recommendation: {payload['recommendation']}",
        "",
        payload.get("message", ""),
        "",
    ]
    if payload.get("cluster_files"):
        lines.extend(
            [
                "## Exact move and edit plan",
                "",
                "| Current | Proposed |",
                "|---|---|",
            ]
        )
        lines.extend(
            f"| {row['current_path']} | {row['new_path']} |" for row in payload["cluster_files"]
        )
        lines.extend(["", "### Exact source edits", ""])
        lines.extend(
            f"- {row['path']}: {row['before']} -> {row['after']}"
            for row in payload["exact_source_edits"]
        )
        module = payload["new_module_file"]
        lines.extend(
            [
                "",
                f"### New {module['path']}",
                "",
                "    " + module["contents"].replace("\n", "\n    ").rstrip(),
                "",
            ]
        )
    lines.extend(
        [
            "## Human review boundary",
            "",
            "The human split judgment and project convention authorize a proposal only, not source mutation.",
            "Review module ownership, navigation value, all recorded paths, and compatibility before applying the plan.",
            "",
            "## Public compatibility",
            "",
            "Public and semver compatibility are not proved. The plan removes old public module paths unless a human adds an explicit compatibility phase.",
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


def build(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = Path(args.project_root).resolve()
    try:
        parent = EVIDENCE.safe_project_path(root, args.parent)
        project = EVIDENCE.collect_project(root)
        if args.cluster_judgment == "cohesive":
            return (
                _terminal(
                    args,
                    "deferred",
                    "defer_cohesive_cluster",
                    "human_cohesive_judgment",
                    "The human judged this cluster cohesive; no move plan was emitted.",
                ),
                0,
            )
        if args.project_convention != "allow-module-group":
            return (
                _terminal(
                    args,
                    "deferred",
                    "defer_project_convention_required",
                    "project_convention_required",
                    "An explicit project convention is required before proposing a Rust module group.",
                ),
                0,
            )
        by_path = {row["path"]: row for row in project["files"]}
        members = []
        for path in sorted(parent.glob(f"{args.prefix}_*.rs")):
            facts = by_path.get(path.relative_to(root).as_posix())
            if facts is None or facts["generated"] or facts["test_like"]:
                continue
            members.append(facts)
        if len(members) < 3:
            return (
                _terminal(
                    args,
                    "deferred",
                    "defer_cluster_below_threshold",
                    "cluster_below_threshold",
                    "Fewer than three eligible direct Rust module siblings match the prefix.",
                ),
                0,
            )
        unsupported = sorted({signal for row in members for signal in row["unsupported"]})
        if unsupported:
            payload = _terminal(
                args,
                "partial",
                "defer_unsupported_rust_shape",
                unsupported[0],
                "A selected module uses a Rust shape this bounded move-impact proposal does not resolve.",
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
        parent_relative = parent.relative_to(root).as_posix()
        cluster_files = []
        module_names = []
        for facts in members:
            path = Path(facts["path"])
            suffix = path.stem.removeprefix(f"{args.prefix}_")
            module_names.append((path.stem, suffix))
            cluster_files.append(
                {
                    "current_path": facts["path"],
                    "new_path": f"{parent_relative}/{args.prefix}/{suffix}.rs",
                    "module_before": path.stem,
                    "module_after": f"{args.prefix}::{suffix}",
                }
            )
        parent_module_candidates = [
            parent / "lib.rs",
            parent / "mod.rs",
            parent / "main.rs",
        ]
        parent_module = next((path for path in parent_module_candidates if path.is_file()), None)
        if parent_module is None:
            payload = _terminal(
                args,
                "partial",
                "defer_parent_module_ambiguity",
                "parent_module_missing",
                "No conventional lib.rs, main.rs, or mod.rs owns the selected siblings.",
            )
            payload["native_verification"] = native
            return payload, 0
        owner_text = parent_module.read_text(encoding="utf-8")
        declarations = []
        for old, _new in module_names:
            match = re.search(
                rf"(?m)^\s*(?:pub\s+)?mod\s+{re.escape(old)}\s*;\s*$",
                owner_text,
            )
            if match is None:
                payload = _terminal(
                    args,
                    "partial",
                    "defer_module_declaration_ambiguity",
                    "module_declaration_missing",
                    f"Conventional declaration for {old} was not found.",
                )
                payload["native_verification"] = native
                return payload, 0
            declarations.append(match.group(0).strip())
        declaration_block = "\n".join(declarations)
        if declaration_block not in owner_text:
            payload = _terminal(
                args,
                "partial",
                "defer_module_declaration_ambiguity",
                "module_declarations_not_contiguous",
                "Selected module declarations are not one exact contiguous block.",
            )
            payload["native_verification"] = native
            return payload, 0
        owner_relative = parent_module.relative_to(root).as_posix()
        source_edits = [
            {
                "path": owner_relative,
                "before": declaration_block,
                "after": f"pub mod {args.prefix};",
                "kind": "module_declarations",
            }
        ]
        for file in project["files"]:
            if file["generated"] or file["test_like"]:
                continue
            for old, new in module_names:
                before = f"{old}::"
                after = f"{args.prefix}::{new}::"
                if before in file["semantic_text"]:
                    source_edits.append(
                        {
                            "path": file["path"],
                            "before": before,
                            "after": after,
                            "kind": "bounded_first_party_path_token",
                        }
                    )
        new_module_contents = "".join(f"pub mod {new};\n" for _old, new in module_names)
        return (
            {
                "schema_version": 1,
                "skill": "propose-folder-reorganization",
                "language": "rust",
                "analyzer": "cargo-locked-offline-plus-bounded-rust-source-evidence",
                "status": "ready_for_human_review",
                "recommendation": "review_folder_plan",
                "message": "A bounded conventional module-folder plan is ready for human review.",
                "target": {"parent": parent_relative, "prefix": args.prefix},
                "cluster_files": cluster_files,
                "exact_source_edits": source_edits,
                "new_module_file": {
                    "path": f"{parent_relative}/{args.prefix}/mod.rs",
                    "contents": new_module_contents,
                },
                "defer_signals": [],
                "human_review_required": True,
                "project_convention": args.project_convention,
                "public_compatibility": {
                    "claim": "not_proved",
                    "old_public_module_paths_removed": [old for old, _new in module_names],
                },
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
    parser.add_argument("--parent", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--cluster-judgment", choices=("split", "cohesive"), required=True)
    parser.add_argument(
        "--project-convention",
        choices=("allow-module-group", "unspecified"),
        default="unspecified",
    )
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
