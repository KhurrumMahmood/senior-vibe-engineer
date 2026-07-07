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
  - scripts/_lib/lang_adapter/
embodied_by: ["skill:find-perimeter-gaps", "skill:find-omnibus", "script:scripts/_lib/lang_adapter/__init__.py"]
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

## Implementation status

*Updated 2026-06-17.* Rule 1's analyzer-adapter pattern, originally a
private seam inside `find-omnibus/scripts/detect.py`, is now a shared,
reusable package at `scripts/_lib/lang_adapter/` (a `LanguageAdapter` ABC,
a `python-ast` adapter wrapping stdlib `ast`, a `js-heuristic` adapter for
`.js/.mjs/.cjs/.ts/.tsx`, an extension-keyed registry, and two capability
flags — `CAP_SYMBOLS` and `CAP_PYTHON_AST`). The extraction is byte-for-byte
faithful to the original find-omnibus extractors.

~21 AST consumers were migrated onto the registry:

- **find-omnibus** was re-pointed at the shared package and its private
  adapter code deleted; output is byte-identical, and it is now relabeled
  `language: any` (it genuinely processes JS/TS — verified end-to-end on a
  TypeScript fixture, `analyzer: js-heuristic`).
- The **deep Python-AST detectors** (semantic_inventory, name_audit,
  duplication_audit, find-complexity-hotspots, find-implicit-state,
  find-query-mutation, find-layer-violation, find-transaction-overreach,
  find-contract-drift, find-dormant, find-async-lifecycle-drift,
  find-duplication, extract-enum, extract-state-type, introduce-fk,
  propose-boundary, propose-folder-reorganization, explain-code, and the
  shared `_common/product_topology.py`) now parse through the registry
  behind a `CAP_PYTHON_AST` gate: they skip non-Python inputs gracefully
  instead of relying on `SyntaxError`, but their analysis stays
  Python-specific so they correctly keep `language: python`. This is
  standardization onto the seam, not generalization — an honest
  distinction.

The deliberate boundary: the `scripts/lint/*` rules and infra parsers that
read the ecosystem's *own* Python/Markdown (specs, skill_comply, chunk_file,
find-skill-artifact-drift, find-standard-gaps) were **not** migrated —
they are Python-by-purpose and `path_utils` already scopes them to `.py`.

Two known precision limits of the v1 `js-heuristic` adapter (consistent with
this ADR's "expected under-detection must be documented" rule), each a
candidate for the heuristic→real-parser graduation: it matches only
column-0 declarations, so `export function` / `export const` (common in
ESM/TS) are missed; and find-omnibus's clustering still strips a
host-tuned generic-verb list, so non-matching verbs under-cluster.

Known wart pending the `_lib/{core,language,framework,repo}` reorg: skill
scripts reach the package by inserting the repo `scripts/` dir on
`sys.path` (`PROJECT_ROOT / "scripts"`), a cross-tree import the reorg in
`_common/portability-roadmap.md` will formalize.

## Verification

- `tests/test_lang_adapter.py` pins the shared package: Python/JS symbol
  extraction, god-class expansion, dunder skip, registry routing,
  capability flags, and `PythonAdapter.parse` None-on-SyntaxError.
- `tests/test_omnibus_language_adapters.py` pins: the Python adapter
  reproduces pre-ADR behavior; the JavaScript adapter flags a synthetic
  multi-domain JS file and stays silent on a cohesive one.
- `tests/test_perimeter_gaps.py` pins: a fixture tree with an uncovered
  high-LOC root is reported as a gap; covered and below-threshold roots
  are not.
- `.claude/docs/architectural-smells.md` carries per-smell language-scope
  tags and the fourth (re-architect) verdict; `find-omnibus/SKILL.md`
  documents adapter coverage and the substrate gate in its handoff.
