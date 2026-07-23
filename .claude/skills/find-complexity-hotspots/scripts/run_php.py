#!/usr/bin/env python3
"""Write PHP syntactic complexity leads and the standard hotspot artifacts."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
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


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    provider = Path(__file__).resolve().parents[2] / "_php-syntax/php_syntax_facts.php"
    if not provider.is_file():
        return {
            "status": "partial", "failure_kind": "php_syntax_provider_missing",
            "analyzer": "php-token-syntax-facts-v1", "files": [], "inventory": [],
            "source_manifest": {"preserved": True},
        }, 2
    runner = args.php_runner or shutil.which("php") or "php"
    command = [
        runner, str(provider), "--project-root", str(args.project_root), "--target", str(args.target),
        "--php", args.php, "--composer", args.composer,
        "--minimum-php", args.minimum_php, "--minimum-composer", args.minimum_composer,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return json.loads(result.stdout), result.returncode
    except (OSError, json.JSONDecodeError) as error:
        return {
            "status": "failed", "failure_kind": "php_syntax_provider_execution_failed",
            "analyzer": "php-token-syntax-facts-v1", "files": [], "inventory": [],
            "provider_error": str(error), "source_manifest": {"preserved": True},
        }, 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--php", default="php")
    parser.add_argument("--composer", default="composer")
    parser.add_argument("--php-runner")
    parser.add_argument("--minimum-php", default="8.1.0")
    parser.add_argument("--minimum-composer", default="2.2.0")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    latest = output.parent / "latest"
    latest.unlink(missing_ok=True)
    facts, code = _facts(args)
    findings = []
    if facts["status"] == "complete":
        findings = [
            {
                "pattern": "high-branch-function", "language": "php", "analyzer": facts["analyzer"],
                "file": file["file"], "function": function["qualified_name"],
                "lineno": function["line"], "end_lineno": function["end_line"],
                "loc": function["loc"], "branch_score": function["branch_score"],
                "branch_events": function["branch_events"],
                "summary": "syntactic branch score; measure runtime cost before changing code",
            }
            for file in facts["files"]
            for function in file["functions"]
            if function["branch_score"] >= THRESHOLD
        ]
    findings.sort(key=lambda row: (-row["branch_score"], row["file"], row["lineno"]))
    status = facts["status"]
    verdict = "scan-blocked" if status == "failed" else "safe-defer-incomplete" if status != "complete" else "measure-first" if findings else "no-hotspots"
    payload = {
        "status": status, "failure_kind": facts["failure_kind"], "verdict": verdict,
        "analysis": {"php": facts},
        "summary": {"findings_total": len(findings), "high-branch-function": len(findings)},
        "findings": findings,
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "detections.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings))
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Complexity hotspot audit", "", f"Status: `{status}`", f"Verdict: `{verdict}`",
        f"Analyzer: `{facts['analyzer']}`", f"Findings: {len(findings)}", "",
    ]
    lines.extend(
        f"- `{row['file']}:{row['lineno']}` `{row['function']}` — branch score {row['branch_score']}"
        for row in findings
    )
    if status != "complete":
        lines.append(f"- Analysis incomplete: `{facts['failure_kind']}`; no clean conclusion is available.")
    lines.append("- PHP branch tokens do not establish behavior, cost, types, or refactor authority.")
    _atomic(output / "report.md", "\n".join(lines) + "\n")
    if status == "complete":
        try:
            latest.symlink_to(output.name)
        except OSError:
            pass
    print(output / "report.md")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
