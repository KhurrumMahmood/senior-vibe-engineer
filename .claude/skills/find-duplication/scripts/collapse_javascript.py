#!/usr/bin/env python3
"""Map JavaScript jscpd pairs to conservative lexical symbol spans.

This is a JavaScript-family-local mapping pass, not an AST or semantic
analysis. A pair is retained only when both reported spans fit inside one
named function or block-bodied arrow. Similar text therefore remains human
triage evidence, never a claim that consolidation is behaviorally safe.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


JAVASCRIPT_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs"})
SKIP_DIRECTORIES = frozenset({
    ".git", ".jscpd-input", ".next", ".venv", "__tests__", "build",
    "coverage", "dist", "generated", "node_modules", "reports", "test",
    "tests", "vendor",
})
IDENTIFIER = r"[$A-Za-z_][A-Za-z0-9_$]*"
FUNCTION_RE = re.compile(
    rf"\b(?:export\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>{IDENTIFIER})\s*\("
)
COMMONJS_FUNCTION_RE = re.compile(
    rf"\b(?:module\.)?exports\.(?P<name>{IDENTIFIER})\s*=\s*(?:async\s+)?function\s*\*?\s*\("
)
ARROW_RE = re.compile(
    rf"\b(?:export\s+)?(?:const|let|var)\s+(?P<name>{IDENTIFIER})\s*=\s*(?:async\s+)?(?:\([^;{{}}]*?\)|{IDENTIFIER})\s*=>\s*\{{"
)
COMMONJS_ARROW_RE = re.compile(
    rf"\b(?:module\.)?exports\.(?P<name>{IDENTIFIER})\s*=\s*(?:async\s+)?(?:\([^;{{}}]*?\)|{IDENTIFIER})\s*=>\s*\{{"
)


@dataclass(frozen=True)
class SymbolSpan:
    symbol: str
    start_line: int
    end_line: int


def _looks_like_regex_start(source: str, slash_index: int) -> bool:
    before = source[:slash_index].rstrip()
    if not before:
        return True
    if before.endswith(("=", "(", "[", "{", ",", ":", ";", "!", "?", "=>", "&&", "||")):
        return True
    word_match = re.search(r"([A-Za-z_$][\w$]*)$", before)
    return bool(
        word_match
        and word_match.group(1)
        in {"case", "delete", "in", "instanceof", "new", "return", "throw", "typeof", "void", "yield"}
    )


def _mask_noncode(source: str) -> str:
    """Mask JavaScript literals/comments while retaining line positions."""
    out: list[str] = []
    index = 0
    state = "code"
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and following == "/":
                out.extend((" ", " "))
                index += 2
                state = "line"
                continue
            if char == "/" and following == "*":
                out.extend((" ", " "))
                index += 2
                state = "block"
                continue
            if char in {"'", '"', "`"}:
                out.append(" ")
                index += 1
                state = {"'": "single", '"': "double", "`": "template"}[char]
                continue
            if char == "/" and _looks_like_regex_start(source, index):
                out.append(" ")
                index += 1
                state = "regex"
                continue
            out.append(char)
            index += 1
            continue
        if state == "line":
            out.append("\n" if char == "\n" else " ")
            index += 1
            if char == "\n":
                state = "code"
            continue
        if state == "block":
            if char == "*" and following == "/":
                out.extend((" ", " "))
                index += 2
                state = "code"
            else:
                out.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if state in {"regex", "regex-class"}:
            if char == "\\":
                out.append(" ")
                index += 1
                if index < len(source):
                    out.append("\n" if source[index] == "\n" else " ")
                    index += 1
                continue
            if char == "\n":
                out.append("\n")
                index += 1
                state = "code"
                continue
            out.append(" ")
            index += 1
            if state == "regex" and char == "[":
                state = "regex-class"
            elif state == "regex-class" and char == "]":
                state = "regex"
            elif state == "regex" and char == "/":
                state = "code"
            continue
        quote = {"single": "'", "double": '"', "template": "`"}[state]
        if char == "\\":
            out.append(" ")
            index += 1
            if index < len(source):
                out.append("\n" if source[index] == "\n" else " ")
                index += 1
            continue
        out.append("\n" if char == "\n" else " ")
        index += 1
        if char == quote:
            state = "code"
    if state not in {"code", "line"}:
        raise ValueError(f"unterminated {state}")
    _validate_delimiters("".join(out))
    return "".join(out)


def _validate_delimiters(masked: str) -> None:
    close_for = {"(": ")", "[": "]", "{": "}"}
    open_for = {value: key for key, value in close_for.items()}
    stack: list[tuple[str, int]] = []
    line = 1
    for char in masked:
        if char == "\n":
            line += 1
        elif char in close_for:
            stack.append((char, line))
        elif char in open_for:
            if not stack or stack[-1][0] != open_for[char]:
                raise ValueError(f"unexpected {char!r} on line {line}")
            stack.pop()
    if stack:
        opening, opening_line = stack[-1]
        raise ValueError(f"unclosed {opening!r} from line {opening_line}; expected {close_for[opening]!r}")


def _line_for(source: str, position: int) -> int:
    return source.count("\n", 0, max(0, position)) + 1


def _match_delimiter(source: str, opening: int, left: str, right: str) -> int | None:
    depth = 0
    for index in range(opening, len(source)):
        char = source[index]
        if char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if depth == 0:
                return index
    return None


def _span_from_match(masked: str, match: re.Match[str], *, arrow: bool) -> SymbolSpan | None:
    if arrow:
        opening = masked.rfind("{", match.start(), match.end())
    else:
        params_open = masked.find("(", match.start(), match.end())
        params_end = _match_delimiter(masked, params_open, "(", ")")
        if params_end is None:
            return None
        opening = masked.find("{", params_end)
    if opening < 0:
        return None
    end = _match_delimiter(masked, opening, "{", "}")
    if end is None:
        return None
    return SymbolSpan(
        symbol=match.group("name"),
        start_line=_line_for(masked, match.start()),
        end_line=_line_for(masked, end),
    )


def symbols_in_source(source: str) -> list[SymbolSpan]:
    """Return named JavaScript spans only when lexical bounds are known."""
    masked = _mask_noncode(source)
    spans = [
        span
        for pattern, arrow in (
            (FUNCTION_RE, False),
            (COMMONJS_FUNCTION_RE, False),
            (ARROW_RE, True),
            (COMMONJS_ARROW_RE, True),
        )
        for match in pattern.finditer(masked)
        if (span := _span_from_match(masked, match, arrow=arrow)) is not None
    ]
    return sorted(spans, key=lambda span: (span.start_line, span.end_line - span.start_line))


def _path_is_excluded(path: Path, project_root: Path, target: Path) -> bool:
    if path.is_symlink() or path.suffix.lower() not in JAVASCRIPT_SUFFIXES:
        return True
    name = path.name.lower()
    if (
        ".test." in name
        or ".spec." in name
        or ".generated." in name
        or ".gen." in name
        or name.endswith((".min.js", ".min.jsx", ".min.mjs", ".min.cjs"))
    ):
        return True
    try:
        relative_target = path.resolve().relative_to(target.resolve())
        relative_root = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return True
    return any(
        part.lower() in SKIP_DIRECTORIES
        for part in relative_target.parts[:-1] + relative_root.parts[:-1]
    )


def _site_for(
    record: dict[str, Any], *, project_root: Path, target: Path, symbol_cache: dict[Path, list[SymbolSpan]]
) -> tuple[dict[str, Any] | None, str]:
    name = record.get("name")
    path = Path(name) if isinstance(name, str) and Path(name).is_absolute() else project_root / str(name or "")
    if not name or _path_is_excluded(path, project_root, target):
        return None, "excluded_path"
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, "unreadable_source"
    try:
        start = int(record.get("start") or 0)
        end = int(record.get("end") or start)
    except (TypeError, ValueError):
        return None, "invalid_span"
    if start < 1 or end < start or end > len(source.splitlines()):
        return None, "invalid_span"
    resolved = path.resolve()
    if resolved not in symbol_cache:
        symbol_cache[resolved] = symbols_in_source(source)
    candidates = [span for span in symbol_cache[resolved] if span.start_line <= start <= end <= span.end_line]
    if not candidates:
        return None, "unmapped_symbol"
    symbol = min(candidates, key=lambda span: span.end_line - span.start_line)
    try:
        relative = resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return None, "outside_project_root"
    return {
        "file": relative,
        "symbol": symbol.symbol,
        "method": symbol.symbol,
        "start_line": start,
        "end_line": end,
        "symbol_start_line": symbol.start_line,
        "symbol_end_line": symbol.end_line,
    }, "accepted"


def collapse(*, jscpd: dict[str, Any], project_root: Path, target: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reasons: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    cache: dict[Path, list[SymbolSpan]] = {}
    raw_pairs = jscpd.get("duplicates", []) or []
    for duplicate in raw_pairs:
        if not isinstance(duplicate, dict):
            reasons["invalid_record"] = reasons.get("invalid_record", 0) + 1
            continue
        first, first_reason = _site_for(duplicate.get("firstFile") or {}, project_root=project_root, target=target, symbol_cache=cache)
        second, second_reason = _site_for(duplicate.get("secondFile") or {}, project_root=project_root, target=target, symbol_cache=cache)
        if first is None or second is None:
            reason = first_reason if first is None else second_reason
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        if (first["file"], first["start_line"], first["end_line"]) == (second["file"], second["start_line"], second["end_line"]):
            reasons["same_occurrence"] = reasons.get("same_occurrence", 0) + 1
            continue
        findings.append({
            "finding_id": f"js-jscpd-{len(findings) + 1:04d}",
            "source": "jscpd-javascript",
            "shape_hint": "lexical_clone_cluster",
            "multiplicity": 2,
            "shared_lines_max": int(duplicate.get("lines") or 0),
            "sites": sorted([first, second], key=lambda site: (site["file"], site["start_line"])),
            "raw_pairs_collapsed": 1,
            "consolidation_safety": "unknown_human_review_required",
        })
    return findings, {
        "raw_pair_count": len(raw_pairs),
        "filtered_pair_count": sum(reasons.values()),
        "finding_count": len(findings),
        "filter_reasons": dict(sorted(reasons.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jscpd-report", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.jscpd_report.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: cannot read jscpd report: {exc}", file=sys.stderr)
        return 2
    target, project_root = args.target.resolve(), args.project_root.resolve()
    if not target.is_dir() or not project_root.is_dir():
        print("error: --target and --project-root must be directories", file=sys.stderr)
        return 2
    try:
        findings, stats = collapse(jscpd=report, project_root=project_root, target=target)
    except ValueError as exc:
        print(f"syntax-error: JavaScript lexical span mapping failed: {exc}", file=sys.stderr)
        return 1
    output = {
        "scan_meta": {
            "target": str(args.target), "project_root": str(args.project_root),
            "language": "javascript", "detector": "jscpd-project-local",
            "analysis": "lexical_or_near_lexical_only",
            "consolidation_safety": "unknown_human_review_required",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "jscpd_raw_pair_count": stats["raw_pair_count"],
            "jscpd_filtered_pair_count": stats["filtered_pair_count"],
            "jscpd_finding_count": stats["finding_count"],
            "jscpd_lexical_scan_degraded": False,
            "jscpd_lexical_scan_status": str((report.get("run") or {}).get("status") or "completed"),
            "ast_finding_count": 0, "ast_filtered_count": 0,
            "filter_reasons": stats["filter_reasons"],
        },
        "findings": findings,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"[collapse-javascript] raw={stats['raw_pair_count']} filtered={stats['filtered_pair_count']} findings={stats['finding_count']}", file=sys.stderr)
    print(f"[collapse-javascript] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
