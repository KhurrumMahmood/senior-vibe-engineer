#!/usr/bin/env python3
"""Write a bounded Dart subsystem map from the family-local LSP fact pack."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _provider():
    path = Path(__file__).with_name("dart_lsp_facts.py")
    if not path.is_file():
        raise RuntimeError("assembled Dart LSP fact provider is missing")
    spec = importlib.util.spec_from_file_location("dart_map_lsp_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
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


def _safe(root: Path, supplied: Path, allowed: Path, label: str) -> Path:
    path = supplied if supplied.is_absolute() else root / supplied
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(
            f"{label} must stay beneath {allowed.relative_to(root).as_posix()}/"
        ) from exc
    if not relative.parts:
        raise ValueError(f"{label} must name a file")
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValueError(f"{label} must not traverse a symbolic link")
    return path


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _selected(path: str, target: str) -> bool:
    return path == target or path.startswith(f"{target.rstrip('/')}/")


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        f"subsystem: {payload['name']}",
        f"target: {payload['target']}",
        f"regenerated: {payload['generated_at']}",
        f"status: {payload['status']}",
        f"files: {len(payload['selected_files'])}",
        f"public_symbols: {len(payload['public_surface'])}",
        f"map_content_sha256: {payload['map_content_sha256']}",
        "---",
        "",
        f"# {payload['name']}",
        "",
        "Read-only Dart 3.12 selected-configuration map. Static edges are LSP-resolved; runtime behavior is not inferred.",
        "",
        "## Status",
        "",
        f"`{payload['status']}` — diagnostic state `{payload['diagnostic_state']}`; fact pack `{payload['fact_pack_sha256']}`.",
        "",
        "## Files",
        "",
        "| Path | SHA-256 |",
        "|---|---|",
    ]
    lines.extend(f"| `{row['path']}` | `{row['sha256']}` |" for row in payload["selected_files"])
    lines.extend(["", "## Direct public surface", ""])
    if payload["public_surface"]:
        lines.extend(
            f"- `{row['name']}` ({row['kind_label']}) — `{row['source']}:{row['line']}`"
            for row in payload["public_surface"]
        )
    else:
        lines.append("None on the selected production surface.")
    lines.extend(["", "## Resolved outbound edges", ""])
    if payload["outbound_edges"]:
        lines.extend(
            f"- `{row['source']}` {row['kind']} `{row['specifier']}` → "
            + ", ".join(f"`{target['path']}`" for target in row["targets"])
            for row in payload["outbound_edges"]
        )
    else:
        lines.append("None.")
    lines.extend(["", "## Resolved inbound edges", ""])
    if payload["inbound_edges"]:
        lines.extend(
            f"- `{row['source']}` {row['kind']} `{row['specifier']}` → "
            + ", ".join(f"`{target['path']}`" for target in row["targets"])
            for row in payload["inbound_edges"]
        )
    else:
        lines.append("None.")
    lines.extend(["", "## Unresolved and excluded", ""])
    for row in payload["unresolved"]:
        lines.append(
            f"- `{row.get('source', row.get('path', 'project'))}` — {row.get('reason', row.get('kind', 'unresolved'))}"
        )
    if not payload["unresolved"]:
        lines.append("None for the selected static configuration.")
    lines.extend(["", "## Limitations", "", *[f"- {item}" for item in payload["limits"]], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    output = _safe(root, args.output, root / ".claude" / "docs" / "subsystems", "output")
    evidence = _safe(root, args.evidence, root / "reports" / "map", "evidence")
    provider = _provider()
    facts = provider.load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        queries=[],
        dart=args.dart,
        packages=args.packages,
        cache_dir=args.cache_dir,
        timeout=args.timeout,
    )
    target = (
        Path(os.path.realpath((root / args.target).resolve(strict=True)))
        .relative_to(root)
        .as_posix()
    )
    selected_files = [
        row
        for row in facts.get("source_inventory", [])
        if row.get("role") == "production" and _selected(row["path"], target)
    ]
    selected_paths = {row["path"] for row in selected_files}
    kind_names = {
        5: "class",
        6: "method",
        10: "enum",
        11: "interface",
        12: "function",
        13: "variable",
        22: "enum member",
        23: "struct",
    }
    public = [
        {**row, "kind_label": kind_names.get(row.get("kind"), f"LSP kind {row.get('kind')}")}
        for row in facts.get("document_symbols", [])
        if row.get("top_level")
        and row.get("source") in selected_paths
        and isinstance(row.get("name"), str)
        and not row["name"].startswith("_")
    ]
    edges = facts.get("module_edges", [])
    conditional_sources = {
        row.get("path")
        for row in facts.get("boundaries", [])
        if row.get("kind") in {"augmentation", "conditional-directive", "part"}
    }
    bounded_edges = [row for row in edges if row["source"] not in conditional_sources]
    outbound = [
        row for row in bounded_edges if row["source"] in selected_paths and row.get("targets")
    ]
    inbound = [
        row
        for row in bounded_edges
        if row["source"] not in selected_paths
        and any(target_row.get("path") in selected_paths for target_row in row.get("targets", []))
    ]
    unresolved = list(facts.get("unresolved_requests", [])) + list(facts.get("boundaries", []))
    status = facts.get("status", "failed")
    content = {
        "name": args.name,
        "target": target,
        "status": status,
        "selected_files": [
            {"path": row["path"], "sha256": row["sha256"]} for row in selected_files
        ],
        "public_surface": public,
        "outbound_edges": outbound,
        "inbound_edges": inbound,
        "unresolved": unresolved,
    }
    payload: dict[str, Any] = {
        "schema_version": "dart-subsystem-map-v1",
        "language": "dart",
        "read_only": True,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        **content,
        "map_content_sha256": _canonical_hash(content),
        "diagnostic_state": "error"
        if any(row.get("severity") == 1 for row in facts.get("diagnostics", []))
        else "clean",
        "diagnostics": facts.get("diagnostics", []),
        "package_config": facts.get("package_config", {}),
        "capabilities": facts.get("capabilities", {}),
        "query_plan_sha256": facts.get("query_plan_sha256"),
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "excluded_sources": [
            row for row in facts.get("source_inventory", []) if row.get("role") != "production"
        ],
        "limits": facts.get("limits", []),
        "reason": facts.get("failure_kind"),
    }
    markdown = _render(payload)
    payload["markdown_sha256"] = hashlib.sha256(markdown.encode()).hexdigest()
    _atomic(output, markdown)
    _atomic(evidence, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote Dart subsystem map: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
