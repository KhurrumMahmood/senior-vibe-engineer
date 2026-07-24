#!/usr/bin/env python3
"""Render lexical Kotlin comment-drift leads from the copied Kotlin provider."""
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
    "lexical Kotlin comment tokens only; no comment-to-declaration association "
    "or semantic drift claim"
)
STALE_TERM_RE = re.compile(
    r"\b(?:SiteConfig|Site Configuration|site configuration|site config)\b"
)
DOC_REF_RE = re.compile(
    r"\b(?:L\d{2,}|line\s+\d{2,}|[A-Za-z0-9_./-]+\.kt:\d{1,5})\b",
    re.I,
)
SECTION_RE = re.compile(r"^(?:section\s+\d+.*|[A-Z][A-Z0-9 _/:-]{5,})$", re.I)
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
    spec = importlib.util.spec_from_file_location("kotlin_comment_facts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load copied Kotlin provider: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _provider() -> ModuleType | None:
    provider = next(
        (
            parent / "_kotlin/kotlin_facts.py"
            for parent in Path(__file__).resolve().parents
            if (parent / "_kotlin/kotlin_facts.py").is_file()
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
    lines = []
    for line in text.splitlines() or [text]:
        normalized = re.sub(r"^\s*\*?\s?", "", line).strip()
        if normalized:
            lines.append(normalized)
    return " ".join(lines)


def _patterns(summary: str) -> list[str]:
    found = []
    if STALE_TERM_RE.search(summary):
        found.append("stale_terminology")
    if DOC_REF_RE.search(summary):
        found.append("brittle_doc_reference")
    if SECTION_RE.fullmatch(summary):
        found.append("detached_section_banner")
    if NARRATION_RE.match(summary) and not WHY_RE.search(summary):
        found.append("narration_comment")
    return found


def _findings(facts: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for file in facts.get("files", []):
        for comment in file.get("comments", []):
            summary = _summary(comment["text"])
            for pattern in _patterns(summary):
                seed = (
                    f"{file['file']}\0{comment['line']}\0{pattern}\0{summary}".encode()
                )
                findings.append(
                    {
                        "finding_id": f"KOTLIN-COMMENT-{hashlib.sha256(seed).hexdigest()[:12].upper()}",
                        "pattern": pattern,
                        "language": "kotlin",
                        "file": file["file"],
                        "lineno": comment["line"],
                        "summary": summary,
                        "evidence": {
                            "comment_form": comment["form"],
                            "comment_span": comment["span"],
                            "source_sha256": file["source_sha256"],
                            "scope": "eligible-manifest-source-comment-token",
                        },
                        "claim_boundary": CLAIM_BOUNDARY,
                    }
                )
    return sorted(findings, key=lambda row: (row["file"], row["lineno"], row["pattern"]))


def _publish(output: Path, facts: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    rows = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    outcome = (
        "advisory-findings"
        if facts.get("status") == "complete" and findings
        else "clean-within-complete"
        if facts.get("status") == "complete"
        else "incomplete"
    )
    payload = {
        "schema_version": 1,
        "status": facts.get("status", "partial"),
        "failure_kind": facts.get("failure_kind", "kotlin_fact_producer_missing"),
        "outcome": outcome,
        "analysis": {"kotlin": facts},
        "findings": findings,
        "finding_count": len(findings),
        "detections_sha256": hashlib.sha256(rows.encode()).hexdigest(),
        "source_manifest_sha256": facts.get("source_manifest", {}).get(
            "after_sha256"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "limits": [
            "Only comment tokens from eligible lowercase .kt sources in the exact kotlin-project.json manifest are scanned.",
            "Quoted strings, tests, generated, vendor, build, tooling, unreadable, symlink, Java, and .kts inputs do not create findings.",
            "The rules are lexical stale-term, brittle-reference, section-banner, and narration leads; they do not associate a comment with a declaration or prove behavior drift.",
        ],
    }
    _atomic(output / "detections.jsonl", rows)
    _json(output / "scan.json", facts)
    _json(output / "findings.json", payload)
    report_lines = [
        "# Comment drift — Kotlin/JVM",
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
    report_lines.extend(["", "## Limits", "", *[f"- {item}" for item in payload["limits"]], ""])
    _atomic(output / "report.md", "\n".join(report_lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--kotlinc")
    parser.add_argument("--java")
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
            "status": "partial",
            "failure_kind": "kotlin_fact_producer_missing",
            "language": "kotlin",
            "inventory": [],
            "files": [],
            "source_manifest": {"preserved": True},
        }
        code = 2
    else:
        facts, code = provider.produce(
            root,
            args.target,
            kotlinc=args.kotlinc,
            java=args.java,
        )
    findings = _findings(facts) if facts.get("status") == "complete" else []
    _publish(output, facts, findings)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
