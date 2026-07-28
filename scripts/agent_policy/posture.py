#!/usr/bin/env python3
"""Operator posture: read it from the host, normalise it, act on it.

Hooks run at step 1 of Claude Code's six-step permission evaluation —
"a hook deny applies even in bypassPermissions mode" — which is *above*
the permission mode applied at step 4. So a layer that never reads
``permission_mode`` cannot help but override an operator who has already
declared they want to be unblocked. That is the mechanism, not a defect
in any individual rule.

Three responsibilities, deliberately separate from the rule set:

1. **Detect** the host's native posture, per host.
2. **Normalise** it onto one stance ladder, so downstream code sees only
   the ladder and two hosts at the same stance behave identically.
3. **Filter** decisions by that stance, subject to the rule that the
   irreversible tier is never dialable.

Kept out of ``policy.py`` on purpose: rule definitions, the evaluation
engine, the posture engine and the per-host projections are four
responsibilities, and this is the one that most easily grows.

**Nothing calls ``filter_decisions`` yet.** This module is inert until
``hook.py`` is taught to detect posture and pass it through. That
wiring is a deliberate later step, so that landing the vocabulary, the
rule registry and their tests changes no behavior and can be reviewed
on its own.

Stdlib-only, like the rest of the package.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from scripts.agent_policy.vocab import Band, PostureSource, Severity, Stance, Tier
except ModuleNotFoundError:  # direct execution — see policy.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.agent_policy.vocab import Band, PostureSource, Severity, Stance, Tier

REPO_ROOT = Path(__file__).resolve().parents[2]

# ``.engineering/`` is this project's cross-agent state home, so the
# operator's declared tuning lives beside the rest of it rather than in
# a fourth dotfile.
DEFAULT_CONFIG_PATH = REPO_ROOT / ".engineering" / "agent-policy.json"

# What the engine assumes when nothing declares otherwise. Deliberately
# STANDARD and not STRICT: an unknown posture falls back to the declared
# stance, never to maximum enforcement. A host-agnostic contract that
# silently hardened on the two hosts that cannot report posture would be
# worse than no contract.
FALLBACK_STANCE = Stance.STANDARD


@dataclass(frozen=True)
class Posture:
    stance: Stance
    source: PostureSource
    #: The host's own word for it, kept verbatim for telemetry.
    raw: str = ""


# --- Host detection --------------------------------------------------------
#
# Only *detection* is host-specific. Everything below the ladder is shared,
# which is where cross-host behavioral identity comes from.

# Claude Code sends `permission_mode` in every hook payload.
_CLAUDE_MODES: dict[str, Stance] = {
    "default": Stance.STANDARD,
    "plan": Stance.STANDARD,
    "acceptEdits": Stance.STANDARD,
    "auto": Stance.RELAXED,
    "dontAsk": Stance.RELAXED,
    "bypassPermissions": Stance.RELAXED,
}

# Codex splits the concept across approval_policy and sandbox_mode.
# Whether either reaches a hook payload is UNCONFIRMED — absent from the
# official docs as of 2026-07-27 — so this map is written to be correct
# if they appear and inert if they never do.
_CODEX_APPROVAL: dict[str, Stance] = {
    "untrusted": Stance.STRICT,
    "on-request": Stance.STANDARD,
    "auto_review": Stance.STANDARD,
    "never": Stance.RELAXED,
}
_CODEX_SANDBOX: dict[str, Stance] = {
    "read-only": Stance.STRICT,
    "workspace-write": Stance.STANDARD,
    "danger-full-access": Stance.RELAXED,
}

# Augment reports nothing. Its hook payload carries tool-name,
# event-type, details and timestamp, and it has no bypass mode at all,
# so `declared` is the best it can ever do. This is not a gap to close
# later; it is a property of the host.


def detect(
    tool: str,
    payload: dict,
    *,
    config_path: Path | None = None,
    config: Config | None = None,
) -> Posture:
    """Resolve the stance in force for one hook invocation.

    Pass an already-loaded ``config`` to avoid re-reading the file: the
    declared stance and the per-rule overrides live in the same file and
    must not be read at two different moments.
    """
    reported = _host_reported(tool, payload)
    if reported is not None:
        stance, raw = reported
        return Posture(stance=stance, source=PostureSource.HOST_REPORTED, raw=raw)
    declared = config.stance if config is not None else load_declared_stance(config_path)
    return Posture(stance=declared, source=PostureSource.DECLARED, raw="")


def _host_reported(tool: str, payload: dict) -> tuple[Stance, str] | None:
    if tool == "claude":
        raw = payload.get("permission_mode") or payload.get("permissionMode") or ""
        if raw and raw in _CLAUDE_MODES:
            return _CLAUDE_MODES[raw], str(raw)
        return None

    if tool == "codex":
        # Strictest of the two wins if both are present — they constrain
        # different things (approval prompts vs filesystem reach) and the
        # operator opted into whichever is tighter.
        candidates: list[tuple[Stance, str]] = []
        approval = payload.get("approval_policy") or payload.get("approvalPolicy")
        if approval in _CODEX_APPROVAL:
            candidates.append((_CODEX_APPROVAL[approval], f"approval_policy={approval}"))
        sandbox = payload.get("sandbox_mode") or payload.get("sandboxMode")
        if sandbox in _CODEX_SANDBOX:
            candidates.append((_CODEX_SANDBOX[sandbox], f"sandbox_mode={sandbox}"))
        if not candidates:
            return None
        return max(candidates, key=lambda pair: _stance_rank(pair[0]))

    # augment, and any host we have not taught yet
    return None


def _stance_rank(stance: Stance) -> int:
    return {Stance.RELAXED: 0, Stance.STANDARD: 1, Stance.STRICT: 2}[stance]


@dataclass(frozen=True)
class Config:
    """The operator's declared tuning. Deliberately not a rule DSL.

    Operator tuning belongs outside ``policy.py``, so adjusting the layer
    stops requiring a code review of the engine. The reason it is safe to
    un-review is that this file cannot define behavior — only re-tier
    rules that already exist:

    - It cannot add a rule, change a matcher, or change a severity.
    - It can only name a rule id the rule set already knows.
    - It cannot move a rule INTO the irreversible tier's exemption:
      ``tier_overrides`` may relax ``irreversible`` → ``recoverable``
      only if the rule set did not declare it irreversible in the first
      place. An irreversible rule stays irreversible, because that is
      the one guarantee no posture and no config may dial.

    Shape::

        {
          "stance": "relaxed",
          "tier_overrides": {"command.require_venv_python": "recoverable"},
          "band_overrides": {"command.require_venv_python": "redundant"}
        }

    A malformed entry is dropped with the rest of the file intact.
    Silently hardening on a config the engine cannot parse is the
    failure mode to avoid, so every parse failure resolves downward.
    """

    stance: Stance = FALLBACK_STANCE
    tier_overrides: dict[str, Tier] = field(default_factory=dict)
    band_overrides: dict[str, Band] = field(default_factory=dict)


def load_config(config_path: Path | None = None) -> Config:
    """Read the declared config, falling back safely on anything odd."""
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return Config()
    if not isinstance(data, dict):
        return Config()

    raw_stance = data.get("stance")
    stance = Stance(raw_stance) if _is_member(raw_stance, Stance) else FALLBACK_STANCE

    return Config(
        stance=stance,
        tier_overrides=_coerce_map(data.get("tier_overrides"), Tier),
        band_overrides=_coerce_map(data.get("band_overrides"), Band),
    )


def _is_member(value, enum_cls) -> bool:
    return isinstance(value, str) and value in tuple(enum_cls)


def _coerce_map(raw, enum_cls) -> dict:
    if not isinstance(raw, dict):
        return {}
    return {
        key: enum_cls(value)
        for key, value in raw.items()
        if isinstance(key, str) and _is_member(value, enum_cls)
    }


def effective_tier(rule, config: Config) -> Tier:
    """The rule's tier after config, with the irreversible floor applied.

    A rule the rule set declares irreversible cannot be talked out of it.
    That is the whole content of the second axis: if config could relax
    it, ``rm -rf`` would be one JSON edit away from being silent under
    ``bypassPermissions``, and the layer would be back to having a
    single dial.
    """
    if rule.tier is Tier.IRREVERSIBLE:
        return Tier.IRREVERSIBLE
    return config.tier_overrides.get(rule.id, rule.tier)


def effective_band(rule, config: Config) -> Band:
    return config.band_overrides.get(rule.id, rule.band)


def load_declared_stance(config_path: Path | None = None) -> Stance:
    """Read the operator's declared stance, or fall back to STANDARD.

    Missing file, unreadable file, malformed JSON and unknown stance all
    resolve to ``FALLBACK_STANCE``. A config the engine cannot parse
    must not silently harden enforcement.
    """
    return load_config(config_path).stance


# --- Filtering -------------------------------------------------------------


def filter_decisions(decisions, posture: Posture, *, rules_by_id: dict, config: Config | None = None):
    """Split decisions into (kept, suppressed) for the stance in force.

    Returns ``[]`` for a suppressed decision — never ``allow``, never
    ``warn``. Both of those render as an affirmative host allow through
    ``hook._DECISION_TO_PERMISSION``, which would pre-empt the
    operator's own permission rules rather than deferring to them.
    Suppression means silence.

    The irreversible tier is not dialable. No stance reduces it below a
    grantable ask, so ``rm -rf`` still gates under
    ``bypassPermissions`` — which is the whole point of the second axis.

    Suppressed decisions are returned rather than dropped so the caller
    can still record them. Silently dropping would make a rule the
    operator's posture quiets read, in the friction log, as a rule
    nobody trips.
    """
    if posture.stance is not Stance.RELAXED:
        return list(decisions), []

    settings = config if config is not None else Config()
    kept, suppressed = [], []
    for decision in decisions:
        rule = rules_by_id.get(decision.rule_id)
        if rule is None or not is_dialable(rule, settings):
            # Unknown rule id fails CLOSED — an id the rule set does not
            # know is not something to quiet on the operator's behalf.
            kept.append(decision)
        else:
            suppressed.append(decision)
    return kept, suppressed


def is_dialable(rule, config: Config | None = None) -> bool:
    """May posture quiet this rule? Both axes have to say yes.

    The 2x2 has four cells and only ONE of them is dialable::

        ..                  | Covered elsewhere | Nothing else can hold it
        ------------------- | ----------------- | ------------------------
        **Recoverable**     | **dialable**      | keep, cheap static rule
        **Irreversible**    | keep anyway       | keep, strongest rung

    Tier alone is not enough, and getting this wrong is quiet. A band-C
    rule is host-*inexpressible*: suppressing it under RELAXED does not
    hand enforcement back to the host, because the host never had it.
    Nothing gates the action at all.

    So a rule yields to posture only when something else can actually
    take over: recoverable damage AND real coverage elsewhere.
    """
    settings = config if config is not None else Config()
    if effective_tier(rule, settings) is Tier.IRREVERSIBLE:
        return False
    # LINT_COVERED yields for the same reason REDUNDANT does — something
    # else enforces it. The layer is a repo lint rather than the host, but
    # the operator's bargain is identical: go quiet here, stay caught there.
    return effective_band(rule, settings) in (
        Band.REDUNDANT,
        Band.PARTIAL,
        Band.LINT_COVERED,
    )


def floor_for_tier(severity: str, tier: Tier) -> str:
    """Clamp an irreversible rule to the grantable band.

    Never below ``ask`` (there must be a gate) and never above ``block``
    (there must be a path forward — the grant mechanism). Recoverable
    rules are returned untouched.
    """
    if tier is not Tier.IRREVERSIBLE:
        return severity
    if severity in (Severity.ALLOW, Severity.WARN):
        return str(Severity.ASK)
    return severity
