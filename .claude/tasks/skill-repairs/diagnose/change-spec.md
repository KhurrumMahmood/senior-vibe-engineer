# Change spec — /diagnose repair

Inputs: `reports/skill-frame-review/diagnose.md` (F1–F6) + `scout.md`
here (claims verified TRUE; new defects D1–D4; anchors). Doctrine:
declared verdict, artifact-truth gates, load-bearing-or-delete,
no invention, smallest responsible edits, preserve voice/numbering.

## Declared verdict

A fresh, non-context-sharing verifier re-runs the frame-review rubric
against the repaired skill and checks finding-by-finding that F1–F6 and
D1–D4 are resolved without new defects of the same classes: every
mandated artifact names its producer and consumer; every gate states
its pass condition and failure path; nothing invented. Write to that
test.

## C1 — Root-cause proof standard (F1)

`root-cause.md` content requirements stated in Phase 6 (and where the
file is first mentioned): it must contain (a) the falsifiable Phase 3
statement that was satisfied, (b) the confirming probe's exact command
and PASTED observed output, and (c) where feasible, a cause-toggle
demonstration (loop fails with cause present, passes with cause
neutralized) recorded BEFORE the fix is written. A one-sentence
narrative without a pasted probe is not a root cause.

## C2 — Elimination gate (F2)

Inline gate between Phase 4 and Phase 5 (scout: shared insertion point
with C4, end of Phase 4): before any fix, name each remaining
hypothesis and the observation that rules it out; any hypothesis that
cannot be ruled out is named in `root-cause.md` as residual
uncertainty. Consistent evidence is not discriminating evidence.

## C3 — Phase 0 evidence inventory + reporter-theory quarantine (F3)

Two added Phase 0 bullets: "evidence already in hand" (tracebacks,
logs, prior fix attempts, exact commands from the conversation) and
"reporter's suspected cause — recorded as one hypothesis among
several, never as a finding."

## C4 — Loop back-edges and stop (F4)

Same insertion point as C2: if every hypothesis is falsified, return
to Phase 3 and re-rank using the new observations; after two full
cycles without a confirmed cause, stop and write up the eliminated
space as partial findings. If Phase 6 verification fails, the root
cause is unconfirmed — return to Phase 3; do not patch the fix.

## C5 — Gate made load-bearing + index consumes core outputs (F5)

(a) The `evidence_gate.py check` step: gate must exit 0 before the
diagnosis is reportable; on exit 1, fix the named gap (do not
proceed); paste the gate's summary line in the final reply. (b) Add
`## Root cause` and `## Reproduction` sections to the Diagnosis Index
Shape so `diagnosis.md` consumes the two headline artifacts.

## C6 — Transcript-backed reproduction and verification (F6)

`reproduction.md` must embed the exact loop command and one pasted
failing run (plus observed fail rate over N runs when intermittent);
`verification.md` must embed the passing rerun output of the same
command. Assertion without transcript does not count.

## C7 — Artifact-reality drift (scout D1–D4)

- D1: name each required evidence file at the phase that produces it
  (align the prose with the gate's manifest expectations).
- D2: wire `cleanup-check.md` to the Phase 6 `[DIAG-` cleanup grep —
  the grep's output is recorded there; the gate/index consumes it.
- D3: correct the `produces: regression_test` claim to its real
  conditional form.
- D4: fix the stale "PR F/G will enforce" docstring sentence in
  `scripts/evidence_gate.py` to state reality (manual/skill-invoked
  gate; nothing in CI consumes it). Comment-only edit; no behavior
  change to the script.

OUT OF SCOPE (ledgered, not yours): content-level checks inside
evidence_gate.py (shared by three other skills; needs its own tested
change).

## Constraints

Smallest edits; no phase renumbering; keep the skill's voice; nothing
invented beyond review + scout fragments; internal-consistency sweep
after edits (counts, artifact names, cross-references).
