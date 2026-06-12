# Path A implementation report — /which-shape boost weights as registry data

Date: 2026-06-12. Implements Path A from `scout.md` §3 on top of the
committed C1–C7 repair (`implementation.md`). Files touched:
`.claude/skills/which-shape/shapes.yml`,
`.claude/skills/which-shape/scripts/route.py`,
`.claude/skills/which-shape/SKILL.md`, `tests/test_which_shape.py`.
Working files (kept for audit): `parity_battery.py` and
`parity_baseline.json` in this directory. Nothing committed.

## 1. Design chosen — boost block schema

Every shape in `shapes.yml` MUST declare a `boost:` key (it joined the
required-keys set). `boost: {}` is an explicit opt-out — a shape author
can ship an unboosted shape, but only by writing the empty block, so the
F4b handicap can never recur silently. Two forms:

**Simple form** (9 of 11 shapes):

```yaml
boost:
  cues: [bug, broken, ..., crash]
  weight: 30
  rationale: "task starts from a failure symptom"
```

Fires once (additively) when any cue token appears in the task.

**Rules form** (the two genuinely conditional shapes):

```yaml
boost:
  mode: first-match | additive
  rules:
    - conditions: [...]      # AND-ed; [] = always
      weight: 36
      rationale: "..."
```

Condition vocabulary — deliberately minimal, schema-validated, NOT an
expression language (three types):

- `{type: cue-hit, cues: [...]}` or `{type: cue-hit, cues_from: <shape-id>}`
  — `cues_from` resolves to the referenced shape's simple-form boost
  cues (validated: the target must have a simple boost). Used by
  regression-prevention's compound +8 to read bug-fix's failure
  vocabulary without duplicating it across shapes.
- `{type: context-missing}` — project context state == missing.
- `{type: not-narrow}` — no token from the narrow union (below).

**Shape-knowledge migrations beyond boosts** (both judged low-risk and
done, eliminating the last in-code per-shape tables):

- `narrow_signal: true` (inside boost) on direct-change, bug-fix,
  decision-capture, regression-prevention. The `narrow` union is now the
  union of those shapes' declared boost vocabularies — previously the
  hard-coded `DIRECT_CUES | BUG_CUES | DECISION_CUES | REGRESSION_CUES`.
- `context_exempt: true` (shape level) on project-intake, direct-change,
  bug-fix, decision-capture — previously the hard-coded −4 exemption set.

**Per-shape encoding of the two risky cases:**

- `project-intake` (first-match, 4 rules): the original branch
  `context_missing ∧ intake_hits ∧ (forced ∨ ¬narrow) → +36` splits into
  two +36 rules (one with the force-cues condition, one with not-narrow),
  followed by the `context_missing ∧ forced → +18` rule and an
  unconditional `−30` otherwise-rule. First-match semantics reproduce
  the original if/elif/else exactly (verified by truth-table walk and by
  the parity battery).
- `regression-prevention` (additive, 2 rules): +30 on its recurrence
  cues; +8 when recurrence cues AND `cues_from: bug-fix` both hit —
  the cross-shape compound preserved as data. The recurrence cue list is
  duplicated across the two rules of the same block (adjacent lines;
  accepted over inventing a self-reference construct).

**route.py after the rewrite:** the eleven hard-coded `if/elif sid ==`
arms, the 12 module cue constants, `BOOSTED_SHAPE_IDS`,
`CUE_CONSTANT_SYNC`, and `validate_scorer_coverage` are all GONE — the
parallel in-code constant table (the format-equivalence smell) is
eliminated entirely. The scorer is now a generic interpreter:
`_boost_rules` (simple form normalizes to one additive cue-hit rule),
`_condition_holds`, `_boost_cue_vocabulary`, `narrow_cue_union`, and a
`context_exempt` read. `_score_shape` gained `shapes_by_id` /
`narrow_cues` parameters (internal; no external caller).

## 2. Parity result

Method: an 18-prompt battery (`parity_battery.py`) covering every shape,
the fallback, both standard probes, and four restored-token prompts was
scored against the pre-migration scorer and saved
(`parity_baseline.json`). The migration was done in two passes:

- **Pass 1 (migration only, boost cues == the old constants): EXACT
  PARITY — 18/18 prompts identical (shape, score, confidence).** The
  data-driven interpreter reproduces the hard-coded arms with no delta.
- **Pass 2 (vocabulary restoration): 14/18 unchanged; exactly the 4
  restored-token prompts changed, all intentionally:**

| Prompt | Before | After |
|---|---|---|
| "the app shows a crash on startup" | bug-fix, 4, low | bug-fix, **34, medium** |
| "stop this regression from coming back" | bug-fix, 4, low (alphabetical tiebreak) | **regression-prevention, 34, medium** |
| "build a new export page" | feature-shaping, 4, low | feature-shaping, **30, medium** |
| "extract the service and split the module" | refactor-execution, 4, low | refactor-execution, **28, medium** |

These restore pre-narrowing routing quality (the constant-sync repair
had silently dropped these boosts). The battery is committed as
`test_parity_battery_against_recorded_scores` with the deltas annotated.

## 3. Re-added token curation list (operator review)

Each token was boosted pre-repair via the in-code constants, lost in the
constant-sync narrowing, and is now re-added as DATA in its shape's
boost cues (each carries a YAML comment naming the restoration):

| Token | Shape (boost cues) | Note |
|---|---|---|
| `crash` | bug-fix | also flows into regression's compound via `cues_from: bug-fix`, and into the narrow union via bug-fix's `narrow_signal` |
| `regression` | regression-prevention | narrow union via `narrow_signal` |
| `back` | regression-prevention | narrow union via `narrow_signal` |
| `new` | feature-shaping | stays a NEGATIVE cue for bug-fix / regression-prevention / task-closeout (unchanged) |
| `extract` | refactor-execution | not a narrow signal |
| `split` | refactor-execution | not a narrow signal |

Side effect, intentional: the narrow union regains exactly
{crash, regression, back} — i.e. it now equals the pre-narrowing union
again (affects only project-intake's not-narrow condition).

## 4. --validate changes

- Boost blocks are schema-validated inside `validate_shapes_payload`:
  form detection (simple vs rules), non-empty string-list cues, integer
  weights (bools rejected), non-empty rationales, mode ∈
  {first-match, additive}, condition type ∈ {cue-hit, context-missing,
  not-narrow}, cue-hit's cues XOR cues_from, `cues_from` referential
  check (must name a simple-boost shape), unknown-key rejection at
  boost / rule / condition level, `narrow_signal` / `context_exempt`
  type checks.
- Boost-arm coverage check became "every shape has a `boost` key"
  (missing → schema error; `{}` allowed) — enforced by the required-keys
  set, no separate validator.
- The cue-sync check is RETIRED — the parallel in-code constant table it
  policed no longer exists; there is nothing left to drift.
- `main() --validate` now just calls `load_shapes` (which raises on any
  schema error) and prints `shapes OK`. Exit codes unchanged (0 / 2).
- `check-ecosystem-consistency`'s own `validate_shapes_payload` was
  inspected and left alone: it ignores unknown keys, so the new
  `boost` / `context_exempt` keys pass; boost enforcement is route.py's
  job. Its 5 tests pass unmodified.

## 5. SKILL.md change

The Registry paragraph that said boosts/cue-constants live in the scorer
(and that the narrow union + exemption set "still live in
scripts/route.py") now says: boost weights are registry data
(`boost:` block per shape, `{}` = explicit opt-out), `narrow_signal` /
`context_exempt` are registry flags, the scorer holds no per-shape
table, adding a shape never requires editing route.py, and `--validate`
checks the schema including every boost block. No other SKILL.md prose
needed changing (the mandatory-run, lexical-prior, and low-confidence
gates from the C1–C7 repair are unaffected).

## 6. Tests

`tests/test_which_shape.py`: 29 tests (was 25). Removed 2 obsolete
(`test_validate_fails_on_shape_without_boost_arm`,
`test_validate_fails_on_cue_constant_drift` — they policed the deleted
constant table); added 6:

- `test_validate_fails_on_shape_without_boost_block`
- `test_validate_accepts_explicitly_empty_boost_block` (also proves an
  opt-out shape still routes on base cues)
- `test_validate_fails_on_malformed_boost_blocks` (8 malformed cases:
  string weight, empty cues, unknown boost key, bad mode, unknown
  condition type, cue-hit with neither/both cue sources, cues_from →
  missing shape, cues_from → rules-form shape)
- `test_parity_battery_against_recorded_scores` (18 prompts)
- `test_restored_boost_tokens_come_from_data`
- `test_regression_compound_boost_reads_bug_cues_via_cues_from`

Results:
- `.venv/bin/python -m pytest tests/test_which_shape.py tests/test_ecosystem_consistency.py -q`
  → **34 passed** (29 + 5), 0 failed.
- `python3 .claude/skills/which-shape/scripts/route.py --validate` →
  `shapes OK`, exit 0.
- `.venv/bin/ruff check route.py tests/test_which_shape.py` → all checks
  passed (shapes.yml and SKILL.md are not ruff surfaces).
- Not run: full repo suite (scoped per verification policy to the
  touched surfaces; shapes.yml's only schema consumers are the two
  suites above).

## 7. Probe outputs (post-change, --skip-log)

**Probe A** — `"help me with the thing we discussed"`: **byte-identical
to baseline** — Bug Fix (`bug-fix`), `Confidence: low (score=0)`,
rationale `fallback shape candidate` + `project status: 3 plan(s) in
flight`; alternatives decision-capture 0, direct-change 0,
concept-rename −4. (Presentation still governed by the C1
low-confidence gate.)

**Probe B** — `"this is not a typo, the whole subsystem terminology is
wrong"`: **Concept Rename wins, unchanged** — `Confidence: medium
(score=28)`, rationale strong `terminology`, negative `typo`, boost
rationale `task names a glossary-level concept or terminology change`;
Direct Change first alternative at 26.
