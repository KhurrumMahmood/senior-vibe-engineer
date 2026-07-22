#!/usr/bin/env python3
"""Detect compiler-resolved Rust string state operations for human review."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
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
    spec = importlib.util.spec_from_file_location("rust_state_facts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _fields(root: Path, target: Path) -> list[dict]:
    rows = []
    struct = None
    generic_owner = False
    owner_line = 0
    brace = 0
    for path in sorted((target / "src").rglob("*.rs")):
        if path.is_symlink():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            start = re.search(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)(?P<tail>[^\{]*)", line)
            if start:
                struct = start.group(1)
                generic_owner = "<" in start.group("tail")
                owner_line = line_no
                brace = line.count("{") - line.count("}")
            elif struct:
                brace += line.count("{") - line.count("}")
            if struct:
                field = re.search(
                    r"(?:pub(?:\([^)]*\))?\s+)?(state|status|phase)\s*:\s*([^,]+)", line
                )
                if field:
                    rows.append(
                        {
                            "owner": struct,
                            "name": field.group(1),
                            "type": field.group(2).strip(),
                            "generic_owner": generic_owner,
                            "owner_line": owner_line,
                            "file": path.relative_to(root).as_posix(),
                            "line": line_no,
                        }
                    )
            if struct and brace <= 0:
                struct = None
                generic_owner = False
                owner_line = 0
    return rows


def _unsafe_or_ffi(facts: dict, file: str, line: int) -> bool:
    return any(
        row["source"] == file and row["start_line"] <= line <= row["end_line"]
        for row in facts.get("unsafe_ffi_boundaries", [])
    ) or any(
        row["source"] == file and row["start_line"] <= line <= row["end_line"]
        for row in facts.get("macro_regions", [])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--rust-analyzer", default="rust-analyzer")
    parser.add_argument("--cargo-target-dir", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    target = (root / args.target).resolve()
    fields = _fields(root, target)
    facts = _facts_module().load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        queries=sorted({row["name"] for row in fields}),
        cargo=args.cargo,
        rustc=args.rustc,
        rust_analyzer=args.rust_analyzer,
        cargo_target_dir=args.cargo_target_dir,
    )
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    edges = facts.get("definition_edges", [])
    candidates, classifications, deferred = [], [], []
    for field in fields:
        if roles.get(field["file"]) != "production-module":
            classifications.append(
                {**field, "classification": roles.get(field["file"], "excluded")}
            )
            continue
        if field["generic_owner"]:
            classifications.append({**field, "classification": "generic_state_deferred"})
            deferred.append(
                {
                    "file": field["file"],
                    "line": field["line"],
                    "reason": "generic owner is outside state-domain claims",
                }
            )
            continue
        cfg_or_unknown_attribute = any(
            row.get("source") == field["file"]
            and row.get("line", 0) <= field["owner_line"] <= row.get("line", 0) + 2
            for row in [
                *facts.get("cfg_boundaries", []),
                *[
                    item
                    for item in facts.get("attribute_boundaries", [])
                    if item.get("classification") == "procedural_or_unknown"
                ],
            ]
        )
        if cfg_or_unknown_attribute:
            classifications.append({**field, "classification": "cfg_or_attribute_deferred"})
            deferred.append(
                {
                    "file": field["file"],
                    "line": field["owner_line"],
                    "reason": "cfg/procedural attribute owner is outside state-domain claims",
                }
            )
            continue
        if field["type"] not in {"String", "std::string::String"}:
            classifications.append({**field, "classification": "typed_state"})
            continue
        operations, literals = [], set()
        for edge in edges:
            if edge.get("name") != field["name"]:
                continue
            if not any(
                item.get("file") == field["file"] and item.get("line") == field["line"]
                for item in edge.get("definitions", [])
            ):
                continue
            if _unsafe_or_ffi(facts, edge["source"], edge["line"]):
                deferred.append(
                    {
                        "file": edge["source"],
                        "line": edge["line"],
                        "reason": "unsafe/FFI/macro operation is outside state-domain claims",
                    }
                )
                continue
            line = (
                (root / edge["source"]).read_text(encoding="utf-8").splitlines()[edge["line"] - 1]
            )
            values = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line)
            if values and edge["line"] != field["line"]:
                literals.update(values)
                operations.append(
                    {
                        "file": edge["source"],
                        "line": edge["line"],
                        "syntax": line.strip()[:180],
                        "literals": values,
                    }
                )
        if len(literals) >= 2 and facts.get("status") == "complete":
            candidates.append(
                {
                    **field,
                    "classification": "extract_enum_candidate",
                    "human_verdict": "required",
                    "literals": sorted(literals),
                    "operations": operations,
                    "boundary": "candidate only; the domain is not proven closed",
                }
            )
        elif len(literals) < 2:
            classifications.append(
                {
                    **field,
                    "classification": "insufficient_operations",
                    "literal_count": len(literals),
                }
            )
        else:
            deferred.append(
                {
                    **field,
                    "reason": "compiler/LSP fact pack is incomplete; candidate promotion withheld",
                }
            )
    if facts.get("semantic_analysis", {}).get("state") != "complete":
        deferred.append({"reason": "stable LSP definition evidence is incomplete"})
    for name, key in (
        ("macro", "macro_boundaries"),
        ("cfg", "cfg_boundaries"),
        ("trait", "trait_dispatch_boundaries"),
    ):
        deferred.extend(
            {
                "file": row.get("source"),
                "line": row.get("line"),
                "reason": f"{name} boundary is not state-domain evidence",
            }
            for row in facts.get(key, [])
        )
    status = (
        "failed"
        if facts.get("status") == "failed"
        else ("complete" if facts.get("status") == "complete" else "partial")
    )
    payload = {
        "schema_version": "rust-implicit-state-v1",
        "language": "rust",
        "status": status,
        "analyzer": "cargo-compiler+rust-analyzer-field-definitions",
        "read_only": True,
        "target": args.target,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "candidates": candidates,
        "classifications": classifications,
        "deferred": deferred,
        "summary": {
            "extract_enum_candidate": len(candidates),
            "classified_not_candidate": len(classifications),
            "deferred": len(deferred),
        },
        "limits": facts.get("limits", []),
    }
    lines = [
        "# find-implicit-state — Rust",
        "",
        "> Detection-only evidence; no enum extraction or source edit was performed.",
        "",
        f"Status: `{status}`",
        "",
        "## Review candidates",
        "",
    ]
    lines.extend(
        f"- `{row['owner']}.{row['name']}` at `{row['file']}:{row['line']}` — {', '.join(row['literals'])}; human verdict required"
        for row in candidates
    )
    if not candidates:
        lines.append("None on the bounded surface.")
    lines.extend(
        [
            "",
            "## Explicit boundary",
            "",
            "A string-state candidate does not prove that the state domain is closed.",
            "",
        ]
    )
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    try:
        output.resolve(strict=False).relative_to(
            (root / "reports/implicit-state").resolve(strict=False)
        )
    except ValueError:
        parser.error("output-dir must stay beneath reports/implicit-state")
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(
        output / "hits.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates)
    )
    _atomic(output / "report.md", "\n".join(lines))
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
