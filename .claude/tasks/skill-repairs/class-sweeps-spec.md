# Class-lift sweeps — batch-fix spec

Date: 2026-06-12. Scope: all 74 `.claude/skills/*/SKILL.md`. Read-only
detector pass; no SKILL.md was edited. Paths are repo-relative.

Three defect classes from this session's repairs, swept catalog-wide per
the class-lift gate. Raw counts up front:

| Class | Raw candidates | Confirmed hits | Exempt / FP |
|---|---|---|---|
| 1 — missing declared-verdict block | 73 lack the string; 47 are multi-stage | **41** | 31 exempt, 2 already have it |
| 2 — ceremony stages | 45 skills sample-read (≥4 stages) | **4** (+3 borderline) | 29 skills under threshold, not examined |
| 3 — dispatch/write contract mismatch | 18 mechanical flags | **2** (+1 borderline) | 15 false positives |

---

## Class 1 — missing declared-verdict block

Repaired exemplars: `.claude/skills/repair-skill/SKILL.md:45`
(`## How success is judged`) and
`.claude/skills/refactor-subsystem/SKILL.md:34` (inline bold variant).

### Detector commands

```bash
# Step 1 — string absence (73/74 hit; only repair-skill + refactor-subsystem have it)
grep -L "How success is judged" .claude/skills/*/SKILL.md

# Step 2 — equivalent-section absence (only rename-concept/repair-skill match; converge has a verdict contract)
grep -lEi "how success is judged|^##+ +success criteria|^##+ .*verdict" .claude/skills/*/SKILL.md

# Step 3 — staged-structure filter (45 skills have >=4 stage headers)
for f in .claude/skills/*/SKILL.md; do
  n=$(grep -cE "^#{2,3} +(Stage|Phase|Step) " "$f"); [ "$n" -ge 4 ] && echo "$n $f"
done | sort -rn
# plus 2 bold-text staged pipelines the header count misses:
# propose-boundary (5 "Stage N —" bold stages), propose-folder-reorganization (4)
```

Raw counts: 73 skills lack the string; 45 + 2 bold-staged = 47
multi-stage candidates; minus 2 that already have the block, minus 4
exempt within the staged set = **41 hits**.

### Hits (41) — citation is the first pipeline/stage header; fix is one line each

Fix template by family — add a 4-8 line `## How success is judged` block
after the intro, naming the gates the run will face:

- **SUSPECT fan-out scanners** — "report at the scan dir with every
  candidate carrying a scout verdict + evidence; zero silent drops;
  handoff IDs resolvable by the named downstream skill."
- **EXPLAIN proposal skills** — "proposal complete per template (incl.
  migration table + stop condition); zero production edits; defer
  signals honored."
- **Plan-chain skills** — "required plan/spec sections filled with
  grounded content; status field advanced; gate refusals explicit."
- **Meta/ideas skills** — per-skill line below.

| Skill | Citation | Smallest fix (one line) |
|---|---|---|
| find-duplication | `.claude/skills/find-duplication/SKILL.md:37` | SUSPECT template: triage.md verdict per cluster, evidence quoted, P0 IDs valid for /fix-workflow |
| find-semantic-duplication | `.claude/skills/find-semantic-duplication/SKILL.md:43` | SUSPECT template: capability matrix per confirmed cluster; confirming-scout pass required before report |
| find-dormant | `.claude/skills/find-dormant/SKILL.md:55` | SUSPECT template: every deletion candidate carries call-site evidence + recency check; no unilateral deletes |
| find-omnibus | `.claude/skills/find-omnibus/SKILL.md:59` | SUSPECT template: each candidate scored by facet-vs-domain rule; decomposition handoff named |
| find-query-mutation | `.claude/skills/find-query-mutation/SKILL.md:47` | SUSPECT template: every hit bucketed (rename/split/warming/FP) by a scout, none dropped |
| find-implicit-state | `.claude/skills/find-implicit-state/SKILL.md:47` | SUSPECT template: each candidate routed to /extract-enum or /introduce-fk with evidence |
| find-layer-violation | `.claude/skills/find-layer-violation/SKILL.md:71` | SUSPECT template: authority judgments per entry point; extract-service candidates actionable |
| find-transaction-overreach | `.claude/skills/find-transaction-overreach/SKILL.md:53` | SUSPECT template: findings.json + report agree; each finding has span evidence |
| find-frontend-duplication | `.claude/skills/find-frontend-duplication/SKILL.md:50` | SUSPECT template: candidates compared against cotton inventory; handoff to /extract-cotton-primitive valid |
| find-standard-gaps | `.claude/skills/find-standard-gaps/SKILL.md:80` | SUSPECT template: portability verdict per candidate; coverage cells enumerated |
| find-orphaned-ideas | `.claude/skills/find-orphaned-ideas/SKILL.md:230` | SUSPECT template: per-mode findings separated; no write without --apply-stale |
| find-incomplete-sweep | `.claude/skills/find-incomplete-sweep/SKILL.md:152` | SUSPECT template: one rubric verdict per packet, forgotten-first triaged.md, rationale per leave |
| extract-enum | `.claude/skills/extract-enum/SKILL.md:117` | EXPLAIN template: proposal with enum class + caller table + data-migration risks; read-only |
| extract-state-type | `.claude/skills/extract-state-type/SKILL.md:117` | EXPLAIN template: shape table + caller-by-caller plan + characterization matrix; read-only |
| extract-cotton-primitive | `.claude/skills/extract-cotton-primitive/SKILL.md:104` | EXPLAIN template: c-vars decl + callsite migration table + stop condition; read-only |
| introduce-fk | `.claude/skills/introduce-fk/SKILL.md:134` | EXPLAIN template: FK shape + two-step backfill + tie-break strategy; read-only |
| propose-boundary | `.claude/skills/propose-boundary/SKILL.md:125` | EXPLAIN template: seams + public API + shim shape; defer signals recorded in frontmatter |
| propose-folder-reorganization | `.claude/skills/propose-folder-reorganization/SKILL.md:125` | EXPLAIN template: move table satisfies ADR 0006 thresholds; read-only |
| unify-shadows | `.claude/skills/unify-shadows/SKILL.md:106` | EXPLAIN template: shadow pairs proven equivalent or divergence documented; read-only |
| explain-code | `.claude/skills/explain-code/SKILL.md:111` | EXPLAIN template: every public symbol annotated or listed unexplained; no invented behavior |
| scope-feature | `.claude/skills/scope-feature/SKILL.md:77` | Plan-chain template: §1-2 filled from answered questions, status `scoped`, open unknowns named |
| impact-feature | `.claude/skills/impact-feature/SKILL.md:68` | Plan-chain template: one scout per touched subsystem, §3-4 filled, status `impacted` |
| architecture-fit | `.claude/skills/architecture-fit/SKILL.md:76` | Plan-chain template: every material fork surfaced in §6, status `architected` |
| plan-spec | `.claude/skills/plan-spec/SKILL.md:70` | Plan-chain template: refuse on unresolved P0 forks; spec scaffolded; plan `promoted` |
| plan-feature | `.claude/skills/plan-feature/SKILL.md:112` | Plan-chain template: spec sections grounded in context.md/impact.md, not invented |
| plan-skill | `.claude/skills/plan-skill/SKILL.md:52` | Plan-chain template: surface adversarial pushback + evidence manifest gates as the run's verdict |
| decide | `.claude/skills/decide/SKILL.md:126` | Plan-chain template: ADR passes decisions.py lint, backrefs checked, no duplicate decision |
| design-it-twice | `.claude/skills/design-it-twice/SKILL.md:86` | Plan-chain template: 3 designs with genuinely different binding constraints + comparative recommendation |
| fix-workflow | `.claude/skills/fix-workflow/SKILL.md:119` | Verdict: regression test first and green, behavior-preserving commit separate from bug-fix commit, matrix run |
| prevent-regression | `.claude/skills/prevent-regression/SKILL.md:191` | Verdict: guard artifact + verification recipe emitted; never installed unilaterally |
| diagnose | `.claude/skills/diagnose/SKILL.md:47` | Verdict: trusted repro loop demonstrated before any fix; surface `evidence_required` (already in frontmatter) as the body block |
| audit-decisions | `.claude/skills/audit-decisions/SKILL.md:77` | Verdict: drift.md row per symptom with next command; registry untouched |
| map-subsystem | `.claude/skills/map-subsystem/SKILL.md:102` | Verdict: inventory doc complete (files/surface/deps/compliance score); no refactor intent leaked |
| triage-debt | `.claude/skills/triage-debt/SKILL.md:86` | Verdict: queue.md ranked with score rationale per entry; inputs declared |
| teach-pattern | `.claude/skills/teach-pattern/SKILL.md:82` | Verdict: all 5 briefing sections grounded in real artifacts (no invented exemplars) |
| brainstorm-ideas | `.claude/skills/brainstorm-ideas/SKILL.md:88` | Verdict: candidates deduped against ledger; survivors written via helper script only |
| extract-existing-ideas | `.claude/skills/extract-existing-ideas/SKILL.md:82` | Verdict: candidates JSON + report; writes only via brainstorm helper handoff |
| mature-existing-ideas | `.claude/skills/mature-existing-ideas/SKILL.md:121` | Verdict: research-log event appended per researched slug; markers cleared only with evidence |
| harvest-learnings | `.claude/skills/harvest-learnings/SKILL.md:80` | Verdict: each harvested lesson lands in exactly one capture tier with provenance |
| gut-check | `.claude/skills/gut-check/SKILL.md:163` | Verdict: every checklist dimension answered with evidence or marked not-run |
| orient | `.claude/skills/orient/SKILL.md:166` | Verdict: project-state.json written from observed signals, unknowns explicit |

### Exemptions (one line each)

Already have the block (baseline, not hits): `repair-skill` (SKILL.md:45),
`refactor-subsystem` (SKILL.md:34).

| Skill | Reason |
|---|---|
| converge | Verdict contract IS the output — Stage 3 "Emit the verdict" with fixed schema (SKILL.md:85) |
| engineer-init | Setup runbook; Stage 5 "Verify" (SKILL.md:186) is an executable smoke test, success is mechanical |
| which-skill | Lookup-table matcher; script ranks, orchestrator relays (SKILL.md:91) |
| query-patterns | Lookup-table query; in-memory match, conversational render |
| track-idea | Single-script append wrapper; validation is the script's job |
| which-shape | Script-backed router, no staged orchestration |
| which-cleanup | Script-backed router; one run.py call builds the closeout |
| check-ecosystem-consistency | Diff-audit script wrapper (Forms, not stages); `evidence_required` declared in frontmatter |
| rename-concept | v0 assess-only single script; has "## Stop condition"-class boundary already |
| adapt-project | Single-script scan; `evidence_required` declared in frontmatter |
| project-interview | Conversational interview, single-script backed; `evidence_required` declared |
| find-perimeter-gaps | 3-stage deterministic scan-and-relay, no judgment fan-out |
| extract-workflow-registry, map-product-workflow | Single-script EXPLAIN relays (0 stage headers) |
| find-async-lifecycle-drift, find-comment-drift, find-complexity-hotspots, find-concept-divergence, find-contract-drift, find-dead-route-surface, find-doc-route-drift, find-folder-topology-drift, find-frontend-contract-drift, find-route-sprawl, find-rule-surface-drift, find-skill-artifact-drift, find-skill-intent-drift, find-stale-artifacts, find-test-obligation-drift, find-workflow-duplication, find-workflow-state-gaps | Single-script SUSPECT scanners: deterministic scan writes the report, orchestrator relays; no scout judgment to grade |

### Coverage statement

All 74 SKILL.md files passed through Steps 1-3; staged-structure
classification verified by header counts plus a manual check of the two
bold-text pipelines (propose-boundary, propose-folder-reorganization)
and find-incomplete-sweep (3 Steps + scout fan-out → counted as hit).
Skills with "## Stop condition" sections (7) were kept as hits — a stop
condition bounds the run but does not state how it is graded.

---

## Class 2 — ceremony stages

### Detector

For every skill with ≥4 stage headers (the 45-skill roster from the
Class 1 Step 3 command), a sub-agent read the full SKILL.md, listed
every artifact each stage mandates writing, and searched for a consumer
(later stage, `scripts/` input — checked via
`grep -rn "<artifact>" .claude/skills/<name>/scripts/` — reply
contract / `evidence_required`, future runs of the same skill, or any
other skill via `grep -rn "<artifact>" .claude/skills/ scripts/`).
Five read-only sub-agent batches of 9 skills each; confident hits only.

### Confirmed hits (4)

1. **audit-decisions — `raw-drift.json` (Stage 5)**
   Producing stage: `.claude/skills/audit-decisions/SKILL.md:228` —
   "Write `raw-drift.json` … so the heuristic is debuggable and
   downstream skills (e.g., `/triage-debt`) can consume the structured
   form." Absence evidence: `/triage-debt` reads `decisions-audit.json`
   produced by running `python3 scripts/decisions.py audit --json`
   directly (`.claude/skills/triage-debt/SKILL.md:105`), never
   `raw-drift.json`; repo-wide grep finds no other reference. The
   stated consumer claim is false.

2. **triage-debt — `raw-scores.json` (Stage 2)**
   Producing stage: `.claude/skills/triage-debt/SKILL.md:184` — "Write
   per-candidate breakdowns to `${REPORT_DIR}/raw-scores.json`" (also
   promised in the output contract at SKILL.md:81). Absence evidence:
   no later stage, script, or skill reads it; `queue.md` does not
   reference it; repo-wide grep is writer-only.

3. **fix-workflow — `reports/duplication/learnings.md` append (Step 5)**
   Producing stage: `.claude/skills/fix-workflow/SKILL.md:235` —
   "Append a cluster entry to `reports/duplication/learnings.md`".
   Absence evidence: the file the skill actually *reads* is the
   skill-internal `knowledge/learnings.md` (SKILL.md:44, 263-265); the
   cross-cluster log has no reader in any stage, script, or other
   skill — the find-* SKILL.md mentions (e.g.
   `.claude/skills/find-duplication/SKILL.md:205`) are repository-layout
   listings, not reads.

4. **find-standard-gaps — `coverage.json` (Stage 1)**
   Producing stage: `.claude/skills/find-standard-gaps/SKILL.md:101` —
   "writes `coverage.md` (human report) and `coverage.json` (machine)."
   Absence evidence: Stage 2 (SKILL.md:107) reads only `coverage.md`;
   the only non-writer mention (`scripts/query_planner.py:24` in the
   skill dir) names it as a *future* consumer ("v1.0 layers those in
   once both substrates ship").

### Borderline — examined, not counted as hits

- **plan-spec `# Provenance` block** (SKILL.md:158): never parsed by
  `scripts/specs.py`, but it lives inside the spec document that
  `/refactor-subsystem` and the human read whole — consumed in the
  broad sense.
- **refactor-subsystem `phase-1-inventory-gate.md`** (SKILL.md:313):
  `knowledge/operations.md:157` names "1.5 delta count" as consumer,
  but §1.5 (SKILL.md:604) never wires the read explicitly —
  half-wired, not confidently dead.
- **extract-cotton-primitive `targets.json` / `profile.md`**
  (SKILL.md:39): the *inverse* defect — promised in the opening but
  never written by any stage (stages write `profile.json`,
  `census.json`, `primitive.md`, `proposal.md`). Belongs to the
  /find-skill-artifact-drift class; noted here for routing.

### Coverage statement

Examined (sample-read in full by a sub-agent): all 45 skills with ≥4
stage headers — teach-pattern, scope-feature, repair-skill,
map-subsystem, find-semantic-duplication, refactor-subsystem,
prevent-regression, plan-feature, converge, triage-debt, plan-spec,
mature-existing-ideas, impact-feature, fix-workflow,
find-frontend-duplication, find-duplication, extract-cotton-primitive,
engineer-init, diagnose, audit-decisions, architecture-fit,
unify-shadows, plan-skill, introduce-fk, harvest-learnings, gut-check,
find-transaction-overreach, find-query-mutation, find-orphaned-ideas,
find-omnibus, find-layer-violation, find-implicit-state, find-dormant,
extract-state-type, extract-existing-ideas, extract-enum, explain-code,
decide, brainstorm-ideas, which-skill, track-idea, query-patterns,
design-it-twice, orient, find-standard-gaps.

NOT examined for Class 2 (under the ≥4-stage threshold; 29 skills):
adapt-project, check-ecosystem-consistency, extract-workflow-registry,
find-async-lifecycle-drift, find-comment-drift,
find-complexity-hotspots, find-concept-divergence, find-contract-drift,
find-dead-route-surface, find-doc-route-drift,
find-folder-topology-drift, find-frontend-contract-drift,
find-incomplete-sweep, find-perimeter-gaps, find-route-sprawl,
find-rule-surface-drift, find-skill-artifact-drift,
find-skill-intent-drift, find-stale-artifacts,
find-test-obligation-drift, find-workflow-duplication,
find-workflow-state-gaps, map-product-workflow, project-interview,
propose-boundary, propose-folder-reorganization, rename-concept,
which-cleanup, which-shape.

---

## Class 3 — dispatch/write contract mismatches

Historical exemplar: scope-feature dispatched Explore agents with Agent
missing from allowed-tools — now fixed
(`.claude/skills/scope-feature/SKILL.md:5` includes `Agent`).

### Detector

Mechanical cross-check (stdlib Python over all 74 files): parse
frontmatter `allowed-tools`, then scan the body for (a) Agent signals
(`sub-agent`, `Dispatch a/one/fresh`, `fan-out`, `scout`, `spawn`,
`Agent(`), (b) Write signals (writes to `reports/`/`.claude/`/
`ai-docs/`, `Write` tool mentions, scaffold/append), (c) Edit signals
(`fill §`, `amend`, `update in place`), (d) Bash signals (```bash
fences, `scripts/*.py` invocations). Flag when the signal class has no
covering tool. Raw output: **18 flagged skills**; manual triage of every
flag below.

### Confirmed hits (2)

1. **find-incomplete-sweep — Agent missing**
   `allowed-tools: Bash, Read, Grep, Glob, Write`
   (`.claude/skills/find-incomplete-sweep/SKILL.md:16`). Body Step B
   (SKILL.md:172-173): "Dispatch one investigation per packet
   (`subagent_type=general-purpose`, batch in a single message…)" —
   that is the Agent tool. The inline-judging fallback exists for small
   sets only; the primary path is unexecutable as declared.
   Smallest fix: add `Agent` to allowed-tools.

2. **mature-existing-ideas — Agent missing**
   `allowed-tools: Bash, Read, WebSearch, WebFetch`
   (`.claude/skills/mature-existing-ideas/SKILL.md:5`). Body Stage 1.5
   (SKILL.md:189): "Delegate to a sub-agent with: — Sub-agent type:
   `general-purpose` by default…" — the `--adversarial` mode cannot run
   without the Agent tool.
   Smallest fix: add `Agent` to allowed-tools.

### Borderline hit (1)

3. **propose-boundary — Agent ambiguous**
   `allowed-tools: Bash, Read, Grep, Glob, Write`
   (`.claude/skills/propose-boundary/SKILL.md:5`). Body Stage 2
   (SKILL.md:163): "the orchestrator dispatches a cheap read-only scout
   (Bash + grep)". The dispatch mechanism is unnamed: if the Agent tool
   is intended, the tool is missing; if
   `_common/dispatch_scout_cheap.sh` is intended, Bash covers it but the
   body never says so.
   Smallest fix: name the dispatch path (`dispatch_scout_cheap.sh`) in
   Stage 2, or add `Agent`.

### False positives triaged (15, one line each)

| Skill | Flag | Why FP |
|---|---|---|
| architecture-fit | Agent | SKILL.md:130 describes what downstream `/design-it-twice` does, not its own dispatch |
| audit-decisions | Edit | SKILL.md:151 "amend the ADR" is a recommended next command for `/decide`, not this run |
| brainstorm-ideas | Agent | SKILL.md:229 names `/design-it-twice` fan-out as a contrast, not a mandate |
| decide | Agent | SKILL.md:325 "future scout sub-agents (if added)" — hypothetical |
| engineer-init | Write | "scaffolding" mentions are non-goals (SKILL.md:223); venv writes go through Bash |
| find-orphaned-ideas | Write | reports/events written by the script (Bash); line 141 is prose about test scaffolding |
| find-rule-surface-drift | Agent | SKILL.md:87 "sub-agents" is a topic word in an exemption list |
| find-standard-gaps | Agent | SKILL.md:43 explicitly "there is no scout fan-out" |
| orient | Agent | SKILL.md:49 explicitly "no scout fan-out" |
| plan-skill | Agent | SKILL.md:131/181 state contract rules for skills being authored and refer to `/repair-skill`'s loop |
| propose-folder-reorganization | Edit | SKILL.md:90 is the read-only disclaimer ("no Edit tool") itself |
| rename-concept | Write | the write half is explicitly deferred v1 (SKILL.md:135-141 "not yet ported"); assess.py writes via Bash |
| which-cleanup | Agent | fan-out is mandated via `_common/dispatch_scout_cheap.sh` (SKILL.md:116-118) — Bash covers it |
| which-shape | Edit | SKILL.md:137 "it does not amend the first" — a negation |
| which-skill | Agent | SKILL.md:227 explicitly "no fan-out" |

(propose-boundary's Edit flag at SKILL.md:82 is also its own read-only
disclaimer — FP; its Agent flag is the borderline hit above.)

### Coverage statement

All 74 skills cross-checked mechanically; all 18 flags manually triaged
by reading the cited context. Skills without an `allowed-tools` key
inherit all tools and cannot mismatch (none were found missing the key).

---

## Batch-fix spec

Ordering: Class 3 first (cheapest, unblocks broken modes), then Class 2
(four one-line decisions), then Class 1 (41 small text blocks, batchable
by template family).

**Class 3 (2 edits + 1 wording fix)**
- find-incomplete-sweep: add `Agent` to `allowed-tools` (SKILL.md:16).
- mature-existing-ideas: add `Agent` to `allowed-tools` (SKILL.md:5).
- propose-boundary: in Stage 2 name `_common/dispatch_scout_cheap.sh` as
  the dispatch path (keeps the tool list read-only-tight), or add `Agent`.

**Class 2 (4 decisions, one line each)**
- audit-decisions raw-drift.json: either wire `/triage-debt` to read it
  (real consumer) or rewrite the stage text to "debug artifact, no
  downstream consumer" — the false claim is the defect.
- triage-debt raw-scores.json: demote to optional debug output ("write
  only when debugging the heuristic") or delete the mandate.
- fix-workflow learnings.md append: add the read — Step 1 (load
  context) reads `reports/duplication/learnings.md` tail — or fold the
  append into the skill-internal `knowledge/learnings.md` promotion path.
- find-standard-gaps coverage.json: mark "reserved for query_planner
  v1.0, not yet consumed" in Stage 1, or stop writing until the
  consumer ships.

**Class 1 (41 blocks)**
- Author 4 template blocks (SUSPECT fan-out / EXPLAIN proposal /
  plan-chain / per-skill meta) per the family lines in the hit table;
  instantiate per skill with its concrete gates (report path, handoff
  skill, status transition, read-only constraint).
- Insert after the intro paragraph, before `## Core beliefs`, matching
  the repair-skill exemplar shape (`.claude/skills/repair-skill/SKILL.md:45`).
- For diagnose / plan-skill, surface the existing `evidence_required`
  frontmatter as the body block rather than inventing new gates.
- Batch by family (4 commits), run
  `scripts/lint/run.py --self` + `/check-ecosystem-consistency` after.
