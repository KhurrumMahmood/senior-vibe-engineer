#!/usr/bin/env python3
"""Write audit-decisions artifacts from bounded compiler-validated Swift comments."""

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
    return _module(PRODUCER, "swift_project_facts_a2_audit") if PRODUCER.is_file() else None


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


def _terminal(output: Path, facts: dict[str, Any], producer: ModuleType | None) -> None:
    public = _public(facts, producer)
    raw = {
        "status": facts["status"],
        "failure_kind": facts["failure_kind"],
        "analysis": {"swift": public},
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
        "# Decision-registry drift\n\n"
        f"Status: `{facts['status']}`\n\nFailure: `{facts['failure_kind']}`\n",
    )


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

    facts, producer, code = _facts(args)
    if facts["status"] != "complete":
        _terminal(output, facts, producer)
        return code

    audit = _module(Path(__file__).with_name("audit.py"), "audit_decisions_swift_base")
    try:
        decisions = audit.load_decisions(root / "ai-docs/decisions")
        known = {decision.id for decision in decisions}
        form = {
            "line": "line",
            "block": "block",
            "doc-line": "doc",
            "doc-block": "doc",
        }
        references = [
            {
                "path": row["file"],
                "line": comment["span"]["start"]["line"],
                "language": "swift",
                "comment_form": form[comment["kind"]],
                "id": match.group(1),
                "resolved": match.group(1) in known,
                "source_sha256": row["source_sha256"],
                "spelling_sha256": comment["spelling_sha256"],
            }
            for row in facts["inventory"]
            if row["role"] == "eligible"
            for comment in row["comments"]
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
        facts.update(
            status="failed",
            failure_kind="invalid-decision-registry",
            registry_error=str(exc),
        )
        _terminal(output, facts, producer)
        return 1

    output.mkdir(parents=True, exist_ok=True)
    raw = {
        "status": "complete",
        "failure_kind": "none",
        "scan_id": output.name,
        "analysis": {"swift": _public(facts, producer)},
        "references": references,
        "registry_audit": {"drift": registry},
        "link_check": {"drift": link_drift, "advisory": link_advisory},
        "drift": rows,
        "limitation": (
            "Real Swift comment tokens only; references do not establish that a decision "
            "applies to a symbol, target, runtime path, framework, or Xcode configuration."
        ),
    }
    _atomic(output / "raw-drift.json", json.dumps(raw, indent=2, sort_keys=True) + "\n")
    _atomic(
        output / "registry-audit.json",
        json.dumps({"count": len(decisions), "drift": registry}, indent=2, sort_keys=True)
        + "\n",
    )
    links = [*link_advisory, *link_drift] or [
        f"OK — {len(decisions)} decisions, all links resolve"
    ]
    _atomic(output / "link-check.txt", "\n".join(links) + "\n")
    rendered = audit.render_drift(output.name, decisions, references, rows)
    _atomic(
        output / "drift.md",
        rendered
        + "\nSwift evidence is compiler-validated lexical comment syntax; applicability "
        "and symbol identity remain unresolved.\n",
    )
    print(output / "drift.md")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
