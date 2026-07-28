#!/usr/bin/env python3
"""The canonical rule set.

Before this module, the rules lived as regex literals inline in
``policy.evaluate_command`` and as ``_looks_like_*`` predicates in
``policy.scan_patch``. That is enough to *evaluate* a rule and not
enough to *reason* about one: there was nowhere to record whether the
damage a rule guards against can be undone, whether some other layer
already covers it, or how it would be spelled if the host enforced it
instead. Every one of those questions had to be re-derived from scratch
each time someone asked "should this rule still exist?".

This module is a Python module of frozen dataclasses, not a parsed DSL.
A Python literal lets the engine import *the* rules rather than a copy,
so there is no serialization boundary for two representations to drift
across.

Every rule declares:

- ``tier``   — recoverable or irreversible. Posture may dial the first,
               never the second.
- ``band``   — how much some other layer already covers. Required, so an
               unjustified rule fails by type rather than by review.
- ``scan_basis`` — which form of the command the matcher reads.
- ``projections`` — per-host spelling, or an explicit ``INEXPRESSIBLE``
               carrying the reason. This repo ships no generated host
               permission artifacts yet, so today these are the
               *evidence* for each band claim: a rule cannot be called
               ``REDUNDANT`` without someone writing down the native
               rule that makes it redundant.
- ``fixtures`` — commands that must and must not match, asserted by the
               test suite.

Matchers come in two shapes. Command rules carry a regex. Patch and Stop
rules carry ``pattern=None`` because their matcher is code — a
line-by-line scan of a diff, or a Stop-event check against the test log.
They still carry full metadata, because every residual rule should have
to state which 2x2 cell earns it.

**Behavior is unchanged by this module.** Rule ids, severities, reason
strings, matcher patterns, group order and the destructive group's
first-match-only break are all reproduced exactly as
``evaluate_command`` had them inline. No rule is retired, no matcher is
widened, and nothing reads ``tier`` or ``band`` at runtime yet — they
are declarations awaiting the posture wiring.

Provenance: the two-axis model (tier x band), the projection type and
the retirement machinery were authored in a host project (host-a) and
ported here. The *rules* are this repo's own, and the bands and tiers
below were re-derived against this repo's hosts and lints. Where that
re-derivation disagrees with the originating project's copy, the
disagreement is noted at the rule.

Stdlib-only, like the rest of the package.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from scripts.agent_policy.vocab import Band, ScanBasis, Severity, Tier
except ModuleNotFoundError:  # direct execution — see policy.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.agent_policy.vocab import Band, ScanBasis, Severity, Tier

# ---------------------------------------------------------------------------
# Per-host projection
# ---------------------------------------------------------------------------

HOSTS = ("claude", "codex", "augment")


@dataclass(frozen=True)
class Projection:
    """How one rule is spelled on one host, or why it cannot be.

    ``verb`` is the host-native decision word. ``why`` is set only on an
    inexpressible projection, and is meant to be emitted verbatim into
    any generated artifact so the divergence rationale travels with the
    file rather than living in a doc that can go stale.
    """

    verb: str | None = None
    spelling: str | None = None
    why: str | None = None
    overmatches: str | None = None
    #: Additional spellings for hosts whose rule form has no alternation.
    #: A Codex ``prefix_rule`` matches one argv prefix, so a rule covering
    #: pip AND npm AND uv needs three of them. Regex hosts fold them into
    #: the alternation instead.
    also: tuple[str, ...] = ()

    @property
    def all_spellings(self) -> tuple[str, ...]:
        return (self.spelling, *self.also) if self.spelling else ()

    @property
    def expressible(self) -> bool:
        """True when this projects to a concrete rule in the artifact."""
        return self.why is None

    @property
    def covered_by_default(self) -> bool:
        """True when the correct artifact entry is *no entry*."""
        return self.verb == NATIVE_DEFAULT_VERB


def INEXPRESSIBLE(why: str) -> Projection:
    return Projection(why=why)


NATIVE_DEFAULT_VERB = "native_default"


def NATIVE_DEFAULT(why: str) -> Projection:
    """No artifact entry — the host's own default already does this.

    A third state, distinct from both a spelling and a capability gap.

    A recoverable band-A rule must NOT become a native ``ask``: explicit
    ask rules sit at step 3 of Claude Code's evaluation, above the
    permission mode at step 4, so they survive ``bypassPermissions`` and
    would reproduce the prompt in exactly the mode an operator entered
    to stop being prompted. A native ``deny`` is worse still — it
    relocates the block rather than removing it.

    What these rules want is *nothing at all*: with no entry, Claude Code
    prompts for the command in ``default`` mode and allows it under
    ``bypassPermissions``. That is precisely the intended behavior on
    both axes, and it costs zero lines of artifact.
    """
    return Projection(verb=NATIVE_DEFAULT_VERB, why=why)


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    tier: Tier
    band: Band
    reason: str
    # Why this rule earns its place in the 2x2.
    justification: str
    pattern: str | None = None
    scan_basis: ScanBasis = ScanBasis.STRIPPED
    projections: dict[str, Projection] = field(default_factory=dict)
    # (command, should_match) pairs, asserted by the test suite.
    fixtures: tuple[tuple[str, bool], ...] = ()
    # Set to the disposition rationale when the rule no longer evaluates.
    # A retired rule is NOT deleted: it stays in ``ALL_RULES`` so its
    # projections survive, and so the reason it left the hook is readable
    # at the point of the decision rather than only in a commit message.
    # It is absent from ``COMMAND_GROUPS``, which is what makes it inert.
    retired: str | None = None
    # Set when ``band is Band.LINT_COVERED``: the pre-commit hook id that
    # holds this constraint instead. Named rather than implied so the
    # claim is checkable — a test asserts the id exists in
    # ``.pre-commit-config.yaml``, which is what stops "a lint covers it"
    # from decaying into folklore after the lint is renamed or dropped.
    covering_lint: str | None = None
    # Free-text note about a matcher the rule set knows to be incomplete.
    # Recorded rather than silently fixed, because widening a matcher is
    # a behavior change and belongs in its own commit.
    known_gap: str | None = None

    @property
    def active(self) -> bool:
        return self.retired is None

    def matches(self, scan_text: str) -> bool:
        if self.pattern is None:
            return False
        return bool(re.search(self.pattern, scan_text))


@dataclass(frozen=True)
class RuleGroup:
    """An ordered group of rules sharing an evaluation policy.

    ``first_match_only`` reproduces the ``break`` in the original
    destructive loop: at most one destructive rule is ever reported for
    a command, in declaration order. The ask group has no such break and
    reports every match. Both behaviors are observable — they decide
    which rule id a compound command reports — so both are pinned by
    tests.
    """

    name: str
    rules: tuple[Rule, ...]
    first_match_only: bool = False


# ---------------------------------------------------------------------------
# Shared matcher fragments
# ---------------------------------------------------------------------------

# Start-of-string or a shell separator. This is the lead every command
# rule below uses, reproduced from the inline patterns verbatim.
#
# It is worth naming what it does NOT match, because one rule depends on
# the gap: a command with a *wrapper* in front of it — ``sudo rm -rf``,
# ``xargs rm -rf``, ``time rm -rf``, ``find . -exec rm -rf {} +`` — does
# not match, because the wrapper token sits between the separator and
# the command. See ``SUDO`` for what currently backstops that.
_SEPARATOR_LEAD = r"(^|[;&|]\s*)"


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

_PATH_BASED_HOST = (
    "Host permission rules match on tool name and path only; they cannot "
    "inspect the content of a write."
)
_NO_STOP_ANALOG = "No host exposes a Stop-event permission surface."

_DESTRUCTIVE_REASON = (
    "Destructive command blocked by agent policy; ask the user for an explicit path."
)
_ASK_REASON = "This command crosses a higher-risk boundary and should be user-approved."


REQUIRE_VENV_PYTHON = Rule(
    id="command.require_venv_python",
    severity=Severity.BLOCK,
    tier=Tier.RECOVERABLE,
    band=Band.GENUINE_GAP,
    reason="Use `.venv/bin/python`, not bare `python` or `python3`, for project commands.",
    justification=(
        "Recoverable — running the wrong interpreter produces an import error, not "
        "damage — but host-inexpressible: no host can express 'python manage.py is "
        "denied but .venv/bin/python manage.py is allowed', because command rules "
        "are wildcard/prefix matchers with no negative condition."
    ),
    pattern=r"(^|[;&|]\s*)(python|python3)\s+(manage\.py|-m\s+pytest)\b",
    projections={
        "claude": INEXPRESSIBLE(
            "Bash rules are wildcard-only; 'deny python manage.py EXCEPT "
            ".venv/bin/python manage.py' has no negative form."
        ),
        "codex": INEXPRESSIBLE("prefix_rule anchors at argv[0]; same negative-condition gap."),
        "augment": INEXPRESSIBLE("shellInputRegex is a flat deny list; same gap."),
    },
    fixtures=(
        ("python manage.py test", True),
        ("python3 -m pytest tests/", True),
        (".venv/bin/python manage.py test", False),
        (".venv/bin/python -m pytest tests/", False),
    ),
)

DESTRUCTIVE_RM = Rule(
    id="command.destructive_rm",
    severity=Severity.BLOCK,
    tier=Tier.IRREVERSIBLE,
    band=Band.PARTIAL,
    reason=_DESTRUCTIVE_REASON,
    justification=(
        "Irreversible, and the host only half-covers it: Claude Code circuit-breaks "
        "`rm -rf /` and `~` only; every other path is unguarded natively. "
        "Irreversibility overrides host coverage — this is the 2x2 cell where a rule "
        "is kept despite partial redundancy. The loudest rule in this repo's friction "
        "log (77 of 194 events), which is an argument for narrowing the *grant* path, "
        "not for retiring the rule."
    ),
    pattern=_SEPARATOR_LEAD + r"rm\s+-[A-Za-z]*r[A-Za-z]*f\b",
    known_gap=(
        "Narrower than it looks, in two independent ways, and the fixtures below "
        "are written to record both rather than to flatter the pattern.\n"
        "\n"
        "(1) The flag run must be one token, lowercase, with `r` before `f` AND `f` "
        "last: the character class is case-sensitive and the trailing `\\b` fails "
        "against any letter after `f`. So `rm -rf` matches while `rm -fr`, "
        "`rm -rfv`, `rm -Rf`, `rm -r -f` and `rm --recursive --force` do not.\n"
        "\n"
        "(2) The lead anchor requires `rm` at the start of a command or right after "
        "a shell separator, so every wrapped form escapes: `sudo rm -rf`, "
        "`xargs rm -rf`, `time rm -rf`, `find . -exec rm -rf {} +`. Of those, only "
        "the `sudo` spelling is caught at all, and only incidentally, by "
        "`command.sudo`.\n"
        "\n"
        "Widening this is a coverage change on an irreversible rule and belongs in "
        "its own commit — it can only add gates, never remove one, but it will "
        "change which id a compound command reports."
    ),
    projections={
        "claude": Projection(
            verb="deny", spelling="Bash(rm:*)", overmatches="all rm, not just -rf"
        ),
        "codex": Projection(
            verb="forbidden",
            spelling='["rm", "-rf"]',
            overmatches="prefix-anchored; misses `xargs rm -rf`",
        ),
        "augment": Projection(
            verb="deny", spelling="^rm -rf", overmatches="prefix-anchored; same miss"
        ),
    },
    fixtures=(
        ("rm -rf /tmp/x", True),
        ("echo hi && rm -rf /tmp/x", True),
        ("rm -rf ~", True),
        ("rm file.txt", False),
        ("rm -v file", False),
        ("rm -r nodir", False),
        # The known_gap, as executable examples. Every one of these deletes a
        # tree irrecoverably and none of them is gated. They are `False` here
        # because that is the truth today, and they are here at all so that
        # widening the matcher flips a visible assertion rather than quietly
        # changing behavior nobody had written down.
        ("rm -fr /tmp/x", False),
        ("rm -rfv /tmp/x", False),
        ("rm -Rf /tmp/x", False),
        ("rm -r -f /tmp/x", False),
        ("rm --recursive --force /tmp/x", False),
        ("xargs rm -rf", False),
        ("find . -exec rm -rf {} +", False),
    ),
)

GIT_RESET_HARD = Rule(
    id="command.git_reset_hard",
    severity=Severity.BLOCK,
    tier=Tier.IRREVERSIBLE,
    band=Band.REDUNDANT,
    reason=_DESTRUCTIVE_REASON,
    justification=(
        "Natively expressible as an exact prefix, so band A. Irreversible on the "
        "second axis, which is where this re-derivation departs from the "
        "originating project's copy: "
        "the reflog recovers the *commit* the reset moved away from, and nothing "
        "recovers the uncommitted working-tree changes it discards on the way. "
        "Band A + irreversible is the `keep anyway` cell — retiring it to a native "
        "`deny` is still correct (a deny sits at step 2, above the permission mode "
        "at step 4, so it survives bypassPermissions), but retiring it to `no entry` "
        "would not be."
    ),
    pattern=_SEPARATOR_LEAD + r"git\s+reset\s+--hard\b",
    projections={
        "claude": Projection(verb="deny", spelling="Bash(git reset --hard:*)"),
        "codex": Projection(verb="forbidden", spelling='["git", "reset", "--hard"]'),
        "augment": Projection(verb="deny", spelling="^git reset --hard"),
    },
    fixtures=(("git reset --hard HEAD~1", True), ("git reset HEAD~1", False)),
)

GIT_CLEAN_FORCE = Rule(
    id="command.git_clean_force",
    severity=Severity.BLOCK,
    tier=Tier.IRREVERSIBLE,
    band=Band.REDUNDANT,
    reason=_DESTRUCTIVE_REASON,
    justification=(
        "Natively expressible. Irreversible for the same reason as git_reset_hard "
        "and more plainly: untracked files have never been in the object store, so "
        "there is nothing to recover them from. Band A + irreversible — keep, or "
        "retire only to a native `deny`."
    ),
    pattern=_SEPARATOR_LEAD + r"git\s+clean\s+-[A-Za-z]*f\b",
    known_gap=(
        "`-f` must be the last letter of the flag run, so `git clean -fd` — the "
        "spelling that also removes directories, i.e. the worse one — does not "
        "match. The native projection `deny Bash(git clean:*)` has no such hole."
    ),
    projections={
        "claude": Projection(verb="deny", spelling="Bash(git clean:*)"),
        "codex": Projection(verb="forbidden", spelling='["git", "clean"]'),
        "augment": Projection(verb="deny", spelling="^git clean"),
    },
    fixtures=(("git clean -f .venv", True), ("git clean -n", False)),
)

SUDO = Rule(
    id="command.sudo",
    severity=Severity.BLOCK,
    tier=Tier.RECOVERABLE,
    band=Band.REDUNDANT,
    reason=_DESTRUCTIVE_REASON,
    justification=(
        "The tier describes privilege escalation itself, which changes nothing on "
        "its own; whatever follows is judged by its own rule. Natively expressible "
        "as `deny Bash(sudo:*)`, so band A, and on both axes this reads as a "
        "retirement candidate. It is NOT one yet, and the reason is not about sudo: "
        "`destructive_rm`'s lead anchor rejects any token before `rm`, so this rule "
        "is currently the only thing in the set that matches `sudo rm -rf /`. "
        "Retiring it before that matcher is widened would open a hole in an "
        "irreversible rule. Second-noisiest in the friction log (26 of 194)."
    ),
    pattern=_SEPARATOR_LEAD + r"sudo\b",
    projections={
        "claude": Projection(verb="deny", spelling="Bash(sudo:*)"),
        "codex": Projection(verb="forbidden", spelling='["sudo"]'),
        "augment": Projection(verb="deny", spelling="^sudo"),
    },
    fixtures=(("sudo ls", True), ("sudo rm -rf /", True), ("ls", False)),
)

CHMOD_777 = Rule(
    id="command.chmod_777",
    severity=Severity.BLOCK,
    tier=Tier.RECOVERABLE,
    band=Band.REDUNDANT,
    reason=_DESTRUCTIVE_REASON,
    justification=(
        "Recoverable with a second chmod, and natively expressible as an exact "
        "prefix. The clean band-A/recoverable cell — the one cell posture may dial."
    ),
    pattern=_SEPARATOR_LEAD + r"chmod\s+777\b",
    projections={
        "claude": Projection(verb="deny", spelling="Bash(chmod 777:*)"),
        "codex": Projection(verb="forbidden", spelling='["chmod", "777"]'),
        "augment": Projection(verb="deny", spelling="^chmod 777"),
    },
    fixtures=(("chmod 777 /etc/passwd", True), ("chmod 644 f", False)),
)

GIT_PUSH = Rule(
    id="command.git_push",
    severity=Severity.ASK,
    tier=Tier.RECOVERABLE,
    band=Band.REDUNDANT,
    reason=_ASK_REASON,
    justification=(
        "Recoverable (a push is revertible; a force-push is a different command "
        "with a different flag) and natively expressible. Band A + recoverable, and "
        "the second-loudest rule in the friction log at 67 of 194 events — the "
        "clearest candidate in the set for moving to the operator's own permission "
        "rules, which they can edit without a code review of this package."
    ),
    pattern=_SEPARATOR_LEAD + r"git\s+push\b",
    projections={
        "claude": NATIVE_DEFAULT(
            "Recoverable, so a native ask would sit at step 3 and survive "
            "bypassPermissions, reproducing the prompt in the exact mode the "
            "operator entered to stop being prompted. With no entry, Claude prompts "
            "in default mode and allows under bypass."
        ),
        "codex": Projection(verb="prompt", spelling='["git", "push"]'),
        "augment": Projection(verb="deny", spelling="^git push"),
    },
    fixtures=(("git push origin main", True), ("git pull", False)),
)

GIT_CHECKOUT_DASHDASH = Rule(
    id="command.git_checkout_dashdash",
    severity=Severity.ASK,
    tier=Tier.IRREVERSIBLE,
    band=Band.REDUNDANT,
    reason=_ASK_REASON,
    justification=(
        "Discards uncommitted edits to the named paths with no undo — irreversible, "
        "the third place this re-derivation departs from the originating project's "
        "copy. Natively "
        "expressible as an exact prefix, so band A. Already an `ask` rather than a "
        "`block`, which is the right severity for an irreversible-but-often-intended "
        "action: gate it, don't forbid it."
    ),
    pattern=_SEPARATOR_LEAD + r"git\s+checkout\s+--\s+",
    projections={
        "claude": Projection(verb="ask", spelling="Bash(git checkout --:*)"),
        "codex": Projection(verb="prompt", spelling='["git", "checkout", "--"]'),
        "augment": Projection(verb="deny", spelling="^git checkout --"),
    },
    fixtures=(("git checkout -- foo.py", True), ("git checkout main", False)),
)

DJANGO_MIGRATION = Rule(
    id="command.django_migration",
    severity=Severity.ASK,
    tier=Tier.RECOVERABLE,
    band=Band.PARTIAL,
    reason=_ASK_REASON,
    justification=(
        "Recoverable on a development database by a backwards migration. Only "
        "half-expressible: a host can prompt on the `manage.py migrate` prefix, but "
        "the `--dry-run` / `--check` exemption is a negative condition no host has a "
        "form for, so the native version over-asks. This rule is inert in this repo "
        "— there is no manage.py here — and ships as part of the portable set for "
        "host projects that are Django."
    ),
    pattern=r"manage\.py\s+(migrate|makemigrations)\b(?!.*--(?:dry-run|check)\b)",
    projections={
        "claude": INEXPRESSIBLE(
            "Bash rules are wildcard-only; the --dry-run exemption is a negative "
            "condition with no wildcard form. An over-broad ask would also survive "
            "bypassPermissions."
        ),
        "codex": Projection(
            verb="prompt",
            spelling='[".venv/bin/python", "manage.py", "migrate"]',
            also=('[".venv/bin/python", "manage.py", "makemigrations"]',),
            overmatches="misses the --dry-run exemption and non-.venv spellings",
        ),
        "augment": INEXPRESSIBLE(
            "shellInputRegex is a flat deny list with no negative condition, so the "
            "--dry-run / --check exemption cannot be expressed."
        ),
    },
    fixtures=(
        (".venv/bin/python manage.py migrate", True),
        (".venv/bin/python manage.py makemigrations", True),
        (".venv/bin/python manage.py migrate --dry-run --check", False),
        (".venv/bin/python manage.py makemigrations --dry-run", False),
    ),
)

PACKAGE_INSTALL = Rule(
    id="command.package_install",
    severity=Severity.ASK,
    tier=Tier.RECOVERABLE,
    band=Band.REDUNDANT,
    reason=_ASK_REASON,
    justification=(
        "Recoverable by uninstalling, and natively expressible — though only as one "
        "entry per package manager, since no host has an alternation form. Band A + "
        "recoverable. 24 of 194 friction events."
    ),
    pattern=(
        r"(^|[;&|]\s*)((pip|pip3|uv\s+pip|poetry|npm|pnpm|yarn)\s+"
        r"(install|add|update|upgrade|sync|ci)\b)"
    ),
    projections={
        "claude": NATIVE_DEFAULT(
            "Recoverable, and a native rule would need one entry per package "
            "manager. No entry gives the right behavior in both permission modes."
        ),
        "codex": Projection(
            verb="prompt",
            spelling='["pip", "install"]',
            also=('["pip3", "install"]', '["npm", "install"]', '["uv", "pip", "install"]'),
        ),
        "augment": Projection(verb="deny", spelling="^(pip|pip3|npm|uv) install"),
    },
    fixtures=(
        ("pip install requests", True),
        ("npm install", True),
        ("uv pip install ruff", True),
        # `_strip_quoted` blanks the grep query before the matcher sees it.
        ('grep -E "command|pip install" docs/setup.md', False),
    ),
)

LIVE_INTEGRATION = Rule(
    id="command.live_integration",
    severity=Severity.ASK,
    tier=Tier.RECOVERABLE,
    band=Band.GENUINE_GAP,
    reason=_ASK_REASON,
    justification=(
        "Recoverable but host-inexpressible: the trigger is a flag or an env var "
        "anywhere in the command line, not a command prefix, and every host's "
        "command grammar is prefix- or start-anchored."
    ),
    pattern=r"(--run-live|RUN_LIVE_INTEGRATION=1)",
    projections={
        "claude": INEXPRESSIBLE("matches a mid-command flag; Bash rules are prefix-wildcard."),
        "codex": INEXPRESSIBLE("prefix_rule anchors at argv[0]."),
        "augment": INEXPRESSIBLE("shellInputRegex is anchored at the start of the command."),
    },
    fixtures=(
        (".venv/bin/python -m pytest --run-live", True),
        ("RUN_LIVE_INTEGRATION=1 pytest tests/", True),
        (".venv/bin/python -m pytest", False),
    ),
)


# --- Patch rules -----------------------------------------------------------
#
# These three are declared here but their matchers are the
# ``policy._looks_like_*`` predicates, which are the documented
# extension surface for host projects and return False by default. They
# are metadata-complete and inert, which is the honest state: the
# constraint each names is real, and nothing in this repo enforces it
# until a host project fills the predicate in.

PATCH_ISOLATED_RUNTIME_DIRECT_PROVIDER = Rule(
    id="patch.isolated_runtime_direct_provider",
    severity=Severity.BLOCK,
    tier=Tier.RECOVERABLE,
    band=Band.GENUINE_GAP,
    reason="Isolated runtime model calls must go through the canonical AI runtime facade.",
    justification=(
        "Recoverable — it is an edit, and edits revert — but inexpressible to any "
        "host, because the decision depends on which *lines* a write puts into a "
        "file and host permission rules see only tool name and path. A host project "
        "that owns such a boundary should consider whether a diff-scoped AST lint is "
        "the better home (band `lint_covered`), since a lint sees the whole file, "
        "runs on the committed state rather than mid-edit, and batches instead of "
        "interrupting."
    ),
    pattern=None,  # predicate: policy._looks_like_direct_provider
    projections={host: INEXPRESSIBLE(_PATH_BASED_HOST) for host in HOSTS},
)

PATCH_ARTIFACT_ONLY_PRODUCTION_WRITE = Rule(
    id="patch.artifact_only_production_write",
    severity=Severity.BLOCK,
    tier=Tier.RECOVERABLE,
    band=Band.GENUINE_GAP,
    reason="Artifact-only packages must not write production rows or dispatch background tasks.",
    justification="Content inspection; see patch.isolated_runtime_direct_provider.",
    pattern=None,  # predicate: policy._looks_like_production_write
    projections={host: INEXPRESSIBLE(_PATH_BASED_HOST) for host in HOSTS},
)

PATCH_PROMPT_TRUTH_LEAK = Rule(
    id="patch.prompt_truth_leak",
    severity=Severity.BLOCK,
    tier=Tier.RECOVERABLE,
    band=Band.GENUINE_GAP,
    reason="Resolver/planner prompts must not include scorer-only truth or holdout values.",
    justification=(
        "Content inspection, and the one patch rule that stays a hook rule rather "
        "than becoming a lint even in a project that writes the lint: it judges "
        "prompt *text*, which no AST reads. Benchmark-validity-critical — a leak "
        "silently invalidates evaluation results rather than breaking anything."
    ),
    pattern=None,  # predicate: policy._looks_like_prompt_truth_leak
    projections={host: INEXPRESSIBLE(_PATH_BASED_HOST) for host in HOSTS},
)


# --- Stop rules ------------------------------------------------------------

STOP_REQUIRE_VERIFICATION_NOTE = Rule(
    id="stop.require_verification_note",
    severity=Severity.BLOCK,
    tier=Tier.RECOVERABLE,
    band=Band.GENUINE_GAP,
    reason=(
        "Sensitive files changed. Run relevant tests or state what was not run and "
        "why before finishing."
    ),
    justification=(
        "Structurally impossible to express natively: no host has a Stop-event "
        "permission surface at all, so this rule has no host analog to be redundant "
        "with. Recoverable — the worst case is finishing a turn without a "
        "verification note."
    ),
    pattern=None,  # matcher: policy.evaluate_stop
    known_gap=(
        "Effectively dead as wired. `hook.py` passes `payload.get(\"changed_files\") "
        "or _changed_files_from_conversation(payload)`, and that helper returns `[]` "
        "when the payload has no `conversation` key — so the argument is `[]`, not "
        "`None`, and `evaluate_stop`'s git fallback (which only runs when "
        "`changed_files is None`) is unreachable. The rule can therefore only fire "
        "on a `changed_files` key no host actually sends, and the friction log "
        "records zero Stop events. Deliberately not repaired here: repairing it "
        "would switch on a non-dialable end-of-turn blocker, which is a behavior "
        "change and needs its own decision, not a drive-by fix."
    ),
    projections={host: INEXPRESSIBLE(_NO_STOP_ANALOG) for host in HOSTS},
)


# ---------------------------------------------------------------------------
# Evaluation order
# ---------------------------------------------------------------------------

# Group order and within-group order are both observable — they decide
# which rule id a compound command reports. Both are pinned by tests.
#
# Reproduced exactly from the inline dict literals in the original
# ``evaluate_command``: the venv check first, then the destructive dict
# with its trailing ``break``, then the ask dict with none.
COMMAND_GROUPS: tuple[RuleGroup, ...] = (
    RuleGroup("venv", (REQUIRE_VENV_PYTHON,)),
    RuleGroup(
        "destructive",
        (DESTRUCTIVE_RM, GIT_RESET_HARD, GIT_CLEAN_FORCE, SUDO, CHMOD_777),
        first_match_only=True,
    ),
    RuleGroup(
        "ask",
        (
            GIT_PUSH,
            GIT_CHECKOUT_DASHDASH,
            DJANGO_MIGRATION,
            PACKAGE_INSTALL,
            LIVE_INTEGRATION,
        ),
    ),
)

PATCH_RULES: tuple[Rule, ...] = (
    PATCH_ISOLATED_RUNTIME_DIRECT_PROVIDER,
    PATCH_ARTIFACT_ONLY_PRODUCTION_WRITE,
    PATCH_PROMPT_TRUTH_LEAK,
)

STOP_RULES: tuple[Rule, ...] = (STOP_REQUIRE_VERIFICATION_NOTE,)

# Every rule the project has ever declared, retired or not.
ALL_RULES: tuple[Rule, ...] = (
    tuple(rule for group in COMMAND_GROUPS for rule in group.rules)
    + PATCH_RULES
    + STOP_RULES
)

# Derived from ``retired=`` rather than hand-listed. Maintaining
# membership in two places — a tuple and a field — is a standing
# invitation for a rule to be marked retired and still evaluate, or the
# reverse. The field is the single source of truth; these follow from it.
ACTIVE_RULES: tuple[Rule, ...] = tuple(rule for rule in ALL_RULES if rule.active)
RETIRED_RULES: tuple[Rule, ...] = tuple(rule for rule in ALL_RULES if not rule.active)

BY_ID: dict[str, Rule] = {rule.id: rule for rule in ALL_RULES}
