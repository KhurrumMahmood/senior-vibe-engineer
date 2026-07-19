#!/usr/bin/env python3
"""Collapse jscpd TypeScript pairs into reliable lexical-clone clusters.

This is deliberately not a TypeScript parser or semantic analyser.  It masks
comments and strings, maps the narrow declaration forms it can prove (function
declarations and block-bodied arrows), and *drops* a jscpd pair when either
site lacks a reliable enclosing symbol.  It also drops overload signatures and
the generated/test/declaration/vendor boundary even if a hand-supplied jscpd
report contains them.  The output is evidence for human triage only.
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


TYPESCRIPT_SUFFIXES = frozenset({".ts", ".tsx"})
SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".next",
        ".venv",
        "__tests__",
        "build",
        "coverage",
        "dist",
        "generated",
        "node_modules",
        "test",
        "tests",
        "vendor",
    }
)
IDENTIFIER = r"[$A-Za-z_][A-Za-z0-9_$]*"
FUNCTION_RE = re.compile(
    rf"\b(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>{IDENTIFIER})\s*(?:<[^{{}};()]*>)?\s*\("
)
ARROW_RE = re.compile(
    rf"\b(?:export\s+)?(?:declare\s+)?(?:const|let|var)\s+(?P<name>{IDENTIFIER})\s*=\s*(?:async\s+)?(?:\([^;{{}}]*?\)|{IDENTIFIER})\s*(?::[^=;{{}}]+)?=>\s*\{{"
)


@dataclass(frozen=True)
class SymbolSpan:
    symbol: str
    start_line: int
    end_line: int
    overload_signature: bool


def _mask_noncode(source: str) -> str:
    """Mask TypeScript strings/comments without changing any line positions."""
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
                continue
            out.append("\n" if char == "\n" else " ")
            index += 1
            continue
        if char == "\\":
            out.append(" ")
            index += 1
            if index < len(source):
                escaped = source[index]
                out.append("\n" if escaped == "\n" else " ")
                index += 1
            continue
        quote = {"single": "'", "double": '"', "template": "`"}[state]
        out.append("\n" if char == "\n" else " ")
        index += 1
        if char == quote:
            state = "code"
    return "".join(out)


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


def _function_tail(masked: str, params_end: int) -> tuple[int, bool] | None:
    """Return the final declaration/body position and overload state."""
    index = params_end + 1
    parens = brackets = angles = 0
    return_type = False

    def previous_nonspace(position: int) -> str:
        while position >= 0 and masked[position].isspace():
            position -= 1
        return masked[position] if position >= 0 else ""

    while index < len(masked):
        char = masked[index]
        if char == ":" and not (parens or brackets or angles):
            return_type = True
        elif char == "(":
            parens += 1
        elif char == ")" and parens:
            parens -= 1
        elif char == "[":
            brackets += 1
        elif char == "]" and brackets:
            brackets -= 1
        elif char == "<":
            angles += 1
        elif char == ">" and angles:
            angles -= 1
        elif char == "{":
            is_type_literal = return_type and (
                parens
                or brackets
                or angles
                or previous_nonspace(index - 1) in {":", "|", "&", "=", ",", "(", "["}
            )
            if is_type_literal:
                type_end = _match_delimiter(masked, index, "{", "}")
                if type_end is None:
                    return None
                index = type_end + 1
                continue
            end = _match_delimiter(masked, index, "{", "}")
            return (end, False) if end is not None else None
        elif char == ";" and not (parens or brackets or angles):
            return index, True
        index += 1
    return None


def symbols_in_source(source: str) -> list[SymbolSpan]:
    """Return only symbol spans whose lexical bounds can be established."""
    masked = _mask_noncode(source)
    spans: list[SymbolSpan] = []
    for match in FUNCTION_RE.finditer(masked):
        opening = masked.find("(", match.start(), match.end())
        params_end = _match_delimiter(masked, opening, "(", ")")
        if params_end is None:
            continue
        tail = _function_tail(masked, params_end)
        if tail is None:
            continue
        end, overload = tail
        spans.append(
            SymbolSpan(
                symbol=match.group("name"),
                start_line=_line_for(masked, match.start()),
                end_line=_line_for(masked, end),
                overload_signature=overload,
            )
        )
    for match in ARROW_RE.finditer(masked):
        opening = masked.rfind("{", match.start(), match.end())
        end = _match_delimiter(masked, opening, "{", "}")
        if end is None:
            continue
        spans.append(
            SymbolSpan(
                symbol=match.group("name"),
                start_line=_line_for(masked, match.start()),
                end_line=_line_for(masked, end),
                overload_signature=False,
            )
        )
    return sorted(spans, key=lambda span: (span.start_line, span.end_line - span.start_line))


def _path_is_excluded(path: Path, project_root: Path, target: Path) -> bool:
    if path.suffix.lower() not in TYPESCRIPT_SUFFIXES:
        return True
    if path.name.lower().endswith(".d.ts"):
        return True
    name = path.name.lower()
    if ".test." in name or ".spec." in name or ".generated." in name or ".gen." in name:
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


def _resolve_name(name: object, project_root: Path) -> Path | None:
    if not isinstance(name, str) or not name:
        return None
    path = Path(name)
    return path if path.is_absolute() else project_root / path


def _site_for(
    record: dict[str, Any],
    *,
    project_root: Path,
    target: Path,
    symbol_cache: dict[Path, list[SymbolSpan]],
) -> tuple[dict[str, Any] | None, str]:
    path = _resolve_name(record.get("name"), project_root)
    if path is None or _path_is_excluded(path, project_root, target):
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
    spans = symbol_cache.setdefault(path.resolve(), symbols_in_source(source))
    candidates = [span for span in spans if span.start_line <= start <= span.end_line]
    if not candidates:
        return None, "unmapped_symbol"
    symbol = min(candidates, key=lambda span: span.end_line - span.start_line)
    if symbol.overload_signature:
        return None, "overload_signature"
    try:
        relative = path.resolve().relative_to(project_root.resolve()).as_posix()
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


def _union_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parents = list(range(len(groups)))

    def find(value: int) -> int:
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    by_site: dict[tuple[str, str], list[int]] = {}
    for index, group in enumerate(groups):
        for site in group["sites"].values():
            by_site.setdefault((site["file"], site["symbol"]), []).append(index)
    for indices in by_site.values():
        for index in indices[1:]:
            union(indices[0], index)

    merged: dict[int, dict[str, Any]] = {}
    for index, group in enumerate(groups):
        bucket = merged.setdefault(
            find(index), {"sites": {}, "shared_lines_max": 0, "raw_pairs_collapsed": 0}
        )
        bucket["sites"].update(group["sites"])
        bucket["shared_lines_max"] = max(bucket["shared_lines_max"], group["shared_lines_max"])
        bucket["raw_pairs_collapsed"] += group["raw_pairs_collapsed"]
    return list(merged.values())


def collapse(
    *, jscpd: dict[str, Any], project_root: Path, target: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    symbol_cache: dict[Path, list[SymbolSpan]] = {}
    raw_pairs = jscpd.get("duplicates", []) or []
    for duplicate in raw_pairs:
        if not isinstance(duplicate, dict):
            reasons["invalid_record"] = reasons.get("invalid_record", 0) + 1
            continue
        first, first_reason = _site_for(
            duplicate.get("firstFile") or {}, project_root=project_root, target=target,
            symbol_cache=symbol_cache,
        )
        second, second_reason = _site_for(
            duplicate.get("secondFile") or {}, project_root=project_root, target=target,
            symbol_cache=symbol_cache,
        )
        if first is None or second is None:
            reason = first_reason if first is None else second_reason
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        if first["file"] == second["file"] and first["symbol"] == second["symbol"]:
            reasons["same_symbol"] = reasons.get("same_symbol", 0) + 1
            continue
        shared_lines = int(duplicate.get("lines") or 0)
        groups.append(
            {
                "sites": {
                    (first["file"], first["symbol"]): first,
                    (second["file"], second["symbol"]): second,
                },
                "shared_lines_max": shared_lines,
                "raw_pairs_collapsed": 1,
            }
        )

    findings: list[dict[str, Any]] = []
    for index, group in enumerate(
        sorted(_union_groups(groups), key=lambda item: (-item["shared_lines_max"], sorted(item["sites"]))),
        start=1,
    ):
        sites = sorted(group["sites"].values(), key=lambda site: (site["file"], site["symbol"]))
        findings.append(
            {
                "finding_id": f"ts-jscpd-{index:04d}",
                "source": "jscpd-typescript",
                "shape_hint": "lexical_clone_cluster",
                "multiplicity": len(sites),
                "shared_lines_max": group["shared_lines_max"],
                "sites": sites,
                "raw_pairs_collapsed": group["raw_pairs_collapsed"],
                "consolidation_safety": "unknown_human_review_required",
            }
        )
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
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read jscpd report: {exc}", file=sys.stderr)
        return 2
    target, project_root = args.target.resolve(), args.project_root.resolve()
    if not target.is_dir() or not project_root.is_dir():
        print("error: --target and --project-root must be directories", file=sys.stderr)
        return 2
    findings, stats = collapse(jscpd=report, project_root=project_root, target=target)
    output = {
        "scan_meta": {
            "target": str(args.target),
            "project_root": str(args.project_root),
            "language": "typescript",
            "detector": "jscpd@4.0.5",
            "analysis": "lexical_or_near_lexical_only",
            "consolidation_safety": "unknown_human_review_required",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "jscpd_raw_pair_count": stats["raw_pair_count"],
            "jscpd_filtered_pair_count": stats["filtered_pair_count"],
            "jscpd_finding_count": stats["finding_count"],
            "jscpd_lexical_scan_degraded": False,
            "jscpd_lexical_scan_status": str((report.get("run") or {}).get("status") or "completed"),
            "ast_finding_count": 0,
            "ast_filtered_count": 0,
            "filter_reasons": stats["filter_reasons"],
        },
        "findings": findings,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"[collapse-typescript] raw={stats['raw_pair_count']} filtered={stats['filtered_pair_count']} findings={stats['finding_count']}",
        file=sys.stderr,
    )
    print(f"[collapse-typescript] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
