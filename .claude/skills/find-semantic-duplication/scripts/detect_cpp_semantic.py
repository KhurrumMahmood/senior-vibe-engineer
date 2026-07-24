#!/usr/bin/env python3
"""Emit structural C++ semantic-duplication leads without equivalence claims."""

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
    spec = importlib.util.spec_from_file_location("cpp_duplication_facts", path)
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
    leads, rejected, deferred = [], [], []
    if facts["status"] == "complete":
        returns = [
            row for row in facts["aggregate_initializers"]
            if row["context"] == "return" and row.get("function")
            and provider.in_target(row, root, args.target) and not row["macro_expansion"]
        ]
        by_function = {row["function"]: row for row in returns}
        definitions = {}
        by_qualified = defaultdict(list)
        for row in facts["declarations"]:
            if row["kind"] == "function" and row["definition"] and provider.in_target(row, root, args.target):
                by_qualified[row["qualified_name"]].append(row)
        for qualified, rows in by_qualified.items():
            keys = {row["symbol_key"] for row in rows}
            if len(keys) == 1:
                definitions[qualified] = rows[0]
            else:
                deferred.append({"qualified_name": qualified, "reason": "overload_set_not_collapsed"})
        callers = defaultdict(set)
        for row in facts["direct_references"]:
            if row["context"] == "direct_call" and row.get("function") and row.get("name"):
                callers[row["name"]].add(row["function"])
        names = sorted(set(by_function) & set(definitions))
        for index, left_name in enumerate(names):
            left = by_function[left_name]
            left_decl = definitions[left_name]
            if left_decl["template"] or left_decl["operator"]:
                deferred.append({"qualified_name": left_name, "reason": "template_or_operator_unresolved"})
                continue
            for right_name in names[index + 1 :]:
                right = by_function[right_name]
                right_decl = definitions[right_name]
                if right_decl["template"] or right_decl["operator"]:
                    continue
                if left["record"] != right["record"] or left["fields"] != right["fields"] or left["snippet"] != right["snippet"]:
                    continue
                left_callers = sorted(callers[left_decl["name"]])
                right_callers = sorted(callers[right_decl["name"]])
                if not left_callers or not right_callers or left_callers == right_callers:
                    rejected.append({"functions": [left_name, right_name], "reason": "distinct_resolved_caller_contexts_not_established"})
                    continue
                leads.append({
                    "classification": "static_structural_review_lead",
                    "functions": [
                        {"qualified_name": name, "symbol_key": definitions[name]["symbol_key"], "file": definitions[name]["file"], "line": definitions[name]["line"], "direct_callers": sorted(callers[definitions[name]["name"]])}
                        for name in (left_name, right_name)
                    ],
                    "return_shape": {"record": left["record"], "designated_fields": left["fields"], "exact_snippet": left["snippet"]},
                    "human_verdict": "required",
                    "automatic_consolidation": False,
                    "boundary": "compiler-resolved static structure only; never behavioral equivalence, ODR/ABI safety, or safe consolidation",
                })
        for kind in ("function_pointer_or_dynamic_call", "template", "operator", "virtual_dispatch", "overload_set", "odr_header_definition"):
            count = sum(1 for row in facts["boundaries"] if row["kind"] == kind)
            if count:
                deferred.append({"reason": f"{kind}_unresolved", "count": count})
    else:
        deferred.append({"reason": facts["failure_kind"]})
    payload = {
        "schema_version": "cpp-semantic-duplication-v1",
        "language": "cpp",
        "status": facts["status"],
        "read_only": True,
        "analyzer": "clang++-21-resolved-static-return-shape+callers",
        "target": args.target,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "leads": leads,
        "rejected": rejected,
        "deferred": deferred,
        "summary": {"static_structural_review_leads": len(leads)},
        "limits": [*facts["limits"], "matching resolved signatures, aggregate fields, snippets, and caller contexts never establish behavioral equivalence"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/semantic-duplication")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
