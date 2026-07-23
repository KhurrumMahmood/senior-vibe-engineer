#!/usr/bin/env python3
"""Produce RBS-backed Ruby private-method review candidates without writes."""

from __future__ import annotations

import argparse
import hashlib
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
    spec = importlib.util.spec_from_file_location("ruby_dormant_facts", path)
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
    allowed = root / "reports" / "find-dormant" / "ruby"
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/find-dormant/ruby") from exc
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output-dir cannot traverse a symbolic link")
    return output


def _hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _owner_boundary(facts: dict[str, Any], owner: str) -> str | None:
    if any(row.get("owner") == owner for row in facts.get("source", {}).get("dynamic", [])):
        return "dynamic Ruby operation in the candidate owner"
    if any(row.get("owner") == owner for row in facts.get("source", {}).get("mixins", [])):
        return "mixin-bearing owner is outside dormant review claims"
    if any(
        row.get("owner") == owner and row.get("owner_reopened")
        for row in facts.get("correlations", [])
    ):
        return "class/module reopening is outside dormant review claims"
    return None


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# find-dormant — Ruby RBS review candidates",
        "",
        "> Read-only evidence. No candidate is certified safe to delete.",
        "",
        f"Status: `{payload['status']}`",
        f"Review-required candidates: `{len(payload['candidates'])}`",
        "Certain-delete findings: `0`",
        "",
        "## Candidates",
        "",
    ]
    for row in payload["candidates"]:
        lines.append(
            f"- `{row['source']['path']}:{row['source']['line']}` `{row['owner']}#{row['name']}` — private RBS contract, no direct selected-source call; review required"
        )
    if not payload["candidates"]:
        lines.append("None on the bounded RBS-backed surface.")
    lines.extend(["", "## Deferred", ""])
    lines.extend(
        f"- `{row.get('owner', '<unknown>')}#{row.get('name', '<unknown>')}` — {row['reason']}"
        for row in payload["deferred"]
    )
    lines.extend(["", "## Boundary", "", *[f"- {item}" for item in payload["limits"]], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", default="lib")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--ruby", default="ruby")
    parser.add_argument("--bundler", default="bundle")
    parser.add_argument("--rbs", default="rbs")
    parser.add_argument("--test")
    parser.add_argument("--smoke")
    args = parser.parse_args()
    root = args.project_root.resolve()
    provider = _provider()
    facts, _ = provider.load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        ruby=args.ruby,
        bundler=args.bundler,
        rbs=args.rbs,
        test=args.test,
        smoke=args.smoke,
    )
    candidates: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    role_by_path = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    if facts.get("status") == "complete":
        correlations = {
            (row["owner"], row["name"]): row for row in facts.get("correlations", [])
        }
        calls = facts.get("source", {}).get("calls", [])
        for contract in facts.get("rbs", {}).get("methods", []):
            if contract.get("kind") != "instance" or contract.get("visibility") != "private":
                continue
            owner, name = contract["owner"], contract["name"]
            correlation = correlations.get((owner, name), {})
            boundary = _owner_boundary(facts, owner)
            if boundary:
                deferred.append({"owner": owner, "name": name, "reason": boundary})
                continue
            definitions = correlation.get("source_definitions", [])
            if len(definitions) != 1 or correlation.get("owner_reopened"):
                deferred.append(
                    {
                        "owner": owner,
                        "name": name,
                        "reason": "private RBS contract does not have one non-reopened source definition",
                    }
                )
                continue
            direct_calls = [
                row
                for row in calls
                if row.get("name") == name
                and role_by_path.get(row.get("path")) in {"production", "test", "entrypoint"}
            ]
            if direct_calls:
                deferred.append(
                    {
                        "owner": owner,
                        "name": name,
                        "reason": "direct selected-source calls exist",
                        "direct_call_count": len(direct_calls),
                    }
                )
                continue
            source = definitions[0]
            candidates.append(
                {
                    "classification": "review_required_private_contract_candidate",
                    "owner": owner,
                    "name": name,
                    "rbs": {"path": contract["rbs_path"], "line": contract["line"]},
                    "source": {"path": source["path"], "line": source["start_line"]},
                    "direct_selected_source_call_count": 0,
                    "human_verdict": "required",
                    "boundary": "not a reachability or deletion-safety claim",
                }
            )
    else:
        deferred.append({"reason": facts.get("failure_kind", "RBS semantic facts are incomplete")})
    status = "complete" if facts.get("status") == "complete" else facts.get("status", "partial")
    payload = {
        "schema_version": "ruby-rbs-dormant-v1",
        "language": "ruby",
        "analyzer": "project-owned-rbs-private-contract+prism-direct-call-boundary",
        "status": status,
        "read_only": True,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_manifest_sha256": facts.get("source_manifest_sha256"),
        "candidates": candidates,
        "candidate_sha256": _hash(candidates),
        "deferred": deferred,
        "summary": {"review_required": len(candidates), "certain_delete": 0, "deferred": len(deferred)},
        "limits": facts.get("limits", []),
    }
    try:
        output = _safe_output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(output / "report.md", _render(payload))
    return 1 if status == "failed" else (2 if status == "partial" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
