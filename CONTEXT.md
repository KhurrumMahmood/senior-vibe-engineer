# engineering-skills — Domain Glossary

A working ubiquitous-language reference for the **engineering-skills**
ecosystem itself. Lives at the project root so any agent (Claude, Codex,
Augment) can resolve a term without paging through docs. Add an entry
the first time a term causes real confusion; flag the conflict under
**Flagged ambiguities** before collapsing it under **Language**.

This file is lazily maintained — incomplete is fine, wrong is not.

_Shape and ubiquitous-language framing borrowed from
[mattpocock/skills](https://github.com/mattpocock/skills) (`CONTEXT.md`)._

## Language

**Skill**:
A capability under `.claude/skills/<name>/`. Each skill
has a `SKILL.md` (agent-facing definition with frontmatter that declares
tier / job / best_for / not_for), optional `agents/*.md` (scout briefs),
`knowledge/*.md` (reusable rules and false-positive catalogues),
`scripts/*.py` (detection/synthesis logic), and `fixtures/` + `tests/`
(executable checks). Only the three routers are ambient by default; other
skills are reached through exact guide/tool closures in the external library.
_Avoid_: confusing skill with the underlying tool (a skill *uses*
tools); calling sub-agent briefs "skills."

**Skill body vs Knowledge**:
The **body** of a skill (its `SKILL.md` and scripts) owns the reusable contract
and lives in this repo. **Knowledge** files (`knowledge/*.md`) carry
language/framework guidance, project-specific examples, false positives, and
exemplar paths. The separation is a portability seam, not proof that copying
one skill directory is sufficient; the capability matrix and declared
on-demand closure own that claim.
_Avoid_: putting host-project examples in the skill body; putting
ecosystem-wide rules in `knowledge/` where they won't be loaded
generally.

**Job (five-job loop)**:
One of **MAP**, **SUSPECT**, **EXPLAIN**, **REFACTOR**, **GUARD** —
the five-stage maintenance loop the ecosystem orchestrates. Each skill
declares its job in its frontmatter; the catalogue
(`.claude/docs/skill-catalog.md`) groups by job.
_Avoid_: treating jobs as strict ordering — MAP and EXPLAIN can be
skipped when the target is already understood. **GUARD must not be
skipped** — that's the rule that protects against recurring tax.

**Scout**:
A sub-agent dispatched by a skill (typically a SUSPECT or EXPLAIN
skill) to investigate one candidate in parallel with siblings. Scout
output goes to disk (`reports/<skill>/scan-*/scouts/<id>.md`), not back
into the orchestrator's context. The dispatch helpers live at
`.claude/skills/_common/dispatch_scout.sh` and
`.claude/skills/_common/dispatch_scout_cheap.sh`.
_Avoid_: returning scout findings via stdout (they pollute context);
calling unrelated worker sub-agents "scouts".

**Tier (task)**:
Task complexity classification — **Quick** (one-line fix), **Feature**
(1–3 day scope, single workflow), **System** (new subsystem,
cross-subsystem feature, multi-week), **Maintenance** (cleanup loop
work). The System-tier chain is `/scope-feature` → `/impact-feature` →
`/architecture-fit` → `/plan-spec`. The judgment pauses between System
stages are the point — don't collapse them.
_Avoid_: forcing every task through the heaviest tier; using "tier" to
mean LLM model size.

**Canonical pattern**:
A named way to do a recurring thing (input parsing, dispatch, atomic
file writes, AI calls, …). Catalogued in
`.claude/docs/canonical-patterns.md`. Many canonical patterns have a
matching diff-scoped lint rule under `scripts/lint/`.
_Avoid_: documenting patterns inline in skills; treating canonical-
patterns.md as a tutorial (it's a catalogue, terse by design).

**Architectural smell**:
A named anti-pattern that a SUSPECT skill targets. Catalogued in
`.claude/docs/architectural-smells.md`. The current catalogue includes omnibus
modules, stringly-typed state, query mutation, layer violation,
format-equivalence gaps, product-topology drift, frontend primitive bypass,
folder-topology drift, and missing boundaries. Host projects add more.
_Avoid_: using "smell" as a generic complaint — a smell has a SUSPECT
skill, an exemplar, a counter-example, and an enforcement story.

**ADR (Architectural Decision Record)**:
A versioned record under `ai-docs/decisions/NNNN-<slug>.md` capturing
a choice that **constrains future work** or excludes alternatives.
ADRs supersede each other and link to related smells/patterns. Scaffold
with `python3 scripts/decisions.py init <slug>`. Threshold: 2–5 ADRs
per quarter.
_Avoid_: ADRs for trivial choices; treating ADRs as todo items
(superseding is the closure path, not "completion").

**Plan vs Spec**:
A **Plan** lives at `ai-docs/plans/<name>.md`, has a status
(`proposed → scoped → impacted → architected → promoted`), and is the
System-tier judgment-pause artifact. A **Spec** lives at
`ai-docs/specs/<name>.md` and is what `/refactor-subsystem` reads as
input — it pins behavior to preserve, characterization tests, and the
extraction shape. Plans promote into specs once architecturally clean.
_Avoid_: writing the Spec directly when a Plan is the right artifact;
treating Plan / Spec as interchangeable.

**Ledger (canonical findings)**:
The append-only record (`reports/_meta/effectiveness.jsonl` + per-skill
`ledger.md` files where used) that captures one row per skill run.
Defined in ADR 0003. Lets the maintenance loop measure whether running
the same SUSPECT skill against the same area is producing fewer
findings over time.
_Avoid_: editing past entries; using the ledger as a todo list.

**Cross-tool mirror**:
The pattern of having multiple agent tools (Claude Code, Codex,
Augment, Cursor, Gemini) read the same canonical guide. Implementation:
`AGENTS.md`, `.cursor/CURSOR.md`, `.gemini/GEMINI.md` are symlinks to
`.claude/CLAUDE.md`; Augment imports condensed always-apply rules from
`.augment/rules/imported/`. Editing protocol in
`.claude/docs/cross-tool-agent-governance.md`.
_Avoid_: editing the mirrors directly when the source is CLAUDE.md;
copy-pasting CLAUDE.md to a mirror file instead of symlinking.

**Diff-scoped lint**:
A lint that runs only against files changed in the current diff (not
the whole repo). Implemented by `scripts/lint/run.py` reading
`git diff --name-only origin/main...HEAD`. Lets the ruleset grow
without producing a noise wall against legacy code. Existing violations
in untouched files don't block commits.
_Avoid_: running the lint runner without `--changed-from` in CI;
treating diff-scoped as "weaker" — it's the *only* enforcement model
that scales in an AI-grown codebase.

## Relationships

- A **Skill** has a **body** (project-agnostic) and **knowledge**
  (project-local). The body ships in this repo; the knowledge fills in
  per host project.
- A **Skill** declares a **Job** in frontmatter (MAP / SUSPECT /
  EXPLAIN / REFACTOR / GUARD).
- A **SUSPECT skill** targets one or more **Architectural smells** and
  produces a triage report whose entries link to **EXPLAIN skills** or
  **REFACTOR skills**.
- A **REFACTOR skill** reads a **Spec** as input. A **Spec** is
  promoted from a **Plan** via the System-tier chain.
- An **ADR** can supersede another ADR (creating a chain) and may
  declare `related_smell` / `related_pattern` to link it into the
  canonical-patterns / architectural-smells catalogues.
- A **Canonical pattern** can have a **Diff-scoped lint** that enforces
  it. The lint lives under `scripts/lint/` and is wired into
  `.pre-commit-config.yaml` + `.github/workflows/ci.yml`.
- A **Ledger entry** is appended per **Skill run** to
  `reports/_meta/effectiveness.jsonl`; the dashboard
  (`reports/_meta/dashboard.md`) is regenerated from it.

## Flagged ambiguities

### Resolved

- **Skill body vs knowledge** — separation introduced explicitly to make
  skills portable. Body = generic; knowledge = host-project. The
  `_common/portability-roadmap.md` document pins the porting contract.
- **Where host-project ADRs live** — this repository's ADR registry governs the
  toolkit. A host project owns its own `ai-docs/decisions/` registry; installing
  the routers or external library does not silently copy toolkit ADRs into that
  host. `/decide` writes against the project in which it is deliberately run.

### Open

- **Skill effectiveness as a metric** — counting findings-over-time is
  the obvious-but-imperfect signal. Open question: what's the right
  composite that also weights "guard installed" (real closure) vs
  "finding dismissed without a guard" (deferred tax)? Not blocking, but
  the answer will eventually live in
  `quality-coordination-kernel.md`.
