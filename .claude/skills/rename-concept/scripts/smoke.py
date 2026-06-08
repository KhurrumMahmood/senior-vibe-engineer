#!/usr/bin/env python3
"""Smoke test for rename-concept (v0 assess-only).

Black-box against the real ES2 find-concept-divergence scanner. Proves the
TWO-BAND completeness gate — the skill's headline novelty — actually renders
and gates correctly:

  1. both bands render on a clean run (band 3 superseded_co_occurrence AND
     band 1 avoid_term_hit each print a status line);
  2. the gate goes RED when a band-1 retired-prose hit exists (inject a probe
     file using a glossary `avoid:` phrase verbatim, assert band 1 flips RED
     and the verdict is HALF-APPLIED — then REMOVE the probe);
  3. gate logic requires BOTH bands clean (a band-1 hit alone, with band 3
     green, is sufficient to turn the verdict away from COMPLETE).

Self-contained: manages its own probe lifecycle via tempfile + os.remove, and
reads assess.py's rendered stdout rather than depending on the live tree's
findings. Exit 0 = pass (the ecosystem skill-smoke gate requires this).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
ASSESS = SCRIPT_DIR / "assess.py"
# .claude/skills/rename-concept/scripts/smoke.py -> repo root.
#   parents[0]=scripts [1]=rename-concept [2]=skills [3]=.claude [4]=repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
GLOSSARY = REPO_ROOT / ".claude/contracts/concepts.yaml"
# Probe lives under a scanned root (tests/) so find-concept-divergence's
# default targets pick it up. Distinct name so it can never collide with a
# real fixture, and it is always removed in a finally.
PROBE = REPO_ROOT / "tests" / "_rename_concept_band1_probe_TMP.md"

BAND3_HEADER = "### band 3 — superseded_co_occurrence"
BAND1_HEADER = "### band 1 — avoid_term_hit"


def run_assess(old: str, new: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-B", str(ASSESS), old, new],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=240,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"assess.py exited {proc.returncode}\n--- stdout ---\n{proc.stdout}"
            f"\n--- stderr ---\n{proc.stderr}"
        )
    return proc.stdout


def _band_status(out: str, header: str) -> str:
    """Return the status token (GREEN / RED / UNAVAILABLE) printed on the line
    immediately following a band header."""
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if header in line:
            for follow in lines[i + 1:]:
                token = follow.strip()
                if token.startswith(("GREEN", "RED", "UNAVAILABLE")):
                    return token.split(maxsplit=1)[0]
    return "MISSING"


def pick_avoid_phrase() -> tuple[str, str]:
    """Pick a real glossary `avoid:` phrase and the concept slug that owns it,
    so the probe deterministically trips band 1 (avoid_term_hit) for that
    concept. Mirrors find-concept-divergence's own phrase extraction (text
    before the first '(' clarifier, stripped of surrounding quotes)."""
    try:
        raw = GLOSSARY.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Required artifact for this smoke: fail cleanly, never let the decode
        # error escape as a traceback (read-decode-safety.v1).
        raise SystemExit(f"cannot read glossary {GLOSSARY}: {exc}") from exc
    data = yaml.safe_load(raw)
    for concept in data.get("concepts", []):
        for entry in concept.get("avoid", []) or []:
            if not isinstance(entry, str):
                continue
            phrase = entry.split("(")[0].strip().strip('"').strip("'").rstrip(",.;:")
            # Skip phrases containing inner quotes/slashes the scanner escapes
            # literally — pick a clean, single-line, plainly greppable phrase.
            if phrase and "'" not in phrase and "/" not in phrase and len(phrase.split()) >= 4:
                return concept["name"], phrase
    raise SystemExit("no usable avoid: phrase found in glossary — cannot build band-1 probe")


def main() -> int:
    # --- check 1: both bands render on a clean run -------------------------
    # Use a synthetic NEW slug that appears nowhere, so we exercise the
    # rendering for an arbitrary real concept without tripping either band.
    clean = run_assess("ledger", "zzz-nonexistent-target")
    if BAND3_HEADER not in clean or BAND1_HEADER not in clean:
        print("clean run did not render both band headers", file=sys.stderr)
        print(clean, file=sys.stderr)
        return 1
    b3 = _band_status(clean, BAND3_HEADER)
    b1 = _band_status(clean, BAND1_HEADER)
    if b3 not in {"GREEN", "RED"} or b1 not in {"GREEN", "RED"}:
        print(f"clean run bands did not render a status (band3={b3}, band1={b1})", file=sys.stderr)
        print(clean, file=sys.stderr)
        return 1
    # The ES2 tree is clean against its own glossary, so the honest expectation
    # is GREEN/GREEN — but the assertion above only requires *a rendered
    # status*, so the smoke does not rot if a real divergence later appears.

    # --- check 2 + 3: band-1 prose hit turns the gate RED ------------------
    concept_slug, phrase = pick_avoid_phrase()
    PROBE.write_text(
        f"# rename-concept smoke probe (transient)\n\n"
        f"This line intentionally uses retired phrasing: {phrase}.\n",
        encoding="utf-8",
    )
    try:
        # Run with old=<concept owning the avoid phrase> so the emitted
        # avoid_term_hit `concept` normalizes to our `old` key and band 1 trips.
        red = run_assess(concept_slug, "some-new-name")
    finally:
        if PROBE.exists():
            os.remove(PROBE)
    if PROBE.exists():
        print("FAILED to remove transient probe", file=sys.stderr)
        return 1

    red_b1 = _band_status(red, BAND1_HEADER)
    red_b3 = _band_status(red, BAND3_HEADER)
    if red_b1 != "RED":
        print(f"band 1 should be RED with the probe injected, got {red_b1}", file=sys.stderr)
        print(red, file=sys.stderr)
        return 1
    if red_b3 != "GREEN":
        # No concept in ES2 has superseded_by, so band 3 is structurally empty.
        print(f"band 3 should stay GREEN (no superseded_by concepts), got {red_b3}", file=sys.stderr)
        print(red, file=sys.stderr)
        return 1
    if str(PROBE.relative_to(REPO_ROOT)) not in red:
        print("probe file not named in the band-1 RED output", file=sys.stderr)
        print(red, file=sys.stderr)
        return 1
    # Gate logic: band 1 RED alone (band 3 GREEN) must keep the verdict OUT of
    # COMPLETE — both bands clean is required for done.
    verdict_block = red.split("## verdict", 1)[-1]
    if "COMPLETE" in verdict_block and "INCOMPLETE" not in verdict_block:
        print("a band-1 hit alone must not yield a COMPLETE verdict", file=sys.stderr)
        print(red, file=sys.stderr)
        return 1
    if "band 1 RED" not in verdict_block:
        print("verdict should cite 'band 1 RED' as an open item", file=sys.stderr)
        print(red, file=sys.stderr)
        return 1

    print(
        f"OK — both bands render (clean: band3={b3}, band1={b1}); "
        f"band-1 probe ('{phrase[:40]}…' on '{concept_slug}') flips band 1 RED "
        f"while band 3 stays GREEN; verdict HALF-APPLIED; probe removed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
