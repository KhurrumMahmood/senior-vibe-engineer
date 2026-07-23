#!/usr/bin/env python3
"""Write Dart's bounded adjacent-doc/fixed-return comment-drift artifacts."""
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
CLAIM = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age)?|rate)\b", re.I)


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _provider() -> ModuleType | None:
    path = Path(__file__).resolve().parents[2] / "_dart/scripts/dart_syntax_facts.py"
    return _module(path, "dart_syntax_facts") if path.is_file() else None


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    provider = _provider()
    if provider is None:
        return {
            "status": "partial",
            "failure_kind": "dart_fact_producer_missing",
            "analyzer": "dart-syntax-facts-v1",
            "inventory": [],
            "files": [],
            "source_manifest": {"preserved": True},
        }, 2
    return provider.produce(
        args.project_root,
        args.target,
        dart=args.dart,
        pub_cache=args.pub_cache,
        native_test=args.native_test,
        smoke=args.smoke,
        smoke_stdout=args.smoke_stdout,
        tool_root=args.tool_root,
    )


def _output(root: Path, requested: Path) -> Path:
    reports = root / "reports"
    configured = reports / "find-comment-drift"
    output = requested if requested.is_absolute() else root / requested
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(configured)
    except ValueError as exc:
        raise ValueError("output must be below reports/find-comment-drift") from exc
    if not relative.parts:
        raise ValueError("output must be a run directory")
    current = configured
    for candidate in (reports, configured):
        if candidate.is_symlink():
            raise ValueError("report ancestors must not be symlinks")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output must not resolve through a symlink")
    try:
        output.resolve().relative_to(configured.resolve())
    except ValueError as exc:
        raise ValueError("unsafe report output path") from exc
    return output


def _publish(output: Path, facts: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    lines = [json.dumps(row, sort_keys=True) for row in findings]
    jsonl = "\n".join(lines) + ("\n" if lines else "")
    detections_hash = hashlib.sha256(jsonl.encode()).hexdigest()
    outcome = (
        "advisory-findings"
        if facts["status"] == "complete" and findings
        else "clean-within-complete"
        if facts["status"] == "complete"
        else "incomplete"
    )
    payload = {
        "status": facts["status"],
        "failure_kind": facts["failure_kind"],
        "outcome": outcome,
        "analysis": {"dart": facts},
        "findings": findings,
        "finding_count": len(findings),
        "detections_sha256": detections_hash,
        "limitation": (
            "One adjacent Dart /// numeric percentage/rate claim versus a direct fixed "
            "numeric return; no flow, inherited docs, macros, generated code, runtime, "
            "framework, or Flutter claim."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "detections.jsonl", jsonl)
    _atomic(output / "scan.json", json.dumps({"analysis": {"dart": facts}}, indent=2, sort_keys=True) + "\n")
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    report = [
        "# Dart comment drift",
        "",
        f"Status: `{facts['status']}`",
        f"Outcome: `{outcome}`",
        f"Findings: {len(findings)}",
        "",
    ]
    report.extend(
        f"- `{row['file']}:{row['lineno']}` `{row['function']}` claims "
        f"{row['claimed_value']} but directly returns {row['returned_literal']}"
        for row in findings
    )
    _atomic(output / "report.md", "\n".join(report) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", default=Path("."), type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dart")
    parser.add_argument("--pub-cache", type=Path)
    parser.add_argument("--native-test", type=Path)
    parser.add_argument("--smoke", type=Path)
    parser.add_argument("--smoke-stdout")
    parser.add_argument("--tool-root", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    try:
        output = _output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    facts, code = _facts(args)
    findings: list[dict[str, Any]] = []
    if facts["status"] == "complete":
        for file in facts["files"]:
            for function in file["functions"]:
                match = CLAIM.search(function["comment"])
                if match is None:
                    continue
                claimed = float(match.group(1))
                returned = float(function["fixed_return"])
                if claimed == returned:
                    continue
                finding = {
                    "pattern": "behavior_drift_comment",
                    "language": "dart",
                    "file": file["file"],
                    "lineno": function["comment_line"],
                    "function": function["name"],
                    "summary": function["comment"].removeprefix("///").strip(),
                    "claimed_value": claimed,
                    "returned_literal": function["fixed_return"],
                    "evidence": {
                        "comment_form": "doc",
                        "claim_kind": "fixed-numeric-percentage-or-rate",
                        "code_fact": "direct-fixed-numeric-return",
                        "comment_span": {
                            "start": function["comment_offset"],
                            "end": function["comment_end"],
                        },
                        "function_span": {
                            "start": function["offset"],
                            "end": function["end"],
                        },
                        "source_sha256": file["source_sha256"],
                        "analyzer": facts["analyzer"],
                    },
                }
                finding["finding_sha256"] = hashlib.sha256(
                    json.dumps(finding, sort_keys=True).encode()
                ).hexdigest()
                findings.append(finding)
    _publish(output, facts, findings)
    if facts["status"] != "complete":
        return code or 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
