#!/usr/bin/env python3
"""Assess one namespace-aware C++ concept rename without editing source."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


def _provider():
    candidates = [Path(__file__).with_name("cpp_semantic_facts.py")]
    candidates.extend(parent / "_cpp-semantic/cpp_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C++ semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("cpp_rename_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _selected_files(provider, facts: dict, root: Path, target: str) -> set[str]:
    selected_tus = {
        row["path"] for row in facts["source_inventory"]
        if Path(row["path"]).suffix in provider.SOURCE_SUFFIXES
        and row["role"] == "production"
        and provider.in_target({"file": row["path"]}, root, target)
    }
    selected = set(selected_tus)
    for translation_unit in selected_tus:
        selected.update(facts.get("dependency_closure", {}).get(translation_unit, []))
    return selected


def _declarations(rows: list[dict]) -> list[dict]:
    grouped = {}
    for row in rows:
        key = (row["symbol_key"], row["file"], row["line"], row["kind"])
        if key not in grouped:
            grouped[key] = {**row, "translation_unit_observations": 0}
        grouped[key]["translation_unit_observations"] += 1
    for row in grouped.values():
        row.pop("ast_id", None)
        row.pop("previous_ast_id", None)
    return list(grouped.values())


def main() -> int:
    provider = _provider()
    parser = provider.common_parser(__doc__)
    parser.add_argument("old")
    parser.add_argument("new")
    args = parser.parse_args()
    root = args.project_root.resolve()
    facts = provider.load_or_collect(project_root=root, facts=args.facts, clangxx=args.clangxx)
    declarations = {"old": [], "new": []}
    resolved = {"old": [], "new": []}
    spellings = {"old": [], "new": []}
    residue = []
    if facts["status"] == "complete":
        selected = _selected_files(provider, facts, root, args.target)
        for band, term in (("old", args.old), ("new", args.new)):
            declarations[band] = _declarations([
                row for row in facts["declarations"]
                if row["name"] == term and row["file"] in selected
                and row["kind"] in {"type_alias", "typedef", "enum", "record"}
            ])
            resolved[band] = [
                row for row in facts["direct_references"]
                if row.get("name") == term and row["file"] in selected
            ]
            pattern = re.compile(rf"\b{re.escape(term)}\b")
            for relative in sorted(selected):
                path = root / relative
                for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if not pattern.search(line):
                        continue
                    row = {"term": term, "file": relative, "line": number, "syntax": line.strip()[:220]}
                    spellings[band].append(row)
                    if re.match(r"\s*#", line):
                        residue.append({**row, "kind": "macro_or_inactive_variant"})
                    if re.search(rf"['\"][^'\"]*\b{re.escape(term)}\b[^'\"]*['\"]", line):
                        residue.append({**row, "kind": "string_literal"})
        if declarations["old"] or declarations["new"]:
            residue.extend([
                {"kind": "external_consumers_and_linkage", "reason": "public headers and out-of-tree source/binary consumers are outside the compile-command closure"},
                {"kind": "overloads_templates_operators_adl", "reason": "spelling replacement cannot prove overload, specialization, operator, or ADL identity"},
                {"kind": "odr_abi", "reason": "mangled names, ODR, layout, RTTI, serialization, and binary compatibility require separate approval"},
            ])
    else:
        residue.append({"kind": "semantic_evidence_incomplete", "reason": facts["failure_kind"]})
    if declarations["old"] and declarations["new"]:
        verdict = "HALF-APPLIED / INCOMPLETE"
    elif declarations["new"] and not declarations["old"]:
        verdict = "CANDIDATE COMPLETE — ODR/ABI/EXTERNAL REVIEW REQUIRED"
    else:
        verdict = "INCOMPLETE"
    payload = {
        "schema_version": "cpp-rename-assessment-v1",
        "language": "cpp",
        "status": facts["status"],
        "read_only": True,
        "assess_only": True,
        "source_mutated": False,
        "old_concept": args.old,
        "new_concept": args.new,
        "verdict": verdict,
        "declarations": declarations,
        "resolved_direct_references": resolved,
        "textual_spellings": spellings,
        "unresolved_residue": list({str(row): row for row in residue}.values()),
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "limits": [*facts["limits"], "assessment only: a namespace-aware declaration census plus exact spellings is not mutation authority"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/rename-concept")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
