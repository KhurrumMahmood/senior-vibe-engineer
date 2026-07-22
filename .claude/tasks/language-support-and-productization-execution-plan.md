# Language support and productization execution plan

Status: active
Current phase: P3 — implement the profile contract from the frozen P3.0 spine
Last updated: 2026-07-21 (P2 complete; P3.0 complete; P3.1 next)

## Objective

Complete the product work in this order:

1. preserve and publish the simple three-router installation journey;
2. make additional language support cheaper without weakening final outcomes;
3. expand honest support across the selected major-language set; and
4. improve host guidance, routing, batching, context use, and measured user
   outcomes only after the preceding boundaries work.

This file is the sole active resumable execution ledger for unfinished
installation, language-support, and user-journey work. Durable contributor
doctrine lives in `.claude/docs/`; experiments and completed evidence remain in
the task artifacts linked below. `productization-restart-plan.md` and
`multilanguage-expansion-plan.md` are historical evidence, not competing
execution authorities.

## How to use this file

1. Work on exactly one numbered phase at a time. A phase may explicitly permit
   disjoint worktree lanes; otherwise later-phase implementation does not start.
   Read-only toolchain preflight may overlap but does not advance a later phase.
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
- Cross-language execution distinguishes complete, partial, unsupported, and
  concrete failures. A verified no-finding result is a skill-owned `clean`
  domain result inside a complete run, not a universal terminal state.
- Use established native tools when they establish the required facts; do not
  build a universal AST, semantic schema, language server, workflow DAG, or
  package manager.
- Mutations remain serial and require their own native verification. Read-only
  identical facts may be batched only after two real consumers prove the seam.
- Public publication, remote pushes, and modifications to external repositories
  require repository-owner authorization at the point of action.

## Worktree and sub-agent protocol

- The root coordinator records the exact base SHA and `git worktree list`
  before opening a lane. Existing live/unmerged worktrees are never deleted or
  repurposed; prunable registrations are changed only after explicit review.
  At this plan revision Git reports 87 registered worktrees, 59 prunable, so
  the first implementation wave must review that inventory before adding more.
- Implementation workers are fresh non-context sub-agents. Every packet names
  the project/worktree root, `.venv/bin/python`, platform, base SHA, owned and
  forbidden paths, native tools, final artifacts, stop conditions, and exact
  tests. Workers write durable evidence to their lane and make one logical
  commit; they do not push or edit the active ledger.
- Branches use `codex/<phase>-<language-or-component>-<cohort>` and sibling
  worktrees use `<repo-parent>/engineering-skills-wt-<lane>`. A frozen spine
  commit precedes dependent cohort lanes.
- At most three worker worktrees run concurrently. Read-only or isolated
  fixture mutations may run in separate worktrees; integration, shared-file
  edits, capability publication, and mutations against one host remain serial.
- The root coordinator owns shared profiles/schema after freeze,
  `scripts/source_inventory.py`, routers/catalogs, generated matrices, durable
  docs, release evidence, and this ledger. One exclusive worker may edit a
  shared surface only when its packet is recorded below as an ownership
  exception and no other lane can touch it. Language lanes otherwise add only
  their named providers/helpers, fixtures, focused tests, and learning
  fragments.
- Integration is one commit at a time into the active integration branch. After
  each commit, run its focused tests plus the narrow shared regression surface;
  after a wave, run the frozen cross-language and on-demand replay gates.
- A failed lane is not merged to make a matrix row look complete. Preserve its
  evidence, publish partial/unsupported honestly, and revise the next packet.

## Phase summary

| Phase | Outcome | Status | Completion revision |
|---|---|---|---|
| P1 | Durable docs and execution ledger committed | `done` | `cc2a4fc` |
| P2 | Release truth aligned; public install/library journey replayed | `done` | `60898a7` |
| P3 | Minimal reusable language-support kit scaffold proven | `in_progress` | — |
| P4 | PHP pilot proves real outcomes and kit economics | `not_started` | — |
| P5 | .NET toolchain and C# Roslyn pilot prove typed semantics | `not_started` | — |
| P6 | Shared components promoted or rejected on evidence | `not_started` | — |
| P7 | Remaining selected languages receive honest coverage | `not_started` | — |
| P8 | Current journey, update/repair, and help are measured | `not_started` | — |
| P9 | Only measured user-journey improvements are adopted | `not_started` | — |

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

- [x] This file is the sole active execution ledger; both durable contributor
  guides point here and the former productization/language plans identify
  themselves as historical evidence rather than resumable status authorities.
- [x] The candidate revision is available from the public source named by
  `README.md`; the publication action and source revision are recorded.
- [x] `skills@1.5.19 add <public-source> --list` exits zero and reports the
  expected catalog count at that revision.
- [x] The documented install command on a clean temporary Git host creates
  exactly `which-skill`, `which-shape`, and `which-cleanup` in discovery.
- [x] The documented entrypoints for all three routers and the installed
  `which-cleanup` smoke run under isolated/no-site Python without importing
  repository-only modules or using network access.
- [x] The documented bootstrap creates a complete sibling library outside the
  host repository and discovery roots.
- [x] One `which-skill` route and one `which-shape` route return exact selected
  closure paths from that library and reach a representative final useful
  outcome without ambiently installing a task skill.
- [x] `which-cleanup` returns a bounded closeout result with valid on-demand
  paths from the same library.
- [x] Every router recommendation returns its complete manifest-declared
  companion closure; capability validation and optional installation operate
  on that exact closure rather than the primary skill alone.
- [x] The documented removal path removes the three routers, preserves an
  out-of-scope sentinel byte-for-byte, and does not claim to remove the external
  library unless separately requested.
- [x] The installed router source revision or recorded router-tree digest and
  `git -C <library-root> rev-parse HEAD` both match the final public candidate
  SHA; replay does not infer revision coherence merely because two clones
  succeeded.
- [x] `README.md`, per-language coverage files, generated capability matrix,
  router output, and shared source inventory agree on all earned Python,
  TypeScript/JavaScript, Go, and Java claims. A freshness/consistency check plus
  Go and Java inventory/routing sentinels prevent recurrence.
- [x] `tests/test_installed_routers.py` and the clean public-source replay pass
  again at the final truth-aligned committed/public revision.
- [x] No additional installer platform, attestation system, or custom package
  manager is introduced.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Execution authority | Header/pointers in this file, both durable contributor guides, and both superseded plans | Pass: one current ledger; historical evidence retained without competing status authority | `7637fcf` |
| Public source state | `git ls-remote <distribution-named-by-README> refs/heads/main` | Pass: public `main`/HEAD is `60898a705115bc4eeb12d0eca55e82c6a7d217ea` | `60898a7` |
| Public catalog | `DO_NOT_TRACK=1 npx --yes skills@1.5.19 add <public-source> --list` | Pass: 76 skills at the final candidate | `60898a7` |
| Local installed-router suite | `.venv/bin/python -m pytest -q tests/test_installed_routers.py` | Pass: 58, including default runtime creation, check-only replay, explicit-old-Python rejection, and moved-venv rebuild | `60898a7` |
| Related router/portability suites | `.venv/bin/python -m pytest -q tests/test_which_cleanup_portable_routing.py tests/scripts/test_which_cleanup.py tests/scripts/test_which_cleanup_roots.py tests/test_portability_on_demand_journeys.py tests/test_router_decision_quality.py` | Pass: 76, 1 intentional skip | `96eb9f5` |
| Clean stock-CLI local replay | `skills@1.5.19` install from local source; isolated router entrypoints/smoke; sibling bootstrap; closure assertions; `remove --all` | Pass: exactly three routers, `organize-project-structure` task route, `adapt-project` shape route, exact `prevent-regression` + `find-implicit-state` cleanup closure, sentinel preserved | `96eb9f5` |
| Final candidate focused gate | `.venv/bin/python -m pytest -q tests/test_release_language_consistency.py tests/test_source_inventory.py tests/test_multilanguage_expansion_matrix.py tests/test_java_j1_closeout.py tests/test_installed_routers.py tests/test_which_cleanup_portable_routing.py tests/scripts/test_which_cleanup.py tests/scripts/test_which_cleanup_roots.py tests/test_portability_on_demand_journeys.py tests/test_router_decision_quality.py` | Pass: 141, 1 intentional skip; release claims, inventory, matrix, routers, cleanup, and on-demand portability agree | `60898a7` |
| Router/library revision coherence | Public bootstrap; `git -C <library-root> rev-parse HEAD`; `git rev-parse HEAD:.claude/skills/<router>`; `diff -qr` against installed router directories | Pass: library HEAD `60898a7`; installed bytes equal tree ids `which-skill=187935096c2ff939ee40ab06fcb7491a98a395d7`, `which-shape=91d504ab8eb1984c5ff620da547e5638c2f22267`, `which-cleanup=a75170d0bd7afbf698c4ea74b47bb45e468443d0` | `60898a7` |
| Clean public-source replay | `/private/tmp/engineering-skills-p2-60898a7.xgSJLL`; clean Git host; public stock install; `/usr/bin/python3 -I -S` routers/smoke; default public bootstrap; routes; final `adapt-project` artifacts + evidence gate; cleanup; stock removal | Pass: exactly three routers; Python 3.11.10 library runtime created and verified; exact useful closures; `adapter.json`, `adapter.yml`, `report.md`, and `evidence.json` validated; host source unchanged; `preserve-me` Git-config sentinel preserved; routers removed; library retained and healthy | `60898a7` |
| Release-truth consistency | `tests/test_release_language_consistency.py`; `tests/test_source_inventory.py`; matrix freshness | Pass: README, Go/Java 22-row coverage, generated matrix, representative routes, and shared `.go`/`.java` inventory agree | `60898a7` |

Completed serial closeout packet (`60898a7`):

1. [x] Add a failing release-consistency check covering README counts, per-language
   coverage, generated matrix/router projection, and Java source inventory.
2. [x] Correct README Go/Java claims and make `.java` profile/inventory-supported
   without implying Kotlin or framework-level Java support.
3. [x] Run the focused consistency, source-inventory, matrix/router, and installed-
   router suites; record the local Framework-Python anomaly only if it remains
   reproducible with a healthy interpreter control.
4. [x] Commit and publish the truth-aligned candidate, then repeat the exact public
   list/install/bootstrap/three-router/final-outcome/remove journey at that SHA,
   including router-tree/source and external-library revision equality.
5. [x] Only after every P2 checkbox has committed evidence, mark P2 done and freeze
   the P3.0 baseline. Do not open P3 worktrees early.

## P3 — Prove the minimal language-support kit scaffold

Outcome: repeated non-semantic mechanics have one small, testable contributor
surface before another full language implementation begins.

Acceptance:

- [x] Before new code, an inventory names the existing source inventory,
  capability matrix, portability journey harness, and representative
  skill-local lifecycle implementations. Each P3 component extends one of them
  or records why reuse is rejected; no parallel second system is created.
- [ ] A versioned, stdlib-only JSON language profile describes suffixes,
  project markers, source
  roles, native tools, fact tiers, verification commands, and explicit limits.
  The loader runs under isolated/no-site Python and rejects duplicate suffixes,
  unsafe command shapes, unknown roles/outcomes, and schema drift.
- [ ] A read-only doctor resolves project-local before system tools and reports
  available, too-old, unavailable, and limited capabilities without installing
  dependencies.
- [ ] Shared source inventory covers source/test/generated/vendor/build/
  declaration/configuration/tooling/symlink roles from profile data.
- [ ] A small lifecycle/conformance interface defines terminal status, atomic
  artifacts, stale-output clearing, source manifests, exact documented-command
  replay, and valid-to-failed same-destination behavior.
- [ ] The lifecycle surface shares only atomic text/JSON output, stale-output
  clearing, and source-manifest mechanics. Read-only conformance extends
  `tests/support/portability_journey.py`; mutations, rollback, final artifact
  schemas, and domain-level clean results remain skill-owned.
- [ ] The scaffold is exercised through the installed/on-demand
  `find-omnibus` TypeScript and Java paths, including positive, clean,
  malformed, missing/old-tool, excluded-role, valid-to-failed, and
  failed-to-valid cases without changing final outcome claims.
- [ ] Interface-depth checks identify the real consumers and what policy the
  shared surface removes from them; no universal semantic result schema is
  added.
- [ ] The kit runs from an exact on-demand closure without a hidden repository
  import or network requirement.
- [x] Focused tests and a size/latency baseline are recorded for comparison in
  P4 and P5.
- [ ] P3 adds no universal AST/fact/result/proposal schema, mutation executor,
  package installer, dependency cache, framework profile, or scaffolder, and
  does not migrate all 22 skills.

Work packages and dependencies:

| Packet | Depends on | Lane and ownership | Verification/merge gate |
|---|---|---|---|
| P3.0 freeze | P2 final candidate | Root serial: classify the 87 worktree registrations, prune only entries confirmed prunable, preserve every live/unmerged branch, then freeze TS+Java `find-omnibus` projections, negative boundaries, tool versions, closure bytes, adapter/test LOC, and timing protocol | Worktree inventory plus baseline artifact committed before workers branch |
| P3.1 profile contract | P3.0 | Root serial; JSON profiles/loader and lifecycle vocabulary/helpers only | Isolated loader/schema tests; one logical commit becomes the spine |
| P3.2 inventory | P3.1 | Root serial; extend existing inventory and tests only | Existing Python/JS/TS/Go projections preserved; Java and all source roles pass |
| P3.3 doctor | P3.1 | `codex/p3-toolchain-doctor`; doctor and focused tests only | Project-local precedence and available/old/missing/limited fixtures pass; no writes/install/network |
| P3.4 conformance | P3.1 | `codex/p3-conformance`; extend test harness, exact-command replay, TS+Java omnibus fixtures | External-library final artifacts and both same-destination transitions pass |
| P3.5 integrate | P3.2-P3.4 | Root serial: integrate one commit at a time; only root touches shared inventory/matrix/docs/ledger and any proven omnibus lifecycle repair | Focused suites after each commit; seven alternating warm trials; final public on-demand replay |

Benchmark contract:

- Freeze candidate SHA, host fixtures, tool versions, final projections,
  must/must-not-fire boundaries, counted adapter/test paths, closure file list
  and bytes, cold setup, and seven alternating warm trials before P3 code.
- Correctness, source preservation, and no hidden checkout imports are hard
  gates. Median warm latency and copied/shared closure bytes must remain within
  +10% for the exercised paths or the scaffold is reduced/rejected.
- Record maintained LOC for later comparison. The 25% reduction gate belongs
  to P4/P5; it is not manufactured from a P3 refactor.

Planned implementation surfaces (subject to P3.0 interface-depth confirmation):

- `scripts/language_profiles/*.json` for versioned language data;
- `scripts/_lib/language_support/profile.py` for isolated strict loading and
  `lifecycle.py` only for proven atomic/stale/source-manifest mechanics;
- `scripts/language_doctor.py` for read-only capability resolution;
- the existing `scripts/source_inventory.py`, extended rather than replaced;
- the existing `tests/support/portability_journey.py` plus a narrow conformance
  helper and focused profile/doctor/inventory/journey tests; and
- no changes to `scripts/_lib/lang_adapter/`, `status_schema.py`, or
  `artifact_scope.py`, whose contracts do not match this substrate.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Worktree review | `.claude/tasks/p3-baseline/worktree-inventory.json` | Reviewed 87 registrations; pruned only 59 missing-path registrations after proving all 21 detached heads remained reachable; preserved 28 present worktrees including both dirty worktrees; post-prune dry-run reports zero prunable registrations | `f56a5f3` spine |
| Existing-substrate/interface-depth gate | `.claude/tasks/p3-baseline/existing-substrate-inventory.md` | Extends source inventory, capability publication, portability journey, and only proven skill-local lifecycle mechanics; rejects competing/broader abstractions | `f56a5f3` spine |
| Frozen `find-omnibus` baseline | `.claude/tasks/p3-baseline/find-omnibus-baseline.json` | Exact `60898a7` skill tree/fixtures/toolchain/projections/negative boundaries/closure bytes/LOC frozen; TypeScript+Java suite `18 passed`; cold plus seven alternating warm trials recorded | `f56a5f3` spine |

## P4 — PHP final-outcome and economics pilot

Outcome: PHP proves whether the kit reduces real porting cost for a dynamic
ecosystem rather than merely centralizing setup code.

Acceptance:

- [ ] PHP and Composer versions are recorded; project-local PHP tooling wins
  over system fallback and no dependency is silently added to the host.
- [ ] Before implementation, freeze the comparison cohort:
  `find-comment-drift` (lexical/filesystem), `map-subsystem`
  (semantic/project), and `move-path` (mutation). Record final artifacts,
  must/must-not-fire boundaries, counted paths, closure definition, tool
  versions, machine, and cold/seven-warm-trial protocol.
- [ ] The bounded tree-sitter experiment reaches or is rejected by one real PHP
  final outcome; syntax availability is not presented as semantic support.
- [ ] Established PHP tooling such as PHP Parser, PHPStan, or Psalm is used only
  where the host owns or the on-demand closure explicitly provides it.
- [ ] All selected skills distinguish complete, partial, unsupported, and
  concrete failures; any clean result remains inside the skill-owned final
  artifact. Each reaches its final artifact/diff from the external library.
- [ ] Positive, clean, malformed, generated/test/vendor/build/symlink,
  tool-missing/old, and same-destination transition cases pass.
- [ ] Native PHP verification for each selected outcome passes.
- [ ] Router/matrix output explains PHP capabilities and limitations without
  installing task skills ambiently.
- [ ] Every one of the 22 language-level skills receives an evidence-backed
  supported, partial, unsupported, or not-applicable disposition map. Pilot
  completion records an explicit owner `expand` or `stop` decision; P4 does not
  require implementing beyond the three frozen cohorts.
- [ ] Compared with the frozen equivalent Java mechanics, maintained
  adapter-plus-test LOC eligible for sharing falls at least 25%, copied closure
  size does not increase more than 10%, and median execution latency does not
  increase more than 10%. Language-specific semantic/provider code is reported
  separately. A failed economic gate keeps the PHP implementation family-local
  and does not erase a correct final outcome.
- [ ] A PHP learning packet states what generalized, what stayed language- or
  family-local, tool acquisition/setup, and instructions for the C# pilot.

Worktree sequence:

1. Root freezes `codex/p4-php-spine` with the PHP profile, doctor evidence,
   representative Composer host, pilot contracts, and comparison baseline.
2. Fresh workers branch from that spine into `codex/p4-php-lexical`,
   `codex/p4-php-semantic`, and `codex/p4-php-mutation`. Their owned provider,
   fixture, test, and learning-fragment paths are disjoint; the mutation lane
   may mutate only its disposable fixture.
3. Root integrates the three lanes serially and records the pilot decision.
4. Root records `expand` or `stop`; any expansion becomes an explicit P7 slice
   after P6, not automatic continuation inside the pilot.
5. Root alone publishes the 22-row PHP disposition map, router/matrix pilot
   truth, complete learning packet, preserved-language regression, economics,
   decision, and P4 completion revision.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## P5 — .NET setup and C# Roslyn pilot

Outcome: a pinned .NET/Roslyn path proves that the kit also works for strong
compiler-backed semantic and rewrite facts.

Acceptance:

- [ ] Read-only readiness runs during P4 and records that `dotnet` is currently
  unavailable. No sub-agent installs it. Before P5 product work, the owner
  authorizes a supported .NET SDK or provides a reproducible development path.
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
- [ ] All 22 language-level skills receive an evidence-backed supported,
  partial, unsupported, or not-applicable disposition map. Pilot completion
  records an explicit owner `expand` or `stop` decision; P5 does not require
  implementing beyond the three frozen cohorts.
- [ ] LOC, copied closure size, cold/warm setup, and median execution latency are
  compared with Java and PHP.
- [ ] A C# learning packet identifies reusable infrastructure and facts that
  must remain Roslyn/family-specific.
- [ ] If an owner-authorized SDK path cannot be established within the bounded
  readiness task, record C# as deferred and select another available typed
  pilot through a criteria revision. Do not auto-install or block truthful
  promotion/rejection of the already-proven mechanics indefinitely.

Worktree sequence mirrors P4: a root-owned `codex/p5-csharp-spine`, then at
most three disjoint `lexical`, `semantic`, and `mutation` pilot lanes, followed
by a serial `expand` or `stop` decision. Any expansion becomes a P7 slice after
P6. Root alone edits Roslyn toolchain policy, shared profiles, dispatch,
matrix/router projection, and the 22-row closeout.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## P6 — Promote or reject shared kit components

Outcome: only evidence-backed reuse becomes product architecture.

Acceptance:

- [ ] Each proposed shared component names at least two real consumers and
  passes deletion, caller-knowledge, test-surface, and adapter-reality checks.
- [ ] PHP and the feasible typed-pilot final outcomes remain unchanged whether
  a candidate component is promoted or correctly rejected.
- [ ] Shared lifecycle/profile/doctor/conformance behavior has focused tests;
  language-semantic facts and skill-owned final artifact schemas remain local.
- [ ] Components failing the 25% LOC or 10% closure/latency gates are rejected,
  reduced, or retained locally with the evidence recorded.
- [ ] No promoted component requires network access during routed execution or
  creates a hidden dependency outside the selected closure.
- [ ] The contributor guide, accepted profile schema, and work-packet template
  match the accepted interfaces. A scaffolder is added only after two
  post-pilot language lanes demonstrate the same hand-written setup; otherwise
  it remains deferred.
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

Before selecting a new language, service any owner-approved PHP or typed-pilot
`expand` decision from P4/P5 as the first P7 slice.

P7 is a repeatable language slice, not a single all-at-once conversion. At P6
closeout, rank the queue using user demand, representative-host availability,
native/offline tool feasibility, expected closure cost, and transfer evidence.
Read-only profiles/toolchain preflight for up to three languages may run
concurrently. Exactly one language may have product implementation in flight;
the global maximum of three worker worktrees applies across that language's
lanes. Root publishes it before selecting the next language so shared skill
dispatch, docs, routers, and matrices never collide.

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
- [ ] Existing Python, TypeScript/JavaScript, Go, Java, PHP, and the completed
  feasible typed-pilot outcomes retain their frozen regression checks; C# is
  required here only if P5 completed C#.
- [ ] One learning packet per language records setup, reusable components,
  semantic limitations, framework follow-ups, and next-language guidance.
- [ ] Shared surfaces are integrated serially; lane commits contain only their
  owned profile/provider/fixture work.

Repeatable per-language slice:

1. `codex/p7-<lang>-spine`: profile, doctor, representative host, native-tool
   evidence, three frozen pilot contracts, and all 22 initial dispositions.
2. `codex/p7-<lang>-lexical`, `-semantic`, and `-proposal` may run concurrently
   from the spine with disjoint ownership. Unsupported/partial is a valid pilot
   result; no agent weakens a fact claim to pass.
3. Root serially integrates the pilot and records expand/stop. A stopped
   language still receives 22 honest dispositions, router explanation, and a
   learning packet.
4. If expanded, root issues up to three read-only cohort packets at a time.
   Relationship/state lanes follow graph facts; proposal/guard consumers follow
   accepted producer artifacts; mutation lanes are last and serially merged.
5. Root runs focused, preserved-language, matrix/router, exact-library, native,
   and adversarial gates, publishes the language, then re-ranks the queue.

Every worker owns only language-named provider/helper files, fixtures, focused
tests, and a learning fragment. Shared dispatch/SKILL prose, profiles shared by
multiple languages, matrix generation, routers, ledgers, and durable docs are
forbidden and root-owned.

Per-language status:

| Language | Status | Profile/doctor | Final outcomes | Matrix/router | Learning packet | Revision |
|---|---|---|---|---|---|---|
| PHP expansion | `awaiting_p4_decision` | P4-owned | — | — | — | — |
| Typed-pilot expansion | `awaiting_p5_decision` | P5-owned | — | — | — | — |
| Ruby | `preflight_needed` | System Ruby 2.6.10/Bundler 1.17.2 observed; likely old | — | — | — | — |
| Rust | `toolchain_missing` | `cargo`/`rustc` absent | — | — | — | — |
| Swift | `ready_for_preflight` | Swift 6.3.3/SwiftPM available | — | — | — | — |
| Dart | `toolchain_missing` | `dart`/Flutter absent | — | — | — | — |
| Kotlin | `toolchain_missing` | `kotlin`/`kotlinc` absent | — | — | — | — |
| C/C++ | `partial_toolchain` | Clang/clangd 21 available; CMake absent; host compile DB still required | — | — | — | — |

## P8 — Measure the current journey and finish lifecycle/help semantics

Outcome: the completed installer and language system have a reproducible
baseline, clear orientation, and a documented stock update/repair boundary
before optional UX infrastructure is proposed.

Acceptance:

- [ ] A frozen corpus covers clear, ambiguous, negated/misleading, direct/no-
  skill, unsupported-language, and different-scope cases across all three
  routers. Expected routes, allowed ambiguity sets, final-outcome rubrics,
  source revisions, and commands are frozen before optimization.
- [ ] Every clear case reaches the intended route, every ambiguous case returns
  an allowed set or discriminating question, heavy false positives on direct
  tasks are zero, and every selected closure path is valid.
- [ ] One representative installed/on-demand journey per router is judged on
  its final task outcome, not router JSON alone.
- [ ] Router `--help` behavior explains the three router jobs, external library,
  current language/framework capability, tool prerequisites, slow/manual
  paths, and no-action help semantics without initiating task execution.
- [ ] A minimal read-only status/doctor reports installed router source/ref,
  external-library HEAD, and match/mismatch. It does not add a package manager.
- [ ] The documented repair uses stock router reinstall plus explicit library
  replacement/re-bootstrap. Router uninstall, optional managed guidance, the
  external library, and user-owned files have separate stated scopes.
- [ ] A clean host passes install, help, route, selected execution, native
  verification, closeout, stock update/repair, and uninstall while preserving
  non-managed bytes.
- [ ] Fixed serial and existing batched workflows record correctness,
  completion, wall time, observable model tokens, controlled/repeated context
  bytes, native-tool invocations, and human interventions. Unobservable values
  are reported unavailable, not passed.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## P9 — Adopt only measured user-journey improvements

Outcome: routing, batching, context use, and optional host guidance improve a
measured user problem without hiding failures or expanding ambient context by
default.

Acceptance:

- [ ] Before each experiment, predeclare its primary metric, hard correctness
  gates, paired workflow, trial count, and adoption threshold. The default gate
  is at least five paired runs and either >=20% median wall-time reduction or
  >=30% controlled-context reduction without >10% token growth; a different
  threshold requires a criteria revision.
- [ ] Complementary read-only facts/lenses batch only where outputs remain
  independently attributable; mutations and final verification remain serial.
- [ ] An optimization is adopted only when every correctness/support-honesty
  gate is preserved and its threshold passes. Neutral or harmful changes are
  rejected and recorded.
- [ ] Host-instruction integration is promoted only if P8 identifies instruction
  discoverability as a material friction point. The first bounded experiment is
  `routers-only` plus one previewed, byte-preserving `signpost` mode.
- [ ] Any mutating guidance mode previews the exact diff, requires explicit
  approval, detects existing `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` and symlinks,
  and preserves every non-managed byte across apply/update/remove.
- [ ] `selected-guidance`, `project-template`, generalized model/effort mapping,
  and multi-host adapter infrastructure remain deferred until a real second
  consumer demonstrates need.
- [ ] The full skill catalog is never injected into ambient context; fresh
  non-context handoffs carry only binding rules, native commands, authority,
  stop conditions, and evidence needed by that task.
- [ ] Final documentation states measured benefits, rejected experiments,
  limitations, supported languages/frameworks, prerequisites, and known
  slow/manual paths.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Pending | — | — | — |

## Overall definition of done

- Exactly one active ledger owns unfinished work and every durable contributor
  guide points to it.
- One named public revision has consistent README/inventory/router/matrix
  claims, installs exactly three routers, bootstraps a same-revision external
  library, reaches representative final outcomes, and removes only documented
  scope.
- The P3 mechanics extend/reject existing primitives, pass TypeScript+Java
  final-outcome and benchmark gates, and do not become a semantic platform.
- PHP and one feasible compiler-backed typed pilot complete their frozen
  three-cohort journeys, all 22 dispositions, native checks, economic evidence,
  and promote/reject decisions.
- Every language selected in P7 has 22 honest dispositions; every supported
  fact tier reaches a final artifact from the external library, and every
  stopped lane remains explicitly partial/unsupported with a learning packet.
- Every worker starts from a recorded SHA in a disjoint worktree, obeys owned
  and forbidden paths, commits exact evidence, and is integrated serially with
  preserved-language regressions.
- The current journey is measured before optional infrastructure is built, and
  only improvements that pass predeclared correctness and efficiency gates are
  adopted.

## Criteria revisions

| Date | Phase | Change | Reason/evidence | User decision |
|---|---|---|---|---|
| 2026-07-21 | All | Initial verifiable criteria created | Requested resumable one-by-one execution with final validation | Approved by request |
| 2026-07-21 | P2 | Added installed-smoke and exact companion-closure gates | Clean stock replay exposed a repo-only smoke import and `which-cleanup` treating `prevent-regression` as a singleton despite its declared companion | Strengthening from observed installer failures; no scope expansion beyond easy installation |
| 2026-07-21 | All | Made this the sole active ledger and added non-context/worktree ownership protocol | Fresh review found three competing active plans and unsafe shared-file collision risk | User requested a resumable plan using sub-agents and separate worktrees |
| 2026-07-21 | P2 | Added release-truth consistency and final-candidate replay | Public replay passed, but README/inventory contradict earned Go/Java 22/22 evidence | Required to avoid publishing misleading support claims |
| 2026-07-21 | P3 | Reframed as extension of existing profile/inventory/journey/lifecycle primitives with TS+Java proof | Fresh substrate review found useful partial primitives and duplicated native-tool probing; greenfield infrastructure would repeat the prior rabbit hole | Keep only mechanics likely to reduce language-port cost |
| 2026-07-21 | P4-P7 | Added spine/cohort worktrees, frozen economics, 22-row closeouts, toolchain readiness, and serial shared integration | Completed Go/Java evidence supports cohort fan-out, while different-language branches collide on shared dispatch/matrix surfaces | Parallelize disjoint work without parallelizing shared truth |
| 2026-07-21 | P8-P9 | Measure baseline/update/help before optional host-instruction infrastructure | Adversarial review showed the prior order could make an unmeasured optional platform mandatory | Preserve installer -> languages -> measured journey order |

## Execution log

| Date | Phase | Event | Evidence/next action |
|---|---|---|---|
| 2026-07-21 | P1 | Started | Validate discoverability, reference integrity, diff scope, then commit the documentation/ledger unit. |
| 2026-07-21 | P1 | Completed | `cc2a4fc`; all P1 acceptance items passed. |
| 2026-07-21 | P2 | Started | Audit the documented public source and compare its remote revision with `cc2a4fc`; prepare the clean replay and stop for owner authorization before any publication action. |
| 2026-07-21 | P2 | Local replay repaired | Installed smoke is stdlib-only; cleanup handoffs and optional commands now use the exact manifest closure. Focused suite and clean local stock-CLI replay pass. Public visibility/publication and the fresh useful-outcome replay remain open. |
| 2026-07-21 | P2 | Public replay passed provisionally | Owner made the repository public; `main` is `8dc37d7`; stock list reports 76; clean public install/bootstrap/routes/`adapt-project` evidence/removal pass. Repair stale README Go/Java counts and Java inventory classification, add consistency sentinels, publish, then rerun the same journey at the final candidate. |
| 2026-07-21 | P2 | Runtime bootstrap integrated | `9208fca`; normal external-library bootstrap now health-checks Python >=3.11, creates/verifies the library venv, installs declared requirements, and exposes the exact runtime path through all three routers. The final P2 candidate and public replay must include this revision plus the pending release-truth repair. |
| 2026-07-21 | P8 | Router corpus seed captured | Resuming this explicit ledger produced `Project context: missing (adapter=False, profile=False, approved=False)` and a score-zero lexical `bug-fix` fallback. The explicit sole active plan correctly overrode it. Preserve this as an authoritative-plan/low-context routing case for the frozen P8 corpus; do not create project context or block P2 merely to raise router confidence. |
| 2026-07-21 | P2 | Completed | `60898a7`; public Go/Java claims, accepted coverage, generated matrix, router capability output, and shared inventory agree. The final public list/install/bootstrap/route/`adapt-project`/cleanup/remove replay passed with exact router-tree/library revision coherence, runtime setup, host-source preservation, sentinel preservation, and library retention. Begin P3.0 baseline/worktree inventory; do not revise P2 further unless a reproduced installer regression appears. |
| 2026-07-21 | P3 | Started | Freeze the exact `60898a7` TypeScript+Java `find-omnibus` baseline and review the 87 registered/59 previously prunable worktree registrations before opening any P3 worker lane. |
| 2026-07-21 | P3.0 | Completed | Committed evidence freezes the existing-substrate decisions, exact TypeScript/Java projections and exclusions, copied closure bytes, fixture manifests, maintained LOC, OpenJDK 17.0.20/TypeScript 5.9.3 toolchain, full `18 passed` correctness run, and cold plus seven alternating warm trials. Registration-only pruning reduced 87 worktree records to 28 without deleting a path, branch, commit, or dirty worktree. P3.1 may now start from this spine. |
| 2026-07-21 | Planning | Non-context plan review completed | `7637fcf`; three independent lanes reviewed the P3 substrate, language/worktree execution, and adversarial product alignment. Accepted bounded reuse, exact ownership, economics, release-truth, and measure-before-optimization findings; rejected stale private-repo assumptions and blanket prohibition on user-requested Swift/Dart planning. |
