# Multi-language support backlog

Status: active backlog; no item here is committed implementation work

This file records useful follow-ups discovered while making the skill ecosystem
language-agnostic. It is intentionally separate from the active milestone plan:
an adversarial review finding belongs here before it belongs in a delivery plan.

## How to use this file

1. Keep each item in exactly one state: `proposed`, `candidate`, `scheduled`,
   `in_progress`, `done`, or `rejected`.
2. New review findings start as `proposed`. Do not promote them merely because a
   reviewer found a theoretical defect.
3. Promote an item to `candidate` only when its trigger is observed in a real
   host, a second skill/language needs the same mechanism, or a current product
   journey is measurably harmed.
4. Before setting `scheduled`, name the user-visible outcome, owned paths,
   smallest experiment, verification command or fixture, and explicit
   non-goals. Put scheduled work in the relevant milestone plan.
5. Set `done` only when the acceptance evidence is linked here. Set `rejected`
   with a short reason when the idea no longer fits the product.
6. Review this backlog after each language pilot and before planning the next
   one. Consolidate duplicate items rather than creating a platform-shaped
   variant of the same need.

Promotion remains subordinate to the product priorities: simple installation,
real multi-language support, then a better and faster installed journey. Work
that does not materially improve one of those outcomes stays deferred unless
it prevents concrete, likely user harm.

## Current TypeScript baseline

The completed language-level inventory contains 76 unique skill dispositions:
22 `typescript-supported`, 19 `validated-neutral`, 22 honestly `stack-bound`,
and 13 `ecosystem-runtime`.

For TypeScript-aware repository work, `.ts` and `.tsx` are the minimum source
ingress. Every first-party file with either suffix under the declared project
roots should be inventoried before a skill applies narrower eligibility rules.
Each exclusion must be attributable to an explicit role or boundary—such as
test, declaration, generated output, vendored dependency, build artifact, or
out-of-scope root—rather than silently disappearing from traversal.

Suffix coverage is only an inventory guarantee. It does not establish that a
file is semantically understood, relevant to a particular skill, or safe to
mutate. A skill may intentionally ignore an inventoried role, but its evidence
should make the eligible, excluded, unsupported, and failed-to-classify counts
auditable when completeness matters.

## Backlog

### ML-001 — Repository file-role and content classification

- State: `in_progress`
- User value: skills can reason about what a file *is*, not only its suffix,
  while avoiding generated, vendored, declaration-only, test, or configuration
  surfaces that require different treatment.
- Trigger: at least two skill families need the same role distinctions, or a
  real host shows material false positives/omissions caused by suffix-only
  discovery.
- Smallest experiment: produce a read-only manifest for one TypeScript host
  using repository boundaries, `tsconfig`/package metadata, paths, and minimal
  content facts. Allow `unknown` and multiple roles instead of guessing.
- Acceptance: all first-party `.ts`/`.tsx` files appear exactly once in the
  inventory; exclusions have machine-readable reasons; deliberately ambiguous
  fixtures remain unknown; two real skill consumers reduce a demonstrated
  omission or false positive without duplicating the classifier.
- Non-goals: a universal AST, a mandatory whole-repository indexing service,
  framework inference from package names alone, or mutation authority.
- Current slice: `scripts/source_inventory.py` inventories Python/TypeScript
  roles, visible unsupported-language files, excluded roots, and ambiguity.
  Its contract matches the accepted production-source boundaries of both
  `adapt-project` and `map-subsystem`; completion still requires demonstrating
  a user-visible omission or false-positive reduction in two consumers.

### ML-002 — Natural-language language and framework context for routing

- State: `proposed`
- User value: a user should not have to say “TypeScript” when strong project
  evidence already makes that unambiguous.
- Trigger: the next language pilot includes realistic prompts that omit the
  language and current routing selects an ineligible or weaker skill.
- Smallest experiment: compare explicit prompt context with strong host facts
  in a small mixed/single-language router corpus; ask or return unsupported when
  evidence conflicts.
- Acceptance: all clear single-language fixtures route to eligible skills;
  mixed or ambiguous fixtures do not guess; existing explicit-language and
  unsupported-route regressions remain green.
- Non-goals: ambient semantic indexing or automatic framework selection from a
  dependency name alone.

### ML-003 — Shared language-tool bootstrap and path-boundary primitives

- State: `proposed`
- User value: installed skills avoid repeating reliable compiler discovery,
  project-root containment, exclusion, and diagnostic handling.
- Trigger: a maintenance change must be made consistently in at least two
  accepted installed consumers, and a shared closure can still be installed by
  the stock installer without hidden repository dependencies.
- Smallest experiment: extract only the repeated behavior changed by that real
  repair; replay both consumers from copied installs.
- Acceptance: both consumers lose duplicated code, preserve their existing
  final outcomes, and install an exact declared closure; no unrelated analysis
  API is introduced.
- Non-goals: a general TypeScript analysis platform or universal language
  adapter before demonstrated consumers exist.

### ML-004 — Normalize and compress cross-language learning packets

- State: `done`
- User value: the next language can reuse proven contracts without loading the
  full TypeScript implementation history.
- Trigger: planning the first non-TypeScript pilot reveals which packet fields
  agents actually consume.
- Smallest experiment: synthesize the TypeScript packets into one family-level
  translation guide while retaining links to raw evidence.
- Acceptance: a fresh, non-context pilot agent can identify required native
  tooling, fixtures, false-positive boundaries, and installed-outcome checks
  without reading unrelated packets; raw evidence remains recoverable.
- Non-goals: deleting accepted evidence or designing a generic knowledge base.
- Evidence: P0 of `.claude/tasks/multilanguage-expansion-plan.md` generated the
  76-row matrix and `.claude/tasks/multilanguage-typescript-transfer-guide.md`.
  A fresh no-context reader found one missing current-closure field; after the
  repair, bounded re-review passed for all 22 language-level rows.

### ML-005 — Framework-specific TypeScript lanes

- State: `done_rejected_for_complexity_provider`
- User value: the 22 honestly stack-bound skills can support concrete Node,
  React, ORM, router, or UI ecosystems rather than making vague TypeScript
  claims.
- Trigger: a real host and named stack need one of these skills.
- Smallest experiment: select one coherent framework family and one useful
  installed journey; do not relabel all stack-bound skills at once.
- Acceptance: framework/version assumptions are explicit, must-not-fire
  fixtures protect other stacks, native checks pass, and routing selects the
  skill only for earned contexts.
- Non-goals: treating language support as framework support or covering every
  JavaScript framework speculatively.
- Scheduled scope: P4 of `.claude/tasks/multilanguage-expansion-plan.md` limits
  the first framework work to the route/workflow family, Express, and FastAPI.

### ML-006 — JavaScript disposition and shared JS/TS behavior

- State: `done`
- User value: repositories containing `.js`, `.jsx`, `.mjs`, or `.cjs` receive
  honest support instead of being accidentally included or omitted by
  TypeScript tooling.
- Trigger: JavaScript is selected as a supported language or appears in the
  next representative mixed host.
- Smallest experiment: inventory which TypeScript implementations already
  support `allowJs`/JSX safely and which depend on TypeScript-only guarantees.
- Acceptance: every generally applicable skill has an explicit JavaScript
  disposition and representative installed evidence; unsupported syntax and
  mixed-host behavior are visible.
- Non-goals: claiming JavaScript coverage from shared file traversal alone.
- Scheduled scope: P2 of `.claude/tasks/multilanguage-expansion-plan.md` owns
  the exact suffix set, mixed-host behavior, four independent cohorts, and the
  76-row completion gate.
- Completion evidence: 22/22 language-level skills are
  `javascript-supported`; three fresh router-only/on-demand outcomes and final
  product review passed; the canonical root-module suite passed 681 with one
  intentional skip. The accepted transfer guide records the bounded contract.

### ML-007 — Router decision-quality corpus across languages

- State: `in_progress`
- User value: the three default routers reliably lead agents to the right
  language-capable skill or to an honest unsupported/question state.
- Trigger: user-journey milestone work begins, after the next language scope is
  frozen.
- Smallest experiment: one committed corpus containing clear, ambiguous,
  negated, mixed-language, stack-bound, and direct/no-skill tasks.
- Acceptance: clear cases match; ambiguous cases name a discriminating
  question or allowed set; selected skills include their exact on-demand
  guide/tool closure and explicitly secondary install option; every repaired
  misroute becomes a regression.
- Non-goals: a general evaluator or learned router.
- Observed evidence: JavaScript P2 converted four exact natural prompts into
  regressions. U1 added a committed 30-case corpus across all three routers and
  repaired the gating tactical misroutes, ordered-phase errors, stack-bound
  handoff claim, and cleanup resolution failures. Generic database/API plans
  now abstain tactically; the shape router still represents them as a
  low-confidence fallback without an executable handoff. First-class ambiguity
  wording remains useful follow-up, but is not a reason to delay the Go pilot or
  expand this work into a general evaluator.

### ML-008 — Make proposal candidate cutoffs visible

- State: `done`
- User value: a boundary proposal does not silently omit equally ranked
  concerns merely because the command's candidate limit was reached.
- Trigger: the final JavaScript proposal journey required changing
  `--candidates 2` to `--candidates 4` after two equally scored domains were
  absent from the first artifact.
- Smallest experiment: report the count and scores of omitted candidates and
  either include ties at the cutoff or tell the agent which explicit flag will
  include them; keep documented and script defaults identical.
- Acceptance: a tied four-domain fixture makes every included/omitted domain
  visible, the final proposal remains deterministic, and ordinary small
  targets do not grow noisier.
- Non-goals: removing bounded candidate limits, adding a generic ranking
  platform, or blocking JavaScript P2 when the final artifact already includes
  the explicitly requested domains.
- Completion evidence: `5bc7618` includes all cutoff ties, reports deterministic
  selection/omission evidence in Python and JavaScript/TypeScript artifacts,
  passes the focused 10-test suite, and passed bounded product re-review.

### ML-009 — Cross-language batching and performance measurement

- State: `complete`
- User value: applying several relevant engineering lenses should be faster and
  repeat less context than running every skill serially.
- Trigger: representative installed workflows exist and serial measurements
  show material latency, token, or repeated-context cost.
- Smallest experiment: run up to three independent read-only lenses in
  parallel, keep mutation serial, and compare the same final outcome with the
  serial baseline.
- Acceptance: correctness does not regress; wall time, tokens, repeated context
  bytes, and human interventions are reported; coordination code is built only
  for a measured need.
- Frozen benchmark contract: seven paired trials for both TypeScript and
  JavaScript, alternating condition order, using the same three copied
  read-only closures (`audit-decisions`, `find-complexity-hotspots`, and
  `find-standard-gaps`). Serial and max-three parallel semantic projections
  must be identical, native checks must pass, source bytes must not change,
  and interventions/failures must remain zero. Setup time is excluded.
- Pre-declared materiality gate: native parallel execution earns a product
  launcher experiment only if each language saves at least 20% at the median,
  saves at least 100 ms in absolute median wall time, and wins at least five of
  seven pairs. Packet/closure/input-overlap bytes are reported separately;
  actual model tokens and OS read bytes remain explicitly unmeasured. A native
  pass cannot by itself justify an agent workflow coordinator.
- Non-goals: a workflow platform before a fixed benchmark demonstrates value.
- Completion evidence: `scripts/benchmark_readonly_lenses.py` and
  `tests/test_readonly_lens_batch_benchmark.py` produced seven correct paired
  trials per language with zero failures, interventions, native-check
  failures, or source changes. TypeScript saved 414.719 ms / 50.19% at the
  median and JavaScript saved 409.126 ms / 49.42%; parallel won 7/7 pairs in
  both languages. The compact result is
  `.claude/tasks/ml009-readonly-batch-results.json`. Each condition used the
  same 438-byte task packets and 167,171-byte copied closure; eligible-input
  overlap proxies were 1,774 bytes for TypeScript and 1,968 for JavaScript.
  Model tokens and actual filesystem-read bytes remain unmeasured, so this
  closes the native benchmark only and does not support a coordinator claim.

### ML-011 — Bounded explicit read-only launcher experiment

- State: `scheduled`
- User value: an agent can request a known set of independent read-only lenses
  once and receive their final artifacts faster, without ambient skill loading
  or a general workflow platform.
- Trigger: ML-009 passed its pre-declared materiality gate for both languages.
- Smallest experiment: expose an explicit ordered list of at most three
  capability-declared read-only closures, run them concurrently from the
  on-demand library, and return each lane's outcome independently.
- Acceptance: one fresh router-only TypeScript host and one JavaScript host
  select the fixed ML-009 lanes explicitly; no task skill is ambient-installed;
  final semantic projections match serial execution; one lane failure remains
  isolated and visible; mutations are rejected; and seven paired production-
  launcher trials preserve the ML-009 correctness gate and material wall-time
  benefit.
- Non-goals: automatic complementary-lens selection, dependency DAGs, shared
  context caches, retries, synthesis ownership, mutation parallelism, or an
  agent workflow coordinator. Any coordinator proposal requires a separate
  live-agent benchmark of tokens, context transfer, failures, and human
  interventions.

### ML-010 — Select and validate the next major-language pilot

- State: `complete`
- User value: TypeScript learning is converted into repeatable support for
  another common language without another blanket conversion campaign.
- Trigger: the TypeScript learning synthesis is usable and target-language
  demand is chosen.
- Smallest experiment: one read-only detector, one proposal skill, and one
  mutation/guard family in a single target language, selected for contract
  transferability and native tooling availability.
- Acceptance: all three run from stock-installed closures, reach their final
  useful outcomes on locked native fixtures, preserve unsupported boundaries,
  and produce an updated translation guide before wider batching.
- Non-goals: simultaneous full coverage of Go, Rust, Java/Kotlin, C#, and Ruby.
- Scheduled scope: P3 of `.claude/tasks/multilanguage-expansion-plan.md` names a
  three-family Go pilot and requires an evidence gate before broader Go work.
- Completion evidence: `1b6e2eb`, `6de5762`, `966be1c`, `3492764`, and
  `39115e7`; all three family reviewers passed after bounded repairs. The
  remaining nineteen skills are staged as G1/G1D/G2/G3 in the transfer guide.
- Residual Go backlog: add test-only caller impact to `propose-boundary` when a
  real proposal needs it; record the detector's resolved Go path in every final
  artifact rather than only its version. None changes the three accepted pilot
  outcomes or justifies a shared Go platform today.

### ML-012 — Evaluate ast-grep as an on-demand structural provider

- State: `done_rejected_for_complexity_provider`
- User value: syntax-oriented skills may gain new-language support with less
  bespoke parser code while keeping native semantic verification authoritative.
- Trigger: the Java pilot created a third language-specific implementation of
  the same bounded complexity fact family.
- Smallest experiment: X1 in
  `.claude/tasks/cross-language-tool-evaluation-plan.md` compares a pinned
  ast-grep CLI with the accepted TypeScript, Go, and Java complexity fixtures.
- Acceptance: exact parity gaps, false positives/negatives, malformed and
  exclusion behavior, LOC, latency, footprint, and network/cache requirements
  are measured; the result makes no semantic-support claim.
- Non-goals: replacing `rg`, replacing native compiler/project tools, adding
  ast-grep to the default router install, or blocking Java J1.
- Evidence: `.claude/tasks/tool-evaluations/ast-grep-results.json`. Exact final
  record parity was not enough to offset a roughly 268 MB cold cache, retained
  language-specific policy/identity code, and an invisible Java malformed
  parse. Revisit for a narrower structural-search outcome, not this family.

### ML-013 — Evaluate Tree-sitter language-pack as a syntax fact source

- State: `done_continue_pilot`
- User value: a cached grammar portfolio could lower the setup cost for queued
  languages while keeping capability claims honest.
- Trigger: C# and PHP are queued after Java and both need a credible syntax
  path before semantic work is planned.
- Smallest experiment: X2 in the tool evaluation plan tests pinned Java, C#,
  and PHP grammars in an isolated environment, including prefetch then offline
  replay.
- Acceptance: grammar availability, validated syntax facts, and semantic
  support are separated; cache/download size, parse-error behavior, query
  portability, and maintenance risk are measured.
- Non-goals: claiming hundreds of supported languages, a mandatory whole-repo
  index, or replacing native build/test/type tools.
- Evidence: `.claude/tasks/tool-evaluations/tree-sitter-results.json`. Pinned
  Java/C#/PHP grammars replayed offline with syntax errors visible; one real C#
  or PHP final-outcome pilot is still required before adoption.

### ML-014 — SkillOpt pilot for standards-backed skill effectiveness

- State: `done_inconclusive_no_headroom`
- User value: one high-leverage judgment skill is improved from scored evidence
  rather than prose preference, and the project learns whether optimization is
  worth its run cost.
- Trigger: `/scope-feature` has a clear standards contract and directly guards
  against product-goal drift, but currently lacks a held-out execution corpus.
- Smallest experiment: X3 in the tool evaluation plan freezes a compact corpus,
  baselines no-skill/current-skill, and permits SkillOpt to edit only a copied
  skill body under a one-epoch/two-edit budget.
- Acceptance: an untouched held-out comparison, hard standards gates, cost and
  variation evidence, and human review precede any production change.
- Non-goals: autonomous catalog evolution, session mining, coupled-skill
  optimization, or treating a training-score increase as product proof.
- Evidence: `.claude/tasks/tool-evaluations/skillopt-scope-feature/results.json`.
  The source revision, 6/2/2 corpus, deterministic scorer, production-copy
  boundary, and restartable runner are frozen. The four-call baseline cost
  41,847 reported tokens but no-skill and current-skill both passed 2/2, so no
  optimizer calls were justified. A retry requires natural prompts, hidden
  standards, harder binding-precedent cases, and measured run variation.

### ML-015 — Optional cross-file semantic index adapters

- State: `proposed`
- User value: skills needing definitions and references could consume an
  existing project index instead of reimplementing every language service.
- Trigger: at least two accepted skill consumers need the same cross-file facts
  in one language, or a representative host already produces `index.scip`.
- Smallest experiment: consume one existing SCIP index and compare it with the
  native provider; separately probe an already-installed LSP server without
  owning its lifecycle.
- Acceptance: symbol identity, definitions, references, incomplete-index state,
  freshness, and build/config provenance are explicit and useful to two final
  skill outcomes.
- Non-goals: maintaining an indexer/server fleet, requiring an editor daemon,
  or silently substituting syntax facts for semantic facts.

### ML-016 — Specialized security, policy, and migration engines

- State: `proposed`
- User value: mature engines may outperform home-grown rules for narrow deep
  security or large migration work.
- Trigger: a real host requests a security/data-flow audit or a Java/Spring
  migration whose native/manual implementation is materially costly.
- Smallest experiment: Semgrep for one tested local security/policy rule;
  CodeQL only through an existing CI database; OpenRewrite for one concrete
  Java/Spring recipe.
- Acceptance: final user outcome, licensing, setup/cache/network cost, false
  positives, and native verification are measured per engine.
- Non-goals: installing these by default or presenting them as a common
  cross-language analysis substrate.

### ML-017 — Framework practice adapters and external skill references

- State: `proposed`
- User value: framework-aware skills can turn official conventions into native
  checks and bounded facts without loading large best-practice packs ambiently.
- Trigger: P4 starts or a real host needs a named framework family.
- Smallest experiment: one route/workflow adapter plus official verification
  commands; React/Next and Spring are the next research candidates after the
  already-planned Express/FastAPI pair.
- Acceptance: version/detection evidence, source-role boundaries, dynamic-case
  unknowns, native commands, positive/must-not-fire fixtures, official source
  links, and last-reviewed version are recorded.
- References to evaluate rather than bulk-install: Vercel agent-skills,
  Addy Osmani agent-skills, obra/superpowers, GitHub Awesome Copilot, the
  Agent Skills specification, ast-grep's agent skill, Microsoft Waza, and
  Semgrep skills. Provenance and license must be recorded before adaptation.
- Research links: [Agent Skills specification](https://agentskills.io/specification),
  [Vercel skills installer](https://github.com/vercel-labs/skills),
  [Vercel framework skills](https://github.com/vercel-labs/agent-skills),
  [Addy Osmani agent-skills](https://github.com/addyosmani/agent-skills),
  [Superpowers](https://github.com/obra/superpowers),
  [GitHub Awesome Copilot](https://github.com/github/awesome-copilot),
  [ast-grep agent skill](https://github.com/ast-grep/agent-skill),
  [Microsoft Waza](https://github.com/microsoft/waza), and
  [Semgrep skills](https://github.com/semgrep/skills).
- Non-goals: inferring frameworks from dependency names alone, copying huge
  generated instruction dumps, or making framework packs default routers.

### ML-018 — Interchange and lightweight inventory tools

- State: `proposed`
- User value: external findings can integrate with host CI and broad declaration
  inventory may be cheaper than a semantic provider for orientation tasks.
- Trigger: a consumer requests GitHub/CI finding interchange or two orientation
  skills need declarations across unsupported languages.
- Smallest experiment: export one accepted finding set as SARIF 2.1; compare
  Universal Ctags JSONL with the selected structural provider for declarations.
- Acceptance: round-trip fidelity, provenance, source spans, limitations, and
  net implementation reduction are demonstrated.
- Non-goals: changing internal schemas to SARIF or presenting tags as references,
  types, or call graphs.

### ML-019 — Skill-effectiveness contract and trigger evaluation

- State: `proposed_after_core_product_outcomes`
- User value: a skill can be judged against explicit positive triggers,
  negative triggers, evidence/exit behavior, and context cost instead of prose
  preference or a benchmark that merely restates the answer.
- Trigger: a redesigned SkillOpt corpus or the planned router-quality
  validation begins after installer and core-language work.
- Smallest experiment: encode those four promises for `/scope-feature` and one
  deterministic skill, seed one realistic regression per promise, and compare
  a small local evaluator with Waza's spec-to-eval coverage approach. Do not
  adopt the Waza Go CLI merely to write the contract.
- Acceptance: each seeded regression is caught; an unchanged conforming skill
  passes; target prompts do not disclose hidden standards; repeated no-skill
  and current-skill baselines establish headroom and variation; token/context
  cost is reported before any optimizer runs.
- Sources: [Microsoft Waza](https://github.com/microsoft/waza),
  [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt), and the
  [Agent Skills specification](https://agentskills.io/specification).
- Non-goals: autonomous prompt rewriting, synthetic-score-driven production
  edits, or making a new evaluation runtime part of the default router install.

### ML-020 — Compress skill families and batch complementary lenses by default

- State: `queued_after_java_j1_before_broad_language_or_framework_expansion`
- User value: one routed family operation can cover the relevant engineering
  lenses with less repeated context and wall time than invoking several large
  skills independently, while the root agent receives one actionable result.
- Product hypothesis: many current skills are lens implementations rather than
  distinct user journeys. Keep the three ambient routers; have routing select
  one primary family outcome plus a small complementary coverage set; load one
  shared family core and concise member contracts into fresh execution lanes.
- Default execution boundary: run at most three independent read-only lenses
  concurrently with one synthesis owner. Keep user-decision stages and every
  mutation serial. Individual skills remain directly invocable and every
  skipped lens has an explicit reason.
- Trigger and sequence: complete the already-bounded Java J1
  `propose-boundary`/`move-path` pilot first. Run this experiment before
  starting broad C#, PHP, Rust, or framework-family conversion so a successful
  family unit can reduce that later work. It does not reopen X1-X4 or delay J1.
- Smallest experiment: choose one read-only SUSPECT/health coverage set with
  three already-proven lenses and real supported hosts. Compare (A) current
  full-skill serial execution, (B) compressed-family serial execution, and
  (C) compressed-family parallel execution. Use natural requests and hidden
  outcome checks; reuse the ML-009 launcher evidence but add model execution,
  synthesis, tokens, and actual context-byte measurements.
- Acceptance:
  - compressed serial preserves every required final finding/outcome and never
    turns incomplete evidence into a clean result;
  - parallel execution produces one deduplicated synthesis with the same
    accepted semantic projection and zero source mutations;
  - shared-family plus member context bytes fall by at least 30% versus the
    current full-skill condition, total reported model tokens grow by no more
    than 10%, and median wall time improves by at least 20% across five paired
    trials rather than merely shifting work to synthesis;
  - router output names the selected coverage set, dependencies, skips, and
    exact on-demand closure paths without ambiently installing member skills;
  - a fresh replay on an unseen host passes before the pattern is reused.
- Stop conditions: keep direct individual execution if compression removes a
  binding guard, batching increases total cost without better outcomes, lens
  findings cannot be reconciled deterministically, or a general coordinator
  becomes larger than the family-specific product work.
- Reusable outcome if successful: a small family manifest and launcher pattern,
  not a universal DAG, shared-context cache, autonomous mutation engine, or
  rewrite of every existing skill.

### ML-021 — Reduce repeated Java launcher/plumbing without sharing semantic facts

- State: `proposed_after_java_j1_measure_before_more_java_mutation_families`
- User value: copied/on-demand Java skills remain self-contained without making
  every new family carry another several hundred lines of path, compiler-launch,
  failure, and JSON plumbing.
- Trigger: a third Java family is proposed, or maintenance of either existing
  Java helper requires the same plumbing correction in both closures.
- Smallest experiment: identify only byte-identical or behavior-identical
  bootstrap/path/JSON routines in the 677-line proposal runner and 443-line
  mutation helper; compare a tiny copied utility closure against the current
  two independent runners.
- Acceptance: final proposal and transactional mutation outcomes remain equal;
  copied/on-demand execution still works; total maintained Java source shrinks
  materially; mutation span/rollback ownership and proposal clustering stay
  separate; missing utility evidence fails visibly.
- Stop conditions: reject the extraction if it creates a shared Java fact
  schema, makes one family import another, complicates selected-skill copying,
  or saves little code after tests and adapters are counted.
- Non-goals: a universal JVM platform, Maven/Gradle ownership, Kotlin support,
  or normalizing all language adapters behind one interface.

### ML-022 — Bind capability evidence to an accepted closeout revision

- State: `proposed_low_priority_integrity`
- User value: a `*-supported` matrix row can be traced to the revision that
  includes accepted review fixes, not merely any nonempty historical hash.
- Trigger: release automation starts consuming capability revisions, or a
  supported row is found to cite a pre-closeout implementation commit.
- Smallest experiment: add one optional closeout revision/source-tree digest to
  the language coverage schema and verify it against the release candidate.
- Acceptance: stale or nonexistent references fail generation while local
  uncommitted development remains possible; existing TypeScript/JavaScript/Go
  evidence can migrate without rewriting historical claims.
- Non-goals: commit signing, content-addressed installation, or reviving the
  discarded transactional-attestation platform.

## External release dependency (tracked, not a language feature)

The reviewed branch is still not the public source named by the README. Before
making public installation or TypeScript-support claims, publish the intended
revision and replay the documented public-source journey: install exactly the
three routers, bootstrap the non-discovered library, route to one closure, and
reach its final outcome without installing a task skill. This needs
repository-owner release authorization; it does not justify more installer
infrastructure and should not be implemented as part of an unrelated language
item above.
