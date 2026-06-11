---
id: "0032"
namespace: core
title: Language-general detection
status: accepted
date: 2026-06-11
deciders: [khurrum, claude-code]
supersedes: []
superseded_by: null
applies_to:
  - .claude/skills/find-omnibus/
  - .claude/skills/find-perimeter-gaps/
  - .claude/docs/architectural-smells.md
embodied_by: ["skill:find-perimeter-gaps", "skill:find-omnibus"]
tags: [portability, detectors, perimeter, substrate]
related_smell: omnibus-module
related_pattern: null
---

# Language-general detection

## Context

The skill ecosystem is a general code-quality tool system. It was defined
and tested against a Python/Django host first, and that origin leaked into
detector scope: `find-omnibus` declares `language: python` and its walker
matches only `*.py`, so structural smells in other languages are invisible
even when the smell definition is language-neutral.

The motivating incident (2026-06-11, seed host project): `static/js/` had grown to
~34.6K lines with a 5,181-line file mixing ~14 concerns — a textbook
omnibus module — and **no detector in this ecosystem or the host could
flag it**. The host's template-lint family actively pushed JS out of
templates into `static/js/`, funneling code into files no guard watched.
The gap had three layers:

1. **Detector scope** — omnibus detection was Python-AST-only, though its
   clustering/scoring logic (tokenize → strip verbs → head-noun cluster →
   SRP "and"-count) is language-independent.
2. **Invisible perimeter** — nothing reported "this code root has
   significant LOC and zero structural detectors covering it", so the blind
   spot was discovered by accident, not by audit.
3. **No substrate check** — even if detection had fired, the standard
   remediation ("decompose the file") was unexecutable: the JS layer had no
   module system, no test infrastructure, and five copies of its own
   infrastructure helpers. Advice that assumes missing substrate is not a
   refactor plan; it is a hidden re-architecture decision.

`_common/portability-roadmap.md` already anticipated cross-language
adapters; this ADR converts that roadmap posture into binding rules for
detectors.

## Decision

The detection layer is **language-general by architecture**, enforced by
three rules:

1. **Analyzer-adapter pattern for structural detectors.** A structural
   detector (omnibus, and future structural smells) separates
   language-neutral analysis (clustering, scoring, thresholds, reporting)
   from per-language **symbol extraction adapters** keyed by file
   extension. The Python adapter uses `ast`; other languages start with
   deterministic stdlib heuristics (e.g. top-level declaration scanning
   for JavaScript) and may graduate to real parsers — adding a build/tool
   dependency is acceptable **when a heuristic adapter demonstrably
   under-detects**, not before. A detector's `language:` frontmatter
   declares its *current adapter coverage* honestly; new optional
   frontmatter `scans:` lists the languages a detector's scan surface
   actually covers when that differs from its implementation language.

2. **The perimeter is audited, not assumed.** `find-perimeter-gaps`
   reports every (code root × language) cell above an LOC threshold
   together with the SUSPECT detectors whose declared `scans:` coverage
   includes it, and flags uncovered cells. Running it is part of adopting
   the ecosystem into a host project (`/adapt-project`) and of any
   "audit the whole codebase" request. A blind spot may be *accepted*
   (vendored code, generated code) but must be visible.

3. **Substrate gate before remediation advice.** When a structural
   detector's findings hand off to refactor planning, the EXPLAIN step
   must check the target layer's substrate first: a module/import
   mechanism, test infrastructure, and non-duplicated infrastructure
   helpers. If any is missing, the verdict escalates from the omnibus
   playbook's three options (decompose / reorganize-in-place / leave
   alone) to a fourth: **re-architect — substrate decision (ADR) required
   before file surgery**. ADR 0017's staging rules then apply to the
   re-architecture itself.

## Alternatives considered

- **Per-language detector forks** (`find-js-omnibus`, `find-rs-omnibus`).
  Rejected: duplicates the scoring/reporting/threshold logic per language,
  which then drifts — the same failure mode the ecosystem exists to
  prevent.
- **Require real parsers (babel/tree-sitter) from day one.** Rejected:
  adds a non-Python toolchain to every host for marginal v1 gain; the
  omnibus signal (many top-level symbols clustering into many domains)
  survives coarse extraction. The graduation path is explicit instead.
- **Fold perimeter auditing into `check-ecosystem-consistency`.**
  Rejected: that skill audits the ecosystem's internal consistency;
  perimeter coverage is a property of a *host codebase* against the
  detector fleet, and belongs to the SUSPECT family hosts run directly.

## Consequences

- Easier: extending any structural detector to a new language (write one
  adapter); seeing coverage holes before they cost an incident; refusing
  unexecutable refactor advice early.
- Harder: heuristic adapters are coarser than AST adapters — expected
  under-detection must be documented per adapter, and findings carry the
  adapter name so reviewers can calibrate trust.
- Disallowed: new structural detectors hard-wiring single-language
  walkers without an adapter seam; `language:`/`scans:` frontmatter that
  overstates coverage; decompose recommendations into layers whose
  substrate is missing.

## Verification

- `tests/test_omnibus_language_adapters.py` pins: the Python adapter
  reproduces pre-ADR behavior; the JavaScript adapter flags a synthetic
  multi-domain JS file and stays silent on a cohesive one.
- `tests/test_perimeter_gaps.py` pins: a fixture tree with an uncovered
  high-LOC root is reported as a gap; covered and below-threshold roots
  are not.
- `.claude/docs/architectural-smells.md` carries per-smell language-scope
  tags and the fourth (re-architect) verdict; `find-omnibus/SKILL.md`
  documents adapter coverage and the substrate gate in its handoff.
