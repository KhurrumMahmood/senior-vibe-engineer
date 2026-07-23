#!/usr/bin/env python3
"""Write audit-decisions final artifacts from bounded Dart comment facts."""
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


REFERENCE = re.compile(r"\bdecision:(\d{4})\b")
ARTIFACTS = ("drift.md", "raw-drift.json", "registry-audit.json", "link-check.txt")


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


def _output(root: Path, requested: Path) -> Path:
    reports = root / "reports"
    report_root = reports / "audit-decisions"
    output = requested if requested.is_absolute() else root / requested
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(report_root)
    except ValueError as exc:
        raise ValueError("output must be a run directory below reports/audit-decisions") from exc
    if not relative.parts:
        raise ValueError("output must not be the audit report root")
    current = report_root
    for candidate in (reports, report_root):
        if candidate.is_symlink():
            raise ValueError("audit report ancestors must not be symlinks")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("audit output path must not resolve through a symlink")
    try:
        output.resolve().relative_to(report_root.resolve())
    except ValueError as exc:
        raise ValueError("unsafe audit output path") from exc
    return output


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


def _terminal(output: Path, facts: dict[str, Any]) -> None:
    raw = {
        "status": facts["status"],
        "failure_kind": facts["failure_kind"],
        "analysis": {"dart": facts},
        "references": [],
        "drift": [],
    }
    _atomic(output / "raw-drift.json", json.dumps(raw, indent=2, sort_keys=True) + "\n")
    _atomic(
        output / "registry-audit.json",
        json.dumps({"status": "not-run", "drift": []}, indent=2) + "\n",
    )
    _atomic(output / "link-check.txt", f"NOT RUN — {facts['failure_kind']}\n")
    _atomic(
        output / "drift.md",
        f"# Decision-registry drift\n\nStatus: `{facts['status']}`\n\n"
        f"Failure: `{facts['failure_kind']}`\n",
    )


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
    if facts["status"] != "complete":
        _terminal(output, facts)
        return code or 2

    audit = _module(Path(__file__).with_name("audit.py"), "audit_decisions_dart_base")
    try:
        decisions = audit.load_decisions(root / "ai-docs/decisions")
        known = {decision.id for decision in decisions}
        references = [
            {
                "path": file["file"],
                "line": comment["line"],
                "language": "dart",
                "comment_form": comment["form"],
                "id": match.group(1),
                "resolved": match.group(1) in known,
            }
            for file in facts["files"]
            for comment in file["comments"]
            for match in REFERENCE.finditer(comment["text"])
        ]
        references.sort(key=lambda row: (row["path"], row["line"], row["id"]))
        full_scope = Path(args.target).as_posix() in {".", ""}
        rows = audit.make_drift(
            decisions,
            root,
            references,
            full_reference_scope=full_scope,
        )
        registry = audit.registry_audit(decisions)
        link_drift, link_advisory = audit.link_check(decisions, root)
    except (OSError, TypeError, ValueError) as exc:
        failed = {**facts, "status": "failed", "failure_kind": "invalid_decision_registry"}
        failed["registry_error"] = str(exc)
        _terminal(output, failed)
        return 2

    output.mkdir(parents=True, exist_ok=True)
    raw = {
        "status": "complete",
        "failure_kind": "none",
        "scan_id": output.name,
        "analysis": {"dart": facts},
        "references": references,
        "registry_audit": {"drift": registry},
        "link_check": {"drift": link_drift, "advisory": link_advisory},
        "drift": rows,
    }
    _atomic(output / "raw-drift.json", json.dumps(raw, indent=2, sort_keys=True) + "\n")
    _atomic(
        output / "registry-audit.json",
        json.dumps({"count": len(decisions), "drift": registry}, indent=2, sort_keys=True)
        + "\n",
    )
    links = [*link_advisory, *link_drift] or [f"OK — {len(decisions)} decisions, all links resolve"]
    _atomic(output / "link-check.txt", "\n".join(links) + "\n")
    rendered = audit.render_drift(output.name, decisions, references, rows)
    _atomic(
        output / "drift.md",
        rendered + f"\nDart syntax status: `{facts['status']}` via `{facts['analyzer']}`.\n",
    )
    print(output / "drift.md")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
