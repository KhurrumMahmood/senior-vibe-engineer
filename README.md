# engineering-skills

A **senior-engineer skill ecosystem** for AI coding agents: skills that find
architectural debt, refactor systematically, author ADRs, and turn one-off
discoveries into durable guardrails. Extracted from a real production codebase.
**Today it is Python/Django-flavored** — the lint substrate and most worked
examples are Django — with a *roadmap* toward language-neutral reuse, not yet a
proven-portable core (see [Tech assumptions](#tech-assumptions)).

**Where it's headed:** [`VISION.md`](./VISION.md) states the end-state this
ecosystem converges a project toward — the success criterion the skills serve.

This README is the **human entrypoint**. AI agents (Claude Code, Codex,
Augment, Cursor, Gemini) should start at
[`AGENTS.md`](./AGENTS.md) → [`.claude/CLAUDE.md`](./.claude/CLAUDE.md).

**Where to start:** `/engineer-init` for first-time setup (venv, deps,
hooks); `/which-shape` for routing whenever you're unsure what kind of
work to run.

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
  skills. Nine starter ADRs are highlighted below; the full live registry is
  under `ai-docs/decisions/`. Entries marked *(proposed)* are calibrated
  starting points an adopting project confirms or supersedes:
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
# Install deps and pre-commit hooks — or run /engineer-init to do all this
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pre-commit install   # requires a git repo; skip if unversioned

# Try a skill (under Claude Code; Codex/Augment vary)
/which-shape "this inherited project feels messy and slow"
/which-skill "I need to clean up duplicated workflow modules"
/find-duplication app/services
/triage-debt
```

To run the complete repository suite, including the Playwright renderer smoke,
install the optional browser prerequisite explicitly:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium --only-shell
.venv/bin/python -m pytest
```

Skills are designed to be invoked by AI coding agents inside a host
project's repo. The host project drops `.claude/`, `scripts/`, and
`ai-docs/` into its root (or symlinks them) and the skills become
available to the agent.

## Before the skills work — two gotchas

Claude Code auto-discovers `.claude/skills/` and lists every skill as a
slash command, so the skills *look* ready before they actually are. Two
things commonly block them:

1. **The runtime isn't installed.** Most skills shell out to helper
   scripts under `scripts/` (`decisions.py`, `ledger.py`, the lint
   runner, …) that need `PyYAML` from `requirements.txt`. Until the venv
   exists the slash command is listed but errors on its first script
   call. Run the Quick start install block — or `/engineer-init` —
   first. Prompt-only skills (`/gut-check`, `/which-skill`) work without
   it; the script-backed majority do not.

2. **The skills must run from a host project root.** Skill scripts use
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
- **The lint substrate and worked examples are Django/Python — not just
  illustration.** The AST lint rules (`no_query_mutation`, `no_bare_delay`, …)
  are Django/Celery detectors, and the patterns' only proven instances are
  Django. `.claude/skills/_common/portability-roadmap.md` holds the cross-language
  porting contract. A shared JavaScript/TypeScript heuristic adapter now extracts
  top-level symbols and powers `/find-omnibus`, but it misses common ESM exports
  and the deeper semantic detectors remain Python-specific. No non-Django host
  portfolio has passed end-to-end installation and conformance yet, so
  "portable" is a partially embodied roadmap, not a verified product claim.

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
