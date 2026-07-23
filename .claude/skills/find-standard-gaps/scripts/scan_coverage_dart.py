#!/usr/bin/env python3
"""Write Dart direct-call/try standard coverage final artifacts."""
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


ARTIFACTS = ("coverage.json", "coverage.md", "scan.json")


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
    configured = reports / "standard-gaps"
    output = requested if requested.is_absolute() else root / requested
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(configured)
    except ValueError as exc:
        raise ValueError("output must be below reports/standard-gaps") from exc
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


def _standards(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    ideas = payload.get("ideas")
    if not isinstance(ideas, list):
        raise ValueError("standards JSON must contain an ideas array")
    for idea in ideas:
        if not isinstance(idea, dict) or not isinstance(idea.get("id"), str):
            raise ValueError("every standard must be an object with a string id")
        detector = idea.get("contract", {}).get("detector")
        if not isinstance(detector, dict):
            raise ValueError(f"{idea['id']}: detector must be an object")
        if not isinstance(detector.get("paths"), list):
            raise ValueError(f"{idea['id']}: detector paths must be an array")
        if detector.get("kind") == "ast":
            re.compile(detector.get("call_matches", ""))
    return ideas


def _publish(
    output: Path,
    facts: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    payload = {
        "status": facts["status"],
        "failure_kind": facts["failure_kind"],
        "analysis": {"dart": facts},
        "standards": rows,
        "limitation": (
            "Direct spelled Dart calls and one lexical try-body condition only; no callee "
            "identity, aliases, receivers, exception flow, framework, or Flutter semantics."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "coverage.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(output / "scan.json", json.dumps({"analysis": {"dart": facts}}, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Standard coverage",
        "",
        f"Status: `{facts['status']}`",
        f"Analyzer: `{facts['analyzer']}`",
        "",
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
    parser.add_argument("--target", default=Path("."), type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ideas", required=True, type=Path)
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
    try:
        ideas = _standards(args.ideas)
    except (OSError, json.JSONDecodeError, ValueError, re.error) as exc:
        failed = {
            "status": "failed",
            "failure_kind": "invalid_standards",
            "analyzer": "dart-syntax-facts-v1",
            "standards_error": str(exc),
            "inventory": [],
            "files": [],
            "source_manifest": {"preserved": True},
        }
        _publish(output, failed, [])
        return 2
    facts, code = _facts(args)
    fact_files = {row["file"]: row for row in facts.get("files", [])}
    rows: list[dict[str, Any]] = []
    for idea in ideas:
        detector = idea["contract"]["detector"]
        base = {"id": idea["id"], "label": idea.get("label", idea["id"])}
        if detector.get("kind") in {"manual", "skill"}:
            rows.append(
                {
                    **base,
                    "status": "skipped",
                    "situation_sites": 0,
                    "gap_count": 0,
                    "coverage_percent": None,
                    "gaps": [],
                }
            )
            continue
        if detector.get("kind") != "ast" or detector.get("enclosed_by") != "try":
            rows.append(
                {
                    **base,
                    "status": "language_unsupported",
                    "situation_sites": 0,
                    "gap_count": 0,
                    "coverage_percent": None,
                    "gaps": [],
                }
            )
            continue
        matched: set[str] = set()
        for pattern in detector["paths"]:
            matched.update(
                path.relative_to(root).as_posix()
                for path in root.glob(pattern)
                if path.is_file() and path.suffix.casefold() == ".dart"
            )
        selected = [fact_files[path] for path in sorted(matched) if path in fact_files]
        if not selected:
            rows.append(
                {
                    **base,
                    "status": "no_files_matched",
                    "situation_sites": 0,
                    "gap_count": 0,
                    "coverage_percent": None,
                    "gaps": [],
                }
            )
            continue
        call_pattern = re.compile(detector["call_matches"])
        sites = [
            {"file": file["file"], **call}
            for file in selected
            for call in file["calls"]
            if call_pattern.fullmatch(call["spelling"])
        ]
        gaps = [site for site in sites if not site["in_try"]]
        status = "scanned" if facts["status"] == "complete" else facts["status"]
        coverage = round(100 * (len(sites) - len(gaps)) / len(sites), 2) if sites else 100.0
        rows.append(
            {
                **base,
                "status": status,
                "situation_sites": len(sites),
                "gap_count": len(gaps),
                "coverage_percent": coverage,
                "gaps": gaps,
            }
        )
    _publish(output, facts, rows)
    if facts["status"] != "complete":
        return code or 2
    total_gaps = sum(row["gap_count"] for row in rows if row["status"] == "scanned")
    print(
        f"Dart syntax: scanned {sum(row['status'] == 'scanned' for row in rows)}/"
        f"{len(rows)} standard(s): {total_gaps} coverage gap(s)"
    )
    return 1 if total_gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
