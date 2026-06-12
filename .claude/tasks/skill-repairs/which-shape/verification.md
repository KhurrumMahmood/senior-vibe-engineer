# Verification — /which-shape repair (independent verifier)

Date: 2026-06-12. Verifier: fresh-context agent, no implementer context.
Inputs read in order: change-spec.md, defect spec
(`reports/skill-frame-review/which-shape.md`), live files, git diffs vs
HEAD (the pre-repair copy; `/tmp/skill-repairs-old/which-shape/` exists
and matches HEAD), live probe runs, test suite — then `scout.md` last,
as instructed.

Scope note: `git status` also shows uncommitted edits to
`.claude/skills/diagnose/SKILL.md`, `.claude/skills/scope-feature/SKILL.md`,
and `scripts/evidence_gate.py`. These are outside this repair's declared
target list and were not verified here (apparently parallel repairs).
The which-shape test file lives at repo-root `tests/test_which_shape.py`
(not `.claude/skills/which-shape/tests/`) — that is the repo convention;
the prompt's path was wrong, not the implementer.

## 1. Verdict table (C1–C7)

| Item | Verdict | Evidence |
|---|---|---|
| C1 low-confidence gate | **RESOLVED** | SKILL.md Output section: "If the script reports `confidence: low` — or any rationale line reads \"fallback shape candidate\" — do not present a single shape. Present the top 2-3 alternatives by score and ask one discriminating question (see the pre-run dimensions under Forms) before routing." Keys off both triggers the spec named; references C3's dimensions as the question source. |
| C2 lexical-prior stage | **RESOLVED** | SKILL.md, directly after the script block: "Treat the script output as a lexical prior, not the decision. If conversation evidence contradicts the cue match (negation, paraphrase, sarcasm), override it, say so, and name the cue collision in your reply so telemetry can see the override." Matches spec wording; placed at the act site. |
| C3 pre-run inventory | **RESOLVED** | SKILL.md Forms, before the examples: "Before invoking, check the conversation for the discriminating dimensions — recurrence? approved proposal in hand? unknown or inherited repo? scope width? durable choice? — and carry those words verbatim into the task string. The matcher is keyword-based, so the paraphrase IS the routing decision." All five dimensions present verbatim. |
| C4a registry sole truth | **RESOLVED** | "V1 shapes:" nine-bullet list deleted. Registry section now: "The explicit shape registry lives in `shapes.yml` — the sole shape inventory; this file deliberately does not mirror the list." Frontmatter description rewritten to "...such as project-intake, bug-fix, concept-rename, or task-closeout (illustrative — shapes.yml is the sole shape inventory)" — marked illustrative as the spec allowed. |
| C4b boost arms | **RESOLVED** | route.py: `elif sid == "concept-rename" and task_tokens & CONCEPT_RENAME_CUES: score += 30` and `elif sid == "task-closeout" and task_tokens & CLOSEOUT_CUES: score += 30`. Cue sets equal those shapes' shapes.yml strong sets exactly (verified token-by-token). Weight 30 = parity with the bug-fix / legacy-stabilization / health-audit / regression-prevention analog arms. ~33 net new route.py lines for C4 overall — within the scout's Path B sizing (30–45). |
| C4c validate coverage + drift fix | **RESOLVED** | New `validate_scorer_coverage()` wired into the `--validate` branch: (i) every shapes.yml id must be in `BOOSTED_SHAPE_IDS` (and vice versa); (ii) `CUE_CONSTANT_SYNC` enforces strong-only constants == the shape's strong set exactly, mixed intake constants ⊆ strong+normal. Pre-existing drift fixed by trimming constants to the registry: BUG_CUES −crash, REGRESSION_CUES −regression −back, FEATURE_CUES −new, REFACTOR_CUES −extract −split (all were shapes.yml *normal* cues, per scout §4). `--validate` → "shapes OK" on the real registry. See residual R1 for the behavioral consequence. |
| C4d tests | **RESOLVED** | tests/test_which_shape.py: `test_concept_rename_strong_cues_route_to_concept_rename` (includes the probe-B string), `test_task_closeout_strong_cues_route_to_task_closeout`, `test_validate_passes_on_real_registry`, `test_validate_fails_on_shape_without_boost_arm`, `test_validate_fails_on_cue_constant_drift` (covers both drift directions: extra constant cue and missing registry cue). |
| C5 telemetry default | **RESOLVED** | route.py argparse: `choices=["unscored", "useful", "partial", "noop", "overridden"], default="unscored"` with honest help text. SKILL.md Telemetry: "with `outcome: unscored` by default — a recommendation is not evidence of usefulness at the moment it is made"; correction path stated honestly: "runs when a human notices a misroute" and "(the rerun appends a second recommendation event; it does not amend the first)" — also closes the scout's n-inflation new-defect #3 at the prose level. Fixture in `test_recommendation_events_do_not_pollute_skill_useful_rate` updated useful→unscored; new `test_outcome_defaults_to_unscored` proves the logged event. |
| C6 un-fakeable artifact | **RESOLVED** | SKILL.md: "Running the script is mandatory — the recommendation must come from a real run, never composed from this file. Paste the script's `Project context:` and `Confidence: ... (score=N)` lines verbatim in your reply." Both line shapes are exactly what `render_markdown` emits (verified against live output). |
| C7 scout extras | **RESOLVED** | SKILL.md Registry: "After editing `shapes.yml`, run `route.py --validate` — it checks the schema, that every shape has a scorer boost arm, and that the scorer's cue constants match the registry's cues." Pointer: "Two pieces of per-shape knowledge still live in `scripts/route.py`, not the registry: the `narrow`-task cue union and the context-missing exemption set" — matches route.py:231 and :279; pointer only, no relocation, per spec. |

## 2. Live re-runs (all with `--skip-log`, repo venv python)

(a) **Probe A** `"help me with the thing we discussed"` → `Recommended
shape: Bug Fix (bug-fix)`, `Confidence: low (score=0)`, rationale
`fallback shape candidate` — byte-equivalent to the pre-repair scout
probe (same status-projection extra line, environmental). Script output
unchanged as the spec required; SKILL.md's C1 gate now forbids
presenting it as a single route. PASS.

(b) **Probe B** `"this is not a typo, the whole subsystem terminology is
wrong"` → `Recommended shape: Concept Rename (concept-rename)`,
`Confidence: medium (score=28)`, beating direct-change (26). Arithmetic:
concept-rename 12 (strong "terminology") − 10 (negative "typo") + 30
(new arm) − 4 (context-missing) = 28; direct-change 12 + 34 − 20 (two
negative cues) = 26. Misroute fixed by the new arm, as the declared
verdict's first acceptable branch requires. PASS. (Margin is 2 points —
fragile, but pinned by a test; see residual R3.)

(c) **`--validate`** → `shapes OK`, exit 0. PASS.

(d) **Synthetic drift, simulated directly** (temp copy of shapes.yml at
/tmp, real registry untouched and restored — verified clean afterward):
added a `phantom-shape` with no arm AND removed "guard" from
regression-prevention strong cues → exit 2 with
`error: phantom-shape: no boost arm in _score_shape — add one and list
it in BOOSTED_SHAPE_IDS; REGRESSION_CUES: cues not in
regression-prevention strong cues: ['guard']`. Both new checks fail
loudly on real drift. The two new tests exercise the same paths
(including the missing-strong-cue direction). PASS.

(e) **Test suites**: `.venv/bin/python -m pytest tests/test_which_shape.py -q`
→ **25 passed**. Adjacent suites touching SKILL.md metadata:
`tests/test_ecosystem_consistency.py`, `tests/test_which_skill_recommendations.py`,
`tests/test_skill_taxonomy.py` → **14 passed**. PASS.

## 3. No-invention audit

- **New boost-arm cues**: CONCEPT_RENAME_CUES {concept, glossary,
  supersede, terminology, deprecate} == concept-rename strong (shapes.yml:43)
  exactly; CLOSEOUT_CUES {closeout, cleanup, stabilize, finished,
  wrap-up, post-commit} == task-closeout strong (shapes.yml:168) exactly.
  Nothing invented.
- **Weights**: both new arms +30, stated parity with the four +30 analog
  arms. Confidence thresholds (40/24), all other weights, and the
  context-missing penalty are untouched.
- **Trimmed constants** all trace to shapes.yml (removed tokens were
  normal-tier cues there; constants now equal strong sets). Direction
  authorized by C4c "fix the existing drift"; consequence in R1.
- **compact.py diff is exactly the unscored-denominator change**: one
  hunk — `scored` column added to the shape table header, overridden%
  denominator switched from n to len(scored), plus a two-line comment.
  No other functions, no per-skill-table change, matches C5's "the
  metric counts only scored events" verbatim.
- **route.py diff** contains only: the constants block + sync comment,
  BOOSTED_SHAPE_IDS, CUE_CONSTANT_SYNC, validate_scorer_coverage, the
  two arms, the --outcome argparse change, and the --validate wiring.
  No stray edits.

## 4. New-defect sweep

- SKILL.md claims vs route.py behavior: every new claim checked —
  validate description matches code; "narrow union / exemption set live
  in route.py" matches code; telemetry default matches argparse;
  "overridden% counts only scored events" matches compact.py; the two
  paste-verbatim line shapes match render_markdown exactly. No drift
  introduced.
- No new ceremony: every added stage has a consumer (C3 feeds the task
  string the scorer reads; C1/C6 feed the user-facing reply; C2 feeds
  the override telemetry path; C7 feeds the registry-edit workflow).
- No hallucination-invited phrasing added; C6 closes the prior
  fabrication template.
- shapes.yml untouched and remains source of truth; the new
  CUE_CONSTANT_SYNC comment says so explicitly.
- The boost-arm rationale strings ("task names a glossary-level concept
  or terminology change", "task asks for post-work cleanup or closeout")
  accurately describe their shapes.

## 5. Telemetry sanity

- `--outcome` default for recommendations is `unscored` (argparse +
  live `test_outcome_defaults_to_unscored`-equivalent run confirmed via
  test suite).
- route.py:459 is the **only** writer of `event_kind: "recommendation"`
  in the repo, and it always passes `outcome=args.outcome` explicitly —
  nothing writes "useful" silently on the recommendation path.
- `skill_use.log_event` still has `outcome: str = "useful"` as its
  library default (pre-existing; applies to other skills' *run* events,
  which is the intended distinct semantics; out of this repair's scope).
- compact.py per-skill useful table still excludes recommendation
  events (filter at compact.py:66; covered by the unchanged pollution
  test).

## 6. Residuals

| # | Residual | Severity |
|---|---|---|
| R1 | The drift fix trimmed boost-trigger tokens instead of promoting them in shapes.yml: prompts whose only cue is "crash", "regression", "back", "new", "extract", or "split" lost their +24..+30 boost. Verified live: "the app shows a crash on startup" → bug-fix **low** (score=4) and "we need a regression test for the export path" → bug-fix **low** (score=4); pre-repair both reached a boosted medium. Mitigation: low confidence now lands in the C1 alternatives-gate instead of a confident single route, and shapes.yml edits were outside this repair's scope — but routing quality for these prompt classes regressed, and the new strong-equality validate rule means the fix-forward is a shapes.yml strong-cue promotion (Path A territory, already ledgered per spec). | Medium-low |
| R2 | `BOOSTED_SHAPE_IDS` is a hand-maintained mirror of the elif arms — `--validate` checks the registry against the *set*, not against the actual `_score_shape` code. Adding an id to the set without writing the arm would pass validate. Fenced only by a comment and by routing tests for shapes that have them. (Structural cause survives by design — Path A is the ledgered follow-up.) | Low |
| R3 | Probe B wins by 2 points (28 vs 26); any future negative-cue change on direct-change or concept-rename flips it. Pinned by `test_concept_rename_strong_cues_route_to_concept_rename`, so a flip is loud. | Low |
| R4 | Scout new-defect #4 (status-projection lines decorate even score-0 fallback rationales, making them look grounded) is unaddressed in code; partially mitigated because the C1 gate keys on the "fallback shape candidate" line, which survives the decoration. Not in C1–C7 scope. | Low |

## Overall: **PASS**

All seven change items RESOLVED; both live probes behave per the
declared verdict; `--validate` passes on the real registry and fails
loudly on simulated drift (both check types); compact.py matches C5's
intent exactly and changes nothing else; no invention found; 25 + 14
tests green. Worst residual is R1 (boost coverage narrowed for six
formerly-boosting tokens — defensible under registry-as-truth, but a
real routing-quality change the change-spec's wording licenses without
naming).
