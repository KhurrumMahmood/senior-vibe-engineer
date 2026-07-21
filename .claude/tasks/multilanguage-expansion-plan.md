# Multi-language and framework expansion plan

Status: active — P0, P1, P2, U1, P3, Go G1/G1D/G2/G3, the bounded Java pilot,
and the measured E1/E2 batching and family-compression gates are complete

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
3. **Installed user-journey stabilization** — make proposal cutoffs visible
   and validate all three default routers with a bounded decision corpus.
4. **Go pilot, then gated expansion** — a deliberately different compiler and
   project model tests whether the contracts really transfer.
5. **Measured cross-skill batching** — benchmark fixed TypeScript/JavaScript
   workflows and build only a demonstrated minimum before framework expansion.
6. **Route/workflow framework pilot** — Express first, then FastAPI as a second
   adapter over the same user outcome.
7. **Next language selection** — rank Java/JVM, C#/.NET, and Rust from actual
   demand, native-tool availability, closure cost, and pilot transferability.

Items 1–6 are scheduled by this plan. The seventh is a selection gate, not a
promise to port three ecosystems simultaneously.

## Phase P0 — Freeze baseline and synthesize TypeScript learning

State: `complete`

Deliverables:

- one generated 76-row expansion matrix derived from the catalog and accepted
  TypeScript evidence;
- one concise family-level translation guide that links, rather than copies,
  the existing raw learning packets;
- one map of the 22 language-level skills by fact level and mutation class;
- one duplication inventory for TypeScript project-loading primitives; and
- one explicit list of behavior that must not be generalized.

Acceptance:

- [x] Matrix contains 76 unique skills with counts 19 neutral, 13 runtime, 22
      language-level, and 22 framework-bound.
- [x] A freshness check fails if catalog membership or a disposition changes
      without regenerating the matrix.
- [x] A fresh reader can identify native tooling, positive/must-not-fire
      fixtures, failure semantics, final artifact, and installed/on-demand
      closure for each language-level family without reading unrelated packet
      history.
- [x] The duplication inventory cites at least two concrete consumers for every
      proposed shared primitive.
- [x] Current TypeScript focused and canonical suites remain green.

## Phase P1 — Build the minimal portability harness

State: `complete`

This phase builds test and inventory infrastructure, not a cross-language
analysis platform.

Deliverables:

- a repository source manifest with first-party, excluded, ambiguous, and
  unsupported file roles;
- a language capability manifest used by tests and routers;
- a reusable journey harness that runs a guide/tool closure from the on-demand
  library, invokes native checks, fingerprints sources, and records the final
  outcome; and
- either the smallest shared TypeScript project primitive justified by a real
  two-consumer repair, or an evidence-backed stop decision that leaves the
  family-local implementations intact.

Acceptance:

- [x] Every first-party `.py`, `.ts`, and `.tsx` fixture file appears once in
      the inventory; every exclusion has a machine-readable reason; ambiguous
      fixtures remain ambiguous.
- [x] The harness distinguishes complete, partial, unsupported, tool-missing,
      syntax-error, native-check-failure, and unexpected-source-mutation.
- [x] The TypeScript primitive decision follows the shared-tooling rule: an
      adopted helper has byte-equivalent syntax and semantic/project consumers,
      or a documented stop decision explains why extraction would not reduce
      code or would obscure a selected skill's closure.
- [x] Any adopted primitive's consumers still work from the default on-demand
      library journey; when extraction stops, the existing family-local
      on-demand journeys remain green.
- [x] Optional selected-skill installation is either self-contained and tested
      or explicitly reported unavailable; it never fails on a hidden import.
- [x] No analysis-specific AST walker or report schema moves into shared code.

Stop condition: if the shared primitive does not reduce repeated code or makes
either consumer's closure less clear, keep the implementations family-local
and retain only the harness and capability contract.

### P1 TypeScript primitive decision

Decision: **stop extraction and keep the analyzer implementations
family-local**.

The P0 inventory confirms repeated project-local TypeScript loading,
`tsconfig` handling, and containment code. A shared runtime file under the
on-demand library would, however, give stock-selected skill installs a hidden
repository-level import; copying that helper into every selected skill would
preserve the duplication instead of reducing it. There is also no current
two-consumer correctness repair whose before/after behavior would justify the
migration. Forcing a syntax and semantic consumer through a new abstraction
would therefore add packaging work without improving a user outcome.

P1 retains two smaller contracts that do cross a proven boundary:

- `scripts/source_inventory.py` is a read-only shared inventory contract, but
  skill analyzers are not coupled to it until a real omission or false positive
  proves the value of migration; and
- the test-only journey harness normalizes final outcome evidence without
  moving any analyzer, AST walker, or report schema into shared code.

Reconsider extraction only when one real repair must change at least two
accepted consumers and the helper can remain explicit in both the on-demand
and selected-install closures.

## Phase P2 — JavaScript coverage

State: `complete`

Scope: `.js`, `.jsx`, `.mjs`, and `.cjs`, including mixed JS/TS projects.
JavaScript support is not inferred from TypeScript filename traversal.

Progress: all 22 language-level skills are evidence-backed
`javascript-supported` across the syntax, lexical/filesystem,
semantic/read-only, and proposal/mutation/guard cohorts. The other 54 skills retain explicit neutral,
stack-bound, or ecosystem-runtime dispositions.

Independent worktree batches after the P1 interfaces are frozen:

1. lexical/filesystem cohort;
2. syntax cohort;
3. semantic/project cohort; and
4. proposal/mutation/guard cohort.

Each worktree owns a disjoint skill list and learning packet. Shared harness or
router changes remain serial integration work.

### P2 frozen JavaScript contract

A JavaScript claim is earned at the final skill outcome, never because the
TypeScript compiler can parse a JavaScript file. Each language-level row ends
as `javascript-supported` or `javascript-limited`; `pending-validation` is
allowed only while its cohort is active.

Evidence modes are fact-level provenance, not a host-wide badge:

- `checked-javascript`: the file is included and successfully checked by the
  host's explicit local JS configuration (`allowJs`, `checkJs`, `noEmit`, and
  JSX mode recorded where relevant);
- `jsdoc`: the fact is directly attributable to parser-recognized JSDoc;
- `compiler-inferred`: the local compiler/language service resolved the fact,
  with version, configuration, diagnostics, and unresolved edges recorded;
- `syntax`: parsed declarations, branches, comments, or import shapes only;
- `lexical`: exact text, path, name, or phrase evidence only; and
- `partial-fallback`: a useful lexical/syntax result that visibly cannot make
  the skill's stronger semantic claim.

Missing project-local tools remain `tool-missing`; malformed selected syntax
remains `syntax-error`; unresolved or uncovered relevant files make the
artifact `partial`, not clean. `node --check` is sufficient only for declared
plain-JavaScript module modes and never establishes JSX or semantic support.
No framework meaning is inferred from JSX, dependencies, or file placement.

The serial mixed-language fixture includes `.js`, `.jsx`, `.mjs`, `.cjs`,
`.ts`, and `.tsx` plus test, generated/minified, vendor, ambiguous, and symlink
cases. Every cohort adds positive, negative, must-not-fire, malformed,
tool-missing, and partial cases appropriate to its fact level; native commands
are literal host package scripts and read-only source fingerprints must remain
unchanged.

### P2 cohort ownership

| Cohort | Skills | Shared-file rule |
|---|---|---|
| lexical/filesystem (6) | `adapt-project`, `explain-code`, `find-comment-drift`, `find-concept-divergence`, `find-duplication`, `find-folder-topology-drift` | Skill directories and cohort fixtures/learning only |
| syntax (4) | `audit-decisions`, `find-complexity-hotspots`, `find-omnibus`, `find-standard-gaps` | Skill directories and cohort fixtures/learning only |
| semantic/read-only (6) | `find-dormant`, `find-implicit-state`, `find-incomplete-sweep`, `find-semantic-duplication`, `map-subsystem`, `rename-concept` | Skill directories and cohort fixtures/learning only |
| proposal/mutation/guard (6) | `extract-enum`, `move-path`, `prevent-regression`, `propose-boundary`, `propose-folder-reorganization`, `unify-shadows` | Skill directories and cohort fixtures/learning only |

The serial owner alone changes source inventory, routers/catalogs, capability
and coverage matrices, shared harness code, plan/backlog files, and integrated
journey tests. Cohorts report evidence for those projections rather than
editing shared registries in parallel.

Acceptance:

- [x] All 76 skills have an explicit JavaScript disposition.
- [x] All 22 generally applicable language-level skills reach a useful final
      JavaScript outcome or have an evidence-backed explicit limitation; no
      skill claims support solely because TypeScript parses JavaScript.
- [x] `.js`, `.jsx`, `.mjs`, and `.cjs` first-party files are inventoried;
      mixed JS/TS roots cannot silently omit either language.
- [x] Semantic skills declare whether evidence comes from checked JavaScript,
      JSDoc, inferred compiler facts, or a partial lexical/syntax fallback.
- [x] Clear JavaScript prompts route to eligible closures; ambiguous mixed-host
      prompts ask or return a bounded set rather than guessing.
- [x] Every batch passes native fixtures, source-integrity checks, a fresh
      on-demand replay, and product-aligned review.
- [x] The final integrated suite and exact 76-row matrix check pass.

## Phase U1 — Installed user-journey stabilization

State: `complete`

This bounded interlude closes reproduced UX defects before another language
depends on the routers. It is not a general routing or evaluation platform.

Acceptance:

- [x] Proposal candidate limits include every cutoff tie and expose requested,
      eligible, returned, cutoff, tied, and omitted evidence consistently in
      Python and JavaScript/TypeScript outcomes.
- [x] The candidate-cutoff repair passes copied/final-artifact tests and a
      product-aligned review.
- [x] One committed corpus covers clear, ambiguous/direct, misleading/negated,
      varied-scope, and language/stack-bound cases for all three default
      routers.
- [x] Clear cases match their expected route or allowed set; confirmed
      high-impact misroutes become exact regressions before heuristic repair.
- [x] Every selected task skill exposes its exact on-demand closure and keeps
      ambient installation explicitly secondary.
- [x] One representative installed forward replay per router reaches the
      expected handoff or final outcome without loading unrelated skill headers.
- [x] Review finds no gating router-decision, handoff, or likely-user-harm
      defect; broader low-confidence cases remain in ML-007 with evidence.

Evidence:

- `5bc7618`: cross-language cutoff selection includes ties and reports omitted
  candidates; focused proposal suite passed 10 and bounded re-review passed.
- This revision: the committed 30-case corpus covers ten shape, eleven skill,
  and nine cleanup decisions. Confirmed defects became regressions for generic
  plan false positives, completed diagnosis, ordered phases, stack-bound
  handoffs, and cleanup path/Git resolution. The focused router surface passed
  201 with one intentional skip; the canonical `tests` suite excluding fixture
  projects passed 770 with two intentional skips. Installed copies of all three
  routers bootstrapped the on-demand library and reached their expected
  handoffs. Product-framed adversarial review findings were repaired and the
  bounded re-review passed.

## Phase P3 — Go three-family pilot

State: `complete`

Pilot families:

- read-only detector: `find-complexity-hotspots` using `go/parser`/`go/ast`;
- proposal: `propose-boundary` using explicit Go package/import facts; and
- mutation: `move-path` with an intentionally bounded Go import/update
  contract and `gofmt` plus `go test ./...` verification.

The pilot may revise these selections during P0 only if the replacement keeps
one detector, one proposal, and one mutation/guard outcome.

### Frozen pilot work packet

All lanes start from this revision and own disjoint skill, fixture, test, and
learning-packet paths. Shared source inventory, router/catalog projection,
capability matrix, plan status, integration tests, and final review remain with
the serial owner.

| Lane | Branch/worktree | Locked outcome |
|---|---|---|
| Detector | `codex/go-detector-pilot` | `find-complexity-hotspots` emits the existing final report from direct `go/parser`/`go/ast` function facts without counting nested closures. |
| Proposal | `codex/go-proposal-pilot` | `propose-boundary` emits a read-only proposal from one Go module/package graph, or defers on cohesive, unresolved, or ambiguous evidence. |
| Mutation | `codex/go-move-pilot` | `move-path` moves one reviewed leaf package directory, rewrites only AST-confirmed exact module imports, and rolls back on native failure. |

Each lane fixture is a standalone module outside repository discovery with a
`go 1.22` directive, positive and clean source, native tests, generated/vendor
must-not-fire source, and test-created malformed/tool-missing cases. The
selected skill must run from a copied on-demand closure with no third-party Go
dependency or repository import. Go is discovered from `PATH`, must be at least
1.22, and the exact resolved version/path is evidence rather than a hard-coded
workstation path. `gofmt` and `go test ./...` are native oracles.

The shared inventory now recognizes `.go` and `_test.go`; this does not promote
any skill. After the three lanes integrate, the 76-row capability matrix will
add one Go disposition per skill: only the three accepted pilots may be
`go-supported`, the other language-level skills remain
`pending-validation`, neutral/runtime rows retain their existing meaning, and
framework rows remain stack-bound. Routers must refuse a pending Go skill
rather than substituting a weaker one.

Acceptance:

- [x] All three closures run from the on-demand library against a locked,
      non-repository Go module.
- [x] Native Go tools and minimum versions are discovered explicitly; missing
      tools return unsupported rather than clean.
- [x] Positive, negative, must-not-fire, malformed, generated/vendor, and
      ambiguous fixtures exist for each family.
- [x] The detector emits its final ranked artifact, the proposal cites resolved
      package evidence, and the mutation produces only its declared diff.
- [x] `gofmt` and `go test ./...` pass after the mutation journey.
- [x] A fresh-context replay completes all three outcomes without consulting
      TypeScript implementation history.
- [x] The translation guide is revised with what transferred, what did not,
      and a measured estimate for expanding the remaining language-level
      cohort.

Expansion gate: do not schedule full Go coverage unless the pilot demonstrates
that at least two of the three family contracts transfer without skill-specific
platform work and the expected user value justifies the measured effort.

Gate decision: passed for staged expansion, not for a blanket conversion.
All three outcomes reached their final user boundary with family-local native
helpers and no shared execution/parser platform. The measured pilot also found
nine user-relevant contract gaps during review, so the remaining nineteen
skills are split into evidence-gated cohorts in the transfer guide rather than
launched as one campaign.

## Phase P3E — Staged Go expansion

State: `complete`

The user chose broader Go coverage as the main product lane before another
language or framework. ML-011 remains an independent bounded follow-up and
must not block this phase.

| Cohort | State | Owned skills | Gate |
|---|---|---|---|
| G1 orientation | complete | `adapt-project`, `audit-decisions`, `explain-code` | Copied closures reach adapter, drift, and explanation artifacts; 18 Go and 47 preserved-language tests passed; fresh review PASS after artifact-lifecycle repairs. |
| G1 lexical/topology | complete | `find-comment-drift`, `find-concept-divergence`, `find-folder-topology-drift` | Reports inventory first-party Go source with explicit generated/vendor/test boundaries; fresh review PASS. |
| G1 structural/standards | complete | `find-omnibus`, `find-standard-gaps` | Batched native syntax facts reach final reports; 51 focused/preserved tests passed; fresh review PASS. |
| G1D duplication | complete | `find-duplication` | Batched native exact-body evidence reaches final triage from a copied closure; 23 family tests passed and fresh product-framed review reached PASS after three bounded correctness repairs. |
| G2 semantic/project | complete | `map-subsystem`, `find-dormant` promoted; four candidates deferred | Two independent family-local pilots passed final artifacts, copied closures, preserved-language suites, and bounded re-review; actual overlap did not justify shared extraction. |
| G3 proposals/guards | complete | `find-implicit-state` → `extract-enum` → `prevent-regression` accepted at `4d295de`; capability closeout records the reviewed revision | One copied-closure maintenance loop reaches resolved detector evidence, a review-only typed-constant proposal, and a staged exact-field guard. Folder reorganization remained pending at this cohort boundary and was completed in G4. |
| G3 semantic maintenance | complete | `find-semantic-duplication`, `unify-shadows`, `rename-concept` | Resolved Go facts reach bounded detector, proposal-consumer, and lifecycle outcomes without inventing behavioral equivalence or a shared analyzer. |
| G4 final coverage | complete | `find-incomplete-sweep`, `propose-folder-reorganization` | Resolved option-struct/Git leads reach human verdict and triage; convention-authorized internal-package clusters reach a read-only current-module move plan. Go language-level coverage is 22/22. |

G1 promotion is per skill. Shared capability, matrix, router, and plan changes
remain serial; implementation lanes may not promote their own rows. Every lane
must preserve its prior language behavior, replay a copied on-demand closure,
run `go test ./...`, and capture transferable and non-transferable learning.

G1D promotes one additional skill after the G1 closeout: 12 of 22
language-level skills are supported and 10 remain `pending-validation`. The G1
learning packet is `.claude/tasks/multilanguage-learnings/go-g1-expansion.md`;
it deliberately keeps analyzers family-local and records only a conditional
future source-policy template, not a shared parser platform. G1D's
detector-specific learning is in
`.claude/tasks/multilanguage-learnings/find-duplication-go.md`.

### G2 pilot decision and acceptance

Two product-framed, non-context assessments selected `map-subsystem` and
`find-dormant`. `find-incomplete-sweep` and `find-implicit-state` are deferred
because their smallest honest Go outcomes are narrow and weakly actionable;
`find-semantic-duplication` and `rename-concept` are deferred until stronger
type/authority evidence can prevent misleading semantic or completeness
claims. Deferred means unpromoted, not silently substituted by a weaker skill.

The two pilots run in isolated worktrees and pass only when each:

- [x] runs from a copied on-demand skill closure using Go 1.22+ discovered
      from `PATH`, with no network or repository-runtime import;
- [x] reaches its final human-readable and structured artifact on a locked Go
      module while preserving every source byte and passing `go test ./...`;
- [x] proves positive, clean-negative, generated/vendor/test, build-constraint,
      malformed-source, and missing/old-tool outcomes without converting an
      incomplete analysis into clean;
- [x] preserves the existing Python, TypeScript, and JavaScript skill paths;
- [x] passes a product-framed fresh review and records transferable and
      non-transferable learning before per-skill promotion.

The post-pilot comparison found only conceptual overlap: both discover Go and
read `go list`, but `map-subsystem` owns current-build package/edge inventory
without type facts, while `find-dormant` owns package-local `go/types` object
identity, static use counts, and runtime uncertainty. Their inputs, failure
states, schemas, and copied closures differ. A shared primitive would add a new
runtime boundary without reducing either user journey, so both remain
family-local.

G2 raised Go coverage to 14 of 22 language-level skills. The closed-state and
semantic-maintenance G3 cohorts raised it to 20 of 22 after committed evidence.
G4 completes the final two rows without inheriting support: incomplete-sweep
has its own resolved-call/history/human-verdict journey, while folder
reorganization has its own explicit-convention/current-module-impact journey.
The accepted matrix is now 22 of 22 language-level skills.

## Efficiency gate E1 — Measured read-only batching

State: `complete`

The frozen ML-009 benchmark ran the same three copied read-only closures in
serial and at max-three concurrency for seven paired trials in both TypeScript
and JavaScript. All semantic projections matched; native checks passed; sources
were unchanged; and failures and interventions remained zero. TypeScript saved
414.719 ms / 50.19% at the median and JavaScript saved 409.126 ms / 49.42%,
with parallel winning 7/7 pairs in each language. Setup, native post-checks,
and artifact hashing were outside the timed boundary.

Decision: the evidence earns only the bounded explicit launcher experiment in
ML-011. It does not measure model tokens or actual filesystem reads and does
not justify automatic lens selection, a DAG/context cache, synthesis
coordination, or parallel mutation.

## Efficiency gate E2 — Compressed code-health family

State: `complete`

ML-020 converted the same three E1 lenses into one bounded routed health
journey: a 1,996-byte family core, three concise member contracts, per-member
capability-backed on-demand closures, explicit dependency skips, and a
family-local max-three read-only launcher. Individual skills remain directly
invocable; no member is added to the three-router ambient installation.

Five paired GPT-5.6 Luna trials ran four real tool/synthesis turns per
condition: full-skill serial, compressed-family serial, and compressed-family
parallel. All 15 timed conditions preserved canonical final-artifact outcomes,
native checks, incomplete states, and source bytes. The compressed parallel
condition reduced controlled prompt context by 78.84%, reported aggregate
tokens by 22.23%, and median model/tool/synthesis wall time by 52.68%. One
unseen host and separate serial/parallel invalid-standards sentinels passed.

Separate post-run product regressions prove all five exact natural prompts
activate the family, unusable standards and excluded-only targets remain
incomplete, mixed-language requests do not enter a one-language launcher, and
host-inactive members remain skipped during execution. Partial resume checks
use the frozen host digest. Future benchmark preparation
also records the route projection before model calls; the completed live run
constructed member commands directly.

Decision: adopt this one family. Do not infer a universal coordinator. The
551-line product launcher and 931-line evaluation harness are explicit bloat
signals; a second family must share the same invariants and reduce total
maintained code before extracting coordination utilities.

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

## Phase P5 — Core language queue and Java pilot

State: `in_progress`

The independent structural-tool and SkillOpt experiments are tracked in
`.claude/tasks/cross-language-tool-evaluation-plan.md`. They may run alongside
P5 because they touch only experimental artifacts. They do not block Java J1,
do not change a support row, and may not add a production dependency until
their adoption gates pass. This keeps parser research and skill optimization
from displacing the next user-visible language outcome.

The durable core is the set of ecosystems with broad professional use and a
credible native/offline analysis path for copied on-demand skills. Current
GitHub and Stack Overflow evidence keeps the already-earned Python,
JavaScript/TypeScript, and Go coverage at the front, then orders the remaining
work as follows:

| Order | Language | State | Reason / revisit boundary |
|---|---|---|---|
| 1 | Python | earned reference | Existing native reference paths. |
| 2 | JavaScript/TypeScript | earned | One closely coupled ecosystem; all 22 language-level outcomes have explicit evidence. |
| 3 | Go | earned | All 22 language-level outcomes have explicit bounded evidence; unsupported framework and toolchain cases remain honest rather than inheriting language support. |
| 4 | Java | active pilot | High professional/GitHub use and JDK 17 compiler-tree APIs are available locally without Maven/Gradle or third-party JARs. Java does not imply Kotlin support. |
| 5 | C#/.NET | queued | High professional use; start only after a real host proves copied, offline Roslyn/SDK resolution and `dotnet build --no-restore`. |
| 6 | PHP | queued | Material web/legacy cleanup value; require a representative Composer host and native parser/project boundary before semantic claims. |
| 7 | Rust | queued | Strong growth and native Cargo verification; require a stable offline syntax/project fact path without adding parser crates or assuming rust-analyzer. |
| 8 | Kotlin | queued separately | JVM proximity does not transfer Java compiler facts or earn Kotlin syntax/build support. |
| 9 | Ruby | queued | Rails/legacy cleanup value; require a representative Bundler host and honest native-reference boundary. |
| 10 | C/C++ | queued last | Large installed base, but compile databases, macros, headers, generated code, and build variance make low-overhead source facts hardest. |

Swift, Dart, Scala, Elixir, and other ecosystems are demand-triggered after the
core queue. This ordering uses the 2025 GitHub Octoverse language ranking and
the 2025 Stack Overflow professional-developer survey, then adjusts for this
product's copied/offline tooling constraint:

- https://github.blog/news-insights/octoverse/what-the-fastest-growing-tools-reveal-about-how-software-is-being-built/
- https://survey.stackoverflow.co/2025/technology

Only one language is active at a time. A language enters the earned core only
after a three-family detector/proposal/mutation-or-guard pilot; passing one
syntax adapter does not trigger broad parallel conversion.

### Java J0/J1 pilot

J0 state: `complete` at `e14274b`. J1 proposal is complete at `cfd0e2d` and
J1 mutation is complete at `cd7a445`. Java has earned the bounded three-family
pilot; the other 19 language-level skills remain explicitly pending rather
than inheriting Java support.

The local tool probe found OpenJDK/Javac 17.0.12. Java begins with one detector
implemented serially to establish the fixture and JDK invocation pattern:

1. `find-complexity-hotspots` — JDK compiler-tree syntax walk of declared
   methods and constructors; direct-body branch score only.
2. `propose-boundary` — one declared Java source/package area with resolved
   internal package/import evidence; proposal only.
3. `move-path` — one reviewed leaf-package move with exact package/import/FQCN
   updates and rollback on native failure.

Java J0 acceptance:

- [x] A locked standalone Java 17 fixture compiles without Maven, Gradle,
      network access, or third-party JARs.
- [x] The copied selected-skill closure discovers `java`/`javac` from `PATH`,
      records their versions, and does not import repository runtime code.
- [x] `find-complexity-hotspots` reaches final Markdown/JSON with positive,
      clean, generated/test, malformed, symlink, and missing/old-JDK outcomes;
      incomplete evidence is never clean.
- [x] Existing Python, TypeScript/JavaScript, and Go paths remain green and
      source fingerprints remain unchanged.
- [x] Fresh product-framed review and a Java learning packet pass before J1
      proposal/mutation lanes start.

Java J1 acceptance:

- [x] `propose-boundary` emits final Markdown/JSON from JDK-attributed package,
      import, and fully-qualified caller evidence, defers on a cohesive package,
      preserves source bytes, and runs from a copied selected-skill closure.
- [x] `move-path` moves one reviewed leaf package beneath the same source root,
      rewrites only compiler-attributed package/import/FQCN spans, compiles
      before and after, checks the exact diff, and rolls back a forced native
      failure.
- [x] Generated, malformed, excluded/non-leaf, symlink, dynamic-identity, and
      missing/old-tool boundaries never become clean Java outcomes.
- [x] The capability manifest declares exactly 3/22 Java language-level skills
      supported and leaves 19 pending; installed router journeys select all
      three supported families and reject unsupported Java families.
- [x] A fresh product-framed review passes and any accepted user-facing defect
      becomes a regression before Java closeout is committed.

The user accepted full staged Java expansion after the three-family pilot.
Java is now the only active language; C# does not start until every remaining
Java language-level row has either passed its own final-outcome evidence or an
explicit product-reviewed stop decision proves that a useful honest outcome is
unavailable.

### Java J2-J5 staged expansion

State: `in_progress`

The remaining 19 rows are owned in four batches. A batch may share fixtures or
invocation patterns, but each skill still needs its own final artifact and
capability evidence. Proposal/guard consumers do not reimplement upstream
detectors.

| Batch | State | Skills | Dependency |
|---|---|---|---|
| J2 lexical/filesystem | 6/6 integrated; review pending | `adapt-project`, `explain-code`, `find-comment-drift`, `find-concept-divergence`, `find-duplication`, `find-folder-topology-drift` | Accepted Java source-role and path boundaries. All six candidate outcomes are integrated through `71ffb81`; promotion still waits for product-framed review and closeout replay. |
| J3 syntax/reports | 3/3 integrated; review pending | `audit-decisions`, `find-omnibus`, `find-standard-gaps` | JDK syntax facts only where text/metadata cannot establish the final report. All three candidate outcomes are integrated through `29d21cd`; promotion waits for closeout review. |
| J4 semantic/project | 2/6 integrated; 4 active | `find-dormant`, `find-implicit-state`, `find-incomplete-sweep`, `find-semantic-duplication`, `map-subsystem`, `rename-concept` | Compiler attribution bounded to each claimed identity/relationship. `find-dormant` and `map-subsystem` are integrated through `13bd2b6`; state, relationship, and rename cohorts are active in isolated lanes. |
| J5 proposals/guards | 0/4 integrated; 4 active behind producers | `extract-enum`, `prevent-regression`, `propose-folder-reorganization`, `unify-shadows` | State and semantic consumers share their producer worktrees; folder proposal is active independently and remains read-only. No J5 row promotes before its accepted producer evidence. |

Execution ownership is deliberately smaller than those reporting batches:

| Cohort | Owned skills | Merge dependency |
|---|---|---|
| J2A source/text facts | `adapt-project`, `find-comment-drift`, `find-concept-divergence`, `find-folder-topology-drift` | none |
| J2B declared symbols/clones | `explain-code`, `find-duplication` | locked Java source-role fixture only |
| J3 report facts | `audit-decisions`, `find-standard-gaps`, then `find-omnibus` | none; omnibus keeps its existing human scout seam |
| J4A project graph | `map-subsystem`, `find-dormant` | none |
| J4B relationship leads | `find-incomplete-sweep`, `find-semantic-duplication` | none; Git evidence remains mandatory for incomplete-sweep |
| J4C state chain | `find-implicit-state` | lands before J5 state consumers |
| J4D rename authority | `rename-concept` | requires accepted J2A `find-concept-divergence` strict-text coverage |
| J5 consumers | `extract-enum`, `prevent-regression`, `unify-shadows` | accepted J4C/J4B evidence; no re-detection |
| J5 folder proposal | `propose-folder-reorganization` | explicit human cluster judgment; J2 topology evidence is optional input, not authority |

Per-skill acceptance:

- [ ] A locked Java 17 host reaches the skill's existing final human and
      structured artifact, not merely parser facts.
- [ ] The selected task skill runs from a copied on-demand closure with no
      network or repository runtime import. Skills claiming compiler facts
      discover host `java`/`javac`; lexical skills still name a native fixture
      check. No skill assumes Maven/Gradle unless it explicitly reports that
      build boundary as unsupported.
- [ ] Positive, clean-negative, generated/test/vendor, malformed or unresolved,
      symlink/path, and missing/old-tool behavior is explicit where applicable;
      partial evidence never becomes clean.
- [ ] Read-only skills preserve source fingerprints. Mutating or guard skills
      prove exact output plus native `javac --release 17 -proc:none` behavior
      and rollback/non-application on failure.
- [ ] Existing Python, TypeScript/JavaScript, and Go paths remain green for the
      touched skill family.
- [ ] A product-framed independent review separates user-facing fixes from
      backlog ideas and disproportionate hardening before the row is promoted.
- [ ] The batch records what transferred, what remained family-local, measured
      implementation cost, and whether any repeated Java bootstrap/path repair
      now satisfies ML-021's extraction gate.

Expansion completion:

- [ ] `java-language-coverage.json` contains 22 `java-supported` rows, or a
      smaller explicitly accepted maximum with named unsupported outcomes and
      user-approved stop decisions.
- [ ] The generated 76-skill matrix is current; installed router journeys
      select every accepted Java capability and reject any stopped row.
- [ ] Copied-closure, native fixture, preserved-language, strict metadata, and
      product-review gates pass at the accepted closeout revision.

Pilot planning history: the original J0/J1 plan was revised in `295a862`
before pilot implementation began. This J2-J5 expansion contract supersedes
the earlier demand-triggered stop after the user explicitly chose full Java
completion.

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
| P0 TypeScript synthesis | complete | P0 commit (this revision) | Accepted TypeScript coverage fixtures | Matrix/coverage/router: 51 passed; canonical: 666 passed, 2 environment skips | Fresh review found missing current closure paths; repaired; bounded re-review PASS | `.claude/tasks/multilanguage-typescript-transfer-guide.md` plus raw linked packets |
| P1 portability harness | complete | `2015c3f`, `7b4cd09`, and this revision | Synthetic seven-outcome hosts; fresh bootstrapped `map-subsystem` complete/partial hosts | Focused P1 integration: 90 passed; canonical: 686 passed, 2 documented environment skips; final collision regression: 3 passed | Fresh product-aligned review found four bounded defects; all repaired and bounded re-review passed | Capability projection, exact install evidence, test-only journey contract, and explicit TypeScript extraction stop decision |
| P2 JavaScript coverage | complete | baseline `eedb3ae`; cohort repairs through `e618ef4`; route/artifact repairs `fa26b9f`, `7713dc6`, `fb0c71d`, `23737ce`, `02524a1` | Inventory/matrix/router fixtures, all four cohort outcomes, and three fresh mixed JS/TS hosts | Focused repaired integration passed 115; final canonical root modules passed 681 with 1 intentional skip | Three forward journeys passed without route override; first RED routes and review findings became regressions; final product review PASS | 22/22 language-level skills promoted; accepted transfer guide captures native/family-local reuse, rejected custom lexer, route-first validation, and next-language brief |
| U1 router journey stabilization | complete | `5bc7618` and this revision | 30-case decision corpus plus copied default-router host | Focused router surface: 201 passed, 1 intentional skip; canonical tests: 770 passed, 2 intentional skips | Installed three-router replay passed; product-framed adversarial findings repaired; bounded re-review PASS | ML-007 retains only broader low-confidence ambiguity refinement; no general evaluator or coordinator added |
| P3 Go pilot | complete | `1b6e2eb`, `6de5762`, `966be1c`, `3492764`, `39115e7`, and this closeout | Three locked standalone modules plus generated/vendor/malformed/tool/topology cases | Go-focused families: 27 passed; preserved cross-language family set: 61 passed, 1 intentional skip; move-path Go/Python preservation after the staging repair: 29 passed, 1 intentional skip; capability/router projection: 71 passed; canonical suite before the final bounded staging repair: 807 passed, 2 intentional skips | Three non-context implementation lanes; each original product-framed reviewer returned PASS after bounded repairs; final closeout review also passed after the advertised staging path was repaired | Three `*-go` packet pairs plus the Go synthesis and measured expansion estimate in `.claude/tasks/multilanguage-typescript-transfer-guide.md` |
| P3E Go G1 expansion | complete | `e4fa2f4`, `dd37954`, `5298be2`, `bd9fe15`, and capability closeout | Eight skill-family Go fixtures with native modules and negative boundaries | Orientation: 18 Go + 47 preserved-language passed; structural/standards: 10 Go + 41 preserved/family tests passed; lexical/topology: 38 family tests passed | Three product-framed fresh reviews reached PASS after user-relevant source, status, filename-constraint, batching, and artifact-lifecycle findings became regressions | `.claude/tasks/multilanguage-learnings/go-g1-expansion.{json,md}`; 11/22 language-level skills now `go-supported` |
| P3E Go G1D duplication | complete | `22147a3` plus capability closeout | One native Go module with exact cross-file and same-file clones, clean/generated/test/vendor/build-constrained/malformed/tool failure boundaries | Go/Python/TypeScript/JavaScript family suite: 23 passed; Ruff and gofmt clean | Fresh product-framed review reached PASS after generated-only, same-file labeling, and partial-report repairs | `.claude/tasks/multilanguage-learnings/find-duplication-go.{json,md}`; 12/22 language-level skills now `go-supported` |
| P3E Go G2 pilots | complete | `94ce0d3`, `2147d5d`, `83d4767`, `0f2d458`, `eeb38da`, plus capability closeout | Independent package-map and dormant-review Go modules with active-build, generated/vendor/test, malformed/tool/symlink, source-safety, and final-artifact cases | Combined focused/preserved suites: 30 passed; final Go-only replay: 12 passed; Ruff, gofmt, and both Go vet checks passed | Map re-review PASS after two correctness and bloat repairs; dormant re-review PASS after last-good, active-build, symlink, malformed-sibling, and generated-evidence repairs | `.claude/tasks/multilanguage-learnings/{map-subsystem-go,find-dormant-go}.{json,md}`; 14/22 language-level skills now `go-supported`; no shared Go runtime extracted |
| P3E Go G3 closed-state family | complete | `4d295de` plus capability closeout | Standalone Go 1.22 module covers direct state operations, named authority, possible vendor boundary, generated/test/build-inactive, malformed/tool, proposal, and staged guard outcomes | Go focused 5 passed; TypeScript 2 and Python 5 preservation tests passed; Ruff, gofmt, go vet, native Go, pre-commit, and diff checks passed | Product-framed review found four closure/claim/fixture/portability defects; all repaired and bounded re-review PASS | `.claude/tasks/multilanguage-learnings/go-closed-state-family.{json,md}`; 17/22 language-level skills now `go-supported`; Go-specific guides load on demand |
| P3E Go semantic maintenance | complete | `bb4e5fa`, `3dff00d` | Compiler-resolved direct-call/return-shape, proposal-consumer, and rename-authority fixtures | Focused Go and preserved-language suites, copied closures, Go vet, Ruff, and strict skill metadata passed | Product-framed review passed after symlink and cross-package identity repairs | `.claude/tasks/multilanguage-learnings/go-semantic-maintenance-family.{json,md}`; 20/22 language-level skills became `go-supported` |
| P3E Go final coverage | complete | `24340ea`, `33c8f27`, `2b83ccd`, `88488c9`, `7f3da12`, plus capability closeout | Go option-struct/Git-trajectory host and convention-gated internal-package move hosts, including inactive, malformed, tool, symlink, dependency-scope, incomplete first-party graph, and copied-closure cases | Final focused Go + preserved TypeScript integration: 29 passed; both fixture modules pass `go test ./...` and `go vet ./...`; both helpers pass Go vet; strict metadata reports 76/76; source preservation is asserted | Blank-context allocation was blocked by the task-thread limit; an independent pre-existing product-review lane found the incomplete first-party graph defect, which became a regression before bounded re-review | `.claude/tasks/multilanguage-learnings/go-final-coverage.{json,md}`; 22/22 language-level skills are `go-supported` |
| E1 read-only batching | complete | benchmark implementation commit (this revision) | Fresh isolated TypeScript and JavaScript hosts per condition and trial | Focused contract: 2 passed; frozen benchmark: 7 paired trials per language, semantic/native/source gates all passed, zero failures/interventions | Fresh product-framed review found a single-language gate bypass; repaired at CLI and aggregate layers; bounded re-review PASS | `.claude/tasks/ml009-readonly-batch-results.json`; ML-011 is the bounded product follow-up |
| E2 compressed code-health family | complete | this revision | Five disposable TypeScript A/B/C triplets, one unseen TypeScript host, two invalid-standards sentinels | 15/15 timed conditions and 3/3 validation cases passed; context -78.84%, tokens -22.23%, median wall -52.68%; 78 focused product tests pass | Fresh product review and two bounded re-review turns closed seven user-real defects; final gate PASS. Live run directly constructed lanes; future preparation freezes route projections and partial resume uses the frozen host digest | `.claude/tasks/ml020-code-health-results.json` and `.claude/tasks/multilanguage-learnings/code-health-family-ml020.{json,md}` |
| P4 route frameworks | pending | — | — | — | — | — |
| P5 Java next-language pilot | complete (bounded 3/22 core) | `e14274b`, `cfd0e2d`, `cd7a445`, closeout commit | Three standalone Java 17 fixtures cover detector, proposal, and transactional mutation boundaries | Integrated Java/preserved proposal+mover/router+matrix replay: 120 passed, 1 intentional skip; canonical committed-head router replay follows closeout commit | J0 product review passed after four regressions; J1 fresh product-framed review found five user-facing defects, all became regressions, and bounded re-review PASS | Three Java packet pairs under `.claude/tasks/multilanguage-learnings/`; capability manifest records 3 supported and 19 pending; ML-021/ML-022 preserve simplification and evidence-integrity follow-ups |

## Final definition of done for this plan

- [x] The three-router installation and on-demand library journey remains
      usable and documented.
- [x] JavaScript has a complete, honest 76-skill disposition and all applicable
      language-level outcomes have validated evidence.
- [x] Go has passed the three-family pilot and either has an evidence-approved
      expansion plan or an explicit stop decision.
- [x] All 22 Go language-level outcomes have bounded evidence, copied/on-demand
      closure coverage, native obligations, and honest unsupported boundaries.
- [ ] Express and FastAPI route/workflow journeys reach consumer artifacts from
      framework-specific native fixtures.
- [x] The next major language and ordered core queue are selected from current usage evidence and local native-tool constraints.
- [x] Shared tooling exists only where at least two consumers prove the same
      primitive; no universal parser or execution platform was introduced by
      default.
- [x] Every completed phase links tests, native checks, fresh on-demand replay,
      product-aligned review, and reusable learning.
- [x] Remaining language, framework, and performance ideas are recorded in the
      backlog with concrete promotion triggers.
