#!/usr/bin/env python3
"""Find one resolved C designated-initializer sweep omission shape."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def _provider():
    candidates = [Path(__file__).with_name("c_semantic_facts.py")]
    candidates.extend(parent / "_c-semantic/c_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("c_sweep_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _blame(root: Path, site: dict) -> tuple[int | None, str]:
    try:
        result = subprocess.run(
            ["git", "blame", "--line-porcelain", "-L", f"{site['line']},{site['line']}", "--", site["file"]],
            cwd=root, capture_output=True, text=True, check=False, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None, "failed"
    match = re.search(r"^committer-time (\d+)$", result.stdout, re.MULTILINE)
    if result.returncode or match is None or result.stdout.startswith("000000000000"):
        return None, "failed" if result.returncode else "insufficient"
    return int(match.group(1)), "available"


def main() -> int:
    provider = _provider()
    parser = provider.common_parser(__doc__)
    parser.add_argument("--verdict", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    facts = provider.load_or_collect(project_root=root, facts=args.facts, clang=args.clang)
    findings = []
    gated_out = []
    deferred = []
    git_state = "not-required"
    if facts["status"] == "complete":
        sites_by_record = defaultdict(list)
        for row in facts["compound_literals"]:
            if row["context"] == "return" and provider.in_target(row, root, args.target) and not row.get("macro_expansion"):
                sites_by_record[row["record"]].append(row)
            elif row["context"] == "return" and provider.in_target(row, root, args.target) and row.get("macro_expansion"):
                deferred.append({"file": row["file"], "line": row["line"], "reason": "macro_expansion_unresolved"})
        fields_by_record = defaultdict(set)
        for row in facts["declarations"]:
            if row["kind"] == "field" and row.get("owner"):
                fields_by_record[row["owner"]].add(row["name"])
        for record, sites in sorted(sites_by_record.items()):
            fields = fields_by_record.get(record, set())
            for field in sorted(fields):
                present = [site for site in sites if field in site["fields"]]
                missing = [site for site in sites if field not in site["fields"]]
                if len(sites) < 4 or len(present) < 3 or len(missing) != 1:
                    continue
                git_state = "available"
                straggler_time, old_state = _blame(root, missing[0])
                present_times = [_blame(root, site) for site in present]
                states = [old_state, *[state for _, state in present_times]]
                if straggler_time is None or any(state != "available" for state in states):
                    git_state = "failed" if "failed" in states else "insufficient"
                    deferred.append({
                        "record": record, "field": field,
                        "reason": f"{git_state}_git_evidence",
                    })
                    continue
                newer = all(timestamp is not None and timestamp > straggler_time for timestamp, _ in present_times)
                candidate = {
                    "record": record, "field": field, "callee": record, "kwarg": field,
                    "group_size": len(sites), "present_count": len(present),
                    "majority_frac": len(present) / len(sites),
                    "straggler": f"{missing[0]['file']}:{missing[0]['line']}",
                    "straggler_site": missing[0],
                    "present_sites": present, "gated_in": newer,
                    "trajectory": (
                        f"{len(present)}/{len(present)} designated-initializer sites touched AFTER the straggler"
                        if newer else "not all field-present sites are newer than the omission"
                    ),
                    "human_verdict": "required", "automatic_fix": False,
                }
                candidate["candidate_sha256"] = hashlib.sha256(
                    json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                (findings if newer else gated_out).append(candidate)
    else:
        deferred.append({"reason": facts["failure_kind"]})
    status = facts["status"]
    if status == "complete" and git_state not in {"available", "not-required"}:
        status = "partial"
    review = {"state": "required" if findings else "not-required"}
    if args.verdict is not None and findings:
        verdict_path = args.verdict if args.verdict.is_absolute() else root / args.verdict
        try:
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            review = {"state": "invalid", "reason": str(exc)}
            status = "partial"
        else:
            allowed = {"forgotten", "deliberate", "optional", "not-applicable"}
            if (
                verdict.get("candidate_sha256") != findings[0]["candidate_sha256"]
                or verdict.get("verdict") not in allowed
                or not isinstance(verdict.get("rationale"), str)
                or not verdict["rationale"].strip()
            ):
                review = {"state": "stale_or_invalid"}
                status = "partial"
            else:
                review = {
                    "state": "bound", "candidate_sha256": verdict["candidate_sha256"],
                    "verdict": verdict["verdict"], "rationale": verdict["rationale"],
                }
    payload = {
        "schema_version": "c-incomplete-sweep-v1", "language": "c",
        "status": status, "read_only": True,
        "analyzer": "clang-21-resolved-c17-designated-initializers+git-blame",
        "target": args.target, "fact_pack_sha256": facts["fact_pack_sha256"],
        "project_resolution": {"git_evidence": git_state},
        "human_review": review,
        "findings": findings, "gated_out": gated_out, "deferred": deferred,
        "summary": {"gated_in": len(findings), "gated_out": len(gated_out), "deferred": len(deferred)},
        "limits": [*facts["limits"], "Git trajectory and a fixed human verdict are required before any completion handoff"],
    }
    try:
        output = provider.safe_output(root, args.output, "reports/find-incomplete-sweep")
    except ValueError as exc:
        parser.error(str(exc))
    provider.atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
