#!/usr/bin/env python3
"""Assess one RBS-backed Ruby rename state without changing source."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


def _provider() -> Any:
    candidates = [Path(__file__).with_name("ruby_semantic_facts.py")]
    candidates.extend(
        parent / "_ruby-semantic" / "ruby_semantic_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Ruby RBS semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("ruby_rename_facts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("assembled Ruby RBS semantic fact provider cannot load")
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
    allowed = root / "reports" / "rename-concept" / "ruby"
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must stay beneath reports/rename-concept/ruby") from exc
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output cannot traverse a symbolic link")
    return output


def _matches(name: str, needle: str) -> bool:
    return name == needle or name.rsplit("::", 1)[-1] == needle


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# rename-concept — Ruby RBS assessment",
        "",
        "> Read-only assessment. It does not edit source and does not certify public API, reflection, dynamic constant, loader, or compatibility safety.",
        "",
        f"Status: `{payload['status']}`",
        f"Verdict: `{payload['verdict']}`",
        "",
        "## RBS authorities",
        "",
    ]
    lines.extend(
        f"- `{row['owner']}` at `{row['rbs_path']}:{row['line']}`" for row in payload["new_rbs_authorities"]
    )
    if not payload["new_rbs_authorities"]:
        lines.append("None.")
    lines.extend(["", "## Remaining old source declarations", ""])
    lines.extend(
        f"- `{row['name']}` at `{row['path']}:{row['line']}`" for row in payload["old_source_declarations"]
    )
    if not payload["old_source_declarations"]:
        lines.append("None on the bounded selected source surface.")
    lines.extend(["", "## Boundary", "", *[f"- {item}" for item in payload["limits"]], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", default="lib")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--ruby", default="ruby")
    parser.add_argument("--bundler", default="bundle")
    parser.add_argument("--rbs", default="rbs")
    parser.add_argument("--test")
    parser.add_argument("--smoke")
    args = parser.parse_args()
    root = args.project_root.resolve()
    facts, _ = _provider().load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        ruby=args.ruby,
        bundler=args.bundler,
        rbs=args.rbs,
        test=args.test,
        smoke=args.smoke,
    )
    new_authorities: list[dict[str, Any]] = []
    old_authorities: list[dict[str, Any]] = []
    new_source: list[dict[str, Any]] = []
    old_source: list[dict[str, Any]] = []
    if facts.get("status") == "complete":
        for row in facts.get("rbs", {}).get("declarations", []):
            item = {"owner": row["owner"], "rbs_path": row["rbs_path"], "line": row["line"], "kind": row["kind"]}
            if _matches(row["owner"], args.new):
                new_authorities.append(item)
            if _matches(row["owner"], args.old):
                old_authorities.append(item)
        for row in facts.get("source", {}).get("classes", []):
            item = {"name": row["name"], "path": row["path"], "line": row["start_line"], "kind": row["kind"]}
            if _matches(row["name"], args.new):
                new_source.append(item)
            if _matches(row["name"], args.old):
                old_source.append(item)
    reasons: list[str] = []
    if facts.get("status") != "complete":
        reasons.append(facts.get("failure_kind", "RBS semantic facts are incomplete"))
    if len(new_authorities) != 1:
        reasons.append("exactly one project-owned RBS authority for the new concept is required")
    if len(new_source) != 1:
        reasons.append("exactly one direct selected-source declaration for the new concept is required")
    if old_authorities or old_source:
        reasons.append("old RBS or selected-source declaration remains")
    if facts.get("status") == "complete" and not reasons:
        verdict = "CANDIDATE COMPLETE — EXTERNAL API REVIEW REQUIRED"
    elif new_authorities or new_source:
        verdict = "HALF-APPLIED / INCOMPLETE"
    else:
        verdict = "INCOMPLETE"
    status = "complete" if facts.get("status") == "complete" else facts.get("status", "partial")
    payload = {
        "schema_version": "ruby-rbs-rename-assessment-v1",
        "language": "ruby",
        "analyzer": "project-owned-rbs-declaration-authority+prism-source-boundary",
        "status": status,
        "read_only": True,
        "assess_only": True,
        "source_mutated": False,
        "old_concept": args.old,
        "new_concept": args.new,
        "verdict": verdict,
        "new_rbs_authorities": new_authorities,
        "old_rbs_authorities": old_authorities,
        "new_source_declarations": new_source,
        "old_source_declarations": old_source,
        "reasons": reasons,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_manifest_sha256": facts.get("source_manifest_sha256"),
        "limits": [
            *facts.get("limits", []),
            "assessment only: no codemod, compatibility, public API, reflection/string, asset, route, or loader safety claim",
        ],
    }
    try:
        output = _safe_output(root, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    _atomic(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(output.with_suffix(".md"), _report(payload))
    return 1 if status == "failed" else (2 if status == "partial" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
