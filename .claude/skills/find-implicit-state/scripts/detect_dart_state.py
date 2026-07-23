#!/usr/bin/env python3
"""Detect bounded, LSP-resolved Dart String state for human review."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "dart-implicit-state-v1"
REVIEW_SCHEMA = "dart-implicit-state-review-v1"
ALLOWED_BUCKETS = {"extract_enum_candidate", "enum_already_used", "legacy_allow_list"}


def _provider():
    candidates = [Path(__file__).with_name("dart_lsp_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "dart_lsp_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Dart LSP fact provider is missing")
    spec = importlib.util.spec_from_file_location("dart_state_lsp_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


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


def _safe_output(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports" / "implicit-state"
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


def _fields(root: Path, target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = [target] if target.is_file() else sorted(target.rglob("*.dart"))
    class_pattern = re.compile(
        r"^\s*(?:(?:abstract|base|final|interface|sealed)\s+)?class\s+([A-Za-z_]\w*)[^;{]*\{"
    )
    field_pattern = re.compile(
        r"^\s*(?:(?:late|final|covariant)\s+)*(?P<type>[A-Za-z_]\w*(?:<[^;=]+>)?\??)\s+"
        r"(?P<field>state|status|phase)\s*(?P<tail>[;=])"
    )
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        owner: str | None = None
        depth = 0
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            code = re.sub(r"//.*$", "", line)
            if owner is None:
                declaration = class_pattern.match(code)
                if declaration:
                    owner = declaration.group(1)
                    depth = code.count("{") - code.count("}")
                continue
            if depth == 1:
                field = field_pattern.match(code)
                if field:
                    rows.append(
                        {
                            "owner": owner,
                            "field": field.group("field"),
                            "type": field.group("type"),
                            "file": path.relative_to(root).as_posix(),
                            "line": line_no,
                            "column": field.start("field") + 1,
                        }
                    )
            depth += code.count("{") - code.count("}")
            if depth <= 0:
                owner = None
                depth = 0
    return rows


def _operation(line: str, field: str, column: int) -> dict[str, Any] | None:
    literal = (
        r"(?P<quote>['\"])(?P<literal>[^'\"\\]*(?:\\.[^'\"\\]*)*)(?P=quote)"
    )
    patterns = (
        ("assignment", re.compile(rf"(?P<field>\b{re.escape(field)}\b)\s*=\s*{literal}")),
        (
            "comparison",
            re.compile(rf"(?P<field>\b{re.escape(field)}\b)\s*(?:==|!=)\s*{literal}"),
        ),
        (
            "comparison",
            re.compile(rf"{literal}\s*(?:==|!=)\s*(?P<field>\b{re.escape(field)}\b)"),
        ),
    )
    token_offset = column - 1
    for kind, pattern in patterns:
        for match in pattern.finditer(line):
            start, end = match.span("field")
            if start <= token_offset < end:
                return {
                    "kind": kind,
                    "literal": match.group("literal"),
                    "start_column": match.start() + 1,
                    "end_column": match.end() + 1,
                    "syntax": match.group(0),
                }
    return None


def _review_rows(review_dir: Path | None) -> list[dict[str, Any]]:
    if review_dir is None:
        return []
    if not review_dir.is_dir() or review_dir.is_symlink():
        raise ValueError("reviews-dir must be a regular directory")
    rows: list[dict[str, Any]] = []
    for path in sorted(review_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"review {path.name} must contain an object")
        rows.append(payload)
    return rows


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# find-implicit-state — Dart",
        "",
        "> Detection-only, selected-configuration evidence. No value domain is claimed closed.",
        "",
        f"Status: `{payload['status']}`",
        f"Raw candidates: `{payload['summary']['raw_candidates']}`",
        f"Human-reviewed findings: `{payload['summary']['accepted']}`",
        "",
        "## Reviewed extract-enum candidates",
        "",
    ]
    lines.extend(
        f"- `{row['owner']}.{row['field']}` at `{row['file']}:{row['line']}` — "
        f"{', '.join(row['literals'])}; human verdict `{row['human_verdict']}`"
        for row in payload["findings"]
    )
    if not payload["findings"]:
        lines.append("None. Unreviewed detector candidates are not promoted.")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in payload["limits"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reviews-dir", type=Path)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
        output = _safe_output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    discovered = _fields(root, target)
    provider = _provider()
    try:
        facts = provider.load_or_collect(
            facts=args.facts,
            project_root=root,
            target=args.target,
            queries=sorted({row["field"] for row in discovered}),
            dart=args.dart,
            packages=args.packages,
            cache_dir=args.cache_dir,
            timeout=args.timeout,
        )
    except (provider.DartFactError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    definition_rows = facts.get("definition_queries", [])
    raw_candidates: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for field in discovered:
        if roles.get(field["file"]) != "production":
            continue
        if re.search(r"(?:Wire|Payload|Request|Response|Event|Message)", field["owner"]):
            classifications.append({**field, "classification": "serialization_or_wire_boundary"})
            continue
        if field["type"].rstrip("?") != "String":
            classifications.append({**field, "classification": "typed_state_authority"})
            continue
        operations: list[dict[str, Any]] = []
        literals: set[str] = set()
        for edge in definition_rows:
            if edge.get("name") != field["field"] or edge.get("source") != field["file"]:
                continue
            if edge.get("line") == field["line"] and edge.get("column") == field["column"]:
                continue
            targets = edge.get("targets", [])
            if not any(
                target_row.get("path") == field["file"]
                and target_row.get("line") == field["line"]
                for target_row in targets
            ):
                continue
            source_lines = (root / edge["source"]).read_text(encoding="utf-8").splitlines()
            if not (1 <= edge["line"] <= len(source_lines)):
                continue
            operation = _operation(source_lines[edge["line"] - 1], field["field"], edge["column"])
            if operation is None:
                continue
            literals.add(operation["literal"])
            operations.append(
                {
                    "file": edge["source"],
                    "line": edge["line"],
                    "column": edge["column"],
                    "definition_targets": targets,
                    **operation,
                }
            )
        if len(literals) < 3:
            classifications.append(
                {
                    **field,
                    "classification": "insufficient_bounded_literals",
                    "literal_count": len(literals),
                }
            )
            continue
        candidate: dict[str, Any] = {
            "candidate_id": f"dart-implicit-state-{len(raw_candidates) + 1:04d}",
            **field,
            "pattern": "stringly_compare",
            "literals": sorted(literals),
            "operations": operations,
            "human_verdict": "required",
            "boundary": "candidate only; the value domain is not proven closed",
            "fact_pack_sha256": facts.get("fact_pack_sha256"),
        }
        candidate["candidate_sha256"] = _canonical_hash(candidate)
        if facts.get("status") == "complete":
            raw_candidates.append(candidate)
        else:
            deferred.append({**field, "reason": "incomplete Dart semantic facts withheld promotion"})

    failure_kind = facts.get("failure_kind")
    reviews: list[dict[str, Any]] = []
    review_error: str | None = None
    try:
        reviews = _review_rows(args.reviews_dir)
        candidates_by_id = {row["candidate_id"]: row for row in raw_candidates}
        reviews_by_id: dict[str, dict[str, Any]] = {}
        for review in reviews:
            candidate_id = review.get("candidate_id")
            if review.get("schema_version") != REVIEW_SCHEMA:
                raise ValueError("review schema is incompatible")
            if candidate_id not in candidates_by_id:
                raise ValueError(f"review names unknown candidate {candidate_id!r}")
            if candidate_id in reviews_by_id:
                raise ValueError(f"duplicate review for {candidate_id}")
            if review.get("candidate_sha256") != candidates_by_id[candidate_id]["candidate_sha256"]:
                raise ValueError(f"review hash does not match {candidate_id}")
            if review.get("bucket") not in ALLOWED_BUCKETS:
                raise ValueError(f"review bucket is invalid for {candidate_id}")
            if review.get("human_verdict") != "accepted":
                raise ValueError(f"review verdict is not accepted for {candidate_id}")
            if not isinstance(review.get("notes"), str) or not review["notes"].strip():
                raise ValueError(f"review notes are required for {candidate_id}")
            reviews_by_id[candidate_id] = review
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        review_error = str(exc)
        reviews_by_id = {}

    findings: list[dict[str, Any]] = []
    if review_error is None:
        for candidate in raw_candidates:
            review = reviews_by_id.get(candidate["candidate_id"])
            if review and review["bucket"] == "extract_enum_candidate":
                findings.append(
                    {
                        **candidate,
                        "bucket": review["bucket"],
                        "confidence": review.get("confidence"),
                        "human_verdict": review["human_verdict"],
                        "review_notes": review["notes"],
                    }
                )
    pending = len(raw_candidates) - len(reviews_by_id) if review_error is None else len(raw_candidates)
    if facts.get("status") == "failed":
        status = "failed"
    elif review_error is not None:
        status = "failed"
        failure_kind = "invalid_human_review"
    elif facts.get("status") != "complete":
        status = "partial"
    elif pending:
        status = "partial"
        failure_kind = "human_review_required"
    else:
        status = "complete"
        failure_kind = None
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "language": "dart",
        "read_only": True,
        "status": status,
        "failure_kind": failure_kind,
        "failure_detail": review_error,
        "target": target.relative_to(root).as_posix(),
        "analyzer": "dart-sdk-lsp-field-definition-operations",
        "findings": findings,
        "classifications": classifications,
        "deferred": deferred,
        "summary": {
            "raw_candidates": len(raw_candidates),
            "accepted": len(findings),
            "pending_review": pending,
            "classified_not_candidate": len(classifications),
            "deferred": len(deferred),
        },
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "query_plan_sha256": facts.get("query_plan_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "limits": [
            *facts.get("limits", []),
            "human verdict required; literals do not prove a closed value domain",
            "serialization, reflection, dynamic access, external compatibility, and Flutter state remain unresolved",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    candidates_text = "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in raw_candidates
    )
    findings_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _atomic(staged / "candidates.jsonl", candidates_text)
    _atomic(staged / "findings.json", findings_text)
    _atomic(staged / "facts.json", json.dumps(facts, indent=2, sort_keys=True) + "\n")
    _atomic(staged / "report.md", _render(payload))
    for review in reviews if review_error is None else []:
        _atomic(
            staged / "scout" / f"{review['candidate_id']}.json",
            json.dumps(review, indent=2, sort_keys=True) + "\n",
        )
    scan = {
        "schema_version": "dart-implicit-state-scan-v1",
        "status": status,
        "failure_kind": failure_kind,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "candidate_count": len(raw_candidates),
        "accepted_count": len(findings),
        "candidates_sha256": hashlib.sha256(candidates_text.encode()).hexdigest(),
        "findings_sha256": hashlib.sha256(findings_text.encode()).hexdigest(),
    }
    _atomic(staged / "scan.json", json.dumps(scan, indent=2, sort_keys=True) + "\n")
    _replace_directory(staged, output)
    print(f"wrote Dart implicit-state evidence: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
