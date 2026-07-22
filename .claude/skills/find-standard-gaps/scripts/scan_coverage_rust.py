#!/usr/bin/env python3
"""Write Rust direct-call/match standard coverage cells and final reports."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType
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


def _producer() -> ModuleType | None:
    path = Path(__file__).resolve().parents[2] / "_rust-syntax/scripts/rust_syntax_facts.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("rust_syntax_facts", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rust_syntax_facts"] = module
    spec.loader.exec_module(module)
    return module


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    producer = _producer()
    if producer is None:
        return {
            "status": "partial", "failure_kind": "rust_fact_producer_missing",
            "analyzer": "rust-syntax-facts-v1", "files": [], "inventory": [],
            "ambiguities": [], "native": {}, "source_manifest": {"preserved": True},
        }, 0
    return producer.produce(
        args.project_root, args.target,
        cargo=args.cargo, rustc=args.rustc, rustfmt=args.rustfmt, clippy=args.clippy,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ideas", required=True, type=Path)
    parser.add_argument("--cargo")
    parser.add_argument("--rustc")
    parser.add_argument("--rustfmt")
    parser.add_argument("--clippy")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    try:
        ideas = json.loads(args.ideas.read_text(encoding="utf-8"))["ideas"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"invalid standards file: {exc}")
        return 2
    facts, code = _facts(args)
    fact_files = {row["file"]: row for row in facts.get("files", [])}
    results: list[dict[str, Any]] = []
    for idea in ideas:
        detector = idea.get("contract", {}).get("detector", {})
        base = {"id": idea.get("id"), "label": idea.get("label", idea.get("id"))}
        if detector.get("kind") in {"manual", "skill"}:
            results.append({**base, "status": "skipped", "situation_sites": 0, "gap_count": 0, "coverage_percent": None, "gaps": []})
            continue
        if detector.get("kind") != "ast" or detector.get("enclosed_by") != "match":
            results.append({**base, "status": "language_unsupported", "situation_sites": 0, "gap_count": 0, "coverage_percent": None, "gaps": []})
            continue
        matched: set[str] = set()
        for pattern in detector.get("paths", []):
            matched.update(
                path.relative_to(root).as_posix()
                for path in root.glob(pattern)
                if path.is_file() and path.suffix == ".rs"
            )
        selected = [fact_files[path] for path in sorted(matched) if path in fact_files]
        if not selected:
            results.append({**base, "status": "no_files_matched", "situation_sites": 0, "gap_count": 0, "coverage_percent": None, "gaps": []})
            continue
        try:
            call_pattern = re.compile(detector["call_matches"])
        except (KeyError, re.error):
            results.append({**base, "status": "error", "situation_sites": 0, "gap_count": 0, "coverage_percent": None, "gaps": []})
            continue
        sites = [
            {"file": file["file"], **call}
            for file in selected
            for call in file["calls"]
            if call_pattern.fullmatch(call["spelling"])
        ]
        gaps = [site for site in sites if "match" not in site["enclosures"]]
        status = "scanned" if facts["status"] == "complete" else facts["status"]
        coverage = round(100 * (len(sites) - len(gaps)) / len(sites), 2) if sites else 100.0
        results.append({
            **base, "status": status, "situation_sites": len(sites),
            "gap_count": len(gaps), "coverage_percent": coverage, "gaps": gaps,
        })
    payload = {
        "status": facts["status"],
        "failure_kind": facts["failure_kind"],
        "analysis": {"rust": facts},
        "standards": results,
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "coverage.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = ["# Standard coverage", "", f"Status: `{facts['status']}`", f"Analyzer: `{facts['analyzer']}`", ""]
    for row in results:
        lines.append(
            f"- `{row['id']}` — `{row['status']}`; {row['situation_sites']} sites, "
            f"{row['gap_count']} gaps, {row['coverage_percent']}% coverage"
        )
    _atomic(output / "coverage.md", "\n".join(lines) + "\n")
    total_gaps = sum(row["gap_count"] for row in results if row["status"] == "scanned")
    print(
        f"Rust syntax: scanned {sum(row['status'] == 'scanned' for row in results)}/{len(results)} "
        f"standard(s): {total_gaps} coverage gap(s)"
    )
    if code:
        return code
    return 1 if facts["status"] == "complete" and total_gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
