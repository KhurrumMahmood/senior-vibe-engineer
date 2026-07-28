#!/usr/bin/env python3
"""Write Ruby direct-method branch leads and standard hotspot artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


THRESHOLD = 8
ARTIFACTS = ("detections.jsonl", "findings.json", "report.md")


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


def _producer() -> ModuleType | None:
    path = Path(__file__).resolve().parents[2] / "_ruby-syntax" / "ruby_syntax_facts.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("ruby_syntax_facts", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ruby_syntax_facts"] = module
    spec.loader.exec_module(module)
    return module


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    producer = _producer()
    if producer is None:
        return {
            "status": "partial",
            "failure_kind": "ruby_syntax_fact_producer_missing",
            "analyzer": "ruby-syntax-prism-v1",
            "files": [],
            "inventory": [],
            "ambiguities": [],
            "source_manifest": {"preserved": True},
        }, 2
    return producer.produce(
        args.project_root,
        args.target,
        ruby=args.ruby,
        bundler=args.bundler,
        test=args.test,
        smoke=args.smoke,
        allow_partial_syntax=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ruby", default="ruby")
    parser.add_argument("--bundler", default="bundle")
    parser.add_argument("--test")
    parser.add_argument("--smoke")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    facts, code = _facts(args)
    findings = []
    if facts["status"] == "complete" or (
        facts["status"] == "partial"
        and facts["failure_kind"] in {"ruby-project-incomplete", "bundle-check-failed"}
    ):
        findings = [
            {
                "pattern": "high-branch-method",
                "language": "ruby",
                "analyzer": facts["analyzer"],
                "file": file["file"],
                "function": function["name"],
                "owner": function["owner"],
                "lineno": function["line"],
                "end_lineno": function["end_line"],
                "loc": function["loc"],
                "branch_score": function["branch_score"],
                "summary": "direct Prism branch score; measure runtime cost before changing code",
            }
            for file in facts["files"]
            for function in file["functions"]
            if function["branch_score"] >= THRESHOLD
        ]
    findings.sort(key=lambda row: (-row["branch_score"], row["file"], row["lineno"]))
    status = facts["status"]
    verdict = (
        "scan-blocked"
        if status == "failed"
        else "safe-defer-incomplete"
        if status != "complete"
        else "measure-first"
        if findings
        else "no-hotspots"
    )
    payload = {
        "status": status,
        "failure_kind": facts["failure_kind"],
        "verdict": verdict,
        "analysis": {"ruby": facts},
        "summary": {"findings_total": len(findings), "high-branch-method": len(findings)},
        "findings": findings,
    }
    _atomic(output / "detections.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings))
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Complexity hotspot audit",
        "",
        f"Status: `{status}`",
        f"Verdict: `{verdict}`",
        f"Analyzer: `{facts['analyzer']}`",
        f"Findings: {len(findings)}",
        "",
    ]
    lines.extend(f"- `{row['file']}:{row['lineno']}` `{row['function']}` — branch score {row['branch_score']}" for row in findings)
    if status != "complete":
        lines.append(f"- Coverage incomplete: `{facts['failure_kind']}`")
    _atomic(output / "report.md", "\n".join(lines) + "\n")
    print(output / "report.md")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
