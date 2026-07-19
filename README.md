# engineering-skills

A **senior-engineer skill ecosystem** for AI coding agents: skills that find
architectural debt, refactor systematically, author ADRs, and turn one-off
discoveries into durable guardrails. Extracted from a real production codebase.
**Its origin and shared runtime remain Python/Django-flavored** — the lint
substrate and most worked examples are Django. TypeScript is the one validated
non-Django host language today: the current coverage matrix records 22
TypeScript-supported skills, 19 validated-neutral skills, 22 deliberately
stack-bound skills, and 13 ecosystem-runtime skills. Other host languages,
including Rust, are not yet proven (see [Tech assumptions](#tech-assumptions)).

**Where it's headed:** [`VISION.md`](./VISION.md) states the end-state this
ecosystem converges a project toward — the success criterion the skills serve.

This README is the **human entrypoint**. AI agents (Claude Code, Codex,
Augment, Cursor, Gemini) should start at
[`AGENTS.md`](./AGENTS.md) → [`.claude/CLAUDE.md`](./.claude/CLAUDE.md).

**Where to start:** install the three lightweight routers, then let
`which-skill` install only the skill selected for the task. Repository
contributors use `/engineer-init` for the development venv and hooks.

## What's in the box

- **`.claude/skills/`** — 76 skills covering diagnosis, construction,
  and five jobs in the maintenance loop:
  - **DIAGNOSE** (`diagnose`) — turn concrete symptoms, regressions,
    flakes, and unclear failures into a reproduction loop, root cause,
    verification, and prevention follow-up.
  - **CONSTRUCT** (`plan-skill` now; future constructive pattern writers) —
    make write-time patterns explicit before drift exists, starting with
    adversarial skill planning and dogfood gates.
  - **PROJECT STRUCTURE** (`organize-project-structure`) — redesign repo
    information architecture under framework/tool/human constraints, then
    hand deterministic move batches to `move-path` when the target topology is
    clear.
  - **MAP** (`map-subsystem`, `map-product-workflow`) — durable inventory
    docs for a subsystem or user-visible workflow.
  - **SUSPECT** (`find-duplication`, `find-dormant`, `find-omnibus`,
    `find-semantic-duplication`, `find-implicit-state`, `find-layer-violation`,
    `find-query-mutation`, `find-transaction-overreach`, `find-comment-drift`,
    `find-*-drift` family, `find-stale-artifacts`, `find-folder-topology-drift`,
    `find-rule-surface-drift`, `find-test-obligation-drift`,
    `find-standard-gaps`, …) — advisory scans that produce ranked,
    evidence-backed candidate lists.
  - **EXPLAIN** (`explain-code`, `teach-pattern`, `extract-cotton-primitive`,
    `extract-enum`, `extract-state-type`, `extract-workflow-registry`,
    `introduce-fk`, `unify-shadows`, `propose-folder-reorganization`) —
    read-only proposals that turn a SUSPECT finding into an
    implementation-ready brief.
  - **REFACTOR** (`refactor-subsystem`, `fix-workflow`, `move-path`) — execute the
    cleanup with a strict spec-first protocol and characterization tests.
  - **GUARD** (`prevent-regression`) — turn a closed cleanup into a
    lint / test guardrail so the problem can't come back.
  - Plus governance skills: `decide`, `audit-decisions`,
    `which-shape`, `check-ecosystem-consistency`, `project-interview`,
    `adapt-project`, `scope-feature` /
    `impact-feature` / `architecture-fit` / `plan-spec` (System-tier
    planning chain), `organize-project-structure`, `design-it-twice`,
    `plan-skill`, `which-skill`, `triage-debt`.
- **`.claude/docs/`** — the doctrine the skills enforce:
  `canonical-patterns.md`, `architectural-smells.md`, `skill-catalog.md`,
  `quality-coordination-kernel.md`, `senior-engineer-posture.md`,
  `development-workflow.md`, `cross-tool-agent-governance.md`,
  `folder-organization.md`, `linting.md`, `testing.md`, `sub-agents.md`,
  and `precedents.yml`.
- **`scripts/`** — the runtime that backs the skills:
  `decisions.py`, `plans.py`, `specs.py`, `ledger.py`, `precedents.py`,
  `skill_meta.py`, `skill_effectiveness.py`, `evidence_gate.py`,
  `project_adapt.py`, `duplication_audit.py`, `semantic_inventory.py`,
  `subsystems.py`, `query_planner.py`, plus a `lint/` runner and the diff-scoped AST rules
  (`silent_catch`, `no_query_mutation`, `no_stringly_typed_status`,
  `no_fat_view`, `no_bare_delay`, `no_comment_drift`,
  `codegen_emits_new_paths`, `run_jscpd`).
- **`ai-docs/`** — the ADR / plan / spec workflow that pairs with the
  skills. Nine ADRs ship as the foundation; the ones marked *(proposed)*
  are calibrated starting points an adopting project confirms or
  supersedes:
  - `0001-textchoices-for-state` — string state fields → typed enums.
  - `0002-spec-first-refactor` — refactors author a spec before code.
  - `0003-canonical-findings-ledger` *(proposed)* — findings get an ID
    and a row in a ledger; refactors close ledger rows.
  - `0004-parallel-writers-shared-helper` — when two writers diverge on
    the same shape, factor a shared helper rather than racing the format.
  - `0005-agent-rules-design` — how this very file (`CLAUDE.md`) is
    architected: lean root + load-on-demand docs + cross-tool mirrors.
  - `0006-folder-organization` *(proposed)* — bidirectional
    folder-packaging convention; ≥3 siblings earn packaging, < 3
    collapse back.
  - `0013-idea-tracking-system` — two-tier idea tracking: a ledger for
    raw ideas, a curated pattern library for the ones that prove out.
  - `0016-importance-map-shape` *(proposed)* — a declarative importance
    map so debt scans can weight findings by where they land.
  - `0017-staged-boundary-rearchitecting` *(proposed)* — when to extract
    a module boundary, when to phase it, when to refuse phasing.
- **`.augment/`, `.codex/`, `.cursor/`, `.gemini/`** — cross-tool agent
  rules that all point back at the same canonical guide (symlinks where
  the host filesystem supports them). See
  `docs/cross-tool-agent-governance.md` for the editing protocol.
- **`.github/workflows/ci.yml`** — diff-scoped lint pipeline for CI.
- **`.pre-commit-config.yaml`** — the same lints wired up locally.

## Quick start

```bash
# From the host project. The command installs only the three routers.
ENGINEERING_SKILLS_SOURCE=https://github.com/KhurrumMahmood/senior-vibe-engineer # host-ref-allow: public distribution repository
DO_NOT_TRACK=1 npx --yes skills@1.5.19 add \
  "$ENGINEERING_SKILLS_SOURCE" \
  --skill which-shape --skill which-skill --skill which-cleanup \
  --agent codex --copy -y
```

Ask the agent to use `which-shape` when the operating mode is unclear,
`which-skill` for the tactical choice, and `which-cleanup` after changes are
made. The three routers run with system Python and do not load the other 73
skill bodies. Their results point to the relevant skill definition and tooling
at the canonical source and include pinned `skills@1.5.19` commands for
installing only the selected follow-up skills.

To remove all skills installed for the project:

```bash
DO_NOT_TRACK=1 npx --yes skills@1.5.19 remove --all
```

The stock CLI owns the installed skill directories and `skills-lock.json`.
Move local edits out of an installed skill directory before replacing or
removing it. Files elsewhere in the host project are outside that boundary.

For repository development, clone this repo and run `/engineer-init`, or:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pre-commit install
```

## Runtime-backed skills

The routers and prompt-only skills are self-contained. Many older
script-backed skills still depend on repository-level helpers and PyYAML; they
are not yet claimed as independently installable. TypeScript support is tracked
per skill, and further cross-language work proceeds one cohesive family at a
time.

1. **The development runtime isn't installed.** Most skills shell out to helper
   scripts under `scripts/` (`decisions.py`, `ledger.py`, the lint
   runner, …) that need `PyYAML` from `requirements.txt`. Until the venv
   exists the slash command is listed but errors on its first script
   call. Run the repository-development block above — or `/engineer-init` —
   when developing the full checkout. Prompt-only skills and the three routers
   do not require it.

2. **Older script-backed skills must run from a full checkout.** Their scripts use
   paths relative to the repo root — `scripts/decisions.py`,
   `ai-docs/decisions/`, `reports/`. Run from a parent or staging
   directory, those paths don't resolve and there is no codebase to act
   on. Set the working directory to a project root that has `.claude/`,
   `scripts/`, and `ai-docs/` — either this repo itself, or a host
   project those folders were copied or symlinked into.

## Layout

```
.claude/
  CLAUDE.md                 # lean root guide for all agents
  docs/                     # doctrine: canonical patterns, smells, catalogue
  skills/                   # 76 skills, each a self-contained dir
    _common/                # shared scout-dispatch, scripts, posture docs
    <skill-name>/SKILL.md   # the agent-facing skill definition
ai-docs/
  decisions/                # ADRs (ecosystem ships a starter set; project adds more)
  plans/                    # System-tier planning docs (scope→impact→architect→spec)
  specs/                    # refactor specs (refactor-subsystem reads these)
scripts/
  _lib/                     # shared frontmatter parser
  agent_policy/             # cross-tool agent permission hooks
  lint/                     # AST lint runner + the diff-scoped rules
  decisions.py plans.py specs.py ledger.py …
reports/
  _meta/                    # effectiveness log + dashboard (tracked)
  …                         # per-skill scan outputs (gitignored)
.augment/  .codex/  .cursor/  .gemini/    # cross-tool agent mirrors
```

## Tech assumptions

- **Python 3.11+** for the script runtime and lint rules.
- **stdlib-first** in `_common/` so skills can run before a project venv
  exists; PyYAML is the only required external dep (for shared
  frontmatter parsing, pinned in `requirements.txt`).
- **The legacy lint substrate and most worked examples are Django/Python — not
  just illustration.** Rules such as `no_query_mutation` and `no_bare_delay`
  remain Django/Celery-specific. TypeScript coverage is separately proven and
  tracked in `.claude/tasks/typescript-skill-coverage.json`: 22 skills are
  TypeScript-supported, 19 are validated-neutral, 22 are deliberately
  stack-bound, and 13 are ecosystem-runtime. That evidence does not establish
  support for Rust or any other host language.

## Where to read next

- **AI agents** → [`AGENTS.md`](./AGENTS.md) (symlink to
  [`.claude/CLAUDE.md`](./.claude/CLAUDE.md)).
- **Skill picker** →
  [`.claude/docs/skill-catalog.md`](./.claude/docs/skill-catalog.md).
- **Why these skills exist (and the smells they target)** →
  [`.claude/docs/architectural-smells.md`](./.claude/docs/architectural-smells.md)
  and
  [`.claude/docs/quality-coordination-kernel.md`](./.claude/docs/quality-coordination-kernel.md).
- **Decisions** → [`ai-docs/decisions/`](./ai-docs/decisions/).
- **Day-1 onboarding** → [`ONBOARDING.md`](./ONBOARDING.md).
