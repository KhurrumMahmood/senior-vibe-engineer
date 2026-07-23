#!/usr/bin/env python3
"""Conservative Swift function-capability overlap leads from resolved calls."""

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


REVIEW_SCHEMA = "swift-semantic-duplication-review-v1"
VERDICTS = {"consolidate_candidate", "keep_separate_document_why", "not_equivalent"}
TYPE_KINDS = {5, 10, 11, 23}
CALLABLE_KINDS = {6, 12}
BUILTIN_TYPES = {
    "Any",
    "Bool",
    "Character",
    "Double",
    "Float",
    "Int",
    "Never",
    "String",
    "UInt",
    "Void",
}


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
    spec = importlib.util.spec_from_file_location("swift_dup_semantic_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _safe_dir(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports/semantic-duplication"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/semantic-duplication/") from exc
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


def _mask(text: str) -> str:
    """Blank comments and strings while preserving offsets and newlines."""
    rendered = list(text)
    index = 0
    state = "code"
    while index < len(text):
        if state == "code" and text.startswith("//", index):
            state = "line"
            rendered[index] = rendered[index + 1] = " "
            index += 2
        elif state == "code" and text.startswith("/*", index):
            state = "block"
            rendered[index] = rendered[index + 1] = " "
            index += 2
        elif state == "code" and text[index] == '"':
            state = "string"
            rendered[index] = " "
            index += 1
        elif state == "line":
            if text[index] == "\n":
                state = "code"
            else:
                rendered[index] = " "
            index += 1
        elif state == "block":
            if text.startswith("*/", index):
                rendered[index] = rendered[index + 1] = " "
                index += 2
                state = "code"
            else:
                if text[index] != "\n":
                    rendered[index] = " "
                index += 1
        elif state == "string":
            if text[index] == "\\" and index + 1 < len(text):
                rendered[index] = rendered[index + 1] = " "
                index += 2
            elif text[index] == '"':
                rendered[index] = " "
                index += 1
                state = "code"
            else:
                if text[index] != "\n":
                    rendered[index] = " "
                index += 1
        else:
            index += 1
    return "".join(rendered)


def _functions(root: Path, target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    header = re.compile(
        r"(?m)^\s*(?P<access>public|package|internal|fileprivate|private)?\s*(?:(?:nonisolated|async|throws|rethrows)\s+)*func\s+(?P<name>[A-Za-z_]\w*)\s*\([^)]*\)\s*(?:async\s+)?(?:throws\s+)?->\s*(?P<return>[A-Za-z_]\w*)\s*\{"
    )
    for source in sorted(target.rglob("*.swift")):
        if source.is_symlink():
            continue
        text = source.read_text(encoding="utf-8")
        masked = _mask(text)
        for match in header.finditer(masked):
            prefix = masked[: match.start()]
            if prefix.count("{") - prefix.count("}") != 0:
                continue
            depth = 1
            index = match.end()
            while index < len(masked) and depth:
                depth += (masked[index] == "{") - (masked[index] == "}")
                index += 1
            if depth:
                continue
            body = text[match.end() : index - 1]
            normalized = re.sub(r"\s+", "", body)
            constructor = re.search(
                rf"\breturn\s+{re.escape(match.group('return'))}\s*\((?P<arguments>[^()]*)\)",
                body,
                re.DOTALL,
            )
            fields = []
            if constructor:
                fields = sorted(
                    set(re.findall(r"(?:^|,)\s*([A-Za-z_]\w*)\s*:", constructor.group("arguments")))
                )
            rows.append(
                {
                    "name": match.group("name"),
                    "return_type": match.group("return"),
                    "return_fields": fields,
                    "file": source.relative_to(root).as_posix(),
                    "line": text.count("\n", 0, match.start("name")) + 1,
                    "end_line": text.count("\n", 0, index - 1) + 1,
                    "body": body,
                    "body_normalized": normalized,
                }
            )
    return rows


def _reviews(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    if not path.is_dir() or path.is_symlink():
        raise ValueError("reviews-dir must be a regular directory")
    return [json.loads(item.read_text(encoding="utf-8")) for item in sorted(path.glob("*.json"))]


def _write(
    output: Path,
    payload: dict[str, Any],
    candidates: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    (staged / "analysis.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (staged / "findings.json").write_text(
        json.dumps(
            {
                "schema_version": payload["schema_version"],
                "status": payload["status"],
                "findings": payload.get("findings", []),
                "rejected": payload.get("rejected", []),
                "uncertain": payload.get("uncertain", []),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (staged / "candidates.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    triage = [
        "# find-semantic-duplication — Swift",
        "",
        "> Hash-bound human review is required; static overlap is not behavioral equivalence.",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Reviewed leads",
        "",
    ]
    triage.extend(
        f"- `{row['candidate_id']}` — {' / '.join(item['name'] for item in row['functions'])}; verdict `{row['verdict']}`"
        for row in payload.get("findings", [])
    )
    if not payload.get("findings"):
        triage.append("None. Unreviewed machine candidates are not promoted.")
    (staged / "triage.md").write_text("\n".join(triage) + "\n", encoding="utf-8")
    for candidate in candidates:
        review = next(
            (row for row in reviews if row.get("candidate_id") == candidate["candidate_id"]),
            None,
        )
        if review is None:
            continue
        matrix = [
            f"# Capability matrix — {candidate['candidate_id']}",
            "",
            "| Function | Return fields | Resolved callees | Production callers |",
            "|---|---|---|---:|",
        ]
        for function in candidate["functions"]:
            matrix.append(
                f"| `{function['name']}` | `{', '.join(candidate['return_shape']['fields'])}` | "
                f"`{', '.join(function['resolved_callees'])}` | {len(function['production_callers'])} |"
            )
        matrix.extend(["", "This matrix is static evidence, not a safe-refactor claim.", ""])
        (staged / f"capability-matrix-{candidate['candidate_id'].lower()}.md").write_text(
            "\n".join(matrix), encoding="utf-8"
        )
        scout = staged / "scout"
        scout.mkdir(exist_ok=True)
        (scout / f"{candidate['candidate_id']}.json").write_text(
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
    parsed_functions = _functions(root, target)
    constructible_types = {row["return_type"] for row in parsed_functions if row["return_fields"]}
    functions = [row for row in parsed_functions if row["return_type"] in constructible_types]
    required_queries = [row["name"] for row in functions]
    required_queries.extend(
        name for row in functions for name in re.findall(r"\b([A-Za-z_]\w*)\s*\(", row["body"])
    )
    required_queries.extend(
        sorted({row["return_type"] for row in functions if row["return_type"] not in BUILTIN_TYPES})
    )
    provider = _provider()
    try:
        facts = provider.load_fact_pack(args.facts, root, args.target_name, required_queries)
    except provider.SwiftFactError as exc:
        payload = {
            "schema_version": "swift-semantic-duplication-v1",
            "language": "swift",
            "status": "failed",
            "failure_kind": exc.kind,
            "failure_detail": str(exc),
            "findings": [],
            "rejected": [],
            "uncertain": [],
            "summary": {"raw_candidates": 0, "reviewed": 0, "rejected": 0},
        }
        _write(output, payload, [], [])
        return 2
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    symbols = facts.get("symbols", [])
    occurrences = facts.get("definition_occurrences", [])
    symbols_by_semantic_id = {row["semantic_id"]: row for row in symbols if row.get("semantic_id")}
    selected: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    for function in functions:
        if roles.get(function["file"]) != "selected-production":
            continue
        matches = [
            row
            for row in symbols
            if row.get("name") == function["name"]
            and row.get("file") == function["file"]
            and row.get("line") == function["line"]
            and row.get("top_level")
            and row.get("semantic_id")
        ]
        if len(matches) != 1:
            uncertain.append(
                {"function": function["name"], "reason": "resolved callable identity unavailable"}
            )
            continue
        symbol = matches[0]
        body_occurrences = [
            row
            for row in occurrences
            if row.get("source") == function["file"]
            and function["line"] < row.get("line", 0) <= function["end_line"]
        ]
        constructors = sorted(
            {
                identity
                for occurrence in body_occurrences
                for identity in occurrence.get("definition_semantic_ids", [])
                if identity in symbols_by_semantic_id
                and symbols_by_semantic_id[identity].get("kind") in TYPE_KINDS
                and symbols_by_semantic_id[identity].get("name") == function["return_type"]
            }
        )
        callees = sorted(
            {
                identity
                for occurrence in body_occurrences
                for identity in occurrence.get("definition_semantic_ids", [])
                if identity in symbols_by_semantic_id
                and symbols_by_semantic_id[identity].get("kind") in CALLABLE_KINDS
                and identity != symbol["semantic_id"]
            }
        )
        callee_names = sorted(
            {str(symbols_by_semantic_id[identity].get("name")) for identity in callees}
        )
        selected.append(
            {
                **function,
                "semantic_id": symbol["semantic_id"],
                "constructor_ids": constructors,
                "resolved_callee_ids": callees,
                "resolved_callees": callee_names,
                "production_callers": [],
            }
        )
    for function in selected:
        callers: list[dict[str, Any]] = []
        for occurrence in occurrences:
            if function["semantic_id"] not in occurrence.get("definition_semantic_ids", []):
                continue
            if roles.get(occurrence.get("source")) != "selected-production":
                continue
            if (
                occurrence.get("source") == function["file"]
                and occurrence.get("line") == function["line"]
            ):
                continue
            enclosing = [
                row
                for row in selected
                if row["file"] == occurrence.get("source")
                and row["line"] < occurrence.get("line", 0) <= row["end_line"]
            ]
            if len(enclosing) == 1:
                caller = enclosing[0]
                callers.append(
                    {
                        "name": caller["name"],
                        "path": caller["file"],
                        "line": caller["line"],
                        "semantic_id": caller["semantic_id"],
                    }
                )
        function["production_callers"] = callers
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, left in enumerate(selected):
        for right in selected[index + 1 :]:
            pair = [left["name"], right["name"]]
            if left["return_type"] != right["return_type"]:
                continue
            if left["body_normalized"] == right["body_normalized"]:
                rejected.append({"functions": pair, "reason": "lexical_clone_only"})
                continue
            if re.search(rf"\b{re.escape(right['name'])}\s*\(", left["body"]) or re.search(
                rf"\b{re.escape(left['name'])}\s*\(", right["body"]
            ):
                rejected.append({"functions": pair, "reason": "direct_wrapper_relationship"})
                continue
            if not left["return_fields"] or left["return_fields"] != right["return_fields"]:
                rejected.append({"functions": pair, "reason": "return_shape_mismatch"})
                continue
            if not left["constructor_ids"] or left["constructor_ids"] != right["constructor_ids"]:
                rejected.append({"functions": pair, "reason": "resolved_constructor_mismatch"})
                continue
            if left["resolved_callee_ids"] != right["resolved_callee_ids"]:
                rejected.append({"functions": pair, "reason": "resolved_callee_set_mismatch"})
                continue
            caller_files = [
                {row["path"] for row in function["production_callers"]}
                for function in (left, right)
            ]
            if not all(caller_files) or caller_files[0] == caller_files[1]:
                uncertain.append(
                    {
                        "functions": pair,
                        "reason": "distinct resolved production callers not established",
                    }
                )
                continue
            functions_payload = []
            for function in (left, right):
                functions_payload.append(
                    {
                        key: value
                        for key, value in function.items()
                        if key
                        not in {"body", "body_normalized", "constructor_ids", "resolved_callee_ids"}
                    }
                )
            candidate = {
                "candidate_id": f"SWIFT-SD-{len(candidates) + 1:04d}",
                "classification": "review_required_semantic_lead",
                "functions": functions_payload,
                "return_shape": {"type": left["return_type"], "fields": left["return_fields"]},
                "resolved_constructor_ids": left["constructor_ids"],
                "human_verdict": "required",
                "boundary": "static selected-configuration lead, not behavioral equivalence or refactor safety",
            }
            candidate["candidate_sha256"] = _hash(candidate)
            candidates.append(candidate)
    reviews: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    review_error: str | None = None
    try:
        reviews = _reviews(args.reviews_dir)
        by_id = {row["candidate_id"]: row for row in candidates}
        seen: set[str] = set()
        for review in reviews:
            identifier = review.get("candidate_id")
            if review.get("schema_version") != REVIEW_SCHEMA or identifier not in by_id:
                raise ValueError("review schema or candidate id is invalid")
            if (
                identifier in seen
                or review.get("candidate_sha256") != by_id[identifier]["candidate_sha256"]
            ):
                raise ValueError(f"duplicate or stale review for {identifier}")
            if review.get("human_verdict") != "accepted" or review.get("verdict") not in VERDICTS:
                raise ValueError(f"review verdict is invalid for {identifier}")
            if not isinstance(review.get("notes"), str) or not review["notes"].strip():
                raise ValueError(f"review notes are required for {identifier}")
            seen.add(identifier)
            accepted.append(
                {
                    **by_id[identifier],
                    "human_verdict": "accepted",
                    "verdict": review["verdict"],
                    "review_notes": review["notes"],
                }
            )
        pending = len(candidates) - len(seen)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        review_error = str(exc)
        pending = len(candidates)
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
        "schema_version": "swift-semantic-duplication-v1",
        "language": "swift",
        "analyzer": "swiftpm-fresh-index+sourcekit-lsp-definition-graph",
        "status": status,
        "failure_kind": failure_kind,
        "failure_detail": review_error,
        "read_only": True,
        "target_name": args.target_name,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "findings": accepted,
        "rejected": rejected,
        "uncertain": uncertain,
        "summary": {
            "raw_candidates": len(candidates),
            "reviewed": len(accepted),
            "pending_review": pending,
            "rejected": len(rejected),
            "uncertain": len(uncertain),
        },
        "limits": [
            *facts.get("limits", []),
            "matching return labels, SourceKit-resolved constructor/callee identities, and distinct resolved callers are review evidence only",
            "human review is candidate-hash-bound and no consolidation shape is selected automatically",
        ],
    }
    _write(output, payload, candidates, reviews if review_error is None else [])
    print(f"wrote Swift semantic-duplication evidence: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
