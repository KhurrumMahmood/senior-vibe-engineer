#!/usr/bin/env python3
"""Render one content-addressed read-only C++ shadow-unification proposal."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _tools():
    candidates = [Path(__file__).with_name("cpp_proposal_tools.py")]
    candidates.extend(parent / "_cpp-semantic/cpp_proposal_tools.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C++ proposal helper is missing")
    spec = importlib.util.spec_from_file_location("cpp_unify_shadows_tools", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


T = _tools()
CHOICES = {"keep_separate_document_why", "share_utilities", "complete_migration", "merge_at_workflow"}
STOP_CONDITIONS = [
    "stop if accepted fact-pack, analysis, compile-database, or source hashes change",
    "stop on any overload-resolution, template-specialization, operator, ADL, virtual-dispatch, callback, or function-pointer ambiguity",
    "stop on any external linkage, symbol visibility, mangled-name, ODR, ABI, layout, RTTI, exception, calling-convention, or binary-compatibility change",
    "stop until characterization covers values, side effects, allocation/lifetime, ordering, I/O, concurrency, reentrancy, and undefined behavior",
    "source mutation requires separate human acceptance and a fresh native test plus executable smoke",
]


def _analysis(path: Path, facts: dict) -> dict:
    payload = T.load_json(path, "semantic duplication analysis")
    if (
        payload.get("schema_version") != "cpp-semantic-duplication-v1"
        or payload.get("language") != "cpp"
        or payload.get("status") != "complete"
        or payload.get("read_only") is not True
        or payload.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
    ):
        raise T.ProposalError("analysis_invalid", "complete fact-bound C++ duplication analysis required")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--finding-index", type=int, default=0)
    parser.add_argument("--choice", choices=sorted(CHOICES), default="share_utilities")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--clangxx", default="clang++")
    parser.add_argument("--make", default="make")
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve()
        output = T.output_dir(root, args.output_dir, "unify-shadows")
        facts_path, facts = T.fact_pack(root, args.facts)
        analysis_path = T.safe_path(root, args.analysis, "duplication analysis")
        analysis = _analysis(analysis_path, facts)
        leads = analysis.get("leads", [])
        if args.finding_index < 0 or args.finding_index >= len(leads):
            raise T.ProposalError("selection_invalid", "finding index selects no exact C++ lead")
        lead = leads[args.finding_index]
        if (
            lead.get("classification") != "static_structural_review_lead"
            or lead.get("automatic_consolidation") is not False
            or len(lead.get("functions", [])) != 2
        ):
            raise T.ProposalError("selection_invalid", "selected lead is not a bounded two-function structural lead")
        declarations = {row["symbol_key"]: row for row in facts["declarations"] if row["definition"]}
        functions = []
        for row in lead["functions"]:
            declaration = declarations.get(row["symbol_key"])
            if declaration is None or declaration["template"] or declaration["operator"]:
                raise T.ProposalError("symbol_unresolved", "exact non-template non-operator definitions required")
            functions.append({
                **row,
                "resolved_type": declaration["type"],
                "linkage": declaration["linkage"],
                "namespace": declaration["namespace"],
            })
        before_sources = T.audited_sources(root)
        native = T.native_proof(root, args.clangxx, args.make)
        if not native["passed"]:
            raise T.ProposalError("native_baseline_failed", "current C++ test/smoke failed")
        if T.audited_sources(root) != before_sources:
            raise T.ProposalError("source_mutated", "read-only unification proposal changed sources")
        boundary_counts = {
            kind: sum(1 for row in facts["boundaries"] if row["kind"] == kind)
            for kind in ("overload_set", "template", "operator", "virtual_dispatch", "function_pointer_or_dynamic_call", "odr_header_definition")
        }
        scope = {
            "schema_version": "cpp-unify-shadows-scope-v1",
            "language": "cpp",
            "status": "review_required",
            "read_only": True,
            "source_mutations": 0,
            "selected_choice": args.choice,
            "functions": functions,
            "static_return_shape": lead["return_shape"],
            "boundary_counts": boundary_counts,
            "characterization_required": ["return values", "side effects", "allocation and lifetime", "exceptions", "ordering", "I/O", "concurrency and reentrancy", "undefined behavior"],
            "stop_conditions": STOP_CONDITIONS,
        }
        evidence = {
            "schema_version": "cpp-unify-shadows-evidence-v1",
            "language": "cpp",
            "status": "proposal_ready",
            "read_only": True,
            "human_acceptance": "required",
            "facts": {"path": facts_path.relative_to(root).as_posix(), "sha256": T.sha256(facts_path), "fact_pack_sha256": facts["fact_pack_sha256"]},
            "analysis": {"path": analysis_path.relative_to(root).as_posix(), "sha256": T.sha256(analysis_path)},
            "source_files": before_sources,
            "native_proof": native,
            "nonclaims": ["static structural identity is not behavioral equivalence", "the proposal grants no mutation authority", "ODR and ABI compatibility are not established"],
        }
        names = " and ".join(f"`{row['qualified_name']}`" for row in functions)
        markdown = f"# C++ shadow-unification proposal\n\nSelected `{args.choice}` for {names}. The evidence supports only a characterized shared-utility investigation. Host sources were not changed.\n\n## Stop conditions\n\n" + "\n".join(f"- {row}" for row in STOP_CONDITIONS) + "\n"
        T.replace_bundle(output, {
            "scope.json": T.json_text(scope),
            "evidence.json": T.json_text(evidence),
            "proposal.md": markdown,
        })
        return 0
    except T.ProposalError as exc:
        print(f"propose_cpp.py: {exc.kind}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
