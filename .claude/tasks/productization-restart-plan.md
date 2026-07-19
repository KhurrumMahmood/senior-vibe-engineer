# Engineering-skills productization restart

Status: active — milestone 1

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

Everything else is non-gating and may be captured in the idea ledger. Review
does not automatically create implementation work.

## Milestone 1 — Simple installation

Outcome: use the stock Agent Skills installer. Do not build a custom package
manager, trust ceremony, transactional lifecycle, five-surface projection, or
generic executor.

- [x] **I1 — Stock discovery.** From a clean checkout, the pinned command
  `npx --yes skills@1.5.19 add <source> --list` exits zero and lists exactly
  76 skills.
- [x] **I2 — Router-only install.** From an empty Git host, one documented
  stock command installs exactly `which-shape` and `which-skill`; the source
  checkout remains clean.
- [x] **I3 — Self-contained routers.** Copies containing only each installed
  router directory run under Python isolated/no-site mode outside the source
  checkout. `which-shape` returns the expected shape for two fixtures;
  `which-skill` returns the expected skill for two fixtures. Neither imports a
  repository-level module, requires a toolkit venv, third-party Python
  package, or network access.
- [x] **I4 — Selected-skill handoff.** `which-skill` emits a pinned stock
  installation command for its winner. Running the command installs only that
  selected skill in addition to the routers.
- [x] **I5 — First useful result.** A fresh-context agent, given only the
  installed routers, selected installed skill, fixture project, and user task,
  produces the fixture's expected useful artifact. The initial selected skill
  is prompt-only or self-contained.
- [x] **I6 — Standard removal boundary.** The documented stock removal path
  removes the installed skill directories and leaves a sentinel outside the
  standard skill paths byte-identical. No promise is made about preserving
  user edits inside installed skill directories.
- [ ] **I7 — Clean replay and goal-anchored review.** One clean scripted replay
  passes I1–I6 at a single revision. A fresh-context reviewer receives the
  ordered product goals and reports no goal-critical or concrete user-harm
  blocker.

Milestone 1 is complete only when I1–I7 are checked with the exact revision and
commands recorded below.

## Milestone 2 — TypeScript-first multi-language support

Do not start implementation until milestone 1 closes.

1. Inventory all 76 skills as language-neutral, language-sensitive analysis,
   mutation, guard generation, or framework-specific.
2. Select one cohesive family; the leading candidate is
   `find-implicit-state → extract-enum → prevent-regression`.
3. Make that family's Python path reference-grade with positive, negative,
   must-not-fire, structured-output, change/guard, native-test, and installed
   self-containment evidence.
4. Implement and install the TypeScript path against the same invariant-level
   outcome contract.
5. Extract only abstractions demonstrated by both implementations and record
   what did not generalize before choosing the next family or language.

Milestone 2 acceptance criteria will be frozen after the inventory and first
family selection. “All languages” and artificial variants of language-neutral
skills are not acceptance criteria.

## Milestone 3 — User journey and efficiency

Do not start implementation until milestone 2 closes.

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

## Current slice

Commit the README journey and frozen first-use fixture, then replay I1–I6 from
that one revision and run the goal-anchored fresh review for I7. No
cross-language or optional high-assurance work is active before I7 closes.
