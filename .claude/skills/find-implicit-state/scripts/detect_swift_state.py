#!/usr/bin/env python3
"""Detect resolved Swift String state operations for hash-bound human review."""

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


REVIEW_SCHEMA = "swift-implicit-state-review-v1"
ALLOWED_BUCKETS = {"extract_enum_candidate", "enum_already_used", "legacy_allow_list"}


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
    spec = importlib.util.spec_from_file_location("swift_state_semantic_facts", path)
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
    allowed = root / "reports/implicit-state"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/implicit-state/") from exc
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


def _fields(root: Path, target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    owner: dict[str, Any] | None
    owner_pattern = re.compile(
        r"^\s*(?P<access>public|package|internal|fileprivate|private)?\s*(?:(?:final|indirect|nonisolated)\s+)*(?P<kind>class|struct|actor)\s+(?P<name>[A-Za-z_]\w*)(?P<tail>[^\{]*)\{"
    )
    field_pattern = re.compile(
        r"^\s*(?:(?:public|package|internal|fileprivate|private)(?:\(set\))?\s+)?(?:(?:lazy|weak|unowned|nonisolated)\s+)*(?:var|let)\s+(?P<field>state|status|phase)\s*:\s*(?P<type>[A-Za-z_]\w*(?:<[^=]+>)?\??)"
    )
    for source in sorted(target.rglob("*.swift")):
        if source.is_symlink():
            continue
        owner = None
        depth = 0
        for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            code = re.sub(r"//.*$", "", line)
            if owner is None:
                match = owner_pattern.match(code)
                if match:
                    owner = {
                        "owner": match.group("name"),
                        "owner_kind": match.group("kind"),
                        "owner_line": line_no,
                        "owner_tail": match.group("tail"),
                    }
                    depth = code.count("{") - code.count("}")
                    continue
            elif depth == 1:
                field = field_pattern.match(code)
                if field:
                    rows.append(
                        {
                            **owner,
                            "field": field.group("field"),
                            "type": field.group("type"),
                            "file": source.relative_to(root).as_posix(),
                            "line": line_no,
                            "column": field.start("field") + 1,
                        }
                    )
            if owner is not None:
                depth += code.count("{") - code.count("}")
                if depth <= 0:
                    owner = None
                    depth = 0
    return rows


def _operation(line: str, field: str, column: int) -> dict[str, Any] | None:
    literal = r'"(?P<literal>[^"\\]*(?:\\.[^"\\]*)*)"'
    patterns = (
        ("assignment", re.compile(rf"(?:\bself\.)?(?P<field>{re.escape(field)})\s*=\s*{literal}")),
        (
            "comparison",
            re.compile(rf"(?:\bself\.)?(?P<field>{re.escape(field)})\s*(?:==|!=)\s*{literal}"),
        ),
        (
            "comparison",
            re.compile(rf"{literal}\s*(?:==|!=)\s*(?:\bself\.)?(?P<field>{re.escape(field)})"),
        ),
    )
    offset = column - 1
    for kind, pattern in patterns:
        for match in pattern.finditer(line):
            start, end = match.span("field")
            if start <= offset <= end:
                return {
                    "kind": kind,
                    "literal": match.group("literal"),
                    "syntax": match.group(0),
                    "start_column": match.start() + 1,
                }
    return None


def _reviews(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    if not path.is_dir() or path.is_symlink():
        raise ValueError("reviews-dir must be a regular directory")
    return [json.loads(item.read_text(encoding="utf-8")) for item in sorted(path.glob("*.json"))]


def _write(
    output: Path, payload: dict[str, Any], candidates: list[dict], reviews: list[dict]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    (staged / "findings.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (staged / "candidates.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    lines = [
        "# find-implicit-state — Swift",
        "",
        "> Detection-only evidence. Literal operations do not prove a closed value domain.",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Accepted enum-review candidates",
        "",
    ]
    lines.extend(
        f"- `{row['owner']}.{row['field']}` — {', '.join(row['literals'])}; human verdict accepted"
        for row in payload.get("findings", [])
    )
    if not payload.get("findings"):
        lines.append("None. Unreviewed candidates are not promoted.")
    (staged / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for review in reviews:
        scout = staged / "scout"
        scout.mkdir(exist_ok=True)
        (scout / f"{review.get('candidate_id', 'invalid')}.json").write_text(
            json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    _replace(staged, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reviews-dir", type=Path)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
        output = _safe_dir(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    fields = _fields(root, target)
    provider = _provider()
    try:
        facts = provider.load_fact_pack(
            args.facts, root, args.target_name, sorted({row["field"] for row in fields})
        )
    except provider.SwiftFactError as exc:
        payload = {
            "schema_version": "swift-implicit-state-v1",
            "language": "swift",
            "status": "failed",
            "failure_kind": exc.kind,
            "failure_detail": str(exc),
            "findings": [],
            "classifications": [],
            "deferred": [],
            "summary": {"raw_candidates": 0, "accepted": 0, "pending_review": 0},
        }
        _write(output, payload, [], [])
        return 2
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    symbols = facts.get("symbols", [])
    raw: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for field in fields:
        if roles.get(field["file"]) != "selected-production":
            continue
        if (
            re.search(r"(?:Wire|Payload|Request|Response|Event|Message)", field["owner"])
            or "Codable" in field["owner_tail"]
        ):
            classifications.append({**field, "classification": "serialization_or_wire_boundary"})
            continue
        if field["type"].rstrip("?") != "String":
            classifications.append({**field, "classification": "typed_state_authority"})
            continue
        matches = [
            row
            for row in symbols
            if row.get("name") == field["field"]
            and row.get("file") == field["file"]
            and row.get("line") == field["line"]
            and row.get("parent")
        ]
        if len(matches) != 1:
            deferred.append({**field, "reason": "resolved field identity is unavailable"})
            continue
        symbol = matches[0]
        hover = json.dumps(symbol.get("hover"), sort_keys=True)
        if "String" not in hover:
            deferred.append({**field, "reason": "SourceKit hover did not confirm String type"})
            continue
        operations: list[dict[str, Any]] = []
        literals: set[str] = set()
        definition_identity = {"path": field["file"], "line": field["line"]}
        resolved_edges = [
            row
            for row in facts.get("definition_occurrences", [])
            if row.get("name") == field["field"]
            and any(
                target_row.get("path") == definition_identity["path"]
                and target_row.get("line") == definition_identity["line"]
                for target_row in row.get("definitions", [])
            )
        ]
        for reference in resolved_edges:
            if roles.get(reference.get("source")) != "selected-production":
                continue
            if reference.get("source") == field["file"] and reference.get("line") == field["line"]:
                continue
            source = root / reference["source"]
            lines = source.read_text(encoding="utf-8").splitlines()
            if not 1 <= reference["line"] <= len(lines):
                continue
            operation = _operation(
                lines[reference["line"] - 1], field["field"], reference["column"]
            )
            if operation is None:
                continue
            literals.add(operation["literal"])
            operations.append(
                {
                    **operation,
                    "file": reference["source"],
                    "line": reference["line"],
                    "column": reference["column"],
                }
            )
        if len(literals) >= 3 and len(operations) >= 3 and facts.get("status") == "complete":
            candidate = {
                "candidate_id": f"swift-implicit-state-{len(raw) + 1:04d}",
                **field,
                "semantic_id": symbol.get("semantic_id"),
                "definition_identity": definition_identity,
                "literals": sorted(literals),
                "operations": operations,
                "human_verdict": "required",
                "boundary": "candidate only; the value domain is not proven closed",
            }
            candidate["candidate_sha256"] = _canonical_hash(candidate)
            raw.append(candidate)
        else:
            classifications.append(
                {
                    **field,
                    "classification": "insufficient_resolved_literal_operations",
                    "literal_count": len(literals),
                    "operation_count": len(operations),
                }
            )
    review_error: str | None = None
    reviews: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    try:
        reviews = _reviews(args.reviews_dir)
        by_id = {row["candidate_id"]: row for row in raw}
        seen: set[str] = set()
        for review in reviews:
            candidate_id = review.get("candidate_id")
            if review.get("schema_version") != REVIEW_SCHEMA or candidate_id not in by_id:
                raise ValueError("review schema or candidate id is invalid")
            if candidate_id in seen:
                raise ValueError(f"duplicate review for {candidate_id}")
            if review.get("candidate_sha256") != by_id[candidate_id]["candidate_sha256"]:
                raise ValueError(f"review hash does not match {candidate_id}")
            if (
                review.get("bucket") not in ALLOWED_BUCKETS
                or review.get("human_verdict") != "accepted"
            ):
                raise ValueError(f"review verdict is invalid for {candidate_id}")
            if not isinstance(review.get("notes"), str) or not review["notes"].strip():
                raise ValueError(f"review notes are required for {candidate_id}")
            seen.add(candidate_id)
            if review["bucket"] == "extract_enum_candidate":
                accepted.append(
                    {
                        **by_id[candidate_id],
                        "bucket": review["bucket"],
                        "human_verdict": "accepted",
                        "confidence": review.get("confidence"),
                        "review_notes": review["notes"],
                    }
                )
        pending = len(raw) - len(seen)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        review_error = str(exc)
        pending = len(raw)
        accepted = []
    if facts.get("status") != "complete":
        status, failure_kind = (
            "partial",
            facts.get("failure_kind") or "semantic_fact_pack_incomplete",
        )
    elif review_error is not None:
        status, failure_kind = "failed", "invalid_human_review"
    elif pending:
        status, failure_kind = "partial", "human_review_required"
    else:
        status, failure_kind = "complete", None
    payload = {
        "schema_version": "swift-implicit-state-v1",
        "language": "swift",
        "analyzer": "swiftpm-fresh-index+sourcekit-lsp-field-definitions",
        "status": status,
        "failure_kind": failure_kind,
        "failure_detail": review_error,
        "read_only": True,
        "target_name": args.target_name,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "findings": accepted,
        "classifications": classifications,
        "deferred": deferred,
        "summary": {
            "raw_candidates": len(raw),
            "accepted": len(accepted),
            "pending_review": pending,
        },
        "limits": [
            *facts.get("limits", []),
            "three resolved direct literal operations are required; literals never prove a closed value domain",
            "serialization/wire owners and typed state remain non-candidates",
        ],
    }
    _write(output, payload, raw, reviews if review_error is None else [])
    print(f"wrote Swift implicit-state evidence: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
