#!/usr/bin/env python3
"""Bucket-B oracle #1: proposer completeness against planted ground truth.

skill-comply's C1–C9 grade Bucket-A guard proposals (a runnable lint rule that
must fire on a bug). This oracle grades the OUTPUT of a SUSPECT/proposer-family
skill — a findings report — for *completeness*: did the skill surface every
planted anti-pattern instance, did it invent any that aren't there?

The ground truth is the seed fixture's planted-instance inventory
(``planted_instances`` in the manifest ``seed_fixture.py`` prints): every
anti-pattern instance live at HEAD, each with a stable ID, file, line, and
syntactic form. No live skill run is needed — the oracle is fixture-based and
grades any findings file against that inventory.

Contract
--------

CLI::

    oracle_proposer_completeness.py \\
        --report <dir>                  # skill report directory
        --ground-truth <manifest.json>  # seed manifest with planted_instances
        [--out <path>]                  # default: <report>/oracle.json
        [--line-tolerance N]            # default 0 (exact line match)

The report directory must contain ``findings.json``::

    {"findings": [{"id": "F1", "file": "app/views/checkout.py", "line": 9}, ...]}

``id`` is optional (synthesized as ``F<position>`` when absent); ``file`` is
repo-relative POSIX; ``line`` is 1-based. A ``triage.md`` may sit beside it —
its presence is noted in the output but not graded (triage quality is a review
concern, not a completeness one).

Matching: a finding matches a planted instance when the files are equal and
``|finding.line - instance.line| <= line-tolerance``. Matching is one-to-one,
greedy in findings order — an instance is consumed by the first finding that
matches it. Findings that match no remaining instance are false positives;
instances no finding matched are misses.

Output shape (written to ``--out`` and summarized on stdout)::

    {
      "report": "...", "ground_truth": "...",
      "total_instances": 3, "total_findings": 3,
      "found":            [{"instance_id": "...", "finding_id": "..."}],
      "missed":           ["<instance_id>", ...],
      "false_positives":  ["<finding_id>", ...],
      "recall": 1.0, "precision": 1.0,
      "triage_present": true,
      "verdict": "pass" | "fail"
    }

Verdict: ``pass`` only when recall == 1.0 AND there are no false positives —
a proposer that misses real instances is incomplete, and one that pads its
report with phantom instances is noise that erodes trust the same way an
over-broad guard does (C8's reasoning, applied to reports).

Exit status::

    0  verdict pass
    1  verdict fail (missed instances and/or false positives)
    2  harness error (missing/malformed inputs)

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_json(path: Path, what: str) -> dict:
    if not path.exists():
        raise SystemExit(f"error: {what} not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SystemExit(f"error: {what} is not valid JSON: {path} — {exc}") from exc


def _normalize_findings(raw: dict) -> list[dict]:
    findings = raw.get("findings")
    if not isinstance(findings, list):
        raise SystemExit("error: findings.json must contain a top-level 'findings' list")
    normalized: list[dict] = []
    for pos, f in enumerate(findings, start=1):
        if not isinstance(f, dict) or "file" not in f or "line" not in f:
            raise SystemExit(
                f"error: finding #{pos} must be an object with 'file' and 'line'"
            )
        try:
            line = int(f["line"])
        except (TypeError, ValueError):
            raise SystemExit(
                f"error: finding #{pos} has a non-integer 'line': {f['line']!r}"
            ) from None
        normalized.append({"id": str(f.get("id") or f"F{pos}"), "file": f["file"], "line": line})
    return normalized


def grade(
    instances: list[dict],
    findings: list[dict],
    line_tolerance: int = 0,
) -> dict:
    """Match findings to planted instances one-to-one and score completeness."""
    remaining = {inst["id"]: inst for inst in instances}
    found: list[dict] = []
    false_positives: list[str] = []

    for f in findings:
        match_id = next(
            (
                iid
                for iid, inst in remaining.items()
                if inst["file"] == f["file"]
                and abs(inst["line"] - f["line"]) <= line_tolerance
            ),
            None,
        )
        if match_id is None:
            false_positives.append(f["id"])
        else:
            found.append({"instance_id": match_id, "finding_id": f["id"]})
            del remaining[match_id]

    missed = sorted(remaining)
    total = len(instances)
    recall = len(found) / total if total else 1.0
    precision = len(found) / len(findings) if findings else 1.0
    verdict = "pass" if not missed and not false_positives else "fail"
    return {
        "total_instances": total,
        "total_findings": len(findings),
        "found": found,
        "missed": missed,
        "false_positives": false_positives,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "verdict": verdict,
    }


def _print_summary(result: dict) -> None:
    print(f"\nProposer-completeness oracle — verdict: {result['verdict'].upper()}")
    print(f"  planted instances : {result['total_instances']}")
    print(f"  findings reported : {result['total_findings']}")
    print(f"  recall            : {result['recall']}  precision: {result['precision']}")
    for pair in result["found"]:
        print(f"  FOUND   {pair['instance_id']}  (finding {pair['finding_id']})")
    for iid in result["missed"]:
        print(f"  MISSED  {iid}")
    for fid in result["false_positives"]:
        print(f"  FALSE+  finding {fid} matches no planted instance")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path,
                        help="Skill report directory containing findings.json")
    parser.add_argument("--ground-truth", required=True, type=Path,
                        help="Seed manifest JSON carrying 'planted_instances'")
    parser.add_argument("--out", type=Path, default=None,
                        help="Where to write oracle.json (default: <report>/oracle.json)")
    parser.add_argument("--line-tolerance", type=int, default=0,
                        help="Max |line delta| for a finding to match an instance (default 0)")
    args = parser.parse_args()

    if not args.report.is_dir():
        print(f"error: report dir not found: {args.report}", file=sys.stderr)
        return 2

    try:
        manifest = _load_json(args.ground_truth, "ground-truth manifest")
        instances = manifest.get("planted_instances")
        if not isinstance(instances, list) or not instances:
            print(
                f"error: {args.ground_truth} has no 'planted_instances' — "
                "re-seed with the current seed_fixture.py",
                file=sys.stderr,
            )
            return 2
        findings = _normalize_findings(_load_json(args.report / "findings.json", "findings.json"))
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    result = grade(instances, findings, line_tolerance=args.line_tolerance)
    result = {
        "report": str(args.report),
        "ground_truth": str(args.ground_truth),
        **result,
        "triage_present": (args.report / "triage.md").exists(),
    }

    out = args.out or (args.report / "oracle.json")
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    _print_summary(result)
    print(f"\nwrote {out}")
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
