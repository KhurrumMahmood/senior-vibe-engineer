#!/usr/bin/env python3
"""Emit an honest Dart semantic-duplication stop artifact for the D4 fact gap."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


MISSING_FACT = "per-function outgoing call-hierarchy results with source and target lineage"


def _provider():
    candidates = [Path(__file__).with_name("dart_lsp_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "dart_lsp_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Dart LSP fact provider is missing")
    spec = importlib.util.spec_from_file_location("dart_duplication_lsp_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _safe_output(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports" / "semantic-duplication"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/semantic-duplication/") from exc
    if not relative.parts:
        raise ValueError("output-dir must name a scan")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValueError("output-dir must not traverse a symbolic link")
    return output


def _replace_directory(staged: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    if destination.exists():
        destination.replace(backup)
    try:
        staged.replace(destination)
    except OSError:
        if backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
        output = _safe_output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    provider = _provider()
    try:
        facts = provider.load_or_collect(
            facts=args.facts,
            project_root=root,
            target=args.target,
            queries=[],
            dart=args.dart,
            packages=args.packages,
            cache_dir=args.cache_dir,
            timeout=args.timeout,
        )
    except (provider.DartFactError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    requests = facts.get("query_plan", {}).get("requests", [])
    call_hierarchy_requests = {
        "textDocument/prepareCallHierarchy",
        "callHierarchy/incomingCalls",
        "callHierarchy/outgoingCalls",
    }
    provider_has_required_facts = bool(
        call_hierarchy_requests.issubset(set(requests))
        and facts.get("call_hierarchy_queries")
    )
    # The accepted v1 D4 interface has no call-hierarchy result surface.  Do
    # not approximate it with spelling, document symbols, or raw references.
    if facts.get("status") == "failed":
        status = "failed"
        failure_kind = facts.get("failure_kind") or "upstream_semantic_failure"
    elif provider_has_required_facts:
        status = "partial"
        failure_kind = "consumer_not_implemented_for_unaccepted_provider_revision"
    else:
        status = "partial"
        failure_kind = "accepted_provider_fact_gap"
    uncertain: list[dict[str, Any]] = [
        {
            "reason": failure_kind,
            "detail": (
                "D4 v1 records definitions and top-level references but no per-function outgoing "
                "call-hierarchy results; matching direct callee sets cannot be established."
            ),
        }
    ]
    payload: dict[str, Any] = {
        "schema_version": "dart-semantic-duplication-v1",
        "language": "dart",
        "read_only": True,
        "status": status,
        "failure_kind": failure_kind,
        "upstream_status": facts.get("status"),
        "upstream_failure_kind": facts.get("failure_kind"),
        "target": target.relative_to(root).as_posix(),
        "analyzer": "dart-sdk-lsp-provider-gap-stop",
        "confirmed": [],
        "rejected": [],
        "uncertain": uncertain,
        "missing_required_facts": [] if provider_has_required_facts else [MISSING_FACT],
        "provider_query_plan": facts.get("query_plan", {}),
        "provider_capabilities": facts.get("capabilities", {}),
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "query_plan_sha256": facts.get("query_plan_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "summary": {"review_required_leads": 0, "rejected": 0, "uncertain": 1},
        "limits": [
            *facts.get("limits", []),
            "no name-similarity, lexical-clone, raw-reference, or inferred-call fallback is permitted",
            "no behavioral equivalence, side-effect model, safe consolidation, or runtime/protocol compatibility is claimed",
            "D5 implementation stops until the accepted D4 public interface supplies outgoing call-hierarchy lineage",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    analysis_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    findings = {
        "schema_version": payload["schema_version"],
        "status": status,
        "failure_kind": failure_kind,
        "confirmed": [],
        "rejected": [],
        "uncertain": uncertain,
    }
    _atomic(staged / "analysis.json", analysis_text)
    _atomic(staged / "findings.json", json.dumps(findings, indent=2, sort_keys=True) + "\n")
    _atomic(staged / "facts.json", json.dumps(facts, indent=2, sort_keys=True) + "\n")
    _atomic(
        staged / "triage.md",
        "\n".join(
            [
                "# find-semantic-duplication — Dart triage",
                "",
                "> No Dart lead was promoted. The accepted D4 fact pack does not contain per-function outgoing call hierarchy.",
                "",
                f"Status: `{status}`",
                f"Failure kind: `{failure_kind}`",
                "",
                "The consumer stopped rather than substituting lexical similarity, raw references, or an unowned second LSP client.",
                "",
            ]
        ),
    )
    scan = {
        "schema_version": "dart-semantic-duplication-scan-v1",
        "status": status,
        "failure_kind": failure_kind,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "analysis_sha256": hashlib.sha256(analysis_text.encode()).hexdigest(),
        "review_required_leads": 0,
    }
    _atomic(staged / "scan.json", json.dumps(scan, indent=2, sort_keys=True) + "\n")
    _replace_directory(staged, output)
    print(f"wrote Dart semantic-duplication stop evidence: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
