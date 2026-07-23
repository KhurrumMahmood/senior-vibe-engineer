#!/usr/bin/env python3
"""Find bounded RBS-backed Ruby string-state candidates for human verdict."""

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
    spec = importlib.util.spec_from_file_location("ruby_state_facts", path)
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
    allowed = root / "reports" / "find-implicit-state" / "ruby"
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/find-implicit-state/ruby") from exc
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output-dir cannot traverse a symbolic link")
    return output


def _owner_safe(facts: dict[str, Any], owner: str) -> bool:
    return not any(row.get("owner") == owner for key in ("dynamic", "mixins") for row in facts.get("source", {}).get(key, [])) and not any(
        row.get("owner") == owner and row.get("owner_reopened") for row in facts.get("correlations", [])
    )


def _state_values(facts: dict[str, Any], owner: str, name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in facts.get("source", {}).get("writes", []):
        if row.get("owner") == owner and row.get("name") == f"@{name}":
            rows.append({"path": row["path"], "line": row["start_line"], "value": row["value"]})
    for row in facts.get("source", {}).get("calls", []):
        if row.get("owner") == owner and row.get("name") == f"{name}=":
            rows.append(
                {
                    "path": row["path"],
                    "line": row["start_line"],
                    "value": row.get("arguments", [""])[0] if row.get("arguments") else "",
                }
            )
    return rows


def _literal(value: str) -> str | None:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return None


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
        "# find-implicit-state — Ruby",
        "",
        "> Detection only. A RBS string attribute plus observed literals is not a proof that the state domain is closed.",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Candidate-hash-bound review",
        "",
        f"Candidate SHA-256: `{payload['candidate_sha256']}`",
        f"Verdict state: `{payload['human_verdict']['state']}`",
        "",
        "## Candidates",
        "",
    ]
    for row in payload["candidates"]:
        lines.append(
            f"- `{row['owner']}#{row['name']}` — observed: {', '.join(row['literals'])}; human verdict required"
        )
    if not payload["candidates"]:
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
    candidates: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    if facts.get("status") == "complete":
        aliases = facts.get("rbs", {}).get("aliases", [])
        for attribute in facts.get("rbs", {}).get("attributes", []):
            owner, name = attribute["owner"], attribute["name"]
            if attribute.get("kind") != "attr_accessor" or name not in {"state", "status", "phase"}:
                continue
            if attribute.get("type", {}).get("name") != "String":
                continue
            aliases_for_name = [
                row
                for row in aliases
                if row.get("owner") in {owner.rsplit("::", 1)[0], owner}
                and row.get("name", "").rsplit("::", 1)[-1] == name
                and len(row.get("literals", [])) >= 2
            ]
            if len(aliases_for_name) != 1 or not _owner_safe(facts, owner):
                deferred.append(
                    {"owner": owner, "name": name, "reason": "no unique closed RBS literal alias or owner has a Ruby dynamic boundary"}
                )
                continue
            values = _state_values(facts, owner, name)
            literals = sorted({value for row in values if (value := _literal(row["value"]))})
            declared = aliases_for_name[0]["literals"]
            if len(literals) < 2 or not set(literals).issubset(declared):
                deferred.append(
                    {"owner": owner, "name": name, "reason": "observed assignments do not fit one project-owned RBS literal alias"}
                )
                continue
            candidates.append(
                {
                    "classification": "review_required_string_state_candidate",
                    "owner": owner,
                    "name": name,
                    "rbs_attribute": {"path": attribute["rbs_path"], "line": attribute["line"]},
                    "rbs_literal_alias": {"name": aliases_for_name[0]["name"], "literals": declared},
                    "literals": literals,
                    "operations": values,
                    "human_verdict": "required",
                    "boundary": "RBS and observed literals do not prove a closed runtime state domain",
                }
            )
    else:
        deferred.append({"reason": facts.get("failure_kind", "RBS semantic facts are incomplete")})
    candidate_sha256 = _hash(candidates)
    verdict = _verdict(args.verdict, candidate_sha256)
    status = "complete" if facts.get("status") == "complete" else facts.get("status", "partial")
    if verdict["state"] in {"invalid", "stale"}:
        status = "partial"
        deferred.append({"reason": "human verdict is not bound to the current candidate hash"})
    payload = {
        "schema_version": "ruby-rbs-implicit-state-v1",
        "language": "ruby",
        "analyzer": "project-owned-rbs-state-contract+prism-write-boundary",
        "status": status,
        "read_only": True,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_manifest_sha256": facts.get("source_manifest_sha256"),
        "candidates": candidates,
        "candidate_sha256": candidate_sha256,
        "human_verdict": verdict,
        "deferred": deferred,
        "limits": facts.get("limits", []),
    }
    try:
        output = _safe_output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(output / "report.md", _report(payload))
    return 1 if status == "failed" else (2 if status == "partial" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
