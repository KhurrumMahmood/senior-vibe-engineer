#!/usr/bin/env python3
"""Produce human-reviewed Ruby RBS contract-shape duplication leads."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
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
    spec = importlib.util.spec_from_file_location("ruby_duplication_facts", path)
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


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _safe_output(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports" / "semantic-duplication" / "ruby"
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/semantic-duplication/ruby") from exc
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output-dir cannot traverse a symbolic link")
    return output


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _owner_safe(facts: dict[str, Any], owner: str) -> bool:
    source = facts.get("source", {})
    if any(row.get("owner") == owner for key in ("dynamic", "mixins") for row in source.get(key, [])):
        return False
    return not any(
        row.get("owner") == owner and row.get("owner_reopened")
        for row in facts.get("correlations", [])
    )


def _direct_caller_contexts(facts: dict[str, Any], owner: str, name: str) -> list[dict[str, Any]]:
    short_owner = owner.rsplit("::", 1)[-1]
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    return [
        {
            "path": row["path"],
            "line": row["start_line"],
            "owner": row["owner"],
            "source": row["source"],
        }
        for row in facts.get("source", {}).get("calls", [])
        if row.get("name") == name
        and short_owner in (row.get("receiver") or "")
        and roles.get(row.get("path")) == "production"
    ]


def _verdict(path: Path | None, candidate_sha256: str) -> dict[str, Any]:
    if path is None:
        return {"state": "required", "candidate_sha256": candidate_sha256}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": "invalid", "detail": str(exc), "candidate_sha256": candidate_sha256}
    if payload.get("candidate_sha256") != candidate_sha256:
        return {"state": "stale", "candidate_sha256": candidate_sha256}
    return {"state": "bound", "candidate_sha256": candidate_sha256, "verdict": payload.get("verdict")}


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# find-semantic-duplication — Ruby RBS triage",
        "",
        "> Matching RBS contract shape and matching direct method-body spelling are review leads only, never behavioral equivalence or a safe consolidation claim.",
        "",
        f"Status: `{payload['status']}`",
        f"Candidate SHA-256: `{payload['candidate_sha256']}`",
        f"Verdict state: `{payload['human_verdict']['state']}`",
        "",
        "## Review-required leads",
        "",
    ]
    for row in payload["leads"]:
        lines.append(f"- `{row['id']}` — {' / '.join(item['owner'] + '#' + item['name'] for item in row['functions'])}")
    if not payload["leads"]:
        lines.append("None on the bounded RBS-backed surface.")
    lines.extend(["", "## Boundary", "", *[f"- {item}" for item in payload["limits"]], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", default="lib")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--verdict", type=Path)
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
    leads: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if facts.get("status") == "complete":
        correlations = {(row["owner"], row["name"]): row for row in facts.get("correlations", [])}
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for contract in facts.get("rbs", {}).get("methods", []):
            if contract.get("kind") != "instance" or contract.get("visibility") != "public":
                continue
            correlation = correlations.get((contract["owner"], contract["name"]), {})
            definitions = correlation.get("source_definitions", [])
            if not _owner_safe(facts, contract["owner"]) or len(definitions) != 1:
                continue
            body = _normalized(definitions[0].get("body", ""))
            if not body:
                continue
            groups[(str(contract["name"]), contract["type_sha256"], body)].append(
                {"contract": contract, "source": definitions[0]}
            )
        for (name, type_sha256, body), rows in sorted(groups.items()):
            if len(rows) != 2:
                continue
            functions = []
            for row in rows:
                contexts = _direct_caller_contexts(facts, row["contract"]["owner"], name)
                if not contexts:
                    break
                functions.append(
                    {
                        "owner": row["contract"]["owner"],
                        "name": name,
                        "rbs": {"path": row["contract"]["rbs_path"], "line": row["contract"]["line"]},
                        "source": {"path": row["source"]["path"], "line": row["source"]["start_line"]},
                        "direct_caller_contexts": contexts,
                    }
                )
            if len(functions) != 2:
                rejected.append(
                    {
                        "functions": [row["contract"]["owner"] for row in rows],
                        "reason": "distinct direct selected-source caller contexts not established",
                    }
                )
                continue
            leads.append(
                {
                    "id": f"RRSD-{len(leads) + 1:02d}",
                    "classification": "review_required_rbs_contract_shape_lead",
                    "functions": functions,
                    "rbs_type_sha256": type_sha256,
                    "direct_body_sha256": _hash(body),
                    "human_verdict": "required",
                    "boundary": "matching RBS types and source spelling do not prove behavioral equivalence",
                }
            )
    else:
        rejected.append({"reason": facts.get("failure_kind", "RBS semantic facts are incomplete")})
    candidate_sha256 = _hash(leads)
    verdict = _verdict(args.verdict, candidate_sha256)
    status = "complete" if facts.get("status") == "complete" else facts.get("status", "partial")
    if verdict["state"] in {"invalid", "stale"}:
        status = "partial"
        rejected.append({"reason": "human verdict is not bound to the current candidate hash"})
    payload = {
        "schema_version": "ruby-rbs-semantic-duplication-v1",
        "language": "ruby",
        "analyzer": "project-owned-rbs-method-contract+prism-direct-body-boundary",
        "status": status,
        "read_only": True,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_manifest_sha256": facts.get("source_manifest_sha256"),
        "leads": leads,
        "candidate_sha256": candidate_sha256,
        "human_verdict": verdict,
        "rejected": rejected,
        "limits": facts.get("limits", []),
    }
    try:
        output = _safe_output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    _atomic(output / "analysis.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(output / "triage.md", _report(payload))
    return 1 if status == "failed" else (2 if status == "partial" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
