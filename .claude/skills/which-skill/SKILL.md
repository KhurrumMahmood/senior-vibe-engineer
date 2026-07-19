---
name: which-skill
description: Recommend a skill (or "no planning skill applies — proceed directly") for a free-text task description. Reads a bundled metadata-only catalog without loading skill bodies, then emits on-demand guide/tool paths and a bounded fresh-sub-agent handoff. Ambient installation is explicit and optional.
argument-hint: "<task description>"
allowed-tools: Bash, Read
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  An agent (or human) is unsure which skill to invoke for a task.
  Especially valuable at the start of a non-trivial task — the cost of
  wrong tool selection (Quick task funneled into a System-tier
  planning chain) is much higher than the 5 seconds of running
  /which-skill.
not_for: |
  Tasks where the right skill is obvious (single-finding cleanup → use
  /fix-workflow directly; dead-code audit → use /find-dormant). Don't
  pre-invoke /which-skill out of ritual — the matcher costs context
  and adds latency. Skip it when the next move is unambiguous.
language: any
framework: any
---

# /which-skill

You are the **recommender** that ranks the available skills against a
free-text task description. Your output is one of three shapes:

1. A single recommended skill, with rationale (most common case).
2. A short ranked list (top 3) when several skills could apply and the
   user should pick.
3. "No planning skill applies — proceed directly" when the task is
   Quick-tier or no skill scores above the relevance threshold.

You do NOT invoke the recommended skill yourself. Return its on-demand library
paths so the calling agent can read only the selected closure, preferably in a
fresh non-context sub-agent for non-trivial work. Ambient installation is an
explicit user choice, not the default handoff.

## How success is judged

- The recommendation is rendered from the actual matcher output and
  exit code: exit 0 means a skill recommendation, exit 1 means
  `proceed_directly` or `unsupported`, and exit 2 is surfaced as an error.
- The run reads the bundled metadata catalog only; it does not expand skill
  bodies or execute the recommended skill.
- A successful recommendation includes local guide and tool paths for the
  selected skill's exact declared closure, plus an optional pinned `skills`
  CLI command only for users who request ambient installation.
Write toward these gates from Stage 0.

## Core beliefs

1. **Wrong tool selection is the highest-leverage failure mode.**
   Funnelling a 1-line typo fix into `/refactor-subsystem` wastes
   context and builds the wrong artifacts; failing to invoke
   `/find-implicit-state` before fixing one stringly-typed comparison
   ships the same bug six more places. Recommending well matters more
   than executing fast.
2. **The recommender is also a metadata test.** If `/which-skill`
   consistently picks wrong, the `not_for` / `best_for` fields are
   mis-written, not the matcher. Your output is the audit signal —
   surface bad recommendations to the user as evidence the metadata
   needs revision.
3. **Quick is a real recommendation.** "No skill applies — proceed
   directly" is not a failure; it's the right answer for the majority
   of small tasks. The whole point of the `not_for` field is to make
   the recommender say "no" when planning machinery doesn't earn its
   keep.
4. **Read catalog metadata, not bodies.** SKILL.md bodies are long. The
   installed matcher uses its generated `catalog.json`; repository
   development checks ensure it matches the source frontmatter.

## Argument parsing

The required argument is a free-text task description. Optional repeatable
`--language` and `--framework` flags establish the host context explicitly.
Without `--language`, only an exact language name or source suffix in the task
(`TypeScript`, `.ts`, `.tsx`, `JavaScript`, `.js`, `.jsx`, `Python`, `.py`)
may establish one language. Mixed exact markers disable language filtering;
the matcher never guesses from broad terms such as “frontend.”

Examples:

```
/which-skill add per-site export-fingerprint TTL override
/which-skill find dead code in core/services
/which-skill fix typo in_porgress to in_progress in CrawlJob status
/which-skill record decision to use TextChoices for new model
/which-skill audit repeated status literals --language typescript
```

If the argument is empty, abort with usage guidance.

## Pipeline

### Stage 0 — Setup

**Pre:** task description received. **Post:** none — this skill writes
nothing to disk.

This skill produces no artifact or persistent trace. The output is
conversational.

The default router installation also bundles `scripts/bootstrap_library.py`.
Run it once from the host project to materialize the full repository outside
agent discovery:

```bash
PROJECT_ROOT="$PWD"
(
  cd "$PROJECT_ROOT/.agents/skills/which-skill"
  python3 scripts/bootstrap_library.py \
    --project-root "$PROJECT_ROOT" \
    --source "${ENGINEERING_SKILLS_SOURCE:?Set the engineering-skills source}"
)
```

The default root is the project-scoped sibling cache
`<project-parent>/.engineering-skills/<project-name>`, outside both the target
repository and agent discovery. Existing valid libraries are reused; an
existing incomplete destination is never overwritten.

### Stage 1 — Run the matcher

**Pre:** task description received. **Post:** `match.py` output captured.

```bash
PROJECT_ROOT="$PWD"
(
  cd "$PROJECT_ROOT/.agents/skills/which-skill"
  python3 scripts/match.py \
    "${TASK}" --project-root "$PROJECT_ROOT" --json
)
```

The matcher returns JSON with:
- `inferred_tier` (quick | feature | system | maintenance | cross-cutting | null)
- `inferred_job` (plan | map | suspect | explain | refactor | guard | decide | triage | teach | construct | diagnose | meta | null)
- `tier_hints` and `job_hints` — the matched signal words
- `recommendation` — the top-scoring skill name OR `proceed_directly`
- `routing_context` — resolved language/framework values, their explicit or
  exact-marker source, and whether portability filtering was applied
- `excluded_unsupported[]` — otherwise-relevant skills whose declared
  language, framework, or scanner coverage does not support the resolved host
- `recommendation: unsupported` — returned instead of silently substituting a
  weaker skill when the strongest semantic match is ineligible for the host
- `handoff` — the winner plus declared companions, exact local guide and
  bundled/shared tooling paths, availability, and the default fresh
  non-context-sub-agent execution mode
- `optional_install` — pinned stock command for ambient installation of the
  exact closure, used only when the user explicitly requests it
- `task_packet` — the optional task-packet fields (`lanes`, `stage`,
  `entrypoint`, `consumes`, `produces`, `evidence_required`,
  `risk_triggers`, `max_overhead`) declared by the winning skill, or
  `{}` if it declares none. Omitted entirely on the `proceed_directly`
  path.
- `candidates[]` — ranked list with score, tier, job, rationale per
  skill. Each candidate carries its own `task_packet` so a downstream
  orchestrator can inspect the runner-up shapes without re-reading
  SKILL.md.

The `task_packet` is the contract that lets a calling agent route work
without re-reading the SKILL.md — it answers "use this skill, on these
inputs, expecting these outputs, gated on this evidence." See
`_common/skill-frontmatter.md` for the field reference.

Exit code 0 = recommendation found; exit code 1 = no skill applies
(Quick tier or all-below-threshold). Both are valid outcomes — only
exit code 2 is an error.

### Stage 2 — Render the recommendation

**Pre:** matcher output in hand. **Post:** user-facing recommendation
delivered.

Two output shapes:

**Shape A — Skill recommended (matcher exit 0):**

```
Task: <verbatim task>
Inferred: tier=<X>, job=<Y>

Recommended: /<skill-name>
  - <rationale line 1>
  - <rationale line 2>

Other candidates (also scored above threshold):
  /<other-1>  (score=N, <one-line why>)
  /<other-2>  (score=N, <one-line why>)

Next: load the on-demand guide directly for small work, or pass only the task,
project root, task packet, and returned guide/tool paths to a fresh non-context
sub-agent for non-trivial work.
```

**Shape B — Proceed directly (matcher exit 1):**

```
Task: <verbatim task>
Inferred: tier=quick (or no match)

No planning skill applies. Proceed directly.

Optional next steps:
  - /decide if a real choice is being made along the way.
  - <other applicable cross-cutting skill if relevant>
```

Both shapes are deliberately short. The matcher's --json output
contains more detail; show it only if the user asks "why?" — the
default render is the headline plus enough context to act.

### Stage 3 — Stop

Do NOT invoke the recommended skill yourself. The recommendation is
the work. The user (or the calling agent) is responsible for the next
move.

## Non-goals

- Invoking the recommended skill (that's the user's or calling agent's call).
- Installing the recommended skill unless the user explicitly requests it.
- Reading SKILL.md bodies (the matcher reads frontmatter only — that's
  the design).
- Recommending external tools or non-skill commands (this skill knows
  about `.claude/skills/*/SKILL.md` and nothing else).
- Editing `not_for` / `best_for` to "fix" a bad recommendation — that's
  a separate edit task. Surface the mismatch; let the user decide.
- Proposing a new skill ("we need a /thing-X skill") — the matcher
  reports what exists. Net-new skills are a design decision, not a
  match output.

## When things go sideways

| Symptom | Action |
|---|---|
| Empty task description | Abort with usage example |
| `match.py` exits 2 (usage error) | Surface the diagnostic; check `catalog.json` is installed beside the script |
| All skills score 0 | The catalog has no relevant match; proceed directly and surface the top candidates only on request |
| Strongest match is excluded for language/framework | Return `unsupported` with the exact declaration mismatch; do not substitute a weaker skill |
| Recommended skill is one the user just *finished* invoking | Flag it explicitly: "the matcher recommends /<skill>, but you just ran it 5 minutes ago — re-confirm before re-invoking" |
| User pushes back ("/which-skill said /X but /X is wrong here") | Surface it as a metadata mismatch; do NOT silently re-recommend a different skill |
| Recommended skill has `tier: cross-cutting` and the user expected a planning skill | This is normal — `/decide` and `/which-skill` are cross-cutting. Confirm in summary that `/decide` is a *complement* to planning, not a replacement |

## Repository layout

```
.claude/skills/which-skill/
├── SKILL.md                  # this file — orchestrator
├── catalog.json              # generated metadata for all distributable skills
└── scripts/
    └── match.py              # stdlib-only installed matcher
```

No `knowledge/` directory — the matcher's heuristics live in
`scripts/match.py` itself, and the orchestrator's reasoning lives in
this file. There's no scout brief because there's no fan-out.

During repository development, `scripts/build_router_catalog.py --check`
verifies the bundled catalog against all source SKILL.md frontmatter. That
generator may use repository dependencies; the installed matcher does not.

## Future evolution

The matcher is intentionally primitive (token overlap + tier/job
inference). When the registry grows past ~30 skills and patterns of
misapplication emerge, the matcher will likely evolve toward LLM-
assisted matching (call a small model with the task description and
the frontmatter table, ask for a ranked recommendation). The
frontmatter contract is designed to support that — `best_for` and
`not_for` are written as natural-language sentences specifically so a
language-model matcher can read them.

Until then, the heuristic version is more debuggable, faster, and
free.
