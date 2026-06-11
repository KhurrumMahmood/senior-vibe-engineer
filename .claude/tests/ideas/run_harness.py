#!/usr/bin/env python3
"""Idea-tracking harness — runs every fixture under fixtures/ against ideas_lib.

Each fixture directory contains:
    scenario.json   declares { function, kwargs, ledger?, plan?, expected }
    ledger.jsonl    starting ledger state (optional, named in scenario.json)
    expected.json   the expected return value (may be inline in scenario.json)
    README.md       scenario description

The harness:
    1. Walks fixtures/*/scenario.json
    2. Loads named inputs (ledger.jsonl, plan_items.json, etc.)
    3. Calls the named ideas_lib function with kwargs (passing loaded ledger
       as first positional arg if `ledger` is set in scenario.json)
    4. Diff-checks the return against expected
    5. Reports per-scenario PASS / FAIL / SKIP

Skip semantics: a scenario.json with `"skip": "reason"` is reported but not
executed. Used for fixtures whose target function does not exist yet
(extraction-truth-set awaits P5).

Usage:
    python3 .claude/tests/ideas/run_harness.py             # all fixtures
    python3 .claude/tests/ideas/run_harness.py <name>...   # specific ones
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HARNESS_PATH = Path(__file__).resolve()
HARNESS_DIR = HARNESS_PATH.parent
REPO_ROOT = HARNESS_DIR.parent.parent.parent
COMMON_DIR = REPO_ROOT / ".claude" / "skills" / "_common"

# Make ideas_lib importable
sys.path.insert(0, str(COMMON_DIR))
import ideas_lib  # noqa: E402


def _normalize(value):
    """Sort lists of dicts/strings so diffs are order-insensitive."""
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items())}
    return value


def _diff(actual, expected) -> str | None:
    """Return a one-line diff summary, or None if equal."""
    a = _normalize(actual)
    e = _normalize(expected)
    if a == e:
        return None
    a_str = json.dumps(a, indent=2, sort_keys=True)
    e_str = json.dumps(e, indent=2, sort_keys=True)
    return f"actual:\n{a_str}\nexpected:\n{e_str}"


def run_fixture(fixture_dir: Path) -> tuple[str, str | None]:
    """Run one fixture. Returns (status, detail)."""
    scenario_path = fixture_dir / "scenario.json"
    if not scenario_path.exists():
        return ("SKIP", "no scenario.json")
    scenario = json.loads(scenario_path.read_text())

    if "skip" in scenario:
        return ("SKIP", scenario["skip"])

    fn_name = scenario["function"]
    fn = getattr(ideas_lib, fn_name, None)
    if fn is None:
        return ("SKIP", f"ideas_lib.{fn_name} not yet implemented")

    kwargs = dict(scenario.get("kwargs", {}))

    # Resolve fixture-relative paths for any kwargs named in `kwargs_paths`.
    # These come through as Path objects rather than strings.
    for key, rel in (scenario.get("kwargs_paths") or {}).items():
        kwargs[key] = (fixture_dir / rel).resolve()

    # Load ledger as positional if named
    args: list = []
    if scenario.get("ledger"):
        ledger_path = fixture_dir / scenario["ledger"]
        args.append(ideas_lib.load_ledger(ledger_path))

    try:
        result = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — test harness: any error from the function under test becomes a FAIL result
        return ("FAIL", f"exception: {type(exc).__name__}: {exc}")

    expected = scenario.get("expected")
    if "expected_path" in scenario:
        expected = json.loads((fixture_dir / scenario["expected_path"]).read_text())

    diff = _diff(result, expected)
    if diff is None:
        return ("PASS", None)
    return ("FAIL", diff)


def main(argv: list[str]) -> int:
    fixtures_dir = HARNESS_DIR / "fixtures"
    selected = set(argv[1:]) if len(argv) > 1 else None

    if not fixtures_dir.exists():
        print(f"no fixtures directory at {fixtures_dir}", file=sys.stderr)
        return 2

    results: list[tuple[str, str, str | None]] = []
    fixture_dirs = sorted(p for p in fixtures_dir.iterdir() if p.is_dir())
    for fix in fixture_dirs:
        if selected and fix.name not in selected:
            continue
        status, detail = run_fixture(fix)
        results.append((fix.name, status, detail))

    width = max((len(n) for n, *_ in results), default=20)
    fails = 0
    skips = 0
    for name, status, detail in results:
        line = f"  {name.ljust(width)}  {status}"
        if detail and status == "SKIP":
            line += f"  ({detail})"
        print(line)
        if status == "FAIL":
            fails += 1
            print()
            for d_line in (detail or "").splitlines():
                print(f"      {d_line}")
            print()
        elif status == "SKIP":
            skips += 1

    passed = len(results) - fails - skips
    print(f"\n{passed} pass, {fails} fail, {skips} skip")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
