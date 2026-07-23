#!/usr/bin/env python3
"""Report bounded RBS constructor-keyword sweep omissions without writes."""

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
    spec = importlib.util.spec_from_file_location("ruby_sweep_facts", path)
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
    allowed = root / "reports" / "find-incomplete-sweep" / "ruby"
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output-dir must stay beneath reports/find-incomplete-sweep/ruby") from exc
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output-dir cannot traverse a symbolic link")
    return output


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _optional_keywords(contract: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for overload in contract.get("overloads", []):
        method_type = overload.get("method_type", {}).get("type", {})
        values.update((method_type.get("optional_keywords") or {}).keys())
    return values


def _safe_owner(facts: dict[str, Any], owner: str) -> bool:
    source = facts.get("source", {})
    if any(row.get("owner") == owner for key in ("dynamic", "mixins") for row in source.get(key, [])):
        return False
    return not any(
        row.get("owner") == owner and row.get("owner_reopened")
        for row in facts.get("correlations", [])
    )


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# find-incomplete-sweep — Ruby",
        "",
        "> Direct selected-source constructor spelling is compared only inside one project-owned RBS optional-keyword contract. This is not a resolved call graph.",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Findings",
        "",
    ]
    for row in payload["findings"]:
        lines.append(
            f"- `{row['owner']}.new` omits optional RBS keyword `{row['keyword']}` at `{row['straggler']['path']}:{row['straggler']['line']}`; {row['with_keyword_count']} direct sibling calls include it"
        )
    if not payload["findings"]:
        lines.append("None on the bounded RBS-backed surface.")
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
    findings: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    if facts.get("status") == "complete":
        for contract in facts.get("rbs", {}).get("methods", []):
            if contract.get("name") != "initialize" or contract.get("kind") != "instance":
                continue
            keywords = _optional_keywords(contract)
            if not keywords or not _safe_owner(facts, contract["owner"]):
                continue
            short_owner = contract["owner"].rsplit("::", 1)[-1]
            calls = [
                row
                for row in facts.get("source", {}).get("calls", [])
                if row.get("name") == "new"
                and row.get("receiver", "").split("::")[-1] == short_owner
                and roles.get(row.get("path")) == "production"
            ]
            for keyword in sorted(keywords):
                with_keyword = [row for row in calls if any(arg.startswith(f"{keyword}:") for arg in row.get("arguments", []))]
                without_keyword = [row for row in calls if not any(arg.startswith(f"{keyword}:") for arg in row.get("arguments", []))]
                if len(with_keyword) >= 2 and len(without_keyword) == 1:
                    straggler = without_keyword[0]
                    findings.append(
                        {
                            "classification": "review_required_optional_keyword_sweep_gap",
                            "owner": contract["owner"],
                            "keyword": keyword,
                            "rbs": {"path": contract["rbs_path"], "line": contract["line"]},
                            "group_size": len(calls),
                            "with_keyword_count": len(with_keyword),
                            "straggler": {"path": straggler["path"], "line": straggler["start_line"], "source": straggler["source"]},
                            "direct_call_rows": [
                                {"path": row["path"], "line": row["start_line"], "source": row["source"]}
                                for row in calls
                            ],
                            "human_verdict": "required",
                            "boundary": "not a trajectory, resolved target, or behavior claim",
                        }
                    )
                elif calls:
                    deferred.append(
                        {
                            "owner": contract["owner"],
                            "keyword": keyword,
                            "reason": "direct selected-source constructor group does not have one bounded straggler",
                        }
                    )
    else:
        deferred.append({"reason": facts.get("failure_kind", "RBS semantic facts are incomplete")})
    status = "complete" if facts.get("status") == "complete" else facts.get("status", "partial")
    payload = {
        "schema_version": "ruby-rbs-incomplete-sweep-v1",
        "language": "ruby",
        "analyzer": "project-owned-rbs-optional-keyword+prism-direct-constructor-boundary",
        "status": status,
        "read_only": True,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_manifest_sha256": facts.get("source_manifest_sha256"),
        "findings": findings,
        "finding_sha256": _hash(findings),
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
