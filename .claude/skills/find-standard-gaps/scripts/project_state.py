#!/usr/bin/env python3
"""Project-state surface + standard-activation gating (ADR 0020).

A standard's *activation* answers "does this rule apply to THIS project,
right now, at this depth?" — before its detector ever runs. The gate has
two independent axes, each an ordinal ladder:

  - maturity: prototype(0) < first-users(1) < production(2)
  - stakes:   internal(0)  < external(1)    < public-adversarial(2)

A project declares its (maturity, stakes) in a `.project-state.json`
surface at the repo root (JSON so this tooling stays stdlib-only). A
standard declares an `activation` of either `{"baseline": true}` (always
in scope) or `{"rungs": [...]}` where each rung carries
`{min_maturity, min_stakes}`. A rung is ACTIVE iff the declared state
meets BOTH thresholds; a standard is IN SCOPE iff it is baseline or has
at least one active rung.

Undeclared state is the dangerous case: rather than silently skip
production concerns, callers assume MAX (production / public-adversarial)
via `assumed_max_state()` so nothing is gated off, and warn the human to
run `/orient`. That assume-max policy is centralized here (the constant +
helper) and applied by callers when `load_project_state` returns None —
the loader itself stays honest and returns None for "absent".

Stdlib-only. Read-only against the project.
"""
from __future__ import annotations

import json
from pathlib import Path

# Ordinal ladders for >= comparison. Index = severity; a higher index
# means "more mature" / "higher stakes". These are the canonical orders
# the ADR-0020 contract fixes; the gate compares declared >= threshold.
MATURITY_LADDER = ["prototype", "first-users", "production"]
STAKES_LADDER = ["internal", "external", "public-adversarial"]

_MATURITY_RANK = {name: i for i, name in enumerate(MATURITY_LADDER)}
_STAKES_RANK = {name: i for i, name in enumerate(STAKES_LADDER)}

# The undeclared-state policy, centralized: when no `.project-state.json`
# is found, assume the top of both ladders so NOTHING is silently gated
# off (an unguarded production concern is the failure mode ADR 0020 most
# wants to avoid). Callers pass this explicit state and surface a warning.
ASSUMED_MAX_STATE = {
    "maturity": MATURITY_LADDER[-1],
    "stakes": STAKES_LADDER[-1],
    "declared_by": "assumed-max",
    "assumed": True,
}

PROJECT_STATE_FILENAME = ".project-state.json"


def load_project_state(root: Path) -> dict | None:
    """Read `<root>/.project-state.json`; validate enums; None if absent.

    Returns the parsed dict on success, or None when the file does not
    exist (the caller then substitutes `assumed_max_state()` and warns).
    Raises ValueError on a present-but-malformed file — a corrupt state
    surface is a real error, not an "absent" signal, and must not be
    silently treated as MAX.
    """
    path = Path(root) / PROJECT_STATE_FILENAME
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{PROJECT_STATE_FILENAME} is unreadable: {exc}") from exc
    if not isinstance(state, dict):
        raise ValueError(f"{PROJECT_STATE_FILENAME} must be a JSON object")
    maturity = state.get("maturity")
    stakes = state.get("stakes")
    if maturity not in _MATURITY_RANK:
        raise ValueError(
            f"{PROJECT_STATE_FILENAME}: maturity must be one of "
            f"{MATURITY_LADDER}, got {maturity!r}")
    if stakes not in _STAKES_RANK:
        raise ValueError(
            f"{PROJECT_STATE_FILENAME}: stakes must be one of "
            f"{STAKES_LADDER}, got {stakes!r}")
    return state


def assumed_max_state() -> dict:
    """The MAX state to use when no `.project-state.json` is declared.

    A fresh dict each call so a caller can annotate it without mutating
    the shared constant.
    """
    return dict(ASSUMED_MAX_STATE)


def rung_active(rung: dict, state: dict) -> bool:
    """A rung is active iff declared.maturity >= min_maturity AND
    declared.stakes >= min_stakes. Missing thresholds default to the
    bottom of their ladder (always met) — a rung that omits an axis does
    not gate on it. Unknown threshold values are treated as the top of
    the ladder (hardest to satisfy) so a typo cannot silently open a gate.
    """
    min_mat = rung.get("min_maturity", MATURITY_LADDER[0])
    min_stk = rung.get("min_stakes", STAKES_LADDER[0])
    mat_rank = _MATURITY_RANK.get(state.get("maturity"), 0)
    stk_rank = _STAKES_RANK.get(state.get("stakes"), 0)
    need_mat = _MATURITY_RANK.get(min_mat, len(MATURITY_LADDER))
    need_stk = _STAKES_RANK.get(min_stk, len(STAKES_LADDER))
    return mat_rank >= need_mat and stk_rank >= need_stk


def standard_in_scope(activation: dict | None, state: dict) -> tuple[bool, str]:
    """Decide whether a standard applies to a project in `state`.

    Returns (in_scope, reason). `reason` is empty when in scope; when
    gated out it names the declared state and the lowest rung's
    thresholds, so the report can say *why* the rule is dormant.

    - activation absent / empty -> baseline:true (back-compat default).
    - {"baseline": true}        -> always in scope.
    - {"rungs": [...]}          -> in scope iff >= 1 rung is active.
    """
    if not activation:
        return True, ""  # missing activation defaults to baseline (back-compat)
    if activation.get("baseline") is True:
        return True, ""
    rungs = activation.get("rungs") or []
    if not rungs:
        # An activation block with neither baseline nor rungs is a
        # malformed standard; fail safe to in-scope rather than silently
        # skip it (matches the missing-activation back-compat default).
        return True, ""
    if any(rung_active(rung, state) for rung in rungs):
        return True, ""
    # Gated out: report the tightest entry threshold across rungs so the
    # human sees the cheapest bar that would activate it.
    cur = (f"{state.get('maturity', '?')}/{state.get('stakes', '?')}")
    lowest = min(
        rungs,
        key=lambda r: (
            _MATURITY_RANK.get(r.get("min_maturity", MATURITY_LADDER[0]),
                               len(MATURITY_LADDER)),
            _STAKES_RANK.get(r.get("min_stakes", STAKES_LADDER[0]),
                             len(STAKES_LADDER)),
        ),
    )
    need = (f"{lowest.get('min_maturity', MATURITY_LADDER[0])}/"
            f"{lowest.get('min_stakes', STAKES_LADDER[0])}")
    name = lowest.get("name", "lowest rung")
    return False, (f"gated out at {cur}: needs >= {need} "
                   f"(rung '{name}'); no rung active at the declared state")
