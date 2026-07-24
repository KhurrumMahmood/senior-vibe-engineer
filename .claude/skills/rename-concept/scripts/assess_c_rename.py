#!/usr/bin/env python3
"""Assess one C concept rename without editing source."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


def _provider():
    candidates = [Path(__file__).with_name("c_semantic_facts.py")]
    candidates.extend(parent / "_c-semantic/c_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("c_rename_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _selected_files(provider, facts: dict, root: Path, target: str) -> set[str]:
    selected_tus = {
        row["path"] for row in facts["source_inventory"]
        if row["path"].endswith((".c", ".i")) and row["role"] == "production"
        and provider.in_target({"file": row["path"]}, root, target)
    }
    selected = set(selected_tus)
    for translation_unit in selected_tus:
        selected.update(facts.get("dependency_closure", {}).get(translation_unit, []))
    return selected


def main() -> int:
    provider = _provider()
    parser = provider.common_parser(__doc__)
    parser.add_argument("old")
    parser.add_argument("new")
    args = parser.parse_args()
    root = args.project_root.resolve()
    facts = provider.load_or_collect(project_root=root, facts=args.facts, clang=args.clang)
    declarations = {"old": [], "new": []}
    resolved = {"old": [], "new": []}
    residue = []
    if facts["status"] == "complete":
        selected_files = _selected_files(provider, facts, root, args.target)
        for band, term in (("old", args.old), ("new", args.new)):
            matching = [
                row for row in facts["declarations"]
                if row["name"] == term and row["file"] in selected_files
                and row["kind"] in {"typedef", "enum", "record"}
            ]
            typedefs = [row for row in matching if row["kind"] == "typedef"]
            declarations[band] = typedefs or matching
            resolved[band] = [
                row for row in facts["direct_references"]
                if row.get("name") == term and row["file"] in selected_files
            ]
            for relative in sorted(selected_files):
                path = root / relative
                for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if not re.search(rf"\b{re.escape(term)}\b", line):
                        continue
                    if re.match(r"\s*#", line):
                        residue.append({"term": term, "file": relative, "line": line_number, "kind": "macro_or_inactive_variant"})
                    if re.search(rf"['\"][^'\"]*\b{re.escape(term)}\b[^'\"]*['\"]", line):
                        residue.append({"term": term, "file": relative, "line": line_number, "kind": "string_literal"})
        if declarations["old"] or declarations["new"]:
            residue.append({
                "kind": "external_consumers", "term": args.old,
                "reason": "public headers and external binary/source consumers are outside the compile-command closure",
            })
    else:
        residue.append({"kind": "semantic_evidence_incomplete", "reason": facts["failure_kind"]})
    if declarations["old"] and declarations["new"]:
        verdict = "HALF-APPLIED / INCOMPLETE"
    elif declarations["new"] and not declarations["old"]:
        verdict = "CANDIDATE COMPLETE — EXTERNAL REVIEW REQUIRED"
    else:
        verdict = "INCOMPLETE"
    payload = {
        "schema_version": "c-rename-assessment-v1", "language": "c",
        "status": facts["status"], "read_only": True, "assess_only": True,
        "source_mutated": False, "old_concept": args.old, "new_concept": args.new,
        "verdict": verdict, "declarations": declarations,
        "resolved_direct_references": resolved,
        "unresolved_residue": list({str(row): row for row in residue}.values()),
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "limits": [*facts["limits"], "assessment only: macro/string/inactive variants, ABI compatibility, and external consumers remain unresolved"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/rename-concept")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
