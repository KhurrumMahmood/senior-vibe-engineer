#!/usr/bin/env python3
"""Write PHP direct-call/try standard coverage cells and final reports."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ARTIFACTS = ("coverage.json", "coverage.md")


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


def _standards(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    ideas = payload.get("ideas")
    if not isinstance(ideas, list):
        raise ValueError("standards JSON must contain an ideas array")
    for idea in ideas:
        if not isinstance(idea, dict) or not isinstance(idea.get("id"), str):
            raise ValueError("every standard must be an object with a string id")
        detector = idea.get("contract", {}).get("detector")
        if not isinstance(detector, dict) or not isinstance(detector.get("paths"), list):
            raise ValueError(f"{idea['id']}: detector must have a paths array")
        if detector.get("kind") == "ast":
            re.compile(detector.get("call_matches", ""))
    return ideas


def _publish(output: Path, facts: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    payload = {
        "status": facts["status"], "failure_kind": facts["failure_kind"],
        "analysis": {"php": facts}, "standards": rows,
        "limitation": (
            "Direct spelled PHP calls and lexical try-body condition only; no callee identity, "
            "aliases, receivers, exception flow, Composer, framework, or behavior semantics."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "coverage.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Standard coverage", "", f"Status: `{facts['status']}`", f"Analyzer: `{facts['analyzer']}`", "",
    ]
    lines.extend(
        f"- `{row['id']}` — `{row['status']}`; {row['situation_sites']} sites, "
        f"{row['gap_count']} gaps, {row['coverage_percent']}% coverage"
        for row in rows
    )
    _atomic(output / "coverage.md", "\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ideas", required=True, type=Path)
    parser.add_argument("--php", default="php")
    parser.add_argument("--composer", default="composer")
    parser.add_argument("--php-runner")
    parser.add_argument("--minimum-php", default="8.1.0")
    parser.add_argument("--minimum-composer", default="2.2.0")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    try:
        ideas = _standards(args.ideas)
    except (OSError, json.JSONDecodeError, ValueError, re.error) as error:
        facts = {
            "status": "failed", "failure_kind": "invalid_standards", "analyzer": "php-token-syntax-facts-v1",
            "standards_error": str(error), "files": [], "inventory": [], "source_manifest": {"preserved": True},
        }
        _publish(output, facts, [])
        return 2
    facts, code = _facts(args)
    fact_files = {row["file"]: row for row in facts.get("files", [])}
    rows: list[dict[str, Any]] = []
    for idea in ideas:
        detector = idea["contract"]["detector"]
        base = {"id": idea["id"], "label": idea.get("label", idea["id"])}
        if detector.get("kind") in {"manual", "skill"}:
            rows.append({**base, "status": "skipped", "situation_sites": 0, "gap_count": 0, "coverage_percent": None, "gaps": []})
            continue
        if detector.get("kind") != "ast" or detector.get("enclosed_by") != "try":
            rows.append({**base, "status": "language_unsupported", "situation_sites": 0, "gap_count": 0, "coverage_percent": None, "gaps": []})
            continue
        matched: set[str] = set()
        for pattern in detector["paths"]:
            matched.update(
                path.relative_to(root).as_posix()
                for path in root.glob(pattern)
                if path.is_file() and path.suffix.casefold() == ".php"
            )
        selected = [fact_files[path] for path in sorted(matched) if path in fact_files]
        if not selected:
            status = "no_files_matched" if facts["status"] == "complete" else facts["status"]
            rows.append({**base, "status": status, "situation_sites": 0, "gap_count": 0, "coverage_percent": None, "gaps": []})
            continue
        call_pattern = re.compile(detector["call_matches"])
        sites = [
            {"file": file["file"], **call}
            for file in selected for call in file["calls"]
            if call_pattern.fullmatch(call["spelling"])
        ]
        gaps = [site for site in sites if "try" not in site["enclosures"]]
        status = "scanned" if facts["status"] == "complete" else facts["status"]
        coverage = round(100 * (len(sites) - len(gaps)) / len(sites), 2) if sites else 100.0
        rows.append({
            **base, "status": status, "situation_sites": len(sites), "gap_count": len(gaps),
            "coverage_percent": coverage, "gaps": gaps,
        })
    _publish(output, facts, rows)
    if facts["status"] != "complete":
        return code or 2
    total_gaps = sum(row["gap_count"] for row in rows if row["status"] == "scanned")
    print(f"PHP syntax: scanned {sum(row['status'] == 'scanned' for row in rows)}/{len(rows)} standard(s): {total_gaps} coverage gap(s)")
    return 1 if total_gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
