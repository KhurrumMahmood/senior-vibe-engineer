# Language support and productization execution plan

Status: active
Current phase: P2 — publish and replay the public installation boundary
Last updated: 2026-07-21

## Objective

Complete the product work in this order:

1. preserve and publish the simple three-router installation journey;
2. make additional language support cheaper without weakening final outcomes;
3. expand honest support across the selected major-language set; and
4. improve host guidance, routing, batching, context use, and measured user
   outcomes only after the preceding boundaries work.

This file is the resumable execution ledger. Durable contributor doctrine lives
in `.claude/docs/`; experiments, evidence, and changing implementation status
live here or in the task artifacts linked below.

## How to use this file

1. Work on exactly one numbered phase at a time. Only setup that cannot affect
   product behavior may be prepared early; it does not advance a later phase.
2. Set the current phase to `in_progress` before editing its product surface.
3. Treat every unchecked acceptance item as required. A phase is `done` only
   when every item is checked and its evidence table names the exact command,
   artifact, result, and committed revision.
4. Criteria may be added or strengthened when implementation or review exposes
   a missing final boundary. Record the change under **Criteria revisions**.
5. Do not delete or weaken a criterion silently. If evidence proves it
   inappropriate, retain it struck through, add the replacement, and record the
   reason and user decision under **Criteria revisions**.
6. A passing intermediate adapter, candidate list, or fixture is not completion
   when the phase requires an installed command, final report, proposal,
   mutation, native verification, or public-source replay.
7. Keep product-goal relevance explicit in reviews: installation,
   multi-language support, then user journey/efficiency. Non-critical findings
   outside those goals go to the appropriate backlog and do not expand this
   plan automatically.
8. After a phase passes, make one logical commit, record it here, update
   `Current phase`, and begin the next phase.

## Global constraints

- Default agent discovery contains only `which-skill`, `which-shape`, and
  `which-cleanup`.
- Task skills, supporting tools, and full guides remain in the external
  on-demand library unless the user explicitly requests ambient installation.
- Fresh non-context workers receive bounded task packets; they are not assumed
  to inherit the parent conversation, model, effort, or host instruction files.
- Complete, partial, unsupported, failed, and clean are distinct outcomes.
- Use established native tools when they establish the required facts; do not
  build a universal AST, semantic schema, language server, workflow DAG, or
  package manager.
- Mutations remain serial and require their own native verification. Read-only
  identical facts may be batched only after two real consumers prove the seam.
- Public publication, remote pushes, and modifications to external repositories
  require repository-owner authorization at the point of action.

## Phase summary

| Phase | Outcome | Status | Completion revision |
|---|---|---|---|
| P1 | Durable docs and execution ledger committed | `done` | `cc2a4fc` |
| P2 | Public three-router install/library journey replayed | `in_progress` | — |
| P3 | Minimal reusable language-support kit scaffold proven | `not_started` | — |
| P4 | PHP pilot proves real outcomes and kit economics | `not_started` | — |
| P5 | .NET toolchain and C# Roslyn pilot prove typed semantics | `not_started` | — |
| P6 | Shared components promoted or rejected on evidence | `not_started` | — |
| P7 | Remaining selected languages receive honest coverage | `not_started` | — |
| P8 | Optional host-instruction integration works safely | `not_started` | — |
| P9 | Router/batching/context journey is measured and improved | `not_started` | — |

## P1 — Commit durable contributor guidance and ledger

Outcome: language-support and installer development have stable, discoverable
entry points; task files continue to own execution status and evidence.

Acceptance:

- [x] `.claude/docs/language-support-development.md` exists and distinguishes
  durable contract from working evidence/status files.
- [x] `.claude/docs/installation-and-on-demand-library.md` exists and
  distinguishes accepted ADR 0038 behavior from proposed follow-ups.
- [x] Both docs have explicit `Read when…` entries in `.claude/CLAUDE.md`.
- [x] Cross-tool documentation inventory is updated without duplicating the
  full guides into always-loaded model-specific files.
- [x] All references to the former task-file locations are removed.
- [x] `git diff --check` passes.
- [x] The exact P1 file set is committed as one logical revision, with no
  unrelated or foreign changes staged.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Durable docs exist and are registered | `test -f ...`; `/usr/bin/grep -nE "language-support-development.md\|installation-and-on-demand-library.md" ...` | Pass; root triggers, task pointers, catalog, and Augment inventory resolve | `cc2a4fc` |
| Former paths absent | `/usr/bin/grep -R -nE "language-tooling-reuse-guide\|installer-instruction-integration-design" . --include='*.md' --exclude-dir=.git` | Pass; no matches | `cc2a4fc` |
| Patch integrity | `/usr/bin/git diff --check`; commit hooks | Pass; whitespace, EOF, conflict, host-reference, and applicable hooks passed | `cc2a4fc` |
| Exact file set committed | `/usr/bin/git diff --cached --name-only`; `/usr/bin/git commit -m "Document language support and productization execution"` | Pass; eight owned documentation/ledger files, no foreign changes | `cc2a4fc` |

## P2 — Publish and replay the public installation boundary

Outcome: a clean user can install exactly the three routers from the documented
public source, bootstrap the external library, route to a useful task outcome,
and remove the ambient installation without relying on this checkout.

Acceptance:

- [ ] The reviewed candidate revision is available from the public source named
  by `README.md`; the publication action and source revision are recorded.
- [ ] `skills@1.5.19 add <public-source> --list` exits zero and reports the
  expected catalog count at that revision.
- [ ] The documented install command on a clean temporary Git host creates
  exactly `which-skill`, `which-shape`, and `which-cleanup` in discovery.
- [ ] Copies of all three routers run under isolated/no-site Python without
  importing repository-only modules or using network access.
- [ ] The documented bootstrap creates a complete sibling library outside the
  host repository and discovery roots.
- [ ] One `which-skill` route and one `which-shape` route return exact selected
  closure paths from that library and reach a representative final useful
  outcome without ambiently installing a task skill.
- [ ] `which-cleanup` returns a bounded closeout result with valid on-demand
  paths from the same library.
- [ ] The documented removal path removes the three routers, preserves an
  out-of-scope sentinel byte-for-byte, and does not claim to remove the external
  library unless separately requested.
- [ ] `tests/test_installed_routers.py` and the clean public-source replay pass
  at one committed/public revision.
- [ ] No additional installer platform, attestation system, or custom package
  manager is introduced.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | Requires repository-owner publication authorization | — | — |

## P3 — Prove the minimal language-support kit scaffold

Outcome: repeated non-semantic mechanics have one small, testable contributor
surface before another full language implementation begins.

Acceptance:

- [ ] A versioned language profile describes suffixes, project markers, source
  roles, native tools, fact tiers, verification commands, and explicit limits.
- [ ] A read-only doctor resolves project-local before system tools and reports
  available, too-old, unavailable, and limited capabilities without installing
  dependencies.
- [ ] Shared source inventory covers source/test/generated/vendor/build/
  declaration/configuration/tooling/symlink roles from profile data.
- [ ] A small lifecycle/conformance interface defines terminal status, atomic
  artifacts, stale-output clearing, source manifests, exact documented-command
  replay, and valid-to-failed same-destination behavior.
- [ ] The scaffold is exercised against at least two already-supported,
  materially different language/toolchain paths without changing their final
  outcome claims.
- [ ] Interface-depth checks identify the real consumers and what policy the
  shared surface removes from them; no universal semantic result schema is
  added.
- [ ] The kit runs from an exact on-demand closure without a hidden repository
  import or network requirement.
- [ ] Focused tests and a size/latency baseline are recorded for comparison in
  P4 and P5.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | Select existing-language exemplars before implementation | — | — |

## P4 — PHP final-outcome and economics pilot

Outcome: PHP proves whether the kit reduces real porting cost for a dynamic
ecosystem rather than merely centralizing setup code.

Acceptance:

- [ ] PHP and Composer versions are recorded; project-local PHP tooling wins
  over system fallback and no dependency is silently added to the host.
- [ ] Before implementation, one lexical/filesystem, one semantic/project, and
  one proposal-or-mutation skill are selected with frozen final artifacts and
  must/must-not-fire boundaries.
- [ ] The bounded tree-sitter experiment reaches or is rejected by one real PHP
  final outcome; syntax availability is not presented as semantic support.
- [ ] Established PHP tooling such as PHP Parser, PHPStan, or Psalm is used only
  where the host owns or the on-demand closure explicitly provides it.
- [ ] All selected skills distinguish complete, partial, unsupported, failed,
  and clean and reach their final artifact/diff from the external library.
- [ ] Positive, clean, malformed, generated/test/vendor/build/symlink,
  tool-missing/old, and same-destination transition cases pass.
- [ ] Native PHP verification for each selected outcome passes.
- [ ] Router/matrix output explains PHP capabilities and limitations without
  installing task skills ambiently.
- [ ] Compared with equivalent Java family work, maintained adapter-plus-test
  LOC falls at least 25%, copied closure size does not increase more than 10%,
  and median execution latency does not increase more than 10%; otherwise the
  failed economic gate is recorded and the abstraction is revised or rejected.
- [ ] A PHP learning packet states what generalized, what stayed language- or
  family-local, tool acquisition/setup, and instructions for the C# pilot.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## P5 — .NET setup and C# Roslyn pilot

Outcome: a pinned .NET/Roslyn path proves that the kit also works for strong
compiler-backed semantic and rewrite facts.

Acceptance:

- [ ] A supported .NET SDK is installed or otherwise made reproducibly
  available for development; exact version, resolution, cache/offline behavior,
  and uninstall/cleanup instructions are recorded.
- [ ] The doctor distinguishes SDK absence, old SDK, invalid solution/project,
  restore-required, syntax-only, and semantic-ready states.
- [ ] Roslyn provides the syntax/semantic/rewrite facts; a generic syntax
  parser does not substitute for symbol identity or project resolution.
- [ ] The same contract cohorts used in P4 have frozen C# outcomes and
  language-appropriate must/must-not-fire boundaries.
- [ ] Selected skills reach their final artifacts from the external library and
  pass exact copied-layout, stale-artifact, source-role, and native
  `dotnet ... --no-restore` verification obligations.
- [ ] Router/matrix output reports C# capability and incomplete project/restore
  boundaries honestly.
- [ ] LOC, copied closure size, cold/warm setup, and median execution latency are
  compared with Java and PHP.
- [ ] A C# learning packet identifies reusable infrastructure and facts that
  must remain Roslyn/family-specific.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## P6 — Promote or reject shared kit components

Outcome: only evidence-backed reuse becomes product architecture.

Acceptance:

- [ ] Each proposed shared component names at least two real consumers and
  passes deletion, caller-knowledge, test-surface, and adapter-reality checks.
- [ ] PHP and C# final outcomes remain unchanged through the promoted interface.
- [ ] Shared lifecycle/profile/doctor/conformance behavior has focused tests;
  language-semantic facts and skill-owned final artifact schemas remain local.
- [ ] Components failing the 25% LOC or 10% closure/latency gates are rejected,
  reduced, or retained locally with the evidence recorded.
- [ ] No promoted component requires network access during routed execution or
  creates a hidden dependency outside the selected closure.
- [ ] The contributor guide, profile schema, scaffolder, and work-packet
  template match the accepted interfaces.
- [ ] A committed promotion decision lists adopted, rejected, and deferred
  components and supplies the frozen commands for P7 lanes.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## P7 — Expand the remaining selected languages

Outcome: the major-language set has useful, explicit, non-misleading support,
using isolated implementation lanes and serial shared integration.

Initial queue: Ruby, Rust, Swift, Dart, Kotlin, and C/C++. The queue may change
only through a recorded criteria revision based on mainstream relevance,
toolchain feasibility, or product evidence.

Acceptance for each language:

- [ ] The toolchain doctor and profile report native tools, project/build
  boundaries, fact tiers, idiom/standard-tool references, and explicit gaps.
- [ ] All 22 language-level skills receive a supported, partial, unsupported,
  or not-applicable disposition with evidence; unsupported is valid and must not
  be silently replaced by a weaker claim.
- [ ] Every supported fact tier has at least one final-outcome fixture from the
  external library, including negative/source-role/tool-failure boundaries and
  native verification.
- [ ] Router output can explain what will work, what may be slow/manual, and
  which established host tools can help.
- [ ] No task skill becomes ambient by default and every copied closure remains
  complete.
- [ ] Existing Python, TypeScript/JavaScript, Go, Java, PHP, and C# outcomes
  retain their frozen regression checks.
- [ ] One learning packet per language records setup, reusable components,
  semantic limitations, framework follow-ups, and next-language guidance.
- [ ] Shared surfaces are integrated serially; lane commits contain only their
  owned profile/provider/fixture work.

Per-language status:

| Language | Status | Profile/doctor | Final outcomes | Matrix/router | Learning packet | Revision |
|---|---|---|---|---|---|---|
| Ruby | `not_started` | — | — | — | — | — |
| Rust | `not_started` | — | — | — | — | — |
| Swift | `not_started` | — | — | — | — | — |
| Dart | `not_started` | — | — | — | — | — |
| Kotlin | `not_started` | — | — | — | — | — |
| C/C++ | `not_started` | — | — | — | — | — |

## P8 — Optional host-instruction integration

Outcome: users may adopt a lean signpost or selected engineering guidance
without changing the router-only default or losing their existing instructions.

Acceptance:

- [ ] `routers-only`, `signpost`, `selected-guidance`, and `project-template`
  modes have documented, explicit behavior; `routers-only` changes no host
  instruction file.
- [ ] Mutating modes preview the exact diff and require explicit approval.
- [ ] Existing `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, symlinks, and equivalent
  supported surfaces are detected and reported rather than overwritten or
  duplicated silently.
- [ ] Apply, update, repair, and remove are idempotent and preserve every
  non-managed byte.
- [ ] Committed project policy and machine-local library/tool/model state are
  stored separately.
- [ ] Guidance units have one neutral authority plus thin agent/model adapters;
  the full skill catalog is not injected into ambient context.
- [ ] Fresh non-context handoffs carry binding shared/model-specific rules,
  native commands, authority, stop conditions, evidence, and a stable execution
  role mapped to an available model/effort.
- [ ] One clean Codex host and one Claude or Gemini host pass install, route,
  non-context execution, update, and uninstall while discovery remains exactly
  the three routers.
- [ ] The actual model and effort are recorded; vendor effort labels are not
  treated as equivalent across systems.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## P9 — Measure and improve the user journey

Outcome: the routed system demonstrably improves useful task completion or
efficiency without hiding failures or expanding ambient context.

Acceptance:

- [ ] A frozen corpus covers clear, ambiguous, negated/misleading, direct/no-
  skill, unsupported-language, and different-scope cases across all three
  routers.
- [ ] Every clear case reaches the intended route, every ambiguous case returns
  an allowed set or discriminating question, heavy false positives on direct
  tasks are zero, and every selected closure path is valid.
- [ ] One representative installed/on-demand journey per router is judged on
  its final task outcome, not router JSON alone.
- [ ] Fixed serial and batched workflows measure completion, correctness, wall
  time, model tokens where observable, repeated context bytes, native-tool
  invocations, and human interventions.
- [ ] Complementary read-only facts/lenses batch only where outputs remain
  independently attributable; mutations and final verification remain serial.
- [ ] An optimization is adopted only when it preserves correctness and shows a
  material improvement on the frozen workflows. Neutral or harmful changes are
  rejected and recorded.
- [ ] Router `--help` behavior explains the three router jobs, external library,
  current language/framework capability, and no-action help semantics without
  initiating task execution.
- [ ] A final clean-host journey covers install, orientation/help, route,
  selected execution, synthesis, native verification, closeout, update, and
  uninstall at one committed revision.
- [ ] Final documentation states measured benefits, limitations, supported
  languages/frameworks, tool prerequisites, and known slow/manual paths.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## Criteria revisions

| Date | Phase | Change | Reason/evidence | User decision |
|---|---|---|---|---|
| 2026-07-21 | All | Initial verifiable criteria created | Requested resumable one-by-one execution with final validation | Approved by request |

## Execution log

| Date | Phase | Event | Evidence/next action |
|---|---|---|---|
| 2026-07-21 | P1 | Started | Validate discoverability, reference integrity, diff scope, then commit the documentation/ledger unit. |
| 2026-07-21 | P1 | Completed | `cc2a4fc`; all P1 acceptance items passed. |
| 2026-07-21 | P2 | Started | Audit the documented public source and compare its remote revision with `cc2a4fc`; prepare the clean replay and stop for owner authorization before any publication action. |
