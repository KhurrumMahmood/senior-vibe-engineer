#!/usr/bin/env python3
"""Produce bounded Rust identifier evidence for rename-concept assessment."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


def _facts_module():
    candidates = [Path(__file__).with_name("rust_semantic_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "rust_semantic_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Rust semantic fact pack is missing")
    spec = importlib.util.spec_from_file_location("rust_rename_facts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _target(root: Path, sources: list[str]) -> str:
    for source in sources:
        path = (root / source).resolve()
        for parent in [path.parent, *path.parents]:
            if parent == root.parent:
                break
            if (parent / "Cargo.toml").is_file():
                return parent.relative_to(root).as_posix()
    raise ValueError("no Cargo package contains the selected Rust sources")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--old-terms", required=True)
    parser.add_argument("--new-terms", required=True)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--rust-analyzer", default="rust-analyzer")
    args = parser.parse_args()
    root = args.project_root.resolve()
    old_terms = json.loads(args.old_terms)
    new_terms = json.loads(args.new_terms)
    sources = json.loads(args.sources)
    target = _target(root, sources)
    facts = _facts_module().collect(
        root,
        target,
        [*old_terms, *new_terms],
        cargo=args.cargo,
        rustc=args.rustc,
        rust_analyzer=args.rust_analyzer,
    )
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    old_keys, new_keys = set(old_terms), set(new_terms)
    declarations = {"old": [], "new": []}
    authority = {"old": [], "new": []}
    for symbol in facts.get("document_symbols", []):
        bucket = (
            "old"
            if symbol.get("name") in old_keys
            else ("new" if symbol.get("name") in new_keys else None)
        )
        if bucket is None or roles.get(symbol["source"]) != "production-module":
            continue
        row = {
            "name": symbol["name"],
            "file": symbol["source"],
            "line": symbol["line"],
            "kind": symbol.get("kind"),
        }
        declarations[bucket].append(row)
        line = (
            (root / symbol["source"]).read_text(encoding="utf-8").splitlines()[symbol["line"] - 1]
        )
        if re.search(
            rf"^\s*pub\s+(?:struct|enum|trait|type)\s+{re.escape(symbol['name'])}\b", line
        ):
            authority[bucket].append(row)
    occurrences, deferred = [], []
    for edge in facts.get("definition_edges", []):
        bucket = (
            "old"
            if edge.get("name") in old_keys
            else ("new" if edge.get("name") in new_keys else None)
        )
        if bucket is None:
            continue
        line = (root / edge["source"]).read_text(encoding="utf-8").splitlines()[edge["line"] - 1]
        classification = "unrelated_symbol"
        target_declarations = declarations[bucket]
        unsafe_or_ffi = any(
            row["source"] == edge["source"] and row["start_line"] <= edge["line"] <= row["end_line"]
            for row in facts.get("unsafe_ffi_boundaries", [])
        )
        macro_region = any(
            row["source"] == edge["source"] and row["start_line"] <= edge["line"] <= row["end_line"]
            for row in facts.get("macro_regions", [])
        )
        generic_or_trait = bool(
            re.search(
                r"\b(?:dyn|impl|trait|where)\b|[A-Za-z_][A-Za-z0-9_:]*\s*<",
                line,
            )
        )
        if unsafe_or_ffi or macro_region:
            classification = "deferred_unsafe_ffi_or_macro"
            deferred.append(
                {
                    "file": edge["source"],
                    "line": edge["line"],
                    "kind": "unsafe_ffi_or_macro_reference",
                    "term": edge["name"],
                    "reason": "unsafe/FFI/macro reference is outside rename authority",
                }
            )
        elif generic_or_trait:
            classification = "deferred_trait_or_generic"
            deferred.append(
                {
                    "file": edge["source"],
                    "line": edge["line"],
                    "kind": "trait_or_generic_reference",
                    "term": edge["name"],
                    "reason": "trait/generic reference is outside rename authority",
                }
            )
        elif any(
            any(
                item.get("file") == decl["file"] and item.get("line") == decl["line"]
                for item in edge.get("definitions", [])
            )
            for decl in target_declarations
        ):
            classification = f"{bucket}_concept_symbol"
        elif not edge.get("definitions"):
            kind = (
                "reflection_or_string"
                if re.search(r'["\']', line)
                else (
                    "comment_or_macro" if "//" in line or "!" in line else "unresolved_identifier"
                )
            )
            deferred.append(
                {
                    "file": edge["source"],
                    "line": edge["line"],
                    "kind": kind,
                    "term": edge["name"],
                    "reason": "stable LSP did not resolve this lexical occurrence to rename authority",
                }
            )
            classification = "deferred_lexical_occurrence"
        occurrences.append(
            {
                "file": edge["source"],
                "line": edge["line"],
                "name": edge["name"],
                "classification": classification,
                "syntax": line.strip()[:180],
            }
        )
    for boundary in facts.get("cfg_boundaries", []):
        source = root / boundary["source"]
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        window = lines[boundary["line"] - 1 : boundary["line"] + 3]
        for term in [*old_terms, *new_terms]:
            if any(term in line for line in window):
                deferred.append(
                    {
                        "file": boundary["source"],
                        "line": boundary["line"],
                        "kind": "cfg_variant_reference",
                        "term": term,
                        "reason": "cfg variant is outside selected rename authority",
                    }
                )
    for boundary in facts.get("attribute_boundaries", []):
        if boundary["classification"] != "procedural_or_unknown" and boundary["name"] != "derive":
            continue
        source = root / boundary["source"]
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        window = lines[boundary["line"] - 1 : boundary["line"] + 3]
        for term in [*old_terms, *new_terms]:
            if any(term in line for line in window):
                deferred.append(
                    {
                        "file": boundary["source"],
                        "line": boundary["line"],
                        "kind": "procedural_or_unknown_attribute_reference",
                        "term": term,
                        "reason": "procedural/unknown attribute is outside rename authority",
                    }
                )
    selected_roles = {"production-module"}
    for inventory in facts.get("source_inventory", []):
        if inventory["role"] in selected_roles:
            continue
        source = root / inventory["path"]
        if not source.is_file() or source.is_symlink():
            continue
        for line_no, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for term in [*old_terms, *new_terms]:
                if term in line:
                    deferred.append(
                        {
                            "file": inventory["path"],
                            "line": line_no,
                            "kind": f"{inventory['role']}_reference",
                            "term": term,
                            "reason": "excluded Cargo/source role is outside rename authority",
                        }
                    )
    authority_status = (
        "resolved" if len(authority["old"]) <= 1 and len(authority["new"]) == 1 else "ambiguous"
    )
    deferred = list(
        {json.dumps(row, sort_keys=True, ensure_ascii=False): row for row in deferred}.values()
    )
    status = (
        "resolved"
        if facts.get("status") == "complete"
        else ("failed" if facts.get("status") == "failed" else "partial")
    )
    payload = {
        "schema_version": "rust-rename-evidence-v1",
        "read_only": True,
        "language": "rust",
        "status": status,
        "analyzer": "cargo-compiler+rust-analyzer-selected-definitions",
        "authority_status": authority_status,
        "declarations": declarations,
        "public_type_authorities": authority,
        "occurrences": occurrences,
        "deferred_references": deferred,
        "inventory_ambiguities": [
            row for row in facts.get("source_inventory", []) if row["role"] == "symlink-excluded"
        ],
        "resolution_diagnostics": facts.get("compiler", {}).get("diagnostics", []),
        "uncovered_files": [
            source
            for source in sources
            if roles.get(source) != "production-module"
            and any(
                term in (root / source).read_text(encoding="utf-8", errors="replace")
                for term in [*old_terms, *new_terms]
            )
        ],
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "limits": facts.get("limits", []),
        "reason": facts.get("failure_kind"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
