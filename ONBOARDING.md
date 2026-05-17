# Onboarding

Welcome to **engineering-skills** — a portable senior-engineer skill
ecosystem for AI coding agents. This is the front-desk guide for humans
new to the codebase. It's a *pointer file*: almost everything you
actually need is in some other doc, and this is the layer that tells you
which one and when. **Spend day 1 reading the things this points at, not
this file.**

If something here feels stale, fix the link target — not this doc.
Otherwise this grows into a wiki and the wiki rots.

---

## 1. What this repo is

A self-contained ecosystem of **skills** (60 of them), supporting
**docs**, **scripts**, and **ADR/plan/spec scaffolding** that AI coding
agents (Claude Code, Codex, Augment, Cursor, Gemini) use to behave like
senior engineers inside a host project.

It exists because completion-trained coding agents default to "got it
done" — patches that work locally but erode system health. This
ecosystem replaces that default with a deliberate posture: **frame the
problem class, refactor with a spec, author ADRs for material decisions,
and convert one-off discoveries into durable guardrails**.

It was extracted from a real Django production codebase, then
generalized. Some lint rules and skill examples still carry Django/Python
flavor; the design has always anticipated cross-language adapters
(TypeScript, Rust). See
[`.claude/skills/_common/portability-roadmap.md`](.claude/skills/_common/portability-roadmap.md).

---

## 2. The three principles the ecosystem is built on

**Hidden structure becomes explicit structure.** The mantra from
[`.claude/docs/skill-catalog.md`](.claude/docs/skill-catalog.md): an
AI-grown codebase needs continuous conversion of hidden structure
(informal patterns, tribal knowledge) into explicit structure (skills,
lints, ADRs). When you find a smell, the move is to *name it* — file a
lint, write an ADR, codify a skill — not just patch it locally. The
patch helps once. The name helps forever.

**AI is held to the same posture you are.** The skills bind agents to
[`.claude/docs/senior-engineer-posture.md`](.claude/docs/senior-engineer-posture.md):
frame the problem class before solving, surface uncertainty, smallest
responsible fix, reproduce bugs first, capture lessons. **You operate
under the same posture.** That doc is short — read it.

**Five-job maintenance loop, never skipping GUARD.** Cleanup goes
**map → suspect → explain → refactor → guard**. The catalogue is in
[`.claude/docs/skill-catalog.md`](.claude/docs/skill-catalog.md). You can
skip MAP and EXPLAIN when the target is already understood. **Skipping
GUARD** — declining to install a lint or characterization test after a
cleanup — turns every refactor into a recurring tax. That is the most
important rule in the ecosystem.

---

## 3. Getting yourself running

```bash
git clone <this-repo>
cd engineering-skills
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pre-commit install
```

**Use `.venv/bin/python`, not bare `python`.** Sub-agents don't inherit
shell activation, so include the venv path in every prompt you hand off.

Most skills are designed to run inside a host project's repo (the skills
read its code, write reports under `reports/`, propose ADRs under
`ai-docs/`). If you're working on the ecosystem itself, the scripts and
lints in `scripts/` are still runnable directly:

```bash
.venv/bin/python scripts/decisions.py list
.venv/bin/python scripts/lint/run.py --rule silent-catch
.venv/bin/python scripts/skill_meta.py show find-duplication
```

---

## 4. Learning a skill or doc quickly

When you land in unfamiliar territory, this is the recipe — the same one
the AI agents use:

1. **Find the anchor doc.** Open
   [`.claude/CLAUDE.md`](.claude/CLAUDE.md), find the *Supplementary
   Documentation* table near the bottom. The "Read when…" column is the
   table of contents for the whole ecosystem — match it to what you're
   about to do, then read that file.
2. **Open the skill itself.** Each skill is a directory under
   `.claude/skills/<name>/`. `SKILL.md` is the agent-facing definition
   (read this first); `agents/` holds scout briefs; `knowledge/` holds
   reusable rules and false-positive catalogues; `scripts/` holds the
   detection/synthesis logic; `fixtures/` and `tests/` exercise it.
3. **Read the canonical-patterns and architectural-smells docs.**
   [`canonical-patterns.md`](.claude/docs/canonical-patterns.md) catalogues
   what the ecosystem considers "the right way" to do things;
   [`architectural-smells.md`](.claude/docs/architectural-smells.md)
   catalogues what it considers "the wrong way." Most skills target a
   named smell and uphold a named pattern.
4. **For the bigger picture**, read
   [`quality-coordination-kernel.md`](.claude/docs/quality-coordination-kernel.md).
   That's the architecture of the ecosystem itself: how skills compose,
   how ADRs supersede each other, how the harness layer separates from
   the kernel.

Shortcut to the most-touched docs:

- Skill picker →
  [`.claude/docs/skill-catalog.md`](.claude/docs/skill-catalog.md)
- The smells skills target →
  [`.claude/docs/architectural-smells.md`](.claude/docs/architectural-smells.md)
- Canonical patterns and the lint catalogue →
  [`.claude/docs/canonical-patterns.md`](.claude/docs/canonical-patterns.md)
- Senior-engineer posture →
  [`.claude/docs/senior-engineer-posture.md`](.claude/docs/senior-engineer-posture.md)
- Cross-tool agent governance (when editing CLAUDE.md, AGENTS.md, etc.) →
  [`.claude/docs/cross-tool-agent-governance.md`](.claude/docs/cross-tool-agent-governance.md)
- ADR template + threshold →
  [`ai-docs/decisions/README.md`](ai-docs/decisions/README.md)

---

## 5. The seven things that bite first

Roughly in order of how often they catch new contributors:

1. **`.venv/bin/python`, always.** Bare `python` is missing dependencies.
   Sub-agents *especially* need the venv path made explicit.
2. **Don't auto-format templates that embed agent syntax.** Prettier and
   friends mangle Django `{% %}`, Jinja, and similar tags.
3. **Match test scope to change shape.**
   [`.claude/CLAUDE.md`](.claude/CLAUDE.md) "Verification Policy" tells
   you what to run for each kind of change. Don't run the full ladder
   for a typo. Don't skip it on shared-surface code.
4. **Frame before solving on non-trivial work.** Read
   [`.claude/docs/senior-engineer-posture.md`](.claude/docs/senior-engineer-posture.md).
   Naming the problem class up front is much cheaper than discovering
   you picked the wrong shape after coding for an hour.
5. **Reproduce bugs first.** Write the failing test (or capture the
   exact traceback) *before* the fix. Same for "this is just a refactor,
   no behavior change" — characterize it before you change it.
6. **Commit discipline.** One commit per logical unit. Check
   `git diff --stat` before staging — unrelated changes have a way of
   sneaking in. Don't `--amend`, don't push, don't `--no-verify` unless
   someone explicitly asked. **No `Co-Authored-By` lines, even from AI
   tools.**
7. **Don't create README/`.md` files unless asked.** New docs without a
   registered trigger become dormant clutter. If you really need one,
   register it in [`.claude/CLAUDE.md`](.claude/CLAUDE.md)'s
   Supplementary Documentation table or add a row to this file.

---

## 6. Where to write things down

The ecosystem has three durable capture surfaces. Pick the right one and
the next reader will find your work; pick the wrong one and it rots.

| Where | What goes here | When |
|---|---|---|
| [`.claude/docs/precedents.yml`](.claude/docs/precedents.yml) | Implementation case law — recurring mechanisms with exemplar, guard, exceptions, supersession. | Whenever a non-obvious pattern recurs across 2–3 spots. |
| [`ai-docs/decisions/`](ai-docs/decisions/) | ADRs — choices that constrain future work or exclude alternatives. Scaffold with `python3 scripts/decisions.py init <slug>`. | 2–5 per quarter. |
| Host-project task diary (`.claude/tasks/lessons.md` is the common location) | Non-obvious fixes, written as **rule + why + how to apply**. Append-only. | Whenever a non-obvious fix lands. (Lives in the host project, not here.) |

The three tiers don't overlap. The split is in
[`.claude/CLAUDE.md`](.claude/CLAUDE.md) "Workflow & Implementation
Discipline" — read it the first time you're not sure which one a thing
belongs in.

---

## 7. The doc map

```
tier 1 — root (human entry surface)
  README.md                    quick start, layout, where to read next
  ONBOARDING.md                this file
  CONTEXT.md                   domain glossary for the ecosystem itself

tier 2 — agent operating manual + reference
  .claude/CLAUDE.md            lean operating manual + trigger table
  .claude/docs/*.md            reference docs, demand-loaded by trigger
  .claude/skills/              the 60 skills

tier 3 — formal artifacts
  ai-docs/decisions/           ADRs (case law)
  ai-docs/specs/               behavior-preserving refactor specs
  ai-docs/plans/               System-tier plans (scope → impact → architect → spec)
  reports/_meta/               skill effectiveness log + dashboard

tier 4 — cross-tool mirrors (don't edit unless you're syncing)
  AGENTS.md                    symlink → .claude/CLAUDE.md (Codex)
  .cursor/CURSOR.md            symlink → .claude/CLAUDE.md (Cursor)
  .gemini/GEMINI.md            symlink → .claude/CLAUDE.md (Gemini)
  .augment/rules/imported/     Augment always-apply rules
  .codex/config.toml           Codex agent-policy hooks
```

**Navigation tip:** the trigger column in
[`.claude/CLAUDE.md`](.claude/CLAUDE.md)'s Supplementary Documentation
table is your TOC. Read down it; the question that matches what you're
about to do is the doc you should open next.

---

## 8. Keeping this doc fresh

The links in this file are checked by
[`.claude/skills/find-rule-surface-drift/`](.claude/skills/find-rule-surface-drift/).
A broken link fires a `missing_link` finding. A doc registered in
CLAUDE.md but not linked here fires an info-level
`dormant_in_onboarding` finding so the curator can decide whether it
belongs.

When you change [`README.md`](README.md), [`/CONTEXT.md`](CONTEXT.md), or
the Supplementary Documentation table in
[`.claude/CLAUDE.md`](.claude/CLAUDE.md) in a way that **renames or
moves a section**, update the matching pointer here too. The trigger
sentence is in [`.claude/CLAUDE.md`](.claude/CLAUDE.md) under "Keeping
Docs Current & Cross-Tool Sync."

This file isn't mirrored to `.augment/` or `AGENTS.md` — it's read once,
by a human, in days 1–7. The agents have their own entry point
(CLAUDE.md). Different audiences, different doors, same building.
