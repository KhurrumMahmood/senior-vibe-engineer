#!/usr/bin/env python3
"""Write the audit-decisions artifact contract from bounded Rust comments."""
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


def _producer() -> ModuleType | None:
    path = Path(__file__).resolve().parents[2] / "_rust-syntax/scripts/rust_syntax_facts.py"
    return _module(path, "rust_syntax_facts") if path.is_file() else None


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


def _write_terminal(output: Path, facts: dict[str, Any]) -> None:
    raw = {
        "status": facts["status"],
        "failure_kind": facts["failure_kind"],
        "analysis": {"rust": facts},
        "references": [],
        "drift": [],
    }
    _atomic(output / "raw-drift.json", json.dumps(raw, indent=2, sort_keys=True) + "\n")
    _atomic(output / "registry-audit.json", json.dumps({"status": "not-run", "drift": []}, indent=2) + "\n")
    _atomic(output / "link-check.txt", f"NOT RUN — {facts['failure_kind']}\n")
    _atomic(output / "drift.md", f"# Decision-registry drift\n\nStatus: `{facts['status']}`\n\nFailure: `{facts['failure_kind']}`\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cargo")
    parser.add_argument("--rustc")
    parser.add_argument("--rustfmt")
    parser.add_argument("--clippy")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    facts, code = _facts(args)
    if facts["status"] != "complete":
        _write_terminal(output, facts)
        return code

    audit = _module(Path(__file__).with_name("audit.py"), "audit_decisions_base")
    decisions = audit.load_decisions(root / "ai-docs/decisions")
    known = {decision.id for decision in decisions}
    references: list[dict[str, Any]] = []
    for file in facts["files"]:
        for comment in file["comments"]:
            for match in REFERENCE.finditer(comment["text"]):
                references.append({
                    "path": file["file"],
                    "line": comment["line"],
                    "language": "rust",
                    "comment_form": comment["form"],
                    "id": match.group(1),
                    "resolved": match.group(1) in known,
                })
    references.sort(key=lambda row: (row["path"], row["line"], row["id"]))
    full_scope = Path(args.target).as_posix() in {".", ""}
    rows = audit.make_drift(
        decisions, root, references, full_reference_scope=full_scope
    )
    registry = audit.registry_audit(decisions)
    link_drift, link_advisory = audit.link_check(decisions, root)
    output.mkdir(parents=True, exist_ok=True)
    raw = {
        "status": "complete",
        "failure_kind": "none",
        "scan_id": output.name,
        "analysis": {"rust": facts},
        "references": references,
        "registry_audit": {"drift": registry},
        "link_check": {"drift": link_drift, "advisory": link_advisory},
        "drift": rows,
    }
    _atomic(output / "raw-drift.json", json.dumps(raw, indent=2, sort_keys=True) + "\n")
    _atomic(output / "registry-audit.json", json.dumps({"count": len(decisions), "drift": registry}, indent=2, sort_keys=True) + "\n")
    links = [*link_advisory, *link_drift] or [f"OK — {len(decisions)} decisions, all links resolve"]
    _atomic(output / "link-check.txt", "\n".join(links) + "\n")
    rendered = audit.render_drift(output.name, decisions, references, rows)
    _atomic(output / "drift.md", rendered + f"\nRust syntax status: `{facts['status']}` via `{facts['analyzer']}`.\n")
    print(output / "drift.md")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
