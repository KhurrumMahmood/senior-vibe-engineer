---
id: "0041"
namespace: core
title: "Bindings are profile-selected, ordered overlays with ambiguity as an error"
status: accepted
date: 2026-07-16
deciders: [khurrum, codex]
assumes: ["a skill's portable procedure must remain understandable without a framework binding", "host profiles can identify languages, frameworks, tools, and roots before routing"]
revisit_when: ["two real bindings require non-monotonic composition rather than ordered overlays", "a supported agent cannot load the selected binding without copying the core procedure", "per-root selection cannot express a mixed monorepo"]
supersedes: []
superseded_by: null
applies_to: [.claude/skills/, .engineering/manifest.json, scripts/installer_selection.py]
embodied_by: ["doctrine:.claude/skills/_common/capability-registry.yml", "script:scripts/installer_selection.py", "contract:tests/test_capability_consumers.py", "pending:WP3 implements binding documents and the extract-enum exemplar"]
tags: [bindings, skills, routing, layers, portability]
related_smell: missing-boundary
related_pattern: null
---

# Bindings are profile-selected, ordered overlays with ambiguity as an error

## Context

ADR 0034 established concept-plus-binding as the default for general concepts
with stack-specific idioms, but did not define how a binding is named, selected,
or loaded. Without that contract, a router could silently pick Django for a
Python host, load React merely because Vite is installed, or combine two same-
precedence bindings in an order no author intended.

## Decision

A core skill owns one framework-neutral `SKILL.md`. Optional overlays live at
`bindings/<binding-id>.md`; binding ids and their compatible language/framework
sets come from ADR 0038's registry. Binding documents contain idioms, adapter
pointers, commands, and executable examples—not a copy of the core procedure.

Selection is per canonical project root and is computed from the approved host
profile. The deterministic precedence is:

`core -> language -> framework -> domain -> host overlay`

Every selected overlay must be compatible with the root's language/framework
and declared skill binding. Zero matches means the capability is unsupported
for that root and fails loudly when required. More than one match at the same
precedence is an ambiguity error unless the host manifest explicitly selects
one id. Detection order, directory order, and “first installed” are never
tie-breakers. Mixed monorepos retain isolated per-root selections and compose
only at the orchestration boundary.

Legacy flat skills are read as their existing implementation during migration;
they do not acquire a portable core claim. WP3 first implements one exemplar,
then WP8 converts the catalog. Invocation names remain stable through aliases.

The `/extract-enum` exemplar is designed as:

- core: identify a closed state vocabulary, preserve wire identifiers, plan
  call-site migration, and verify behavior;
- language overlays: Python and TypeScript symbol/reference/change mechanics;
- framework overlay: Django `TextChoices` and migration/wire-value constraints;
- host overlay: project-specific enum base classes or lint commands.

The core makes no Django/React API reference. A TypeScript host selects the
TypeScript language overlay and its native compiler guard, not Django. React is
not selected merely because Vite/Vitest is present; those are tools.

## Alternatives considered

- **Copy the full skill per stack.** Rejected because procedural corrections
  drift across copies.
- **Put all framework branches in one SKILL.md.** Rejected because every host
  loads irrelevant instructions and core leakage becomes untestable.
- **Let the agent choose an overlay from prose.** Rejected because ambiguity
  and unsupported states would be nondeterministic.
- **Select by installed tool only.** Rejected: tools do not identify a
  framework, and a monorepo may contain several stacks.
- **Permit arbitrary overlay order.** Rejected because later overlays can
  silently contradict earlier contracts.

## Consequences

Skills retain one conceptual source while using idiomatic executable guidance.
Selection is explainable, reproducible, and safe for mixed hosts. Authors must
maintain compatibility declarations and executable overlay fixtures. Missing or
ambiguous bindings become visible failures. Framework references in core,
implicit tie-breaking, and forked full procedures are disallowed.

## Verification

`scripts/installer_selection.py` proves data-driven layer/binding selection and
`tests/test_capability_consumers.py` covers the TypeScript/React selection.
WP3 must add exact-one ambiguity, missing-binding, mixed-root isolation,
core-leakage, and extract-enum executable tests before replacing the pending
embodiment.
