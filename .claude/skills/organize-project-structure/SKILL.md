---
name: organize-project-structure
description: Arrive at an ideal or near-ideal repo folder structure and organization approach under framework/tool/human constraints. Use when a project has historical top-level folders, source/input/output dumps, KB/spec/eval/runtime boundaries, or a proposed directory map that needs recursive folder summaries, ideal-vs-constrained topology review, boundary discovery, folder-worth judgment, deterministic move-plan options, dry-run validation, and a safe implementation approach. Not for one-off file moves or Python package prefix clusters.
argument-hint: "[--target .] [--plan-only|--dry-run]"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: system
job: plan
best_for: |
  Whole-project information architecture: making a repo root easier to
  skim, demoting historical inputs/outputs from the top level, summarizing
  folder purpose/value at multiple abstraction levels, separating source
  material from doctrine, splitting idea lifecycle from specs, adapting an
  ideal topology to framework constraints, deciding where
  evals/runtime/apps/scripts/tests belong, and producing an
  implementation approach. When safe, this may include a batched
  /move-path plan with dry-run review; when not safe, the output is a
  human/LLM decision brief with deterministic and judgment-based parts
  separated.
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
job is to infer the clearer mental model, adapt it to hard project
constraints, preserve source material, and arrive at a near-ideal target
topology plus an implementation approach. Use deterministic movement when
the move table and reference behavior are clear; otherwise separate what
can be automated from what needs human/LLM judgment.

Read `_common/structural-design-principles.md` before judging the target
tree. The floor is framework/tool correctness; above the floor, optimize
for skim, find, cluster, and stranger tests.

## Core Contract

Separate design judgment from mechanical movement:

```text
inventory -> folder value summaries -> repeated abstraction -> ideal topology
-> constraint overlay -> target topology -> implementation approach
-> optional move-path plan/dry-run -> decision -> apply/check if chosen
```

Do not hand-edit broad references when `/move-path` can resolve them.
Do not let an LLM do unstructured path rewrites. Do not apply a move plan
just because the skill can write one; applying is a decision after the
dry-run report and constraints are reviewed.

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

## Abstraction Ladder

Use summaries to climb from concrete contents to structural boundaries:

1. **Folder summaries.** For each top-level folder and major subfolder,
   summarize what work happens there, what value gets created, what
   artifacts are produced or consumed, and what reader question the
   folder answers. For code, sample entry points and public APIs; for
   docs, sample headings and cross-links; for data, sample manifests or
   READMEs before large payloads.
2. **Second-pass summary.** Summarize the summaries. Look for repeated
   ownership patterns, lifecycle phases, hidden parallel hierarchies,
   source-vs-derived confusion, and names that describe history instead
   of current purpose.
3. **Third-pass summary.** Summarize the second pass into the smallest
   useful set of navigation keys: e.g. doctrine, ideas, contracts,
   runtime, proof machinery, raw source material, apps, tools, tests.
   This is the ideal logical topology before constraints.

Use the discovered boundaries to decide folder-worth. A boundary is a
folder candidate when it has its own reader question, lifecycle,
artifact set, or change cadence. It is a strong folder candidate when
two or more of these are true:

- readers would naturally ask for it by name;
- edits inside it usually happen together and separately from neighbors;
- it owns a distinct value-producing workflow or artifact type;
- it has enough siblings/subparts that flat filenames would need a fake
  prefix;
- its name is being used as a tag on multiple siblings instead of as a
  container, e.g. several rename/move skills that naturally read as a
  `renaming/` cluster;
- it needs its own README/index to explain what belongs there and what
  does not.

Pairs can stay flat when the boundary is weak. A small but distinct
boundary can still earn a folder when the navigation key is durable.
When possible, prefer colocating the cluster under a real folder over
sprinkling a shared tag through filenames or sibling names. Keep the tag
flat only when a framework, discovery mechanism, or strong reader
preference requires it.

Keep the intermediate summaries short enough to review. They are not
deliverables unless the user asks; they are the ladder that makes the
target topology explainable instead of vibes-based.

## Constraint Overlay

After proposing the ideal logical topology, apply constraints before
solidifying the target topology:

- Framework/runtime conventions: Next.js `app/` or `pages/`, Python
  package/import roots, Django app layout, build config discovery, test
  runner discovery, static asset discovery.
- Tooling contracts: CI paths, deployment manifests, codegen outputs,
  docs/link checkers, package metadata, `.gitignore`, data loader paths,
  notebook/report expectations.
- Human constraints: preferred names, backwards-compatible public paths,
  source-package preservation, review scope, rollback story.

Constraints do not erase the ideal model; they explain where the final
target topology intentionally bends. If a constraint is merely manual
reference-update cost, consider improving `/move-path` or adding an
adapter over keeping an unintuitive layout, but do not pretend all
constraints are automatable.

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

Use `/move-path` for the deterministic part when the move table is clear.
Write one YAML plan for the conceptual batch, with `exact_text_paths:
update` only after reviewing that plain path prose should move
mechanically too. If the uncertainty bucket is large, stop at a dry-run
report and a decision brief.

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

Use one batch for one mental-model migration. Split when move groups have
different reviewers, rollback stories, or confidence levels.

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

- state the ideal topology, the constrained target topology, and why
  they differ;
- separate deterministic moves from judgment/manual follow-up;
- if moves were applied, run `/move-path --check`;
- run project-native link/test checks if they exist;
- report any historical references intentionally left unchanged;
- do not update ecosystem or project state snapshots just to silence
  unrelated advisory findings.
