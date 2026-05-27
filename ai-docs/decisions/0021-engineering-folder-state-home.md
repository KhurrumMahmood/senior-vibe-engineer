---
id: "0021"
title: Portable .engineering/ state home
status: accepted
date: 2026-05-22
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [".claude/skills/find-standard-gaps/scripts/project_state.py", ".claude/skills/find-standard-gaps/scripts/scan_coverage.py", ".claude/skills/orient/", ".engineering/project-state.json"]
tags: [state, portable, cross-tool, engineering-folder, project-state, committed-vs-gitignored, schema-versioning, migration, derived-knowledge]
related_smell: null
related_pattern: null
---

# Portable .engineering/ state home

## Context

The toolkit is a portable, cross-tool (Claude Code / Codex / Augment) meta-repo
of code-quality skills, meant to drop into *any* consuming project. As of
ADR 0020 it also keeps **per-project state** — declared maturity × stakes lives
in `.project-state.json` at the repo root, read by `project_state.py`, consumed
by `scan_coverage.py`, written by `/orient`. More state is already arriving:
convention / capability descriptors (which template dir holds cotton primitives —
the cotton scanner's hardcoded `app/_components/cotton` is the trigger),
accepted-gate / enforcement decisions and frozen detectors (ADR 0022), and
curated reports worth keeping for future work.

Two problems with the status quo:

- **No neutral home.** State is starting to scatter — `.project-state.json` at
  root, scans under `reports/`, skills + idea-ledger under `.claude/`. But
  `.claude/` is *Claude-specific*; Codex reads `AGENTS.md`, Augment reads
  `.augment/`. Per-project *state* shared by three agents must not live under one
  agent's folder. Instructions already mirror across `CLAUDE.md` / `AGENTS.md` /
  `.augment/`; state has no such neutral seam yet.
- **No commit/ignore discipline.** Some state is durable team knowledge that
  belongs in git (declared maturity, accepted gates, a curated finding). Some is
  per-run scratch that must *not* be committed (scan working files, caches,
  synthesis intermediates). Today every new state file forces an ad-hoc
  `.gitignore` decision, one at a time.

The design is also explicitly **emergent** — new kinds of state keep surfacing as
we hit needs we hadn't anticipated. So this ADR fixes the *container, the zones,
and the rules*, not an exhaustive file list.

## Decision

Introduce **`.engineering/`** at the consuming project's root as the toolkit's
agent-neutral, per-project state home — the *state* analog of the cross-tool
instruction mirror (`CLAUDE.md` / `AGENTS.md` / `.augment/`). All three agents
read and write it. Model it on `.vscode/` and `.github/`: a namespaced dotfolder
that is partly committed, partly local.

**Two zones, split by commit policy:**

1. **Committed zone** (tracked, top level of `.engineering/`) — durable, shared,
   team-level state that should travel with the repo and survive clones,
   analogous to a checked-in `.vscode/settings.json`:
   - project-state (maturity × stakes — ADR 0020);
   - convention / capability descriptors (the cotton primitive root, the
     template/js roots — what ADR 0022's curated detectors parameterize against);
   - accepted-gate / enforcement decisions and frozen generated detectors
     (ADR 0022);
   - **curated reports that inform future work** — kept findings, not every raw
     scan.

2. **Gitignored zone** (a reserved subdirectory, e.g. `.engineering/local/`) —
   ephemeral, machine-local, per-run process state that must not be committed:
   - scan working files and intermediate stage outputs;
   - caches, synthesis scratch, detector candidate drafts before acceptance;
   - run-local effectiveness logs that don't need to travel.
   The toolkit **ships the ignore rule** (a `.gitignore` inside `.engineering/`
   that ignores the local subdir and nothing else), so adoption is automatic — a
   consuming project doesn't have to author it.

The seam is **commit policy**, not data type: "would a teammate cloning this repo
need it / should review touch it?" → committed; "is it scratch from one run on
one machine?" → gitignored.

**Versioned schema.** `.engineering/` carries a schema `version:` (a small
manifest, e.g. `.engineering/manifest.json` holding `{"version": N}`) so the
layout can evolve across toolkit releases with an explicit migration path rather
than silent breakage. Readers check the version; a mismatch triggers a documented
migration, not a crash.

**Migration (first inhabitant).** `.project-state.json` moves from repo root into
`.engineering/` (committed zone). Three call sites move with it: `project_state.py`
(the loader), `scan_coverage.py` (the consumer), `/orient` (the writer). The
loader keeps a **root-location fallback** during the transition (read
`.engineering/…` first, fall back to `./.project-state.json`, warn once) so an
un-migrated clone still works.

**Open question — merge conflicts on derived-knowledge files (flagged, not
decided here).** Committed-zone files capture *knowledge about the project* — they
are **derived fields**, not hand-authored code. When two branches both update one
(each appends a discovered convention; each bumps project-state differently;
concurrent appends to an append-only log), git's line-based merge is the wrong
resolution model: it can silently drop a discovered convention or mis-merge a
declaration. This likely needs **per-kind merge strategies** (union-by-id for
append logs, set-union for decision / convention lists, semantic reconcile +
escalation for scalar declarations), plausibly via git custom merge drivers
scoped to `.engineering/**`, with an LLM-assisted or human reconciliation path for
irreducible *knowledge* conflicts. Captured as a ledger intake for maturing;
deliberately **not** decided in this ADR.

## Alternatives considered

- **Keep state under `.claude/`.** Rejected: `.claude/` is one agent's folder; the
  toolkit is tri-agent (Claude / Codex / Augment). Shared state under a single
  agent's namespace is a category error — the same reason instructions are
  mirrored, not housed once under `.claude/`.
- **Scatter at repo root** (`.project-state.json` plus future siblings). Rejected:
  pollutes the root, no namespacing, and every new state kind is a fresh
  root-level file with its own ad-hoc ignore decision. The just-added
  `.project-state.json` is exactly this smell starting.
- **One committed folder, no gitignored zone.** Rejected: conflates durable team
  knowledge with per-run scratch. Either scratch pollutes git history, or each
  scratch file needs a bespoke ignore line — the discipline this ADR is meant to
  fix.
- **A published config *package* / service** the toolkit imports. Rejected as
  over-heavy: per-project state is naturally a per-project *folder*, versioned in
  that project's own repo; a package adds a dependency and a release cadence for
  what is just local files.
- **No schema version.** Rejected: an emergent design that will gain fields is
  exactly the case that needs a version + migration path; skipping it trades a
  one-time field for unbounded silent-breakage risk.

## Consequences

- **Easier:** one neutral, namespaced home all agents share; an explicit
  commit/ignore seam shipped with the toolkit; every new state kind has an obvious
  zone; migrations are localized and versioned; the cross-tool instruction mirror
  finally has a matching *state* seam.
- **Harder:** a migration touchpoint now (`.project-state.json` + its three call
  sites, plus a transitional fallback); the toolkit must own the shipped
  `.gitignore` rule and the schema version + migrations; one more dotfolder in
  consuming repos.
- **Now disallowed:** writing new toolkit per-project state to the repo root or
  under `.claude/`. New state goes into the correct `.engineering/` zone.
- **Relocates (not re-decides):** the host-config docs previously shipped under
  `.claude/docs/` — `todo-tuning.md` and `importance-map.md` — now live in
  `.engineering/docs/` (loaders keep a one-time-warning `.claude/docs/` fallback
  during transition). This refines only the *location* line in ADR 0016; ADR 0016's
  importance-map *shape* decision is unchanged.
- **Surfaced, not closed:** derived-knowledge merge handling (above). The folder
  makes the problem *concrete* — it concentrates derived-knowledge files in one
  place — which is why the open question lands with this ADR.

## Verification

- `.engineering/` exists in the consuming project; the committed zone is tracked
  and the local zone is gitignored by a **toolkit-shipped** rule (not a
  host-authored one).
- A schema `version:` is present and a migration path is documented.
- `.project-state.json` resolves from `.engineering/` with a root-location
  fallback during transition; `project_state.py` / `scan_coverage.py` / `/orient`
  updated and still green.
- A ledger intake exists for derived-knowledge merge handling.
- **Accepted (2026-05-27):** the folder exists in es2 (dogfood) — `.project-state.json`
  migrated into the committed zone; the shipped `.gitignore` rule and the
  `manifest.json` schema `version` are real; and the three call sites
  (`project_state.py`, `scan_coverage.py`, `/orient`) read from the new location with
  the root fallback. The scope mechanism (`_common/scope.py` + `engineering_home.py`),
  its first `.engineering/docs/<skill>-scope.md` descriptor, and the migrated
  `todo-tuning.md` / `importance-map.md` host-config docs are the committed zone's
  second inhabitant cohort. Pairs with ADR 0020 (project-state, the folder's first
  inhabitant) and ADR 0022 (which stores accepted-gate decisions + frozen detectors
  here; **remains proposed** — its `.engineering/` storage dependency is now satisfied
  but its detector-lifecycle work is out of scope).
