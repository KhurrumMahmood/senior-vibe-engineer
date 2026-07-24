#!/usr/bin/env python3
"""Emit conservative C++ dormant-function review leads."""

from __future__ import annotations

import importlib.util
import sys
from collections import defaultdict
from pathlib import Path


def _provider():
    candidates = [Path(__file__).with_name("cpp_semantic_facts.py")]
    candidates.extend(parent / "_cpp-semantic/cpp_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C++ semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("cpp_dormant_facts", path)
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
    facts = provider.load_or_collect(project_root=root, facts=args.facts, clangxx=args.clangxx)
    candidates = []
    deferred = []
    if facts["status"] == "complete":
        declarations_by_symbol = defaultdict(list)
        for row in facts["declarations"]:
            declarations_by_symbol[row["symbol_key"]].append(row)
        reference_ids = defaultdict(list)
        for row in facts["direct_references"]:
            reference_ids[row.get("target_ast_id")].append(row)
        seen = set()
        for declaration in facts["declarations"]:
            if not (
                declaration["kind"] == "function"
                and declaration["definition"]
                and provider.in_target(declaration, root, args.target)
                and declaration["symbol_key"] not in seen
            ):
                continue
            seen.add(declaration["symbol_key"])
            family = declarations_by_symbol[declaration["symbol_key"]]
            references = [
                reference
                for member in family
                for reference in reference_ids.get(member.get("ast_id"), [])
            ]
            reason = None
            if declaration["linkage"] != "internal":
                reason = "external_linkage_or_out_of_tree_consumers_unresolved"
            elif declaration["template"]:
                reason = "template_instantiations_unresolved"
            elif declaration["operator"]:
                reason = "operator_resolution_unresolved"
            elif declaration["macro_expansion"] or any(row["macro_expansion"] for row in references):
                reason = "macro_expansion_unresolved"
            elif any(row["context"] == "value_or_address" for row in references):
                reason = "function_pointer_callback_or_registration"
            elif references:
                continue
            if reason:
                deferred.append({
                    "qualified_name": declaration["qualified_name"],
                    "symbol_key": declaration["symbol_key"],
                    "file": declaration["file"],
                    "line": declaration["line"],
                    "reason": reason,
                })
            else:
                candidates.append({
                    "qualified_name": declaration["qualified_name"],
                    "symbol_key": declaration["symbol_key"],
                    "file": declaration["file"],
                    "line": declaration["line"],
                    "linkage": "internal",
                    "direct_reference_count": 0,
                    "classification": "review_required",
                    "certain_delete": False,
                })
        deferred.extend(
            {**row, "reason": "function_pointer_callback_or_registration"}
            for row in facts["boundaries"]
            if row["kind"] == "function_pointer_or_dynamic_call"
            and provider.in_target(row, root, args.target)
        )
    else:
        deferred.append({"reason": facts["failure_kind"]})
    payload = {
        "schema_version": "cpp-dormant-v1",
        "language": "cpp",
        "status": facts["status"],
        "read_only": True,
        "analyzer": "clang++-21-c++20-resolved-symbols",
        "target": args.target,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "candidates": candidates,
        "deferred": deferred,
        "summary": {"review_required": len(candidates), "certain_delete": 0},
        "limits": [*facts["limits"], "zero observed direct use of one internal non-template non-operator function is a review lead, never deletion authority"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/find-dormant")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
