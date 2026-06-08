---
name: find-skill-intent-drift
description: |
  Advisory SUSPECT scan that compares each skill under `.claude/skills/`
  against its machine-checkable intent + provenance contract under
  `.claude/contracts/skills/<name>.yaml` (schema v2). Flags four drift
  bands — missing (skill has no contract), orphaned (contract for a
  deleted skill), malformed (contract missing required schema keys), and
  stale (SKILL.md committed after the contract's last commit, so captured
  intent may have silently drifted). This is the "no easy reversion of
  intent" guard: it cannot block an edit, but it makes intent erosion
  visible. It is the intent/provenance layer of the skill-meta trio,
  distinct from frontmatter-contract lint and artifact-coherence drift.
argument-hint: "[--strict for CI exit-1] [--skills-root DIR] [--contracts-dir DIR] [--no-index]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Keeping the skill ecosystem's recorded "why each skill exists / what it
  solves / what it was dogfooded on" honest as skills are added, edited,
  renamed, or deleted. The canonical case is catching a skill whose
  SKILL.md was reworked (new problem class, narrowed scope, merged
  responsibility) without its intent contract being updated to match — the
  silent reversion the contracts exist to prevent. Also surfaces the
  duplication picture: each contract's `duplication_risk[]` block records
  sibling skills that touch the same surface and the `not_for` line that
  disambiguates them, rolled up into `_index.yaml` and
  `_duplication-watchlist.yaml`.
not_for: |
  The other two layers of the skill-meta trio. Frontmatter *contract*
  validation (required fields, enum values, name==dir) — that is
  `scripts/skill_meta.py lint`. SKILL.md prose ↔ on-disk artifact
  coherence (a documented script/flag/tool the files no longer provide) —
  that is `/find-skill-artifact-drift`. Authoring or revising a skill
  itself, which should also write or refresh its intent contract — that is
  `/plan-skill`. Agent-rules doc-surface drift (oversized always-loaded
  files, dormant docs, broken onboarding links) — `/find-rule-surface-drift`.
  This skill never edits skills or contracts and never blocks a commit; it
  is advisory unless run `--strict` in CI.
language: python
framework: any
---

# /find-skill-intent-drift

You are running an advisory audit that keeps the **skill intent +
provenance contracts** in sync with the skills they describe. Each skill
under `.claude/skills/<name>/` should have a contract at
`.claude/contracts/skills/<name>.yaml` (schema v2 — see
`_schema.yaml` in that directory) recording, in machine-checkable form,
*why the skill exists, what it solves, when it was born, and what it was
dogfooded on*. Those contracts are the durable record of intent; this
detector flags where the record and the reality have diverged.

The guard cannot block an edit. Its job is to make silent intent erosion
**visible** — the "no easy reversion of intent" property — so a reviewer
notices that a skill's recorded purpose no longer matches what the skill
now does.

## The skill-meta trio

Three layers guard the skills-about-skills surface, at increasing
semantic depth — keep them distinct:

1. **Frontmatter contract** — `scripts/skill_meta.py lint`: required
   fields present, enum values legal, `name` matches directory. Structural
   well-formedness of the YAML header.
2. **Artifact coherence** — `/find-skill-artifact-drift`: the SKILL.md
   *prose* references (named scripts, documented `--flags`, declared
   tools/evidence) match the *files on disk*. Does the procedure point at
   things that exist.
3. **Intent + provenance** — *this skill*: the recorded *why it exists /
   what it solves / where it came from* matches the skill, and has not
   silently drifted. The deepest layer; the only one a human reviewer must
   ultimately judge.

A skill can pass all of (1) and (2) — perfectly well-formed frontmatter,
every script and flag real — while its captured *intent* has quietly
reverted. That gap is what this skill exists to surface.

## Default Target

With no arguments, the scan compares:

- **Skills** — every directory under `.claude/skills/` that contains a
  `SKILL.md` (excluding `_common/`).
- **Contracts** — every `*.yaml` under `.claude/contracts/skills/` whose
  name does not start with `_` (so `_schema.yaml`, `_index.yaml`, and
  `_duplication-watchlist.yaml` are excluded from the skill enumeration).

Both roots are flags (`--skills-root`, `--contracts-dir`) defaulting to
the conventional layout, so the same script runs unchanged against a
host-project checkout that vendors these skills.

## Pipeline

Run with the project venv:

```
.venv/bin/python .claude/skills/find-skill-intent-drift/scripts/scan.py
```

Advisory by default: always exits 0 and prints the findings per band.
Pass `--strict` to exit 1 on any finding (for a CI gate). As a side
effect the scan regenerates `.claude/contracts/skills/_index.yaml` — the
auto-generated roll-up (per-skill born date, problem class, dogfood kind +
confidence, duplication-risk count, stale state); pass `--no-index` to
skip that write.

When **bootstrapping** the contracts in a fresh repo, regenerate
`_index.yaml` *after* the contracts are committed. A roll-up written while
they are still uncommitted records every entry as `stale: baseline
(contract uncommitted)`; only a post-commit re-run resolves them to `ok`.

Unlike the report-producing SUSPECT skills, this is a single-script
meta-guard: it has no `fixtures/` pair and writes no `reports/<skill>/`
run directory. Its durable output is the regenerated `_index.yaml`
(tracked in git alongside the contracts), not a gitignored scan dir.

## Drift Bands

- `missing` — a skill exists with no intent contract. Its purpose was
  never captured (or the contract was deleted). New skills should ship a
  contract via `/plan-skill`.
- `orphaned` — a contract exists for a skill directory that is gone. The
  intent record outlived the skill; the contract should be removed (or the
  skill restored if the deletion was unintended).
- `malformed` — a contract is present but missing required schema-v2 keys
  or carries invalid enum values. Required keys: `skill`, `job`,
  `problem_class`, `intent`, `solves`, `born` (with `commit` + `date`),
  `dogfood_kind` (one of `subsystem-refactor` / `self-installed-guard` /
  `fixture-pair` / `none-found`), and `provenance_confidence` with all
  four axes (`textual` / `structural` / `temporal` / `dogfood`) set to
  `high` / `med` / `low`. Capture is incomplete until these are filled.
- `stale` — the contract is committed, and the `SKILL.md` **frontmatter
  intent surface** changed between the contract's last commit and now. The
  comparison is intent-aware, not a raw timestamp check: the YAML frontmatter
  (description / best_for / not_for / job / tier / ...) is compared across the
  two revisions after dropping operational keys (`argument-hint`,
  `allowed-tools`, `name`, `user-invocable`) and collapsing path-like tokens
  to a placeholder, so a body-only sweep (e.g. a `core/` → `app/` path
  reference rewrite, prose edits below the frontmatter) does **not** flag —
  only a real intent edit does. Edge cases: a `SKILL.md` absent at the
  contract commit flags stale (the intent surface can't be vouched for); a git
  or YAML-parse failure falls back conservatively to the legacy "SKILL.md
  newer than contract" timestamp compare. A contract that is not yet committed
  reports `baseline (contract uncommitted)` and is **not** flagged stale —
  there is no committed baseline to drift from yet.

## Out of Scope

- **Judging whether the recorded intent is *correct*.** The detector
  checks structural presence and freshness (keys, enums, commit recency),
  not whether the prose accurately describes the skill. A human reviewer
  reading a `stale` finding makes that call.
- **Editing skills or contracts.** This is detection only; refreshing a
  drifted contract is a follow-up (manual, or via `/plan-skill` when the
  skill itself is being revised).
- **Provenance archaeology.** Determining `born`, `dogfood_kind`,
  `dogfooded_on`, and the confidence axes from git history is the
  contract-authoring step, not this scan. The scan only verifies those
  fields are present and well-formed.
- **Blocking commits.** Advisory by design. The only non-zero exit is the
  explicit `--strict` CI mode.

## Provenance Note

The contracts triangulate intent from git-native channels (textual commit
subjects, structural guard-install signatures, temporal proximity to
birth) plus a dogfood axis, corroborated by structured sources —
`.claude/docs/precedents.yml`, the load-on-demand docs, and the ADR tree at
`ai-docs/decisions/` (NOT `docs/decisions/`). `embodies_decisions.adr` is
populated only where an ADR actually governs the skill (bidirectional
signal — the SKILL.md cites the ADR and the ADR names the skill back), not
for every passing mention. Skill *outputs* under `reports/<skill>/` are gitignored
(`/reports/*`, only `/reports/_meta/` tracked) but exist on disk as
timestamped run artifacts — useful for raising the `dogfood` axis when
authoring a contract, but never a trusted oracle (they are the skill's own
self-report). See `_schema.yaml` for the full field reference and the
worked example.
