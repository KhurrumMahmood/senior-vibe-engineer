# SCOUT report — /which-shape repair (findings F1–F6)

Date: 2026-06-12. Scout: read-only against the skill; probes run with
`--skip-log` (routing output is identical; only the telemetry append is
suppressed — verified in `main()` route.py:428-435, logging happens after
`route()` returns).

Files examined:
- `.claude/skills/which-shape/SKILL.md` (131 lines, frontmatter lines 1-29)
- `.claude/skills/which-shape/shapes.yml` (172 lines, 11 shapes)
- `.claude/skills/which-shape/scripts/route.py` (445 lines)
- `.claude/skills/which-shape/agents/openai.yaml` (4 lines, exists)
- `.claude/skill-use/compact.py`, `.claude/skill-use/project.py`,
  `.claude/skills/_common/skill_use.py` (telemetry consumers)
- `tests/test_which_shape.py` (18 tests)
- Defect spec: `reports/skill-frame-review/which-shape.md`

CLI form: `route.py [task ...]` — positional free text, `nargs="*"`.
Flags confirmed via `--help`: `--project-root`, `--shapes`, `--json`,
`--status`, `--validate`, `--skip-log`, `--log`,
`--outcome {useful,partial,noop,overridden}`, `--human-override`.
System `python3` has PyYAML 6.0.2; script runs without the venv.
Repo state during probes: `.engineering/project/` does NOT exist (project
context = "missing"); `.engineering/local/status.json` DOES exist and was
fresh (its signals appear in probe rationale).

---

## 1. Claim verification

### Probe A (F1 claim) — REPRODUCED EXACTLY

```
$ python3 .claude/skills/which-shape/scripts/route.py --skip-log "help me with the thing we discussed"
Task: help me with the thing we discussed
Project context: missing (adapter=False, profile=False, approved=False)

Recommended shape: Bug Fix (`bug-fix`)
Confidence: low (score=0)

Why:
- fallback shape candidate
- project status: 3 plan(s) in flight

First next: reproduce the failure

Loop:
- reproduce with a test, log, or traceback
- trace call sites and patch the root cause
- verify the failure no longer occurs
- /prevent-regression if the bug shape can recur

Stop/reassess: Stop and reframe if the bug cannot be reproduced or spans a subsystem boundary.

Alternatives:
- `decision-capture` (Decision Capture), score=0
- `direct-change` (Direct Change), score=0
- `concept-rename` (Concept Rename), score=-4
```

Mechanism confirmed: all-zero scores; tiebreak at route.py:308
`ranked.sort(key=lambda item: (-item[0], item[1]["id"]))` — alphabetical
on shape id, so `bug-fix` beats `decision-capture` / `direct-change`.
Rationale fallback string at route.py:211
(`return score, rationale or ["fallback shape candidate"]`).

### Probe B (F2/F4 claim) — REPRODUCED EXACTLY

```
$ python3 .claude/skills/which-shape/scripts/route.py --skip-log "this is not a typo, the whole subsystem terminology is wrong"
Task: this is not a typo, the whole subsystem terminology is wrong
Project context: missing (adapter=False, profile=False, approved=False)

Recommended shape: Direct Change (`direct-change`)
Confidence: medium (score=26)

Why:
- strong cues: typo
- negative cues: subsystem, terminology
- task looks narrow enough to skip routing overhead
- project status: 3 plan(s) in flight

First next: proceed directly
...
Alternatives:
- `bug-fix` (Bug Fix), score=0
- `concept-rename` (Concept Rename), score=-2
- `refactor-execution` (Refactor Execution), score=-4
```

Arithmetic confirmed: direct-change = +12 (strong "typo") − 20 (negative
"subsystem","terminology") + 34 (boost, route.py:181-183) = 26 → medium.
concept-rename = +12 (strong "terminology") − 10 (negative "typo")
− 4 (context-missing penalty, route.py:209) = −2; no boost branch exists
for it. `tokenize()` (route.py:57-58) is a bag-of-words set; "not" is a
STOPWORD (route.py:37-43) — negation literally invisible, as claimed.

### F1 — TRUE

- Confidence thresholds exactly where the review says: route.py:311
  (`"high" if score >= 40 else "medium" if score >= 24 else "low"`).
- SKILL.md "## Output" (lines 66-74) lists the fields; NO rule anywhere
  in SKILL.md for `confidence: low` or "fallback shape candidate". Grep
  confirms: the words "low", "fallback", "confidence" appear in SKILL.md
  only as the Output field name ("confidence and rationale", line 70).
- Nuance (does not weaken the claim): when status.json is present, the
  rationale gains "project status: ..." lines (route.py:321), so a
  fallback recommendation renders with extra grounded-looking rationale —
  arguably worse than the review describes.

### F2 — TRUE

- Probe reproduced at medium, exact mechanism per review.
- SKILL.md has no division-of-labor statement: the script is introduced
  only as "The script form:" (line 47); no stage says the output is a
  lexical prior, no override license, no override-logging instruction.
  The only judgment-adjacent prose is the `/which-skill` boundary
  (lines 124-130), which is about a different skill.
- Both review-named failure modes are structurally live: nothing forbids
  rubber-stamping, nothing licenses/records overrides.

### F3 — TRUE

- SKILL.md "## Forms" (lines 39-54) is three example invocations plus the
  script form. Zero guidance on composing the task string from
  conversation context. `route()` (route.py:292-303) consumes only the
  literal string via `tokenize(task)`.
- The review's example mechanics check out: "keeps", "again", "back" are
  REGRESSION_CUES (route.py:51) and regression-prevention strong/normal
  cues (shapes.yml:137-138); a paraphrase to "fix the export bug" hits
  only BUG_CUES. Paraphrase choice flips the route.

### F4 — TRUE (one sentence overstated; see nuance)

(a) Doc drift — TRUE:
- SKILL.md lines 87-97: heading "V1 shapes:" + nine ids (project-intake,
  direct-change, bug-fix, feature-shaping, legacy-stabilization,
  health-audit, refactor-execution, regression-prevention,
  decision-capture).
- shapes.yml has ELEVEN: the nine above plus `concept-rename`
  (shapes.yml:33-46) and `task-closeout` (shapes.yml:157-171).
- Frontmatter description (SKILL.md line 3) "such as" list names seven;
  omits concept-rename and task-closeout (and direct-change /
  feature-shaping — it is explicitly a "such as" list, so only the two
  registry-newcomer omissions align with the review's point).
- Provenance nuance: `git log --follow shapes.yml` shows ONE commit
  (393566c "Initial public release") — both "new" shapes were in
  shapes.yml at initial release. The drift is not from later additions
  via the documented process; SKILL.md and the scorer were stale at
  birth. The review's "newly added" framing is a plausible pre-release
  history reconstruction, but in this repo's history the documented
  add-a-shape process has never actually been exercised.

(b) Scorer handicap — TRUE:
- Boost branches at route.py:169-207, exactly nine `if/elif sid == ...`
  arms: project-intake (169-180, conditional ±36/±18/−30), direct-change
  (+34, 181), bug-fix (+30, 184), legacy-stabilization (+30, 187),
  health-audit (+30, 190), regression-prevention (+30 +8 combo, 193-198),
  decision-capture (+34, 199), feature-shaping (+26, 202),
  refactor-execution (+24, 205). `concept-rename` and `task-closeout`
  have NO branch — confirmed by reading every arm.
- `--validate` runs clean today (`shapes OK`) and checks only schema
  (validate_shapes_payload, route.py:71-106); no boost-coverage check
  exists anywhere.
- Nuance — "can almost never win" is slightly overstated: a clean-cue
  probe wins for the unboosted shape:
  `route.py --skip-log "rename the domain concept across the glossary and all surfaces"`
  → `Concept Rename, confidence medium (score=28)`. The accurate
  statement: unboosted shapes lose any contest where a boosted
  competitor lands even one strong cue (12+30 ≥ 42 vs 12+8ish), and they
  are effectively CAPPED AT MEDIUM — reaching high (≥40) requires 4+
  strong-cue hits at +12 each (minus the −4 context penalty), which no
  realistic prompt produces, while any boosted shape reaches high from a
  single strong token ("bug" alone = 42).

### F5 — TRUE on substance, PARTLY on one supporting sentence

- `--outcome` default is `"useful"`: route.py:413. Logged at
  recommendation time via `log_recommendation` (route.py:373-395),
  `event_kind="recommendation"`, extras: shape, confidence,
  project_context_state, recommended_first_skill. (skill_use.py
  `log_event` also defaults outcome="useful" at its own line 23, but
  route.py always passes explicitly.)
- Correction path is indeed "re-run the same command with
  `--outcome overridden`" (SKILL.md lines 115-122). Re-running APPENDS A
  SECOND recommendation event — there is no amend; a corrected route
  therefore counts n=2, overridden=1 → 50% in compaction, and an
  uncorrected one n=1, 0%.
- PARTLY: "nothing downstream in the session consumes that step" — a
  downstream consumer DOES exist outside the session: compact.py:148-174
  renders a per-shape `overridden%` table from recommendation events,
  and project.py:187-230 summarizes them. What is true and load-bearing:
  no in-session mechanism ever triggers the rerun, and with default
  `useful` the overridden% metric is structurally biased toward 0%. The
  review's net conclusion ("the log is structurally biased to report
  useful") stands.
- Also verified TRUE as SKILL.md claims: recommendation events ARE kept
  out of per-skill useful rates (project.py:229 states it; both files
  split on `event_kind == "recommendation"` — compact.py:64-70,
  project.py:65-71; covered by
  tests/test_which_shape.py::test_recommendation_events_do_not_pollute_skill_useful_rate).
- Fix-shape note: a neutral default (e.g. `unscored`) must be added to
  the argparse `choices` list (route.py:413); compact.py/project.py only
  special-case "overridden" (and "useful" for run events), so a new
  outcome value flows through their Counters without code changes, but
  the overridden% denominator semantics should be re-checked at
  compact.py:160-174 when the default changes.

### F6 — TRUE

- Nothing in SKILL.md requires the script to run. The invocation is
  introduced as "The script form:" (line 47) — grammatically one form
  among the slash-command examples above it. No "must run", no
  evidence-paste requirement, no `evidence_required` frontmatter key
  (frontmatter is lines 1-29; it has `produces: [shape_recommendation]`
  but nothing ties that to script execution).
- The "## Output" section (66-74) enumerates exactly the fields
  `render_markdown` emits — shape id/title, confidence, rationale, first
  next, loop, stop, alternatives — a complete fabrication template, as
  claimed.
- The review's proposed un-fakeable artifact lines exist verbatim in
  `render_markdown`: `Project context: ...` is built at route.py:348-350,
  `Confidence: {confidence} (score={N})` at route.py:353. A fabricator
  cannot know the live score integer or the context booleans without
  running.
- Compounding-F5 point confirmed: skipping the run also skips
  `log_recommendation` (only called from `main()`, route.py:428-435).

---

## 2. Edit anchors (smallest fixes; no code written here)

### SKILL.md (all anchors by current line numbers)

| Fix | Anchor |
|---|---|
| F1 low-confidence gate | "## Output" section, after the field list (insert after line 74, before "## Registry" line 76). Rule keys off `Confidence: low` and/or rationale "fallback shape candidate". |
| F2 lexical-prior / override license | Insert a short stage between the script form block (ends line 54) and the status-projection paragraph (line 56) — or as its own `## Judgment` section before "## Output" (line 65). Must license override + require naming the cue collision + require logging it (ties to F5's `--outcome overridden` path). |
| F3 pre-run inventory | "## Forms" section, before the example block (after line 39 heading, before line 41 fence) — 3-line checklist of discriminating dimensions (recurrence / approved proposal / unknown-inherited repo / scope width / durable choice) to carry verbatim into the task string. These five dimensions map 1:1 to the cue families at route.py:45-54. |
| F4(a) shape list | Delete lines 87-97 ("V1 shapes:" + nine bullets) in "## Registry"; replace with a pointer to shapes.yml as sole inventory. Also frontmatter `description:` (line 3): drop or regenerate the "such as" enumeration. |
| F5 rerun ritual | "## Telemetry" section lines 109-122 — rewrite the feedback paragraph/example (lines 115-122) per chosen fix shape. |
| F6 run-required artifact | Same Forms/Output area as F1/F2: change "The script form:" (line 47) to a mandate, and add "paste the script's `Project context:` and `Confidence: ... (score=N)` lines verbatim in your reply". |

### route.py

| Fix | Anchor |
|---|---|
| Boost branches (F4b) | `_score_shape`, route.py:152-211; the nine arms are 169-207. New arms for `concept-rename` / `task-closeout` would slot before the final `if context_missing` penalty (line 209). |
| Cue constants | route.py:45-54 (module level) — the parallel cue registry any fix must reckon with (see §3). |
| `narrow` computation | route.py:167 (`DIRECT_CUES | BUG_CUES | DECISION_CUES | REGRESSION_CUES`). |
| Context-missing exemption set | route.py:209 (hard-coded `{"project-intake", "direct-change", "bug-fix", "decision-capture"}`). |
| --validate coverage check | Two candidate seams: (i) inside `validate_shapes_payload` (route.py:71-106) — but it currently has no knowledge of scorer internals; (ii) the `--validate` branch in `main()` (route.py:418-421), comparing shapes.yml ids against a new module-level constant/dict of boosted ids that `_score_shape` also dispatches from. Seam (ii) keeps schema validation pure-data. |
| --outcome default (F5) | route.py:413 (`choices=[...], default="useful"`). New neutral value must be added to `choices`. SKILL.md Telemetry section must change in the same commit. |
| Confidence thresholds (F1 context) | route.py:311 — no change needed for the smallest F1 fix (which is SKILL.md-side), but it is the number the gate keys off. |

### Tests

- `tests/test_which_shape.py` — 18 tests; routing tests at lines 32-57
  cover the nine boosted shapes' cues only; NO test routes to
  `concept-rename` or `task-closeout` (grep confirms zero mentions).
  Any F4(b) fix should add routing tests for both, and the F5 fix will
  interact with `test_recommendation_events_do_not_pollute_skill_useful_rate`
  (line 68) and `test_compaction_summarizes_recommendations_separately`
  (line 231).
- `tests/test_ecosystem_consistency.py` writes its own minimal shapes.yml
  fixture (line 50) — schema additions (Path A below) would touch it.

---

## 3. Fix-shape decision input for F4(b)

### Path A — move boost weights into shapes.yml (data-driven)

What it touches, factually:

1. **shapes.yml** — 11 entries gain boost data (e.g. weight + rationale
   string). The 8 simple cases (direct-change +34, bug-fix +30,
   legacy +30, health +30, decision +34, feature +26, refactor +24,
   regression +30) are pure data. Two are NOT pure data:
   - `regression-prevention` has a compound boost: +8 extra when
     BUG_CUES also hit (route.py:196-198) — cross-shape cue reference.
   - `project-intake` is conditional on runtime context state AND the
     cross-shape `narrow` computation (route.py:169-180): three branches
     (+36 / +18 / −30) keyed on `context_missing`, `intake_hits`,
     `forced`, `narrow`. Expressing this as YAML requires a mini-DSL or
     keeping it as the one hard-coded special case.
2. **validate_shapes_payload** (route.py:71-106) — new schema rules for
   the boost keys (~10-20 lines).
3. **_score_shape** (route.py:152-211) — rewrite the nine elif arms into
   a data read (~30-50 lines changed); the boost cue-sets currently come
   from the module constants, not the YAML (see drift note below), so
   the fix must decide whether boost triggers = the shape's own `strong`
   cues (cleanest; mostly true today) or a separate cue list.
4. **Module cue constants** (route.py:45-54) — partially dissolvable,
   but DIRECT_CUES/BUG_CUES/DECISION_CUES/REGRESSION_CUES remain needed
   for `narrow` (line 167) and project-intake logic; BUG_CUES also feeds
   the regression combo. These constants have ALREADY drifted from the
   YAML strong-cue lists (see §4 drift table) — Path A forces resolving
   that drift.
5. **Context-missing exemption set** (route.py:209) — same per-shape-data
   problem; consistent Path A also moves it to YAML (one more schema key).
6. **Tests** — test_which_shape.py routing tests re-verified;
   test_ecosystem_consistency.py fixture updated for new schema.

Realistic size: ~80-120 changed lines across route.py + shapes.yml, plus
two test files. Risk concentrates in project-intake's conditional logic.

### Path B — `--validate` boost-coverage check + hand-written arms for the two missing shapes

What it touches, factually:

1. **route.py** — a module-level registry of boosted ids (constant set,
   or a small dict if the simple boosts are tabled) that `_score_shape`
   dispatch and the validator share; the check itself (every shapes.yml
   id ∈ boosted ∪ declared-exempt) in the `--validate` path
   (route.py:418-421). ~15-25 lines.
2. **route.py** — two new boost arms for `concept-rename` and
   `task-closeout` (~10-14 lines) with weights/cue-sets chosen. Without
   these, Path B only makes the drift loud; it does not fix the Probe B
   misroute or the medium-confidence cap.
3. **Tests** — two new routing tests + one validate-coverage test.

Realistic size: ~30-45 lines in route.py + ~25 test lines. Leaves the
parallel cue-constant registry, the exemption set, and the documented
"edit shapes.yml to add a shape" story (SKILL.md lines 81-85,
check-ecosystem-consistency) still pointing at a file that cannot, by
itself, produce a competitive shape — the structural cause survives,
fenced by a loud check.

Shared fact for either path: the SKILL.md "Registry" prose (lines 78-85)
says shapes live in shapes.yml and routes new-skill review through
`/check-ecosystem-consistency`, whose own SKILL.md (line 61) audits
"`/which-shape/shapes.yml` schema and referenced skill slugs" — neither
mentions the scorer. Path A makes that documented story true; Path B
amends the story (the add-a-shape process must mention the scorer/validate
step).

---

## 4. Pointer + artifact-drift audit (SKILL.md references vs reality)

| SKILL.md reference | Reality | Drift? |
|---|---|---|
| `.venv/bin/python .claude/skills/which-shape/scripts/route.py` (lines 50, 118) | Script exists; `.venv/bin/python` exists; plain `python3` also works (PyYAML 6.0.2 system-wide) | OK |
| `--json`, `--skip-log` (line 54) | Both in argparse | OK |
| `--outcome overridden`, `--human-override` (lines 120-121) | Both in argparse | OK |
| `--status <path>` (line 63) | In argparse, route.py:405-409 | OK |
| `.engineering/local/status.json`, ADR 0037, `scripts/status.py` (lines 56-58) | File exists; `ai-docs/decisions/0037-status-projection-schema.md` exists; `scripts/status.py` exists | OK |
| `shapes.yml` (line 78) | Exists, validates | OK (content drift = F4a) |
| "V1 shapes" list (87-97) | 9 listed vs 11 in registry | **DRIFT (F4a)** |
| Frontmatter description "such as" list (line 3) | omits concept-rename, task-closeout | **DRIFT (F4a)** |
| `.engineering/project/adapter.yml` / `profile.yml` / `open-questions.md` (101-103) | Directory absent in this repo; SKILL.md says "when present" and route.py treats absence as `state: missing` | OK (conditional) |
| `.claude/skill-use/log.jsonl` (line 112) | Exists | OK |
| `/check-ecosystem-consistency` (line 82) | Skill exists; its SKILL.md audits shapes.yml slugs | OK |
| `/which-skill`, `/project-interview` (19, 126-127) | Skills exist | OK |
| `--validate` | **Exists in script, never mentioned in SKILL.md** | **REVERSE DRIFT (new, minor)** — the registry-edit workflow (lines 81-85) never tells the editor to run it |
| `agents/openai.yaml` | Exists (display metadata only); not referenced by SKILL.md, references nothing stale | OK |
| `allowed-tools: Bash, Read` (line 5) | Consistent with a run-the-script skill | OK |

Code-internal drift found (new, feeds F4b):
**Module cue constants vs shapes.yml strong cues** (route.py:45-54):
- `BUG_CUES` adds `crash` (a bug-fix NORMAL cue in YAML)
- `REGRESSION_CUES` adds `regression`, `back` (YAML normal cues)
- `FEATURE_CUES` adds `new` (YAML normal cue — and `new` is a NEGATIVE
  cue for bug-fix, regression-prevention, task-closeout)
- `REFACTOR_CUES` adds `extract`, `split` (YAML normal cues)
- `PROJECT_INTAKE_CUES` mixes strong+normal; `INTAKE_FORCE_CUES` =
  YAML strong set
- `DIRECT_CUES`, `LEGACY_CUES`, `HEALTH_CUES`, `DECISION_CUES` =
  exact copies of the YAML strong sets
Net: a second, independently-driftable cue registry lives in the scorer.
Boost triggering is therefore not even consistently "strong-cue hit" —
e.g. "crash" alone triggers the bug-fix +30 boost off a normal cue.

---

## 5. Load-bearing audit (every mandated/implied step → consumer)

| Step (SKILL.md) | Consumer of its output | Verdict |
|---|---|---|
| Run the script (line 47-54) | Orchestrator's routing choice; telemetry event | **Not actually mandated** — F6. The one load-bearing step is optional. |
| `--json` for machine-readable output (54) | None wired anywhere in-repo (no caller parses route.py JSON besides tests) | Optional affordance, fine |
| Status-projection paragraph (56-64) | Implemented end-to-end (load_status_signals route.py:237-289; 4 tests) | Load-bearing, healthy |
| Output field list (66-74) | The reply the user reads | Load-bearing, but doubles as fabrication template (F6) |
| Registry edit + `/check-ecosystem-consistency` on skill changes (81-85) | check-ecosystem-consistency audits shapes.yml slugs/schema | Partly load-bearing; but the documented process omits the scorer (F4b) and never says to run `--validate` (new minor) |
| "V1 shapes" list (87-97) | Nothing consumes it; shapes.yml is what the script reads | **Pure ceremony + actively wrong (F4a)** — delete |
| Project Context section (99-107) | Implemented by project_context_state + scorer | Load-bearing, healthy (review credits this) |
| Telemetry logging (109-113) | compact.py overridden% table; project.py shape section | Consumer exists |
| Feedback rerun with `--outcome overridden` (115-122) | compact.py/project.py would consume it, BUT no in-session trigger exists, default poisons the base rate, and the rerun appends a second event (n inflation) rather than amending | **Ceremony in practice (F5)** — executes ~never; metric biased to 0% overridden |
| max_overhead contract (frontmatter 28, body 37) | Constrains the executor's reply | Load-bearing belief, stated thrice (frontmatter, line 37, route.py docstring) — healthy |

---

## New defects beyond the review (summary)

1. **`--validate` undocumented** — SKILL.md's registry-edit workflow never
   instructs running it (route.py:410; SKILL.md lines 81-85).
2. **Parallel cue registry drift** — route.py:45-54 constants vs
   shapes.yml strong cues (crash/regression/back/new/extract/split
   discrepancies); boost triggers are not consistently strong-cue-based.
3. **Feedback rerun inflates n** — correction appends a second
   recommendation event; compaction counts both (n=2, overridden=1 →
   50%, not 100%). Any F5 fix touching the ritual should note this.
4. **Status signals decorate fallbacks** — projection rationale lines
   append to ANY winner including a score-0 fallback (route.py:321),
   making Probe A's arbitrary route look more grounded (aggravates F1).
5. **Hard-coded per-shape data beyond boosts** — the `narrow` cue union
   (route.py:167) and the context-missing exemption set (route.py:209)
   are two more shape-knowledge tables living in code that new shapes
   never join; same structural cause as F4(b).
6. **Test gap** — zero routing tests for concept-rename / task-closeout
   (tests/test_which_shape.py); the structural handicap was invisible to
   the suite.

## History note

`git log --follow shapes.yml` shows both "missing" shapes present since
the initial public release commit (393566c); route.py has had one change
since (109a418, status grounding). The doc/scorer drift shipped at birth;
the documented add-a-shape process has never been exercised in-repo.
