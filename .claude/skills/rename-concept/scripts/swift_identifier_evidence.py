#!/usr/bin/env python3
"""Assess a Swift concept rename with swiftc declaration authority."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path


TYPE_KINDS = {5, 10, 11, 23}


def _provider():
    candidates = [Path(__file__).with_name("swift_semantic_facts.py")]
    for parent in Path(__file__).resolve().parents:
        candidates.extend(
            [
                parent / "_swift-semantic-readonly/swift_semantic_facts.py",
                parent / ".claude/skills/_swift-semantic-readonly/swift_semantic_facts.py",
            ]
        )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Swift semantic provider is missing")
    spec = importlib.util.spec_from_file_location("swift_rename_semantic_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _safe_output(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports/rename-concept"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must stay beneath reports/rename-concept/") from exc
    if not relative.parts:
        raise ValueError("output must name an assessment file")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValueError("output must not traverse a symbolic link")
    return output


def _write(output: Path, payload: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
        output = _safe_output(root, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    provider = _provider()
    try:
        facts = provider.load_fact_pack(args.facts, root, args.target_name, [args.old, args.new])
    except provider.SwiftFactError as exc:
        payload = {
            "schema_version": "swift-rename-evidence-v1",
            "language": "swift",
            "status": "failed",
            "reason": exc.kind,
            "failure_detail": str(exc),
            "authority_status": "unavailable",
            "mutation_applied": False,
            "deferred_references": [],
            "summary": {"old_symbol_references": 0, "new_symbol_references": 0},
        }
        _write(output, payload)
        return 2
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    authorities: dict[str, list[dict]] = {"old": [], "new": []}
    for symbol in facts.get("symbols", []):
        bucket = (
            "old"
            if symbol.get("name") == args.old
            else ("new" if symbol.get("name") == args.new else None)
        )
        if (
            bucket is None
            or symbol.get("kind") not in TYPE_KINDS
            or roles.get(symbol.get("file")) != "selected-production"
            or not symbol.get("top_level")
            or not symbol.get("semantic_id")
            or not symbol.get("prepare_rename")
        ):
            continue
        authorities[bucket].append(symbol)
    authority_status = (
        "resolved" if len(authorities["old"]) <= 1 and len(authorities["new"]) == 1 else "ambiguous"
    )
    resolved_locations: dict[str, set[tuple[str, int, int]]] = {
        "old": set(),
        "new": set(),
    }
    occurrences: list[dict] = []
    for bucket, rows in authorities.items():
        for authority in rows:
            for reference in facts.get("definition_occurrences", []):
                if authority["semantic_id"] not in reference.get("definition_semantic_ids", []):
                    continue
                resolved_locations[bucket].add(
                    (reference["source"], reference["line"], reference["column"])
                )
                occurrences.append(
                    {
                        "term": args.old if bucket == "old" else args.new,
                        "classification": f"{bucket}_concept_symbol",
                        "semantic_id": authority["semantic_id"],
                        "file": reference["source"],
                        "line": reference["line"],
                        "column": reference["column"],
                        "role": roles.get(reference["source"]),
                    }
                )
    deferred: list[dict] = []
    for inventory in facts.get("source_inventory", []):
        source = root / inventory["path"]
        if not source.is_file() or source.is_symlink():
            continue
        for line_no, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for bucket, term in (("old", args.old), ("new", args.new)):
                for match in re.finditer(rf"\b{re.escape(term)}\b", line):
                    if (
                        inventory["path"],
                        line_no,
                        match.start() + 1,
                    ) in resolved_locations[bucket]:
                        continue
                    kind = (
                        f"{inventory['role']}_reference"
                        if inventory["role"] != "selected-production"
                        else "unresolved_or_unrelated_lexical"
                    )
                    deferred.append(
                        {
                            "term": term,
                            "file": inventory["path"],
                            "line": line_no,
                            "column": match.start() + 1,
                            "kind": kind,
                            "syntax": line.strip()[:180],
                            "reason": "the selected swiftc authority did not own this lexical occurrence",
                        }
                    )
    status = (
        "resolved"
        if facts.get("status") == "complete" and authority_status == "resolved"
        else ("failed" if facts.get("status") == "failed" else "partial")
    )
    payload = {
        "schema_version": "swift-rename-evidence-v1",
        "language": "swift",
        "analyzer": "swiftpm+swiftc-dump-ast-rename-definitions",
        "status": status,
        "reason": None
        if status == "resolved"
        else facts.get("failure_kind") or "rename_authority_ambiguous",
        "read_only": True,
        "mutation_applied": False,
        "target_name": args.target_name,
        "old": args.old,
        "new": args.new,
        "authority_status": authority_status,
        "authorities": {
            bucket: [
                {
                    "name": row["name"],
                    "semantic_id": row["semantic_id"],
                    "semantic_identity_kind": row["semantic_identity_kind"],
                    "file": row["file"],
                    "line": row["line"],
                    "kind": row["kind"],
                    "prepare_rename": row["prepare_rename"],
                }
                for row in rows
            ]
            for bucket, rows in authorities.items()
        },
        "occurrences": occurrences,
        "deferred_references": deferred,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "summary": {
            "old_symbol_references": len(resolved_locations["old"]),
            "new_symbol_references": len(resolved_locations["new"]),
            "deferred": len(deferred),
        },
        "limits": [
            *facts.get("limits", []),
            "assessment only: no rename edit is applied and no compatibility or reflection safety is claimed",
            "comments, strings, local homonyms, excluded roles, conditional variants, and dynamic/Objective-C identity remain deferred",
        ],
    }
    _write(output, payload)
    print(f"wrote Swift rename assessment: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
