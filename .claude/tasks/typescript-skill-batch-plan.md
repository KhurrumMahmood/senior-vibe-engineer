# TypeScript-first skill batch plan

Status: B0, B1, B2P, and B3 complete; B2T, move-path, and explain-code in progress

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

## Full TypeScript coverage target

“Full TypeScript coverage” means complete, honest coverage of the ecosystem's
language-level product—not a claim that Django workflows have become React or
Node workflows by changing metadata.

At completion, every one of the 76 skills must have exactly one mechanically
checkable disposition:

- `validated-neutral`: the skill's outcome is independent of host language and
  a representative installed TypeScript-host task proves that no language
  variant is needed;
- `typescript-supported`: the skill's declared TypeScript invariant passes
  D1–D8 through its final installed outcome;
- `stack-bound`: the skill encodes a named framework/ORM/router/UI contract and
  is truthfully excluded from framework-neutral TypeScript routing; or
- `ecosystem-runtime`: the skill operates on this toolkit rather than host
  source language.

No skill may remain `candidate`, claim TypeScript from suffix handling alone,
or silently under-detect TypeScript at this milestone. `stack-bound` is a
complete and honest language-coverage result, but it is not cross-framework
support. A later Node/React/Express/ORM packet must be separately named and
validated before any of the 20 framework-specific skills changes disposition.

The milestone is complete only when:

- [ ] A committed 76-row coverage matrix contains one unique disposition,
  evidence path, installed command, and latest reviewed revision per skill.
- [ ] Every generally applicable language-level skill is either
  `typescript-supported` or has evidence that it is genuinely
  `validated-neutral`; metadata-only relabeling does not count.
- [ ] Every `typescript-supported` skill passes its final report/proposal or
  mutation/guard outcome, copied-install closure, native TypeScript
  verification where applicable, fresh forward task, and adversarial review.
- [ ] Copied stock routers carry `language`, `framework`, and `scans`, select
  only eligible skills for exact TypeScript tasks, and return explicit
  unsupported/no-match for stack-bound or not-yet-earned claims.
- [ ] No installed selected skill imports repository-level `scripts/`, sibling
  `_common`, another uninstalled skill, a toolkit venv, or an undeclared
  network dependency.
- [ ] One clean-host matrix replays a read-only detector, proposal-only skill,
  safe path mutation, state mutation/guard, and semantic-analysis skill using
  TypeScript fixtures; all native tests and the Python regression paths pass.
- [ ] The completion review finds no remaining ambiguous language claim and no
  shared TypeScript infrastructure without at least two accepted consumers.

### Full-coverage execution sequence

Each numbered wave is a dependency gate. Within a wave, at most three
path-disjoint skill lanes run concurrently; shared router/catalog/dependency
changes remain serial-integrator work.

1. **Accept the current foundation.** Independently review and integrate B1,
   B3, the narrow `move-path` TypeScript contract, and B2P. Complete the B1
   router-language integration and establish the first coverage-matrix rows.
2. **Complete the state family (B2T).** Implement the family-local Compiler API
   path for `find-implicit-state`, `extract-enum`, and `prevent-regression`;
   prove detection → proposal → applied fixture mutation → `tsc`/native tests
   → guard red/green → installed replay.
3. **Prove syntax facts without a platform.** Port `find-omnibus` first for
   trustworthy top-level TypeScript symbol spans. Use its accepted evidence to
   scope, not assume, the separate `find-complexity-hotspots` function-body
   syntax contract.
4. **Run independent lexical/outcome pilots.** In separate worktrees, port
   `explain-code`, `find-duplication`, and `find-folder-topology-drift`; then
   `find-standard-gaps` and `rename-concept` after their concrete standards and
   B1 concept inputs are frozen. These lanes may reuse validation procedure,
   not a speculative common parser.
5. **Prove module resolution with real consumers.** Port `map-subsystem` first
   with one project-local `tsconfig` resolver. Only after acceptance may
   `propose-boundary` and `propose-folder-reorganization` reuse the exact
   demonstrated resolution contract. The completed narrow `move-path` v1
   remains honest about ignored imports; import-safe mutation is an optional
   later extension, not a hidden prerequisite.
6. **Complete semantic families separately.** Port `find-dormant`,
   `find-incomplete-sweep`, and `find-semantic-duplication` as independent
   Compiler API consumers with their already-frozen judgment boundaries. Port
   `unify-shadows` only after the semantic report schema and TypeScript handoff
   are accepted.
7. **Close routing, installation, and evidence.** Regenerate the catalog,
   finish the 76-row matrix, run the five clean-host journeys, replay Python
   regressions, and adversarially audit every remaining `validated-neutral`,
   `typescript-supported`, `stack-bound`, and `ecosystem-runtime` claim.

### Parallel queue after the current reviews

- Critical path: B2P acceptance → B2T.
- Parallel syntax lane: `find-omnibus`.
- Parallel lexical lane: `explain-code`.
- Next queue: `find-duplication`, then folder-topology policy/pilot.
- Serial integration after each wave: contracts, frontmatter, router catalog,
  coverage rows, installed forward tests, and learning review.

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

## Pilot-derived implementation guidance

B3 is the reference procedure for parallel TypeScript conversions. It is a
process template, not a shared parser design. Give each implementing agent the
following ordered loop and require evidence at every boundary:

1. **Freeze the outcome before choosing a tool.** Name the final report,
   proposal, change, or guard a user will receive; distinguish deterministic
   facts from agent judgment; list Python/framework modes excluded from TS v1.
2. **Prove the reference path.** Add or lock Python positive, clean, and
   must-not-fire fixtures. Repair discovered reference defects before copying
   behavior. B3's stale contract and source-tree-only imports would otherwise
   have been reproduced as “TypeScript support.”
3. **Write the TypeScript outcome test red.** Include a positive, negative,
   must-not-fire, and final-artifact assertion. A parser/symbol unit test alone
   is not the acceptance test. Capture the red transcript before production
   edits.
4. **Prove selected-skill closure immediately.** Copy only the owned skill to
   a directory outside the checkout and run it with isolated host tools. Do
   this before polishing shared infrastructure. B3 exposed repository
   `_common` imports and an external guard owner at this step.
5. **Use the least semantic tool that can prove the accepted outcome.** B3's
   lexical invariant needed suffix and typed-signature handling, not a TS
   compiler. State/dormancy/resolved-import work must use compiler facts rather
   than stretching this regex approach.
6. **Keep detection and enforcement consistent without conflating them.** A
   guard may block a reasoned subset of advisory detector records. Put reusable
   enforcement inside the installed closure and make repository wiring thin.
7. **Exercise real repository shapes.** Include hidden ancestors, generated
   and test exclusions, TSX, typed arrows/functions, and host invocation from a
   different cwd. Apply skip rules relative to the requested target, not the
   toolkit's absolute parent path.
8. **Run a fresh forward test.** Give a non-context agent only the installed
   skill, raw fixture, and natural task. It must produce and interpret the
   final user artifact without being told the expected diagnosis.
9. **Extract evidence, not speculative abstractions.** Write both learning
   files, name exact code that could be reused, and keep it family-local until
   an actual second consumer demonstrates the same contract.
10. **Review against the ordered product goals.** Reject metadata-only ports,
    source-checkout-only success, platform expansion without a batch outcome,
    and any review request that does not materially improve installability,
    TypeScript usefulness, or later measurable UX.

Parallel lanes own only their skill directories, namespaced fixtures/tests,
and learning files. If two candidates need a shared adapter, catalog, root
dependency, installer behavior, or global lint wiring, they are not safe
parallel edits: each lane records its proposed interface and the serial
integrator resolves it after both evidence packets are reviewed.

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

State: `complete` — accepted on `codex/productization-restart` at `e6f6a5d`

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

- [x] A glossary `avoid_term` in `.ts` and `.tsx` fires; canonical-only TSX,
  unrelated homonyms, generated/vendor paths, and a justified compatibility
  alias stay clean.
- [x] The four ecosystem/artifact skills preserve their existing behavior and
  declare host-language neutrality without artificial TypeScript variants.
- [x] Regenerated router data retains the three portability fields and a
  TypeScript fixture cannot select a known Django-only skill. The exact
  regression task `find repeated bare status literals in a TypeScript source
  file` must not select the current Python/Django `find-implicit-state` until
  B2T earns TypeScript support.
- [x] Before the copied-router test, the serial integrator removes the current
  unearned TypeScript scan claim from `find-omnibus`; B4 restores it only after
  D1–D7 pass. The task `find an omnibus TypeScript module with too many
  unrelated responsibilities` returns unsupported/no-match until then.
- [x] The serial integrator corrects `find-workflow-state-gaps` from
  `framework:any` to its current Django binding. A TypeScript workflow-state
  task cannot select it until a later concrete framework packet earns support.
- [x] A copy containing only the installed `which-skill` directory exercises
  explicit, exact-marker, ambiguous/mixed, and no-language cases outside the
  source checkout; the final recommendation and routing-context JSON are
  asserted, not just the regenerated catalog bytes.
- [x] D1, D3, D5–D8 pass. D2/D4 are not applicable because this batch corrects
  text-scan coverage and routing truth, not a Python→TypeScript mutation.

### B2P — Python closed-state reference proof

State: `complete` — accepted at `33e96a6` after independent adversarial
re-review; B2T is active at `/private/tmp/engineering-skills-ts-b2t`

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

- [x] A disposable Django-shaped fixture produces real detector JSONL,
  collapsed/reviewed findings, extractor targets/proposal, a reviewed enum
  before/after change, and lint red-before/green-after evidence.
- [x] Positive, negative, must-not-fire, vendor-boundary, structured-output,
  and native Python tests are checked in.
- [x] Copied installed skills execute outside the toolkit checkout with no
  repository-level imports or toolkit venv.
- [x] D1–D8 pass, with the TypeScript clauses of D3/D4 deferred specifically
  to B2T.

### B2T — TypeScript closed-state outcome

State: `in_progress` — `codex/ts-b2t` at
`/private/tmp/engineering-skills-ts-b2t`

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

State: `complete` on `codex/productization-restart`

Skill and guard: `find-comment-drift` plus its shared enforcement consumer
`scripts/lint/no_comment_drift.py`.

Invariant: the advisory scan and diff guard agree about useful comments,
docstrings, JSDoc, and template comments. The pre-pilot baseline covered
`.py/.js/.html`; B3 adds `.jsx/.ts/.tsx` through the final lint runner and
pre-commit invocation path as well as the detector.

Owned paths: the skill directory, comment lint, B3 fixtures/tests and learning
files. Router-catalog regeneration remains integrator owned.

Installed closure contract: the reusable guard entry point lives at
`find-comment-drift/scripts/guard.py`; the repository-level
`scripts/lint/no_comment_drift.py` is a thin source-tree wrapper. A copied
selected skill can invoke `scripts/guard.py` directly without repository
`_common` or `scripts/lint` paths.

Acceptance:

- [x] Must-fire fixtures include a typed exported/async function and typed
  arrow handler with narration or thin JSDoc.
- [x] Useful typed JSDoc stays clean; an ordinary TSX component does not become
  a JSDoc candidate merely because it contains JSX.
- [x] The lint's blocking subset is derived from the same detector records for
  TS/TSX, while advisory-only records stay non-blocking and the existing
  Python/JS/HTML good/bad smoke behavior is preserved.
- [x] A copy containing only the installed `find-comment-drift` directory runs
  both its detector and `scripts/guard.py` against TS/TSX fixtures outside the
  source checkout.
- [x] D1–D8 pass; D4 uses detector/guard red-green evidence rather than a code
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

#### Clarified candidate contracts

Three fresh non-context review lanes inspected the 14 skills against their
actual scripts, fixtures, contracts, installed closure, and downstream
consumer. The result is intentionally not a new mega-batch. Each row below is
the minimum honest TypeScript v1 and the evidence required before its state may
move from `candidate` to `ready`.

| Candidate | Minimum honest TypeScript v1 | Tooling / prerequisite gate | Promotion oracle and definition of done |
|---|---|---|---|
| `explain-code` | Produce the complete explanation document and sidecars for direct explicit top-level exports; unresolved aliases/re-exports remain visibly unexplained. | Freeze a Python `targets.json` reference oracle. A lexical export collector is allowed; no resolver claim. | Positive exported branchy symbols, private/test must-not-fire cases, final explanation with honest unexplained region, copied-install run, and fresh-agent outcome. |
| `find-complexity-hotspots` | Advisory syntactic TS function-body complexity only: nesting and branch score. Exclude ORM, React/Node, and receiver-type claims. | A proven family-local TypeScript body AST; type checker only if a later contract claims container/API identity. | Existing six-band Python oracle stays green; locked TS positive/clean/must-not-fire fixture produces the final report; copied closure and forward test pass. Keep separate from incomplete-sweep. |
| `find-dormant` | Report statically unreferenced, non-exported TS implementation candidates for human review; never infer safe deletion. Exclude routes/endpoints/error swallowing. | Project-local Compiler API `Program`/`TypeChecker` and resolvable `tsconfig`; dynamic/external reachability stays a judgment boundary. | Unreferenced private must fire; direct references and exported APIs stay clean; registry/event/framework shapes are must-not-fire; no result is `certain_delete` from static evidence alone. |
| `find-duplication` | Report lexical/near-lexical TS clone clusters with reliable source spans and enclosing symbols; never claim consolidation is safe. | Family-local jscpd invocation plus a TS span-to-symbol mapper and deterministic/offline dependency resolution. | One real typed clone cluster, behaviorally different negative pair, generated/test/declaration/overload must-not-fire corpus, final `triage.md`/JSON, and copied-install replay. |
| `find-folder-topology-drift` | A narrow lexical TS flat-prefix cluster under declared source roots only. No package-demotion, Next/pages, or barrel claim. | First freeze a repository-neutral TS folder policy: prefixes, source roots, test colocation, generated/vendor exclusions, and barrel treatment. | Exactly one three-sibling positive cluster; two siblings, tests, `index.ts`, generated/vendor stay clean; final report only claims `flat_prefix_cluster`; copied closure passes. |
| `find-incomplete-sweep` | Do not promote a lexical approximation. A TS sweep groups resolved call sites and options/property presence, then produces scout packets and explicit human verdicts. | Compiler program/resolution for callees, aliases, spreads, overloads, defaults, and Git trajectory; first freeze the final `triaged.md` writer/oracle. | Full candidate→packet→verdict→triage journey on a locked fixture, framework APIs explicitly excluded, installed closure, and fresh forward result. Keep separate from complexity. |
| `find-semantic-duplication` | Function-level, typed TS candidates only; output confirmed/uncertain/rejected triage plus capability matrix. No workflow/structural claim. | Compiler `Program`/`TypeChecker` and direct-call resolution. First repair missing `end_line`, unused workflow/artifact inventories, and `uncertain` filtering in the Python reference path. | Same-outcome/different-code positive, caller→callee and lexical-clone negatives, protocol/test-double/divergent-policy must-not-fire cases, final triage, copied closure, and forward scout. |
| `find-standard-gaps` | One concrete TS standard with explicit unsupported and mixed-language behavior; the declared standards file remains the durable user artifact. | Choose the host standard first. Lexical grep can enumerate candidates only; structural/API standards need TS AST and often type resolution. | Add the actual config plus positive/negative/must-not-fire fixtures, final `coverage.md`/JSON, honest unsupported states, copied closure, and forward test. Do not build a generic detector platform first. |
| `map-subsystem` | Complete TS subsystem map only: exported surface, resolved inbound/outbound imports, workflow participation, and applicable compliance. A partial lexical inventory must not masquerade as the artifact. | Named `tsconfig`/project-reference/alias resolver and TS lint policy. | Multi-file direct+alias import fixture, test/generated/vendor exclusions, accurate final map counts and unavailable fields, copied closure, and forward outcome. |
| `move-path` | Deterministic TS/TSX path/text move with Markdown/HTML/config/reference rewrites; explicitly ignore source imports and expose that risk. | Decide self-contained JSON plan versus bundled PyYAML. No parser is needed until import-safe moves are claimed. | Extend the strong existing move oracle with standalone TS file, docs/config references, external/prose/import must-not-fire cases, explicit ignored-import report, `tsc --noEmit`, and copied-install replay. First near-term candidate. |
| `propose-boundary` | Proposal from a resolved TS symbol/import/call graph, including public API, compatibility/barrel plan, caller impact, and characterization tests. | `tsconfig` resolver plus ES-module/barrel compatibility decision. First reconcile documented versus implemented graph/scoring schema. | Two-domain cross-private fixture must fire; cohesive/unresolved cases defer; final proposal cites resolved evidence and native test/typecheck command; copied closure and forward test pass. |
| `propose-folder-reorganization` | One TS cluster proposal with complete resolved import-impact table, tree/move/test plan, and compatibility decision. | TS module-specifier resolver plus `index.ts`/subpath/test convention. It is not automatically batched with detector or mover. | Direct relative+alias importer positive; below-threshold/scratch/unresolved cases stay clean or explicitly block; final proposal and native verification plus copied closure. |
| `rename-concept` | Assessment-only TS/TSX lifecycle report: lexical retired prose plus resolved identifier completeness; no codemod claim. | B1 must first make `find-concept-divergence` TS/TSX-correct and self-contained. Identifier completeness later needs language-service references and `tsc --noEmit`. | Genuine old→new TS/TSX fixture, positive/clean/prose/identifier must-not-fire cases, TS guard-recognition contract, persistent structured assessment, copied closure, and forward test. |
| `unify-shadows` | Consume one confirmed structured TS semantic finding and produce an evidence-cited proposal; `keep_separate_document_why` is a valid success. | Proven semantic report schema and explicit TS handoff. First add templates for all upstream result shapes and repair unknown-caller parsing/scope fallback. | Missing/unconfirmed/wrong-kind inputs fail before synthesis; keep-separate never emits a merge plan; final proposal includes caller impact, native test matrix, stop condition, human approval, and copied closure. |

Cross-cutting decisions from this clarification:

- `move-path` is the next plausible standalone candidate after B3 because its
  narrow path/text contract needs no TypeScript parser. `explain-code` is the
  next plausible lexical analysis pilot, but only after its Python oracle.
- `map-subsystem`, `propose-boundary`, `propose-folder-reorganization`, and
  import-safe `move-path` require a named `tsconfig`-aware module resolver.
- `find-dormant`, `find-incomplete-sweep`, and `find-semantic-duplication`
  require semantic compiler facts. The B3 lexical pilot does not justify that
  platform.
- `find-duplication`, `find-standard-gaps`, folder topology, and rename each
  need independent outcome contracts; name adjacency does not establish a
  shared batch.
- All 14 currently fail the selected-skill installed-closure criterion. None
  may claim TypeScript readiness merely because the source checkout can reach
  repository helpers.

Active candidate promotion:

- `move-path` is `in_progress` on `codex/ts-move-path` at
  `/private/tmp/engineering-skills-ts-move-path`. Its v1 contract guarantees a
  self-contained JSON plan path, keeps YAML optional when PyYAML is available,
  rewrites only identity-resolved text/path references, explicitly ignores
  TypeScript source imports, and must expose that residual risk in the final
  report. It may move to `ready/complete` only after its locked TS fixture,
  native typecheck, copied-install replay, learning packet, and fresh review
  pass.

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
| 2026-07-19 UTC | working tree on `codex/productization-restart` | B3 TypeScript comment hygiene | Red-green implementation added TS/TSX positive/clean fixtures, a skill-local stdlib closure, shared detector/guard ownership, root lint wrapper, pre-commit and `--all` invocation coverage, and final report assertions. Fresh installed forward test produced four useful TS findings and kept an ordinary TSX component clean. Targeted suite: 30 passed; smoke: 23 bad findings and good fixtures clean; metadata/catalog/Ruff/JSON/diff checks passed. Full suite: 415 passed, 1 skipped, with one unrelated pre-existing calendar-sensitive `test_triage_audit.py` failure (its fixed 2026-06-11 fixture is compared by the CLI to real current time; neither test nor implementation is in this diff). Adversarial re-review: PASS after it exposed and verified the pre-commit/runner repair. |
| 2026-07-19 UTC | `33e96a6` | B2P Python closed-state reference | Detector→review→enum proposal→guard reference accepted after adversarial repairs for parse-error rc 2, chained assignments, repo-ignore fallback, and whole-tree immutability. Targeted suite: 8 passed; copied `python3 -I -S` forward artifacts at `/tmp/es-forward-state.xDtbxT` preserved vendor/open-ended boundaries; independent re-review returned PASS. |
| 2026-07-19 UTC | `eb4d498` | B1 router-language integration foundation | Bundled catalog now retains `language`, `framework`, and `scans`; copied matcher resolves explicit/exact language context, excludes unsupported language/framework/scanner claims, and returns `unsupported` instead of substituting a weaker skill. Unearned `find-omnibus` TypeScript and Django-bound workflow-state claims are withheld. Router suite: 19 passed; metadata/conformance/Ruff clean. B1 skill-local acceptance remains pending. |
| 2026-07-19 UTC | `e6f6a5d` | B1 complete | TS/TSX concept findings plus four host-neutral artifact/rules skills pass copied `python -I -S` final-outcome tests. Two adversarial rounds found and repaired quoted/commented YAML false-clean/false-positive paths. The five real contracts are acknowledged and index `stale: ok`; catalog/routing integrated. Final integrated suite: 35 passed; independent re-review PASS. |
