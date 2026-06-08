---
id: "0024"
title: Concept-rename completeness includes prose, not just identifiers
status: proposed
date: 2026-06-08
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [".claude/skills/rename-concept/", ".claude/contracts/concepts.yaml", ".claude/skills/find-concept-divergence/"]
tags: [skills, rename, concept-glossary, completeness, prose]
related_smell: format-equivalence-gap
related_pattern: null
---

# Concept-rename completeness includes prose, not just identifiers

> Proposed ADR — a calibrated starting point an adopting project confirms or
> supersedes. The doctrine is enforced by the `/rename-concept` two-band gate
> that ships with this ecosystem.

## Context

A domain-concept rename is a multi-surface change — identifiers, string literals
/ wire keys, comments, docstrings, docs, and cross-tool agent mirrors. The
durable guard a rename ships is typically an **identifier-scoped** lint (a
`no_<old>_references` AST rule that flags the old name in code identifiers but,
by design, NOT in string literals, comments, or docstrings). That guard is
correct for what it covers and leaves a blind spot: the **prose** surface.

The host project this ecosystem was extracted from demonstrated the failure
concretely. A concept rename (a "sidecar" AI path → the primary runtime) shipped
its identifier lint and several "retire the old prose" commits, yet the retired
term survived in code comments, a module docstring, message strings, a test
docstring, and multiple docs — because the identifier lint cannot see prose, and
the rename's completeness gate read only the identifier-co-occurrence band of the
concept-divergence scanner (a band that is itself skipped when a concept declares
a `coverage_lint:`). So a lint-guarded rename's gate went green while prose still
used the old term. `/rename-concept` plus the concept glossary
(`.claude/contracts/concepts.yaml`) give us a place to enforce the prose surface
mechanically instead of by hand.

## Decision

A domain-concept rename is not complete until the retired term is **corrected in
prose** (comments, docstrings, message strings, docs), not only in identifiers:

- The canonical concept records the retired phrasings in its `avoid:` block in
  `.claude/contracts/concepts.yaml`, scoped to distinctive forms so the generic
  sense of a word is not flagged.
- `/rename-concept`'s completeness gate is **two-band**:
  `/find-concept-divergence`'s `superseded_co_occurrence` (identifiers — deferred
  to a `no_<old>_references` lint via `coverage_lint`) AND `avoid_term_hit`
  (prose) must BOTH be clean. A rename cannot be declared done on identifiers
  alone.
- "Correcting" prose is the obligation, not merely "retiring" the term: where a
  rename changes what a concept *is*, the surrounding explanation is
  substantively wrong and must be rewritten. The term layer is gate-enforced; the
  substance layer is surfaced by `/find-comment-drift` and corrected by
  human/LLM judgment.

## Alternatives considered

- **Identifier-only guards.** The `no_<old>_references` lint alone. Rejected:
  certifies one surface "done" while prose rots; demonstrably failed in the host
  project despite explicit prose-retirement commits.
- **Widen the identifier lint to scan strings/comments.** Rejected: the lint is
  AST-identifier-shaped by design, and a blanket string/comment grep for a common
  word floods false positives on the generic sense; the glossary `avoid:` block
  scopes to distinctive phrasings, which an AST lint cannot.
- **Leave prose to a manual checklist step.** Rejected: an un-gated checklist
  item is exactly what the host project's prose-retirement commits missed.

## Consequences

**Easier:**
- A rename's "done" is mechanically verifiable across both surfaces; the prose
  blind spot cannot silently reopen.
- The concept glossary is the single home for "what the old phrasings were,"
  reused by the gate and any future scan.

**Harder:**
- A rename now requires authoring a scoped `avoid:` block (judgment: distinctive
  vs generic phrasings) before the gate can pass.
- Substance correction remains human judgment — the gate proves the term is gone,
  not that the explanation is now true.

**Now expected / now disallowed:**
- A new domain-concept rename MUST add the retired phrasings to the canonical
  concept's `avoid:` block and pass the two-band completeness gate before "done."
- `/rename-concept` may not certify a rename complete on the identifier band alone.

## Verification

- **Tooling**: `/rename-concept`'s `assess.py` two-band completeness gate (band 3
  `superseded_co_occurrence` + band 1 `avoid_term_hit`); `/find-concept-divergence`'s
  `avoid_term_hit` band over `.claude/contracts/concepts.yaml`; the
  `no_<old>_references` lint family for identifiers.
- **Doc backref**: recommend a `Decided in: 0024` backref on the
  `format-equivalence-gap` smell entry once the smell catalogue grows one.
- **Existing artifacts**: the ported `/rename-concept` assess-only v0 carrying the
  two-band gate, and its smoke test proving band 1 fails on retired prose.
