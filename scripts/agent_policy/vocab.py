#!/usr/bin/env python3
"""Closed vocabularies for the agent-policy engine.

Posture, stance, tier, band and scan basis are five pieces of state that
would otherwise be bare string literals compared by ``==`` all over the
package — the stringly-typed-state smell this repo's own
``no-stringly-typed-status`` lint exists to catch.

That lint is scoped to host application code, not to ``scripts/``, and
this package is deliberately stdlib-only so it runs before a virtualenv
exists — so the Django ``TextChoices`` mechanism ADR 0001 names is
unavailable here. ``enum.StrEnum`` is the stdlib replacement.

``StrEnum`` members compare equal to their string values, so existing
call sites and the JSONL friction log keep working unchanged while new
code gets a closed set.

Provenance: this vocabulary was authored in a host project (host-a) and
ported here. The mechanism is portable; the rule set that uses it is
not, so ``rules.py`` re-derives every band and tier against *this*
repo's hosts and lints rather than copying the originating project's.
"""
from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    """What a rule asks the host to do. Ordered by ``DECISION_ORDER``."""

    ALLOW = "allow"
    WARN = "warn"
    ASK = "ask"
    BLOCK = "block"


# Kept as a module-level map rather than a method so the existing
# ``DECISION_ORDER`` import in policy.py keeps resolving to the same object.
DECISION_ORDER: dict[str, int] = {
    Severity.ALLOW: 0,
    Severity.WARN: 1,
    Severity.ASK: 2,
    Severity.BLOCK: 3,
}


class Tier(StrEnum):
    """Whether the damage a rule guards against can be undone.

    This is the axis that survives host coverage. A recoverable rule may
    yield to operator posture; an irreversible one may not, and no
    stance and no config entry may reduce it below a grantable ask.

    The test for the tier is narrow and mechanical: *after* the command
    runs, is there a command that puts the state back? A reflog entry, a
    reinstall, a second chmod, a backwards migration all count. "The
    user could retype it" does not.
    """

    RECOVERABLE = "recoverable"
    IRREVERSIBLE = "irreversible"


class Band(StrEnum):
    """How much of this rule some *other* enforcement layer already covers.

    Required on every rule, so "a rule with no declared gap
    justification" fails by type rather than by review.

    Three of the four bands measure the **host's** permission system —
    and because the hosts are the same three products everywhere, those
    three bands port between projects essentially unchanged. The fourth
    measures the *project's own* diff-scoped lints and is therefore
    strictly local: a rule that is ``LINT_COVERED`` in one repo is a
    genuine gap in a repo that never wrote the lint.

    A lint is the better home whenever the subject is committed code
    rather than a command: it sees the whole file, runs on the final
    state rather than mid-edit, batches instead of interrupting, and
    carries an allow-list marker. Prefer it, and reach for a hook rule
    only when the thing being judged never reaches a commit.
    """

    REDUNDANT = "redundant"          # band A — fully expressible natively
    PARTIAL = "partial"              # band B — host covers part of it
    GENUINE_GAP = "genuine_gap"      # band C — structurally inexpressible
    LINT_COVERED = "lint_covered"    # band D — a repo lint already enforces it


class ScanBasis(StrEnum):
    """Which form of the command a rule's matcher reads.

    ``STRIPPED`` runs against ``policy._strip_quoted`` output, which
    blanks quoted spans so documentation text and commit messages don't
    trip command detectors. ``RAW`` runs against the command as typed.

    RAW exists because a rule can need to see *inside* the quotes — a
    database-destruction rule has to read ``mysql -e "DROP DATABASE x"``.
    It is per-rule rather than global: changing the shared basis would
    make every widened matcher fire on quoted prose. No rule in this
    repo's set needs it yet; the word is here so that adding such a rule
    is a one-field change rather than a change to the scan engine.
    """

    STRIPPED = "stripped"
    RAW = "raw"


class Stance(StrEnum):
    """Normalised operator posture. Ladder: STRICT > STANDARD > RELAXED.

    Each host reports posture differently — or, in Augment's case, not
    at all. Adapters map their native concept onto this ladder and
    everything downstream sees only the ladder, which is where
    cross-host behavioral identity comes from.
    """

    STRICT = "strict"
    STANDARD = "standard"
    RELAXED = "relaxed"


STANCE_ORDER: dict[str, int] = {
    Stance.RELAXED: 0,
    Stance.STANDARD: 1,
    Stance.STRICT: 2,
}


class PostureSource(StrEnum):
    """Where the stance in force came from.

    Three absences must stay distinguishable and must never collapse
    into one sentinel:

    - ``HOST_REPORTED`` — the payload carried it (Claude's
      ``permission_mode``).
    - ``DECLARED`` — the host reported nothing and the configured stance
      was used. Augment can never do better than this.
    - ``CLI_ORIGIN`` — no hook payload existed at all; the event came
      from ``grant.py`` or ``friction.py report`` running in a shell.
    - ``PRE_INSTRUMENTATION`` — read-side only. Events written before
      the posture field existed carry no value; readers synthesise this
      rather than defaulting to a stance.
    """

    HOST_REPORTED = "host_reported"
    DECLARED = "declared"
    CLI_ORIGIN = "cli_origin"
    PRE_INSTRUMENTATION = "pre_instrumentation"
