# Implementation report — /which-shape repair (C1–C7)

Date: 2026-06-12. Implementer pass against
`.claude/tasks/skill-repairs/which-shape/change-spec.md`, anchors from
`scout.md`. Files touched: `.claude/skills/which-shape/SKILL.md`,
`.claude/skills/which-shape/scripts/route.py`,
`.claude/skill-use/compact.py` (judgment call, see C5),
`tests/test_which_shape.py`. `shapes.yml` NOT edited — the C4c drift fix
went into the in-code constants, matching the declared source of truth.
Nothing committed.

## Per-change record

### C1 — Low-confidence gate (F1)

- Anchor: SKILL.md "## Output", after the field list (was line 74).
- Before: field list only; no rule for `confidence: low`.
- After: new paragraph — `confidence: low` or any "fallback shape
  candidate" rationale ⇒ do not present a single shape; present the top
  2–3 alternatives by score and ask one discriminating question (cross-
  references the C3 pre-run dimensions instead of repeating them).
- Judgment: prose-only, as the spec's "smallest F1 fix" — thresholds at
  route.py (now ~407) untouched.

### C2 — Script-is-lexical-prior stage (F2)

- Anchor: SKILL.md Forms section, directly after the `--json/--skip-log`
  line (was line 54), before the status-projection paragraph — scout's
  first suggested seam.
- Before: script introduced as just "The script form:"; no division of
  labor.
- After: "Treat the script output as a lexical prior, not the decision.
  If conversation evidence contradicts the cue match (negation,
  paraphrase, sarcasm), override it, say so, and name the cue collision
  in your reply so telemetry can see the override."

### C3 — Pre-run situation inventory (F3)

- Anchor: SKILL.md "## Forms", before the example block (was line 41).
- After: check the conversation for the discriminating dimensions
  (recurrence / approved proposal / unknown-or-inherited repo / scope
  width / durable choice — the five families mapping 1:1 to the cue
  constants) and carry those words verbatim into the task string; "the
  paraphrase IS the routing decision."

### C4a — Registry sole source of truth (F4a)

- Anchors: SKILL.md frontmatter `description:` (line 3) and "## Registry"
  lines 87–97.
- Before: frontmatter "such as" list of seven; body "V1 shapes:" list of
  nine (vs eleven in shapes.yml).
- After: frontmatter example list rewritten to four examples explicitly
  marked "(illustrative — shapes.yml is the sole shape inventory)",
  deliberately including the two previously-omitted shapes; body list
  deleted and replaced with "the sole shape inventory; this file
  deliberately does not mirror the list."

### C4b — Boost arms for concept-rename and task-closeout (F4b, Path B)

- Anchor: `_score_shape` elif chain, slotted after the
  refactor-execution arm, before the context-missing penalty (scout's
  anchor).
- New constants `CONCEPT_RENAME_CUES` / `CLOSEOUT_CUES` = exactly those
  shapes' shapes.yml strong cue lists ({concept, glossary, supersede,
  terminology, deprecate} and {closeout, cleanup, stabilize, finished,
  wrap-up, post-commit}). Nothing invented.
- Weights: +30 for both. Closest analog arms: for `concept-rename`,
  **legacy-stabilization** (+30) — both boost on "the task describes a
  structural, cross-surface condition"; for `task-closeout`,
  **health-audit** (+30) — both are advisory sweep loops handing off to
  /triage-debt. +30 is also the modal single-cue-set boost (4 of the 9
  existing arms), i.e. strict parity, not a tuned number.
- Rationale strings styled on neighbors: "task names a glossary-level
  concept or terminology change" / "task asks for post-work cleanup or
  closeout".
- Not done (deliberately): no addition to the context-missing exemption
  set; no `narrow` union change; Path A (data-driven boosts) out of
  scope per spec.

### C4c — --validate coverage + cue-constant sync (F4b + scout drift)

- Anchors: cue constants (was route.py:45–54), `--validate` branch in
  `main()` (was 418–421).
- Drift fixed in code (shapes.yml untouched, as the source of truth):
  - `BUG_CUES` − `crash`; `REGRESSION_CUES` − `regression`, `back`;
    `FEATURE_CUES` − `new`; `REFACTOR_CUES` − `extract`, `split`.
  - Every strong-only constant now equals its shape's YAML strong set;
    `PROJECT_INTAKE_CUES` stays the documented strong+normal mix
    (validated as ⊆ strong ∪ normal — it intentionally omits
    `inherited`, which `INTAKE_FORCE_CUES` carries).
  - Side effect on `narrow` (route.py): loses crash/regression/back
    tokens. All existing routing tests still pass (re-derived by hand:
    "this bug keeps coming back" still wins regression-prevention 50
    vs bug-fix 42 via "keeps").
- New module registries: `BOOSTED_SHAPE_IDS` (11 ids) and
  `CUE_CONSTANT_SYNC` (constant → shape id → allowed cue keys).
- New `validate_scorer_coverage(shapes)`: (i) every shapes.yml id must
  be in `BOOSTED_SHAPE_IDS` (and vice versa — a stale arm id also
  fails); (ii) each constant must not contain cues missing from its
  shape's allowed YAML cue keys, and strong-only constants must not be
  missing any YAML strong cue (full equality both directions).
- `--validate` now runs it after `load_shapes`; failures raise
  ValueError → existing `error: ...` stderr path, exit 2.
- Judgment: `BOOSTED_SHAPE_IDS` is a declared mirror of the elif chain,
  not introspected from it — the seam the scout sized as Path B; the
  bidirectional id check makes one-sided drift loud in both directions.

### C5 — Telemetry default (F5)

- Anchors: route.py `--outcome` argparse (was line 413); SKILL.md
  "## Telemetry"; compact.py shape-feedback table (was 157–174); test
  fixture in `test_recommendation_events_do_not_pollute_skill_useful_rate`.
- Before: `default="useful"`, choices without `unscored`; SKILL.md
  presented the rerun without a trigger.
- After: `choices=["unscored", "useful", "partial", "noop",
  "overridden"], default="unscored"` with a help string. SKILL.md now
  says runs log `outcome: unscored` by default, states the correction
  trigger honestly ("runs when a human notices a misroute"), notes the
  rerun appends a second event rather than amending (scout new-defect
  #3), and keeps the documented rerun example.
- **Judgment call (out-of-list file):** the spec's mandated sentence
  "the metric counts only scored events" would be false against
  compact.py, whose overridden% denominator included all recommendation
  events — with an `unscored` default the metric would stay biased
  toward 0% (the exact F5 defect). Smallest change that makes the prose
  artifact-true: compact.py's shape table now computes overridden% over
  scored events only and gains an explicit `scored` column
  (`| Shape | n | scored | overridden% | top override theme |`).
  project.py needs no change (its shape section computes no rate).
- Fixture update: the recommendation event in the project.py test now
  carries `outcome: "unscored"` (models a default-logged event).

### C6 — Un-fakeable run artifact (F6)

- Anchor: SKILL.md Forms, "The script form:" lead-in (was line 47).
- After: "Running the script is mandatory — the recommendation must come
  from a real run, never composed from this file. Paste the script's
  `Project context:` and `Confidence: ... (score=N)` lines verbatim in
  your reply." Doubles as C1's input (the gate keys off the pasted
  confidence line).

### C7 — Scout extras

- `--validate` documented: one paragraph in "## Registry" — run it after
  editing shapes.yml; names the three things it checks (schema, boost-arm
  coverage, cue-constant sync). Closes scout reverse-drift item #1.
- Pointer (not relocation): same paragraph notes the `narrow`-task cue
  union and the context-missing exemption set still live in
  `scripts/route.py`, not the registry.

## Test results

- `python3 -m pytest tests/test_which_shape.py -q` → **25 passed**
  (18 pre-existing + 7 new), 0 failed.
- New tests: `test_concept_rename_strong_cues_route_to_concept_rename`
  (includes the literal probe-B prompt),
  `test_task_closeout_strong_cues_route_to_task_closeout`,
  `test_validate_passes_on_real_registry`,
  `test_validate_fails_on_shape_without_boost_arm` (synthetic 12th shape
  → exit 2, "no boost arm" on stderr),
  `test_validate_fails_on_cue_constant_drift` (both directions: YAML
  strong cue removed → constant-extra error; YAML strong cue added →
  constant-missing error),
  `test_outcome_defaults_to_unscored` (end-to-end via `main()` +
  `--log`), `test_compaction_overridden_rate_counts_only_scored_events`
  (n=3, scored=1, overridden%=100, not 33).
- `python3 -m pytest tests/test_ecosystem_consistency.py -q` → 5 passed
  (its private shapes fixture is schema-only; unaffected by the new
  coverage check, which runs only under route.py `--validate`).
- `python3 .claude/skills/which-shape/scripts/route.py --validate` →
  `shapes OK`, exit 0.
- `.venv/bin/ruff check` on route.py, compact.py, test_which_shape.py →
  all checks passed.
- Not run: full repo test suite (working tree contains unrelated
  parallel-repair edits to diagnose/scope-feature/evidence_gate.py;
  scoped per verification policy to the touched surfaces).

## Probe before/after

### Probe A — `route.py --skip-log "help me with the thing we discussed"`

- Before (scout.md): Bug Fix, confidence low (score=0), "fallback shape
  candidate" + status lines; alternatives decision-capture 0,
  direct-change 0, concept-rename −4.
- After: **byte-identical script output** (same winner, score, rationale,
  alternatives — incl. "project status: 3 plan(s) in flight"). Expected:
  no scored cue fires, so the constant/arm changes don't touch it. The
  repair is the C1 gate — `confidence: low` + "fallback shape candidate"
  now forbids presenting this as a single route; the executor must show
  the top alternatives and ask one discriminating question. Per the
  declared verdict, probe A is "no longer presentable as a single
  confident route per the new SKILL.md rule," not changed at script
  level.

### Probe B — `route.py --skip-log "this is not a typo, the whole subsystem terminology is wrong"`

- Before (scout.md): **Direct Change, medium (score=26)** — "typo"
  strong cue + +34 boost beat the −20 negatives; concept-rename −2 with
  no boost arm.
- After: **Concept Rename, medium (score=28)** — strong "terminology"
  (+12), negative "typo" (−10), new +30 boost arm, −4 context penalty;
  rationale "task names a glossary-level concept or terminology change".
  Direct Change drops to first alternative at 26. The F2/F4 misroute is
  fixed by the scorer itself; the C2 override stage additionally covers
  the residual negation blindness (the matcher still cannot see "not").
