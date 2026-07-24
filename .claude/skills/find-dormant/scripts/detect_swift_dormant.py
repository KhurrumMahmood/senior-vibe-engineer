#!/usr/bin/env python3
"""Produce review-only Swift dormant-function candidates from resolved references."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


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
    spec = importlib.util.spec_from_file_location("swift_dormant_semantic_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _safe_dir(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports/find-dormant"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/find-dormant/") from exc
    if not relative.parts:
        raise ValueError("output-dir must name a scan")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValueError("output-dir must not traverse a symbolic link")
    return output


def _replace(staged: Path, destination: Path) -> None:
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


def _declarations(root: Path, target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"^\s*(?P<access>private|fileprivate)\s+(?:(?:nonisolated|static|class|async|throws|rethrows)\s+)*func\s+(?P<name>[A-Za-z_]\w*)\s*\("
    )
    for source in sorted(target.rglob("*.swift")):
        if source.is_symlink():
            continue
        depth = 0
        for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            match = pattern.match(line)
            if match and depth == 0:
                rows.append(
                    {
                        "name": match.group("name"),
                        "access": match.group("access"),
                        "file": source.relative_to(root).as_posix(),
                        "line": line_no,
                    }
                )
            code = re.sub(r"//.*$", "", line)
            depth += code.count("{") - code.count("}")
            depth = max(depth, 0)
    return rows


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# find-dormant — Swift",
        "",
        "> Resolved read-only leads. No candidate is proof that deletion is safe.",
        "",
        f"Status: `{payload['status']}`",
        f"Review-required candidates: `{len(payload['candidates'])}`",
        "Certain-delete findings: `0`",
        "",
        "## Candidates",
        "",
    ]
    lines.extend(
        f"- `{row['file']}:{row['line']}` `{row['name']}` — zero resolved references; human review required"
        for row in payload["candidates"]
    )
    if not payload["candidates"]:
        lines.append("None on the bounded selected target.")
    lines.extend(["", "## Deferred", ""])
    lines.extend(
        f"- `{row.get('file', 'unknown')}:{row.get('line', 0)}` — {row['reason']}"
        for row in payload["deferred"]
    )
    return "\n".join(lines) + "\n"


def _write(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    (staged / "findings.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (staged / "report.md").write_text(_render(payload), encoding="utf-8")
    _replace(staged, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
        output = _safe_dir(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    declarations = _declarations(root, target)
    provider = _provider()
    try:
        facts = provider.load_fact_pack(
            args.facts, root, args.target_name, [row["name"] for row in declarations]
        )
    except provider.SwiftFactError as exc:
        payload = {
            "schema_version": "swift-dormant-v1",
            "language": "swift",
            "status": "failed",
            "failure_kind": exc.kind,
            "failure_detail": str(exc),
            "candidates": [],
            "deferred": [],
            "summary": {"review_required": 0, "deferred": 0, "certain_delete": 0},
        }
        _write(output, payload)
        return 2
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    symbols = facts.get("symbols", [])
    candidates: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for declaration in declarations:
        if roles.get(declaration["file"]) != "selected-production":
            continue
        matches = [
            row
            for row in symbols
            if row.get("name") == declaration["name"]
            and row.get("file") == declaration["file"]
            and row.get("line") == declaration["line"]
            and row.get("top_level")
        ]
        if len(matches) != 1:
            deferred.append(
                {**declaration, "reason": "resolved declaration identity is unavailable"}
            )
            continue
        definition_identity = {
            "path": declaration["file"],
            "line": declaration["line"],
        }
        resolved_edges = [
            row
            for row in facts.get("definition_occurrences", [])
            if row.get("name") == declaration["name"]
            and any(
                target.get("path") == definition_identity["path"]
                and target.get("line") == definition_identity["line"]
                for target in row.get("definitions", [])
            )
        ]
        if not any(
            row.get("source") == declaration["file"] and row.get("line") == declaration["line"]
            for row in resolved_edges
        ):
            deferred.append(
                {**declaration, "reason": "swiftc did not resolve the declaration to itself"}
            )
            continue
        reflection_hits = []
        for inventory in facts.get("source_inventory", []):
            if inventory.get("role") not in {"selected-production", "selected-consumer"}:
                continue
            source = root / inventory["path"]
            for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(
                    rf"[\"']{re.escape(declaration['name'])}[\"']|#selector\s*\([^)]*\b{re.escape(declaration['name'])}\b",
                    line,
                ):
                    reflection_hits.append({"file": inventory["path"], "line": line_no})
        references = [
            row
            for row in resolved_edges
            if not (
                row.get("source") == declaration["file"] and row.get("line") == declaration["line"]
            )
        ]
        if reflection_hits:
            deferred.append(
                {
                    **declaration,
                    "reason": "reflection/string-like name occurrence prevents dormant promotion",
                    "reflection_hits": reflection_hits,
                }
            )
        elif not references and facts.get("status") == "complete":
            candidate = {
                **declaration,
                "definition_identity": definition_identity,
                "resolved_reference_count": 0,
                "classification": "review_required",
                "human_verdict": "required",
                "boundary": "candidate only; deletion safety and runtime reachability are not established",
            }
            candidate["candidate_sha256"] = _canonical_hash(candidate)
            candidates.append(candidate)
    status = "complete" if facts.get("status") == "complete" else "partial"
    if status == "partial":
        deferred.append({"reason": facts.get("failure_kind") or "semantic fact pack incomplete"})
    payload = {
        "schema_version": "swift-dormant-v1",
        "language": "swift",
        "analyzer": "swiftpm+swiftc-dump-ast-definitions",
        "status": status,
        "failure_kind": facts.get("failure_kind") if status != "complete" else None,
        "read_only": True,
        "target_name": args.target_name,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "candidates": sorted(candidates, key=lambda row: (row["file"], row["line"])),
        "deferred": deferred,
        "summary": {
            "review_required": len(candidates),
            "deferred": len(deferred),
            "certain_delete": 0,
        },
        "limits": facts.get("limits", []),
    }
    _write(output, payload)
    print(f"wrote Swift dormant evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
