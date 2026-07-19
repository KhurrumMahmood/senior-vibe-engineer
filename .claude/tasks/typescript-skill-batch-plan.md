# TypeScript-first skill batch plan

Status: B0 complete; B1 and B2P ready for isolated worktrees

This tracker turns the second product goal—genuine multi-language support,
beginning with TypeScript—into agent-sized units. It does not reopen installer
design or begin the later routing/performance milestone.

## How to use this file

1. Work top to bottom unless a batch explicitly names a parallel wave.
2. Give one batch to one fresh, non-context sub-agent in an isolated worktree.
   Give the agent the ordered product goals, the batch contract below, the
   exact paths it owns, and the learning-report requirement.
3. Set only one state for each batch: `proposed`, `ready`, `in_progress`,
   `review`, `complete`, or `deferred`. Record the worktree/branch beside the
   state when work starts.
4. Check an acceptance box only after its named artifact or command has been
   inspected. Commits, changed-line counts, parser helpers, and passing unit
   tests do not count by themselves.
5. Before merge, a fresh reviewer receives raw fixtures and the ordered product
   goals. The reviewer must reject work that merely flips metadata, tests a
   parser in isolation, or adds infrastructure without improving the batch's
   installed user journey.
6. The implementing agent writes both
   `.claude/tasks/multilanguage-learnings/<batch-id>.md` and
   `.claude/tasks/multilanguage-learnings/<batch-id>.json` from the required
   schema in this file. The Markdown holds the reasoning and experience; the
   JSON makes cross-batch comparison mechanical. The integrator records both
   paths and the validation evidence in the evidence log.
7. Only the serial integrator edits shared adapters, global metadata, routers,
   README files, this tracker, or the idea ledger. Batch agents propose shared
   changes in their learning report instead of racing on those files.

## Product and review boundary

The ordered product goals remain:

1. Make the skill collection easy to install.
2. Make applicable skills genuinely multi-language, beginning with
   TypeScript.
3. Improve the installed user journey and execution efficiency.

Milestone 1 already proved the local three-router stock-install journey. This
plan may require a selected TypeScript skill to be self-contained when
installed, but it must not build a custom package manager, trust platform,
generic executor, evaluator platform, or workflow coordinator.

A review finding may add work only when it materially affects the current
TypeScript batch, the next required installed journey, or prevents concrete
critical user harm.

## What counts as a batch

A batch is a cohesive invariant family. Its skills share at least two of:

- one developer outcome or maintenance-loop handoff;
- one syntax/semantic model;
- one fixture corpus and false-positive boundary;
- one report schema or change/guard contract;
- one installed runtime closure.

Similar names and shared use of Python are not sufficient. Framework-specific
behavior is not silently treated as language behavior.

## Standard sub-agent handoff

Every batch prompt must be self-contained and include:

- the repository/worktree path and explicit owned paths;
- the three ordered product goals and review relevance rule;
- the batch's invariant, exclusions, prerequisites, D1–D8 criteria, and
  batch-specific acceptance checks copied from this tracker;
- instructions to use the worktree's `.venv/bin/python` explicitly, preserve
  unrelated changes, and avoid shared/global files reserved for the
  integrator;
- the exact native TypeScript fixture setup and test command once the batch is
  frozen;
- a requirement to produce both learning files before asking for review;
- a stop rule: if the accepted outcome requires an excluded framework choice,
  unavailable host prerequisite, or shared-platform expansion, document the
  evidence and return the batch for rescoping instead of guessing.

The final handoff asks the agent to report acceptance criterion by criterion,
with commands, artifact paths, and unresolved failures. A conversational
summary without repository artifacts does not complete a batch.

## Catalog inventory

The current 76-skill frontmatter divides into:

| Declared support | Count | Meaning for this plan |
|---|---:|---|
| `any / any` | 33 | No language variant is presumed necessary. Validate representative real use; do not create artificial TypeScript copies. |
| `any / django` | 5 | Language coverage and framework portability are separate. Keep deferred until a TypeScript web stack is named. |
| `python / any` | 15 | Audit whether the encoded invariant is Python-specific or the Python program is merely an implementation detail. |
| `python / django` | 23 | Port only a framework-neutral sub-invariant, or defer until an explicit TypeScript framework/ORM packet exists. |

The declaration is a routing claim, not proof. A skill is “TypeScript-ready”
only after the batch definition of done passes.

## Definition of done for every implementation batch

- [ ] **D1 — Scope honesty.** The batch names the supported TypeScript
  invariant and explicitly lists excluded Python modes and deferred framework
  behavior. Frontmatter and router metadata make no broader claim.
- [ ] **D2 — Python oracle.** The affected Python path has positive, negative,
  and must-not-fire fixtures plus stable structured output. Any discovered
  reference-path defect is fixed before its behavior is copied.
- [ ] **D3 — TypeScript outcome.** A committed, locked TypeScript fixture
  proves the same invariant-level outcome through the final skill report or
  proposal, not merely through a parser/helper test.
- [ ] **D4 — Change or guard semantics.** If the family proposes a change or
  guard, the proposed result type-checks and its native tests pass; the guard
  fires on the pre-fix fixture and stays quiet on the fixed and must-not-fire
  fixtures.
- [ ] **D5 — Installed closure.** The pinned stock installer installs only the
  selected batch skills. From outside the source checkout, each executable
  path runs without repository-level `scripts/`, `_common`, a toolkit venv,
  undeclared network access, or another uninstalled skill.
- [ ] **D6 — Fresh forward test.** A fresh non-context agent receives the
  installed skill, raw fixture, and natural user task—not the expected answer
  or prior diagnosis—and produces the expected useful artifact.
- [ ] **D7 — Regression and conformance.** Targeted native tests, skill
  metadata/conformance checks, and the Python regression path pass at one
  revision. Unsupported combinations fail clearly instead of silently
  under-detecting.
- [ ] **D8 — Learning handoff.** The batch learning report is complete,
  evidence-linked, and reviewed before another language or dependent batch is
  planned.

## Required learning handoff

Every implementing agent must record all of the following, including “none”
where appropriate:

1. **Invariant:** the language-independent behavior the batch protects.
2. **Reference repair:** defects or missing evidence found in the Python path.
3. **TypeScript model:** syntax, type-system, module-resolution, runtime, and
   framework assumptions actually used.
4. **Tool decision:** parser/linter/compiler/library selected, rejected
   alternatives, dependency and install consequences, and why the chosen
   degree of precision was necessary.
5. **Fixture results:** exact commands and positive, negative, must-not-fire,
   structured-output, native-test, installed, and forward-test evidence.
6. **False-positive boundary:** legitimate TypeScript shapes that resemble the
   smell and how they were kept clean.
7. **What generalized:** shared concepts, schemas, orchestration, and tests
   demonstrated by both Python and TypeScript.
8. **What did not generalize:** framework idioms, language semantics, output
   forms, and tooling that must remain variant-specific.
9. **Next-language translation:** for Rust, Go, Java/Kotlin, C#, and Ruby,
   state the syntax/semantic capability and fixture needed before claiming
   support. Do not claim support based on analogy.
10. **Reuse proposal:** exact code or knowledge another batch could reuse,
    with evidence; also list abstractions that should not yet be extracted.
11. **User experience:** observed install steps, wall time, agent confusion,
    repeated work, and the smallest later improvement worth measuring.
12. **Residual risks and next decision:** known gaps, deferred modes, and a
    recommendation to expand, revise, split, or stop the family.

The companion JSON uses these required top-level keys:
`batch`, `revision`, `family`, `invariant`, `reference_repairs`,
`language_model`, `tooling`, `outcome_contract`, `evidence`,
`false_positive_boundary`, `generalized`, `did_not_generalize`,
`reuse_decision`, `translation_prerequisites`, `user_experience`,
`residual_risks`, and `next_decision`. `translation_prerequisites` must contain
`rust`, `go`, `java_or_kotlin`, `csharp`, and `ruby`; each records a native
analysis tool, idiomatic representation, required fixtures, and semantic gaps.
Unknown values are explicit `null` or empty arrays. In particular, no shared
abstraction is extracted when `reuse_decision.actual_second_consumer` is
`null`. Copy `.claude/tasks/multilanguage-learning-template.json` rather than
inventing a new per-batch shape.

## Ordered batch map

### B0 — Catalog claim audit and batch freeze

State: `complete`

Scope: all 76 skills, frontmatter, scripts, tests, router catalog fields,
current JavaScript adapter, and installed-closure dependencies. This is
analysis only.

Acceptance:

- [x] Every skill is assigned to exactly one disposition in the catalog map
  below.
- [x] Every ready implementation batch has exact members, exclusions,
  prerequisites, owned paths, and a measurable end-to-end outcome.
- [x] A fresh goal-anchored review finds no unowned language-sensitive skill,
  unjustified grouping, or scope expansion unrelated to goals 1–3.

### B1 — Portability truth and TypeScript routing metadata

State: `ready` — small, independent batch

Skills: `find-concept-divergence`, `find-rule-surface-drift`,
`find-skill-artifact-drift`, `find-skill-intent-drift`, and
`find-stale-artifacts`.

Invariant: these skills inspect text, docs, frontmatter, or artifact graphs;
their Python executable is an implementation detail rather than a Python host
assumption. `find-concept-divergence` already scans `.ts` but omits `.tsx`.

Owned paths: the five skill directories and B1-namespaced tests/fixtures and
learning files. The serial integrator owns router-catalog generation and the
smallest patch needed to carry `language`, `framework`, and `scans` into
`which-skill`; the current generated catalog omits those fields, so its matcher
cannot honestly filter a TypeScript host.

Installed matcher language-source contract:

1. Explicit repeatable `--language` and optional `--framework` arguments are
   authoritative.
2. Without `--language`, exact task markers (`TypeScript`, `.ts`, `.tsx`,
   `JavaScript`, `.js`, `Python`, `.py`) may establish one language. Ambiguous
   or mixed markers establish no language; the matcher must not guess from a
   broad word such as “frontend.”
3. With a known language, a skill is eligible only when its declared
   `language` is `any` or matches. A framework-specific skill is eligible only
   when its declared framework is `any` or the framework was explicitly named
   and matches. Thus `--language typescript` without a framework excludes
   Django-only skills.
4. For a `suspect`/scanner skill that declares `scans`, a known task language
   must appear in that list; TypeScript and JavaScript are not interchangeable.
   `scans` never expands a conflicting `language` or `framework` claim. It is
   not a filter for non-scanning jobs.
5. JSON output records the resolved language/framework and whether each came
   from an explicit argument or exact task marker. With no resolved language,
   current general ranking remains available but the output says filtering was
   not applied.

Acceptance:

- [ ] A glossary `avoid_term` in `.ts` and `.tsx` fires; canonical-only TSX,
  unrelated homonyms, generated/vendor paths, and a justified compatibility
  alias stay clean.
- [ ] The four ecosystem/artifact skills preserve their existing behavior and
  declare host-language neutrality without artificial TypeScript variants.
- [ ] Regenerated router data retains the three portability fields and a
  TypeScript fixture cannot select a known Django-only skill. The exact
  regression task `find repeated bare status literals in a TypeScript source
  file` must not select the current Python/Django `find-implicit-state` until
  B2T earns TypeScript support.
- [ ] Before the copied-router test, the serial integrator removes the current
  unearned TypeScript scan claim from `find-omnibus`; B4 restores it only after
  D1–D7 pass. The task `find an omnibus TypeScript module with too many
  unrelated responsibilities` returns unsupported/no-match until then.
- [ ] The serial integrator corrects `find-workflow-state-gaps` from
  `framework:any` to its current Django binding. A TypeScript workflow-state
  task cannot select it until a later concrete framework packet earns support.
- [ ] A copy containing only the installed `which-skill` directory exercises
  explicit, exact-marker, ambiguous/mixed, and no-language cases outside the
  source checkout; the final recommendation and routing-context JSON are
  asserted, not just the regenerated catalog bytes.
- [ ] D1, D3, D5–D8 pass. D2/D4 are not applicable because this batch corrects
  text-scan coverage and routing truth, not a Python→TypeScript mutation.

### B2P — Python closed-state reference proof

State: `ready` — run before B2T; one isolated worktree

Skills: `find-implicit-state` (string-state branch), `extract-enum`, a reviewed
representative fixture mutation, and the state-specific path of
`prevent-regression` plus the existing `stringly-status` guard.

Invariant: a first-party state carrier has one named symbolic value authority;
callers do not compare or assign bare state strings. Vendor-bound literals are
explicit, reasoned exceptions.

Current gap: these skills describe replay cases but have no checked-in
positive/negative oracle chain, and the detector/collector import repository
`scripts/_lib` or `_common`, so a stock-installed copy is not self-contained.

Explicit exclusions: tuple-inferred identity, `introduce-fk`, and unrelated
general guard-generator modes.

Owned paths: the three skill directories, the state lint/fixtures, B2P tests,
and B2P learning files. No concurrent work may touch `prevent-regression`.

Acceptance:

- [ ] A disposable Django-shaped fixture produces real detector JSONL,
  collapsed/reviewed findings, extractor targets/proposal, a reviewed enum
  before/after change, and lint red-before/green-after evidence.
- [ ] Positive, negative, must-not-fire, vendor-boundary, structured-output,
  and native Python tests are checked in.
- [ ] Copied installed skills execute outside the toolkit checkout with no
  repository-level imports or toolkit venv.
- [ ] D1–D8 pass, with the TypeScript clauses of D3/D4 deferred specifically
  to B2T.

### B2T — TypeScript closed-state outcome

State: `proposed` — blocked only on accepted B2P evidence

Skills: `find-implicit-state` (new TypeScript state-only branch),
`extract-enum` (TypeScript proposal branch), a reviewed fixture mutation, and
`prevent-regression` (narrow TypeScript state guard branch).

Reference TypeScript outcome: replace repeated bare state literals with one
exported runtime value object declared `as const` and a derived union type;
migrate all first-party callers; retain vendor wire literals at a named
boundary; then prevent new first-party bare state operations. A project-native
string enum is allowed only when the fixture establishes that convention.

Tool boundary: use one family-local Node launcher with the host project's
pinned `typescript` Compiler API when semantic resolution is needed. Fail
clearly if the compatible project-local package or `tsconfig` is absent. Do not
add ts-morph, tree-sitter, ast-grep, a root fact platform, or a shared adapter
until an accepted second consumer demonstrates the same contract.

Explicit exclusions: tuple identity/FK, Django migrations,
Prisma/TypeORM/Sequelize model semantics, and general TypeScript lint
generation.

Owned paths: the same three skill directories, B2T fixture/package lock/tests,
and B2T learning files. Shared adapters and global lint wiring remain serial
integrator owned.

Guard artifact contract: the batch adds a family-local generator and verifier
under `prevent-regression/scripts/`. A completed run stages
`reports/prevent-regression/<id>/scripts/lint/no_stringly_state.mjs` plus
paired `.ts`/`.tsx` bad/good fixtures and a host-wiring diff. The serial
integrator owns the copied-install invocation test and any repository-global
lint-runner wiring; the family agent does not edit global wiring.

Acceptance:

- [ ] Detection distinguishes first-party state from a typed union/enum,
  vendor payload literals, unrelated `status` text, tests/fixtures, and
  open-ended strings.
- [ ] `extract-enum` consumes the detector result, inventories all callers and
  boundaries, and emits an implementation-ready TypeScript proposal.
- [ ] The reviewed fixture change passes `tsc --noEmit` and its native tests.
- [ ] A narrow TypeScript-AST guard uses the same 0/1/2 CLI contract, fires on
  all pre-fix variants, and stays quiet on fixed/must-not-fire fixtures and a
  reasoned `// noqa` vendor boundary.
- [ ] From a stock-installed `prevent-regression` directory outside the
  checkout, the family-local generator stages the named guard artifact and
  the verifier executes that staged artifact against the standalone fixture.
- [ ] Stock-installed copies run outside this repository using only declared
  host prerequisites; a fresh-context agent completes the useful proposal.
- [ ] D1–D8 pass.

### B3 — TypeScript comment hygiene

State: `ready` — may run parallel with B2P; no parser dependency

Skill and guard: `find-comment-drift` plus its shared enforcement consumer
`scripts/lint/no_comment_drift.py`.

Invariant: the advisory scan and diff guard agree about useful comments,
docstrings, JSDoc, and template comments. Current suffix handling covers
`.py/.js/.html`, not `.ts/.tsx`.

Owned paths: the skill directory, comment lint, B3 fixtures/tests and learning
files. Router-catalog regeneration remains integrator owned.

Installed closure contract: the reusable guard entry point lives at
`find-comment-drift/scripts/guard.py`; the repository-level
`scripts/lint/no_comment_drift.py` is a thin source-tree wrapper. A copied
selected skill can invoke `scripts/guard.py` directly without repository
`_common` or `scripts/lint` paths.

Acceptance:

- [ ] Must-fire fixtures include a typed exported/async function and typed
  arrow handler with narration or thin JSDoc.
- [ ] Useful typed JSDoc stays clean; an ordinary TSX component does not become
  a JSDoc candidate merely because it contains JSX.
- [ ] Detector and lint return the same TS/TSX findings while preserving the
  existing Python/JS/HTML good/bad smoke behavior.
- [ ] A copy containing only the installed `find-comment-drift` directory runs
  both its detector and `scripts/guard.py` against TS/TSX fixtures outside the
  source checkout.
- [ ] D1–D8 pass; D4 uses detector/guard red-green evidence rather than a code
  mutation.

### B4 — First-class TypeScript omnibus detection

State: `proposed` — start only after B2T tooling lessons are reviewed

Skill: `find-omnibus`.

Invariant: responsibility clustering consumes trustworthy TypeScript symbol
spans. The current column-zero heuristic is only a candidate generator: it
misses normal ESM `export` declarations and reports `.ts` as JavaScript.

Owned paths: the skill directory, language-adapter files if the serial
integrator approves, B4 fixtures/tests and learning files. This batch has sole
ownership of the shared adapter while active.

Acceptance:

- [ ] An ESM `.ts` module with exported functions/typed arrows/classes across
  four domains fires; a cohesive ESM module stays clean.
- [ ] Legacy `.js`, Python, minified, generated, and `*.spec.ts` behavior stays
  correct; output identifies TypeScript as `typescript`.
- [ ] The installed skill contains or declares its complete runtime closure
  and does not reach into repository-level `scripts/_lib`.
- [ ] D1–D8 pass; D4 is satisfied by detection/report semantics.

### B5 — Deep control-flow candidates

State: `deferred` — dispatch only after B4 exposes a proven reusable AST need

Skills: `find-complexity-hotspots` and `find-incomplete-sweep`.

Candidate shared invariant: both need TypeScript function bodies, calls,
defaults, and control-flow nesting. This is not yet a ready batch because they
do not share a complete detection→action loop, and B4 may not produce the
semantic capability they need.

Promotion gate:

- [ ] B4 learning evidence identifies an exact reusable syntax contract used
  by both skills, or the two skills are split into separate batches.
- [ ] Framework-specific ORM/React/Node signals are excluded from the first
  language-level fixture.
- [ ] Exact positive/negative/must-not-fire and final-report acceptance is
  frozen before dispatch.

## Catalog disposition map

This map assigns every skill to one present disposition. A later accepted
learning report may move a skill, but no agent should infer an unlisted port.

### Shared, no host-language port required (31)

`adapt-project`, `architecture-fit`, `audit-decisions`, `brainstorm-ideas`,
`check-ecosystem-consistency`, `converge`, `decide`, `design-it-twice`,
`diagnose`, `extract-existing-ideas`, `find-orphaned-ideas`,
`find-perimeter-gaps`, `gut-check`, `harvest-learnings`, `impact-feature`,
`mature-existing-ideas`, `organize-project-structure`, `orient`,
`plan-feature`, `plan-skill`, `plan-spec`, `project-interview`,
`query-patterns`, `repair-skill`, `scope-feature`, `teach-pattern`,
`track-idea`, `triage-debt`, `which-cleanup`, `which-shape`, and `which-skill`.

Representative installed forward tests must still validate their neutrality;
do not create TypeScript copies.

### Ecosystem/runtime implementation, not a host-language variant (1)

`engineer-init`. TypeScript skills may declare a Node/TypeScript preflight, but
that does not turn the toolkit's Python bootstrap into a TypeScript skill.

### Ready or ordered batches (10 unique skills)

- B1: `find-concept-divergence`, `find-rule-surface-drift`,
  `find-skill-artifact-drift`, `find-skill-intent-drift`,
  `find-stale-artifacts`.
- B2P/B2T: `find-implicit-state`, `extract-enum`, `prevent-regression`.
- B3: `find-comment-drift`.
- B4: `find-omnibus`.

### Candidate language-level families, not ready to dispatch (14)

`explain-code`, `find-complexity-hotspots`, `find-dormant`,
`find-duplication`, `find-folder-topology-drift`, `find-incomplete-sweep`,
`find-semantic-duplication`, `find-standard-gaps`, `map-subsystem`, `move-path`,
`propose-boundary`, `propose-folder-reorganization`, `rename-concept`, and
`unify-shadows`.

These require a crisp action/output handoff, fixture policy, or a proven parser
consumer before batching. Apparent chains such as omnibus→refactor,
duplication→unify, folder-topology→move, and concept-divergence→rename are not
ready merely because their verbs line up.

### Framework-specific; do not dispatch without a named stack (20)

`extract-cotton-primitive`, `extract-state-type`,
`extract-workflow-registry`, `find-async-lifecycle-drift`,
`find-contract-drift`, `find-dead-route-surface`, `find-doc-route-drift`,
`find-frontend-contract-drift`, `find-frontend-duplication`,
`find-layer-violation`, `find-query-mutation`, `find-route-sprawl`,
`find-test-obligation-drift`, `find-transaction-overreach`,
`find-workflow-duplication`, `find-workflow-state-gaps`, `fix-workflow`,
`introduce-fk`, `map-product-workflow`, and `refactor-subsystem`.

Choose and freeze a concrete router/server/UI/ORM/migration stack before moving
one of these. find-workflow-state-gaps currently says `framework:any`, but
its default path imports a Django-shaped workflow scanner; that claim must be
corrected rather than treated as working framework neutrality.

## Parallel worktree schedule

1. Finish B0 and freeze the review findings.
2. Run B1 and B2P concurrently; their owned paths are disjoint. The serial
   integrator alone handles router catalog changes and merges one branch at a
   time.
3. Run B2T only after B2P's accepted evidence. B3 may run concurrently because
   it neither touches the state family nor needs a TypeScript parser.
4. Review B2T's tooling/closure learnings before B4. Do not build a shared
   TypeScript fact layer between them.
5. Promote or split B5 only after B4. Select the next candidate family using
   saved evidence and an actual host need, not catalog coverage percentage.
6. Keep at most two implementation worktrees active. No concurrent edits to
   `scripts/_lib/lang_adapter/`, router catalogs, frontmatter schemas, root
   dependency files, or global lint wiring.

## Evidence log

| Date | Revision | Batch / criterion | Evidence |
|---|---|---|---|
| 2026-07-18 | this planning commit | B0 inventory | Frontmatter census: 33 `any/any`, 5 `any/django`, 15 `python/any`, 23 `python/django`; 76 total. A mechanical disposition check found 31 + 1 + 10 + 14 + 20 = 76, with no omission or duplicate. Existing shared JS/TS adapter exposes only top-level-symbol capability and is explicitly a column-zero heuristic. |
| 2026-07-18 | this planning commit | B0 independent lanes | Three fresh non-context Terra xhigh lanes independently reviewed detector families, mutation/guard chains, and tooling/installed closure. Their disagreement split the state work into B2P/B2T, kept the first TypeScript wrapper family-local, added the small B1/B3 batches, and moved unproven or framework-bound chains out of the dispatch queue. |
| 2026-07-18 | this planning commit | B0 verification | Targeted baseline: 38 adapter, omnibus, perimeter, metadata, and router tests passed. The learning template parsed as JSON; `git diff --check` passed. A fresh goal-anchored adversarial review first found two real router-honesty defects; after adding explicit language-source/filtering rules, copied-router regressions, and withholding unearned omnibus/workflow claims, the reviewer returned PASS and reconfirmed exact 76-skill coverage. |
