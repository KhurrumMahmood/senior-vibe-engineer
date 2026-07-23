#!/usr/bin/env python3
"""Assess one Dart concept rename without changing source."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


def _provider():
    candidates = [Path(__file__).with_name("dart_lsp_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "dart_lsp_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Dart LSP fact provider is missing")
    spec = importlib.util.spec_from_file_location("dart_rename_lsp_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _type_declaration(root: Path, symbol: dict[str, Any]) -> bool:
    source = root / symbol["source"]
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    if symbol["line"] < 1 or symbol["line"] > len(lines):
        return False
    return bool(
        re.search(
            rf"\b(?:abstract\s+|base\s+|final\s+|interface\s+|sealed\s+)?(?:class|enum|mixin|extension\s+type|typedef)\s+{re.escape(symbol['name'])}\b",
            lines[symbol["line"] - 1],
        )
    )


def _lexical_evidence(
    root: Path, facts: dict[str, Any], old: str, new: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    strict: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for inventory in facts.get("source_inventory", []):
        source = root / inventory["path"]
        if not source.is_file() or source.is_symlink():
            continue
        for line_no, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for term, band in ((old, "old"), (new, "new")):
                for match in re.finditer(rf"\b{re.escape(term)}\b", line):
                    stripped = line.lstrip()
                    if "//" in line and match.start() >= line.index("//"):
                        kind = "comment_or_prose"
                    elif re.search(rf"['\"][^'\"]*\b{re.escape(term)}\b[^'\"]*['\"]", line):
                        kind = "string_literal"
                    else:
                        kind = "identifier_candidate"
                    row = {
                        "term": term,
                        "band": band,
                        "file": inventory["path"],
                        "line": line_no,
                        "column": match.start() + 1,
                        "kind": kind,
                        "role": inventory["role"],
                        "syntax": stripped[:180],
                    }
                    (strict if inventory["role"] == "production" else excluded).append(row)
    return strict, excluded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", default="lib")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    provider = _provider()
    facts = provider.load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        queries=[args.old, args.new],
        dart=args.dart,
        packages=args.packages,
        cache_dir=args.cache_dir,
        timeout=args.timeout,
    )
    authorities: dict[str, list[dict[str, Any]]] = {"old": [], "new": []}
    declarations: dict[str, list[dict[str, Any]]] = {"old": [], "new": []}
    unresolved_source_paths = {
        row.get("path")
        for row in facts.get("boundaries", [])
        if row.get("kind") in {"augmentation", "conditional-directive", "part"}
    }
    for symbol in facts.get("document_symbols", []):
        band = (
            "old"
            if symbol.get("name") == args.old
            else ("new" if symbol.get("name") == args.new else None)
        )
        if band is None or not symbol.get("top_level"):
            continue
        row = {
            "name": symbol["name"],
            "file": symbol["source"],
            "line": symbol["line"],
            "column": symbol["column"],
            "kind": symbol.get("kind"),
        }
        declarations[band].append(row)
        if (
            symbol["source"] not in unresolved_source_paths
            and not symbol["name"].startswith("_")
            and _type_declaration(root, symbol)
        ):
            authorities[band].append(row)
    authority_locations = {
        band: {(row["file"], row["line"]) for row in rows} for band, rows in authorities.items()
    }
    for symbol in facts.get("document_symbols", []):
        band = (
            "old"
            if symbol.get("name") == args.old
            else ("new" if symbol.get("name") == args.new else None)
        )
        if band is None or symbol.get("parent") != symbol.get("name"):
            continue
        if any(row["file"] == symbol["source"] for row in authorities[band]):
            authority_locations[band].add((symbol["source"], symbol["line"]))
    occurrences: list[dict[str, Any]] = []
    unresolved_identifiers: list[dict[str, Any]] = []
    for edge in facts.get("definition_queries", []):
        band = (
            "old"
            if edge.get("name") == args.old
            else ("new" if edge.get("name") == args.new else None)
        )
        if band is None:
            continue
        resolved = any(
            (target.get("path"), target.get("line")) in authority_locations[band]
            for target in edge.get("targets", [])
        )
        classification = (
            f"{band}_concept_symbol" if resolved else "unrelated_or_unresolved_identifier"
        )
        row = {
            "name": edge["name"],
            "file": edge["source"],
            "line": edge["line"],
            "column": edge["column"],
            "classification": classification,
            "targets": edge.get("targets", []),
        }
        occurrences.append(row)
        if not resolved:
            unresolved_identifiers.append(row)
    strict_text, excluded_text = _lexical_evidence(root, facts, args.old, args.new)
    strict_deferred = [row for row in strict_text if row["kind"] != "identifier_candidate"]
    old_resolved = [row for row in occurrences if row["classification"] == "old_concept_symbol"]
    new_resolved = [row for row in occurrences if row["classification"] == "new_concept_symbol"]
    rename_probes = {
        row["name"]: row
        for row in facts.get("rename_queries", [])
        if row.get("name") in {args.old, args.new}
    }
    reasons: list[str] = []
    if facts.get("status") != "complete":
        reasons.append("Dart semantic evidence is not complete")
    if len(authorities["new"]) != 1:
        reasons.append("exactly one public new-type authority is required")
    if authorities["old"] or old_resolved:
        reasons.append("retired identifier authority or resolved references remain")
    if any(row["band"] == "old" for row in strict_deferred):
        reasons.append("strict-text old-term evidence remains deferred")
    if unresolved_identifiers:
        reasons.append("same-spelled or unresolved identifiers cannot certify the rename")
    if args.new not in rename_probes or rename_probes[args.new].get("prepare") is None:
        reasons.append("read-only prepareRename evidence for the new authority is missing")
    complete = not reasons
    mixed = bool(authorities["old"] or old_resolved) and bool(authorities["new"] or new_resolved)
    verdict = "COMPLETE" if complete else ("HALF-APPLIED / INCOMPLETE" if mixed else "INCOMPLETE")
    status = (
        "complete" if complete else ("failed" if facts.get("status") == "failed" else "partial")
    )
    payload: dict[str, Any] = {
        "schema_version": "dart-rename-assessment-v1",
        "language": "dart",
        "read_only": True,
        "assess_only": True,
        "source_mutated": False,
        "old_concept": args.old,
        "new_concept": args.new,
        "verdict": verdict,
        "status": status,
        "authority_status": "resolved"
        if len(authorities["old"]) <= 1 and len(authorities["new"]) == 1
        else "ambiguous",
        "declarations": declarations,
        "public_type_authorities": authorities,
        "resolved_occurrences": occurrences,
        "old_resolved_reference_count": len(old_resolved),
        "new_resolved_reference_count": len(new_resolved),
        "unresolved_identifiers": unresolved_identifiers,
        "strict_text": {
            "status": "clean"
            if not any(row["band"] == "old" for row in strict_deferred)
            else "deferred",
            "evidence": strict_text,
            "deferred_evidence": strict_deferred,
            "excluded_scope_evidence": excluded_text,
        },
        "rename_probes": rename_probes,
        "reasons": reasons,
        "diagnostics": facts.get("diagnostics", []),
        "boundaries": facts.get("boundaries", []),
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "query_plan_sha256": facts.get("query_plan_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "limits": [
            *facts.get("limits", []),
            "assessment only: no codemod, compatibility, generated API, reflection/string completeness, or asset/route safety",
        ],
    }
    output = args.output if args.output.is_absolute() else root / args.output
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(root / "reports" / "rename-concept")
    except ValueError:
        parser.error("output must stay beneath reports/rename-concept/")
    if not relative.parts:
        parser.error("output must name an assessment file")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            parser.error("output must not traverse a symbolic link")
    _atomic(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote Dart rename assessment: {output}")
    return 2 if facts.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
