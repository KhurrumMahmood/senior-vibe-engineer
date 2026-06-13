# Machine-check lane — repaired SKILL.md vs skill-comply harness

Date: 2026-06-12. Harness: `scripts/skill_comply/` (owned by a parallel
agent — read and run only, never edited; verified untouched via
`git status --porcelain scripts/skill_comply/` → empty).

## Protocol

1. Seeded a fresh mini-host via `.venv/bin/python
   scripts/skill_comply/seed_fixture.py` (repo under the system temp
   dir; anchor `31484b1f`; antipattern files products/checkout/reports;
   recall file reports.py).
2. The campaign orchestrator then acted as a `/prevent-regression`
   executor following the **repaired** SKILL.md (working tree): Form B
   free-form pattern; Phase 1 `git show <anchor>` survey + `pattern.md`;
   Phase 2 rule scaffolded with the skill's own
   `scripts/generate_rule.py`, matcher filled per pattern.md
   (`int(<receiver>.POST/GET.get(...))`, receiver unconstrained); Phase 3
   fixture pair + `verify_rule.py`; Phases 4–5 wiring + CLAUDE bullet
   emitted as ready-to-apply diff blocks inside `proposal.md`; Phase 6
   proposal + historical-fire/HEAD-clean checks. Per the repaired staging
   contract, every guard artifact was staged under the proposal dir
   (`reports/prevent-regression/no-bare-int-request/` in the seeded
   repo) at repo-relative paths; nothing was wired into the seeded tree
   by the skill run.
3. `proposal_manifest.json` was authored as **harness glue** (required
   by `install_proposal.py`), not as a skill output — the skill text
   does not and must not mandate it.
4. `install_proposal.py` installed the staged artifacts;
   `score_conformance.py` graded the result.

## Scores (pasted verbatim summary)

```
C1  PASS  [cosmetic]       pattern.md exists & non-empty
C2  PASS  [cosmetic]       rule script + CLI contract
      └─ empty_rc=2, bad_rc=1, clean_rc=0, output_format_ok=True, stdlib_only=True
C3  PASS  [CONSEQUENTIAL]  fixture pair + verify_rule.py
      └─ verify_rule rc=0; bad rc=1 hits=4 | good rc=0 hits=0
C4  PASS  [CONSEQUENTIAL]  historical-fire
      └─ app/views/products.py: pre-anchor hits=2 (need >0), HEAD hits=0 → OK
C5  PASS  [cosmetic]       pre-commit + CI + run.py wiring
C6  PASS  [cosmetic]       CLAUDE.md canonical-pattern entry
C7  PASS  [cosmetic]       proposal.md exists with required sections
C8  PASS  [CONSEQUENTIAL]  bounded incidental firing
      └─ scanned 6 in-scope files; hits only in checkout.py + reports.py
         (both in antipattern allow-list); no stray hits (cart.py clean)
C9  PASS  [CONSEQUENTIAL]  planted-variant recall
      └─ app/views/reports.py: hits=2 (self.request + aliased receiver) → OK
VERDICT: PASS
```

Post-lane harness self-test: `.venv/bin/python
scripts/skill_comply/validate.py` → `OVERALL: PASS` (all six fixtures:
conformant, defective, over-broad, poisoned-good, wrong-name,
under-broad).

## What WAS machine-checked

- The repaired SKILL.md's output contract is Bucket-A conformant: an
  executor following its staging contract produces a proposal dir whose
  artifacts install via `install_proposal.py` and pass C1–C9, including
  all four consequential gates (own-verifier pass, historical fire,
  bounded incidental firing, planted-variant recall).
- The skill's own helper scripts (`generate_rule.py`, `verify_rule.py`)
  execute as the text describes.

## What was NOT machine-checked (no overclaiming)

- The executor was the campaign orchestrator (context-rich), not an
  uncoached fresh model — this lane proves the contract is followable
  and scoreable, not that a weak-tier executor follows it (Stage 6
  probes address that at one defect site only).
- Phase 6's `log_effectiveness.py` telemetry append was not exercised
  (host-repo surface, not part of the harness scorecard).
- The ruff-coverable Phase-1 branch, Form A/C/D routing, the topology
  templates, and the Phase 3b test-only branch were not exercised
  (harness models the custom-AST-rule path only — a known harness gap).
- C8's oracle was supplied by the seed manifest, as in all harness runs;
  the real-run oracle problem remains open (harness-owner lane).
