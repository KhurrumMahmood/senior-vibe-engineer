---
name: structure-redesign-lessons
description: Lessons from System-tier project-structure-redesign scoping runs. Augments the standard /scope-feature Stage 2 questions when the work is structural (top-level shape, package boundaries, multi-app split, framework migration).
---

# Lessons — System-tier project-structure scoping

These augment the standard `/scope-feature` Stage 2 questions when
the work is a project-wide structural redesign. Surface them at the
right points in the conversation; do not bombard the user with all
of them at once.

The canonical structural design rules live in
`.claude/skills/_common/structural-design-principles.md` — read it
before driving these questions.

## Pre-Q1: Two-zone framing

Before asking the user for a one-sentence problem statement, ask
yourself: **does this project mix zones with different floors?**

Common zones:

- **Actual code zone** — framework + language norms (Django app
  boundaries, Python package semantics, JS bundler entry points).
  Floor is usually minimal; most of the layout is design space
  above it.
- **Agent/tool config zone** — `.claude/`, `.augment/`, `AGENTS.md`,
  IDE configs, skill discovery dirs. Floor is tool discovery
  conventions (skill directory shape, expected import paths,
  symlinks). Floor is usually intrusive; structural rules apply
  *softly*.
- **Build/CI/deployment zone** — `Dockerfile`, `manage.py`,
  `pyproject.toml`, GitHub Actions configs. Floor is "must stay
  where the toolchain looks for it." Usually fixed, narrow.

A two-zone problem statement names both zones and their floors. The
zones get different treatment downstream — what's a fixable
violation in zone A is "deliberately accept" in zone B. Without the
two-zone framing, scope creeps into agent-tool restructuring that
breaks discovery.

## Q2 augmentation: latent-design-choice checklist

Standard Q2 ("what's in scope?") often misses the choices that
*emerge from* a structural redesign. Walk the user through this
checklist before locking the in-scope list:

- **Templates location.** Project-level `templates/`, app-level
  `<app>/templates/<app>/`, or colocated with views? Cohesion
  argues for colocation; framework defaults push toward parallel
  hierarchies — see `_common/structural-design-principles.md`,
  rule 3 ("parallel hierarchies fail this rule").
- **Tasks placement.** Top-level `tasks/`, or colocated with the
  subsystem they serve? (Recommended: colocate. But Celery
  autodiscovery may break test mocks that target old import paths
  — investigate before deciding.)
- **Models central vs. distributed.** One central `models/` (with
  domain sub-grouping) or split per feature? Tied to
  single-app-vs-multi-app choice. Worth naming as a deliberate
  trade so the next agent doesn't undo it.
- **Tests mirror source.** Does `tests/` topology mirror `app/`?
  (Recommended: yes — find-test for tests becomes trivial.)
- **Substrate vs. feature.** Where does subsystem-internal code (AI
  runtime, crawler infra) live vs. feature code that uses it? Apply
  the test from `_common/structural-design-principles.md`,
  "Substrate vs. feature": *would this code still exist if we
  replaced the provider tomorrow?*
- **Framework-floor folders.** `management/commands/`,
  `templatetags/`, `migrations/` — Django mandates locations
  *within* the app. Inside a multi-package restructure, name where
  each lives.
- **Static files.** Same question as templates — colocate or
  centralize? Often a follow-on to template colocation.
- **Page-local components.** `pages/_components/` (route-mirror
  meta) vs. shared `_components/` at app root? Both have a place;
  admission rules matter (≥2 page subtrees use it before promoting).

Most of these surface as latent decisions during Stage 2-3. Naming
them up front shortens the conversation and prevents "wait, what
about X?" interruptions later.

## Q5 augmentation: success criteria for structural work

Structural redesigns have specific kinds of observables. Push for:

- **60-second discoverability test passes** — a stranger reading
  only top-level folder names locates the product, tests, docs,
  configs each in one folder hop.
- **Topology drift detector reports zero findings** in the bands
  the redesign aims to fix (e.g., `flat_prefix_cluster`,
  `tests_by_prefix`, `sparse_folder_package`).
- **Move-tool exists, has ≥N characterization tests, and is
  reusable** for future restructures (if scope built one).
- **No regressions** — full test suite passes; manual smoke-test of
  N representative pages confirms render parity.
- **ADR codifies the target** with the structural rules' applied
  form, deferred decisions and their revisit triggers.

Avoid: "feels cleaner," "better organized," "more intuitive."
Those are the *goal*, not the criterion.

## Iterative refinement is normal at System tier

System-tier scoping legitimately takes 5-8 conversational
iterations. Each iteration peels off another layer:

1. Problem statement
2. Target shape sketch
3. Zone framing (different floors per zone)
4. Cost calculus (manual vs. tooling-buildable)
5. Latent decisions (templates, tasks, models, etc.)
6. Final scope contract

If the user pushes back on a frame mid-conversation, that's the
skill *working*, not failing. Don't try to one-shot the scope. The
"surface uncertainty rather than guess" rule from the project's
workflow guidance applies more strongly here, not less.

## AI changes the cheap-vs-expensive calculus

Before deferring an "expensive" move on cost grounds, ask: *is the
cost manual or tooling-buildable?*

- Manual reference-updates across hundreds of imports → expensive.
- Sub-agent-built move-tool with characterization tests → cheap
  once the tool exists.
- The tool itself becomes a reusable artifact — the second
  restructure pays for the first.

This shifts what "cheap path" means in the scoping conversation.
The tool may belong as Q2 artifact #1 (in scope) rather than as a
prerequisite (out of scope).

See `_common/structural-design-principles.md` — "When the two
layers conflict" — for the canonical text.

## Frame-as-questions, not prescriptions

If the skill ecosystem may be open-sourced, the framing matters
more than the answer. A skill that *prescribes* (use `app/`, use
bounded contexts, use route-mirroring) only helps people who
already trust the prescription. A skill that *frames the right
questions* helps anyone — engineer, designer, non-coder — arrive
at a wiser shape themselves.

The five structural rules in
`_common/structural-design-principles.md` are still load-bearing,
but they should be paired with diagnostic questions that let a
reader derive each rule from first principles. Examples:

- Rule 1 (purpose-aligned top level) → *"If a stranger read only
  the folder names, what would they predict is inside? Does that
  prediction match reality?"*
- Rule 2 (depth = specificity) → *"Does each folder narrow the
  kind of thing inside it, or does it broaden the scope?"*
- Rule 5 (no prefix-as-fake-folder) → *"If you grouped these
  files by their prefix, would they form a coherent folder?"*

The wisdom is in the questions, not the answers.
