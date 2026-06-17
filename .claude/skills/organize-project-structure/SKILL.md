---
name: organize-project-structure
description: Design and execute a repo-wide folder-structure reorganization around intuitive top-level ownership, artifact lifecycle, and reader navigation. Use when a project has historical top-level folders, source/input/output dumps, KB/spec/eval/runtime boundaries, or a proposed directory map that needs review, move planning, dry-run validation, reference updates, and safe handoff to /move-path. Not for one-off file moves or Python package prefix clusters.
argument-hint: "[--target .] [--apply]"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: system
job: refactor
best_for: |
  Whole-project information architecture: making a repo root easier to
  skim, demoting historical inputs/outputs from the top level, separating
  source material from doctrine, splitting idea lifecycle from specs,
  deciding where evals/runtime/apps/scripts/tests belong, and producing a
  batched /move-path plan with dry-run review before edits.
not_for: |
  Single file or folder rename/move with known destination (use
  /move-path directly). Python package topology drift such as prefix
  clusters or sparse packages (use /find-folder-topology-drift and
  /propose-folder-reorganization). Glossary/domain terminology renames
  (use /rename-concept). Behavior-changing subsystem extraction (use
  /refactor-subsystem).
language: any
framework: any
---

# /organize-project-structure

You are the orchestrator for repo-wide folder-structure redesign. Your
job is to choose a clearer mental model, preserve source material, write
a deterministic move plan, run `/move-path --dry-run`, review uncertainty,
then apply only when the dry run matches the intended topology.

Read `_common/structural-design-principles.md` before judging the target
tree. The floor is framework/tool correctness; above the floor, optimize
for skim, find, cluster, and stranger tests.

## Core Contract

Separate design judgment from mechanical movement:

```text
inventory -> lifecycle classification -> target topology -> move-path plan
-> dry-run report -> apply/check -> update signposts
```

Do not hand-edit broad references when `/move-path` can resolve them.
Do not let an LLM do unstructured path rewrites.

## Classification Pass

Classify every top-level folder and major root file by lifecycle:

- `root-signpost` — files a new reader should see first, usually
  `README.md`, `AGENT.md`, or repo config.
- `doctrine-kb` — source-grounded knowledge, summaries, claims,
  process, schemas, synthesis.
- `idea-lifecycle` — ideas before they become default routes, skills,
  workbench features, or specs.
- `build-commitment` — contracts, architecture decisions, product specs,
  security decisions, acceptance criteria.
- `runtime` — executable product/library code.
- `proof-machinery` — fixtures, scorers, runners, experiments,
  run-records, reports.
- `raw-source-material` — datasets, imported source packages, logs,
  extraction outputs, third-party or historical inputs.
- `tooling` — scripts, tests, apps, CLIs, dashboards.
- `archive` — preserved historical state that should not shape daily
  navigation.

Top-level folders must earn their position by being a durable reader
navigation key. Historical names like `inputs-1/`, `inputs-2/`, and
`outputs/` usually fail that test; preserve them under a source-material
or archive owner instead of deleting or flattening them.

## Target Tree Rules

- Keep root small. Top-level names should describe kinds of work, not
  import chronology.
- Keep raw materials out of `kb/`; KB may contain source maps and claim
  ledgers, but not large/raw dumps unless the project explicitly chooses
  that.
- Keep active idea lifecycle outside `kb/` when ideas need intake,
  pilots, composition, routing, promotion, or retirement.
- Put executable schemas in `specs/contracts/` only when they become
  build commitments; Markdown-first templates can remain in the faster
  lifecycle folder.
- Put pilot intent/specs near ideas; put runnable experiment execution
  and results under `evals/`.
- Add or update README/index signposts for every newly important folder.

## Move Planning

Use `/move-path` for execution. Write one YAML plan for the conceptual
batch, with `exact_text_paths: update` only after reviewing that plain
path prose should move mechanically too.

Recommended reference scope for docs-heavy repos:

```yaml
reference_scope:
  include:
    - "**/*.md"
    - "**/*.mdx"
    - "**/*.yml"
    - "**/*.yaml"
    - "**/*.json"
    - "**/*.html"
  exclude:
    - ".git/**"
    - ".move-path/**"
    - "node_modules/**"
    - ".venv/**"
    - "__pycache__/**"
```

Use one batch for one mental-model migration. Split only when two move
groups have different reviewers or rollback stories.

## Dry-Run Review

After `/move-path --dry-run`, inspect:

- move map: does every source land under the intended lifecycle owner?
- auto rewrites: are path references changing to the right new identity?
- suggestions: are they true references, historical citations, or
  intentionally unchanged labels?
- blocked findings: do not apply until resolved.
- Git impact: tracked moves should preserve history with `git mv`.

## Handoff

Before final handoff:

- run `/move-path --check`;
- run project-native link/test checks if they exist;
- report any historical references intentionally left unchanged;
- do not update ecosystem or project state snapshots just to silence
  unrelated advisory findings.
