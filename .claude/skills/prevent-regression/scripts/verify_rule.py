#!/usr/bin/env python3
"""Verify a custom AST lint rule against its fixture pair.

Runs the rule against `<rule>_bad.py` (expects ≥ 1 violation, exit 1)
and `<rule>_good.py` (expects 0 violations, exit 0), and prints a
report the orchestrator includes in `proposal.md`.

Usage:

    python3 .claude/skills/prevent-regression/scripts/verify_rule.py \\
      --rule scripts/lint/silent_catch.py \\
      --bad tests/lint/silent_catch_bad.py \\
      --good tests/lint/silent_catch_good.py

Exit status:

    0  both fixtures behave as expected (BAD_RC=1, GOOD_RC=0)
    1  one or both fixtures behave wrong — rule or fixtures need work
    2  invocation error

The verifier is the load-bearing gate for Phase 3. A rule without a
passing fixture pair is not trustworthy — the bad-case may be too
permissive, or the good-case may be accidentally matched.

Stdlib-only; runs under bare `python3`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(rule: Path, fixture: Path) -> tuple[int, str, str]:
    """Run the rule on the fixture and return (rc, stdout, stderr)."""
    proc = subprocess.run(
        ["python3", str(rule), str(fixture)],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _count_hits(stdout: str) -> int:
    """Count violation lines. A violation line has the shape
    `<path>:<line>:<col>: <rule>: <msg>`.
    Empty / whitespace-only lines and stderr pass-through don't count.
    """
    return sum(1 for line in stdout.splitlines() if line.strip() and ":" in line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rule",
        required=True,
        type=Path,
        help="Path to the rule script, e.g. scripts/lint/silent_catch.py",
    )
    parser.add_argument(
        "--bad",
        required=True,
        type=Path,
        help="Path to the known-bad fixture, e.g. tests/lint/silent_catch_bad.py",
    )
    parser.add_argument(
        "--good",
        required=True,
        type=Path,
        help="Path to the known-good fixture, e.g. tests/lint/silent_catch_good.py",
    )
    parser.add_argument(
        "--expected-bad-hits",
        type=int,
        default=None,
        help=(
            "If set, require the bad fixture to produce EXACTLY this many hits. "
            "Useful once the rule is stable and you want a regression guard on "
            "the fixture count."
        ),
    )
    args = parser.parse_args()

    for label, path in (("rule", args.rule), ("bad", args.bad), ("good", args.good)):
        if not path.exists():
            print(f"error: {label} file not found: {path}", file=sys.stderr)
            return 2

    bad_rc, bad_out, bad_err = _run(args.rule, args.bad)
    good_rc, good_out, good_err = _run(args.rule, args.good)

    bad_hits = _count_hits(bad_out)
    good_hits = _count_hits(good_out)

    report_lines = [
        f"rule  : {args.rule}",
        f"bad   : {args.bad}  rc={bad_rc}  hits={bad_hits}",
        f"good  : {args.good}  rc={good_rc}  hits={good_hits}",
    ]
    print("\n".join(report_lines))

    failures: list[str] = []

    if bad_rc != 1:
        failures.append(
            f"BAD_RC expected 1 (violations fired), got {bad_rc}. "
            "The rule is not catching the anti-pattern."
        )
    if bad_hits == 0:
        failures.append(
            "bad fixture produced 0 hits. Either the fixture is empty or the "
            "AST predicate does not match any variant."
        )
    if args.expected_bad_hits is not None and bad_hits != args.expected_bad_hits:
        failures.append(
            f"bad fixture produced {bad_hits} hits, expected exactly "
            f"{args.expected_bad_hits}. Update the fixture or the regression "
            "count."
        )
    if good_rc != 0:
        failures.append(
            f"GOOD_RC expected 0 (clean), got {good_rc}. The rule is firing on "
            "legitimate code — tighten the predicate or extend the allow-list."
        )
    if good_hits != 0:
        failures.append(
            f"good fixture produced {good_hits} hits. Inspect the stdout "
            "above; every hit is a false positive the rule must not produce."
        )

    if bad_err.strip():
        print("bad stderr:", bad_err, sep="\n")
    if good_err.strip():
        print("good stderr:", good_err, sep="\n")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        print("\nstdout (bad):")
        print(bad_out or "  <empty>")
        print("stdout (good):")
        print(good_out or "  <empty>")
        return 1

    print("\nPASS: BAD_RC=1, GOOD_RC=0, fixtures behave as expected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
