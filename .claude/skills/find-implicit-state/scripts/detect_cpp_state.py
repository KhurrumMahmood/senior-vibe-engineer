#!/usr/bin/env python3
"""Find repeated exact C++ field string writes as enum-class review leads."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path


def _provider():
    candidates = [Path(__file__).with_name("cpp_semantic_facts.py")]
    candidates.extend(parent / "_cpp-semantic/cpp_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C++ semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("cpp_state_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _literal(value):
    if isinstance(value, str) and value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def main() -> int:
    provider = _provider()
    parser = provider.common_parser(__doc__)
    args = parser.parse_args()
    root = args.project_root.resolve()
    facts = provider.load_or_collect(project_root=root, facts=args.facts, clangxx=args.clangxx)
    candidates = []
    deferred = []
    if facts["status"] == "complete":
        fields = {
            row["ast_id"]: row for row in facts["declarations"]
            if row["kind"] == "field" and row["name"] in {"state", "status", "phase"}
        }
        operations = defaultdict(list)
        for row in facts["state_operations"]:
            if provider.in_target(row, root, args.target):
                operations[row["field_ast_id"]].append({**row, "literal": _literal(row["literal"])})
        for ast_id, rows in operations.items():
            field = fields.get(ast_id)
            if field is None:
                continue
            if field["type"] != "const char *":
                deferred.append({"owner": field["owner"], "field": field["name"], "reason": "non_exact_field_type"})
                continue
            literals = sorted({row["literal"] for row in rows if isinstance(row["literal"], str)})
            if len(literals) < 3:
                continue
            candidates.append({
                "owner": field["owner"],
                "field": field["name"],
                "file": field["file"],
                "line": field["line"],
                "type": field["type"],
                "literals": literals,
                "operations": rows,
                "classification": "enum_class_review_only",
                "human_verdict": "required",
                "automatic_migration": False,
            })
            deferred.extend([
                {"owner": field["owner"], "field": field["name"], "reason": "constructor_default_and_special_members_unresolved"},
                {"owner": field["owner"], "field": field["name"], "reason": "alias_callback_external_and_variant_writes_unresolved"},
                {"owner": field["owner"], "field": field["name"], "reason": "enum_class_layout_abi_storage_and_wire_compatibility_unresolved"},
            ])
    else:
        deferred.append({"reason": facts["failure_kind"]})
    payload = {
        "schema_version": "cpp-implicit-state-v1",
        "language": "cpp",
        "status": facts["status"],
        "read_only": True,
        "analyzer": "clang++-21-c++20-resolved-field-string-writes",
        "target": args.target,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "candidates": candidates,
        "deferred": deferred,
        "summary": {"enum_class_review_only": len(candidates)},
        "limits": [*facts["limits"], "repeated direct writes do not prove a closed state domain or authorize enum-class migration"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/implicit-state")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
