#!/usr/bin/env python3
"""Emit static C semantic-duplication review leads without equivalence claims."""

from __future__ import annotations

import importlib.util
import sys
from collections import defaultdict
from pathlib import Path


def _provider():
    candidates = [Path(__file__).with_name("c_semantic_facts.py")]
    candidates.extend(parent / "_c-semantic/c_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("c_duplication_facts", path)
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
    leads = []
    rejected = []
    deferred = []
    if facts["status"] == "complete":
        returns = [
            row for row in facts["compound_literals"]
            if row["context"] == "return" and row.get("function")
            and provider.in_target(row, root, args.target) and not row.get("macro_expansion")
        ]
        deferred.extend(
            {"file": row["file"], "line": row["line"], "reason": "macro_expansion_unresolved"}
            for row in facts["compound_literals"]
            if row["context"] == "return" and row.get("function")
            and provider.in_target(row, root, args.target) and row.get("macro_expansion")
        )
        by_function = {row["function"]: row for row in returns}
        definitions_by_name = defaultdict(list)
        for row in facts["declarations"]:
            if (
                row["kind"] == "function" and row["definition"]
                and row["linkage"] == "external"
                and provider.in_target(row, root, args.target)
            ):
                definitions_by_name[row["name"]].append(row)
        definitions = {
            name: rows[0] for name, rows in definitions_by_name.items() if len(rows) == 1
        }
        callers = defaultdict(set)
        for row in facts["direct_references"]:
            if row["context"] == "direct_call" and row.get("function"):
                callers[row["name"]].add(row["function"])
        names = sorted(set(by_function) & set(definitions))
        for index, left_name in enumerate(names):
            left = by_function[left_name]
            for right_name in names[index + 1 :]:
                right = by_function[right_name]
                if left["record"] != right["record"] or left["fields"] != right["fields"]:
                    continue
                pair = [left_name, right_name]
                left_callers = sorted(callers[left_name])
                right_callers = sorted(callers[right_name])
                if not left_callers or not right_callers or left_callers == right_callers:
                    rejected.append({"functions": pair, "reason": "distinct_direct_caller_contexts_not_established"})
                    continue
                leads.append({
                    "classification": "static_review_lead",
                    "functions": [
                        {"name": name, "file": definitions[name]["file"], "line": definitions[name]["line"],
                         "direct_callers": sorted(callers[name])}
                        for name in pair
                    ],
                    "return_shape": {"record": left["record"], "designated_fields": left["fields"]},
                    "human_verdict": "required", "automatic_consolidation": False,
                    "boundary": "static review lead only; never behavioral equivalence or safe consolidation",
                })
        if any(row["kind"] == "function_pointer_call" for row in facts["boundaries"]):
            deferred.append({"reason": "function_pointer_call_graph_unresolved"})
    else:
        deferred.append({"reason": facts["failure_kind"]})
    payload = {
        "schema_version": "c-semantic-duplication-v1", "language": "c",
        "status": facts["status"], "read_only": True,
        "analyzer": "clang-21-static-return-shape+direct-callers",
        "target": args.target, "fact_pack_sha256": facts["fact_pack_sha256"],
        "leads": leads, "rejected": rejected, "deferred": deferred,
        "summary": {"static_review_leads": len(leads)},
        "limits": [*facts["limits"], "matching static shapes never establish behavioral equivalence, alias safety, UB equivalence, or consolidation safety"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/semantic-duplication")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
