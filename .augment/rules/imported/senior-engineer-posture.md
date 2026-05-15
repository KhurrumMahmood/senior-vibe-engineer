---
type: "always_apply"
---

# Senior-Engineer Posture

For non-trivial work — new features, underdeveloped features, major
rework, recurrent-headache surfaces, or any new UI surface — pause to
frame before choosing an approach. Trivial bug fixes / one-line tweaks /
clear-shape refactors are exempt.

In the response that accepts the task, before any implementation:

1. **Problem class** — name it in one line ("form-layout / IA problem",
   "long-running-job orchestration", "state-machine refactor",
   "discovery-pipeline addition").
2. **Canonical best practices** — what does good look like for this
   class? Industry baseline, key concerns, common failure modes.
3. **Existing skills / references** — `.claude/skills/`, Anthropic
   plugins (e.g. official `frontend-design`), prior decisions in
   `ai-docs/decisions/`. Skim if unsure. Don't install / enable anything
   without user confirmation.
4. **Approach scoped to the ask** — adopt, defer, or skip canonical
   practices deliberately, with the choice visible. Don't expand scope;
   don't gold-plate. Surface tradeoffs to the user when canonical
   practice and requested scope are in tension.

**Naming ≠ adopting.** Best practices have real overhead. Early
prototypes, exploratory features, and anything whose eventual shape is
unclear legitimately defer or skip them; just make the skip **visible**
(named, with a revisit trigger) rather than silent. Revisit when the
feature matures past prototype, when complexity arrives (third headache,
fourth call site, first regression), or when the feature is one you know
up front needs robustness from day one.

**UI surfaces specifically:** match the host project's shared
form-input family (e.g. a `.form-input` class chain or extracted Cotton
primitives); match neighbor patterns elsewhere; never leave raw
unstyled HTML in production templates. Reference: Anthropic
`frontend-design` plugin (built into Claude Code; enable via
`/config`). Don't install third-party UI skills without confirmation.

**Structural choices specifically (folder topology, module placement,
naming, top-level organization):** frame the design space in two
layers, in this order. (1) Framework and language norms are a
**floor** — hard constraints that break things if violated (Django
app boundaries, Python package semantics, test-runner discovery).
(2) Above the floor, maximally prioritize **intuitiveness and ease
of skimming** — a reader who has never seen this codebase scans the
directory listing and locates what they need without already knowing
the codebase. The floor tells you what you can't do; intuitiveness
tells you what to do with the freedom you have. Don't conflate the
two — "it's a Django app, so everything goes in `app/`" treats
framework convention as the answer when it's only a constraint.

Above the floor, five structural sub-rules apply at every depth:
(1) **purpose-aligned top level** (folder names reveal what kinds of
things live in them, not project history); (2) **depth =
specificity** (each level narrows scope; pure-grouping folders like
`util/` / `misc/` / `common/` fail this); (3) **cohesion =
colocation** (related code shares a file when small, a folder when
large; six prefix-siblings are a folder waiting to be born);
(4) **per-folder README as signpost** (folders self-describe via a
README that tells you what's in it and what isn't); (5) **no
prefix-as-fake-folder** (`<prefix>_<thing>.py` clusters become real
directories at the project's siblings threshold).
Canonical text:
`.claude/skills/_common/structural-design-principles.md`.

Full prose: `.claude/docs/senior-engineer-posture.md`.

**Comments/docstrings/JSDoc specifically:** comments explain intent,
ownership, caveats, compatibility, non-obvious history, or why a surprising
shape is deliberate; they should not narrate the next line. Keep comments
adjacent to the symbol/block they describe. Use concise Python docstrings for
route/view/service/workflow ownership, real JSDoc for public-ish JS functions
(`initialize*`, `handle*`, async/global/shared helpers), and Django-template
comments only for conditional rendering, shared payload/modal ownership, or
template gotchas. Delete stale terminology and visible-heading duplicates.
Use `/find-comment-drift` for the advisory audit; `comment-drift` blocks
clearly bad comment shapes on the live code surface.

**Product-health scanners specifically:** for non-trivial product-route
work, use the advisory scanners as before/after sensors when relevant:
`/find-contract-drift`, `/find-async-lifecycle-drift`,
`/find-dead-route-surface`, `/find-workflow-state-gaps`, and
`/find-test-obligation-drift`. Fix high-confidence new findings; triage
baseline findings separately. Capture false positives as fixtures, skill
knowledge, or explicit report tradeoffs. Promote detector bands to lints
only after fixtures, at least one real fix, explicit false-positive
handling, and low noise on the target surface.

**Implementation precedents specifically:** `.claude/docs/precedents.yml` is
the updateable case-law registry for recurring mechanisms. Use it when a
best-practice shape has canonical examples, guards, exceptions, and old
applications that should migrate together if the shape changes. ADRs preserve
history; precedents describe current law-as-applied.
