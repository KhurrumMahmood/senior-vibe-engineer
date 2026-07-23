#!/usr/bin/env python3
"""Emit bounded Dart static semantic-duplication leads from accepted D4 facts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "dart-semantic-duplication-v1"
REVIEW_SCHEMA = "dart-semantic-duplication-review-v1"
MISSING_FACT = "complete per-function outgoing call-hierarchy lineage"
SHAPES = {
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}
EXCLUDED_PARTS = {
    ".dart_tool",
    "build",
    "example",
    "generated",
    "integration_test",
    "reports",
    "test",
    "vendor",
}
GENERATED_SUFFIXES = (".g.dart", ".freezed.dart", ".mocks.dart")
TOKEN_RE = re.compile(
    r"[A-Za-z_]\w*|\d+(?:\.\d+)?|==|!=|<=|>=|=>|&&|\|\||\?\?|\?\.|\.\.|\S"
)
FUNCTION_RE = re.compile(
    r"(?m)^[ \t]*(?P<return>[A-Za-z_]\w*(?:\??|<[^\n{};]*>)?)"
    r"[ \t]+(?P<name>[A-Za-z_]\w*)(?P<generic>[ \t]*<[^\n{};]*>)?[ \t]*\("
)
RESERVED_RETURNS = {
    "catch",
    "class",
    "const",
    "else",
    "extension",
    "factory",
    "for",
    "if",
    "mixin",
    "return",
    "switch",
    "typedef",
    "while",
}
LIMITS = [
    "a lead is selected-configuration static evidence, not behavioral equivalence or refactor safety",
    "only authored production top-level non-generic synchronous free functions with explicit return types and direct named-constructor returns are considered",
    "runtime dispatch, reflection, registries, isolates, native/JS interop, generated code, external callers, parts, augmentations, conditional configurations, and Flutter behavior remain unresolved",
    "the consumer compares complete D4 outgoing-call identities and does not infer a universal call graph or parser",
    "machine evidence never chooses a consolidation shape; a content-hash-bound human review is mandatory",
]


class DetectionError(RuntimeError):
    """A typed consumer-local failure."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def _provider() -> Any:
    candidates = [Path(__file__).with_name("dart_lsp_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "dart_lsp_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Dart LSP fact provider is missing")
    spec = importlib.util.spec_from_file_location("dart_duplication_lsp_facts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("assembled Dart LSP fact provider cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _contained(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_output(root: Path, supplied: Path) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(raw))
    allowed = root / "reports" / "semantic-duplication"
    if not _contained(allowed, output) or output == allowed:
        raise DetectionError(
            "failed",
            "unsafe_output_path",
            "output-dir must stay beneath reports/semantic-duplication/ and name a scan",
        )
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise DetectionError(
                "failed", "unsafe_output_path", "output-dir traverses a symbolic link"
            )
    return output


def _replace_directory(staged: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    destination.parent.mkdir(parents=True, exist_ok=True)
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


def _mask_noncode(text: str) -> str:
    """Mask comments and strings while preserving offsets and newlines."""

    chars = list(text)
    masked = list(text)
    index = 0
    while index < len(chars):
        if text.startswith("//", index):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            for position in range(index, end):
                masked[position] = " "
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) if end < 0 else end + 2
            for position in range(index, end):
                if masked[position] not in "\r\n":
                    masked[position] = " "
            index = end
            continue
        raw_prefix = chars[index] in {"r", "R"} and index + 1 < len(chars)
        quote_index = index + 1 if raw_prefix and chars[index + 1] in {"'", '"'} else index
        if chars[quote_index] in {"'", '"'}:
            quote = chars[quote_index]
            triple = text.startswith(quote * 3, quote_index)
            delimiter = quote * (3 if triple else 1)
            start = index
            cursor = quote_index + len(delimiter)
            while cursor < len(chars):
                if not raw_prefix and chars[cursor] == "\\":
                    cursor += 2
                    continue
                if text.startswith(delimiter, cursor):
                    cursor += len(delimiter)
                    break
                cursor += 1
            for position in range(start, min(cursor, len(chars))):
                if masked[position] not in "\r\n":
                    masked[position] = " "
            index = cursor
            continue
        index += 1
    return "".join(masked)


def _brace_depths(masked: str) -> list[int]:
    depths: list[int] = [0] * (len(masked) + 1)
    depth = 0
    for index, character in enumerate(masked):
        depths[index] = depth
        if character == "{":
            depth += 1
        elif character == "}" and depth:
            depth -= 1
    depths[len(masked)] = depth
    return depths


def _balanced(masked: str, start: int, opening: str, closing: str) -> int | None:
    if start >= len(masked) or masked[start] != opening:
        return None
    depth = 0
    for index in range(start, len(masked)):
        if masked[index] == opening:
            depth += 1
        elif masked[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    start = text.rfind("\n", 0, offset) + 1
    return line, offset - start + 1


def _span(text: str, path: str, start: int, end: int) -> dict[str, Any]:
    start_line, start_column = _line_column(text, start)
    end_line, end_column = _line_column(text, end)
    return {
        "path": path,
        "start_line": start_line,
        "start_column": start_column,
        "end_line": end_line,
        "end_column": end_column,
        "sha256": hashlib.sha256(text[start:end].encode()).hexdigest(),
    }


def _source_files(target: Path) -> list[Path]:
    rows: list[Path] = []
    for path in sorted(target.rglob("*.dart")):
        relative = path.relative_to(target)
        if (
            path.is_symlink()
            or any(part in EXCLUDED_PARTS for part in relative.parts)
            or path.name.endswith(GENERATED_SUFFIXES)
        ):
            continue
        rows.append(path)
    return rows


def _declarations(root: Path, target: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    top_level: list[dict[str, Any]] = []
    nested: list[dict[str, Any]] = []
    for path in _source_files(target):
        text = path.read_text(encoding="utf-8")
        masked = _mask_noncode(text)
        depths = _brace_depths(masked)
        relative = path.relative_to(root).as_posix()
        for match in FUNCTION_RE.finditer(masked):
            returned = match.group("return")
            if returned in RESERVED_RETURNS:
                continue
            opening = masked.find("(", match.start("name") + len(match.group("name")))
            closing = _balanced(masked, opening, "(", ")")
            if closing is None:
                continue
            cursor = closing + 1
            while cursor < len(masked) and masked[cursor].isspace():
                cursor += 1
            modifier_start = cursor
            modifier_match = re.match(r"(?:(?:async|sync)\s*\*?\s*)", masked[cursor:])
            modifier = modifier_match.group(0).strip() if modifier_match else ""
            if modifier_match:
                cursor += len(modifier_match.group(0))
                while cursor < len(masked) and masked[cursor].isspace():
                    cursor += 1
            if masked.startswith("=>", cursor):
                body_start = cursor
                body_end = masked.find(";", cursor + 2)
                if body_end < 0:
                    continue
                body_end += 1
                body_kind = "expression"
            elif cursor < len(masked) and masked[cursor] == "{":
                close_body = _balanced(masked, cursor, "{", "}")
                if close_body is None:
                    continue
                body_start, body_end, body_kind = cursor, close_body + 1, "block"
            else:
                continue
            name_start, name_end = match.start("name"), match.end("name")
            row = {
                "path": relative,
                "name": match.group("name"),
                "return_type": returned.strip(),
                "generic": bool(match.group("generic")),
                "parameters": text[opening + 1 : closing],
                "modifier": modifier,
                "header": text[match.start() : modifier_start],
                "body": text[body_start:body_end],
                "body_masked": masked[body_start:body_end],
                "body_kind": body_kind,
                "source_span": _span(text, relative, match.start(), body_end),
                "name_span": _span(text, relative, name_start, name_end),
            }
            (top_level if depths[match.start()] == 0 else nested).append(row)
    return top_level, nested


def _named_fields(arguments: str) -> list[str]:
    fields: list[str] = []
    depth = 0
    start = 0
    segments: list[str] = []
    for index, character in enumerate(arguments):
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            segments.append(arguments[start:index])
            start = index + 1
    segments.append(arguments[start:])
    for segment in segments:
        match = re.match(r"\s*([A-Za-z_]\w*)\s*:", segment)
        if match:
            fields.append(match.group(1))
    return sorted(set(fields))


def _direct_constructor(row: dict[str, Any]) -> tuple[str, list[str]] | None:
    body = row["body_masked"]
    if row["body_kind"] == "block":
        returns = list(
            re.finditer(r"\breturn\s+([A-Z]\w*(?:\.[A-Za-z_]\w*)?)\s*\(", body)
        )
    else:
        returns = list(re.finditer(r"=>\s*([A-Z]\w*(?:\.[A-Za-z_]\w*)?)\s*\(", body))
    if len(returns) != 1:
        return None
    match = returns[0]
    opening = body.find("(", match.start(1) + len(match.group(1)))
    closing = _balanced(body, opening, "(", ")")
    if closing is None:
        return None
    constructor = match.group(1)
    returned_base = re.split(r"[?<]", row["return_type"], maxsplit=1)[0]
    if constructor.split(".", 1)[0] != returned_base:
        return None
    fields = _named_fields(row["body"][opening + 1 : closing])
    return constructor, fields


def _lexical(row: dict[str, Any]) -> tuple[list[str], str]:
    tokens = TOKEN_RE.findall(row["body_masked"])
    normalized = " ".join(tokens)
    return tokens, hashlib.sha256(normalized.encode()).hexdigest()


def _classify_declarations(
    top_level: list[dict[str, Any]], nested: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible: list[dict[str, Any]] = []
    ineligible: list[dict[str, Any]] = []
    for row in nested:
        ineligible.append(
            {"path": row["path"], "name": row["name"], "reason": "not_top_level_free_function"}
        )
    for row in top_level:
        reason: str | None = None
        combined = f"{row['header']} {row['parameters']} {row['modifier']} {row['body_masked']}"
        if row["generic"]:
            reason = "generic_function"
        elif row["return_type"] in {"dynamic", "void"}:
            reason = "unsupported_or_implicit_return_type"
        elif row["return_type"].startswith(("Future", "Stream")) or row["modifier"]:
            reason = "not_synchronous"
        elif re.search(r"\bdynamic\b", combined):
            reason = "dynamic_syntax"
        direct = _direct_constructor(row) if reason is None else None
        if reason is None and direct is None:
            if re.search(r"(?:\breturn\s+|=>\s*)[a-z_]\w*\s*\(", row["body_masked"]):
                reason = "wrapper_without_direct_constructor_return"
            else:
                reason = "no_direct_named_constructor_return"
        if reason is None and direct is not None and len(direct[1]) < 2:
            reason = "insufficient_named_return_fields"
        if reason is not None:
            ineligible.append({"path": row["path"], "name": row["name"], "reason": reason})
            continue
        assert direct is not None
        tokens, lexical_hash = _lexical(row)
        eligible.append(
            {
                **row,
                "constructor_spelling": direct[0],
                "return_fields": direct[1],
                "policy_markers": {
                    marker: bool(re.search(rf"\b{marker}\b", row["body_masked"]))
                    for marker in ("throw", "rethrow", "try", "catch", "await")
                },
                "lexical_tokens": tokens,
                "lexical_hash": lexical_hash,
            }
        )
    return eligible, ineligible


def _query_index(facts: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in facts.get("call_hierarchy_queries", []):
        caller = row.get("caller", {})
        if caller.get("kind_name") != "function":
            continue
        key = (caller.get("path"), caller.get("name"))
        result.setdefault(key, []).append(row)
    return result


def _identity_span(root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    relative = identity["path"]
    source = (root / relative).read_text(encoding="utf-8")
    selection = identity["selection_range"]
    lines = source.splitlines(keepends=True)

    def offset(line: int, column: int) -> int:
        return sum(len(item) for item in lines[: line - 1]) + column - 1

    start = offset(selection["line"], selection["column"])
    end = offset(selection["end_line"], selection["end_column"])
    return _span(source, relative, start, end)


def _call_facts(
    root: Path,
    facts: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index = _query_index(facts)
    usable: list[dict[str, Any]] = []
    ineligible: list[dict[str, Any]] = []
    all_queries = [row for rows in index.values() for row in rows]
    for candidate in candidates:
        matches = index.get((candidate["path"], candidate["name"]), [])
        caller_identity = matches[0].get("caller", {}) if len(matches) == 1 else {}
        if (
            len(matches) != 1
            or matches[0].get("status") != "complete"
            or caller_identity.get("origin") != "first-party"
            or caller_identity.get("role") != "production"
            or matches[0].get("source_sha256") != _sha256(root / candidate["path"])
        ):
            ineligible.append(
                {
                    "path": candidate["path"],
                    "name": candidate["name"],
                    "reason": "incomplete_call_hierarchy",
                }
            )
            continue
        query = matches[0]
        constructor_edges = [
            edge
            for edge in query["outgoing_calls"]
            if edge["callee"].get("kind_name") == "constructor"
            and edge["callee"].get("name") == candidate["constructor_spelling"].split(".", 1)[0]
            and edge.get("resolution") == "resolved-first-party"
            and edge["callee"].get("role") == "production"
        ]
        if len(constructor_edges) != 1:
            ineligible.append(
                {
                    "path": candidate["path"],
                    "name": candidate["name"],
                    "reason": "constructor_identity_not_resolved",
                }
            )
            continue
        nonconstructors = [
            edge
            for edge in query["outgoing_calls"]
            if edge["callee"].get("kind_name") != "constructor"
        ]
        if any(edge.get("resolution") != "resolved-first-party" for edge in nonconstructors):
            ineligible.append(
                {
                    "path": candidate["path"],
                    "name": candidate["name"],
                    "reason": "non_first_party_callee_boundary",
                }
            )
            continue
        callers: list[dict[str, Any]] = []
        symbol_id = query["caller"]["symbol_id"]
        for caller_query in all_queries:
            caller = caller_query["caller"]
            if (
                caller_query.get("status") != "complete"
                or caller.get("origin") != "first-party"
                or caller.get("role") != "production"
                or caller.get("kind_name") != "function"
                or caller.get("symbol_id") == symbol_id
            ):
                continue
            for edge in caller_query.get("outgoing_calls", []):
                if edge["callee"].get("symbol_id") != symbol_id:
                    continue
                callers.append(
                    {
                        "symbol_id": caller["symbol_id"],
                        "name": caller["name"],
                        "path": caller["path"],
                        "source_span": _identity_span(root, caller),
                        "call_sites": edge["call_sites"],
                    }
                )
        callers.sort(key=lambda row: (row["path"], row["name"], row["symbol_id"]))
        usable.append(
            {
                **candidate,
                "symbol_id": symbol_id,
                "resolved_source_span": _identity_span(root, query["caller"]),
                "constructor_target": constructor_edges[0]["callee"],
                "first_party_nonconstructor_callees": sorted(
                    [edge["callee"] for edge in nonconstructors],
                    key=lambda row: row["symbol_id"],
                ),
                "direct_callers": callers,
                "fact_status": query["status"],
            }
        )
    return usable, ineligible


def _similarity(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return 1.0 if not union else len(left_set & right_set) / len(union)


def _public_member(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol_id": row["symbol_id"],
        "name": row["name"],
        "path": row["path"],
        "return_type": row["return_type"],
        "return_fields": row["return_fields"],
        "source_span": row["resolved_source_span"],
        "lexical_sha256": row["lexical_hash"],
        "policy_markers": row["policy_markers"],
        "first_party_nonconstructor_callees": row["first_party_nonconstructor_callees"],
        "constructor_target": row["constructor_target"],
        "direct_callers": row["direct_callers"],
        "fact_status": row["fact_status"],
    }


def _pair_candidates(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for left, right in itertools.combinations(candidates, 2):
        if (
            left["return_type"] != right["return_type"]
            or left["return_fields"] != right["return_fields"]
            or left["constructor_target"]["symbol_id"]
            != right["constructor_target"]["symbol_id"]
        ):
            continue
        pair = [
            {"path": left["path"], "name": left["name"]},
            {"path": right["path"], "name": right["name"]},
        ]
        similarity = _similarity(left["lexical_tokens"], right["lexical_tokens"])
        if left["lexical_hash"] == right["lexical_hash"] or similarity >= 0.95:
            rejected.append(
                {"members": pair, "reason": "lexical_clone", "lexical_similarity": similarity}
            )
            continue
        left_calls = {
            row["symbol_id"] for row in left["first_party_nonconstructor_callees"]
        }
        right_calls = {
            row["symbol_id"] for row in right["first_party_nonconstructor_callees"]
        }
        if right["symbol_id"] in left_calls or left["symbol_id"] in right_calls:
            rejected.append({"members": pair, "reason": "member_to_member_wrapper"})
            continue
        if left_calls != right_calls:
            rejected.append(
                {"members": pair, "reason": "first_party_policy_callee_mismatch"}
            )
            continue
        if left["policy_markers"] != right["policy_markers"]:
            rejected.append({"members": pair, "reason": "policy_marker_mismatch"})
            continue
        left_callers = {row["symbol_id"] for row in left["direct_callers"]}
        right_callers = {row["symbol_id"] for row in right["direct_callers"]}
        if not left_callers or not right_callers:
            rejected.append({"members": pair, "reason": "first_party_caller_evidence_missing"})
            continue
        if left_callers == right_callers:
            rejected.append(
                {"members": pair, "reason": "distinct_first_party_callers_not_established"}
            )
            continue
        accepted.append(
            {
                "members": sorted(
                    [_public_member(left), _public_member(right)],
                    key=lambda row: (row["path"], row["name"]),
                ),
                "return_shape": {
                    "type": left["return_type"],
                    "fields": left["return_fields"],
                },
                "constructor_target": left["constructor_target"],
                "first_party_nonconstructor_callees": left[
                    "first_party_nonconstructor_callees"
                ],
                "policy_markers": left["policy_markers"],
                "lexical_similarity": round(similarity, 6),
                "machine_consolidation_shape": None,
                "human_verdict": "required",
                "static_lead_only": True,
            }
        )
    accepted.sort(key=lambda row: [(member["path"], member["name"]) for member in row["members"]])
    rejected.sort(key=_canonical_hash)
    return accepted, rejected


def _matrix(candidate_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "dart-semantic-capability-matrix-v1",
        "language": "dart",
        "candidate_id": candidate_id,
        "static_lead_only": True,
        "return_shape": candidate["return_shape"],
        "constructor_target": candidate["constructor_target"],
        "first_party_nonconstructor_callees": candidate[
            "first_party_nonconstructor_callees"
        ],
        "policy_markers": candidate["policy_markers"],
        "lexical_similarity": candidate["lexical_similarity"],
        "members": candidate["members"],
        "machine_consolidation_shape": None,
        "limitations": LIMITS,
    }


def _matrix_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        f"# Dart static capability matrix — {matrix['candidate_id']}",
        "",
        "This matrix is a conservative review lead. It does not establish behavioral equivalence or consolidation safety.",
        "",
        "| Function | Return fields | First-party callees | Resolved production callers |",
        "|---|---|---|---:|",
    ]
    callee_names = ", ".join(
        row["name"] for row in matrix["first_party_nonconstructor_callees"]
    )
    for member in matrix["members"]:
        lines.append(
            f"| `{member['path']}::{member['name']}` | "
            f"`{', '.join(matrix['return_shape']['fields'])}` | "
            f"`{callee_names}` | {len(member['direct_callers'])} |"
        )
    lines.extend(
        [
            "",
            f"- Constructor identity: `{matrix['constructor_target']['symbol_id']}`",
            f"- Lexical token-set similarity: `{matrix['lexical_similarity']}`",
            "- Consolidation shape: not selected by machine evidence",
            "",
        ]
    )
    return "\n".join(lines)


def _review(
    candidate: dict[str, Any], reviews_dir: Path | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if reviews_dir is None:
        return None, None
    path = reviews_dir / f"{candidate['candidate_id']}.json"
    if not path.is_file() or path.is_symlink():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DetectionError("failed", "invalid_human_review", str(exc)) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != REVIEW_SCHEMA
        or payload.get("candidate_id") != candidate["candidate_id"]
        or payload.get("candidate_sha256") != candidate["candidate_sha256"]
        or payload.get("human_verdict") not in {"accepted", "rejected"}
        or not isinstance(payload.get("reviewer"), str)
        or not payload["reviewer"].strip()
        or not isinstance(payload.get("notes"), str)
        or not payload["notes"].strip()
    ):
        raise DetectionError(
            "failed",
            "invalid_human_review",
            f"review does not verify candidate {candidate['candidate_id']}",
        )
    if payload["human_verdict"] == "accepted" and payload.get("consolidation_shape") not in SHAPES:
        raise DetectionError(
            "failed", "invalid_human_review", "accepted review requires a supported shape"
        )
    if payload["human_verdict"] == "rejected" and payload.get("consolidation_shape") is not None:
        raise DetectionError(
            "failed", "invalid_human_review", "rejected review must not select a shape"
        )
    review_sha = _sha256(path)
    return payload, {"path": path, "sha256": review_sha}


def _configuration_hashes(root: Path, facts: dict[str, Any]) -> list[dict[str, str]]:
    paths: list[Path] = []
    pubspec = root / "pubspec.yaml"
    if pubspec.is_file() and not pubspec.is_symlink():
        paths.append(pubspec)
    raw_config = facts.get("package_config", {}).get("path")
    if isinstance(raw_config, str) and raw_config:
        config = Path(os.path.realpath(Path(raw_config)))
        if _contained(root, config) and config.is_file() and not config.is_symlink():
            paths.append(config)
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
        for path in sorted(set(paths))
    ]


def _terminal(
    status: str,
    failure_kind: str,
    detail: str,
    *,
    target: str,
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts = facts or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "find-semantic-duplication",
        "language": "dart",
        "read_only": True,
        "status": status,
        "failure_kind": failure_kind,
        "message": detail,
        "target": target,
        "upstream_status": facts.get("status"),
        "upstream_failure_kind": facts.get("failure_kind"),
        "provider_query_plan": facts.get("query_plan", {}),
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "query_plan_sha256": facts.get("query_plan_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "configuration_hashes": [],
        "machine_candidates": [],
        "confirmed": [],
        "rejected": [],
        "ineligible": [],
        "uncertain": [{"reason": failure_kind, "detail": detail}],
        "missing_required_facts": [MISSING_FACT],
        "summary": {
            "machine_candidates": 0,
            "review_required_leads": 0,
            "confirmed": 0,
            "rejected": 0,
            "ineligible": 0,
        },
        "limits": LIMITS,
    }


def _build(
    root: Path,
    target: Path,
    facts: dict[str, Any],
    reviews_dir: Path | None,
) -> tuple[dict[str, Any], dict[str, str], list[dict[str, Any]]]:
    requests = set(facts.get("query_plan", {}).get("requests", []))
    required = {"textDocument/prepareCallHierarchy", "callHierarchy/outgoingCalls"}
    if not required.issubset(requests) or not isinstance(facts.get("call_hierarchy_queries"), list):
        return (
            _terminal(
                "partial",
                "accepted_provider_fact_gap",
                "the accepted provider does not expose outgoing call-hierarchy facts",
                target=target.relative_to(root).as_posix(),
                facts=facts,
            ),
            {},
            [],
        )
    if facts.get("status") == "failed":
        return (
            _terminal(
                "failed",
                facts.get("failure_kind") or "upstream_semantic_failure",
                "the D4 fact pack failed",
                target=target.relative_to(root).as_posix(),
                facts=facts,
            ),
            {},
            [],
        )

    top_level, nested = _declarations(root, target)
    syntax_candidates, ineligible = _classify_declarations(top_level, nested)
    fact_candidates, fact_ineligible = _call_facts(root, facts, syntax_candidates)
    ineligible.extend(fact_ineligible)
    machine, rejected = _pair_candidates(fact_candidates)
    matrices: dict[str, str] = {}
    matrix_payloads: list[dict[str, Any]] = []
    machine_candidates: list[dict[str, Any]] = []
    for index, row in enumerate(machine, 1):
        candidate_id = f"DART-SD-{index:04d}"
        matrix_payload = _matrix(candidate_id, row)
        matrix_relative = f"capability_matrices/{candidate_id}.json"
        matrix_text = json.dumps(matrix_payload, indent=2, sort_keys=True) + "\n"
        matrices[matrix_relative] = matrix_text
        matrices[f"capability_matrices/{candidate_id}.md"] = _matrix_markdown(matrix_payload)
        candidate = {
            "candidate_id": candidate_id,
            **row,
            "fact_pack_sha256": facts.get("fact_pack_sha256"),
            "query_plan_sha256": facts.get("query_plan_sha256"),
            "capability_matrix_path": matrix_relative,
            "capability_matrix_sha256": hashlib.sha256(matrix_text.encode()).hexdigest(),
        }
        candidate["candidate_sha256"] = _canonical_hash(candidate)
        machine_candidates.append(candidate)
        matrix_payloads.append(matrix_payload)

    confirmed: list[dict[str, Any]] = []
    copied_reviews: list[dict[str, Any]] = []
    pending = 0
    for candidate in machine_candidates:
        review, review_file = _review(candidate, reviews_dir)
        if review is None:
            pending += 1
            continue
        assert review_file is not None
        copied_reviews.append(review_file)
        if review["human_verdict"] == "rejected":
            rejected.append(
                {
                    "members": [
                        {"path": row["path"], "name": row["name"]}
                        for row in candidate["members"]
                    ],
                    "reason": "human_rejected_static_lead",
                    "candidate_id": candidate["candidate_id"],
                }
            )
            continue
        finding = {
            **candidate,
            "investigation_status": "accepted_static_lead",
            "human_verdict": "accepted",
            "consolidation_shape": review["consolidation_shape"],
            "review": {
                "schema_version": review["schema_version"],
                "reviewer": review["reviewer"],
                "notes": review["notes"],
                "candidate_sha256": review["candidate_sha256"],
                "review_artifact_sha256": review_file["sha256"],
            },
        }
        finding["finding_sha256"] = _canonical_hash(finding)
        confirmed.append(finding)

    if pending:
        status, failure_kind = "partial", "human_review_required"
    elif not machine_candidates and facts.get("status") != "complete":
        status, failure_kind = "partial", "incomplete_selected_semantic_surface"
    else:
        status, failure_kind = "complete", None
    source_hashes = facts.get("source_hashes", [])
    configuration_hashes = _configuration_hashes(root, facts)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "skill": "find-semantic-duplication",
        "language": "dart",
        "read_only": True,
        "status": status,
        "failure_kind": failure_kind,
        "target": target.relative_to(root).as_posix(),
        "upstream_status": facts.get("status"),
        "upstream_failure_kind": facts.get("failure_kind"),
        "provider_query_plan": facts.get("query_plan", {}),
        "provider_call_hierarchy_summary": facts.get("call_hierarchy_summary", {}),
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "query_plan_sha256": facts.get("query_plan_sha256"),
        "source_hashes": source_hashes,
        "configuration_hashes": configuration_hashes,
        "machine_candidates": machine_candidates,
        "confirmed": confirmed,
        "rejected": sorted(rejected, key=_canonical_hash),
        "ineligible": sorted(ineligible, key=lambda row: (row["path"], row["name"], row["reason"])),
        "uncertain": [],
        "missing_required_facts": [],
        "summary": {
            "machine_candidates": len(machine_candidates),
            "review_required_leads": pending,
            "confirmed": len(confirmed),
            "rejected": len(rejected),
            "ineligible": len(ineligible),
        },
        "limits": LIMITS,
    }
    return payload, matrices, copied_reviews


def _triage(payload: dict[str, Any]) -> str:
    lines = [
        "# find-semantic-duplication — Dart triage",
        "",
        f"Status: `{payload['status']}`",
        f"Failure kind: `{payload.get('failure_kind')}`",
        "",
    ]
    if payload["confirmed"]:
        lines.append(
            "> Human-reviewed static review lead(s) are ready for proposal consumption; no behavioral equivalence or consolidation safety is claimed."
        )
        lines.append("")
        for finding in payload["confirmed"]:
            names = " / ".join(row["name"] for row in finding["members"])
            lines.append(
                f"- `{finding['candidate_id']}` — {names}; human shape `{finding['consolidation_shape']}`"
            )
    elif payload["machine_candidates"]:
        lines.append(
            "> Machine evidence found a conservative static review lead. A candidate-hash-bound human verdict must select or reject the shape."
        )
    else:
        lines.append("> No evidence-backed Dart static review lead was promoted.")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in LIMITS)
    return "\n".join(lines).rstrip() + "\n"


def _write(
    output: Path,
    payload: dict[str, Any],
    facts: dict[str, Any],
    matrices: dict[str, str],
    copied_reviews: list[dict[str, Any]],
) -> None:
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir(parents=True)
    try:
        for relative, text in matrices.items():
            _atomic(staged / relative, text)
        candidates_text = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in payload["machine_candidates"]
        )
        analysis_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        findings = {
            "schema_version": SCHEMA_VERSION,
            "skill": "find-semantic-duplication",
            "language": "dart",
            "status": payload["status"],
            "failure_kind": payload["failure_kind"],
            "fact_pack_sha256": payload["fact_pack_sha256"],
            "query_plan_sha256": payload["query_plan_sha256"],
            "source_hashes": payload["source_hashes"],
            "configuration_hashes": payload["configuration_hashes"],
            "findings": payload["confirmed"],
            "summary": payload["summary"],
            "limits": LIMITS,
        }
        findings_text = json.dumps(findings, indent=2, sort_keys=True) + "\n"
        _atomic(staged / "analysis.json", analysis_text)
        _atomic(staged / "findings.json", findings_text)
        _atomic(staged / "facts.json", json.dumps(facts, indent=2, sort_keys=True) + "\n")
        _atomic(staged / "candidates.jsonl", candidates_text)
        _atomic(staged / "triage.md", _triage(payload))
        for review in copied_reviews:
            _atomic(staged / "scout" / review["path"].name, review["path"].read_text())
        matrix_hashes = {
            relative: hashlib.sha256(text.encode()).hexdigest()
            for relative, text in matrices.items()
            if relative.endswith(".json")
        }
        scan = {
            "schema_version": "dart-semantic-duplication-scan-v1",
            "status": payload["status"],
            "failure_kind": payload["failure_kind"],
            "fact_pack_sha256": payload["fact_pack_sha256"],
            "query_plan_sha256": payload["query_plan_sha256"],
            "analysis_sha256": hashlib.sha256(analysis_text.encode()).hexdigest(),
            "findings_sha256": hashlib.sha256(findings_text.encode()).hexdigest(),
            "capability_matrix_hashes": matrix_hashes,
            "source_hashes_sha256": _canonical_hash(payload["source_hashes"]),
            "configuration_hashes_sha256": _canonical_hash(payload["configuration_hashes"]),
            "confirmed": len(payload["confirmed"]),
            "review_required_leads": payload["summary"]["review_required_leads"],
        }
        _atomic(staged / "scan.json", json.dumps(scan, indent=2, sort_keys=True) + "\n")
        _replace_directory(staged, output)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--reviews-dir", type=Path)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        if not _contained(root, target):
            raise DetectionError("failed", "unsafe_target", "target must stay in project root")
        output = _safe_output(root, args.output_dir)
    except DetectionError as exc:
        parser.error(exc.detail)
    top_level, _ = _declarations(root, target)
    syntax_candidates, _ = _classify_declarations(top_level, [])
    candidate_names = {row["name"] for row in syntax_candidates}
    queries = sorted(
        {
            row["name"]
            for row in top_level
            if row["name"] in candidate_names
            or any(
                re.search(rf"\b{re.escape(name)}\s*\(", row["body_masked"])
                for name in candidate_names
            )
        }
    )
    provider = _provider()
    facts: dict[str, Any] = {}
    try:
        facts = provider.load_or_collect(
            facts=args.facts,
            project_root=root,
            target=args.target,
            queries=queries,
            dart=args.dart,
            packages=args.packages,
            cache_dir=args.cache_dir,
            timeout=args.timeout,
        )
        reviews_dir = None
        if args.reviews_dir is not None:
            reviews_dir = Path(os.path.realpath(args.reviews_dir.resolve(strict=True)))
            if not reviews_dir.is_dir():
                raise DetectionError(
                    "failed", "invalid_human_review", "reviews-dir is not a directory"
                )
        payload, matrices, copied_reviews = _build(root, target, facts, reviews_dir)
        exit_code = 2 if payload["status"] == "failed" else 0
    except DetectionError as exc:
        payload = _terminal(
            exc.status,
            exc.failure_kind,
            exc.detail,
            target=target.relative_to(root).as_posix(),
            facts=facts,
        )
        matrices, copied_reviews, exit_code = {}, [], 2
    except (provider.DartFactError, OSError, ValueError, json.JSONDecodeError) as exc:
        payload = _terminal(
            "failed",
            "invalid_or_stale_provider_facts",
            str(exc),
            target=target.relative_to(root).as_posix(),
            facts=facts,
        )
        matrices, copied_reviews, exit_code = {}, [], 2
    _write(output, payload, facts, matrices, copied_reviews)
    print(f"wrote Dart semantic-duplication evidence: {output}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
