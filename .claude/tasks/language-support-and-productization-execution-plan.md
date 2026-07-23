# Language support and productization execution plan

Status: active
Current phase: P7/F2 Cohort A, wave A2 syntax in progress; C#/.NET remains last
Last updated: 2026-07-23 (A1 closed at `98dff01`; three A2 language worktrees active)

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
- Cross-language execution distinguishes complete, partial, pending
  implementation, exceptional unsupported/not-applicable judgments, and
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
  repurposed; obsolete worktrees are removed only after their work is proven
  represented on `main` and their working tree is clean. The 2026-07-23 review
  reduced 70 registrations to two by retiring 64 clean patch-equivalent
  worktrees, two reviewed superseded/anomaly worktrees, and the two accepted
  Dart lanes while retaining every branch and commit. The product checkout is
  `main`. The only other checkout is the clean archived preflight branch,
  retained as the repository's primary administrative worktree because its
  `.git` directory owns the common metadata used by the linked product
  checkout. Removing it requires a separate metadata migration, not ordinary
  worktree retirement.
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
  evidence, publish pending/partial honestly, and revise the next packet.

## Phase summary

| Phase | Outcome | Status | Completion revision |
|---|---|---|---|
| P1 | Durable docs and execution ledger committed | `done` | `cc2a4fc` |
| P2 | Release truth aligned; public install/library journey replayed | `done` | `60898a7` |
| P3 | Minimal reusable language-support kit scaffold proven | `done` | `f249d9a` |
| P4 | PHP pilot proves real outcomes and kit economics | `done` | `268c3ac` |
| P5 | .NET toolchain and C# Roslyn pilot prove typed semantics | `deferred_to_final_language` | — |
| P6 | Shared components promoted or rejected on evidence | `done` | `febc761` |
| P7 | Every chosen language reaches complete, value-tested language-level support | `active_cohort_a1` | — |
| P8 | Current journey, update/repair, and help are measured | `not_started` | — |
| P9 | Only measured user-journey improvements are adopted | `not_started` | — |

## Follow-on execution sequence — 2026-07-23

This is the active queue within P6-P9. Update `Status` and the named phase
evidence table after each accepted integration. Do not mark a row done from a
worker report alone: root must replay the final copied/installed boundary from
the committed integration revision.

| ID | Outcome | Status | Execution owner and parallelism | Completion evidence |
|---|---|---|---|---|
| F0 | Close Dart and normalize repository state | `done` | Root integrated serially; fresh non-context agents reviewed but did not publish shared truth | D5/D7 and D8 accepted; Dart published at 22/22; installed replay passed; anomaly branches retained; only useful checkouts remain |
| F1 | Complete P6 reuse decisions | `done` | Three fresh non-context read-only comparison lanes; root owned the decision and shared reduction | `febc761`: promotion decision, frozen packet index, 65.80% lifecycle-surface reduction, Ruby/Rust semantics normalized, committed installed replay passed |
| F2 | Complete PHP, Ruby, and Swift | `in_progress` | One fresh non-context worktree per language for the same family; maximum three; root integrates serially | All 22 jobs per language have accepted outcomes or strict reviewed exceptions; installed routes and native value suites pass |
| F3 | Complete C, C++, and Kotlin | `pending_f2` | Kotlin spine first; then one worktree per language for the same family; maximum three | Separate C/C++ truth retained; Kotlin project boundary proven; all three languages meet the F2 outcome gate |
| F4 | Complete C#/.NET last | `pending_f3` | One spine, then disjoint read-only family lanes only where ownership is proven; mutation serial | Roslyn/project facts, all 22 jobs, copied closures, native build/test/analyze, and installed routing pass |
| F5 | Publish final language release | `pending_f4` | Root only | No coverage-level pending or partial rows; bounded supported contracts may still report explicit runtime partial configurations; public install/bootstrap/route/execute/cleanup/uninstall replay passes at one SHA |
| F6 | Measure and finish the existing user journey (P8) | `pending_f5` | Up to three read-only corpus/measurement lanes; router/help/status implementation serial | Frozen router corpus, non-executing help, stock update/repair journey, and serial/batched baseline measurements pass |
| F7 | Adopt only measured UX/performance improvements (P9) | `pending_f6` | One experiment at a time; shared routing and mutation integration serial | Only experiments meeting predeclared correctness and efficiency thresholds ship; neutral/harmful results are recorded and rejected |

### F0 — Dart and repository closeout

Run in this order:

1. Integrate completed D5/D7 semantic consumer commit `382ab7e` onto the
   accepted D4 provider revision `dec49ac`. Replay its focused suite, the accepted-evidence
   validator, D4/D5/D7 preservation, and one copied detector and proposer
   journey before continuing.
2. Review D8 commit `45f0c3f`, which was based before the final D4 extension,
   before integration. Compare the standalone
   adapter with existing move-path mechanics; retain only behavior required for
   one reviewed private Dart library move, complete directive impact, native
   postflight, residue proof, and rollback. Do not extract a transaction
   platform. Its current refusal scan also treats unrelated generated Dart,
   parts/augmentations, dynamic-loading tokens, and symlinks anywhere in the
   host as blockers. Add unrelated-decoy tests and either narrow refusal to the
   impacted evidence closure or publish the outcome as partial; global
   over-refusal cannot earn supported. Then integrate and replay Dart plus
   preserved move families.
3. Publish `find-semantic-duplication`, `unify-shadows`, and `move-path` through
   shared skill prose, coverage, matrix, catalog, routers, and installed
   external-library closures. Run artifact drift, matrix freshness, router
   decision, installed-router, and final copied execution tests from the
   committed revision.
4. Apply the accepted coverage/runtime distinction: a coverage row is
   `supported` when its bounded implementation fully satisfies the declared
   useful contract, even though unsupported input configurations may terminate
   visibly as runtime `partial`; coverage `partial` means the implementation
   itself remains incomplete and keeps the language open. Dart's bounded map
   satisfies the former rule without claiming conditional, part, generated, or
   Flutter completeness.
5. Repository anomaly review is complete: the Java review's substantive bytes
   already exist on `main`, and the dirty JavaScript lane was an abandoned
   precursor to the smaller committed mutation implementation; its focused
   regression passed `2 passed`. Both worktrees were retired and their branch
   refs retained. Keep `codex/portable-v1-preflight` as an archive branch, but
   retire its physical worktree after its machine-local policy logs are
   handled. Retire the two Dart worktrees only after accepted integration.

F0 acceptance:

- [x] D5/D7 and D8 are integrated one at a time with focused and preserved
  regressions green after each commit.
- [x] D8's retained production size and closure are justified by required user
  behavior; redundant lifecycle/evidence machinery is removed or documented
  as necessary, unrelated host files do not block a provably bounded move, and
  no generic transaction abstraction is introduced.
- [x] Dart coverage, skill prose, generated matrix, catalog, all three routers,
  installed closure manifests, and the execution ledger agree at one commit.
- [x] Installed routing reaches final Dart semantic-duplication, keep-separate
  unification, and move preview/apply/check outcomes without ambiently
  installing task skills.
- [x] Dart has zero coverage-level partial rows under the accepted bounded-
  contract/runtime-partial distinction; no whole-language or Flutter claim is
  implied.
- [x] The committed ledger records the Java byte-equivalence decision and the
  JavaScript supersession plus green mutation regression; branch refs remain.
- [x] ~~Only `main` remains checked out.~~ The product checkout is `main`; the
  only other checkout is the clean archived preflight branch that owns Git's
  common administrative metadata. All completed implementation lanes are
  retired, and archive/completed lane branches remain as refs.

### F1 — Evidence-backed reuse decision

Use completed TypeScript/Java, PHP, Rust, and Dart families as the sample. Three
read-only lanes may independently examine: project/lexical facts, syntax facts,
and semantic/proposal/mutation facts. Root then writes one decision.

- Adopt only a component used immediately by at least two real consumers that
  reduces maintained LOC by at least 25%, grows the copied closure by no more
  than 10%, and grows median latency by no more than 10%. Any exception
  requires an explicit criteria revision rather than an `or` interpretation.
- Keep language-semantic schemas, consumer verdicts, proposal formats, and
  mutation rollback local unless evidence independently clears that gate.
- Freeze a work packet for each family containing owned files, provider facts,
  positive/decoy/degraded fixtures, copied closure, native commands, and final
  artifacts. This packet—not the full conversation—is passed to workers.
- Record rejected abstractions, including universal AST/call-graph/result
  schemas, workflow DAGs, daemons, package managers, and cross-language
  mutation executors, so later reviews do not repeatedly reopen them.
- Apply the accepted coverage/runtime distinction consistently: a coverage row
  is `supported` when a bounded implementation fully satisfies its declared
  contract even though unsupported configurations may terminate as runtime
  `partial`; coverage `partial` remains reserved for an implementation that
  does not yet satisfy its useful contract and therefore keeps the language
  open. Dart is resolved in F0; re-evaluate the existing Rust and Ruby map rows
  under the same rule rather than calling the same disposition both complete
  and incomplete.
- Reconcile P4/P5 wording with the chosen-language requirement: economics may
  reject shared extraction but cannot stop useful PHP outcomes, and P5 becomes
  the required C# spine/economics gate rather than an optional stop-after-pilot
  decision.

F1 acceptance is the existing P6 checklist plus a committed family-packet
index that the next cohort can execute without repository archaeology.

### F2-F4 — Repeatable language cohorts

Process languages in cohorts so comparable work is visible at the same time:

1. **Cohort A:** PHP, Ruby, Swift. Their spines and at least one value outcome
   already exist.
2. **Cohort B:** C, C++, Kotlin. C and C++ retain separate profiles and compile
   modes; Kotlin first earns its project/build spine.
3. **Cohort C:** C#/.NET, deliberately last.

Within a cohort, execute the same family across up to three languages before
advancing:

1. lexical/filesystem;
2. syntax;
3. semantic read-only;
4. accepted-evidence proposal and guard consumers; and
5. mutation, one language at a time.

One worker owns all still-pending skills in one family for one language. Do
not create one agent or worktree per skill. A worker may share one
language-local fact producer only when every consumer retains an independent
final artifact and value assertion. Root alone updates shared skill guides,
coverage, matrices, routers, durable docs, and this ledger.

The concrete wave queue is also the resumability ledger. At wave start, replace
`TBD` with the exact base SHA and branch/worktree names. After each root
integration, record accepted revisions and the exact replay command/result
before changing status to `done`.

| Wave | Status | Base SHA / lane refs | Accepted revisions | Root replay evidence | Required result before advancing |
|---|---|---|---|---|---|
| A1 — PHP/Ruby/Swift lexical-filesystem | `done` | `febc761`; retired `codex/f2-{php,ruby,swift}-project-lexical` worktrees; branches retained | PHP `35e957b`; Ruby `a38a2e5` + exit-contract repair `debbfb2`; Swift `105c7a2`; publication `7d196dd` | PHP `70 passed`; Ruby `44 passed` plus focused exit repair `21 passed`; Swift worker `71 passed, 1 deselected` and independent root `71 passed, 1 deselected`; shared publication `152 passed`; committed installed routers `58 passed` after refreshing three stale pending assertions | Every targeted final artifact, bounded closure, routing surface, and committed installed-library handoff passed |
| A2 — PHP/Ruby/Swift syntax | `in_progress` | `98dff01`; `codex/f2-php-syntax`, `codex/f2-ruby-syntax`, `codex/f2-swift-syntax` | — | — | Native token/compiler facts remain syntax-scoped; no syntax-as-semantics promotion |
| A3 — PHP/Ruby/Swift semantic read-only | `pending_a2` | TBD; three worktrees | — | — | Project/configuration identity and explicit dynamic/unresolved boundaries; revisit Ruby map disposition here |
| A4 — PHP/Ruby/Swift proposal/guard | `pending_a3` | TBD; three worktrees | — | — | Accepted producer envelopes only; no consumer reruns detection |
| A5 — Ruby mutation and Cohort A publication | `pending_a4` | TBD; serial | — | — | PHP and Swift preserve accepted mutation outcomes; Ruby proves preview, authority, rollback, exact after-tree, and native checks |
| B0 — Kotlin spine and C/C++ reuse decision | `pending_a5` | TBD; root/exclusive | — | — | Kotlin project/build boundary frozen; C and C++ remain separate even if a shared lifecycle helper is accepted |
| B1 — C/C++/Kotlin lexical-filesystem | `pending_b0` | TBD; three worktrees | — | — | Independent copied final outcomes under trustworthy language modes |
| B2 — C/C++/Kotlin syntax | `pending_b1` | TBD; three worktrees | — | — | Native syntax facts and complete degraded-tool boundaries |
| B3 — C/C++/Kotlin semantic read-only | `pending_b2` | TBD; three worktrees | — | — | Trustworthy compile/project configuration and independent semantic outcomes |
| B4 — C/C++/Kotlin proposal/guard | `pending_b3` | TBD; three worktrees | — | — | Accepted producer evidence, distinct proposal/guard artifacts, and human authority |
| B5 — C, C++, then Kotlin mutation/publication | `pending_b4` | TBD; serial | — | — | One accepted mutation and publication at a time |
| C0 — C# spine/P5 | `pending_b5` | TBD; serial | — | — | .NET/Roslyn project, restore/cache, source-role, and native command boundaries frozen |
| C1 — C# lexical/syntax/semantic families | `pending_c0` | TBD; up to three disjoint worktrees | — | — | One project-aware fact boundary only if ownership and immediate consumers are proven |
| C2 — C# downstream accepted-evidence consumers | `pending_c1` | TBD; up to three disjoint worktrees | — | — | Enum/guard, boundary/folder, and unification consumers preserve distinct artifacts and review authority |
| C3 — C# mutation and publication | `pending_c2` | TBD; serial | — | — | All 22 C# jobs close and the final chosen-language release gate may start |

This converts the unfinished matrix into roughly thirty multi-skill read-only
cohorts plus five serial mutation closeouts, instead of 142 skill-sized worker
lanes. Slow native family suites run serially after worker-focused tests to
avoid the contention already observed in combined language runs.

A1's frozen membership is `adapt-project`, `explain-code`,
`find-concept-divergence`, `find-duplication`, and
`find-folder-topology-drift` for PHP and Ruby; Swift adds
`find-comment-drift`. Existing supported rows are preserved rather than
reimplemented. `move-path` remains in the serial mutation closeout even though
the matrix describes its input facts as lexical/filesystem.

A2's frozen membership is `audit-decisions`, `find-complexity-hotspots`,
`find-omnibus`, and `find-standard-gaps` for PHP and Ruby. Swift targets the
same family except that its already-supported `find-omnibus` path is preserved
rather than reimplemented. Each language lane must produce independent final
artifacts for the remaining skills, keep token/compiler facts syntax-scoped,
record incomplete native evidence as non-clean, and measure any language-local
producer against literal consumer ownership before root publication.

Family-wave entry gate:

- exact base SHA, tool versions, project/build boundary, and existing coverage
  are frozen;
- every target skill names its useful final outcome, positive fixture, clean or
  safe-defer case, must-not-fire cases, degraded-tool behavior, copied closure,
  and native verification;
- producer/consumer dependencies are explicit; proposal/guard work does not
  start before accepted producer evidence; and
- no worker installs tooling, edits shared publication surfaces, or weakens a
  claim to make a row green.

Family-wave merge gate:

- each skill reaches its own final report/proposal/guard/mutation boundary;
- source preservation or rollback is proven as applicable;
- missing, old, failing, incomplete, stale, generated, vendor, test/example,
  symlink, and framework-bound cases remain honest;
- copied execution runs outside the checkout with no network or hidden import;
- the host's native build/test/typecheck/lint and exact smoke pass; and
- root replays focused, preserved-language, matrix/router, and installed
  closure tests before publishing the new dispositions.

### F5 — Final language release

F5 starts only after every chosen language has zero pending rows. Frameworks
remain explicitly separate. Root freezes one release SHA and proves README,
coverage files, inventory, matrix, router output, closure manifests, and
prerequisite documentation agree. A clean public host must install exactly the
three routers, bootstrap the same-revision external library, route to
representative completed language outcomes, explain unsupported framework or
configuration boundaries, preserve user bytes, and uninstall only documented
scope.

### F6-F7 — Measured user journey and efficiency

P8 remains measure-first. Up to three read-only lanes may freeze the router
quality corpus, help/status/update-repair journeys, and serial/batched
measurement corpus. Shared router behavior changes only after root integrates
the evidence.

The mandatory P8 surface is:

- clear/ambiguous/misleading/direct/unsupported-language router cases;
- non-executing `--help` for all three routers, including capability,
  prerequisites, limitations, and slow/manual paths;
- read-only router/library revision status and stock reinstall/re-bootstrap
  repair instructions; and
- final-outcome measurements for wall time, observable tokens, controlled
  context bytes, native-tool calls, repeated facts, and human interventions.

Execute P8 in this order:

1. Root freezes a versioned router corpus and measurement protocol before any
   matcher edit. Hard gates are 100% clear routes, allowed-set or discriminating
   question behavior for every ambiguous case, zero heavy false positives on
   direct tasks, honest support classification, and valid selected closures.
2. Three read-only evidence lanes may then run concurrently: fresh-context
   corpus adjudication, stock-CLI help/update/repair observation on disposable
   hosts, and measurement-protocol audit. They do not edit shared files.
3. Make matcher changes only for reproduced frozen-corpus failures. If the
   corpus passes, do not change routing.
4. One exclusive owner implements non-executing help for all three routers and
   one stdlib-only read-only status command. Status reports available source
   ref/digests and router/library match or mismatch; it never installs,
   updates, fetches, or writes.
5. Document stock router reinstall and explicit reversible library
   re-bootstrap rather than implementing a package manager. Router removal,
   optional managed guidance, external-library removal, and user files remain
   four separate scopes.
6. Root runs the clean public replay with an intentional mismatch, proves
   status detects it, repairs through the documented stock path, and preserves
   every non-managed byte.
7. Record alternating fixed serial and accepted batched baselines without
   inventing a telemetry service; unavailable system-context metrics remain
   unavailable.

P9 then evaluates, one bounded experiment at a time: complementary read-only
lens batching, smaller non-context handoffs/shared fact reuse, and optional
previewed host-file signposts. Mutation and final verification remain serial;
the full catalog never becomes ambient. Adopt only experiments meeting P9's
predeclared correctness and performance gates.

The existing bounded code-health family is the batching positive control, not
authority for arbitrary sets. A second family is attempted only after at least
two real tasks request the same fixed two or three complementary read-only
lenses and the serial baseline shows material repetition. Context-packet and
batching experiments require at least five paired alternating runs, identical
outcomes, either at least 30% controlled-context reduction or 20% median wall
reduction, aggregate token growth no greater than 10%, and no new failure or
human intervention. A host-file signpost experiment starts only if at least two
of five cold runs show discoverability intervention or wrong-entry behavior.

Framework profiles, generalized model/effort mapping, blanket skill
compression, and a new SkillOpt run remain backlog. The prior SkillOpt pilot
was inconclusive from insufficient differentiation; rerun only with a skill and
frozen corpus that first demonstrate measurable baseline failures or headroom.

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
- [x] A versioned, stdlib-only JSON language profile describes suffixes,
  project markers, source
  roles, native tools, fact tiers, verification commands, and explicit limits.
  The loader runs under isolated/no-site Python and rejects duplicate suffixes,
  unsafe command shapes, unknown roles/outcomes, and schema drift.
- [x] A read-only doctor resolves project-local before system tools and reports
  available, too-old, unavailable, and limited capabilities without installing
  dependencies.
- [x] Shared source inventory covers source/test/generated/vendor/build/
  declaration/configuration/tooling/symlink roles from profile data.
- [x] A small lifecycle/conformance interface defines terminal status, atomic
  artifacts, stale-output clearing, source manifests, exact documented-command
  replay, and valid-to-failed same-destination behavior.
- [x] The lifecycle surface shares only atomic text/JSON output, stale-output
  clearing, and source-manifest mechanics. Read-only conformance extends
  `tests/support/portability_journey.py`; mutations, rollback, final artifact
  schemas, and domain-level clean results remain skill-owned.
- [x] The scaffold is exercised through the installed/on-demand
  `find-omnibus` TypeScript and Java paths, including positive, clean,
  malformed, missing/old-tool, excluded-role, valid-to-failed, and
  failed-to-valid cases without changing final outcome claims.
- [x] Interface-depth checks identify the real consumers and what policy the
  shared surface removes from them; no universal semantic result schema is
  added.
- [x] The kit runs from an exact on-demand closure without a hidden repository
  import or network requirement.
- [x] Focused tests and a size/latency baseline are recorded for comparison in
  P4 and P5.
- [x] P3 adds no universal AST/fact/result/proposal schema, mutation executor,
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
| Strict profile/lifecycle contract | `scripts/language_profiles/*.json`; `scripts/_lib/language_support/{profile,lifecycle}.py`; `tests/test_language_support_{profile,lifecycle}.py` | Five current inventory languages load under isolated/no-site Python; duplicate suffixes, schema drift, unknown roles/outcomes, unsafe argv, and symlinks fail closed; lifecycle is limited to terminal vocabulary, atomic text/JSON, bounded stale clearing, and source manifests; `20 passed` | `7236d4e` P3.1 spine |
| Profile-driven shared inventory | `scripts/source_inventory.py`; `tests/test_source_inventory.py`; `tests/test_portability_journey_harness.py` | Existing Python/JavaScript/TypeScript/Go/Java projections and reasons preserved; source/test/generated/vendor/build/declaration/configuration/tooling/migration/symlink roles pass; isolated profile override changes suffix and role behavior; external-library fixture hashes the expanded exact closure; widened consumer suite `96 passed` | `a880251` |
| Read-only doctor | `scripts/language_doctor.py`; `tests/test_language_doctor.py` | Project-local precedence and available/too-old/unavailable/limited outcomes pass without writes, installs, or network; focused suite `8 passed`, integrated profile/inventory suite `26 passed` | `45f3c9c` |
| Installed/on-demand lifecycle conformance | `tests/support/portability_journey.py`; `tests/test_language_support_conformance.py`; `.claude/skills/find-omnibus/scripts/detect.py` | Copied-library TypeScript and Java positive/clean/malformed/excluded-role/missing-or-old-tool and both same-destination transitions pass. The harness now launches copied inventory under isolated/no-site Python, and the exercised pipeline clears stale artifacts for every language; `20 passed` with no expected failure | `bbd886d`, `f249d9a` |
| Integrated correctness and regression | P3 profile/lifecycle/inventory/doctor/conformance plus five-language omnibus, installed-router, on-demand, and release suites | `141 passed in 109.69s`; preserved omnibus language suites separately `29 passed in 56.18s`; all changed-file pre-commit checks pass | `f249d9a` |
| Benchmark and interface-depth closeout | `.claude/tasks/p3-baseline/find-omnibus-baseline.json` | Seven alternating trials: TypeScript median `+0.949%`, Java `+3.690%`; copied skill closure `-0.092%`; tracked `scripts/` bytes `+4.231%`; maintained comparison paths decreased by three lines. No semantic/result/proposal/mutation/package/framework abstraction was introduced | `f249d9a` |
| Exact public replay | Public `main` at `f249d9a`; stock `skills@1.5.19`; temporary clean host recorded in the baseline artifact | Public HEAD/digest coherence, 76 listed skills, exactly three installed routers, external-library bootstrap/runtime, TypeScript route/doctor/six-case conformance, cleanup/uninstall, sentinel/source preservation, and retained exact library HEAD all passed | `f249d9a` |

## P4 — PHP final-outcome and economics pilot

Outcome: PHP proves whether the kit reduces real porting cost for a dynamic
ecosystem rather than merely centralizing setup code.

Acceptance:

- [x] PHP and Composer versions are recorded; project-local PHP tooling wins
  over system fallback and no dependency is silently added to the host.
- [x] Before implementation, freeze the comparison cohort:
  `find-comment-drift` (lexical/filesystem), `map-subsystem`
  (semantic/project), and `move-path` (mutation). Record final artifacts,
  must/must-not-fire boundaries, counted paths, closure definition, tool
  versions, machine, and cold/seven-warm-trial protocol.
- [x] The bounded tree-sitter experiment reaches or is rejected by one real PHP
  final outcome; syntax availability is not presented as semantic support.
- [x] Established PHP tooling such as PHP Parser, PHPStan, or Psalm is used only
  where the host owns or the on-demand closure explicitly provides it.
- [x] All selected skills distinguish complete, partial, pending
  implementation, exceptional unsupported/not-applicable judgments, and
  concrete failures; any clean result remains inside the skill-owned final
  artifact. Each implemented cohort reaches its final artifact/diff from the
  external library.
- [x] Positive, clean, malformed, generated/test/vendor/build/symlink,
  tool-missing/old, and same-destination transition cases pass.
- [x] Native PHP verification for each selected outcome passes.
- [x] Router/matrix output explains PHP capabilities and limitations without
  installing task skills ambiently.
- [x] Every one of the 22 language-level skills receives an evidence-backed
  supported, partial, pending-implementation, unsupported, or not-applicable
  disposition map. Pilot
  completion records an explicit owner `expand` or `stop` decision; P4 does not
  require implementing beyond the three frozen cohorts.
- [x] Compared with the frozen equivalent Java mechanics, maintained
  adapter-plus-test LOC eligible for sharing falls at least 25%, copied closure
  size does not increase more than 10%, and median execution latency does not
  increase more than 10%. Language-specific semantic/provider code is reported
  separately. A failed economic gate keeps the PHP implementation family-local
  and does not erase a correct final outcome.
- [x] A PHP learning packet states what generalized, what stayed language- or
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
| PHP profile and doctor | `scripts/language_profiles/php.json`; `tests/test_language_{support_profile,doctor}.py`; `.venv/bin/python -I -S scripts/language_doctor.py --project-root tests/fixtures/php-pilot/host --language php` | PHP 8.4.2 and Composer 2.4.0 available; fake project-local PHP/Composer win over newer system tools; doctor is read-only; no dependency installed or updated | `1bda74f` |
| Frozen host and cohort contracts | `tests/fixtures/php-pilot`; `.claude/tasks/p4-baseline/php-pilot-baseline.json`; `tests/test_php_pilot_spine.py` | Offline Composer host freezes lexical, semantic, and mutation final artifacts, exclusions, terminal cases, native checks, exact fixture/skill closure manifests, Java comparison LOC, and one cold plus seven rotating warm trials; ignored build-role sentinel deliberately committed; focused spine suite `44 passed` plus fresh-clone manifest/native proof `3 passed` | `1bda74f`, `a3c70cb` |
| Preserved shared substrate | P3 integrated suite plus PHP profile/spine | Initial widened run exposed only the expected copied-closure hash addition; after adding PHP to that exact closure assertion, the P3/P4 focused surface passed `44 passed`; wider run reached `140 passed` before the three now-repaired expected-hash assertions | `1bda74f` |
| Lexical final outcome | `tests/test_find_comment_drift_php.py`; `.claude/tasks/multilanguage-learnings/php-find-comment-drift.md` | Native token parsing, positive/clean/malformed/excluded-role/tool/lifecycle/copied-closure cases reach the final JSONL/report; full family regression passed `22 passed` | `6a9d27b`, `05fc1a7` |
| Semantic final outcome | `tests/test_map_subsystem_php.py`; `.claude/tasks/multilanguage-learnings/php-map-subsystem.md` | Composer PSR-4 facts reach final Markdown/JSON; tree-sitter rejected as a semantic producer; full map regression passed `25 passed` | `78f8e1f`, `8a212d3` |
| Mutation final outcome | `tests/test_php_move_path.py`; `.claude/tasks/multilanguage-learnings/php-move-path.md` | One bounded namespace-directory move reaches exact diff/report, native validation, rollback, and source-preservation boundaries; full move regression passed `41 passed, 1 skipped` | `499d070`, `8399c98` |
| Capability truth and disposition closeout | `.claude/tasks/php-language-coverage.json`; generated matrix; all three routers; `tests/test_{multilanguage_expansion_matrix,installed_routers}.py` | P4 proved three supported outcomes. The other 19 are now `php-pending-implementation`; router refusal remains correct until each job receives support or a strict native-alternative/impossibility judgment. Only three routers remain ambient | `2d7c277`, `268c3ac`, criteria revision `424d7e4` plus follow-up |
| Economics and learning | `.claude/tasks/p4-baseline/php-pilot-baseline.json`; `.claude/tasks/multilanguage-learnings/php-pilot.md` | LOC reduction `11.11%` fails 25%; closure growth `26.63%` fails 10%; aggregate warm latency growth `9.18%` passes. These results reject premature shared-mechanic promotion, not PHP completion; expansion is reopened | `2d7c277`, criteria revision `424d7e4` plus follow-up |
| Preserved-language closeout | P4 final outcomes plus profile/lifecycle/doctor/inventory/conformance, TypeScript/Go/Java, router, and matrix suites | Combined run: `305 passed, 1 skipped`; one Java subprocess received OS `SIGKILL` under combined load, then passed alone. Targeted Java-map plus PHP/router/matrix replay: `83 passed` | `268c3ac` |

## P5 — .NET setup and C# Roslyn pilot

Outcome: a pinned .NET/Roslyn path proves that the kit also works for strong
compiler-backed semantic and rewrite facts.

Acceptance:

- [x] Read-only readiness runs during P4 and records that `dotnet` is currently
  unavailable. No sub-agent installs it. Before P5 product work, the owner
  authorizes a supported .NET SDK or provides a reproducible development path.
- [x] A supported .NET SDK is installed or otherwise made reproducibly
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
  partial, pending-implementation, unsupported, or not-applicable disposition
  map. P5 freezes the required Roslyn spine/economics and hands every still-
  pending row to F4; a pilot stop decision cannot complete the chosen C#
  language.
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
by a serial required-expansion handoff to F4 for every pending row. Root alone
edits Roslyn toolchain policy, shared profiles, dispatch,
matrix/router projection, and the 22-row closeout.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| .NET readiness | `command -v dotnet`; `dotnet --info`; generated console `dotnet run` | Owner authorized installation on 2026-07-22. Microsoft `dotnet-install.sh` installed SDK 10.0.302 and runtime 10.0.10 at `~/.dotnet`; `~/.local/bin/dotnet` exposes it on `PATH`; no workloads are installed; generated console builds/runs. Download was 226,536,510 bytes and installed tree is about 637 MiB. Remove the symlink and `~/.dotnet`; run `dotnet dev-certs https --clean` if the first-run development certificate should also be removed. NuGet caches are host-owned and must not be deleted blindly. | local machine state after `c5b3d46` |

## P6 — Promote or reject shared kit components

Outcome: only evidence-backed reuse becomes product architecture.

Acceptance:

- [x] Each proposed shared component names at least two real consumers and
  passes deletion, caller-knowledge, test-surface, and adapter-reality checks.
- [x] PHP and the feasible typed-pilot final outcomes remain unchanged whether
  a candidate component is promoted or correctly rejected.
- [x] Shared lifecycle/profile/doctor/conformance behavior has focused tests;
  language-semantic facts and skill-owned final artifact schemas remain local.
- [x] Components failing the 25% LOC or 10% closure/latency gates are rejected,
  reduced, or retained locally with the evidence recorded.
- [x] No promoted component requires network access during routed execution or
  creates a hidden dependency outside the selected closure.
- [x] The contributor guide, accepted profile schema, and work-packet template
  match the accepted interfaces. A scaffolder is added only after two
  post-pilot language lanes demonstrate the same hand-written setup; otherwise
  it remains deferred.
- [x] A committed promotion decision lists adopted, rejected, and deferred
  components and supplies the frozen commands for P7 lanes.

Evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Three independent comparisons | Fresh non-context project/lexical, syntax, and semantic/proposal/mutation reviews of TypeScript, Java, PHP, Rust, and Dart | No new cross-language provider/runtime cleared all conjunctive gates. Proven Rust/Dart providers remain language-local; PHP extraction is rejected at `11.11%` LOC reduction and `26.63%` closure growth | `febc761`; `.claude/tasks/shared-kit-promotion-decision.md` |
| Shared foundation and deletion proof | `tests/test_language_support_{profile,lifecycle,conformance}.py`, `tests/test_source_inventory.py`, `tests/test_language_doctor.py` | `40 passed`; unused generic lifecycle API/test surface reduced from 231 to 79 lines (`65.80%`) and the Ruby/Rust profile runtime closures each shrink by 3,479 bytes | `febc761` |
| Final outcomes and semantics | Ruby/Rust map plus PHP pilot suite; matrix/spines; committed installed router | `38 passed`; `13 passed`; committed external-library replay `1 passed in 4.04s`. Ruby and Rust bounded maps route as supported while their artifacts retain explicit runtime partial completeness | `febc761` |
| Contributor/packet truth | `.claude/docs/language-support-development.md`; `.claude/tasks/shared-kit-promotion-decision.md`; `.claude/tasks/multilanguage-learning-template.json` | Accepted interfaces, rejected abstractions, exact representative family packets, frozen commands, and refreeze gaps are discoverable without conversation context | `febc761` |

## P7 — Expand the remaining selected languages

Outcome: every chosen language has complete, useful, non-misleading support
for every applicable language-level skill, using isolated implementation lanes
and serial shared integration.

Chosen supported-language set: Python (baseline), TypeScript, JavaScript, Go,
Java, PHP, Swift, C, C++, Ruby, Rust, Dart, Kotlin, and C#/.NET. Framework
profiles such as Flutter, Rails, Spring, ASP.NET, and platform-specific Swift
remain separate expansion surfaces unless explicitly adopted. Removing a
chosen language requires an owner-approved criteria revision; a difficult or
expensive implementation is not by itself a removal criterion. C#/.NET remains
the final language by owner sequencing.

Before selecting a new language, service any owner-approved PHP or typed-pilot
`expand` decision from P4/P5 as the first P7 slice.

P7 is a repeatable language slice, not a single all-at-once conversion. At P6
closeout, rank the remaining queue using user demand, representative-host
availability, native/offline tool feasibility, expected closure cost, and
transfer evidence. By owner-approved sequencing exception, the Swift spine may
begin while P5 awaits .NET and before P6: it may reuse already-accepted P3
mechanics, but it cannot promote a new shared component or weaken P5/P6 gates.
Read-only profiles/toolchain preflight for up to three languages may run
concurrently. After their spines are accepted, up to three language-specific
cohorts from one skill family may run concurrently in disjoint worktrees.
Workers own only language-named providers, fixtures, focused tests, and learning
fragments; root integrates shared skill dispatch, docs, routers, matrices, and
scenario manifests serially. Mutation remains serial per language. This allows
transferable work to be batched without creating shared-file merge races.

Acceptance for each language:

- [ ] The toolchain doctor and profile report native tools, project/build
  boundaries, fact tiers, idiom/standard-tool references, and explicit gaps.
- [ ] All 22 language-level skills receive evidence-backed dispositions.
  `pending-implementation` and `partial` are honest intermediate states but
  cannot close a chosen language. Completion normally requires `supported`.
  Permanent `unsupported` is allowed only with evidence of technical
  impossibility or conceptual incompatibility with the language/framework;
  lack of implementation, cost, missing tooling, or pilot scope is never such
  evidence.
- [ ] If the original skill mechanics do not fit but its underlying engineering
  need still exists, the language/framework supplies and routes to a
  value-tested native alternative. `not-applicable` is allowed only when both
  the original skill and its underlying engineering job genuinely have no
  meaningful analogue. Every permanent unsupported/not-applicable judgment is
  independently reviewed and names the language practice or tool that serves
  the need, or explicitly proves that no such need exists.
- [ ] Every applicable skill has a language-native value scenario that reaches
  its final outcome from the copied external-library closure. The scenario
  encodes a real engineering problem and machine-checkable useful output; an
  empty report, generic advice, fixture-name matching, or exit-zero alone fails.
- [ ] Every applicable skill/language value suite includes: positive expected
  facts or changes; decoys and must-not-fire boundaries; missing/old/failing
  tool and incomplete-project states; source-role and stale-artifact behavior;
  copied-layout execution; and the host's native build/test/typecheck/lint
  obligation. Mutation and guard skills additionally prove rollback or
  pre/post behavior at the final executable boundary.
- [ ] Advisory/proposal skills assert the affected paths/symbols, evidence
  provenance, required obligations, and at least one rejected unsafe or
  irrelevant candidate. They do not pass by snapshotting prose alone.
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

Cross-language implementation families:

1. Lexical/filesystem: `adapt-project`, `explain-code`, `find-comment-drift`,
   `find-concept-divergence`, `find-duplication`, and
   `find-folder-topology-drift`.
2. Syntax: `audit-decisions`, `find-complexity-hotspots`, `find-omnibus`, and
   `find-standard-gaps`.
3. Semantic read-only: `find-dormant`, `find-implicit-state`,
   `find-incomplete-sweep`, `find-semantic-duplication`, `map-subsystem`, and
   `rename-concept`.
4. Proposal/mutation/guard: `extract-enum`, `move-path`, `prevent-regression`,
   `propose-boundary`, `propose-folder-reorganization`, and `unify-shadows`.

Each family wave reuses a common scenario shape while retaining
language-native fixtures and providers. Passing in one language never promotes
another language automatically.

Repeatable per-language slice:

1. `codex/p7-<lang>-spine`: profile, doctor, representative host, native-tool
   evidence, three frozen pilot contracts, and all 22 initial dispositions.
2. `codex/p7-<lang>-lexical`, `-semantic`, and `-proposal` may run concurrently
   from the spine with disjoint ownership. Pending/partial is a valid pilot
   result but not a completed language; no agent weakens a fact claim to pass.
3. Root serially integrates the pilot, records lessons/economics, and issues
   the remaining skill-family cohorts. A pilot may pause expansion for a
   concrete blocker, but `stop-after-pilot` never satisfies language completion.
4. Root issues up to three read-only cohort packets at a time.
   Relationship/state lanes follow graph facts; proposal/guard consumers follow
   accepted producer artifacts; mutation lanes are last and serially merged.
5. Root runs focused, preserved-language, matrix/router, exact-library, native,
   and value-scenario gates, publishes the language only at 22/22 applicable
   completion, then advances the queue.

Every worker owns only language-named provider/helper files, fixtures, focused
tests, and a learning fragment. Shared dispatch/SKILL prose, profiles shared by
multiple languages, matrix generation, routers, ledgers, and durable docs are
forbidden and root-owned.

Per-language status:

| Language | Status | Profile/doctor | Final outcomes | Matrix/router | Learning packet | Revision |
|---|---|---|---|---|---|---|
| PHP expansion | `pilot_complete_expansion_required` | PHP 8.4.2/Composer 2.4.0 proven | 3 supported, 19 pending implementation; not complete under full-language criteria | Pilot truth published | `.claude/tasks/multilanguage-learnings/php-pilot.md` | `268c3ac` |
| Typed-pilot expansion | `toolchain_ready_deferred_to_final` | .NET 10.0.302 installed user-locally; P5 remains last by owner decision | — | — | — | — |
| Ruby | `family_expansion_active` | Homebrew Ruby 3.4.1, RubyGems 3.6.2, and Bundler 2.6.2 pass direct execution smoke | 2 supported (`find-comment-drift`, bounded `map-subsystem`), 20 pending implementation; not complete | Ruby column and supported bounded-map routing published; runtime dynamic completeness stays partial | Two family-specific learning packets plus spine/preflight | spine `6b87331`; lexical `eed1f1d`; map `423fd08`; semantics `febc761` |
| Rust | `complete` | rustc/Cargo 1.97.1 plus rust-analyzer, Clippy, and rustfmt installed through rustup | 22 supported, 0 partial, 0 pending, 0 unsupported under bounded-contract/runtime-partial semantics | Schema-v5 column plus all bounded families published; installed bounded map route passes | Rust pilots plus lexical, syntax, semantic, proposal, enum/guard, and unification packets | implementation through `9b0faf4`; prior publication `f7311f0`; final semantics `febc761` |
| Swift | `pilot_complete_expansion_required` | SwiftPM-only profile/doctor/inventory and restrictive native fixture proven; SwiftSyntax and native test modules remain unavailable under CLT-only setup | 3 supported (`find-omnibus`, `map-subsystem`, `move-path`), 19 pending implementation; not complete | Pilot truth published and installed-router tested | `.claude/tasks/multilanguage-learnings/swift-pilot.md` plus three cohort packets | spine `09248d4`; cohorts `84bd160`, `7fb2f4f`, `c5a2792`; publication `661e1b1` |
| Dart | `complete` | Dependency-free Dart SDK 3.12.2 foundation plus project/lexical, locked public-analyzer syntax, SDK-LSP semantic, accepted-evidence consumers, and transactional move proven; Flutter remains separate | 22 supported, 0 partial, 0 pending, 0 unsupported under bounded-contract/runtime-partial semantics | Capability column and all three router handoffs published; shared-helper outcomes remain external-library-only rather than advertising broken one-skill stock installs | Spine, contract map, D1-D8 family packets | spine `f4a5eab`; contract `8e16c5c`/`ad6f277`; final integration/publication through `891ad50` |
| Kotlin | `toolchain_ready_queued` | Kotlin 2.4.10 passes JVM expression smoke; project build tooling remains fixture-owned | — | — | — | — |
| C | `pilot_complete_expansion_required` | Apple Clang/clangd 21 plus Make 3.81 proven; `.c`/`.i` only; trustworthy C-mode compile DB required for semantic facts | 2 supported (`find-comment-drift`, `map-subsystem`), 20 pending implementation; not complete | Pilot truth published and installed-router tested | `.claude/tasks/multilanguage-learnings/c-pilot.md` plus spine and cohort packets | spine `56707fe`; lexical `b5a63e9`; semantic `5d6def3`; publication `79d8a27` |
| C++ | `family_expansion_required` | Separate ISO C++20 profile; Apple Clang/clangd 21 and Make proven; trustworthy C++ compile DB required | 2 supported (`find-comment-drift`, `map-subsystem`), 20 pending implementation; not complete | Capability column published and installed-router tested | Spine, lexical, and semantic learning packets | spine `6d642f0`; lexical `9b1ed7d`; semantic `5eeff8e`; publication `7f1c6b3` |

Current Rust family schedule after the three pilot outcomes are accepted:

1. Lexical/filesystem batch (5): `adapt-project`, `explain-code`,
   `find-concept-divergence`, `find-duplication`, and
   `find-folder-topology-drift`.
2. Syntax batch (4): `audit-decisions`, `find-complexity-hotspots`,
   `find-omnibus`, and `find-standard-gaps`.
3. Semantic read-only batch (5): `find-dormant`, `find-implicit-state`,
   `find-incomplete-sweep`, `find-semantic-duplication`, and `rename-concept`.
4. Proposal/guard batch (5), only after the required producer artifacts are
   accepted: `extract-enum`, `prevent-regression`, `propose-boundary`,
   `propose-folder-reorganization`, and `unify-shadows`.

The first three batches may use separate worktrees concurrently. Each skill
retains an independent value scenario and final-outcome assertion; shared fact
production is allowed only when the pilot evidence proves the facts identical.
The proposal/guard batch is integrated after its producers and never shares a
mutation executor.

### Language toolchain dependency register

This table tracks development prerequisites; it is not an instruction to
install them. A sub-agent never installs or updates a language toolchain. Root
must obtain owner authorization immediately before any machine-level install,
record the exact version/path/cleanup behavior, and keep routed product
execution dependent on host-owned or exact on-demand-closure tools.

| Language | Required blocker | Optional host-owned tools | State / timing |
|---|---|---|---|
| Java (preserved support) | Healthy JDK 17+ launcher | Existing Maven/Gradle or project analyzers when a host requires them | Homebrew OpenJDK 17.0.20 at `/opt/homebrew/opt/openjdk@17` is healthy and all preserved Java family suites pass when its `bin` is first on `PATH` and `JAVA_HOME` names that prefix. The macOS `/usr/bin/java` and `/usr/bin/javac` stubs time out on this host, so setup/verification must publish the resolved executable rather than trusting default `PATH`; no new install is needed. |
| Swift | None for the SwiftPM spine or compiler-AST pilot | SwiftSyntax, SwiftLint, Periphery, SourceKitten; full Xcode for XCTest/Testing and Xcode projects | Current CLT Swift 6.3.3 is enough for the selected build, executable-smoke, AST, index, and SourceKit boundaries. Optional tools do not block the spine and are not installed. |
| C | Trustworthy host or fixture `compile_commands.json`; no new compiler required | CMake, clang-tidy, clang-format, IWYU, cppcheck, capture tools such as Bear | Apple Clang/clangd 21 and Make are available. CMake is absent but not required for a bounded Make fixture. |
| C++ | Separate C++ profile plus trustworthy compile commands; no new compiler required | Same Clang ecosystem as C, selected standard library/build-system tools | Apple Clang/clangd 21 and Make are available. Do not combine C and C++ capability truth. |
| Ruby | Healthy modern Ruby (preflight floor 3.3+) and matching Bundler | Prism, RuboCop, RBS/Steep or Sorbet, Rails/Zeitwerk for explicit framework profiles | Homebrew Ruby 3.4.1, RubyGems 3.6.2, and Bundler 2.6.2 are healthy at `/opt/homebrew/opt/ruby/bin`; `~/.local/bin/{ruby,gem,bundle,bundler}` makes them win over system Ruby 2.6. The Homebrew Ruby predated this task, so cleanup removes only those four symlinks unless the owner separately chooses to uninstall Ruby. Optional analyzers remain language-slice decisions. |
| Rust | Rust compiler and Cargo | rust-analyzer, Clippy/rustfmt components | Homebrew `rustup` 1.29.0_2 manages stable rustc/Cargo 1.97.1 under `~/.rustup`; rust-analyzer, Clippy, and rustfmt are installed. Proxies in `~/.local/bin` make the keg-only installation usable. Cleanup: uninstall the stable toolchain, remove the eight task-created proxy symlinks, then `brew uninstall rustup`; remove `~/.rustup` only after confirming it has no unrelated toolchains. |
| Dart | Dart SDK; Flutter only for an explicit Flutter profile | Analysis Server/analyzer and formatter bundled with the selected SDK | Official `dart-lang/dart` formula 3.12.2 is installed at `/opt/homebrew/opt/dart` and a generated console runs. Only `dart` and `dart-beta` formulas were trusted. Cleanup: `brew uninstall dart`, remove those formula trusts, and untap `dart-lang/dart` if unused. Flutter remains optional and separate. |
| Kotlin | Kotlin compiler plus a reproducible project build path; existing JDK may be reused if compatible | Gradle wrapper, Detekt, ktlint, Analysis API for bounded needs | Homebrew Kotlin 2.4.10 is installed and passes JVM expression smoke. Homebrew also installed OpenJDK 26.0.1 (about 380 MiB); current `kotlinc` resolves the host JRE 17.0.12. Cleanup: `brew uninstall kotlin`, then uninstall OpenJDK 26 only if no other formula uses it. Gradle remains project/fixture-owned. |
| C# | Supported .NET SDK with Roslyn | Project-owned analyzers and formatters | Microsoft user-local SDK 10.0.302 and runtime 10.0.10 are installed under `~/.dotnet`, exposed by `~/.local/bin/dotnet`, and pass generated-console execution. No workloads are installed. C# product work remains last by owner sequencing, not by toolchain availability. Cleanup is recorded in P5 readiness above. |

For every new preflight, add any newly discovered required or optional tool to
this register before opening implementation worktrees. Missing optional tools
produce an explicit limitation; they do not automatically become dependencies.

Swift slice evidence:

| Check | Command/artifact | Result | Revision |
|---|---|---|---|
| Three-language preflight and selection | `.claude/tasks/p7-preflight/{swift,ruby,c-cpp}.md` | Swift selected; Ruby deferred for unhealthy runtime; C and C++ queued as separate compile-database-gated profiles | `ef07cca` |
| SwiftPM spine | `scripts/language_profiles/swift.json`; `.claude/tasks/p7-baseline/swift-pilot-baseline.json`; `.claude/tasks/swift-language-coverage.json`; `tests/test_swift_pilot_spine.py` | Restrictive dependency-free build, executable smoke, typecheck/AST, malformed/source-role/symlink/tool-precedence/source-preservation boundaries pass; the spine initially earned no support; main replay `36 passed` including PHP spine | `09248d4` |
| Swift pilot cohorts | `tests/test_find_omnibus_swift.py`; `tests/test_map_subsystem_swift.py`; `tests/test_swift_move_path.py` | Focused lanes: omnibus `6 passed`, map `5 passed`, move `13 passed`; all three copied closures reach their final artifact/mutation boundary | `84bd160`; `c5a2792`; `7fb2f4f` |
| Preserved families and publication | Omnibus, map, move-path, matrix, and installed-router suites | Non-Java omnibus `21 passed`; Java omnibus `11 passed`; non-Java map `24 passed` plus corrected metadata assertion; Java map `5 passed`; non-Java move `50 passed, 1 skipped`; Java move `4 passed`; matrix/router `59 passed`. Selected-skill install passes with explicit runtime provenance. | publication `661e1b1` plus closeout follow-up |
| C spine | `scripts/language_profiles/c.json`; `.claude/tasks/p7-baseline/c-pilot-baseline.json`; `.claude/tasks/c-language-coverage.json`; `tests/test_c_pilot_spine.py` | C-only Make/Clang fixture, native test, AST/raw tokens, compile-DB validity boundaries, header ambiguity, roles, tool states, source preservation, and 22 initial gap rows pass; integrated profile/doctor/inventory/C suite `33 passed` | `56707fe` plus root census integration |
| C pilot cohorts and publication | `tests/test_find_comment_drift_c.py`; `tests/test_map_subsystem_c.py`; `tests/test_installed_routers.py`; `.claude/tasks/multilanguage-learnings/c-pilot.md` | Lexical `9 passed`; semantic `12 passed`; matrix/router/C closeout `80 passed`; installed router plus preserved non-Java families `114 passed` before one stale PHP metadata assertion was corrected, then the correction and Swift replay `6 passed`; explicit-JDK Java replay `9 passed`. Both copied closures reach final artifacts and preserve source. Two rows are supported and twenty are now explicitly pending implementation | lexical `b5a63e9`; semantic `5d6def3`; publication `79d8a27`; criteria revision follow-up |
| C++ spine | `scripts/language_profiles/cpp.json`; `.claude/tasks/p7-baseline/cpp-pilot-baseline.json`; `.claude/tasks/cpp-language-coverage.json`; `tests/test_cpp_pilot_spine.py` | Separate C++20 suffix/mode truth, native Make build/smoke, compile-database valid/missing/malformed/stale/incomplete/wrong-mode gates, owned-vs-ambiguous headers, source roles, tool failures, preservation, and 22 pending-implementation dispositions pass. Integrated profile/doctor/inventory/conformance replay `39 passed` | `6d642f0` plus root census integration |

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
- Every chosen language has all 22 language-level jobs served by the named
  skill or a routed language-native alternative. Pending/partial rows keep that
  language open; unsupported/not-applicable rows close only under the strict
  impossibility/inapplicability and independent-review rule above.
  Every applicable row passes its positive-value, must-not-fire, degraded-tool,
  copied-layout, stale-artifact, and native final-boundary scenario obligations.
- Every worker starts from a recorded SHA in a disjoint worktree, obeys owned
  and forbidden paths, commits exact evidence, and is integrated serially with
  preserved-language regressions.
- The current journey is measured before optional infrastructure is built, and
  only improvements that pass predeclared correctness and efficiency gates are
  adopted.

## Criteria revisions

| Date | Phase | Change | Reason/evidence | User decision |
|---|---|---|---|---|
| 2026-07-23 | P6/F1 | Close shared-component promotion with no new cross-language runtime; retain proven language-local reuse, prune unused lifecycle API, and normalize Ruby/Rust bounded-map coverage semantics | Three independent comparisons found no new component satisfying the conjunctive consumer/LOC/closure/latency gate. `febc761` records the decision/packet index, removes 65.80% of the unused lifecycle implementation/test surface, and preserves runtime partial truth inside supported bounded contracts | Implements the approved evidence-first reuse gate without adding productization overhead |
| 2026-07-23 | F0 | Replace the literal "only `main` checked out" condition with "only useful checkouts retained" | The archived preflight checkout is Git's primary administrative worktree: its `.git` directory stores the common metadata used by the linked product checkout, so `git worktree remove` correctly refuses it. Its redacted telemetry is committed at `5a8a571`, it is clean, and every completed implementation checkout is retired. Removing it would require a separate repository-metadata migration with no installer or language-support benefit | Consistent with the owner's request to retire worktrees that are no longer useful; no product scope added |
| 2026-07-23 | P6-P9 | Added one bounded follow-on queue: Dart/repository closeout, evidence-backed reuse, family-batched language cohorts, final release, measured journey, then threshold-gated improvements | The owner requested retirement of obsolete worktrees and a resumable plan that can use separate non-context workers. Three fresh read-only reviews independently supported family batching, serial shared integration, criteria repair, and measure-before-UX sequencing | Approved by user request |
| 2026-07-22 | P7 | Replace pilot-closeout completion with full chosen-language completion and value-scenario gates | Owner clarified that every chosen language must support every applicable skill and that tests must prove useful language-native outcomes. PHP 3/22, Swift 3/22, and C 2/22 are therefore honest pilots but incomplete products. Cross-language work is batched by four skill families with language-specific providers and serial shared integration | Approved by user request |
| 2026-07-21 | All | Initial verifiable criteria created | Requested resumable one-by-one execution with final validation | Approved by request |
| 2026-07-21 | P2 | Added installed-smoke and exact companion-closure gates | Clean stock replay exposed a repo-only smoke import and `which-cleanup` treating `prevent-regression` as a singleton despite its declared companion | Strengthening from observed installer failures; no scope expansion beyond easy installation |
| 2026-07-21 | All | Made this the sole active ledger and added non-context/worktree ownership protocol | Fresh review found three competing active plans and unsafe shared-file collision risk | User requested a resumable plan using sub-agents and separate worktrees |
| 2026-07-21 | P2 | Added release-truth consistency and final-candidate replay | Public replay passed, but README/inventory contradict earned Go/Java 22/22 evidence | Required to avoid publishing misleading support claims |
| 2026-07-21 | P3 | Reframed as extension of existing profile/inventory/journey/lifecycle primitives with TS+Java proof | Fresh substrate review found useful partial primitives and duplicated native-tool probing; greenfield infrastructure would repeat the prior rabbit hole | Keep only mechanics likely to reduce language-port cost |
| 2026-07-21 | P4-P7 | Added spine/cohort worktrees, frozen economics, 22-row closeouts, toolchain readiness, and serial shared integration | Completed Go/Java evidence supports cohort fan-out, while different-language branches collide on shared dispatch/matrix surfaces | Parallelize disjoint work without parallelizing shared truth |
| 2026-07-21 | P8-P9 | Measure baseline/update/help before optional host-instruction infrastructure | Adversarial review showed the prior order could make an unmeasured optional platform mandatory | Preserve installer -> languages -> measured journey order |
| 2026-07-22 | P5-P7 | Permit one bounded SwiftPM P7 slice while P5 awaits an owner-authorized .NET SDK; forbid early shared-component promotion | Owner explicitly asked to start other languages meanwhile. Parallel preflights found Swift ready, Ruby unhealthy, and C/C++ feasible only as two compile-database-gated profiles | Approved by user request |
| 2026-07-22 | P5-P7 | Move C#/.NET to the end and add an explicit language-toolchain dependency register | Owner asked to return to .NET at the end and track every other language dependency needing installation | Approved by user request |
| 2026-07-22 | P5-P7 | Install queued language toolchains while retaining .NET as the final product slice | Owner authorized temporary installation. Ruby 3.4.1/Bundler 2.6.2, Rust 1.97.1 with analyzer/Clippy/rustfmt, Dart 3.12.2, Kotlin 2.4.10, and .NET SDK 10.0.302 all resolve on `PATH` and pass execution smoke. Exact paths, transitive OpenJDK, trust scope, caches, and cleanup behavior are recorded in the dependency register and P5 readiness evidence | Approved by user request |

## Execution log

| Date | Phase | Event | Evidence/next action |
|---|---|---|---|
| 2026-07-23 | P7/F2 A2 | PHP/Ruby/Swift syntax wave opened | Three fresh non-context language worktrees start from exact A1 closeout `98dff01`. PHP and Ruby each own audit, complexity, omnibus, and standard-gap outcomes; Swift owns audit, complexity, and standard-gap outcomes while preserving its accepted omnibus path. Workers own language-local implementation/fixtures/tests/packets only; root retains shared guides, coverage, projections, routers, docs, and serial publication. |
| 2026-07-23 | P7/F2 A1 | PHP/Ruby/Swift project/lexical wave completed | Language-local external providers reach five PHP, five Ruby, and six Swift copied final outcomes without ambient skill installation. Bounded adversarial review drove fixes for Ruby partial exit 0 and Swift protocol-requirement body capture. Publication `7d196dd` passes `152` shared tests; the committed on-demand-library/router replay passes `58` after updating only three stale installed-test expectations. PHP/Ruby worktrees are retired; retire Swift and open the frozen A2 syntax lanes from the A1 closeout revision. |
| 2026-07-23 | P6/F1 | Shared-kit decision completed; Cohort A opened | `febc761` retains the narrow profile/inventory/doctor/conformance foundation, reduces unused lifecycle implementation/test surface from 231 to 79 lines, rejects PHP/universal extraction, and freezes representative family packets. Shared foundation replay passes `40`; Ruby/Rust maps plus PHP final outcomes pass `38`; matrix/spines pass `13`; the committed installed router passes in 4.04s. Ruby is now 2 supported/20 pending and Rust is 22/22 supported under the accepted bounded-contract/runtime-partial distinction. Open A1 from `febc761` for PHP, Ruby, and Swift project/lexical work; root retains shared publication ownership. |
| 2026-07-23 | P7/F0 | Dart and repository closeout completed | D5/D7 and D8 were integrated and adversarially repaired through `891ad50`; Dart now has 22 supported rows and no coverage-level partial, pending, or unsupported rows. Installed external-library routing reaches semantic duplication, keep-separate unification, and transactional move outcomes while only three routers remain ambient. Both Dart implementation worktrees are retired. The preflight telemetry was redacted and committed on its archive branch at `5a8a571`; that clean checkout remains solely because it owns Git's common administrative metadata. Begin three read-only P6/F1 reuse comparisons; do not open a new language implementation lane yet. |
| 2026-07-21 | P1 | Started | Validate discoverability, reference integrity, diff scope, then commit the documentation/ledger unit. |
| 2026-07-21 | P1 | Completed | `cc2a4fc`; all P1 acceptance items passed. |
| 2026-07-21 | P2 | Started | Audit the documented public source and compare its remote revision with `cc2a4fc`; prepare the clean replay and stop for owner authorization before any publication action. |
| 2026-07-21 | P2 | Local replay repaired | Installed smoke is stdlib-only; cleanup handoffs and optional commands now use the exact manifest closure. Focused suite and clean local stock-CLI replay pass. Public visibility/publication and the fresh useful-outcome replay remain open. |
| 2026-07-21 | P2 | Public replay passed provisionally | Owner made the repository public; `main` is `8dc37d7`; stock list reports 76; clean public install/bootstrap/routes/`adapt-project` evidence/removal pass. Repair stale README Go/Java counts and Java inventory classification, add consistency sentinels, publish, then rerun the same journey at the final candidate. |
| 2026-07-21 | P2 | Runtime bootstrap integrated | `9208fca`; normal external-library bootstrap now health-checks Python >=3.11, creates/verifies the library venv, installs declared requirements, and exposes the exact runtime path through all three routers. The final P2 candidate and public replay must include this revision plus the pending release-truth repair. |
| 2026-07-21 | P8 | Router corpus seed captured | Resuming this explicit ledger produced `Project context: missing (adapter=False, profile=False, approved=False)` and a score-zero lexical `bug-fix` fallback. The explicit sole active plan correctly overrode it. Preserve this as an authoritative-plan/low-context routing case for the frozen P8 corpus; do not create project context or block P2 merely to raise router confidence. |
| 2026-07-21 | P2 | Completed | `60898a7`; public Go/Java claims, accepted coverage, generated matrix, router capability output, and shared inventory agree. The final public list/install/bootstrap/route/`adapt-project`/cleanup/remove replay passed with exact router-tree/library revision coherence, runtime setup, host-source preservation, sentinel preservation, and library retention. Begin P3.0 baseline/worktree inventory; do not revise P2 further unless a reproduced installer regression appears. |
| 2026-07-22 | P4 | Completed; earlier stop decision superseded | Three bounded PHP outcomes reached final artifacts and native checks. The original closeout called the other 19 skills unsupported; the full-language criteria now correctly classify them as pending implementation and reopen expansion. P5 readiness then found `dotnet` absent; it has since been installed user-locally. |
| 2026-07-22 | P7 | Three preflights completed; Swift selected | `ef07cca`; Swift, Ruby, and C/C++ evidence lives under `.claude/tasks/p7-preflight/`. Begin one root-owned SwiftPM spine from that revision: profile/doctor/inventory, representative host, three frozen final-outcome contracts, and 22 initial gap dispositions. Ruby and C/C++ remain queued; no concurrent product implementation. |
| 2026-07-22 | P7 | SwiftPM spine completed | `09248d4`; strict Swift profile, doctor/inventory truth, restrictive native fixture, executable smoke, syntax/malformed boundaries, and three frozen contracts pass. Its 22 unimplemented outcomes are now treated as pending until cohorts earn support. |
| 2026-07-22 | P7 | Swift pilot cohorts integrated; earlier stop decision superseded | `84bd160`, `7fb2f4f`, and `c5a2792` earn bounded final outcomes for omnibus syntax, SwiftPM mapping, and target-directory mutation. The original closeout froze 3 supported/19 unsupported; the latter 19 are now pending implementation. |
| 2026-07-22 | P7 | Swift pilot published | `661e1b1` published the initial 3 supported/19 gap matrix and router truth; installed router/matrix suite `59 passed`. The current matrix reclassifies the 19 unfinished rows as pending implementation and expansion remains open. |
| 2026-07-22 | P7 | C-only spine integrated | `56707fe`; `.c`/`.i` profile truth, portable two-TU Make fixture, valid/current/complete C-mode compile-database gate, owned-vs-ambiguous headers, source roles, tool states, and native tests pass. Its initial gaps are pending implementation. |
| 2026-07-22 | P7 | C pilot cohorts integrated | Lexical `b5a63e9` and semantic `5d6def3` prove two useful read-only final outcomes. The remaining 20 jobs stay pending implementation; mutation is deferred, not declared impossible. |
| 2026-07-22 | P7 | C published; separate C++ spine opened | `79d8a27` publishes 2 supported/20 gap C capability truth and `87aa135` closes verification. Current criteria reclassify all unfinished gaps as pending. C++ owns a separate profile, compile mode, headers, fixture, dispositions, and dependency truth. |
| 2026-07-22 | P7 | C++ spine accepted under full-language criteria | `6d642f0` adds the separate C++20 spine and root census integration passes `39` tests. All 22 rows are pending implementation; begin skill-family value cohorts and do not publish C++ as complete until every engineering job is served or passes the strict exception rule. |
| 2026-07-22 | P7 | Pending-vs-unsupported rule enforced; next wave opened | `ee1f8bd` reclassifies unfinished PHP/Swift/C/C++ jobs as pending implementation, makes routers preserve that distinction, and rejects permanent unsupported claims without strict evidence and a proven alternative or absent underlying job; committed-checkout replay passes `110` tests. From this exact SHA, open disjoint C++ `find-comment-drift`, C++ `map-subsystem`, and Ruby-spine worktrees. |
| 2026-07-22 | P7 | Router exception semantics and C++ publication completed | `d12c86e` reports stack/language mismatches as `native-alternative-required` and missing scanner coverage as pending rather than unsupported; committed-checkout router replay passes `166` tests. `54c47e7` publishes the C++ capability column through schema v3 and all three routers; installed C++ pending/shape replay passes `91` tests. |
| 2026-07-22 | P7 | Ruby spine integrated; family-batched Ruby cohort opened | Ruby spine `6b87331` plus root census integration `ecd55f6` prove Ruby 3.4 profile/doctor/inventory/native fixture boundaries with `39` tests and classify all 22 jobs as pending implementation. Open `codex/p7-ruby-lexical-full` from the frozen spine while C++ lexical and semantic work continue; the Ruby worker owns only language-specific analyzer/fixture/test/learning files so the shared family guide remains serially integrated. |
| 2026-07-22 | P7 | C++ lexical and semantic value paths published | `9b1ed7d` and `5eeff8e` add compiler-backed comment-drift and subsystem-map outcomes; `7f1c6b3` publishes 2 supported/20 pending C++ jobs. The consolidated map family passed `82` tests, focused publication replay passed `20`, and installed capability replay passed `89`. The remaining jobs stay pending, not unsupported. |
| 2026-07-22 | P7 | Ruby lexical supported; bounded semantic map integrated as partial | Ruby comment drift `230c279` plus publication `923184c` earns 1 supported outcome. Ruby subsystem map `423fd08` produces durable, source-preserving static facts and native checks but correctly remains partial for dynamic semantic reachability. Focused map/spine/matrix/router replay passes `49` tests after restoring an ignored build-role fixture and replacing the stale all-pending spine assertion. Rust spine runs independently; do not run slow full native family suites concurrently. |
| 2026-07-22 | P7 | Rust spine integrated; value cohorts next | Rust spine `f86f11c` plus root census integration proves Rust/Cargo profile, doctor, `.rs` inventory, offline locked workspace, native build/test/Clippy/rustfmt boundaries, direct-rustc boundary, source roles, and all 22 frozen job contracts. Generic integrated replay passes `39` tests. All jobs remain pending implementation—zero unsupported—until final artifacts earn supported or partial outcomes. |
| 2026-07-22 | P7 | Rust capability publication prepared; three value cohorts opened | Matrix schema v5 adds explicit Rust dispositions to all three routers so absent implementations route as pending rather than falling through generic language handling. Matrix/spine/router-unit replay passes `36` tests. Open disjoint Rust `find-comment-drift`, `map-subsystem`, and `move-path` worktrees; root alone integrates shared guides, coverage, matrix, routers, and the consolidated installed replay. |
| 2026-07-22 | P7 | Rust capability publication verified | `8c227b2` publishes schema-v5 Rust dispositions through all three routers. The committed installed/router/matrix replay passes `226` tests with one intentional skip; pending Rust jobs now fail closed as pending, while framework-bound requests preserve their exact `stack-bound` reason. |
| 2026-07-22 | P7 | Rust lexical outcome accepted for publication | `c3bcab2` adds one bounded, exact-span Rust comment-drift producer. Root replay across the complete comment-drift family, Rust spine, matrix, router recommendations, and skill conformance passes `89` tests. The adapter-plus-test cost is 1,200 physical lines and grows the selected closure by 29,910 bytes; compare its discovery/lifecycle/native-gate duplication with semantic and mutation pilots before extracting shared Rust infrastructure. |
| 2026-07-22 | P7 | Rust mutation outcome accepted for publication | `4149971` adds one transactional conventional Cargo library module move with preview, fingerprint-authorized apply, exact edits, native postflight, exact-after-tree proof, and rollback. Worker verification passes `18` focused plus `28` preserved-surface tests with one intentional skip. The adapter-plus-test cost is 2,027 physical lines and adds 59,178 bytes to the selected closure; keep broader module/crate shapes partial until separately proven. |
| 2026-07-22 | P7 | Rust semantic outcome accepted as useful partial | `f0bba1a` adds a durable Cargo/compiler/stable-LSP subsystem map. The selected configuration proves package/target/module/re-export provenance and eight inbound definitions, while macros, build output, include contents, variants, and runtime trait dispatch remain unresolved. Worker replay passes `6` focused, `5` Rust spine, `7` skill compliance, and `12` C-map regression tests. The adapter-plus-test cost is 1,913 physical lines and adds 61,622 bytes to the closure; all three pilot families now justify a measured shared-lifecycle comparison. |
| 2026-07-22 | P7 | Five-skill Rust lexical/filesystem batch accepted | `d59934c` adds one Rust-only fact helper plus distinct consumers for `adapt-project`, `explain-code`, concept divergence, exact lexical duplication, and filename topology. Focused replay passes `17`; preserved affected families pass `121`. The shared design costs 1,918 maintained adapter/test lines versus 4,702 with literal helper duplication, a measured 59.21% reduction, while keeping each final artifact and claim independent. |
| 2026-07-22 | P7 | Four-skill Rust syntax batch accepted for integration | `50e36bf` adds one bounded Rust syntax producer plus distinct decision-audit, advisory complexity, scout-gated omnibus, and match-enclosure standard-gap consumers. Worker replay passes `24` focused and `9` Rust spine/conformance tests. The maintained adapter/test surface is 1,702 lines versus 3,898 with duplicated providers, a measured 56.34% reduction. |
| 2026-07-22 | P7 | Five-skill Rust semantic batch accepted for integration | `67c1372` adds one Cargo/compiler/stable-LSP fact pack plus distinct dormant, implicit-state, incomplete-sweep, semantic-duplication, and rename-assessment consumers. Worker replay passes `4` focused, `18` Rust map/spine/conformance, and `32` preserved Go/Java/TypeScript sweep/rename tests. Provider sharing saves 2,488 lines, or 53.77%, while preserving all five outcome and human-verdict boundaries. |
| 2026-07-22 | P7 | Rust lexical, syntax, and semantic families published | `03ba149` publishes 16 supported, 1 useful partial, and 5 pending Rust outcomes with no unsupported claims. Root replay passes all `45` family tests, `12` Rust spine/matrix/skill-conformance tests, targeted Ruff, all commit hooks, and the committed installed-router journey (`1 passed`) that bootstraps the external library, routes every supported family member, preserves the partial map, and refuses a pending guard skill. |
| 2026-07-22 | P7 | Rust enum proposal and exact-field guard accepted for publication | `7a2e0a5` consumes complete implicit-state evidence into a read-only enum proposal, then requires a separate SHA-bound human acceptance before staging one project-owned Cargo field-type assertion. Focused replay passes `4`; preserved Go/Java state families pass `17`; the Rust semantic handoff passes `1`. The seeded String regression stays buildable without the guard and fails specifically with it installed. |
| 2026-07-22 | P7 | Rust read-only structural proposals accepted for publication | `9b0faf4` adds a shared Cargo evidence seam and distinct boundary/folder proposal adapters. Focused replay passes `7`; combined preserved proposal, Rust spine, metadata, and taxonomy surfaces pass `61`. Sharing saves 481 physical production lines (28.6%), and the exact disposable folder plan passes locked/offline metadata/check/test/Clippy/rustfmt/smoke. |
| 2026-07-22 | P7 | Rust shadow-unification proposal accepted for publication | `1c359d9` validates one accepted semantic lead and fact pack into atomic proposal/evidence/scope artifacts for an explicitly selected shape, without rerunning detection or claiming equivalence. Focused replay passes `12`; combined preserved Go/Java/TypeScript/JavaScript proposal and artifact-scope suites pass `43`. Reusing accepted evidence avoids 972 lines (60%) versus embedding the provider and detector. |
| 2026-07-22 | P7 | Bounded Rust coverage completed and installed journey accepted | `f7311f0` publishes 21 supported jobs, one useful partial map, and zero pending/unsupported jobs. `f1a99c4` correctly gates capability by the primary outcome owner while exposing partial companions; `e6e818e` closes the installed expectation. Root replay passes `23` new-family tests, `16` publication/closure tests, `49` router decision tests, targeted Ruff, all commit hooks, and the committed external-library router journey (`1 passed in 8.56s`). Whole-language completeness remains an explicit non-claim because the selected-configuration map is partial. |
| 2026-07-22 | P7 | Dart zero-write spine and implementation batches accepted | `f4a5eab` adds the dependency-free Dart 3.12 profile, doctor/inventory truth, direct-script test/smoke, native analyze/format, copied runtime, and 22 pending contracts. Focused Dart replay passes `6`; shared profile/doctor/inventory replay passes `28`. The spine proved that `dart run` creates `.dart_tool` and `pubspec.lock`, `dart test` needs host-owned `package:test`, and `dart analyze` does not validate malformed pubspec content. `8e16c5c` plus zero-write correction `ad6f277` divide all 22 jobs into D1-D8 batches, retain Flutter as a separate framework, and select the SDK LSP as a read-only semantic provider only when an existing package configuration resolves imports. Publish pending capability truth, then open D1, D2, and D4 in parallel. |
| 2026-07-22 | P7 | Dart first read-only wave accepted and published | D1 (`70184ee`) proves three project/lexical outcomes with 41.25% shared-maintenance savings. D2 (`8821fb4`) proves three locked public-analyzer outcomes with 43.06% savings; analyzer JIT, not offline Pub setup, dominates its measured runtime. D4 (`f246f0b`) proves two supported semantic outcomes and one useful partial map with 45.95% savings and one union SDK-LSP run. All accepted commands preserve host source and run from copied on-demand closures. Publication records 8 supported, 1 partial, and 13 pending. The six D1/D2 skills that require sibling `_dart` tooling are explicitly external-library-only for Dart so routers do not offer a broken stock selected install. |
| 2026-07-22 | P7 | Dart D3 stopped at an accepted-provider gap | `dcd4443` records that the D2 producer lacks general declarations, directives, body spans/tokens, and branch events. The four D3 consumers remain pending rather than adding private analyzer APIs or parallel lexers. One provider run measured 5.6067s versus 20.3657s for four starts, so a narrow additive D2 contract is now in progress and preserves the measured batching value. |
| 2026-07-22 | P7 | Dart D5 semantic-state family accepted | `eb9f7a6` adds two completed SDK-LSP consumers without modifying the accepted D4 provider. `find-implicit-state` requires a candidate-hash-bound human verdict; `find-incomplete-sweep` preserves resolved-call, Git-trajectory, scout, fixed-verdict, and triage boundaries. The copied six-file closure passes `7` focused tests, saves a conservative 27.48% maintained LOC versus duplicated providers, and reduces two separate LSP packs by a measured median 47.92%. `find-semantic-duplication` remains pending because definitions and references are not a substitute for per-function outgoing call hierarchy. |
| 2026-07-22 | P7 | Dart D6/D7 accepted-evidence consumers accepted pending publication | `4a314d0`, `78b0deb`, and `40a111e` add a bounded accepted-evidence validator plus four useful outcomes: enum proposal, exact-field staged regression guard, boundary proposal, and folder-reorganization proposal. Root replay passes `46` focused tests. The combined four-consumer seam saves 29.56% maintained LOC and 26.80% runtime-closure LOC versus four embedded validator copies; stopped `unify-shadows` is excluded. No runner, proposal schema, cache, or broader platform was extracted. Shared skill prose and capability publication wait for the concurrent D3 closeout. |
| 2026-07-22 | P7 | Dart D3 declaration/body family accepted | Provider extension `a3e6ff9` adds five public-analyzer fact groups without changing D2 semantics. `3c42fd5` consumes one keyed union snapshot for explanation, complexity, exact syntax duplication, and scout-graded omnibus outcomes. Root replay passes all `30` D2/D3 tests. One union avoids 75.23% of four analyzer starts; sharing saves 58.12% maintained LOC and 24.38% aggregate installed bytes versus duplicated providers. Consumer interpretation remains local and no second parser, daemon, cache, or cross-language AST was added. |
| 2026-07-21 | P3 | Started | Freeze the exact `60898a7` TypeScript+Java `find-omnibus` baseline and review the 87 registered/59 previously prunable worktree registrations before opening any P3 worker lane. |
| 2026-07-21 | P3.0 | Completed | Committed evidence freezes the existing-substrate decisions, exact TypeScript/Java projections and exclusions, copied closure bytes, fixture manifests, maintained LOC, OpenJDK 17.0.20/TypeScript 5.9.3 toolchain, full `18 passed` correctness run, and cold plus seven alternating warm trials. Registration-only pruning reduced 87 worktree records to 28 without deleting a path, branch, commit, or dirty worktree. P3.1 may now start from this spine. |
| 2026-07-21 | P3.1 | Completed | Added strict stdlib-only profiles for the five currently inventoried languages and a narrow lifecycle module. The deletion/caller-knowledge test is satisfied by two immediate consumers (TypeScript and Java omnibus); profiles remove duplicated suffix/tool/role/command/limit declarations, while lifecycle removes only atomic-write, stale-clear, source-hash, and terminal-vocabulary policy. No semantic result schema, adapter layer, installer, cache, mutation executor, or framework profile was added. P3.2 may extend the existing inventory from this spine. |
| 2026-07-21 | P3.2 | Completed | The existing `source_inventory.py` now reads the strict profiles under isolated/no-site Python, preserves all five current language projections, publishes profile schema/version capability, and emits explicit roles for excluded vendor/build/symlink roots without changing their established reasons. The portability fixture now copies and hashes the exact expanded inventory closure instead of passing through a checkout import. Widened installed-router/journey/release suite: `96 passed`. P3.3 and P3.4 may branch in parallel from this spine. |
| 2026-07-21 | P3.3 | Completed | `45f3c9c`; the read-only doctor resolves project-local tools before system tools and reports available, too-old, unavailable, and limited states without writes, installs, or network. Focused suite: `8 passed`; profile/inventory integration: `26 passed`. |
| 2026-07-21 | P3.4 | Completed | `bbd886d` plus root repair `f249d9a`; copied-library conformance covers TypeScript and Java final artifacts and state transitions under isolated/no-site Python. Integration exposed a real cross-language stale-artifact defect, now guarded without a language-specific branch; conformance: `20 passed`, preserved language suites: `29 passed`. |
| 2026-07-21 | P3 | Completed | `f249d9a`; integrated P3 surface `141 passed`. Seven alternating warm trials stayed within the +10% gate (TypeScript `+0.949%`, Java `+3.690%`); copied closure changed `-0.092%`, tracked scripts `+4.231%`. The exact public source replay installed only three routers, bootstrapped the retained external library/runtime, routed and conformed TypeScript, preserved host state, and uninstalled the routers. Begin P4 PHP preflight; do not broaden the shared substrate without pilot evidence. |
| 2026-07-21 | P4 | Started | Record PHP/Composer availability, freeze the three-cohort baseline and comparison economics, and create the P4 spine before opening disjoint lexical/semantic/mutation worker lanes. |
| 2026-07-22 | P4.0 | Spine frozen | `1bda74f` plus ignored-fixture correction `a3c70cb`; added the strict PHP profile, project-local doctor precedence, shared inventory classification, representative offline Composer host, malformed/excluded-role boundaries, exact manifests, three final-outcome cohort contracts, and frozen Java LOC/closure/latency economics. PHP 8.4.2 and Composer 2.4.0 are usable; Composer's PHP 8.4 deprecation noise is recorded rather than “fixed” by changing the host. Open three disjoint worker lanes from `a3c70cb`; shared profiles, routers, matrices, docs, and this ledger remain root-owned. |
| 2026-07-21 | Planning | Non-context plan review completed | `7637fcf`; three independent lanes reviewed the P3 substrate, language/worktree execution, and adversarial product alignment. Accepted bounded reuse, exact ownership, economics, release-truth, and measure-before-optimization findings; rejected stale private-repo assumptions and blanket prohibition on user-requested Swift/Dart planning. |
| 2026-07-23 | Planning/F0 | Obsolete worktrees retired and follow-on queue drafted | Fresh audit began with 70 registered worktrees. Root removed 64 clean worktrees whose complete patches were already represented on `main`, then retired the Java review after proving its substantive bytes already landed and the dirty JavaScript precursor after the committed mutation regression passed `2 passed`. All branch refs and commits remain. Four checkouts remain: `main`, two completed unmerged Dart lanes, and the archived preflight checkout with machine-local policy logs. Checked-out disk use fell from about 2.2 GB to 1.1 GB. Three fresh non-context read-only reviews then shaped F0-F7 around serial Dart/repository closeout, family-batched languages, and measured UX adoption. |
| 2026-07-23 | P7/F0 | Dart D5/D7 integrated and published | `ef9a9fb` integrates the bounded Dart semantic-duplication detector and accepted-evidence shadow proposal consumer onto the final D4 outgoing-call provider. Root replay passes `35` D4/D5/D7 and copied-closure tests in 144.60s. Skill prose, coverage, catalog, and generated matrix now publish 20 supported outcomes, one useful partial map, and only `move-path` pending; their focused publication/router tests pass `37` in 8.39s, metadata lint reports 76 conforming skills, and artifact drift is clean. D8 remains isolated until unrelated-file over-refusal is repaired and replayed. |
| 2026-07-23 | P7/F0 | Dart D8 accepted after adversarial repair | `9075acc`, `c037890`, and `80724f4` integrate one evidence-authorized private-library move plus two review-response checkpoints. Regression-first repair scopes unrelated boundaries, refuses impacted symlink consumers before mutation, fingerprints file modes, preserves rollback/exact-tree proof, makes native tests portable, and deletes one dead 563-line copied helper. Worker replay passes `26` Dart move tests, `61` D1/D2/D4/conformance tests, and the preserved non-Dart family at `72 passed, 1` intentional skip; root replays `12` critical transaction, decoy, symlink, mode, rollback, and copied-closure cases in 181.16s. Coverage publication now records 21 supported jobs, one useful partial map, and zero pending jobs. |
| 2026-07-23 | P7/F0 | Dart coverage/runtime semantics resolved | `e22a021` publishes transactional move support, and the committed installed-router replay passes in 3.61s while routing Dart semantic duplication, shadow proposal, and move-path to their external-library closures with only three ambient routers. The accepted distinction now reserves coverage `partial` for an incomplete implementation while allowing a bounded `supported` contract to return visible runtime partials for unsupported configurations. The already-proven selected-configuration Dart map therefore closes as supported with explicit conditional/part/generated/Flutter limitations: Dart is 22 supported, zero partial, zero pending, and zero unsupported. |
