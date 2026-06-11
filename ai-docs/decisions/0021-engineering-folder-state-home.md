---
id: "0021"
namespace: core
title: Portable .engineering/ state home
status: accepted
date: 2026-05-22
deciders: [khurrum]
supersedes: []
superseded_by: null
revisit_when:
  - "the first skill resolves its file universe through the ignore-first scope loader (the first real consumer) — build the skill-level `## Allow` re-inclusion per the locked precedence rule at that moment"
  - "a scope-driven skill needs to re-include a path the project floor denied (e.g. a reports-scanner contradicting a repo-wide ignore) — implement `## Allow` and its precedence tests"
applies_to: [".claude/skills/find-standard-gaps/scripts/project_state.py", ".claude/skills/find-standard-gaps/scripts/scan_coverage.py", ".claude/skills/orient/", ".engineering/project-state.json"]
tags: [state, portable, cross-tool, engineering-folder, project-state, committed-vs-gitignored, schema-versioning, migration, derived-knowledge, per-skill-scope, ignore-first]
related_smell: null
related_pattern: null
---

# Portable .engineering/ state home

## Context

The toolkit is a portable, cross-tool (Claude Code / Codex / Augment) meta-repo of
code-quality skills, meant to drop into *any* consuming project. As of ADR 0020 it also
keeps **per-project state** — declared maturity × stakes lives in `.project-state.json`
at the repo root, read by `project_state.py`, consumed by `scan_coverage.py`, written by
`/orient`. More state is already arriving: convention / capability descriptors (which
directory holds a project's reusable component templates — a component scanner's
hardcoded template path is the trigger), accepted-gate / enforcement decisions and frozen
detectors (ADR 0022), and curated reports worth keeping for future work.

Two problems with the status quo:

- **No neutral home.** State is starting to scatter — `.project-state.json` at root, scans
  under `reports/`, skills + idea-ledger under `.claude/`. But `.claude/` is
  *Claude-specific*; Codex reads `AGENTS.md`, Augment reads `.augment/`. Per-project
  *state* shared by three agents must not live under one agent's folder. Instructions
  already mirror across `CLAUDE.md` / `AGENTS.md` / `.augment/`; state has no such neutral
  seam yet.
- **No commit/ignore discipline.** Some state is durable team knowledge that belongs in
  git (declared maturity, accepted gates, a curated finding). Some is per-run scratch that
  must *not* be committed (scan working files, caches, synthesis intermediates). Today
  every new state file forces an ad-hoc `.gitignore` decision, one at a time.

There is also a related **per-skill scope** problem that lands on the same state home. A
skill needs to answer "which files does *this* skill apply to in *this* repo?" — and that
answer is host-authored *data*, not toolkit code. Without a neutral, declarative seam, each
skill bakes a hardcoded scan path into its own definition (an argument default like
"defaults to the primary source dir", or prose "defaulting to that dir"), so every adopter
with a different layout must fork skill internals and the toolkit ships assumptions about a
host's folder structure it cannot know. The `.engineering/` home gives scope descriptors a
place to live, so scope is *one consumer* of this home rather than a separate decision.

The design is also explicitly **emergent** — new kinds of state keep surfacing as we hit
needs we hadn't anticipated. So this ADR fixes the *container, the zones, and the rules*,
not an exhaustive file list.

## Decision

Introduce **`.engineering/`** at the consuming project's root as the toolkit's
agent-neutral, per-project state home — the *state* analog of the cross-tool instruction
mirror (`CLAUDE.md` / `AGENTS.md` / `.augment/`). All three agents read and write it. Model
it on `.vscode/` and `.github/`: a namespaced dotfolder that is partly committed, partly
local.

**Two zones, split by commit policy:**

1. **Committed zone** (tracked, top level of `.engineering/`) — durable, shared, team-level
   state that should travel with the repo and survive clones, analogous to a checked-in
   `.vscode/settings.json`:
   - project-state (maturity × stakes — ADR 0020);
   - convention / capability descriptors (the component-template root, the template/js
     roots — what ADR 0022's curated detectors parameterize against);
   - accepted-gate / enforcement decisions and frozen generated detectors (ADR 0022);
   - **curated reports that inform future work** — kept findings, not every raw scan.

2. **Gitignored zone** (a reserved subdirectory, e.g. `.engineering/local/`) — ephemeral,
   machine-local, per-run process state that must not be committed:
   - scan working files and intermediate stage outputs;
   - caches, synthesis scratch, detector candidate drafts before acceptance;
   - run-local effectiveness logs that don't need to travel.
   The toolkit **ships the ignore rule** (a `.gitignore` inside `.engineering/` that ignores
   the local subdir and nothing else), so adoption is automatic — a consuming project
   doesn't have to author it.

The seam is **commit policy**, not data type: "would a teammate cloning this repo need it /
should review touch it?" → committed; "is it scratch from one run on one machine?" →
gitignored.

**Versioned schema.** `.engineering/` carries a schema `version:` (a small manifest, e.g.
`.engineering/manifest.json` holding `{"version": N}`) so the layout can evolve across
toolkit releases with an explicit migration path rather than silent breakage. Readers check
the version; a mismatch triggers a documented migration, not a crash.

**Migration (first inhabitant).** `.project-state.json` moves from repo root into
`.engineering/` (committed zone). Three call sites move with it: `project_state.py` (the
loader), `scan_coverage.py` (the consumer), `/orient` (the writer). The loader keeps a
**root-location fallback** during the transition (read `.engineering/…` first, fall back to
`./.project-state.json`, warn once) so an un-migrated clone still works. A resolver locates
`.engineering/docs/` and emits a one-time warning when it finds the legacy `.claude/docs/`
location, so host-config docs (`todo-tuning.md`, `importance-map.md`) move into
`.engineering/docs/` under the same transitional discipline.

### Per-skill scope (additional dimension on the same state home)

On top of the container/zones decision, the committed zone hosts a **per-skill scope
mechanism** so adopters tune a skill's reach via descriptors instead of editing toolkit
code. A scope loader reads two declarative, host-authored files from the committed zone and
resolves them into the set of paths a skill applies to.

**1. Two levels, both ignore-first (shipped, accepted as-is).**

- **Project level** — a repo-wide `ignore.md` (e.g. `.engineering/docs/ignore.md`), loaded
  by a repo-ignore loader (`load_repo_ignore()`), and subtracted from *every* scope-driven
  skill's universe. It accepts a `## Ignore` section only; a repo-wide `## Roots` (a global
  *narrowing*) is nonsensical and is discarded with a one-time stderr warning.
- **Skill level** — a per-skill descriptor (e.g. `.engineering/docs/<skill>-scope.md`),
  loaded by a scope loader (`load_scope()`), with `## Ignore` (subtract) and an optional
  `## Roots` / `## Scan` (narrow).

The default universe is the whole repo, minus a builtin walk-prune (`BUILTIN_SKIP_DIRS` /
`BUILTIN_SKIP_PREFIXES`), minus project ignore, minus skill ignore, narrowed to `## Roots`
when present. A host says what to leave **out**; `## Roots` is the optional narrowing knob,
not the primary one. The mechanism ships **zero assumptions** about any host's folder
layout: scope is data, not code.

**2. Re-inclusion is a skill-level `## Allow` section (decided; implementation deferred).**

Today every layer only ever *subtracts*: a skill cannot re-include a path the project floor
denied, and `## Roots` narrows but cannot rescue an ignored path. The chosen extension is a
dedicated skill-level `## Allow` section whose globs re-include paths against both project
and skill `## Ignore`.

- **Encoding: a named `## Allow` section — NOT literal `+` / `-` bullets.** The parser's
  bullet tokenizer strips a leading `-`, `*`, **or `+`** as a markdown bullet marker, so
  `+ path` / `- path` both parse to the bare path and the sign is lost. A named section
  reuses the existing `## `-heading machinery, keeps bullets as plain markdown, and is
  orthogonal to `## Roots` (narrow) and `## Ignore` (subtract). Patterns are repo-relative
  POSIX with no leading-`/` anchor (e.g. `reports/keep`, not `/reports/keep`).
- **Project level stays deny-only.** Re-inclusion is inherently a specific-case concern;
  there is no `## Allow` at the project level (same rationale as discarding repo-wide
  `## Roots`).
- **Precedence (locked):** a path is in scope iff it is not builtin-pruned AND ( matches
  skill `## Allow` OR ( (`## Roots` unset OR matched) AND not matched by any `## Ignore` ) ).
  In words: **skill `## Allow` > skill `## Roots` > skill `## Ignore` > project ignore >
  builtin skip dirs.** `## Allow` re-includes against project and skill ignores and
  satisfies the `## Roots` gate, but **cannot pierce the builtin walk-prune** — those
  entries are pruned during the directory walk so `## Allow` never sees them, mirroring
  gitignore's "can't re-include a file whose parent dir is excluded."

The two-level resolution (project ignore + skill descriptor + `## Roots`/`## Ignore`) is
**shipped and accepted as-is**. The `## Allow` re-inclusion is **decided but not yet built**:
its encoding and precedence are locked here so the first skill that needs re-inclusion
implements against a settled contract, and the build is gated behind the `revisit_when`
trigger (the first real scope-universe consumer) rather than asserted to exist.

**Open question — merge conflicts on derived-knowledge files (flagged, not decided here).**
Committed-zone files capture *knowledge about the project* — they are **derived fields**, not
hand-authored code. When two branches both update one (each appends a discovered convention;
each bumps project-state differently; concurrent appends to an append-only log), git's
line-based merge is the wrong resolution model: it can silently drop a discovered convention
or mis-merge a declaration. This likely needs **per-kind merge strategies** (union-by-id for
append logs, set-union for decision / convention lists, semantic reconcile + escalation for
scalar declarations), plausibly via git custom merge drivers scoped to `.engineering/**`,
with an LLM-assisted or human reconciliation path for irreducible *knowledge* conflicts.
Captured as a ledger intake for maturing; deliberately **not** decided in this ADR.

## Alternatives considered

- **Keep state under `.claude/`.** Rejected: `.claude/` is one agent's folder; the toolkit
  is tri-agent (Claude / Codex / Augment). Shared state under a single agent's namespace is
  a category error — the same reason instructions are mirrored, not housed once under
  `.claude/`.
- **Scatter at repo root** (`.project-state.json` plus future siblings). Rejected: pollutes
  the root, no namespacing, and every new state kind is a fresh root-level file with its own
  ad-hoc ignore decision.
- **One committed folder, no gitignored zone.** Rejected: conflates durable team knowledge
  with per-run scratch. Either scratch pollutes git history, or each scratch file needs a
  bespoke ignore line — the discipline this ADR is meant to fix.
- **A published config *package* / service** the toolkit imports. Rejected as over-heavy:
  per-project state is naturally a per-project *folder*, versioned in that project's own
  repo; a package adds a dependency and a release cadence for what is just local files.
- **No schema version.** Rejected: an emergent design that will gain fields is exactly the
  case that needs a version + migration path; skipping it trades a one-time field for
  unbounded silent-breakage risk.
- **Hardcode each skill's scan path in its own definition** (an argument default or
  `## Scope` prose pointing at the primary source dir). Rejected: forces every adopter with
  a different layout to fork skill internals, and ships toolkit assumptions about a host's
  folders. A declarative scope descriptor in the committed zone makes reach host-authored
  *data*.
- **Roots-only scope (narrow-only, no ignore layer).** Rejected: most adopters know what to
  leave *out* far more cheaply than they can enumerate every root to keep *in*. Ignore-first
  with an optional `## Roots` narrowing knob matches how hosts actually reason about scope.
- **Literal `+` / `-` bullets for re-inclusion** (the original sketch). Rejected: collides
  with the bullet tokenizer, which treats `+` as a bullet marker, silently dropping the sign.
- **gitignore-style `!token` inside `## Ignore`.** Rejected: forces ordered last-match-wins
  evaluation (the current matcher is unordered set-membership), a larger change for no
  readability gain over a named `## Allow` section.
- **Build `## Allow` now.** Rejected as speculative generality: while no skill yet resolves
  its file universe through the ignore-first walk, an override knob would be untested-by-use.
  Lock the semantics; build on the first real consumer.

## Consequences

- **Easier:** one neutral, namespaced home all agents share; an explicit commit/ignore seam
  shipped with the toolkit; every new state kind has an obvious zone; migrations are
  localized and versioned; the cross-tool instruction mirror finally has a matching *state*
  seam; per-skill scope becomes host-authored data in the committed zone, so adopters tune
  reach without forking skill internals.
- **Harder:** a migration touchpoint now (`.project-state.json` + its three call sites, plus
  a transitional fallback); the toolkit must own the shipped `.gitignore` rule and the schema
  version + migrations; one more dotfolder in consuming repos.
- **Now disallowed:** writing new toolkit per-project state to the repo root or under
  `.claude/`. New state goes into the correct `.engineering/` zone.
- **Relocates (not re-decides):** the host-config docs previously shipped under
  `.claude/docs/` — `todo-tuning.md` and `importance-map.md` — now live in `.engineering/docs/`
  (loaders keep a one-time-warning `.claude/docs/` fallback during transition). This refines
  only the *location* line in ADR 0016; ADR 0016's importance-map *shape* decision is
  unchanged.
- **Per-skill scope — standing design:** the two-level model is confirmed; future
  scope-driven skills inherit the project `ignore.md` and add a per-skill descriptor. The
  `## Allow` encoding and precedence are fixed, so the first skill needing re-inclusion
  implements against a settled contract rather than relitigating syntax.
- **Per-skill scope — deferred work (tracked, build-on-trigger):** implement `## Allow` in
  the scope loader per the precedence rule (with tests for the four cases: allow beats
  project ignore; allow beats skill ignore; allow satisfies the `## Roots` gate; allow
  cannot pierce the builtin prune); migrate the skills still carrying a hardcoded scan-path
  default onto the scope loader's `scan(...)`; wire up or remove any orphaned `<skill>-scope.md`
  descriptor whose detector does not yet read the scope API.
- **Surfaced, not closed:** derived-knowledge merge handling (above). The folder makes the
  problem *concrete* — it concentrates derived-knowledge files in one place — which is why
  the open question lands with this ADR.

## Verification

- `.engineering/` exists in the consuming project; the committed zone is tracked and the
  local zone is gitignored by a **toolkit-shipped** rule (not a host-authored one).
- A schema `version:` is present and a migration path is documented.
- `.project-state.json` resolves from `.engineering/` with a root-location fallback during
  transition; `project_state.py` / `scan_coverage.py` / `/orient` updated and still green.
- A ledger intake exists for derived-knowledge merge handling.
- **Per-skill scope:** the shipped two-level resolution (project `ignore.md` + per-skill
  descriptor, ignore-first, with optional `## Roots` narrowing) is covered by scope-loader
  tests and resolves a skill's universe correctly; a repo-wide `## Roots` is discarded with
  a one-time warning.
- **Per-skill scope (`## Allow`, on implementing the deferred item):** the four precedence
  cases must pass, and the builtin-prune-cannot-be-pierced case must be explicit. No behavior
  change ships with this dimension until the trigger fires.
- **Accepted (2026-05-27):** the folder exists in the dogfood repo — `.project-state.json`
  migrated into the committed zone; the shipped `.gitignore` rule and the `manifest.json`
  schema `version` are real; and the three call sites read from the new location with the
  root fallback. Pairs with ADR 0020 (project-state, the folder's first inhabitant) and ADR
  0022 (which stores accepted-gate decisions + frozen detectors here; remains proposed — its
  `.engineering/` storage dependency is now satisfied but its detector-lifecycle work is out
  of scope).
