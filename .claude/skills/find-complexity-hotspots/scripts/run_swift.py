#!/usr/bin/env python3
"""Write bounded Swift direct-body branch leads and final hotspot artifacts."""

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


PRODUCER = Path(__file__).resolve().parents[2] / "_swift-project-lexical" / "swift_project_facts.py"
BRANCH_THRESHOLD = 8
ARTIFACTS = ("detections.jsonl", "findings.json", "report.md", "scan.json")


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
    spec = importlib.util.spec_from_file_location("swift_project_facts_a2_complexity", PRODUCER)
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
        [args.target],
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
    if output == root:
        raise ValueError("output must not replace the project root")
    return output


def _tool_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--swift", type=Path, default=Path("swift"))
    parser.add_argument("--swiftc", type=Path, default=Path("swiftc"))
    parser.add_argument("--swift-format", type=Path, default=Path("swift-format"))
    parser.add_argument("--check-product")
    parser.add_argument("--expected-check", default="")
    parser.add_argument("--smoke-product")
    parser.add_argument("--expected-smoke", default="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--no-host-write",
        action="store_true",
        help="Require output-dir outside project-root for read-only dogfood",
    )
    _tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    args.project_root = root
    try:
        output = _output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    if args.no_host_write:
        try:
            output.relative_to(root)
        except ValueError:
            pass
        else:
            parser.error("--no-host-write requires output-dir outside project-root")
    latest = output.parent / "latest"
    latest.unlink(missing_ok=True)
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)

    facts, producer, code = _facts(args)
    findings: list[dict[str, Any]] = []
    compiler_validated = any(
        row.get("id") == "compiler-parse" and row.get("returncode") == 0
        for row in facts.get("native_checks", [])
    )
    if producer is not None and facts["status"] != "failed":
        for row in facts["inventory"]:
            if row["role"] not in {"eligible", "candidate"} or "_mask" not in row:
                continue
            for function in producer.function_syntax_facts(row):
                if function["branch_score"] < BRANCH_THRESHOLD:
                    continue
                findings.append(
                    {
                        "pattern": "high-branch-function",
                        "language": "swift",
                        "analyzer": facts["analyzer"],
                        "file": row["file"],
                        "function": function["symbol"],
                        "kind": function["kind"],
                        "lineno": function["span"]["start"]["line"],
                        "end_lineno": function["span"]["end"]["line"],
                        "loc": function["line_count"],
                        "branch_score": function["branch_score"],
                        "threshold": BRANCH_THRESHOLD,
                        "declaration_span": function["span"],
                        "body_span": function["body_span"],
                        "source_sha256": function["source_sha256"],
                        "spelling_sha256": function["spelling_sha256"],
                        "branch_events": function["branch_events"],
                        "runtime_cost_claimed": False,
                        "refactor_authority": False,
                        "evidence_level": (
                            "compiler-validated-lexical"
                            if compiler_validated
                            else "hash-bound-lexical"
                        ),
                        "summary": (
                            "direct-body syntax score only; project-native validation is "
                            f"{'complete' if compiler_validated else 'incomplete'}, nested callable "
                            "bodies are excluded, and runtime cost remains unmeasured"
                        ),
                    }
                )
    findings.sort(key=lambda row: (-row["branch_score"], row["file"], row["lineno"]))
    status = facts["status"]
    outcome = (
        "measure-first"
        if status == "complete" and findings
        else "no-hotspots"
        if status == "complete"
        else "safe-defer-incomplete"
        if status == "partial"
        else "scan-blocked"
    )
    payload = {
        "schema_version": 1,
        "skill": "find-complexity-hotspots",
        "language": "swift",
        "target": args.target,
        "status": status,
        "failure_kind": facts["failure_kind"],
        "outcome": outcome,
        "threshold": BRANCH_THRESHOLD,
        "analysis": {"swift": _public(facts, producer)},
        "summary": {
            "findings_total": len(findings),
            "high-branch-function": len(findings),
        },
        "findings": findings,
        "limitation": (
            f"{'Compiler-validated' if compiler_validated else 'Hash-bound'} lexical branch "
            "tokens only; no resolved symbols, control-flow "
            "equivalence, runtime frequency/cost, framework/Xcode truth, or refactor authority."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    _atomic(output / "detections.jsonl", jsonl)
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(
        output / "scan.json",
        json.dumps({"analysis": payload["analysis"]}, indent=2, sort_keys=True) + "\n",
    )
    lines = [
        "# Swift complexity hotspot audit",
        "",
        f"Status: `{status}`",
        f"Outcome: `{outcome}`",
        f"Frozen branch threshold: {BRANCH_THRESHOLD}",
        f"Findings: {len(findings)}",
        "",
    ]
    lines.extend(
        f"- `{row['file']}:{row['lineno']}` `{row['function']}` — direct branch score "
        f"{row['branch_score']}"
        for row in findings
    )
    if status != "complete":
        lines.append("- Incomplete evidence; no clean conclusion is available.")
    _atomic(output / "report.md", "\n".join(lines) + "\n")
    if status in {"complete", "partial"}:
        try:
            latest.symlink_to(output.name)
        except OSError:
            pass
    print(output / "report.md")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
