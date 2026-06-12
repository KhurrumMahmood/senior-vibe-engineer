#!/usr/bin/env python3
"""End-to-end harness validation: seed → install → score, per proposal.

For each proposal under ``fixtures/`` (default: all six — conformant,
defective, over-broad, poisoned-good, wrong-name, under-broad):

1. Seed a FRESH mini-host repo (its own ``mkdtemp``) so proposals never
   contaminate each other's plumbing/lint files.
2. Install the proposal into that repo (rule + fixtures copied in, wiring
   applied) via ``install_proposal.py``.
3. Score the post-install repo via ``score_conformance.py``.
4. Assert the expected verdict (conformant → all-pass; defective →
   fail-on-exactly-the-seeded-consequential-check).

Prints each scorecard and a final PASS/FAIL banner for the harness itself.

Stdlib-only. Self-cleaning (removes each seeded temp repo unless ``--keep``).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = HERE / "seed_fixture.py"
INSTALL = HERE / "install_proposal.py"
SCORE = HERE / "score_conformance.py"
FIXTURES = HERE / "fixtures"
PROJECT_ROOT = HERE.parents[1]  # repo root (scripts/skill_comply -> scripts -> root): holds .claude/skills/...

# Expected outcomes for the shipped fixtures. Each defective case names the
# exact CONSEQUENTIAL check set it must trip, so a fixture that fails "for the
# wrong reason" is caught too. The defect classes deliberately span the verdict
# space:
#   conformant    pass               every check passes
#   defective     fail  C4+C9        matcher drift — rule misses the real bug
#                                    (subscript-only, so it misses the recall
#                                    siblings too — both fail honestly)
#   over-broad    fail  C8           fires on innocent code (the C8 hole, now closed)
#   poisoned-good fail  C3           the "clean" good fixture hides a live anti-pattern
#   wrong-name    fail  C4+C9        emitted tag drifts from the wired name →
#                                    both tag-counting checks see 0 hits
#   under-broad   fail  C9           literal-`request`-receiver matcher misses the
#                                    sibling forms planted in app/views/reports.py
#                                    (passes C3/C4/C8 — the recall axis is the
#                                    ONLY check that sees it)
# (wrong-name shares C4 with defective by design — see DESIGN.md on the
# tag-coupling fragility; the two are distinguishable only by the C2 cosmetic line.)
EXPECTATIONS = {
    "conformant": {"verdict": "pass", "consequential_fail_ids": []},
    "defective": {"verdict": "fail", "consequential_fail_ids": ["C4", "C9"]},
    "over-broad": {"verdict": "fail", "consequential_fail_ids": ["C8"]},
    "poisoned-good": {"verdict": "fail", "consequential_fail_ids": ["C3"]},
    "wrong-name": {"verdict": "fail", "consequential_fail_ids": ["C4", "C9"]},
    "under-broad": {"verdict": "fail", "consequential_fail_ids": ["C9"]},
}

DEFAULT_FIXTURES = [
    "conformant", "defective", "over-broad", "poisoned-good", "wrong-name", "under-broad",
]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def _seed() -> dict:
    proc = _run([sys.executable, str(SEED)])
    if proc.returncode != 0:
        raise SystemExit(f"seed failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


def _install(proposal: Path, repo: Path) -> None:
    proc = _run([sys.executable, str(INSTALL), "--proposal", str(proposal), "--repo", str(repo)])
    if proc.returncode != 0:
        raise SystemExit(f"install failed for {proposal}:\n{proc.stdout}\n{proc.stderr}")


def _score(proposal: Path, manifest: dict) -> tuple[dict, str]:
    out = proposal / "conformance.json"
    cmd = [
        sys.executable, str(SCORE),
        "--proposal", str(proposal),
        "--repo", manifest["repo"],
        "--anchor", manifest["anchor"],
        "--rule-name", manifest["rule_name"],
        "--fixed-files", *manifest["fixed_files"],
        "--antipattern-files", *manifest["antipattern_files"],
        "--recall-files", *manifest["recall_files"],
        "--project-root", str(PROJECT_ROOT),
        "--out", str(out),
    ]
    proc = _run(cmd)
    # score exits 0 (pass/pass-with-notes) or 1 (fail) — both are expected
    # depending on the fixture; only 2 is a harness error.
    if proc.returncode == 2:
        raise SystemExit(f"scorer harness error for {proposal}:\n{proc.stdout}\n{proc.stderr}")
    card = json.loads(out.read_text(encoding="utf-8"))
    return card, proc.stdout


def _consequential_fail_ids(card: dict) -> list[str]:
    return [c["id"] for c in card["checks"] if c["consequential"] and not c["pass"]]


def validate_one(name: str, keep: bool) -> bool:
    proposal = FIXTURES / name
    if not proposal.is_dir():
        print(f"  [{name}] SKIP — no such proposal dir")
        return False

    manifest = _seed()
    repo = Path(manifest["repo"])
    try:
        _install(proposal, repo)
        card, summary = _score(proposal, manifest)
    finally:
        if not keep:
            shutil.rmtree(repo, ignore_errors=True)

    print(summary)

    exp = EXPECTATIONS.get(name)
    if exp is None:
        print(f"  [{name}] no expectation declared — scorecard printed above, not asserted")
        return True

    got_verdict = card["verdict"]
    got_fail_ids = _consequential_fail_ids(card)
    verdict_ok = got_verdict == exp["verdict"]
    fail_ids_ok = got_fail_ids == exp["consequential_fail_ids"]
    ok = verdict_ok and fail_ids_ok

    print(f"  [{name}] expectation check:")
    print(f"      verdict: got {got_verdict!r}, want {exp['verdict']!r} → {'OK' if verdict_ok else 'MISMATCH'}")
    print(f"      consequential failures: got {got_fail_ids}, want {exp['consequential_fail_ids']} → {'OK' if fail_ids_ok else 'MISMATCH'}")
    print(f"  [{name}] {'VALIDATED' if ok else 'FAILED EXPECTATION'}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=None,
                        help="Validate only these proposal names "
                             f"(default: {' '.join(DEFAULT_FIXTURES)})")
    parser.add_argument("--keep", action="store_true",
                        help="Keep the seeded temp repos for inspection")
    args = parser.parse_args()

    names = args.only or DEFAULT_FIXTURES
    print(f"== skill-comply harness validation: {', '.join(names)} ==")
    results = {name: validate_one(name, args.keep) for name in names}

    print("\n== Harness summary ==")
    for name, ok in results.items():
        print(f"  {name:12s} {'PASS' if ok else 'FAIL'}")
    all_ok = all(results.values())
    print(f"\nOVERALL: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
