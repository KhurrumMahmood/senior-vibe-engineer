#!/usr/bin/env python3
"""Render bounded C# lexical comment-drift leads from Roslyn syntax facts."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


ARTIFACTS = ("detections.jsonl", "scan.json", "findings.json", "report.md")
CLAIM_BOUNDARY = (
    "lexical C# Roslyn comment trivia only; no comment-to-declaration "
    "association, semantic drift, control-flow, or runtime claim"
)
STALE_TERM_RE = re.compile(
    r"\b(?:SiteConfig|Site Configuration|site configuration|site config)\b"
)
DOC_REF_RE = re.compile(
    r"\b(?:L\d{2,}|line\s+\d{2,}|[A-Za-z0-9_./-]+\.cs:\d{1,5})\b",
    re.I,
)
SECTION_NUMBER_RE = re.compile(r"^section\s+\d+.*$", re.I)
UPPER_BANNER_RE = re.compile(r"^[A-Z][A-Z0-9 _/:-]{5,}$")
NARRATION_RE = re.compile(
    r"^(?:get|create|update|delete|remove|save|return|format|parse|load|build|"
    r"render|initialize|validate|check|set|clear|find|filter|sort|count|"
    r"calculate|fetch|call|loop|append|add|show|store|reset|replace|compute)\b",
    re.I,
)
WHY_RE = re.compile(
    r"\b(?:why|because|compat|legacy|intentional|avoid|must|cannot|workaround|"
    r"race|safety|security|contract|temporary|until|fallback|preserve|exclude|"
    r"since|if|when|while|after|before|for|via|with|without|only|needed)\b",
    re.I,
)
PATTERN_CONTRACTS = {
    "stale_terminology": (
        "matches a frozen legacy term spelling; it does not prove that the term "
        "or the comment is obsolete"
    ),
    "brittle_doc_reference": (
        "matches a source-line-shaped reference; it does not resolve the path, "
        "line, or referenced declaration"
    ),
    "detached_section_banner": (
        "matches section-number or uppercase-banner lexical form; it does not "
        "prove that the comment is detached or unnecessary"
    ),
    "narration_comment": (
        "matches an imperative action verb without a frozen rationale lexeme; "
        "it is a style lead, not proof that the comment merely narrates code"
    ),
}


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _json(path: Path, payload: Any) -> None:
    _atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("csharp_comment_facts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load copied C# provider: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _provider() -> ModuleType | None:
    provider = next(
        (
            parent / "_csharp/csharp_facts.py"
            for parent in Path(__file__).resolve().parents
            if (parent / "_csharp/csharp_facts.py").is_file()
        ),
        None,
    )
    return _load(provider) if provider is not None else None


def _safe_output(root: Path, supplied: Path) -> Path:
    allowed = root / "reports/find-comment-drift"
    output = Path(os.path.abspath(supplied if supplied.is_absolute() else root / supplied))
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must stay beneath reports/find-comment-drift") from exc
    if not relative.parts:
        raise ValueError("output must name a run directory")
    current = allowed
    for candidate in (root / "reports", allowed):
        if candidate.is_symlink():
            raise ValueError("report ancestors cannot be symbolic links")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output cannot traverse a symbolic link")
    return output


def _summary(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines() or [text]:
        normalized = line.strip()
        normalized = re.sub(r"^(?:///|//|/\*\*?|\*)\s?", "", normalized)
        normalized = re.sub(r"\s*\*/$", "", normalized).strip()
        if normalized:
            lines.append(normalized)
    return " ".join(lines)


def _patterns(summary: str) -> list[str]:
    found: list[str] = []
    if STALE_TERM_RE.search(summary):
        found.append("stale_terminology")
    if DOC_REF_RE.search(summary):
        found.append("brittle_doc_reference")
    if SECTION_NUMBER_RE.fullmatch(summary) or UPPER_BANNER_RE.fullmatch(summary):
        found.append("detached_section_banner")
    if NARRATION_RE.match(summary) and not WHY_RE.search(summary):
        found.append("narration_comment")
    return found


def _roslyn_spelling(source: str, span: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    start = span["start_byte"]
    end = span["end_byte"]
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start <= end:
        raise ValueError("Roslyn comment span is malformed")
    encoded = source.encode("utf-16-le")
    if end * 2 > len(encoded):
        raise ValueError("Roslyn comment span exceeds its source")
    try:
        prefix = encoded[: start * 2].decode("utf-16-le")
        through = encoded[: end * 2].decode("utf-16-le")
    except UnicodeDecodeError as exc:
        raise ValueError("Roslyn comment span splits a UTF-16 scalar") from exc
    spelling = source[len(prefix) : len(through)]
    return spelling, {
        "start": start,
        "end": end,
        "unit": "utf16-code-unit",
        "interval": "half-open",
    }


def _findings(root: Path, facts: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for file in facts.get("files", []):
        # File.ReadAllText strips an optional UTF-8 BOM before Roslyn assigns
        # TextSpan offsets; mirror that exact source string here.
        source = (root / file["file"]).read_bytes().decode("utf-8-sig")
        for comment in file.get("comments", []):
            summary = _summary(comment["text"])
            spelling, roslyn_span = _roslyn_spelling(source, comment["span"])
            for pattern in _patterns(summary):
                seed = (
                    f"{file['file']}\0{roslyn_span['start']}\0{pattern}\0{summary}".encode()
                )
                findings.append({
                    "finding_id": (
                        f"CSHARP-COMMENT-{hashlib.sha256(seed).hexdigest()[:12].upper()}"
                    ),
                    "pattern": pattern,
                    "pattern_claim": PATTERN_CONTRACTS[pattern],
                    "language": "csharp",
                    "file": file["file"],
                    "lineno": comment["line"],
                    "summary": summary,
                    "evidence": {
                        "comment_form": comment["form"],
                        "roslyn_comment_span": roslyn_span,
                        "comment_spelling_sha256": hashlib.sha256(
                            spelling.encode("utf-8")
                        ).hexdigest(),
                        "source_sha256": file["source_sha256"],
                        "scope": "eligible-manifest-source-roslyn-comment-trivia",
                    },
                    "claim_boundary": CLAIM_BOUNDARY,
                })
    return sorted(
        findings,
        key=lambda row: (
            row["file"], row["evidence"]["roslyn_comment_span"]["start"], row["pattern"]
        ),
    )


def _publish(output: Path, facts: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    rows = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    outcome = (
        "advisory-findings"
        if facts.get("status") == "complete" and findings
        else "clean-within-complete"
        if facts.get("status") == "complete"
        else "incomplete"
    )
    limits = [
        "Only Roslyn comment trivia from eligible lowercase .cs sources in the exact csharp-project.json manifest are scanned.",
        "Quoted, interpolated, verbatim, and raw strings; directives and disabled text; tests; generated, vendor, build, tooling, unreadable, and symlink inputs do not create findings.",
        "The four patterns are frozen lexical review leads. They do not attach comments to declarations or prove prose staleness, code behavior, runtime reachability, documentation completeness, or refactor safety.",
        "Roslyn TextSpan offsets are reported as zero-based UTF-16 code units in a half-open interval, not byte offsets.",
    ]
    payload = {
        "schema_version": 1,
        "status": facts.get("status", "failed"),
        "failure_kind": facts.get("failure_kind", "csharp_fact_producer_missing"),
        "outcome": outcome,
        "analysis": {"csharp": facts},
        "findings": findings,
        "finding_count": len(findings),
        "detections_sha256": hashlib.sha256(rows.encode()).hexdigest(),
        "source_manifest_sha256": facts.get("source_manifest", {}).get("after_sha256"),
        "claim_boundary": CLAIM_BOUNDARY,
        "pattern_contracts": PATTERN_CONTRACTS,
        "limits": limits,
    }
    _atomic(output / "detections.jsonl", rows)
    _json(output / "scan.json", facts)
    _json(output / "findings.json", payload)
    report_lines = [
        "# Comment drift — C# 14 / .NET 10",
        "",
        f"Status: **{payload['status']}**",
        f"Outcome: **{outcome}**",
        f"Findings: **{len(findings)}**",
        "",
        f"> {CLAIM_BOUNDARY}.",
        "",
        "## Findings",
        "",
    ]
    report_lines.extend(
        f"- `{row['file']}:{row['lineno']}` — `{row['pattern']}` — {row['summary']}"
        for row in findings
    )
    if not findings:
        report_lines.append(
            "No lexical findings in the complete selected snapshot."
            if facts.get("status") == "complete"
            else "Analysis is incomplete; no clean claim is available."
        )
    report_lines.extend([
        "", "## Pattern contracts", "",
        *[f"- `{name}`: {claim}." for name, claim in PATTERN_CONTRACTS.items()],
        "", "## Limits", "", *[f"- {item}" for item in limits], "",
    ])
    _atomic(output / "report.md", "\n".join(report_lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dotnet")
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        output = _safe_output(root, args.output_dir)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    output.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    provider = _provider()
    if provider is None:
        facts = {
            "status": "failed",
            "failure_kind": "csharp_fact_producer_missing",
            "language": "csharp",
            "inventory": [],
            "files": [],
            "source_manifest": {"preserved": True},
        }
        code = 2
    else:
        facts, code = provider.produce(root, args.target, dotnet=args.dotnet)
    findings: list[dict[str, Any]] = []
    if facts.get("status") == "complete":
        try:
            findings = _findings(root, facts)
        except (OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
            facts.update(
                status="failed",
                failure_kind="csharp_comment_evidence_invalid",
                detail=str(exc),
                files=[],
            )
            code = 2
    _publish(output, facts, findings)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
