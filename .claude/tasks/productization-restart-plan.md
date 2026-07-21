# Engineering-skills productization restart

Status: router-only on-demand local candidate and TypeScript milestone passed — public publication pending

This is the small progress tracker for the restart. Update checkboxes only
after the named command or journey passes at a committed revision. Tests,
plans, reviews, and line count are supporting activity, not progress by
themselves.

## Ordered product goals

1. Make the skill collection easy to install.
2. Make applicable skills genuinely multi-language, beginning with
   TypeScript.
3. Improve the installed user journey and execution efficiency.

Work proceeds in that order. Later-phase analysis may inform a decision, but
later-phase implementation does not start before the previous milestone
passes.

## Review relevance rule

Every adversarial review must restate the three goals above. A finding may add
work to this plan only when it:

- materially affects a current or next required journey; or
- prevents a concrete critical defect likely to harm users or compromise the
  product.

Everything else is non-gating and may be captured in
`.claude/tasks/multilanguage-support-backlog.md` when it concerns language
support, or in the general idea ledger otherwise. Review does not automatically
create implementation work.

## Milestone 1 — Simple installation

Outcome: use the stock Agent Skills installer for exactly three ambient routers
and a thin source bootstrap for the non-discovered guide/tool library. Do not
build a custom package manager, trust ceremony, transactional lifecycle,
five-surface projection, or generic executor.

- [x] **I1 — Stock discovery.** From a clean checkout, the pinned command
  `npx --yes skills@1.5.19 add <source> --list` exits zero and lists exactly
  76 skills.
- [x] **I2 — Router-only install.** From an empty Git host, one documented
  stock command installs exactly `which-shape`, `which-skill`, and
  `which-cleanup`; the source checkout remains clean.
- [x] **I3 — Self-contained routers.** Copies containing only each installed
  router directory run under Python isolated/no-site mode outside the source
  checkout. `which-shape` returns the expected shape for two fixtures;
  `which-skill` returns the expected skill for two fixtures; `which-cleanup`
  returns a bounded closeout roster with selected-skill/tooling locations.
  None imports a
  repository-level module, requires a toolkit venv, third-party Python
  package, or network access.
- [x] **I4 — On-demand library handoff.** The documented bootstrap materializes
  the full source in a project-scoped sibling cache outside both the target
  repository and agent discovery. Task, shape, and cleanup routing return exact local guide/tool
  closures and default non-trivial work to a fresh non-context sub-agent.
  Ambient selected-skill installation is labeled optional and requires an
  explicit user choice.
- [x] **I5 — First useful result.** A fresh-context agent, given only the
  installed routers, selected on-demand guide/tool closure, fixture project,
  and user task, produces the expected useful artifact without installing a
  task skill. One TypeScript journey must reach its final native outcome from
  the external library through both task and shape routing.
- [x] **I6 — Standard removal boundary.** The documented stock removal path
  removes the installed skill directories and leaves a sentinel outside the
  standard skill paths byte-identical. No promise is made about preserving
  user edits inside installed skill directories.
- [x] **I7 — Clean replay and goal-anchored review.** One clean scripted replay
  passes I1–I6 at a single revision. A fresh-context reviewer receives the
  ordered product goals and reports no goal-critical or concrete user-harm
  blocker.

Milestone 1 is complete only when I1–I7 are checked with the exact revision and
commands recorded below.

## Milestone 2 — TypeScript-first multi-language support

Do not start implementation until milestone 1 closes.

The executable inventory, ordered batches, worktree ownership, acceptance
criteria, and learning handoff are tracked in
`.claude/tasks/typescript-skill-batch-plan.md`.

Status: complete locally at `f626f72`, with the companion-aware `which-shape`
journey repaired at `dceef96`. The final 76-skill matrix records 22
`typescript-supported`, 19 `validated-neutral`, 22 `stack-bound`, and 13
`ecosystem-runtime` dispositions. Broader-language follow-ups are tracked in
`.claude/tasks/multilanguage-support-backlog.md`.

The first outcome family is split serially rather than assigned as one large
port:

1. `B2P` proves the Python string-state chain is reference-grade and
   self-contained when stock-installed.
2. `B2T` proves the same closed-state invariant in a locked TypeScript fixture,
   including proposal, native type/test result, staged guard, installed replay,
   and fresh-context outcome.

Small text/metadata-truth and comment-hygiene batches may run alongside the
Python proof when their worktrees are disjoint. Framework-specific skills stay
deferred until a concrete TypeScript stack is selected. No shared TypeScript
analysis platform may be extracted before an accepted second consumer exists.

## Milestone 3 — User journey and efficiency

Do not start implementation until milestone 2 closes.

Before claiming the router-led journey works well, validate decision quality
for all three default routers. Use one small committed corpus and focused test,
not a general evaluator platform:

1. Cover clear matches, ambiguous cases, direct/no-skill cases, misleading or
   negated cues, and different scope sizes for `which-shape`, `which-skill`,
   and `which-cleanup`.
2. Give each case an expected route or allowed set; ambiguous cases may instead
   require a named discriminating question.
3. Require every selected non-router skill to include its exact on-demand
   guide/bundled-tooling/shared-tooling closure and an explicitly secondary
   optional install command.
4. Require all clear cases to match, zero known heavy-router false positives on
   direct tasks, and zero missing handoffs. Every discovered misroute becomes a
   regression case before changing heuristics.
5. Forward-test one representative on-demand-library journey per router with
   fresh context and judge the final task outcome, not merely the router JSON.

Freeze representative installed workflows and their outcome checks. Measure
completion, correctness, wall time, tokens, repeated context, and human
interventions. Batch complementary read-only lenses; keep mutations serial.
Build shared coordination only when measured fixed workflows demonstrate that
it is necessary.

## Evidence log

| Date | Revision | Criterion | Evidence |
|---|---|---|---|
| 2026-07-18 | `ad685e3` | Baseline only | Stock `skills@1.5.19` discovered 76 and installed both routers; isolated execution failed on repository-level imports. This is RED evidence, not acceptance. |
| 2026-07-18 | `7c14dd4` | I1–I4 | A clean temporary Git host used `skills@1.5.19`: discovery reported exactly 76; router install selected exactly two directories; four installed router fixtures passed under `python3 -I -S`; the router-selected local-source command installed only `gut-check`. Targeted suite: 47 passed. |
| 2026-07-18 | `7c14dd4` | I5 | A GPT-5.6 Terra xhigh fresh-context agent received only the installed `gut-check`, host fixture, and user task. Against the committed fixture now at `tests/fixtures/standard-install/architecture-plan.md`, it produced five cited strong-smell findings. The first shorter fixture correctly exercised the skill's documented below-threshold path and was replaced rather than counted as success. |
| 2026-07-18 | `7c14dd4` | I6 | `skills@1.5.19 remove --all` removed all three installed skill directories. `KEEP.txt` remained SHA-256 `1954cbe1b926f93e3cd432127f483e7db98ab6bfa7453060205ef90b60225fb3`; only empty standard directories and `skills-lock.json` remained. |
| 2026-07-18 | `c404944` | I1–I7 replay | From one clean Git host: stock discovery found 76; exactly two routers installed; two `which-shape` and two `which-skill` isolated fixtures passed; the emitted local-source command installed only `gut-check`; a fresh GPT-5.6 Terra xhigh agent produced four cited strong-smell findings from the committed fixture; removal deleted all three skill directories and preserved the sentinel hash above. Targeted suite: 47 passed. A goal-anchored fresh reviewer returned PASS with no goal-critical finding and rejected unrelated platform expansion. |
| 2026-07-18 | `c404944` | Release prerequisite | The local candidate is complete, but the README's public source still resolves to `ce257f57…`, not `c404944`. Publish the candidate to that distribution ref, then replay the public URL before calling installation publicly complete. |
| 2026-07-18 | `f26d9ea` | Revised I2–I6 | Stock `skills@1.5.19` installed exactly the three default routers. All ran from installed directories under `python3 -I -S`; shape, task, and cleanup results included selected-skill install commands plus definition, bundled-tooling, and shared-tooling locations. Only selected `gut-check` was then added; a fresh GPT-5.6 Terra xhigh agent produced five cited strong-smell findings. `remove --all` removed all four directories and preserved the sentinel SHA-256 `1954cbe1b926f93e3cd432127f483e7db98ab6bfa7453060205ef90b60225fb3`. Targeted suite: 73 passed, 1 intentional skip. |
| 2026-07-18 | `f26d9ea` | Revised I7 | A fresh goal-anchored reviewer returned PASS with no goal-critical or concrete-user-harm blocker. It confirmed exact-three default installation, selected-only follow-up installation, isolated execution, useful output, and sentinel-preserving removal; it explicitly rejected custom trust/installer, multi-surface, coordinator, benchmark, and premature TypeScript expansion. |
| 2026-07-18 | this planning commit | Milestone 2 batch freeze | `.claude/tasks/typescript-skill-batch-plan.md` assigns all 76 skills exactly once, freezes B1/B2P as the first disjoint worktrees, makes B2T serial after the Python proof, requires paired learning artifacts, and defers unproven/framework-bound families. Three fresh non-context inventory lanes informed it; 38 targeted baseline tests passed; a fresh goal-anchored adversarial review returned PASS after router-honesty corrections. |
| 2026-07-19 | `f626f72` | Milestone 2 local completion | The 76-row matrix closed at 22 TypeScript-supported, 19 validated-neutral, 22 stack-bound, and 13 ecosystem-runtime skills. Canonical suite: 660 passed, 2 named environment skips; focused closure set: 77 passed. See `.claude/tasks/typescript-skill-batch-plan.md` for per-family evidence. |
| 2026-07-19 | `dceef96` | Shape-router companion closure | A real clean-host regression now runs both `which-skill` and `which-shape`, installs exactly `rename-concept` plus required `find-concept-divergence`, and reaches the final TypeScript `COMPLETE` outcome. Focused router/outcome suite: 80 passed; canonical suite: 661 passed, 2 documented environment skips; Ruff and registry validation passed. |
| 2026-07-19 | this revision | Router-only on-demand library | Stock `skills@1.5.19` installs exactly the three routers; the bundled stdlib bootstrap materializes a project-scoped sibling library outside the host and discovery roots. Task, shape, and cleanup routers return selected skill roots, guides, optional bundled tools, shared guidance/tool roots, and explicitly secondary ambient-install commands. Both task and shape routing execute the `rename-concept` companion closure from the library and reach TypeScript `COMPLETE` without installing a task skill. A fresh non-context README replay selected `gut-check` and produced four cited strong-smell findings with no user-facing blocker. Focused final suite: 102 passed; canonical suite before the final closure-render additions: 664 passed, 2 documented environment skips; final two-finding re-review: PASS. ADR 0038 records the decision. |
| 2026-07-19 | this revision | Multi-language P1 portability harness | All three routers expose the selected closure's generated language/fact/outcome capabilities and emit ambient-install commands only for closures with passed evidence. The bounded test harness executes the on-demand library's own inventory/tool paths, distinguishes seven final outcomes, preserves source fingerprints, and proves complete/partial TypeScript mapping with a native check. Runtime-helper extraction stopped because it would obscure selected-install closure without a real two-consumer repair. Focused P1 integration: 90 passed; canonical: 686 passed, 2 documented skips; fresh product review and bounded re-review: PASS. |

## Current slice

1. Publish the reviewed candidate to the intended public distribution ref and
   replay the README's stock three-router install, sibling-library bootstrap,
   on-demand route, useful result, and router-only discovery assertion before
   making public support claims. This is a release action, not new installer
   development.
2. Review the TypeScript learning packets and the scoped multi-language backlog
   when selecting one next-language pilot. Start with a small representative
   family, not simultaneous blanket conversion.
3. Begin the user-journey milestone only after the next language scope is
   explicitly chosen; keep routing quality and measured efficiency separate
   from speculative execution-platform work.

## Deferred product-review queue after language compatibility

Two fresh product-framed reviews on 2026-07-21 (GPT-5.6 Luna max and
GPT-5.6 Sol xhigh) agreed that the router-only/on-demand architecture and
support-honesty boundaries are valuable, but the overall product journey is
not finished. These items are recorded now and remain unscheduled until the
active language-compatibility pass reaches its checkpoint:

1. **Library lifecycle:** define the smallest pinned install/update/repair/
   doctor/uninstall journey that prevents router/library version drift. Do not
   revive content attestation or a custom package manager.
2. **Shared support truth, distinct router jobs:** all three routers should
   honor the same language/framework support and partial/unknown states, but
   they must not collapse into one generic router:
   - `which-skill` answers “what skill should I use right now for this task?”;
   - `which-shape` answers “what overall workflow and set/sequence of skills
     fits this situation?”; and
   - `which-cleanup` answers “given the recent work, what proportionate checks,
     cleanup, and guards are needed to bring it up to standard?”
   Expand the natural-language decision corpus around those distinct outputs
   rather than building a learned router.
3. **First-success audit-to-change journey:** prove one cold host can move from
   project orientation and a prioritized roadmap through an approved bounded
   refactor, native verification, and guard closeout. This may justify a
   portable `execute-approved-refactor` contract; it does not justify an
   autonomous mutation coordinator.
4. **Project orientation/profile:** evaluate one concise project profile that
   supplies language/framework evidence, topology, native commands, risks, and
   open questions to routers and execution agents without ambiently loading the
   whole skill catalog.
5. **Outcome telemetry:** prefer resolved/adopted/deferred/regression-held
   outcomes over additional activity dashboards.

Both reviews explicitly rejected a universal DAG/context cache, autonomous
mutation platform, blanket skill compression, more attestation hardening, and
new micro-skills as substitutes for these user journeys. Reassess this queue
after the language pass with real host evidence; do not promote every item
merely because two reviewers mentioned it.
