#!/usr/bin/env python3
"""Read-only Rust dormant-code candidate producer."""

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
    local = Path(__file__).with_name("rust_semantic_facts.py")
    candidates = [local]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "rust_semantic_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Rust semantic fact pack is missing")
    spec = importlib.util.spec_from_file_location("rust_dormant_facts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _declarations(root: Path, target: Path) -> list[dict]:
    rows = []
    pattern = re.compile(
        r"^(?P<indent>\s*)(?!pub(?:\s|\())(?:(?:async|const|unsafe)\s+)*fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*[<(]"
    )
    for path in sorted((target / "src").rglob("*.rs")):
        if path.is_symlink():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, 1):
            match = pattern.search(line)
            if match:
                attributes = []
                index = line_no - 2
                while index >= 0 and lines[index].lstrip().startswith("#["):
                    attributes.append(lines[index].strip())
                    index -= 1
                known_attributes = re.compile(
                    r"^#\[(?:allow|warn|deny|forbid|inline|cold|must_use|deprecated|doc)\b"
                )
                rows.append(
                    {
                        "name": match.group("name"),
                        "file": path.relative_to(root).as_posix(),
                        "line": line_no,
                        "scope": "top_level" if not match.group("indent") else "nested_or_impl",
                        "generic": "<" in line[match.start("name") + len(match.group("name")) :],
                        "attribute_boundary": any(
                            known_attributes.search(attribute) is None for attribute in attributes
                        ),
                    }
                )
    return rows


def _render(payload: dict) -> str:
    lines = [
        "# find-dormant — Rust review candidates",
        "",
        "> Read-only evidence. A candidate is never proof that deletion is safe.",
        "",
        f"Status: `{payload['status']}`",
        f"Review-required candidates: `{len(payload['candidates'])}`",
        "Certain-delete findings: `0`",
        "",
        "## Candidates",
        "",
    ]
    for row in payload["candidates"]:
        lines.append(
            f"- `{row['file']}:{row['line']}` `{row['name']}` — resolved references: 0; human review required"
        )
    if not payload["candidates"]:
        lines.append("None on the bounded selected-module surface.")
    lines.extend(["", "## Uncertain and deferred", ""])
    lines.extend(
        f"- `{row['file']}:{row.get('line', 0)}` — {row['reason']}" for row in payload["uncertain"]
    )
    lines.extend(["", "## Boundary", "", *[f"- {item}" for item in payload["limits"]], ""])
    return "\n".join(lines)


def _unsafe_or_ffi(facts: dict, file: str, line: int) -> bool:
    return any(
        row["source"] == file and row["start_line"] <= line <= row["end_line"]
        for row in facts.get("unsafe_ffi_boundaries", [])
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
    declarations = _declarations(root, target)
    facts = _facts_module().load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        queries=[row["name"] for row in declarations],
        cargo=args.cargo,
        rustc=args.rustc,
        rust_analyzer=args.rust_analyzer,
        cargo_target_dir=args.cargo_target_dir,
    )
    role = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    edges = facts.get("definition_edges", [])
    candidates = []
    uncertain = []
    for declaration in declarations:
        if role.get(declaration["file"]) != "production-module":
            continue
        if _unsafe_or_ffi(facts, declaration["file"], declaration["line"]):
            uncertain.append(
                {**declaration, "reason": "unsafe/FFI function is outside dormant claims"}
            )
            continue
        if declaration["generic"]:
            uncertain.append(
                {**declaration, "reason": "generic function is outside dormant claims"}
            )
            continue
        if declaration["attribute_boundary"]:
            uncertain.append(
                {
                    **declaration,
                    "reason": "cfg/procedural or unknown attribute is outside dormant claims",
                }
            )
            continue
        if declaration["scope"] != "top_level":
            uncertain.append(
                {
                    **declaration,
                    "reason": "nested/impl/trait function requires dispatch-aware review",
                }
            )
            continue
        resolved_refs = []
        string_hits = []
        for edge in edges:
            if edge.get("name") != declaration["name"]:
                continue
            line = (
                (root / edge["source"]).read_text(encoding="utf-8").splitlines()[edge["line"] - 1]
            )
            if re.search(rf"[\"']{re.escape(declaration['name'])}[\"']", line):
                string_hits.append(edge)
            if any(
                item.get("file") == declaration["file"] and item.get("line") == declaration["line"]
                for item in edge.get("definitions", [])
            ) and not (
                edge["source"] == declaration["file"] and edge["line"] == declaration["line"]
            ):
                resolved_refs.append(edge)
        if string_hits:
            uncertain.append(
                {
                    **declaration,
                    "reason": "string/reflection-like name match is not reachability evidence",
                }
            )
        if facts.get("semantic_analysis", {}).get("state") != "complete":
            uncertain.append(
                {**declaration, "reason": "stable LSP definition evidence is incomplete"}
            )
        elif not resolved_refs:
            candidates.append(
                {**declaration, "classification": "review_required", "resolved_reference_count": 0}
            )
    for row in facts.get("macro_boundaries", []):
        uncertain.append(
            {"file": row["source"], "line": row["line"], "reason": "macro boundary is not expanded"}
        )
    status = (
        "failed"
        if facts.get("status") == "failed"
        else ("complete" if facts.get("status") == "complete" else "partial")
    )
    payload = {
        "schema_version": "rust-dormant-v1",
        "language": "rust",
        "analyzer": "cargo-compiler+rust-analyzer-selected-definitions",
        "status": status,
        "read_only": True,
        "target": args.target,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "candidates": candidates,
        "uncertain": uncertain,
        "summary": {
            "review_required": len(candidates),
            "uncertain": len(uncertain),
            "certain_delete": 0,
        },
        "limits": facts.get("limits", []),
    }
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    allowed = root / "reports" / "find-dormant"
    try:
        output.resolve(strict=False).relative_to(allowed.resolve(strict=False))
    except ValueError:
        parser.error("output-dir must stay beneath reports/find-dormant")
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(output / "report.md", _render(payload))
    print(f"wrote Rust dormant evidence: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
