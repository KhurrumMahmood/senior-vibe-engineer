---
id: "0038"
namespace: core
title: "One registry governs stack, capability, support, and completion-floor claims"
status: accepted
date: 2026-07-16
deciders: [khurrum, codex]
assumes: ["the toolkit runtime may remain Python while subject-language support is independently declared and tested", "legacy skill frontmatter must remain readable until the catalog rollout in WP8"]
revisit_when: ["a second registry is required by a supported surface and cannot be generated losslessly", "the support transition model cannot represent a real promotion or demotion", "a target stack needs a capability family that has two named consumers but does not fit the current families"]
supersedes: []
superseded_by: null
applies_to: [.claude/skills/, scripts/skill_meta.py, scripts/project_adapt.py, .engineering/manifest.json]
embodied_by: ["doctrine:.claude/skills/_common/capability-registry.yml", "script:scripts/_lib/capability_registry.py", "script:scripts/check_capability_registry_consumers.py", "contract:tests/test_capability_registry.py", "contract:tests/test_capability_registry_guard.py"]
tags: [capabilities, portability, support, registry, conformance]
related_smell: stringly-state
related_pattern: null
---

# One registry governs stack, capability, support, and completion-floor claims

## Context

Stack identity had become a format-equivalence bug. `skill_meta.py`, project
adaptation, perimeter scanning, and routing each owned different language and
framework vocabularies. Project adaptation emitted `javascript/typescript` and
classified Vite/Vitest as a framework; metadata rejected those values; the
perimeter scanner recognized still more languages. A support word in prose
could not prove executable behavior, and a stack could appear complete simply
by omitting a required cell.

The portability program also needs to distinguish two different languages:
Python is the toolkit runtime, while Python, TypeScript, Rust, and Go are
subject languages in host repositories. Conflating those axes would either
force a pointless runtime rewrite or overstate subject support.

## Decision

`.claude/skills/_common/capability-registry.yml` is the only authored registry
for the portability contract. It is versioned independently from consumers and
distinguishes:

- toolkit runtime and version;
- subject languages, frameworks, and tools (including package managers,
  compilers, builders, linters, and test runners);
- canonical project roots, logical layers, binding identities, and scan
  targets;
- analysis, refactoring, and guard capabilities;
- supported agent surfaces; and
- a machine-readable completion floor for every target stack.

Identifiers are data, not Python enums. A future language, framework, or tool
is registered once in the YAML document. Consumers query
`scripts/_lib/capability_registry.py`; a guard rejects new local stack enums on
the seven load-bearing paths.

Versioned skill contracts are strict. A skill opting into
`capability_contract: 1` must name a valid layer/binding/support state and only
registered capabilities. `language: any` is not universal coverage: it
requires an explicit `portable_subjects` list and per-subject executable
evidence. Every `scans:` target requires a registered adapter or native shim,
an evidence contract, and a skill-local executable. Old frontmatter remains
readable without acquiring new support claims; WP8 converts the catalog and
then removes that compatibility lane.

Support has three states: `unsupported`, `experimental`, and `verified`.
Promotion is one step at a time. Every promotable claim carries a canonical
evidence envelope bound to that exact skill, stack capability, or versioned
agent surface. The fixture command must execute a hashed test artifact; tool
commands must use registry-owned executable and argument policies; stdout,
artifact, envelope, tool-version, and platform checks are mechanical. Missing,
stale, generic, cross-claim, timed-out, out-of-range, or off-platform evidence
demotes the claim to `unsupported`; prose cannot override this. Scan claims are
also capped by the registered adapter/shim support ceiling. For strict skill
contracts, every per-subject and scan-target capability test must be included
in the single integration-test artifact directly executed by the fixture
command. Multi-file suites use that attested wrapper, preventing ignored extra
arguments or unattached hashes from masquerading as executable `language: any`
coverage.

The completion floor is a separate versioned block. Every required cell must
exist and be `verified` with evidence bound to that cell; agent surfaces also
carry a pinned compatible surface version. `unsupported`, `experimental`, a
bare label, evidence reused from another cell, and omission all fail. Changing
the floor requires an ADR amendment and migration-impact review, so a release
cannot make itself green by lowering the target.

## Alternatives considered

- **Keep validator enums in each consumer.** Rejected because adding a stack
  already required coordinated edits and the implementations had demonstrably
  drifted.
- **Use JSON Schema alone.** Rejected as the sole mechanism because consumers
  also need selection, extension lookup, support demotion, and completion-floor
  evaluation. A generated JSON Schema may be added later, but it must derive
  from this registry.
- **Treat `any` as universal support.** Rejected because it turns an absence of
  evidence into the broadest possible claim—the exact failure perimeter audits
  are designed to expose.
- **Infer support from installed tools or file extensions.** Rejected because
  detection is evidence for applicability, not evidence that a capability
  works correctly.
- **Make every current skill conform immediately.** Rejected as a big-bang
  migration. Read-old/write-new compatibility preserves current Python/Django
  behavior while WP8 produces executable evidence.

## Consequences

Adding identifiers is cheaper and category confusion is rejected at one
boundary. Routers, installers, manifests, and sweeps can exchange the same
vocabulary. Support labels become reproducible claims rather than marketing.

The registry is now a release-critical artifact. It requires PyYAML, already a
toolkit dependency, and changes require consumer/guard tests. Strict contracts
are more verbose because evidence and subject coverage are intentional.
Duplicate stack enums, silent `any` expansion, and floor weakening without an
ADR are disallowed.

## Verification

- `tests/test_capability_registry.py` exercises extension by data, invalid
  capability/layer/binding combinations, `any` evidence, scan evidence,
  framework/tool confusion, support demotion, claim binding, executed and
  hashed test evidence, path containment, tool policy ownership, and ungameable
  floor cells.
- `scripts/check_capability_registry_consumers.py` and
  `tests/test_capability_registry_guard.py` prove the load-bearing consumers
  import the registry and do not recreate the retired enums.
- Project adaptation and consumer integration are covered by
  `tests/test_project_adapt.py` and `tests/test_capability_consumers.py`.
