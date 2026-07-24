#!/usr/bin/env python3
"""Emit enum-review-only C string-state leads from resolved field operations."""

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
    spec = importlib.util.spec_from_file_location("c_state_facts", path)
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
        operations = [
            row for row in facts["state_operations"]
            if provider.in_target(row, root, args.target) and not row.get("macro_expansion")
        ]
        deferred.extend(
            {"file": row["file"], "line": row["line"], "reason": "macro_expansion_unresolved"}
            for row in facts["state_operations"]
            if provider.in_target(row, root, args.target) and row.get("macro_expansion")
        )
        grouped = defaultdict(list)
        for row in operations:
            grouped[row["field_ast_id"]].append(row)
        declarations = {
            row["ast_id"]: row for row in facts["declarations"]
            if row["kind"] == "field"
        }
        for ast_id, rows in grouped.items():
            declaration = declarations.get(ast_id)
            if not declaration or declaration["name"] not in {"state", "status", "phase"}:
                continue
            if "char *" not in (declaration.get("type") or ""):
                continue
            literals = sorted({row["literal"] for row in rows if isinstance(row.get("literal"), str)})
            if len(literals) < 3:
                continue
            candidates.append({
                "owner": declaration["owner"], "field": declaration["name"],
                "file": declaration["file"], "line": declaration["line"],
                "type": declaration["type"], "literals": literals,
                "operations": rows, "classification": "enum_review_only",
                "human_verdict": "required", "automatic_migration": False,
            })
            deferred.append({
                "owner": declaration["owner"], "field": declaration["name"],
                "reason": "pointer_alias_or_external_mutation_unresolved",
            })
    else:
        deferred.append({"reason": facts["failure_kind"]})
    payload = {
        "schema_version": "c-implicit-state-v1", "language": "c",
        "status": facts["status"], "read_only": True,
        "analyzer": "clang-21-c17-resolved-field-string-operations",
        "target": args.target, "fact_pack_sha256": facts["fact_pack_sha256"],
        "candidates": candidates, "deferred": deferred,
        "summary": {"enum_review_only": len(candidates)},
        "limits": [*facts["limits"], "repeated direct string writes do not prove a closed state domain"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/implicit-state")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
