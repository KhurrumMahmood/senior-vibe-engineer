#!/usr/bin/env python3
"""Conservative Rust function-level semantic-duplication leads."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
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
    spec = importlib.util.spec_from_file_location("rust_dup_facts", path)
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


def _replace_directory(staged: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    if destination.exists():
        destination.replace(backup)
    try:
        staged.replace(destination)
    except OSError:
        if backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _functions(root: Path, target: Path) -> list[dict]:
    rows = []
    header = re.compile(
        r"(?m)^(?P<indent>[ \t]*)(?:pub(?:\([^)]*\))?\s+)?(?:(?:async|unsafe|const)\s+)*fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*->\s*(?P<return>[A-Za-z_][A-Za-z0-9_:<> ,]*)\s*\{"
    )
    for path in sorted((target / "src").rglob("*.rs")):
        if path.is_symlink():
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for match in header.finditer(text):
            depth = 1
            index = match.end()
            while index < len(text) and depth:
                if text[index] == "{":
                    depth += 1
                elif text[index] == "}":
                    depth -= 1
                index += 1
            if depth:
                continue
            line_no = text.count("\n", 0, match.start("name")) + 1
            attributes = []
            attribute_index = line_no - 2
            while attribute_index >= 0 and lines[attribute_index].lstrip().startswith("#["):
                attributes.append(lines[attribute_index].strip())
                attribute_index -= 1
            known_attributes = re.compile(
                r"^#\[(?:allow|warn|deny|forbid|inline|cold|must_use|deprecated|doc)\b"
            )
            body = text[match.end() : index - 1]
            returned = match.group("return").strip()
            struct = re.search(
                rf"\b{re.escape(returned.split('::')[-1])}\s*\{{(?P<body>[^{{}}]*)\}}",
                body,
                re.DOTALL,
            )
            fields = []
            if struct:
                for segment in struct.group("body").split(","):
                    field = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::|$)", segment)
                    if field:
                        fields.append(field.group(1))
                fields = sorted(set(fields))
            rows.append(
                {
                    "name": match.group("name"),
                    "return_type": returned,
                    "return_fields": fields,
                    "file": path.relative_to(root).as_posix(),
                    "line": line_no,
                    "attribute_boundary": any(
                        known_attributes.search(attribute) is None for attribute in attributes
                    ),
                    "scope": "top_level" if not match.group("indent") else "nested_or_impl",
                    "body": body,
                    "body_normalized": re.sub(r"\s+", "", body),
                }
            )
    return rows


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
    functions = _functions(root, target)
    facts = _facts_module().load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        queries=[row["name"] for row in functions],
        cargo=args.cargo,
        rustc=args.rustc,
        rust_analyzer=args.rust_analyzer,
        cargo_target_dir=args.cargo_target_dir,
    )
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    selected, boundary_functions = [], []
    for row in functions:
        if roles.get(row["file"]) != "production-module":
            continue
        if row["scope"] != "top_level":
            boundary_functions.append(
                {**row, "boundary_reason": "impl/trait function is outside semantic leads"}
            )
        elif any(
            boundary["source"] == row["file"]
            and boundary["start_line"] <= row["line"] <= boundary["end_line"]
            for boundary in facts.get("unsafe_ffi_boundaries", [])
        ) or any(
            boundary["source"] == row["file"]
            and boundary["start_line"] <= row["line"] <= boundary["end_line"]
            for boundary in facts.get("macro_regions", [])
        ):
            boundary_functions.append(
                {**row, "boundary_reason": "unsafe/FFI/macro function is outside semantic leads"}
            )
        elif row["attribute_boundary"]:
            boundary_functions.append(
                {
                    **row,
                    "boundary_reason": "cfg/procedural or unknown attribute is outside semantic leads",
                }
            )
        else:
            selected.append(row)
    functions = selected
    confirmed, rejected = [], []
    uncertain = [
        {"function": row["name"], "reason": row["boundary_reason"]} for row in boundary_functions
    ]
    for index, left in enumerate(functions):
        for right in functions[index + 1 :]:
            if left["name"] == right["name"]:
                continue
            if left["return_type"] != right["return_type"]:
                continue
            pair = [left["name"], right["name"]]
            if left["body_normalized"] == right["body_normalized"]:
                rejected.append({"functions": pair, "reason": "lexical_clone_only"})
                continue
            if re.search(rf"\b{re.escape(right['name'])}\s*\(", left["body"]) or re.search(
                rf"\b{re.escape(left['name'])}\s*\(", right["body"]
            ):
                rejected.append({"functions": pair, "reason": "direct_wrapper_relationship"})
                continue
            if not left["return_fields"] or not right["return_fields"]:
                continue
            if left["return_fields"] != right["return_fields"]:
                rejected.append({"functions": pair, "reason": "policy_or_return_shape_mismatch"})
                continue
            callers = {}
            for function in (left, right):
                refs = []
                for edge in facts.get("definition_edges", []):
                    if edge.get("name") != function["name"]:
                        continue
                    if edge["source"] == function["file"] and edge["line"] == function["line"]:
                        continue
                    if any(
                        item.get("file") == function["file"]
                        and item.get("line") == function["line"]
                        for item in edge.get("definitions", [])
                    ):
                        refs.append({"file": edge["source"], "line": edge["line"]})
                callers[function["name"]] = refs
            if (
                callers[left["name"]]
                and callers[right["name"]]
                and {row["file"] for row in callers[left["name"]]}
                != {row["file"] for row in callers[right["name"]]}
            ):
                confirmed.append(
                    {
                        "id": f"RSD-{len(confirmed)+1:02d}",
                        "classification": "review_required_semantic_lead",
                        "functions": [
                            {
                                key: value
                                for key, value in row.items()
                                if key not in {"body", "body_normalized"}
                            }
                            for row in (left, right)
                        ],
                        "return_shape": {
                            "type": left["return_type"],
                            "fields": left["return_fields"],
                        },
                        "production_callers": callers,
                        "human_verdict": "required",
                        "boundary": "static lead, not behavioral equivalence or a safe-refactor claim",
                    }
                )
            else:
                uncertain.append(
                    {
                        "functions": pair,
                        "reason": "distinct_resolved_production_callers_not_established",
                    }
                )
    if facts.get("status") != "complete":
        if confirmed:
            uncertain.extend(
                {
                    "functions": [function["name"] for function in row["functions"]],
                    "reason": "compiler/LSP fact pack is incomplete; lead promotion withheld",
                }
                for row in confirmed
            )
            confirmed = []
        uncertain.append({"reason": "compiler/LSP fact pack incomplete"})
    elif facts.get("semantic_analysis", {}).get("state") != "complete":
        uncertain.append({"reason": "stable LSP evidence incomplete"})
    status = (
        "failed"
        if facts.get("status") == "failed"
        else ("complete" if facts.get("status") == "complete" else "partial")
    )
    payload = {
        "schema_version": "rust-semantic-duplication-v1",
        "language": "rust",
        "status": status,
        "analyzer": "cargo-compiler+rust-analyzer-function-capability-leads",
        "read_only": True,
        "target": args.target,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "confirmed": confirmed,
        "rejected": rejected,
        "uncertain": uncertain,
        "summary": {
            "review_required_leads": len(confirmed),
            "rejected": len(rejected),
            "uncertain": len(uncertain),
        },
        "limits": facts.get("limits", []),
    }
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    try:
        output.resolve(strict=False).relative_to(
            (root / "reports/semantic-duplication").resolve(strict=False)
        )
    except ValueError:
        parser.error("output-dir must stay beneath reports/semantic-duplication")
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    _atomic(staged / "analysis.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(
        staged / "findings.json",
        json.dumps(
            {
                "schema_version": payload["schema_version"],
                "confirmed": confirmed,
                "rejected": rejected,
                "uncertain": uncertain,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    triage = [
        "# find-semantic-duplication — Rust triage",
        "",
        "> Human review is required. These are static leads, not behavioral-equivalence or safe-refactor claims.",
        "",
        "## Review-required leads",
        "",
    ]
    for lead in confirmed:
        triage.append(
            f"- `{lead['id']}` — {' / '.join(row['name'] for row in lead['functions'])}; return `{lead['return_shape']['type']}`"
        )
    if not confirmed:
        triage.append("None.")
    _atomic(staged / "triage.md", "\n".join(triage) + "\n")
    for lead in confirmed:
        matrix = [
            f"# Capability matrix — {lead['id']}",
            "",
            "| Function | Return fields | Resolved production callers |",
            "|---|---|---:|",
        ]
        for function in lead["functions"]:
            matrix.append(
                f"| `{function['name']}` | `{', '.join(lead['return_shape']['fields'])}` | {len(lead['production_callers'][function['name']])} |"
            )
        matrix.extend(["", "This matrix does not establish behavioral equivalence.", ""])
        _atomic(staged / f"capability-matrix-{lead['id'].lower()}.md", "\n".join(matrix))
    _replace_directory(staged, output)
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
