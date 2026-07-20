# Multi-language and framework expansion plan

Status: proposed — planning complete enough to review; no implementation started

Primary objective: make the generally applicable engineering skills useful on
major-language projects while preserving honest limits, then add framework
support only to coherent framework-bound skill families with demonstrated user
value.

This plan follows the product priority order:

1. preserve the completed router-only installation journey;
2. expand real language support;
3. add selected framework support;
4. optimize batching and execution only after representative journeys exist.

## How to use this file

- Each phase has one state: `pending`, `in_progress`, `blocked`, `complete`, or
  `rejected`. Only one phase may be `in_progress` unless the phase explicitly
  names independent worktree lanes.
- Before starting a phase, record its owner, branch/worktree, target revision,
  and fixture projects in the phase's evidence row.
- A skill or batch is not complete when code is merged. Check every acceptance
  item and link the exact test command, fresh on-demand replay, review result,
  and learning packet in the evidence table.
- Failed or partial evidence stays visible. Do not convert `unsupported`,
  `partial`, or `unknown` into `clean` to finish a matrix row.
- New adversarial findings start in
  `.claude/tasks/multilanguage-support-backlog.md`. Add them to this plan only
  when they materially affect installation, language/framework support, or a
  measured user journey.
- After every pilot, revise later batches from the evidence. Do not launch a
  full-language wave merely because its pilot code exists.

## Product definition of support

A language or framework claim is earned per skill outcome, not per filename or
parser. A supported skill must:

1. be selected or rejected honestly by the routers from declared project
   context;
2. expose its exact guide and tool closure from the on-demand library without
   ambient-installing the task skill;
3. inventory every in-scope first-party source file before narrower eligibility
   rules are applied;
4. distinguish `complete`, `partial`, `unsupported`, and `failed` outcomes;
5. reach the skill's final useful artifact or mutation boundary on a locked
   native fixture;
6. pass the target language's native build, test, lint, or type-check command;
7. preserve source bytes for read-only skills and prove the intended diff for
   mutating skills;
8. pass a fresh-context forward replay and a product-aligned review; and
9. record reusable and non-transferable learning for the next language.

Filename traversal, a parseable AST, or a successful helper process alone is
not a support claim.

## Current baseline

The 76-skill TypeScript matrix is the starting inventory:

| Disposition | Count | Expansion treatment |
|---|---:|---|
| Validated-neutral | 19 | Reuse directly. Run representative sentinel journeys, not artificial language variants. |
| Ecosystem runtime | 13 | No host-language variant. Verify router/library behavior separately. |
| TypeScript-supported language skills | 22 | The language-expansion cohort. Classify and port by fact level. |
| Django/framework-bound | 22 | Do not count as missing language support. Port coherent framework families only. |

Every future matrix must contain exactly the same 76 unique skills and one
current disposition per skill.

## Portability model

Language implementations are grouped by the strongest fact a skill needs:

| Fact level | Examples | Preferred mechanism |
|---|---|---|
| Neutral | planning, teaching, decision artifacts | Guide plus artifact oracle |
| Lexical/filesystem | comments, path moves, filename topology | Standard-library traversal or mature lexical tool |
| Syntax | symbols, branches, call shapes | Target language's native parser |
| Semantic/project | references, imports, types, call identity | Target compiler/language service and project configuration |
| Framework | routes, models, jobs, UI conventions | Named framework adapter over language facts |

The shared contract is capability- and outcome-based. Do not build a universal
AST or force different language toolchains behind a lowest-common-denominator
node schema.

## Shared tooling rule

Extract a runtime primitive only when all of these are true:

- at least two accepted consumers currently duplicate it;
- the proposed API is smaller than the duplicated implementations;
- both consumers retain their existing final output and failure semantics;
- the on-demand library can expose it explicitly to the executing agent;
- optional selected-skill installation either carries an exact self-contained
  closure or refuses the unsupported mode honestly; and
- a fixture locks the primitive independently of any one skill.

The first justified candidates are TypeScript project-local compiler
resolution, `tsconfig` loading, containment/symlink checks, normalized
diagnostics, and first-party `.ts`/`.tsx` inventory. Analysis-specific AST
walkers and report schemas stay with their skill families.

## Target order

1. **TypeScript consolidation** — compress learning and prove the reusable
   harness before translating again.
2. **JavaScript full disposition and coverage** — highest transfer from the
   TypeScript work; explicitly cover `.js`, `.jsx`, `.mjs`, and `.cjs`.
3. **Go pilot, then gated expansion** — a deliberately different compiler and
   project model tests whether the contracts really transfer.
4. **Route/workflow framework pilot** — Express first, then FastAPI as a second
   adapter over the same user outcome.
5. **Next language selection** — rank Java/JVM, C#/.NET, and Rust from actual
   demand, native-tool availability, closure cost, and pilot transferability.

Only items 1–4 are scheduled by this plan. The fifth is a selection gate, not
a promise to port three ecosystems simultaneously.

## Phase P0 — Freeze baseline and synthesize TypeScript learning

State: `pending`

Deliverables:

- one generated 76-row expansion matrix derived from the catalog and accepted
  TypeScript evidence;
- one concise family-level translation guide that links, rather than copies,
  the existing raw learning packets;
- one map of the 22 language-level skills by fact level and mutation class;
- one duplication inventory for TypeScript project-loading primitives; and
- one explicit list of behavior that must not be generalized.

Acceptance:

- [ ] Matrix contains 76 unique skills with counts 19 neutral, 13 runtime, 22
      language-level, and 22 framework-bound.
- [ ] A freshness check fails if catalog membership or a disposition changes
      without regenerating the matrix.
- [ ] A fresh reader can identify native tooling, positive/must-not-fire
      fixtures, failure semantics, final artifact, and installed/on-demand
      closure for each language-level family without reading unrelated packet
      history.
- [ ] The duplication inventory cites at least two concrete consumers for every
      proposed shared primitive.
- [ ] Current TypeScript focused and canonical suites remain green.

## Phase P1 — Build the minimal portability harness

State: `pending`

This phase builds test and inventory infrastructure, not a cross-language
analysis platform.

Deliverables:

- a repository source manifest with first-party, excluded, ambiguous, and
  unsupported file roles;
- a language capability manifest used by tests and routers;
- a reusable journey harness that runs a guide/tool closure from the on-demand
  library, invokes native checks, fingerprints sources, and records the final
  outcome; and
- the smallest shared TypeScript project primitive justified by P0, migrated
  first into one syntax consumer and one semantic/project consumer.

Acceptance:

- [ ] Every first-party `.py`, `.ts`, and `.tsx` fixture file appears once in
      the inventory; every exclusion has a machine-readable reason; ambiguous
      fixtures remain ambiguous.
- [ ] The harness distinguishes complete, partial, unsupported, tool-missing,
      syntax-error, native-check-failure, and unexpected-source-mutation.
- [ ] One syntax skill and one semantic/project skill produce byte-equivalent
      accepted artifacts before and after shared-primitive adoption.
- [ ] Those two skills still work from the default on-demand library journey.
- [ ] Optional selected-skill installation is either self-contained and tested
      or explicitly reported unavailable; it never fails on a hidden import.
- [ ] No analysis-specific AST walker or report schema moves into shared code.

Stop condition: if the shared primitive does not reduce repeated code or makes
either consumer's closure less clear, keep the implementations family-local
and retain only the harness and capability contract.

## Phase P2 — JavaScript coverage

State: `pending`

Scope: `.js`, `.jsx`, `.mjs`, and `.cjs`, including mixed JS/TS projects.
JavaScript support is not inferred from TypeScript filename traversal.

Independent worktree batches after the P1 interfaces are frozen:

1. lexical/filesystem cohort;
2. syntax cohort;
3. semantic/project cohort; and
4. proposal/mutation/guard cohort.

Each worktree owns a disjoint skill list and learning packet. Shared harness or
router changes remain serial integration work.

Acceptance:

- [ ] All 76 skills have an explicit JavaScript disposition.
- [ ] All 22 generally applicable language-level skills reach a useful final
      JavaScript outcome or have an evidence-backed explicit limitation; no
      skill claims support solely because TypeScript parses JavaScript.
- [ ] `.js`, `.jsx`, `.mjs`, and `.cjs` first-party files are inventoried;
      mixed JS/TS roots cannot silently omit either language.
- [ ] Semantic skills declare whether evidence comes from checked JavaScript,
      JSDoc, inferred compiler facts, or a partial lexical/syntax fallback.
- [ ] Clear JavaScript prompts route to eligible closures; ambiguous mixed-host
      prompts ask or return a bounded set rather than guessing.
- [ ] Every batch passes native fixtures, source-integrity checks, a fresh
      on-demand replay, and product-aligned review.
- [ ] The final integrated suite and exact 76-row matrix check pass.

## Phase P3 — Go three-family pilot

State: `pending`

Pilot families:

- read-only detector: `find-complexity-hotspots` using `go/parser`/`go/ast`;
- proposal: `propose-boundary` using explicit Go package/import facts; and
- mutation: `move-path` with an intentionally bounded Go import/update
  contract and `gofmt` plus `go test ./...` verification.

The pilot may revise these selections during P0 only if the replacement keeps
one detector, one proposal, and one mutation/guard outcome.

Acceptance:

- [ ] All three closures run from the on-demand library against a locked,
      non-repository Go module.
- [ ] Native Go tools and minimum versions are discovered explicitly; missing
      tools return unsupported rather than clean.
- [ ] Positive, negative, must-not-fire, malformed, generated/vendor, and
      ambiguous fixtures exist for each family.
- [ ] The detector emits its final ranked artifact, the proposal cites resolved
      package evidence, and the mutation produces only its declared diff.
- [ ] `gofmt` and `go test ./...` pass after the mutation journey.
- [ ] A fresh-context replay completes all three outcomes without consulting
      TypeScript implementation history.
- [ ] The translation guide is revised with what transferred, what did not,
      and a measured estimate for expanding the remaining language-level
      cohort.

Expansion gate: do not schedule full Go coverage unless the pilot demonstrates
that at least two of the three family contracts transfer without skill-specific
platform work and the expected user value justifies the measured effort.

## Phase P4 — Route/workflow framework pilot

State: `pending`

Framework support begins with one coherent user problem: understanding and
auditing HTTP route/workflow registration. It does not relabel all 22
Django-bound skills.

Initial consumers:

- `extract-workflow-registry`;
- `map-product-workflow`; and
- `find-route-sprawl` if the first two establish sufficient route facts.

Adapters:

1. Express on JavaScript/TypeScript;
2. FastAPI on Python as the second framework implementation.

The normalized facts may include route, method, handler, registration site,
middleware/dependency edges, and unresolved/dynamic registrations. Facts that
cannot be established remain unknown.

Acceptance:

- [ ] Framework detection requires corroborating project and source evidence;
      a dependency name alone is insufficient, and ambiguous hosts ask or
      return unsupported.
- [ ] Express and FastAPI fixtures produce equivalent core route facts without
      erasing framework-specific facts.
- [ ] Dynamic registration, decorators/wrappers, mounted routers, generated
      routes, and unresolved handlers have explicit partial/unknown behavior.
- [ ] At least two consumers use the route facts to reach their own distinct
      final artifacts; a fact dump alone is not completion.
- [ ] Must-not-fire fixtures protect Django, Next.js file routing, and unrelated
      HTTP-client code from false framework claims.
- [ ] Router prompts select the earned framework-capable closure and reject or
      ask on unsupported frameworks.
- [ ] Fresh on-demand journeys and native framework tests pass for both hosts.

Later framework families—ORM/data model, async jobs, frontend components, and
test obligations—remain backlog candidates until a real host needs them.

## Phase P5 — Select the next major language

State: `pending`

Rank Java/JVM, C#/.NET, and Rust using:

- user/project demand;
- availability and stability of native parser/compiler/project tooling;
- ability to run from the on-demand library without network-time dependency
  installation;
- coverage of the 22 language-level skill outcomes;
- framework leverage; and
- measured effort and defect rate from JavaScript and Go.

Acceptance:

- [ ] The ranking cites at least one representative host and native-tool probe
      per candidate.
- [ ] The chosen language has a three-family pilot with the same detector,
      proposal, and mutation/guard balance as P3.
- [ ] Rejected candidates retain a revisit trigger; they are not silently
      dropped or promised.
- [ ] The plan is revised before implementation begins.

## Parallelism and merge policy

- P0 is mostly serial because it freezes the contracts every later lane uses.
- P1 source inventory, journey harness, and TypeScript-primitive experiments
  may use separate worktrees, but the shared interfaces merge serially.
- P2 cohorts are deliberately parallel after P1 freezes the capability and
  evidence schemas. Each lane owns disjoint skill directories and tests.
- P3's three skill families may run in parallel worktrees after the Go fixture
  and tool contract are committed.
- P4 adapters may run in parallel only after the route-fact schema and consumer
  artifact contracts are committed.
- Router/catalog/matrix regeneration, shared-tool changes, integrated replay,
  and release evidence always have one serial owner.
- Every lane commits one logical unit. Integration cherry-picks or merges one
  lane at a time and reruns the narrowest shared tests after each merge.

## Efficiency guardrails

- A review finding may expand current work only if it threatens a likely user
  outcome, support honesty, source safety, or the three-router journey.
- Do not require every skill to run every language tool. Load only the selected
  guide, capability-specific tooling, and relevant framework reference.
- Read-only analysis lenses may later run concurrently; mutations remain
  serial. Build coordination only after a fixed workflow benchmark shows a
  meaningful wall-time or repeated-context problem.
- Track per journey: wall time, native-tool setup time, tokens/context bytes,
  repeated source reads, final outcome, human interventions, and failures.
- Stop a batch whose infrastructure work exceeds its demonstrated skill-outcome
  work; record the missing capability and return to the smallest useful path.

## Evidence ledger

| Phase | State | Revision/worktree | Fixture hosts | Verification | Fresh replay/review | Learning artifact |
|---|---|---|---|---|---|---|
| P0 TypeScript synthesis | pending | — | — | — | — | — |
| P1 portability harness | pending | — | — | — | — | — |
| P2 JavaScript coverage | pending | — | — | — | — | — |
| P3 Go pilot | pending | — | — | — | — | — |
| P4 route frameworks | pending | — | — | — | — | — |
| P5 next-language selection | pending | — | — | — | — | — |

## Final definition of done for this plan

- [ ] The three-router installation and on-demand library journey remains
      usable and documented.
- [ ] JavaScript has a complete, honest 76-skill disposition and all applicable
      language-level outcomes have validated evidence.
- [ ] Go has passed the three-family pilot and either has an evidence-approved
      expansion plan or an explicit stop decision.
- [ ] Express and FastAPI route/workflow journeys reach consumer artifacts from
      framework-specific native fixtures.
- [ ] The next major language is selected from evidence rather than assumed.
- [ ] Shared tooling exists only where at least two consumers prove the same
      primitive; no universal parser or execution platform was introduced by
      default.
- [ ] Every completed phase links tests, native checks, fresh on-demand replay,
      product-aligned review, and reusable learning.
- [ ] Remaining language, framework, and performance ideas are recorded in the
      backlog with concrete promotion triggers.
