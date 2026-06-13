# Lift report — prevent-regression P1 (haiku, blind pair)

Judged ONLY from `lift-probes/old-P1.md` and `lift-probes/new-P1.md`
against the criteria locked in `lift-protocol.md`. Both probes ran via
`claude -p --model haiku --allowedTools Read Glob Grep`, rc=0; the only
prompt difference was the skill path (frozen copy vs working tree).
Grounding verified by re-reading the cited lines in each condition's
text after the transcripts were saved.

| Axis | OLD | NEW | Lift |
|---|---|---|---|
| B — placement behavior | 1 | 2 | +1 |
| V — verdict gates | 1 | 2 | +1 |
| G — grounding | 1 | 2 | +1 |

No regressions (NEW ≥ OLD on every axis).

## OLD (frozen text) — B=1, V=1, G=1

- B=1 (mixed/hedged, as predicted): places the rule script and fixtures
  "created in working tree" (`scripts/lint/<rule>.py`,
  `tests/lint/<rule>_*`) with no staging location, while correctly
  refusing the pre-commit/CI/CLAUDE.md edits by leaning on the intro's
  "produces a proposal and stops". The haiku run resolved the old text's
  contradiction better than the worst-case prediction (B=0), but its
  artifact placement still breaks the proposal-dir contract the
  machine-check lane installs from.
- V=1: assembles four gates from the diffused Phase 3/6 text
  (verify_rule RCs, historical fire, clean HEAD, proposal completeness)
  but never-install does not appear in its gate list — it had no verdict
  block to anchor on.
- G=1: every quoted mandate verified real in the frozen text (lines
  14-15, 46-48, 217, 240, 262-263, 339, 365-366 all check out), but it
  cites a "section 'Invocation' (lines 38–48)" — no such heading exists;
  vague-but-real per the locked scale.

## NEW (working tree) — B=2, V=2, G=2

- B=2: staged proposal-dir paths quoted verbatim
  (`reports/prevent-regression/<id>/scripts/lint/<rule>.py`, fixtures
  likewise), wiring "emitted as diff blocks inside proposal.md, not
  applied", and the never-install constraint quoted exactly.
- V=2: gates read straight off `## How success is judged` — never
  installed unilaterally, verify_rule BAD_RC=1/GOOD_RC=0, historical
  fire + clean HEAD, fixture precision/recall, test-only branch.
- G=2: every citation names a real heading and the quoted lines (50-58,
  60-74) match the working-tree text exactly (verified post-hoc).

## Verdict

Lift confirmed at the headline defect site: the repair moved a haiku
executor from improvised in-tree artifact placement and a gateless
self-judgment to the exact staged-emit contract the conformance harness
scores. One probe pair only (task constraint) — the other phases'
behavior is unprobed at this tier.
