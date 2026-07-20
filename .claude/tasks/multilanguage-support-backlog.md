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

- State: `scheduled`
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
  regressions, but neighboring generic planning probes still chose
  low-confidence `bug-fix` at the shape layer and `extract-enum` for a database
  migration at the tactical layer. Those are real corpus seeds, not reasons to
  expand the completed language-outcome work into a general router rewrite.

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

- State: `scheduled`
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
- Non-goals: a workflow platform before a fixed benchmark demonstrates value.

### ML-010 — Select and validate the next major-language pilot

- State: `scheduled`
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

## External release dependency (tracked, not a language feature)

The reviewed branch is still not the public source named by the README. Before
making public installation or TypeScript-support claims, publish the intended
revision and replay the documented public-source journey: install exactly the
three routers, bootstrap the non-discovered library, route to one closure, and
reach its final outcome without installing a task skill. This needs
repository-owner release authorization; it does not justify more installer
infrastructure and should not be implemented as part of an unrelated language
item above.
