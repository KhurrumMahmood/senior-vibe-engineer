# Cross-language tool and SkillOpt evaluation plan

Status: complete — no product dependency adopted; Java J1 is the next product work

Primary objective: determine whether a small number of existing tools can make
the next language ports cheaper and more reliable, without delaying the Java
pilot or creating a universal portability platform. A separate bounded
SkillOpt experiment tests whether evidence-driven optimization can improve one
high-leverage judgment skill.

## How to resume this work

1. Start at this repository root on `codex/productization-restart` and run
   `git status --short --branch`.
2. Read this file and continue the first row whose state is `in_progress`, or
   the first `pending` row whose dependencies are complete. If every row is
   terminal, follow `next_action` into the expansion plan rather than inventing
   another tool experiment.
3. Do not infer completion from installed tools or partial output. Check the
   row's acceptance boxes and its evidence path.
4. Write partial results to the named evidence JSON before pausing. Set
   `last_completed_checkpoint` and `next_action` below so another session does
   not need the conversation history.
5. Keep experimental environments under
   `.claude/tasks/tool-evaluations/local/`; do not add their packages to the
   product requirements unless an adoption gate passes.
6. A candidate may modify only its experiment closure. Product skills remain
   unchanged until the comparison is complete and explicitly accepted.

## Resume state

- `last_completed_checkpoint`: X1 rejected, X2 continued to a real-language
  pilot, X3 stopped after a nondiscriminating four-call baseline, and X4 made
  no production dependency change
- `next_action`: return to Java J1. Redesign X3 only as a later bounded task;
  do not run the optimizer against the current corpus
- `active_experiment`: none
- `production_changes_allowed`: no
- `java_pilot_blocked_by_experiments`: no

## Experiment ledger

| ID | Experiment | State | Dependencies | Evidence |
|---|---|---|---|---|
| X1 | ast-grep structural-fact pilot | `complete_reject` | none | `.claude/tasks/tool-evaluations/ast-grep-results.json` |
| X2 | Tree-sitter language-pack spike | `complete_continue_pilot` | none | `.claude/tasks/tool-evaluations/tree-sitter-results.json` |
| X3 | SkillOpt `/scope-feature` pilot | `stopped_inconclusive_no_headroom` | frozen corpus and runnable backend | `.claude/tasks/tool-evaluations/skillopt-scope-feature/results.json` |
| X4 | Product adoption decision | `complete_no_dependency_adopted` | X1 and X2 complete; X3 may remain independently pending | this file and ML-012/ML-013 |

X1 and X2 are independent of Java J1 and may pause without affecting language
support. X3 is deliberately cost-capped and must not consume the remaining
interactive usage without a recorded run budget.

## X1 — ast-grep structural-fact pilot

**Question.** Can a pinned, on-demand ast-grep CLI reduce per-language syntax
implementation while preserving the facts and failure boundaries already
proved by native TypeScript, Go, and Java complexity detectors?

**Pinned tool.** `@ast-grep/cli@0.44.1`, invoked with `npx --yes`; it is not an
ambient product dependency.

**Frozen inputs.** The committed `find-complexity-hotspots` TypeScript, Go, and
Java fixtures and the corresponding native detector outputs at the experiment
base revision.

**Measured outputs.** Function/method kind, symbol/name when available, exact
start/end span, direct-body control-flow facts, malformed-source behavior,
excluded-source behavior, warm/cold wall time, rule/adapter LOC, downloaded
bytes, and install/runtime prerequisites.

Acceptance:

- [x] Native baseline outputs and source hashes are captured before the
      experiment.
- [x] ast-grep rules are example-tested for all three languages before fixture
      scans.
- [x] The comparison distinguishes structural matches from semantic/project
      facts and never awards semantic support for syntax parity.
- [x] Positive, clean, nested-function/lambda, test/generated/vendor, and
      malformed cases are reported for each language.
- [x] Results report exact parity gaps, implementation LOC, cold/warm time,
      cache/network behavior, and installed footprint.
- [x] The evidence ends in `adopt`, `adopt_on_demand`, `continue_pilot`, or
      `reject`, with a reason tied to future C#/PHP/Rust effort.

Result: `reject` as a replacement for the current complexity helpers. It
reproduced all accepted final records, but the experiment wrapper still owned
language-specific identity and source-exclusion policy, used 104 rule LOC plus
396 harness LOC, downloaded about 268 MB cold, and failed to surface the Java
malformed fixture. Revisit only for a bounded ad-hoc structural search or a
queued-language outcome where those costs are smaller than a native adapter.

Stop conditions: stop rather than expanding rules when reproducing the final
outcome requires language-specific semantic resolution, when exclusion policy
dominates the parser code, or when three rules become three unrelated native
adapters hidden behind one executable.

## X2 — Tree-sitter language-pack spike

**Question.** Does the package provide a stable, genuinely reusable syntax
fact layer for three core languages under the project's copied/offline
constraint?

**Pinned comparison.** Evaluate current `1.13.2` in an isolated experiment
venv. Record the already-present `1.12.5` shared-venv observation only as
history; do not mutate that environment.

**Frozen languages.** Java, C#, and PHP. They exercise one active pilot and the
next two queued ecosystems without claiming product support.

Acceptance:

- [x] A clean isolated environment installs the pinned package and records
      wheel/download/cache sizes.
- [x] Required grammars are prefetched, the network is then disabled, and the
      same queries rerun successfully—or the offline failure is recorded.
- [x] Each language reports declarations, calls/imports where supported,
      spans, parse errors, and query portability differences on locked minimal
      fixtures.
- [x] Grammar availability, validated fact families, and semantic support are
      reported as three different capabilities.
- [x] A version/grammar change risk and maintenance estimate are included.
- [x] The evidence ends in the same four-way disposition used by X1.

Result: `continue_pilot`. The pinned package and 7.5 MB cached grammar closure
replayed Java, C#, and PHP facts under OS-level network denial and surfaced all
malformed fixtures. It still requires language-specific queries and provides
no semantic facts. The next adoption gate is one final C# or PHP product
outcome, not more parser-platform work.

Stop conditions: no product adoption if grammars cannot be made deterministic
without a large vendored bundle, if common queries require incompatible
per-language schemas with no reduction in code, or if error recovery produces
unsafe completeness claims.

## X3 — SkillOpt pilot on `/scope-feature`

**Why this skill.** `/scope-feature` is judgment-heavy and directly addresses
the high-cost failure of allowing technically valid side concerns to displace
the user's current product goal. `/which-skill` is not the pilot because its
recommendation is primarily produced by deterministic `match.py`; optimizing
its Markdown would not test the actual routing outcome.

**Protected production surface.** SkillOpt may train only a copied body of
`.claude/skills/scope-feature/SKILL.md`. It may not edit scripts, metadata,
catalogs, other skills, canonical docs, fixtures, or the production file.

**Corpus contract.** Create small realistic cases across: correct System-tier
scope, Feature-tier downgrade, Quick-tier rejection, explicit product-priority
constraints, tempting but low-value adversarial findings, ambiguous intent,
measurable success criteria, and missing out-of-scope boundaries. Freeze train,
selection, and untouched test IDs before the first candidate is produced.

**Scoring contract.** Hard gates cover correct tier/outcome, no invented user
answers, explicit in/out/non-goal boundaries, observable acceptance criteria,
binding-prior use, and refusal to expand low-value concerns. Soft scoring may
cover concision and question quality only after every hard gate passes.

**First-run budget.** One epoch, at most two edits per update, one fixed seed,
and the smallest corpus that exercises every hard gate. Record target,
optimizer, harness and SkillOpt versions plus calls/tokens/wall time. Do not
start model calls if the remaining usage budget is uncertain; setup and a dry
run may complete independently.

Pinned setup: SkillOpt source commit
`b860a5cf88ce75e2bd02ca981ac21fb28cffba83`, package version `0.2.0`,
`gpt-5.6-terra` at medium effort for both target and optimizer, committed
6/2/2 train/selection/test splits, and a two-edit budget. The production skill
is copied to the ignored run directory during validation and is never an
optimizer write target.

Exact resumable commands, run one phase at a time from the product worktree:

```bash
# Free validation; safe to rerun.
.claude/tasks/tool-evaluations/local/skillopt-0.2.0/bin/python \
  .claude/tasks/tool-evaluations/skillopt-scope-feature/run_experiment.py validate

# Four target calls. Do not rerun after results.json says baseline_complete.
# If interrupted, rerun the same command: completed per-case result.json
# checkpoints are reused, so only unfinished calls are made.
SKILLOPT_RUN_BUDGET_ACCEPTED=1 \
  .claude/tasks/tool-evaluations/local/skillopt-0.2.0/bin/python \
  .claude/tasks/tool-evaluations/skillopt-scope-feature/run_experiment.py baseline

# One frozen training step. DO NOT RUN for the current nondiscriminating
# corpus; this command becomes eligible only after a newly frozen baseline
# demonstrates headroom and the results status is baseline_complete.
SKILLOPT_RUN_BUDGET_ACCEPTED=1 \
  .claude/tasks/tool-evaluations/local/skillopt-0.2.0/bin/python \
  .claude/tasks/tool-evaluations/skillopt-scope-feature/run_experiment.py optimize

# Two held-out target calls, then human review.
SKILLOPT_RUN_BUDGET_ACCEPTED=1 \
  .claude/tasks/tool-evaluations/local/skillopt-0.2.0/bin/python \
  .claude/tasks/tool-evaluations/skillopt-scope-feature/run_experiment.py candidate
```

Acceptance:

- [x] SkillOpt is installed in an isolated, reproducible environment and its
      version/source revision is recorded.
- [x] Corpus IDs, splits, scorers and baseline are frozen before optimization.
- [ ] No-skill, current-skill, and candidate conditions run through the same
      pinned target/harness.
- [ ] The candidate is evaluated on untouched cases and compared with the
      current skill, not merely with no skill.
- [ ] Adoption requires no hard-gate regression, improvement beyond run-to-run
      variation, acceptable context size/cost, and human semantic review.
- [x] Rejected edits and inconclusive evidence remain visible; no automatic
      production update occurs.
- [x] The learning report says whether SkillOpt is useful for other judgment
      skills and what evaluation infrastructure would be reused.

Result: `inconclusive_stop_before_optimization`. Both no-skill and current-skill
conditions passed 2/2 held-out cases, so the corpus had no discriminating
power. The four scored calls used 41,847 reported tokens; one isolated smoke
used another 21,183, and two pre-isolation timeout attempts have unknown usage.
The response schema and evaluator prompt exposed too much of the desired
behavior. A later retry must use natural task prompts, hidden standards, harder
binding-precedent cases, and repeated current/no-skill runs before SkillOpt is
allowed to edit anything. The reusable parts are the isolated runner,
per-case restart checkpoints, frozen split manifest, and deterministic hard
gates—not this corpus.

## X4 — Adoption decision

Do not combine X1 and X2 merely because both parse syntax. Adopt the smallest
tool whose measured reduction is real:

- preserve native compiler/project tools as authoritative for semantic facts;
- keep text search for documentation and exact-text work;
- prefer an on-demand executable/closure over a default installer dependency;
- record each skill's required fact level and the provider used; and
- require one later-language implementation to demonstrate that the measured
  prototype reduction survives a real product journey.

If neither tool passes, continue the existing family-local native approach.
That is a valid result, not a failed experiment.

Decision: adopt no new production dependency now. Keep Tree-sitter
language-pack isolated for one real C# or PHP final-outcome pilot. Do not use
ast-grep to replace the accepted complexity helpers. The Java pilot and normal
language-family work remain on the existing native path.
