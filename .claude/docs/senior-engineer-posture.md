# Senior-Engineer Posture

Practices to apply *before* picking an approach for non-trivial work, so
we ship code that respects system health, not just "got it done." Read
this when starting:

- a new feature being designed (not just added to an existing flow),
- a feature that's clearly underdeveloped and the task is to mature it,
- major rework / improvement on an existing feature,
- a surface that has caused repeated headaches because the original
  architecture was wrong, **or**
- any new UI surface (form, modal, page, template) — even when adjacent
  surfaces are messy.

Trivial bug fixes, one-line tweaks, refactors with a clear shape from
existing code, and anything explicitly marked throwaway/scratch don't
need this — just do the work.

This complements the existing skill ecosystem (`docs/skill-catalog.md`,
`.claude/skills/`): the skill machinery handles cleanup / planning /
decision flows when a skill fires; this doc handles the framing instinct
that should fire even when no skill applies.

## 1. Name the Problem Class First

Before committing to an approach, in the same response that accepts the
task:

1. **Problem class** — name it in one line ("this is a form-layout / IA
   problem", "this is a state-machine refactor", "this is a long-running-job
   orchestration problem", "this is a discovery-pipeline addition").
2. **Canonical best practices** — what does good look like for this class?
   Industry baseline, key concerns, common failure modes.
3. **Existing skills / references** — relevant skills under
   `.claude/skills/`, plugins (e.g. the official Anthropic
   `frontend-design` plugin), well-known tools, prior decisions in
   `ai-docs/decisions/`. Skim briefly if genuinely unsure; don't enable /
   install anything without confirmation.
4. **Approach scoped to the ask** — propose a path **informed by** the
   canonical practices (adopt them, defer them, or skip them —
   deliberately, with the choice visible), scoped to what was actually
   requested. Don't expand scope; don't gold-plate.

If a canonical practice and the requested scope are in tension, **surface
the tradeoff** before committing. Don't silently substitute "the best
version of this" for "the version the user asked for."

### Naming ≠ adopting

Best practices come with real overhead and often aren't worth paying —
particularly for early-stage prototypes, exploratory features, or anything
whose eventual shape is unclear. The right move is often to **deliberately
defer or skip** the canonical practice, write the minimal thing, and
revisit when:

- the feature matures past prototype,
- complexity actually arrives (the third headache, the fourth call site,
  the first regression), or
- the feature is one you know up front needs robustness from day one
  (compliance-bound, multi-tenant, mission-critical).

The point of step 2 is so you know **what** you're skipping, **why**, and
**when** to revisit — not to lock in compliance. A response like

> *"This is a long-running-job orchestration problem. Canonical answer:
> queue + retry policy + idempotency keys (Celery covers all three).
> Scope is one prototype script, so I'm using `subprocess.Popen` and
> skipping the queue — flag this for revisit if it gets a second caller."*

is exactly the shape we want. The skip is **named**, not silent.

## 2. UI Defaults Toward Decent

Specific instance of the rule above. When a task adds a new form field,
modal, page, or template surface — pause to pick a reasonable styling
baseline and information hierarchy, even if adjacent surfaces are messy.

**Why:** When existing UI defaults are messy (missing form-plugin
support, ad-hoc tone palettes, no shared primitives), that's a reason to
**stop the bleeding**, not a license to add more unstyled fields.

**How to apply:**

- **Form inputs** — use the project's shared form-input class or
  primitive. If one doesn't exist, surface that to the user before
  inventing a new shape.
- **Other surfaces** — match neighbor patterns; consider hierarchy
  (primary action prominent, secondary de-emphasized, scannable layout).
- **Never** leave raw unstyled HTML in production templates.
- **Exempt:** internal debug pages or quick scaffolding the user
  explicitly marks as throwaway.
- When the surface area is large or the IA is genuinely unclear, surface
  the design tradeoff to the user before committing — don't silently
  invent.

**Reference skills** (nice-to-have, surface when UI work is non-trivial;
don't enable / install without user confirmation):

- **Anthropic `frontend-design` plugin** (built into Claude Code) —
  enable via `/config` or `settings.json`:
  `"frontend-design@claude-plugins-official": true`. Designed to escape
  generic AI aesthetics and produce distinctive production-grade UI.
  Companion notebook:
  <https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb>.
- **`claude-code-frontend-dev`** (hemangjoshi37a, third-party,
  <https://github.com/hemangjoshi37a/claude-code-frontend-dev>) — visual
  testing with browser automation + screenshot validation. Useful if/when
  the project starts wanting visual regression coverage.
- **`interface-design`** (Dammyjay93, third-party,
  <https://github.com/Dammyjay93/interface-design>) — persists
  design-system decisions across sessions. Useful once the project has
  committed to a design language; less useful while UI defaults are still
  ad-hoc.

When picking up a substantial UI task, mention the Anthropic plugin to
the user (lowest-friction option — already shipped with Claude Code) and
offer to enable it for the work.

## 3. Structural choices: norms-as-floor, intuitiveness-on-top

When the task involves a **structural** decision — folder topology,
module placement, naming, top-level organization, skill grouping, or
any architectural choice that constrains where humans (and agents)
look to find things — frame the design space in two layers, in this
order:

1. **Floor — framework and language norms.** Hard constraints: things
   break if you violate them. Django app boundaries, Python package
   semantics, test-runner discovery, build-tool conventions. List
   them first; they're the constraints, not the goal.
2. **Above the floor — human-skim intuitiveness.** A reader who has
   never seen this codebase opens the directory listing, scans the
   names, and locates the thing they're looking for *without already
   knowing the codebase*. That is the bar.

The failure mode is treating the floor as the answer ("it's a Django
app, so everything goes in `app/`") when the framework only mandates
*that* the package exist, not *what to call it* or *how to organize
content inside it*. The opposite failure is ignoring the floor in
pursuit of intuitiveness — splitting a Django app along workflow
lines without realizing the framework needs the package boundary to
stay coherent.

**Why** — the project's top-level layout is itself an architectural
surface ("why is `views/` inside `app/`? why is `app/` called
`app/`?"). Surfacing the two-layer rule explicitly is what stops
the next agent from re-deriving the same surface from first
principles or, worse, from anchoring on framework convention as if
it were the answer.

**How to apply** — when a structural choice is on the table:
- State the framework constraints first (the floor — what would
  break).
- Evaluate options against the skim test, find test, and cluster
  test (above the floor) named in
  `.claude/skills/_common/structural-design-principles.md`, then
  against the five structural sub-rules in the same doc:
  (1) purpose-aligned top level, (2) depth = specificity,
  (3) cohesion = colocation, (4) per-folder README as signpost,
  (5) no prefix-as-fake-folder.
- If the chosen option is constrained by the floor (e.g. preserving
  a single Django app), name the constraint visibly so the
  intuitiveness loss isn't invisible.

**Reference skills / docs** — the canonical, cross-skill,
cross-project text is at
`.claude/skills/_common/structural-design-principles.md` (sibling of
`_common/interface-depth.md`). Topology-specific application is in
ADR 0006 (`ai-docs/decisions/0006-folder-organization.md`,
intra-folder discipline). Decision-shaping skills (`/architecture-fit`,
`/decide`, `/propose-folder-reorganization`) load the `_common/` doc
when evaluating structural options.

## 4. Outward-Facing Quality: assume hostility, failure, and an audience

Sections 1–3 are mostly *inward* — is this code clean, well-placed,
maintainable? Carry a second axis the inward lens never surfaces: how the
system behaves under a hostile input, a failing dependency, a 3am page, a
privacy obligation, and a bill. Name which of these a change touches
**before** picking an approach — most changes touch at least one.

The axis has five faces:

- **Security** — trust boundaries, authorization (not just
  authentication), injection, secrets, SSRF, and — for AI features —
  prompt injection and LLM-output-as-code.
- **Resilience** — timeouts, retries, idempotency, partial-failure
  behavior, not holding a transaction open across a network call.
- **Observability** — *two* halves. *Application*: can an operator tell
  what broke (structured logs, surfaced errors, metrics)? *Product*: can
  the team tell how users actually move through a workflow — where they
  stall, what they abandon, what they like (usage events on key
  journeys)? You can't debug or improve what you can't see.
- **Data / privacy** — what's sensitive, where it flows, who can see it,
  whether it lands in logs or LLM prompts, whether a user can delete it.
- **Cost / abuse** — can a caller drive unbounded crawl / LLM / export
  spend? Especially acute for AI products.

**Why** — most quality instinct is inward; this axis only shows up when
you deliberately adopt the frame of an attacker, an operator, or an end
user. The instincts below generalize better than any checklist:

- **Trust boundaries are where bugs become vulnerabilities.** Ask "where
  does data cross from less-trusted to more-trusted?" — every crossing
  needs validation or encoding. (Input parsing — a `safe_int` helper — is
  already this instinct.)
- **Default deny, fail closed.** A new endpoint is unauthorized until
  proven otherwise; an error denies rather than falling through to allow.
- **Three separate adversaries:** the input is hostile, the network is
  down, the dependency is compromised. Defend against all three.
- **Irreversibility raises the bar** — deleting, charging, emailing,
  publishing, executing: guard these.
- **Blast radius** — "if this credential / endpoint is compromised, what's
  the worst case?" drives least-privilege.
- **Make the secure path the easy path** — a default-secure base class or
  a linted wrapper beats a rule nobody follows under deadline.
- **It decays** — deps rot, a new endpoint skips the check, a refactor
  drops a guard. *Coverage* and *regression guards* beat one-time audits.

**Stage the controls to maturity** (the §1 "naming ≠ adopting" rule
applies — the failure mode is binary: ignoring this axis, or gold-plating
a prototype with security theater):

- *Prototype* — only the irreversible / exfiltrating floor: secrets never
  in git, never log secrets or PII, parameterized queries, no real
  charges / emails / deletes without a guard.
- *First real users* — authn + authz on every endpoint, input validation
  at boundaries, a dependency-vuln signal, outbound timeouts.
- *Multi-user / money / sensitive data* — object-level authorization
  (IDOR is the most common real-world web vulnerability), rate-limited
  expensive paths, mapped PII flow, audit trails.
- *Scale / compliance* — lightweight per-feature threat modeling, secret
  rotation, least-privilege accounts, supply-chain checks, an incident
  runbook.

**How to apply:**

- **Declare the floor as standards.** Deterministic always-on rules
  ("outbound calls set a timeout", "no `eval`/`exec` on untrusted input",
  "service code logs, not prints") live in `/find-standard-gaps`
  (`standards.example.json`) as `ast`/`grep` detectors, coverage-checked
  across the tree.
- **Record the ceiling as `manual` standards.** Judgment-heavy rules no
  AST captures ("authorize against the object, not just the user", "no PII
  in prompts", "expensive endpoints are abuse-bounded", "external content
  is contained at the boundary") are declared `kind: manual` — the
  baseline stays complete, and these are what the role-based review-avatar
  lane checks.
- **Turn every found issue into a guard** — a vulnerability fixed once is
  a regression waiting to happen; feed it to `/prevent-regression`.
- **ADR the architectural calls** — the trust-boundary posture, the SSRF
  allowlist, the authz model constrain future work; record them with
  `/decide`.

**Reference skills / docs** — `/find-standard-gaps`
(`standards.example.json` ships a security / resilience / observability
baseline), `/prevent-regression`, the two-lane code review (general +
adversarial), and `/design-it-twice` as the parallel-divergent fan-out
pattern the review-avatar lane mirrors.

## Adding New Domain-Specific Instances

When a new "before-you-act framing for a problem class" rule emerges —
e.g. DB schema design, async pipelines, AI-prompt design,
long-running-job orchestration — follow the same shape as §2:

- **Why** — the project context that motivates the default.
- **How to apply** — concrete patterns / exemplars / "use X, see Y".
- **Reference skills** — pointers, not installs.

Add the new rule as a new section in this file rather than splintering
into separate docs. The principles above are mutually reinforcing, and
the discoverability comes from one entry in `CLAUDE.md` plus the
cross-tool mirror at `.augment/rules/imported/senior-engineer-posture.md`.
