---
id: 0002
namespace: core
title: Multi-file refactors are spec-first via ai-docs/specs/
status: accepted
date: 2026-04-30
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [ai-docs/specs/, .claude/skills/refactor-subsystem/]
tags: [refactor, spec, workflow, skill-ecosystem]
related_smell: omnibus-module
related_pattern: spec-first-refactor
---

# Multi-file refactors are spec-first via ai-docs/specs/

> Retro-authored ADR. The convention has been in force since
> `/refactor-subsystem` Phase 1.1 became mandatory; this ADR pins the
> rationale so future engineers and AI agents can trace it back.

## Context

Multi-file refactors (split an omnibus module, extract a service from a
fat view, decompose a god-class into a directory package) failed in two
characteristic ways before the spec-first convention was adopted:

1. **Scope creep.** A "split this view module" change quietly grew to
   include a model rename, a template restructure, and a JS rewrite.
   Every file looked plausible in isolation; the diff was unreviewable
   in aggregate.
2. **Lost characterization.** Implicit invariants (the order of two
   `.save()` calls, the side-effect of a hidden context-manager exit)
   weren't captured anywhere before the refactor moved them, so the
   verification step had no anchor for "is this still doing what it
   was doing?"

A separate failure was AI agents starting refactors with no inventory:
they edited what was visible in their context window and broke
invariants visible only in untouched callers.

## Decision

Every refactor that touches more than one file (or that splits one file
into a directory package) must be driven by a spec under `ai-docs/specs/`.

The spec must include, at minimum:
- A `code_roots:` frontmatter list of files in scope.
- A `## Goals` section — the why.
- A `## Architecture` section — the target shape.
- A `## Implementation` checklist with `IM-N: <description>` items.
- A `## Learnings` section — populated post-refactor.
- A `## Exceptions` section — known opt-outs from the convention.

`/refactor-subsystem` is the canonical executor. Phase 0 of that skill
scaffolds the spec via `python3 scripts/specs.py init <spec-id>`;
Phase 1 populates inventory via scout fan-out; Phases 2-7 execute
against the spec with two-commit discipline (behavior-preserving
refactor commit + separate bug-fix commits).

Behavior-preserving means: the refactor commit does not change observed
behavior. If a bug is discovered along the way, it gets a separate
commit with its own characterization test.

## Alternatives considered

- **No spec; PR description carries the plan.** Rejected: PR descriptions
  are not durable across the lifetime of the codebase, and they don't
  parse with `scripts/specs.py audit` to detect coverage drift later.
- **One large planning doc, not per-refactor specs.** Rejected: the doc
  becomes an unnavigable graveyard. Per-refactor specs each have a
  single owner and a single closure event.
- **Free-form refactor — trust the engineer.** Rejected by experience:
  scope creep and lost characterization are both AI-grown-codebase
  failure modes that strike experienced humans too. The discipline is
  cheap; the audit trail is expensive to reconstruct after the fact.

## Consequences

**Easier:**
- Reviewing a refactor — the spec carries the intent; the diff carries
  the execution. Diff reviewers don't have to guess scope.
- Catching scope creep — `IM-N` checklist items that don't appear in any
  commit, or commits that touch files outside `code_roots:`, are visible
  to `scripts/specs.py audit`.
- Resuming an interrupted refactor — the spec is the handoff document.
- Onboarding AI agents to a refactor — the spec is the durable context
  that survives compaction.

**Harder:**
- Starting a one-file refactor — Phase 0 of `/refactor-subsystem` is
  overhead. Single-file changes that are obviously local can use
  `/fix-workflow` instead, which has no spec requirement.

**Now expected:**
- `code_roots:` enumerates the in-scope files; nothing outside that list
  may be touched without amending the spec or filing a separate PR.
- Bug fixes surfaced during a refactor become separate commits, never
  bundled into the behavior-preserving commit.

## Verification

- **Tooling**: `scripts/specs.py audit` reports drift between
  `IM-N` checklist items and code refs (`# spec:<id>::<item>`).
- **Skill**: `/refactor-subsystem` enforces spec-first via Phase 0
  scaffolding gate.
- **Doc backref**: `.claude/docs/skill-catalog.md` REFACTOR section
  references this decision.
- **Existing artifacts**: every multi-file refactor since 2026-Q1 lives
  under `ai-docs/specs/` (e.g. `async-tasks.md`, `crawling-views.md`,
  `discovery-field-matcher.md`).
