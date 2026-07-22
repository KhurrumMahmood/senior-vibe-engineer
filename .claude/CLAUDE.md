# CLAUDE.md

Shared root agent guide for the **engineering-skills** ecosystem. Claude
reads this as `CLAUDE.md`; Codex reads the root `AGENTS.md` symlink that
points here; Augment imports condensed always-apply rules from
`.augment/rules/imported/`; Cursor and Gemini follow symlinks under
`.cursor/CURSOR.md` and `.gemini/GEMINI.md`.

This file is intentionally lean. Detailed reference material lives in
`.claude/docs/` — read the relevant file when working in that area. The
table at the bottom names every doc and the trigger that should pull it.

Unless a rule explicitly scopes itself to one agent, treat it as applying to
**all agents**: Claude Code, Codex, and Augment. Agent-specific blocks use
square-bracket tags such as `[Codex-Specific]…[/Codex-Specific]`,
`[Claude-Code-Specific]…[/Claude-Code-Specific]`, and
`[Codex-Launching-Claude-CLI]…[/Codex-Launching-Claude-CLI]`. Use these
rarely, only for cross-tool bridge cases.

Machine-local rules that don't generalize — tool/plugin choices, agent
dispatch lanes, spend constraints — live in `.claude/CLAUDE.local.md`
(gitignored, optional). Read it if present; never move shipped rules
there, and never put tool-specific nuance in shipped files.

## What this repo is

A portable senior-engineer **skill ecosystem** — skills, docs, scripts,
linting scaffold, and ADR/plan/spec workflow — extracted from a real
Django host project. It exists to make AI coding agents work like senior
engineers: framing problems before solving them, refactoring deliberately,
authoring ADRs for material decisions, and converting one-off discoveries
into durable guardrails.

The mantra: **"Optimal tooling for an AI-grown codebase continuously
converts hidden structure into explicit structure, and one-off discoveries
into repeatable guardrails."**

Because this kit exists to export standards into other projects, it is
held to its own standard first — that is the condition for it dependably
adding value elsewhere. Skills must meet the activation standard
(`.claude/skills/repair-skill/knowledge/skill-standard.md`); conformance
is machine-checked where possible (`scripts/skill_comply/`); a skill
whose text cannot be trusted at execution time is a defect even with no
incident behind it (`/repair-skill`).

Most files are framework-agnostic. Some lint rules, scripts, and helper
modules grew up around Django/Python — the design has always anticipated
cross-language adapters (TypeScript, Rust) and cross-framework reuse;
see `docs/language-support-development.md` before expanding a language and
`.claude/skills/_common/portability-roadmap.md` for the longer-term porting
contract.

## Python Environment

Many scripts and skills are stdlib-only and run on any Python ≥ 3.11.
Some (e.g. PyYAML-backed frontmatter parsing in `scripts/_lib/`) need
deps from `requirements.txt`. Install once per clone:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pre-commit install
```

Always invoke pip as `.venv/bin/python -m pip` (never the
`.venv/bin/pip` shim): venv shims hardcode the creation-time absolute
path, so after a directory rename they silently target the old
location. `/engineer-init` validates `pyvenv.cfg` and rebuilds a stale
venv automatically. CI-only extras (dashboard browser smoke) live in
`requirements-dev.txt` — optional locally.

`/engineer-init` runs these steps idempotently — Python-version check,
venv, deps, and pre-commit hooks when the repo is git-tracked — then
verifies a script-backed skill runs. Prefer it over the manual block.

**Use `.venv/bin/python` explicitly** (not bare `python`) — sub-agents
don't inherit shell activation, so include the venv path in every prompt
you hand off.

## Verification Policy (Tiered)

Match test scope to the change. Don't run the full ladder for tiny work,
but don't skip verification on shared-surface changes either.

| Change shape | Run |
|---|---|
| Pure docs / comments | Nothing automated |
| Tiny local fix (one file, narrow blast radius) | Touched tests only — name them in your reply |
| Normal code change | Project's narrowest meaningful suite (state which) |
| Shared service / pipeline / settings change | Project's targeted suite for the affected surface |
| UI / template change | Headless browser test (Playwright or equivalent) against a running dev server |
| Live integration change | Full live suite (server + workers + network) |
| Endpoint touched | Manual JSON / page render check, no console errors |

If a verification step cannot be run, **state which one and why** — don't
claim done. See `docs/testing.md` for picking the right test module and
`docs/development-workflow.md` for the test-first protocol.

## Linting

Diff-scoped (pre-commit + CI lint only changed files). Targeted while
editing: `.venv/bin/ruff check <path>`. The full rule catalogue and the
list of active project AST lints lives in `docs/canonical-patterns.md`
and `docs/linting.md`. The base lints shipped with this ecosystem are:

- `silent-catch` — no bare `except: pass` in services/views
- `stringly-status` — TextChoices for state fields and comparisons
- `query-mutation` — `get_/fetch_/load_/...` methods must not mutate
- `fat-view` — view functions must stay within a LOC budget
- `safe-dispatch` — no bare `.delay()` / `.apply_async()` in tasks/views/services
- `comment-drift` — comments and docstrings must stay aligned with code
- `codegen-emits-new-paths` — pluggable check that codegen targets canonical paths

The ecosystem can lint its own runtime too: `scripts/lint/run.py --self`
points the rules that are clean of host/Django assumptions —
`silent-catch` and `query-mutation` — at `scripts/` and `.claude/skills/`.
The remaining rules are skipped (see `RuleSpec.self_applicable` in
`run.py`). `--self` is a manual dogfooding check, not part of
host-project pre-commit.

Project-specific lints (UI primitives, domain rename, sidecar boundary,
etc.) are added by the host project — see `docs/linting.md` for the
authoring pattern.

## Workflow & Implementation Discipline

- **Frame before solving.** For non-trivial work (new/underdeveloped
  features, major rework, recurrent-headache surfaces, any new UI
  surface): name the problem class, note canonical best practices, check
  existing skills/references, then propose an approach. Naming ≠
  adopting — prototypes legitimately defer best practices; just make the
  skip visible. Full prose: `docs/senior-engineer-posture.md`.
- **Surface uncertainty.** When the task is ambiguous, or you've made a
  silent choice between defensible options (format, scope, default,
  fallback, library), ask before guessing or name the tradeoff
  explicitly in your reply. One clarifying question is much cheaper
  than a confidently wrong implementation; completion-trained models
  default to guessing, so this has to be deliberate.
- **Route before working.** For vague, messy, or multi-step requests
  where the operating mode is unclear, consult `/which-shape` first
  (then `/which-skill` once the shape is known) rather than picking
  skills ad hoc or proceeding unrouted. Tiny obvious edits are exempt.
- **Plan when it pays.** Ambiguous / risky / multi-file: write a short
  plan first. Obvious fixes: just do them. The System-tier chain
  (`/scope-feature` → `/impact-feature` → `/architecture-fit` →
  `/plan-spec`) is for new subsystems or multi-week initiatives.
- **Smallest responsible fix.** Don't broaden scope. Don't extract
  abstractions speculatively (see `.claude/skills/_common/interface-depth.md`).
- **Reproduce bugs first** with a test, log, or traceback. For hard bugs
  without a trusted loop/root cause, use `/diagnose` before fixing. Fix
  the root cause, then prove the failure no longer occurs.
- **Trace all call sites.** Grep every place a changed model / field /
  function is created, read, or defaulted.
- **Verify before done.** Run the narrowest meaningful tests; widen if
  shared. State what wasn't run.
- **Prove the core output path.** For pipeline / extraction / export /
  codegen work, candidate-level success is not enough. Verify a
  representative input through the final executable/output boundary.
- **Capture lessons** in the right surface — five tiers, no overlap:
  - `.claude/docs/precedents.yml` — updateable implementation case law for
    recurring mechanisms with exemplars, guards, exceptions, and supersession.
  - `ai-docs/decisions/` — ADRs for choices that constrain future work
    or exclude alternatives. See `ai-docs/decisions/README.md` for the
    threshold (target 2-5 per quarter). Scaffold with
    `python3 scripts/decisions.py init <slug>`.
  - Project-local `known-issues.md` — current-state operational gotchas.
    Updated in place. (Host project owns this file; not shipped here.)
  - Project-local task diary (`.claude/tasks/lessons.md` is the common
    pattern) — append-only, "rule + why + how to apply".
  - `.claude/skill-use/` — skill-effectiveness telemetry (which skill
    was invoked, on what, outcome, human override). Opt-in per skill;
    gitignored log + archive, summarized lessons digests safe to commit.
    See `.claude/skill-use/README.md` for schema and capture helper.
- **Sweep before ending.** Before closing a strategy/design conversation
  that produced agreed-but-unexecuted items, silent decisions, or
  reusable ideas, sweep the conversation and capture them as ledger
  intakes via `/track-idea`. Capture beats curation — the bar is "would
  future-me wish this were written down?"

Full prose (test-first protocol, service-layer / view-pattern conventions,
testing patterns, post-implementation gut check) lives in
`docs/development-workflow.md`. Read it for ambiguous or multi-file work.

## Code Review

When asked to run a code review, use two independent lanes:

1. Sub-agent (or equivalent) general review of the diff for bugs, pattern
   violations, security, dead code.
2. An independent **adversarial review** for a second opinion.

"Adversarial review" means a locally-grounded review lane unless the user
explicitly asks to involve an external model. Do not interpret it as a
request to send repository diffs or source code to an external LLM.

[Claude-Code-Specific]
If a `/codex:review` (or equivalent local) skill is installed, use it for
the adversarial lane. Otherwise fall back to a fresh-context sub-agent
review and state the limitation.
[/Claude-Code-Specific]

[Codex-Specific]
Codex is already the local review lane — perform the adversarial review
directly with local context/tools. Do not shell out to an external CLI for
this lane unless the user explicitly accepts the external-code-sharing
risk for a specific bounded context pack.
[/Codex-Specific]

[Augment-Specific]
Use Augment's configured external review integration if one exists;
otherwise run a separate no-shared-context local review path and note the
limitation.
[/Augment-Specific]

Fix any issues either lane finds before proceeding.

## Commit Discipline

- One commit per logical unit of work. Check `git diff --stat` before
  committing to avoid unrelated changes.
- **Commit only your own work.** When parallel agents or lanes share a
  working tree, stage by the explicit file list your lane owns — never
  a broad `git add <dir>` — and check the staged set against that list
  before committing. A foreign hunk falsifies the commit message and
  misattributes another lane's work.
- Don't amend, don't push, don't force-push, don't `reset --hard` /
  `clean -f` unless explicitly asked.
- **No "Co-Authored-By" lines** — do not add AI co-author attribution.

## Canonical Patterns

There is a canonical-patterns catalogue at `docs/canonical-patterns.md`.
**Check it before**:

- parsing user input (safe parsers, query-string normalization)
- accessing singleton config objects
- writing exports, image serving, or zip downloads
- adding required gitignored files or atomic file writes
- dispatching background tasks
- writing AI calls (provider routing, sidecar boundary, prompt safety)
- naming an API route
- working in a subsystem with sidecar-boundary lints

The catalogue also lists every active diff-scoped lint and the structural
rules that don't have lints yet.

## Maintenance Workflow

Cleanup uses a five-job loop: **map → suspect → explain → refactor →
guard**, with `/diagnose` beside it for concrete symptoms,
`/plan-skill` as the intake gate for new/revised skills, and
`/check-ecosystem-consistency` after significant skill changes. The full
skill catalogue is in `docs/skill-catalog.md`; the six architectural smells
the SUSPECT skills target are in
`docs/architectural-smells.md`. Skipping MAP or EXPLAIN is fine when the
target is already understood. **Skipping GUARD is a mistake** — it turns
every cleanup into a recurring tax.

## Sub-Agents

- Sub-agents don't inherit your context — keep prompts self-contained and
  include the venv path, project root, platform.
- Use sub-agents for parallel/independent work; not for the immediate
  blocking task.
- Prefer file I/O over giant text returns; write findings under a
  project-local working directory (`.claude/tasks/` is a common location)
  for multi-agent work.

Cross-tool bridging (Codex shelling out to `claude -p`, sandbox
workarounds, model-tier picks) is in `docs/sub-agents.md`. Capability
matrix per tool and the parallel context budgeting policy is in
`docs/cross-tool-agent-governance.md`.

## What NOT to Do

- Don't auto-format templates that embed agent syntax (Django `{% %}`,
  Jinja, Liquid, etc.) — formatters break the tag parser.
- Don't refactor adjacent code unless asked.
- Don't create README / `.md` files unless asked.
- Don't add features, error handling, or abstractions beyond the task.

## Supplementary Documentation

Load on demand. Each row's trigger is the question that should make you
read the file.

| File | Read when… |
|---|---|
| `canonical-patterns.md` | Before touching input parsing, dispatch, exports, AI calls, form inputs, or any surface a lint covers. |
| `architectural-smells.md` | Diagnosing omnibus modules, stringly-typed state, query mutation, layer violation, format-equivalence gaps (parallel writers), product-topology drift, or folder-topology drift. |
| `skill-catalog.md` | Picking a cleanup / audit / IDEAS skill (map / suspect / explain / refactor / guard / decide / meta / ideas). |
| `idea-ledger.md` | Capturing or projecting an idea (proposed / in-flight / stalled / done), updating event history, or wiring composability edges. Tier 1 of the idea-tracking system (`/track-idea`, `/find-orphaned-ideas`, `/brainstorm-ideas`, `/extract-existing-ideas`); pairs with `pattern-library.md` (Tier 2) and ADR 0013. |
| `pattern-library.md` | Looking up or promoting a curated pattern from the ledger (≥1 adoption gate); checking generalizability qualifier graduation (`single-constraint-set` → `validated-across-N` → `broadly-applicable`). Read before `/query-patterns` or before promoting a ledger entry. |
| `query-patterns-inline.md` | Doing a low-friction ad-hoc pattern lookup mid-conversation without invoking the full `/query-patterns` skill — e.g. during `/plan-feature` or `/scope-feature` exploration. |
| `.engineering/docs/todo-tuning.md` | Calibrating `/find-orphaned-ideas --todo` for the host project — path-skip globs (vendor JS, agent worktrees, generated migrations), `min_words` override. Optional; defaults work without it. |
| `review-lane.md` | Customizing the adversarial-gate sub-agent for `/mature-existing-ideas --adversarial`. Default is `general-purpose`; override only when the host project ships a project-specific reviewer. |
| `.engineering/docs/importance-map.md` | Declaring high-value areas for `/find-orphaned-ideas --attention-gap` (ADR 0016). Mixed `path:` + `kind:` locators, tier vocabulary `critical` > `core` > `supporting`. Absent map = mode emits "no importance map declared" and exits clean. |
| `quality-coordination-kernel.md` | Designing a new skill / lint / ADR, evaluating maintenance ROI, or thinking about kernel architecture, the harness layer, or productization across projects. |
| `senior-engineer-posture.md` | Starting non-trivial new/underdeveloped/major-rework feature work, or any new UI surface — frame the problem class and canonical practices before picking an approach. |
| `development-workflow.md` | Multi-step / risky implementation work; want test-first / call-path / service / view / testing prose. |
| `linting.md` | Adding a lint rule, debugging hook failures, or expanding the ruff rule set. |
| `testing.md` | Picking the right test module; full coverage map. |
| `folder-organization.md` | Decomposing a flat folder; placing tests for a new package; proposing a directory package; deciding whether a singleton stays flat; or evaluating whether a small folder should collapse back to siblings. Bidirectional convention — folders earn packaging at ≥3 siblings and lose it below ≥3. |
| `language-support-development.md` | Adding or expanding language support; selecting native parser/compiler/analyzer tooling; changing shared source inventory, provider, artifact-lifecycle, conformance, or batching infrastructure. |
| `installation-and-on-demand-library.md` | Changing installation, the router-only/on-demand-library topology, host `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` integration, delegated task packets, or model/effort role mapping. |
| `sub-agents.md` | Cross-tool agent bridging (Codex ↔ Claude CLI, sandbox, model-tier picks). |
| `cross-tool-agent-governance.md` | Editing `CLAUDE.md` / `AGENTS.md` / `.augment/`, or hardening a rule into an enforceable guardrail. |
| `ai-docs/decisions/0006-folder-organization.md` | The bidirectional folder-packaging convention referenced from `folder-organization.md`. |

## Keeping Docs Current & Cross-Tool Sync

When work changes durable behavior, update the matching `docs/*.md`. Only
update for meaningful, durable changes — not minor internal refactors.

Read `docs/cross-tool-agent-governance.md` before editing agent rules.
When changing `.claude/CLAUDE.md` or `.claude/docs/*.md`, also update:

- `.augment/rules/imported/*.md` (condensed always-apply rules)
- nested `AGENTS.md` if a directory needs Codex-local guidance

If a rule protects correctness, data safety, AI-provider routing,
production writes, or benchmark validity, **add an executable guardrail**
(test / lint / hook) — don't rely on prompt context alone.
