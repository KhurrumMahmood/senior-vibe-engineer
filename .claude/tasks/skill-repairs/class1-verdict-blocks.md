# Class 1 verdict-block verification — 34 SKILL.mds

Date: 2026-06-12. Scope: the 34 `## How success is judged` blocks
inserted per `class-sweeps-spec.md` (Class 1 hit table + family
templates), exemplar `.claude/skills/repair-skill/SKILL.md:45`.
fix-workflow and prevent-regression are owned by parallel agents and
were not touched.

Method: for every concrete noun each block cites (artifact path,
report file, handoff skill, status value, script name, stage/step
reference, bucket vocabulary), the same SKILL.md's pre-insertion body
(`git show HEAD:<file>`) was grepped to confirm the body mandates it.
~10-15 tokens checked per skill (≈330 total); the table below cites
the most load-bearing gate per skill. Line numbers are HEAD (pre-block)
line numbers in each skill's `SKILL.md`.

## Citation table (worst-gate verdict per skill)

| Skill | Representative gate checked | Grounded at (HEAD line) | Verdict |
|---|---|---|---|
| find-duplication | `scout/<finding_id>.json` Stage 4 verdicts; `ranked.json`→`classified.json`; `/fix-workflow cluster:` | 102 | GROUNDED |
| find-semantic-duplication | `capability_matrices/<finding_id>.md`; Stage 5 Confirm gate; `semantic:` IDs | 172 | GROUNDED |
| find-dormant | `scout/<candidate_id>.json` + 4 buckets; `external_api_risk`; `delete:`/`fix:` handoff | 133 | GROUNDED |
| find-omnibus | bucket vocab incl. `facets_not_domains`; ADR 0032 rule 3 substrate gate; both handoffs | 38, 134-135, 216 | GROUNDED |
| find-query-mutation | 4-bucket vocab incl. `false_positive_stdlib_wrapper`; `# hidden-mutation:`; `cluster:<symbol>` | 32, 109 | GROUNDED |
| find-implicit-state | 4-bucket vocab incl. `introduce_fk_candidate`; `/extract-enum` + `/introduce-fk` routing | 31, 106 | GROUNDED |
| find-layer-violation | 4-bucket vocab incl. `intentional_http_coupling`; `layer:<candidate_id>` | 42, 121 | GROUNDED |
| find-transaction-overreach | `# atomic-overreach:` marker; `on_commit` deferral; report/`findings.json` agreement | 82, 115 | GROUNDED |
| find-frontend-duplication | `cotton-inventory.json` comparison; `classified.json`; both handoffs | 76, 121 | GROUNDED |
| find-orphaned-ideas | seven modes; `--apply-stale` `transition` events; Stage 3 re-runs Stage 1 ("0 stale findings") | 49, 81, ~328 | GROUNDED |
| find-incomplete-sweep | `scout_packets.json`, Step B vocab, `triaged.md`, `--no-gate` all grounded; **"Stage 0" INVENTED** (skill uses Steps A-C, no Stage 0) | 162 (gates); Stage 0: none | FIXED |
| extract-enum | `models.TextChoices` (never tuple choices); `profile.md` caller table; Follow-on findings | 30, 44 | GROUNDED |
| extract-state-type | `knowledge/proposal-template.md`; characterization-test section; one-target rule | 39 | GROUNDED |
| extract-cotton-primitive | `defer_low_callsite_count` below three-callsite threshold; Stage 3 proposal structure | 43, 47, 195 | GROUNDED |
| introduce-fk | two-step migration; tie-break strategy; `latest_query`/`unique_hit` respect | 63 | GROUNDED |
| propose-folder-reorganization | `defer_below_threshold` (ADR 0006); `inspection.json`; `defer_signals` | 72 | GROUNDED |
| unify-shadows | `consolidation_shape` respected; `profiles/<member-key>.md`; INTENTIONAL-shadow comments | 40, 144 | GROUNDED |
| explain-code | `annotations/<symbol-key>.md`; 15-symbol cap; `reports/explanations/<target-slug>.md` | 106, 164 | GROUNDED |
| scope-feature | Stage 0.5 inferred-answer confirmation; Q1-Q5; binding priors; status `scoped` | 97, 122-123 | GROUNDED |
| impact-feature | `${REPORT_DIR}/scout/<subsystem>.md`; STOP on scope mismatch; status `impacted` | 52-53, 64 | GROUNDED |
| architecture-fit | three checks vs §3 map; §6 fork surfacing; status `architected`; no-spec rule | 37, 42 | GROUNDED |
| plan-spec | ABORT on P0 forks; `successor_spec:`/Provenance bidirectional link; `plans.py promote` | 36 | GROUNDED |
| plan-feature | `motivating_decision` stubs; 2+ workflow ESCALATE; grounding in `context.md`/`impact.md` | 55, 75 | GROUNDED |
| plan-skill | `evidence_gate.py` four-item gate; seven Stage 2 attacks (verified: 7 numbered); both .md artifacts | 46, Stage 2 list | GROUNDED |
| decide | Stage 3 `decisions.py audit` + `link-check`; duplicate→`--amend`/supersession abort | 239, 311 | GROUNDED |
| design-it-twice | `scan-<TS>/<fork-slug>.md` comparative doc; Stage 1 axes stated-and-justified | 44, 109-124 | GROUNDED |
| map-subsystem | doc-complete per `knowledge/output-format.md` and `--refresh` diff grounded; **"nothing outside the doc written" INVENTED** (body mandates `reports/map/<name>/` scratch + `reports/_meta/effectiveness.jsonl`) | 39; conflict at 110, 205 | FIXED |
| teach-pattern | "None yet — file a `/decide`" enforcement gap; five grounded sections | 63, 182 | GROUNDED |
| brainstorm-ideas | `convo+research` origin; `--external-research`; helper-script-only writes; `subsystem_kind` | 57 | GROUNDED |
| extract-existing-ideas | NEW vs WOULD-COLLIDE classification; `brainstorm.py` handoff; `--write` review gate | 127 | GROUNDED |
| mature-existing-ideas | `research:`-prefixed `note` events; source citation; `/track-idea event` routing | 53, 238, 244 | GROUNDED |
| harvest-learnings | `single-constraint-set` caveat; "zero stayed-home → re-run Stage 3"; ADR-0020 tags | 76, 119, 147 | GROUNDED |
| gut-check | confidence bands; `decided-but-still-smell` split; `precedents.yml`-absent disclosure | 90, 123, 193-195 | GROUNDED |
| orient | `.engineering/project-state.json`; maturity + stakes; confirm-before-write | 51, 173 | GROUNDED |

Totals: 32 GROUNDED, 2 INVENTED→FIXED, 0 VAGUE (every block names its
skill's concrete artifacts; none is family boilerplate that could apply
to a sibling).

## Blocks fixed (2, smallest edits)

1. `.claude/skills/find-incomplete-sweep/SKILL.md` — trailing line
   `Write toward these gates from Stage 0.` cited a stage that does
   not exist (the skill is structured as detector pre-filters then
   Steps A/B/C under "Scout stage"). Replaced with
   `Write toward these gates from the first detector run.`
2. `.claude/skills/map-subsystem/SKILL.md` — gate
   "Nothing outside `.claude/docs/subsystems/<name>.md` was written"
   contradicted the body, which mandates a `reports/map/<name>/`
   scratch dir (line 110) and an effectiveness-log append to
   `reports/_meta/effectiveness.jsonl` (line 205). Replaced with
   "Beyond the doc, writes are limited to the `reports/map/<name>/`
   scratch dir and the `reports/_meta/effectiveness.jsonl` line."

No blocks were rewritten wholesale.

## Near-misses resolved as grounded (not fixed)

- extract-cotton-primitive "three-callsite" — capitalized
  "Three-callsite, two-template rule" (line 43).
- scope-feature "binding priors" — "most binding on THIS scope"
  (lines 122-123) + "Prior constraints" subsection.
- plan-skill "seven attacks" — Stage 2 lists exactly 7 numbered
  attack questions.
- decide "duplicate" — failure-mode row at line 311 (existing
  decision → abort into `--amend`/supersession).
- mature-existing-ideas "cited" — "Cite the sources" (line 59),
  citation list mandate (lines 238, 244).
- explain-code `<symbol-key>` — exact body token at line 164.
- find-omnibus body says "three buckets" (line 37) while listing and
  using four (lines 134-135); pre-existing body inconsistency, block
  matches the operative four-bucket vocabulary.

## Placement and diff hygiene

- All 34 blocks sit after the intro prose and before the file's first
  structural section (`## Core beliefs` where present; otherwise
  `## Scope` / `## Bands` / the first Stage heading) — matching the
  repair-skill exemplar shape.
- `git diff` per file: exactly 1 hunk, 0 deletions, in all 34 files —
  no non-block hunks found. (Other working-tree changes —
  `scripts/skill_comply/*`, `tests/test_skill_comply.py`, fix-workflow
  task dir — belong to parallel agents and were not touched.)

## Lint

```
$ .venv/bin/python scripts/skill_meta.py lint
OK — 74 skills, 74 declaring new contract
```
