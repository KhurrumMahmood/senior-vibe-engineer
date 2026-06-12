# Implementation report — /diagnose repair (C1–C7)

Date: 2026-06-12. Files touched: `.claude/skills/diagnose/SKILL.md`,
`scripts/evidence_gate.py` (docstring only). No commits made.

Line numbers below are post-edit unless marked "was".

## C1 — Root-cause proof standard (F1)

- **Anchor:** Phase 6 bullet (was line 143, "write the root cause in one
  sentence;"), now lines 165–170.
- **Before → after:** one-sentence bullet → `write root-cause.md:` bullet
  requiring (a) the satisfied falsifiable Phase 3 statement, (b) the
  confirming probe's exact command and pasted observed output, and
  (c) where feasible, a cause-toggle demonstration recorded before the
  fix was written; closes with "A one-sentence narrative without a
  pasted probe is not a root cause."
- **Judgment call:** the spec's parenthetical "(and where the file is
  first mentioned)" — after the C2 edit, `root-cause.md` is first
  mentioned in the Phase 4 elimination gate, which carries its own
  specific content requirement (residual uncertainty). Full proof
  requirements stated once, at the producing Phase 6 bullet, rather than
  duplicated into the Evidence Manifest section (scout's optional anchor
  2); duplication risks count drift and the spec mandates smallest edits.

## C2 — Elimination gate (F2)

- **Anchor:** end of Phase 4, between the `[DIAG-` paragraph (was
  line 120) and `## Phase 5 - Fix` (was line 122) — scout's shared
  C2/C4 insertion point. Now lines 132–135.
- **Before → after:** Phase 4 ended at the prefix-grep paragraph → new
  paragraph: before any fix, name each remaining hypothesis and the
  observation that rules it out; un-ruled-out hypotheses go in
  `root-cause.md` as residual uncertainty; "Consistent evidence is not
  discriminating evidence."

## C3 — Phase 0 evidence inventory + reporter-theory quarantine (F3)

- **Anchor:** Phase 0 bullet list, after the risk-triggers bullet (was
  line 55). Now lines 56–59.
- **Before → after:** four bullets → six; added "evidence already in
  hand: tracebacks, logs, prior fix attempts, and exact commands from
  the conversation" and "the reporter's suspected cause - recorded as
  one hypothesis among several, never as a finding."
- **Judgment call:** changed the trailing period on the risk-triggers
  bullet to a semicolon so the list keeps its existing
  semicolons-then-final-period style.

## C4 — Loop back-edges and stop (F4)

- **Anchor 1:** same Phase 4 insertion point as C2 (now lines 137–140):
  if every hypothesis is falsified, return to Phase 3 and re-rank with
  the new observations; after two full cycles without a confirmed
  cause, stop and write up the eliminated space as partial findings.
- **Anchor 2:** Phase 6, after the bullet list / before the "If the
  answer is…" routing paragraph (scout's "insert before line 146"), now
  lines 173–174: "If verification fails, the root cause is unconfirmed -
  return to Phase 3; do not patch the fix."
- **Judgment call:** did NOT extend frontmatter `max_overhead` (scout
  marked it optional; spec C4 places the bound at the insertion point).

## C5 — Gate made load-bearing + index consumes core outputs (F5)

- **(a) Anchor:** directly after the `evidence_gate.py check` bash block
  (was lines 179–181), now lines 213–215: gate must exit 0 before the
  diagnosis is reportable; on exit 1, fix the named gap and re-run, do
  not proceed past a failing gate; paste the gate's summary line in the
  final reply.
- **(b) Anchor:** Diagnosis Index Shape template (was lines 185–191):
  added `## Reproduction` and `## Root cause` between `## Symptom` and
  `## Fix`.
- **Judgment call:** section order Symptom → Reproduction → Root cause →
  Fix (narrative order; scout left ordering to implementer).

## C6 — Transcript-backed reproduction and verification (F6)

- **Anchor 1:** Phase 2, new paragraph after the minimization paragraph
  (was lines 92–93), now lines 100–103: `reproduction.md` must record
  the exact loop command and one pasted failing run; for intermittent
  symptoms, the observed fail rate as N failures over M runs;
  "Assertion without a transcript does not count."
- **Anchor 2:** Phase 6 first bullet (was line 139), extended: "…and
  paste the passing rerun output of the same command into
  `verification.md`."
- **Judgment call:** used the per-producing-phase placement (scout
  anchors 1+2) rather than a combined Evidence Manifest content block
  (scout anchor 3), because the D1 fix names files at producing phases
  anyway — same statements, one location each.

## C7 — Artifact-reality drift (D1–D4)

- **D1 (files named at producing phases):**
  - `reproduction.md`: Phase 1 abort path (was line 77) reworded from
    "write `reproduction_or_reason`" to "write `reproduction.md` (the
    `reproduction_or_reason` evidence)…" — keeps the frontmatter-token
    alignment explicit; plus the Phase 2 paragraph (C6).
  - `root-cause.md`: Phase 4 gate (C2) + Phase 6 bullet (C1).
  - `verification.md`: Phase 6 first bullet (C6).
  - `cleanup-check.md`: Phase 6 cleanup bullet (D2).
- **D2 (cleanup grep wired):** Phase 6 third bullet (was "remove every
  `[DIAG-...]` probe;") → "…then grep for the prefix and record the
  grep command and its output in `cleanup-check.md`". Consistent with
  Phase 4's existing "grep for the prefix in the cleanup phase".
- **D3 (conditional produces):** frontmatter line 29
  `regression_test` → `regression_test_or_seam_gap_finding`.
  **Judgment call:** scout offered "regression_test (or seam-gap
  finding)" phrasing or leave-as-is; chose a single snake_case token so
  the corrected claim survives every consumer surface
  (`evidence_gate.py show`, `/which-skill` frontmatter reads) and stays
  within the repo's token convention. "seam_gap_finding" traces to
  Phase 5's "document that as an architecture finding". Grep confirmed
  no external consumer references the old diagnose-specific token.
- **D4 (stale docstring):** `scripts/evidence_gate.py` lines 26–27,
  "PR F will wire this into CI; PR G will turn the warnings into hard
  refusals where appropriate." → "The gate is run manually or by the
  skills that document it; nothing in CI consumes it." Comment-only.
  **Judgment call:** left the docstring title "Evidence gate (PR D)."
  — historical provenance, not a false future promise; D4 scopes to the
  PR F/G sentence. (Note: `_common/skill-frontmatter.md` line 190
  carries a similar "PR G will turn it into a hard refusal" claim —
  out of this repair's scope, flagging for the ledger.)

## Verification

- `python3 scripts/evidence_gate.py --help` — exits 0, output identical
  except the corrected docstring sentence; `git diff
  scripts/evidence_gate.py` shows only the 2-line docstring hunk.
- `.venv/bin/python scripts/evidence_gate.py show --skill diagnose` —
  frontmatter still parses; four `evidence_required` tokens unchanged
  and matching the SKILL.md JSON example exactly.
- Internal-consistency sweep:
  - Each of the five evidence files now has a producer phase and a
    consumer (gate check for all four manifest files; `diagnosis.md`
    index additionally consumes reproduction + root cause via the new
    sections; `cleanup-check.md` consumes the Phase 6 grep).
  - Old phrasings gone: zero hits for "write the root cause in one
    sentence", bare "write `reproduction_or_reason`", "PR F", "PR G"
    in the two touched files.
  - No phase renumbering; Phases 0–6 headings untouched.
  - `.claude/docs/skill-catalog.md` line 215 already describes the five
    evidence files — no stale cross-reference created.
- Not run: no automated test suite exists for `evidence_gate.py`
  (scout §3 confirmed the gap); the change is comment-only, so per the
  tiered verification policy (pure docs/comments) nothing further was
  required.
