#!/usr/bin/env python3
"""Write Swift direct-call/do-catch standard coverage final artifacts."""

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


PRODUCER = Path(__file__).resolve().parents[2] / "_swift-project-lexical" / "swift_project_facts.py"
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


def _producer() -> ModuleType | None:
    if not PRODUCER.is_file():
        return None
    spec = importlib.util.spec_from_file_location("swift_project_facts_a2_standards", PRODUCER)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fallback() -> dict[str, Any]:
    return {
        "language": "swift",
        "analyzer": "swift-project-lexical-facts-v1",
        "status": "partial",
        "failure_kind": "swift-fact-producer-missing",
        "inventory": [],
        "errors": [],
        "source_manifest": [],
        "source_manifest_sha256": None,
        "source_preserved": True,
        "host_state_preserved": True,
        "native_checks": [],
        "limits": ["Swift fact producer unavailable; no clean conclusion is possible."],
    }


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], ModuleType | None, int]:
    producer = _producer()
    if producer is None:
        return _fallback(), None, 2
    facts = producer.collect_snapshot(
        args.project_root,
        [str(args.target)],
        swift=args.swift,
        swiftc=args.swiftc,
        swift_format=args.swift_format,
        check_product=args.check_product,
        expected_check=args.expected_check,
        smoke_product=args.smoke_product,
        expected_smoke=args.expected_smoke,
    )
    facts.setdefault("failure_kind", "none")
    return facts, producer, producer.terminal_return_code(facts)


def _public(facts: dict[str, Any], producer: ModuleType | None) -> dict[str, Any]:
    return producer.public_snapshot(facts) if producer is not None else facts


def _output(root: Path, requested: Path) -> Path:
    output = Path(os.path.abspath(requested if requested.is_absolute() else root / requested))
    try:
        relative = output.relative_to(root)
    except ValueError as exc:
        raise ValueError("output must remain inside the project") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output must not cross a symlink")
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
    producer: ModuleType | None,
    rows: list[dict[str, Any]],
) -> None:
    payload = {
        "status": facts["status"],
        "failure_kind": facts["failure_kind"],
        "analysis": {"swift": _public(facts, producer)},
        "standards": rows,
        "limitation": (
            "Direct spelled Swift calls and one lexical do-catch condition only; no callee "
            "identity, aliases, receivers, throw flow, target semantics, framework, or Xcode truth."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "coverage.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(
        output / "scan.json",
        json.dumps({"analysis": payload["analysis"]}, indent=2, sort_keys=True) + "\n",
    )
    lines = [
        "# Swift standard coverage",
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


def _tool_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--swift", type=Path, default=Path("swift"))
    parser.add_argument("--swiftc", type=Path, default=Path("swiftc"))
    parser.add_argument("--swift-format", type=Path, default=Path("swift-format"))
    parser.add_argument("--check-product", required=True)
    parser.add_argument("--expected-check", required=True)
    parser.add_argument("--smoke-product", required=True)
    parser.add_argument("--expected-smoke", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", default=Path("."), type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ideas", required=True, type=Path)
    _tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    args.project_root = root
    try:
        output = _output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)

    try:
        ideas = _standards(args.ideas)
    except (OSError, json.JSONDecodeError, ValueError, re.error) as exc:
        failed = _fallback()
        failed.update(
            status="failed",
            failure_kind="invalid-standards",
            standards_error=str(exc),
        )
        _publish(output, failed, None, [])
        return 1

    facts, producer, code = _facts(args)
    fact_files = {
        row["file"]: row for row in facts.get("inventory", []) if row["role"] == "eligible"
    }
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
                    "sites": [],
                    "gaps": [],
                }
            )
            continue
        if detector.get("kind") != "ast" or detector.get("enclosed_by") != "do-catch":
            rows.append(
                {
                    **base,
                    "status": "language_unsupported",
                    "situation_sites": 0,
                    "gap_count": 0,
                    "coverage_percent": None,
                    "sites": [],
                    "gaps": [],
                }
            )
            continue
        if facts["status"] != "complete" or producer is None:
            rows.append(
                {
                    **base,
                    "status": facts["status"],
                    "situation_sites": 0,
                    "gap_count": 0,
                    "coverage_percent": None,
                    "sites": [],
                    "gaps": [],
                }
            )
            continue
        matched: set[str] = set()
        for pattern in detector["paths"]:
            matched.update(
                path.relative_to(root).as_posix()
                for path in root.glob(pattern)
                if path.is_file() and path.suffix.casefold() == ".swift"
            )
        selected = [fact_files[file] for file in sorted(matched) if file in fact_files]
        if not selected:
            rows.append(
                {
                    **base,
                    "status": "no_files_matched",
                    "situation_sites": 0,
                    "gap_count": 0,
                    "coverage_percent": None,
                    "sites": [],
                    "gaps": [],
                }
            )
            continue
        call_pattern = re.compile(detector["call_matches"])
        sites = [
            call
            for file in selected
            for function in producer.function_syntax_facts(file)
            for call in function["calls"]
            if call_pattern.fullmatch(call["spelling"])
        ]
        sites.sort(key=lambda row: (row["file"], row["line"], row["function"]))
        gaps = [site for site in sites if not site["in_do_catch"]]
        coverage = round(100 * (len(sites) - len(gaps)) / len(sites), 2) if sites else 100.0
        rows.append(
            {
                **base,
                "status": "scanned",
                "situation_sites": len(sites),
                "gap_count": len(gaps),
                "coverage_percent": coverage,
                "sites": sites,
                "gaps": gaps,
            }
        )
    _publish(output, facts, producer, rows)
    if facts["status"] != "complete":
        return code
    total_gaps = sum(row["gap_count"] for row in rows if row["status"] == "scanned")
    print(
        f"Swift syntax: scanned {sum(row['status'] == 'scanned' for row in rows)}/"
        f"{len(rows)} standard(s): {total_gaps} coverage gap(s)"
    )
    return 1 if total_gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
