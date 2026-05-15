# Quality Coordination Kernel

Meta-architecture for the skill ecosystem and quality-coordination
machinery. Sits above `architecture.md` (codebase architecture) at the
level of "how does the project keep itself coherent over time."

Read this when:

- Designing a new skill, lint, pattern, ADR, or guardrail.
- Evaluating whether a maintenance practice is paying back.
- Onboarding to *why* the skill ecosystem exists in its current shape.
- Considering productizing the coordination machinery for another
  project.

Read **with** `architecture.md`, `canonical-patterns.md`,
`architectural-smells.md`, and the ADR registry under
`ai-docs/decisions/`. Those are the contents this kernel coordinates.

This is durable doctrine, not a backlog or a plan. Gap entries
graduate to plans (`ai-docs/plans/`) and specs (`ai-docs/specs/`)
when prioritized; open questions resolve into framework updates.

## 1. Framework

### 1.1 The four coordination functions

Distributed agentic work generates entropy. The coordination kernel
exists to make distributed work *compound* instead of *collide*.
Across human, AI, and hybrid execution, four functions do the work:

- **Direction Compression** — Convert open-ended environmental
  ambiguity into bounded, actionable objectives. A project's vision
  sentence (e.g. "fill the data gaps that external imports leave so
  the downstream view stays populated") is compression at the
  project level. Skill stop conditions ("file at path X with
  sections A/B/C") are compression at the task level. Without
  compression, agents optimize locally or freeze.

- **Decision-Rights Routing** — Map who decides what, when, with
  what authority. Centralize what must be coherent; delegate
  everything else to the edge. Weight-class inheritance (auth =
  critical, reporting = light) is decision-rights routing wearing
  different clothes.

- **Bottleneck Arbitration** — Stop work that doesn't meet the bar
  *at the bottleneck*, before bad work cascades downstream.
  Spec-first enforcement (`scripts/specs.py`) is the canonical
  example. Generalizes to: every skill output that admits a
  mechanical check should have a validator that gates the next
  step. Judgment-quality outputs (decisions, tradeoff captures)
  fall back to witness review or human approval — there is no
  mechanical equivalent, only weaker substitutes.

- **Adaptive Integrity** — Distinguish productive divergence
  ("learning") from objective decay ("drift"). Make the difference
  legible. Without this, AI-augmented maintenance produces a
  well-tended garden of incoherent decisions — every fix locally
  defensible, the aggregate nonsense.

### 1.2 Kernel as renderer; doctrine as state

The strongest frame for the coordination machinery is **one-way
data flow**: doctrine is *state*, code is the *view*, the kernel
is the *renderer*. Rule changes propagate as re-renders across
the view; without state, the renderer has nothing to apply.

This sharpens the kernel/contents split rather than replacing it:

- The **kernel** is the renderer — skills, lints, validators,
  ledgers, scaffolding under `scripts/`, and the graph +
  provenance layer (§5). Ships across projects.
- The **contents** are project state — vision sentence, system
  manifest, weight classes, rejected alternatives, ADRs. Do not
  ship; have to come from the project itself.
- A new project gets the renderer and the protocol for generating
  state, not someone else's state.

When later sections describe "the kernel" as portable, sellable,
or productized (§4.2, §5), they mean this same machinery layer in
different packagings — not a separate object. The renderer *is*
the thing that ships.

The renderer model is an *aspiration*, not a current description.
Today the ecosystem renders on user prompt — not on
state-change-trigger — and most edges between state and view are
implicit (re-discovered each invocation rather than persisted).
Closing that gap is what §5 (infrastructure) addresses.

The metaphor is also asymmetric: doctrine→view application is
one-way within a render cycle, but observations from execution
(skill failures, user corrections, surprise findings) propose
state changes through a separate decision path. §4.4 (skill
feedback) and §6 (how this doc evolves) live on that return path.
The renderer model governs *application*; it does not govern
doctrine evolution.

In the §1.5 regime (introduced below) the rendering target
multiplies — user-scoped deltas overlay canonical state at render
time. Application is still one-way per render; trickle-up
promotion runs on the doctrine-evolution return path.

### 1.3 Philosophy as prerequisite (in an AI-augmented loop)

Pre-AI, "doctrine in prose" was an acceptable substitute for
machine-readable philosophy because human contributors filled the
gap with judgment. AI-augmented maintenance breaks this assumption.
When fixes are also AI-produced and budget exists, the
human-attention filter that crudely prioritized "important"
findings disappears. Every finding becomes a candidate for fixing,
and without a machine-consumable form of project philosophy, every
fix defaults to local-correctness — which compounds into global
incoherence.

What needs to be machine-consumable is the **project state layer**:
system manifest (§3.1), weight classes, ADR `applies_to:` fields,
rejected alternatives — the artifacts agents must read per fix.
The doctrine *framework* (this doc, the patterns catalogue, the
smell taxonomy) can stay prose; it's read by humans designing
skills and lints, not consumed per-task by agents. The
prerequisite is that the state layer agents *do* read at fix-time
is machine-consumable enough for them to act on. Without that,
more throughput accelerates drift; with it, the loop has a chance
of being net-positive.

### 1.4 The four-outcome judgment step

When detection produces a finding, the next question is not binary
(fix / don't fix). It has at least four legitimate outcomes:

| Outcome | When | Required artifact |
|---|---|---|
| **Act** | Finding is real, obvious fix is correct | Standard `fix-workflow` output |
| **Document as tradeoff** | Finding is real, obvious fix violates an intentional choice | Captured rejected-alternative entry on the relevant system / ADR |
| **Reject finding** | Finding's framing is wrong for this surface | Annotation on the find-* report explaining why |
| **Escalate** | Finding hits a tradeoff not yet in philosophy | `/decide` invocation |

Today the existing skill chain handles **Act** well; the other
three have nowhere to go. Re-flagging is rampant on the same
patterns because there is no place to record "we already
considered this and chose otherwise."

### 1.5 The AI-managed product regime

The framework in §1.1-§1.4 applies generally; this section names
a regime variant where the framework can carry more weight
(governance instead of ownership), conditional on three
structural preconditions. Most current projects don't meet them —
the regime is forward-looking, not current operating reality.

Traditional product ownership exists because changes ship
globally, rollbacks are expensive, and accountability has to live
somewhere when things break. An AI-managed product can operate in
a different regime if three structural conditions hold:

- **User-scoped variation.** Mods affect only the originating
  user's view by default, with no path to mutate shared state
  (databases, caches, async jobs, search indexes, exported
  artifacts); promotion to canonical is a separate, governed
  step (§4.6).
- **Reliable safety floor (§3.10).** The properties that must
  hold on every code path — enforced infrastructure-side, not
  per-mod opt-in. Without this the bounded-blast-radius claim
  collapses.
- **Cheap revert.** Any user variation can roll back to canonical
  in one action with no cross-user cost. Assumes a versioned
  canonical baseline so revert stays deterministic after canonical
  evolves.

When these hold, the *governance* portion of the feature-owner
role decomposes into machinery: bounds, signals, mechanical
promotion gates. The kernel substitutes for that portion. The
*judgment* portion (what's worth promoting, which trade-offs to
accept, who eats a wrong promotion) doesn't disappear — it still
needs a §3.7 / §4.6-style judgment step, which is itself an open
mechanism. This is **not** "AI replaces PM/PO" — it's the regime
where the governance portion can be mechanical.

The regime is conditional, not universal — fail any of the three
conditions and "low risk" becomes "shared liability."

## 2. Current ecosystem

### 2.1 The maintenance loop

`map → suspect → explain → refactor → guard`. Each tier has skills:

| Tier | Job | Skills |
|---|---|---|
| MAP | Inventory existing structure | `map-subsystem`, `map-product-workflow` |
| SUSPECT | Detect smells | `find-omnibus`, `find-duplication`, `find-semantic-duplication`, `find-implicit-state`, `find-layer-violation`, `find-route-sprawl`, `find-workflow-duplication`, `find-frontend-contract-drift`, `find-contract-drift`, `find-async-lifecycle-drift`, `find-dead-route-surface`, `find-workflow-state-gaps`, `find-test-obligation-drift`, `find-doc-route-drift`, `find-dormant`, `find-query-mutation`, `find-comment-drift` |
| EXPLAIN | Annotate behavior + propose migrations | `explain-code`, `extract-enum`, `extract-state-type`, `introduce-fk`, `extract-workflow-registry`, `unify-shadows` |
| REFACTOR | Execute changes | `fix-workflow`, `refactor-subsystem` |
| GUARD | Crystallize learnings | `prevent-regression` |

### 2.2 Cross-cutting skills

Outside the linear loop:

- `triage-debt` — aggregator across find-* outputs; ranked queue.
- `audit-decisions` — ADR registry hygiene.
- `teach-pattern` — turn doctrine into agent-consumable briefings.
- `decide` — author/amend ADRs at any tier.
- `design-it-twice` — parallel-divergent fan-out for material design forks.
- `which-skill` — recommender that defends against skill misapplication.

### 2.3 Planning chain (System tier)

`scope-feature → impact-feature → architecture-fit → plan-spec` —
the judgment-paused chain for cross-subsystem work that doesn't
fit Quick or Feature tiers.

### 2.4 Doctrine artifacts

- `CLAUDE.md` — lean root pointer.
- `.claude/docs/canonical-patterns.md` — patterns + lints.
- `.claude/docs/precedents.yml` — updateable implementation case law:
  canonical examples, guards, exceptions, and supersession for recurring
  mechanisms that should migrate consistently when the pattern changes.
- `.claude/docs/architectural-smells.md` — smell taxonomy.
- `.claude/docs/architecture.md` — codebase architecture.
- `.claude/docs/subsystems/<name>.md` — per-subsystem inventory.
- `.claude/docs/workflows/<name>.md` — per-workflow topology.
- `ai-docs/decisions/` — ADR registry.
- `ai-docs/plans/` — in-flight plans.
- `ai-docs/specs/` — implementation specs.

## 3. Gap inventory

Surfaces the existing ecosystem doesn't yet cover. Each entry:
**what it catches**, **why it matters**, **dependencies**.

### 3.1 List-systems-with-philosophy *(prerequisite)*

**What it catches**: the project has no machine-readable inventory
of *what systems exist*, *what each is for*, and *how seriously
each should be taken*.

**Why it matters**: every other skill operates on named targets
(`map-subsystem <name>`, `find-omnibus <path>`). Without an atlas,
maintenance is reactive — it checks what you point at, never what
you forgot existed. In an AI-augmented loop this is a hard
prerequisite, not a nice-to-have: judgment requires the philosophy
layer, and the philosophy layer must be machine-readable for AI to
consume it.

The artifact would carry, per system:
1. Name.
2. The question this system answers for the rest of the site.
3. Weight class (blast radius + change frequency + correctness-criticality).
4. Patterns/lints/ADRs that govern it (and patterns that *should*
   govern it but have no enforcer — the active backlog).
5. Rejected alternatives — what this system chose not to be.

**Dependencies**: split. The structural inventory (name, import
graph) is auto-generable and has no dependencies. The
philosophical overlay (purpose, weight class, rejected
alternatives) depends on curation authority, project vocabulary,
and someone empowered to declare what each system *is for* —
which is the bootstrapping cost the artifact name disguises.
Calling §3.1 "foundational" without naming this is optimistic.

Downstream consumers: every other gap below.

**Implementation note**: probably auto-generated structural
inventory from the import graph + a curated overlay
(`.claude/docs/site-atlas.md` or similar) for purpose, weight, and
rejected alternatives. Drift check between regenerations.

### 3.2 Cross-file subsystem tangle

**What it catches**: package-level analog to `find-omnibus`.
Directories answering 3+ domain questions, circular imports,
reach-through into sibling internals, god-modules with high
fan-in, low-cohesion siblings.

**Why it matters**: today `find-omnibus` is single-file.
Subsystem-level mess is invisible until you read `map-subsystem`
output and spot it manually.

**Dependencies**: ideally consumes the system manifest from §3.1
to know what the package's intended responsibility is; without it,
"tangle" detection is purely structural and produces noise.

### 3.3 Leaky boundary detection

**What it catches**: drift between *intended* public surface
(declared exports, front-door module) and *actual* surface
(every symbol consumers import). Reach-throughs into deep
internals.

**Why it matters**: bespoke import-boundary lints (one per
isolated runtime / sidecar) are the right shape but one-off
guardrails. Every important boundary should get the same
treatment without writing a custom lint each time.

**Dependencies**: requires §3.1 to know which subsystems should
have declared boundaries at all.

### 3.4 Pattern-drift survey

**What it catches**: violations of canonical patterns that don't
yet have lints. Inverse of `prevent-regression` (which guards a
closed pattern); this surveys an open one.

**Why it matters**: `canonical-patterns.md` is doctrine. Without
pattern-drift detection, you can't ask "where does the codebase
not follow §X?" without writing a one-off ruff rule first.

**Dependencies**: weight-class scoping (§3.1) keeps the output
actionable — critical-weight violations get fixed, light-weight
ones get noted or accepted.

### 3.5 UI / template consistency

**What it catches**: same UX action with different class/treatment
across pages, inline styles vs. design tokens, repeated markup
that should be a partial, inconsistent button/form/dialog
patterns.

**Why it matters**: nothing scans visual/template consistency
today. `find-frontend-contract-drift` covers data contracts but
not visual treatment.

**Dependencies**: depends on having design tokens / canonical
components declared somewhere. A project with isolated patterns
(e.g. a single shared form-input class) but no system-level
vocabulary cannot scan against an absent target.

**See also**: §3.8 — write-time constructive complement to this
detective gap.

### 3.6 Decision noncompliance

**What it catches**: places where an ADR's prescribed approach is
not followed in code.

**Why it matters**: `audit-decisions` checks registry hygiene
(broken links, stale `proposed` decisions). It does *not* check
whether the *decision* is actually applied in the codebase. A
decision is wall art unless it's enforced — by a lint, a test,
or a noncompliance scan.

**Dependencies**: the ADR's `applies_to:` field needs to be
specific enough to scan against.

### 3.7 The judgment step

**What it would do**: between find-* and fix-*, evaluate each
finding against the philosophy layer and emit one of: act /
document-as-tradeoff / reject-finding / escalate (per §1.4).

**Why it matters**: see §1.3. Without this step, AI-augmented
maintenance treats every finding as actionable and produces
incoherent fixes.

**Dependencies**: §3.1 (the philosophy layer to judge against),
plus a destination artifact for the "document-as-tradeoff"
outcome that doesn't currently exist (rejected-alternatives
capture per system).

### 3.8 Constructive pattern libraries

**What it catches**: situations where the right answer is already
known, but the writer (human or AI) needs the pattern *available
at construction time*, not flagged after-the-fact in review.

**Why it matters**: the current ecosystem skews **detective** —
most skills find issues that already exist. Detective skills are
necessary but late; the issue had to be written first. A
**constructive** skill mode supplies the canonical answer up
front: "you're building a form — here's the form pattern." UI is
the salient example (one-off form-input classes are common; a
general component / token vocabulary is rare), but the same shape
applies to other domains where idiomatic answers already exist
(background-task dispatch, AI calls, export pipelines).

This expands the skill taxonomy: **detective** (find-*, audit-*),
**transformative** (extract-*, fix-*, refactor-*), **constructive**
(pattern libraries invoked at write time). The harness must
invoke constructive skills at the right point — when a write is
about to happen — which is a different triggering problem than
detection-on-schedule.

**Dependencies**: §3.1 (the system manifest tells the constructive
skill which subsystem the writer is in, and therefore which
patterns apply); §4.1 (the harness must fire constructive skills
before the writer commits to a non-canonical shape, or they're
useless).

**See also**: §3.5 — detective UI consistency complement.

### 3.9 Product-layer telemetry

Two consumers share one instrumentation backbone, with different
dependency footprints.

**(a) User-friction telemetry** (no preconditions). Workflow
abandonment, repeated attempts at the same action, time-on-task
creep, error rate by view, "user asked the AI for help and the AI
couldn't" events. Useful regardless of regime; most projects today
benefit from this gap closing.

**(b) Variation telemetry** (depends on §1.5). Which mods exist
per user, which canonical views they extend, outcome correlation
per variation.

**Why it matters**: today's telemetry frame is engineer-facing
(skill invocation outcomes, drift state, lint failures). The
*product* layer has no signal stream. Without (a), "users
complain" is anecdote — there's no way to compare a 12%-
abandonment view to a sibling at 2% or detect that a recent
change degraded a workflow before support tickets land. Caveat:
raw event counters aren't product intelligence — abandonment can
mean failure, success, or low intent; the schema needs cohort
normalization and sample-size discipline before it can nominate
canonical changes (the variation-telemetry consumer especially).

**Dependencies**: shares the instrumentation backbone with §4.1
mechanism 5 (skill telemetry) and §4.3 (ecosystem metrics) — same
data layer, different consumer schemas. Variation telemetry adds
§1.5 as a hard dependency.

### 3.10 Safety-floor primitive

**What it catches**: the absence of a unified, declared,
enforceable "safety floor" — the set of properties that must hold
for *any* code path, including AI-suggested variations,
user-scoped mods, and trickle-up promotions (§1.5). Today auth,
PII handling, performance bounds, prompt-injection resistance,
and trust-transfer rules are enforced piecemeal — middleware
here, a lint there, hope elsewhere. These are five distinct
concerns living at different layers (access control, data
governance, resource budgeting, adversarial input handling,
promotion governance); "safety floor" names the policy bundle,
not a single mechanism. Each layer needs its own enforcement
shape; the kernel-side artifact is the *declared aggregate* that
variation-governance (§4.6) and other consumers query.

**Why it matters**: piecemeal enforcement doesn't compose. A
declared, queryable aggregate lets §4.6's promotion gate validate
against the whole bundle in one step instead of re-deriving each
layer's verdict.

**Dependencies**: §3.1 (the system manifest names which
subsystems carry which floor properties).

**See also**: §1.5 (where the floor becomes load-bearing rather
than merely useful); §3.4 (detective form — pattern-drift survey
catches floor violations after the fact); §3.8 (write-time
constructive complement to enforcement).

## 4. Open questions

These don't yet have answers. They block specific gap work and
need their own resolution path before the gap entries above can
be safely acted on.

### 4.1 The harness question

**Telling an agent to do something in a skill prompt does not
guarantee it gets done**, particularly when skills define complex,
not-quite-coherent goals where some sub-goals are easier to focus
on than others.

What kind of harness mechanically forces effective execution?
Layered mechanisms, in roughly increasing leverage:

1. **Mechanical gates** — scripts that refuse to proceed without
   the required artifact. `scripts/specs.py` is the existing
   template. Generalizes to schema-checkable outputs only;
   judgment-quality skills (`decide`, `design-it-twice`, anything
   producing prose tradeoffs) fall back to mechanism 4 (witness)
   instead — gate-grade certainty isn't on offer there.

2. **Output schema enforcement** — required sections, required
   fields. Cheap and high leverage. Eliminates the "skip the step
   entirely" failure mode even if it doesn't ensure quality.

3. **Composable contracts** — skill A's output is skill B's
   typed input. Downstream consumption forces upstream rigor.
   Already partially true (find-* → triage-debt → fix-workflow);
   could be tightened with structural validation.

4. **Witness / evaluator pattern** — a separate agent with
   different prompting verifies outputs against skill goals.
   `/codex:review` is the closest existing example; the pattern
   generalizes to skill execution, not just code review.

5. **Telemetry** — log every skill invocation + outcome.
   Aggregator surfaces skills with high failure rate. **None of
   this exists today**, which means meta-level skill quality is
   invisible.

The right-time-invocation question is harder. It's a triggering
problem. Some triggers are obvious (lint on commit, scan on
schedule). Others are judgment calls: refactor-subsystem when a
file crosses N LOC? find-pattern-drift on every PR? after every
ADR merge? Bad triggering generates noise the agent has to ignore,
which trains the agent to ignore harness signals.

The unifying observation: **execution reliability and right-time
invocation are two halves of the same problem.** Both require the
harness to know what good output looks like in machine-checkable
terms. Skills with checkable success criteria can be both
validated (did it work?) and triggered intelligently (fires when
criterion is unmet). Skills without can't be either.

In practice you don't get guarantees, you get probability shifts.
Layered harness mechanisms make the cost of half-doing the work
exceed the cost of doing it properly — the closest thing to a
guarantee that's actually achievable.

#### 4.1.1 Model tiering depends on harness rigor

The harness question has a direct efficiency consequence:
**smaller/cheaper/faster models are reliable on small,
well-bounded tasks but unreliable on multi-goal skills.** When a
skill defines complex, not-quite-coherent goals, model capability
is what makes execution robust — running it on a smaller model
risks the agent focusing on the easy sub-goals and skipping the
hard ones.

The same harness mechanisms that improve execution reliability
(mechanical gates, output schemas, composable contracts) are the
precondition for safely routing subtasks to smaller models:

- A skill decomposed into validated, single-goal steps with strict
  output schemas can run each step on the smallest model that
  reliably hits the schema.
- A skill that has only a prose prompt and a trust-the-model
  boundary cannot — quality regresses catastrophically when the
  model class drops.
- Per-step telemetry (§4.1 mechanism 5) is what makes model
  selection empirical rather than guess-driven: which steps does
  Haiku-class actually pass? Which need Sonnet? Which justify Opus?

This means **task decomposition for reliability and task
decomposition for efficiency are the same activity.** Investment
in the harness layer pays off twice — once in execution
reliability, once in cost.

The corollary failure mode: skills designed without harness
investment become *trapped* on the most capable model, even when
most of their subtasks would run fine on something cheaper.
`.claude/docs/model-tiering-strategy.md` covers model sizing at
the runtime layer; the analogous question at the *skill* layer is
currently unaddressed.

### 4.2 Productization across projects

The kernel-vs-contents distinction (§1.2) suggests the skill
ecosystem should be packageable for use in multiple projects. The
contents — vision sentence, system manifest, weight classes —
won't transfer; the machinery should.

Open: what's the protocol for generating contents in a new
project? List-systems can produce a structural inventory
automatically; the *purpose + weight + rejected-alternatives*
overlay is human-curated. A bootstrapping skill (something like
`bootstrap-coordination-kernel`) could drive the curation
conversation.

Also open: which artifacts are universal kernel parts vs.
project-specific accidents? A given project's domain-specific
lint rules (e.g. a single dispatch helper that wraps a framework's
async API, or a typed-dict constraint for a particular external
schema) don't transfer. The *pattern* — "every cross-thread call
goes through a single dispatch helper" — is universal; the
specific lint that enforces it for one framework is not. The
kernel should ship the pattern, not the specific lint.

#### 4.2.1 Architectural defaults at project genesis

When the kernel enters a *new* project — not yet constrained by
existing architecture — it cannot stay neutral on early structural
questions: MVC vs MVVM vs CQRS, sync vs event-driven, monolith vs
service-per-domain, ORM vs hand-rolled query layer, server-rendered
vs SPA. These choices have decade-long consequences; the
database / ORM / rendering stack typically outlives every other
decision.

Two postures, both open:

- **Opinionated defaults** — the kernel ships a stack and patterns
  baked-in. Fast bootstrap; expensive to revisit; a wrong default
  shipped to many projects is much costlier than no default.
- **Decision-driver** — the kernel ships a skill that surfaces
  each fork as an early ADR before code is written. Preserves
  judgment; front-loads architectural cost on every new project.

The kernel may need both (defaults at the prototype tier, forced
decisions at the durable tier — see §4.2.2), but the hybrid
itself is an open design. Whichever shape wins, defaults must
*advertise* themselves loudly and stay obvious to revisit, not
get buried.

#### 4.2.2 Project-type calibration

Skill rigor isn't one-size-fits-all. A prototype built to
validate a problem (cost of incoherence: low; cost of slow start:
high) cannot run the same machinery as a durable system that
will outlive its author and carry production load (cost of
incoherence: high; cost of slow start: low relative to lifetime).
Construction discipline, ADR thresholds, planning-tier judgment
pauses, and verification matrices should scale to the project's
stakes — not default to maximum rigor for everything.

The kernel likely needs an explicit **project-type declaration**
(`prototype | feature-shop | durable | regulated`, or similar)
that calibrates ecosystem posture. Without it, prototypes get
over-rigorized or durable work gets under-rigorized depending on
which way the defaults lean.

Open: what's the right declaration shape? A single field is
crude (a prototype evolving into a durable system shouldn't
trigger a rewrite of every artifact); a per-subsystem weight
class (§3.1) is finer-grained but heavier to bootstrap. The
right answer probably interpolates.

#### 4.2.3 Cost economics

The kernel's value proposition is per-fix leverage. If running
the System-tier planning chain costs hours per change, the kernel
is unsellable to anyone whose first instinct is "vibe code a
weekend prototype" — which is most of the addressable market for
an AI-assisted quality tool.

Three things have to land for the value proposition to hold:

- **Substantially cheaper than human-curated review** — ideally
  an order of magnitude — or the "don't bother" alternative wins.
  Maintenance that costs the same as careful human review
  provides no visible value to a vibe-coding user; they weren't
  doing the review either way. The 10× target is a working
  aspiration; the doc has no current unit-economics measurement
  to defend it.
- **Bounded work per state change.** §5.3 is the canonical
  treatment; calling it out here just names it as a precondition
  for pricing.
- **Cheap default at the prototype tier, expensive at the durable
  tier.** Per §4.2.2 the project-type declaration governs which
  default fires; the prototype tier needs something close to
  "lints + critical-path guards only," skipping most of the
  System-tier chain.

Where the §1.5 regime applies, it shifts (rather than reduces)
the cost ceiling: per-change review can be lighter under bounded
floor + cheap revert, but the savings move into platform build
(variation storage, telemetry, promotion governance, incident
response on emergent failures after automated promotion). Net
cost is undetermined; most projects don't yet meet §1.5's
preconditions, so this is forward-looking.

Open: per-invocation cost is still measured in hours in
real-world use today — too expensive at the prototype tier. The
reduction has to come from §5 infrastructure (graph queries beat
re-scanning), project-type calibration (§4.2.2, skip the chain
at low tiers), and skill decomposition for smaller models
(§4.1.1). Which lever pays back most per unit of investment is
unmeasured.

### 4.3 Validating skill execution quality at the ecosystem level

Beyond per-skill validators (§4.1, mechanical gates) the
ecosystem-level question is: how do we know the maintenance loop
is net-positive? Candidate metrics:

- **Coordination entropy ↓** — fewer cross-skill conflicts,
  redundant work, context-switching penalties.
- **Adaptive throughput ↑** — faster sense → decide → execute
  loops without system fracture.
- **Overhead ratio** — leadership/coordination compute should
  scale *sublinearly* with system complexity. If it scales
  linearly or worse, the kernel is becoming the bottleneck.
- **Fix-to-coherence ratio** — analog to the human-era
  report-to-fix ratio, adapted: how many fixes maintain or
  improve project coherence vs. how many drift it, even if
  locally correct. (Hard to measure mechanically; probably
  needs a periodic witness-agent pass.)

None of these are currently measured. The first concrete harness
project is probably the telemetry layer that makes them
measurable in the first place.

### 4.4 Skill evolution via user feedback

Skills are designed in advance against a model of how they'll be
used. Real use surfaces nuances the designer missed — sometimes
**general** (the skill applies to a case its frontmatter implied
but the body doesn't handle), sometimes **contextual** (in *this*
project / *this* subsystem, the skill's defaults pull in a
direction the user doesn't want).

No mechanism exists today for the user to feed nuance back into
the skill itself. Workarounds — drop a memory note, hope the
next designer re-reads it, write a new ADR — none of these update
the skill's frontmatter or body.

Open: what's the lightweight feedback channel? Candidates:

- **In-skill capture** — every skill ends with "anything I
  missed?" and writes the answer to a per-skill `nuances.md`.
- **Telemetry-driven** — flag invocations where the user manually
  corrected the output; aggregate per-skill.
- **Witness-pass** — periodic agent that reads recent skill
  invocations and proposes frontmatter / body amendments.

The general-vs-contextual split matters for routing: general
nuances should update the skill itself (cross-project value);
contextual ones belong in the project's contents layer (system
manifest, weight classes, ADRs). Without the distinction, the
skill bloats with project-specific accidents — the same failure
mode §1.2 already warns against in the kernel-vs-contents split.

Linked to §4.1 mechanism 5 (telemetry) and §4.3 (fix-to-coherence
ratio): all three want the same instrumentation layer, just for
different consumers.

### 4.5 State-transformation skills (A → B)

The maintenance loop assumes incremental work: find local issues,
fix them, guard. It does not handle bulk reshaping — the case
where the *entire codebase* should move from state A to state B.
Examples:

- Adopt a newer pattern across every existing call site.
- Migrate a subsystem from one architectural style to another
  (fat-views → service-layer; sync → event-driven).
- Port the project to a different language / framework.
- Integrate end-to-end best-practice updates after a kernel
  upgrade in another project shows what the new ceiling looks
  like.

Mass transformation has different planning, sequencing, and
verification needs from the incremental loop:

- **Planning** — the goal isn't "every site of this pattern
  fixed" (loop-shape) but "this delta applied consistently
  end-to-end." Specs need a transformation contract, not a punch
  list.
- **Sequencing** — partial states must remain runnable. No
  realistic A→B campaign is a single PR; every commit along the
  way must be shippable.
- **Verification** — the existing test matrix verifies *behaviour
  preservation*; A→B transformations may intentionally change
  behaviour at the seams. Witness-style equivalence checking
  (run both versions, compare outputs) is closer to what's needed
  than unit-level pass/fail.
- **Rollback** — a transformation half-applied across 200 files
  can't be reverted by `git revert`. The skill must produce a
  rollback plan, or stage the transformation behind feature
  flags / parallel implementations from the start.

This is enough new discipline that it probably wants its own
skill class (transformation skills), distinct from REFACTOR
(which operates within a stable architectural model). Open: do
transformation skills compose with the existing System-tier
planning chain (`scope-feature → impact-feature → architecture-fit
→ plan-spec`), or do they need their own chain that explicitly
addresses the A→B-specific concerns?

### 4.6 Variation governance

In the §1.5 regime, variations are user-scoped deltas on top of
canonical. Concrete example: a user adjusts their site-config
sidebar to add a custom tab; the delta lives only on their
account; if 47 users do similar things, the popularity signal
makes the variation eligible for promotion to the canonical
sidebar. The open governance questions:

- **Promotion**: when does a popular variation become canonical?
  Pure-popularity thresholds are gameable and can promote local
  optima; pure judgment requires a human and defeats the regime.
  Probably hybrid — popularity gates *eligibility*, then a
  structured re-evaluation against the safety floor (§3.10) gates
  the promotion itself. Popular ≠ safe; promotion has to evaluate
  flaws the originating users didn't notice. This is the same
  shape as §3.7's judgment step, applied to variations rather than
  findings — same machinery, different input.
- **Demotion / retirement**: a canonical view outperformed by
  promoted variations should retire, but retirement breaks any
  user explicitly using the canonical shape. The regime needs an
  "old shape stays available as a variation" path (not deletion)
  plus a migration policy for users left on the retired shape
  (warn / pin / migrate).
- **Cross-variation synthesis**: 5 users solving one problem 5
  ways isn't 5 independent data points — they implicitly test
  trade-offs against each other. Extracting the trade-off
  structure (this is faster, that is more accessible, the third
  is more discoverable) requires analytics designed for
  cross-variation comparison, not per-variation usage logging.

Variation drift (a user's variation going stale when canonical
changes) is graph state, not governance — see §5.1 for the model.

This is enough surface area that it likely wants its own
governance skill (something like `evaluate-variation`), distinct
from the maintenance loop. Open: does it compose into the
system-tier planning chain, or sit alongside as its own stream?

## 5. Productization infrastructure

The renderer-vs-state framing (§1.2) only operates if state and
view are persistently linked. Today they aren't — every find-*
skill rediscovers edges from rules to code on each invocation.
That's the bottleneck behind several pain points:

- Rule changes have unknown blast radius until you re-scan.
- The judgment step (§3.7) has nowhere to record "this finding
  was evaluated against rule X v3 and rejected" so the rejection
  goes stale silently when X moves to v4.
- Token cost scales with doctrine size; loading the whole kernel
  doc into context is already noticeable, would be prohibitive
  at 10× the size.
- Work isn't quotable. "Apply the new pattern" is unbounded;
  "apply the new pattern to these 47 nodes" is bounded.

A *hypothetical* infrastructure layer with roughly four parts —
sketch-grade, not committed architecture (§5.5 names the open
questions). Each part below should be read as "what would have to
exist for the renderer model to be reactive," not as the current
shape of anything in the repo.

### 5.1 Graph + provenance edges

A persistent graph linking:

- **Rules** — entries in `canonical-patterns.md`, ADRs in
  `ai-docs/decisions/`, smells in `architectural-smells.md`,
  patterns from §3.8 constructive libraries.
- **Sites** — files, functions, modules, routes; the surfaces
  rules apply to.
- **Applications** — edges: this rule was applied at this site,
  at this revision, by this skill / this human.
- **Outcomes** — applied / rejected-with-reason /
  documented-as-tradeoff (per §1.4 four-outcome model) /
  superseded.

Edges are durable artifacts, not regenerated each scan. A rule
change becomes a state-delta query: "give me every site whose
last application of rule X is now stale."

In the §1.5 regime, the graph extends to track **variations** —
user-scoped state deltas that extend canonical site nodes. A
variation node carries `(user, delta, base_revision)` and is
linked to canonical via an "extends" edge. Variation drift is its
*own* state machine, not §5.2 with a user field added: a
variation can go stale because canonical moved, the delta schema
changed, the safety-floor version changed, the base revision
retired, or another promoted variation shifted the expected
baseline. Promotion to canonical (§4.6) retires the variation
node and updates the canonical node. "Which users have variations
of view X?" and "which variations drifted relative to recent
changes to X?" become cheap queries; both are core to variation
governance.

### 5.2 Drift state per node

Each (rule, site) edge carries a state:

- **clean** — site renders correctly under the current rule
  version.
- **dirty** — rule has changed since last application; node
  needs revalidation.
- **unrendered** — rule was added; node has never been checked.
- **rejected** — finding was reviewed and rule does not apply
  here, with reason.

Drift state is what makes the renderer reactive rather than
poll-based: changing a rule flips its edges to dirty; the
maintenance loop's job becomes "drain the dirty queue," not
"continually re-scan everything."

### 5.3 Diff-driven work sizing

Provenance edges + drift state turn rule changes into bounded
work units:

- "Update rule X" → "X has 47 dirty edges across these
  subsystems with these weight classes; estimated work: N hours."
- "Revisit ADR Y" → "Y's `applies_to:` field touches 12 files;
  3 are dirty, 9 are clean — light revisit."
- "Add new pattern Z" → "Z is unrendered everywhere; bulk
  initial pass, estimated cost M."

Bounded work is the only kind a productized tool can quote a
price on. This is what makes the kernel sellable at all (see
§4.2.3).

### 5.4 Graph as primary context retrieval

Once the graph exists, agents querying for context become much
cheaper. Today an agent loading "context for refactoring service
X" reads service X plus its tests plus the relevant doctrine
plus the relevant ADRs, all flat. With the graph, the same query
is "give me the subgraph rooted at service X within 2 hops":
rules that govern X, decisions that apply to X, sites that
depend on X, recent application outcomes at X.

This bears directly on model-tiering (§4.1.1). Smaller models
are reliable on small, bounded tasks — exactly what graph-scoped
context produces. The same harness investment that makes work
bounded also makes the work cheaper to run on smaller models;
productization compounds with the cost-economics tension in
§4.2.3.

### 5.5 Implementation shape

Sketch, not commitment. The first concrete project is probably
the telemetry layer (§4.3 already calls for this) — log every
skill invocation with rule + site + outcome metadata. Telemetry
plus the existing ADR registry + spec status + scan outputs are
most of the data the graph needs; the graph is the indexing
layer on top.

Open: which graph technology pays off here? A real graph DB
(Neo4j, Memgraph) is heavyweight. SQLite with a JSON edges
table might cover the read patterns. The doctrine artifacts
could themselves be the source of truth, with the graph as a
derived, git-managed-source-plus-regenerable-index shape — the
cheapest option and the most aligned with how the existing
artifacts work.

The lightest storage shape worth naming: **inline tags on sites**
— decorator-style annotations or comment markers that make the
rule→site edge part of the source itself, in the same family as
pytest markers, AOP advice, or Django `@receiver`. Forward
queries are cheap (the symbol's own annotation answers "what
governs *this* site?"), git tracks tags for free, and the §5.2
drift state falls out naturally: a tag with no recorded
verification is unrendered, a tag verified at rule v3 with rule
now v4 is dirty. Same state machine, stored inline rather than
in a side table.

Where the graph still earns its keep is **backward / multi-hop
reasoning** — the doctrine-update return path (§4.4 / §6)
effectively wants backpropagation. When real-world experience
invalidates an assumption (skill failure, ADR superseded,
surprise finding), the propagation question is "which other
rules and sites depend on the assumption that just got
invalidated?" That's a reverse + transitive query. Tags alone
answer it only by full scan; a derived index over them makes the
first hop cheap, and the graph can keep traversing —
site → other tags on it → other sites carrying those tags —
until the affected blast radius is enumerated.

## 6. How this doc evolves

The opening preamble already states the lifecycle (gap entries
graduate to plans, open questions resolve into framework updates).
A few specifics worth pinning:

- **Framework updates (§1) are rare** and deserve their own ADRs.
- **Current ecosystem (§2) is a snapshot**, regenerable from the
  skill catalogue; expected to drift, periodic resync is fine.
- **Resolved questions migrate from §4 into §1 and are removed**,
  not left as historical artifacts.

For everything else, use the right surface: `reports/BACKLOG.md`
for backlog, `ai-docs/plans/` for plans, `ai-docs/decisions/` for
ADRs, `ai-docs/specs/` for specs.
