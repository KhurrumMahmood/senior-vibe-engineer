#!/usr/bin/env python3
"""Emit review-only C dormant-function leads from Clang direct facts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _provider():
    candidates = [Path(__file__).with_name("c_semantic_facts.py")]
    candidates.extend(parent / "_c-semantic/c_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("c_dormant_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    provider = _provider()
    parser = provider.common_parser(__doc__)
    args = parser.parse_args()
    root = args.project_root.resolve()
    facts = provider.load_or_collect(project_root=root, facts=args.facts, clang=args.clang)
    candidates = []
    deferred = []
    if facts["status"] == "complete":
        references = facts["direct_references"]
        for declaration in facts["declarations"]:
            if not (
                declaration["kind"] == "function"
                and declaration["definition"]
                and declaration["linkage"] == "internal"
                and provider.in_target(declaration, root, args.target)
            ):
                continue
            declaration_ids = {
                row["ast_id"] for row in facts["declarations"]
                if row["kind"] == "function" and row["linkage"] == "internal"
                and row["file"] == declaration["file"] and row["name"] == declaration["name"]
            }
            matching = [row for row in references if row.get("target_ast_id") in declaration_ids]
            if declaration.get("macro_expansion") or any(row.get("macro_expansion") for row in matching):
                deferred.append({
                    "name": declaration["name"], "file": declaration["file"],
                    "line": declaration["line"], "reason": "macro_expansion_unresolved",
                })
            elif any(row["context"] == "value_or_address" for row in matching):
                deferred.append({
                    "name": declaration["name"], "file": declaration["file"],
                    "line": declaration["line"],
                    "reason": "function_pointer_or_dynamic_registration",
                })
            elif not matching:
                candidates.append({
                    "name": declaration["name"], "file": declaration["file"],
                    "line": declaration["line"], "linkage": "internal",
                    "direct_reference_count": 0, "classification": "review_required",
                    "certain_delete": False,
                })
        for boundary in facts["boundaries"]:
            if boundary["kind"] == "function_pointer_call" and provider.in_target(boundary, root, args.target):
                deferred.append({**boundary, "reason": "function_pointer_or_dynamic_registration"})
    else:
        deferred.append({"reason": facts["failure_kind"]})
    payload = {
        "schema_version": "c-dormant-v1", "language": "c",
        "status": facts["status"], "read_only": True,
        "analyzer": "clang-21-c17-direct-references", "target": args.target,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "candidates": candidates, "deferred": deferred,
        "summary": {"review_required": len(candidates), "certain_delete": 0},
        "limits": [*facts["limits"], "zero direct static use is a review lead, never deletion authority"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/find-dormant")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
