---
name: which-cleanup
description: Route a completed change to proportionate cleanup and guard skills. Use after editing or committing code to inspect only the changed scope, choose warranted closeout guides, and return on-demand guide/tool paths for direct or fresh-sub-agent execution. Ambient installation is explicit and optional.
argument-hint: "[paths… | --staged | --changed-from REF | --commit SHA | --range A..B]"
allowed-tools: Bash, Read
user-invocable: true
tier: cross-cutting
job: meta
language: any
framework: any
best_for: |
  End-of-task closeout: identify cleanup and GUARD work warranted by changed
  files or a bounded Git diff. Use when the question is “I changed this; what
  engineering checks should happen before I call it done?”
not_for: |
  Forward routing before work starts (use /which-shape then /which-skill).
  A global debt sweep (use /triage-debt). Running every recommended scanner,
  editing production code, or scanning the whole repository without a scope.
lanes: [routing]
stage: verify
entrypoint: true
consumes: [changed_paths, commit_range]
produces: [closeout_recommendation, selected_skill_handoffs]
risk_triggers: [post-change, multi-file, missing-guard]
max_overhead: "Return the bounded roster and stop; do not run recommended skills automatically."
---

# /which-cleanup

Route a completed change to a small, proportionate closeout roster. This is the
third default router alongside `/which-shape` and `/which-skill`:

- `/which-shape` chooses the operating loop;
- `/which-skill` chooses a task skill;
- `/which-cleanup` chooses post-change checks and guards.

Do not execute the recommended skills. Return exact on-demand guide and tool
paths so the calling agent can load only what it needs. For non-trivial
closeout, prefer a fresh non-context sub-agent per independent read-only lens;
keep mutations serial.

## Run

From a Codex project installation:

```bash
cd .agents/skills/which-cleanup
python3 scripts/route.py <scope args> --project-root <host-root> --json
```

Supported scopes:

```text
<path> [<path> ...]
--staged
--changed-from <ref>
--commit <sha>
--range <a..b>
```

With no scope flag, inspect the working-tree, staged, and untracked file lists.
The portable router requires only Python’s standard library and Git when a diff
scope is used.

## Interpret the result

Honor these fields:

- `scope_band`: `trivial`, `small`, `medium`, or `large`, based on changed-file
  count. It controls roster width, not correctness or risk by itself.
- `resolved_paths`: the exact bounded paths considered.
- `recommendations[]`: skill, reason, primary on-demand `handoff` with the
  shared source-inventory path and manifest-backed language/fact/outcome
  capability row, and an `optional_install` command used only when the user
  requests ambient installation.
- `source`: the canonical repository and conventional skill/tool roots.
- `limitations`: what portable mode deliberately does not infer.

The universal closeout floor is test-obligation drift, comment drift, and
regression prevention. Wider changes additionally surface duplication,
omnibus-module, and incomplete-sweep checks. This is a conservative router,
not proof that every recommendation applies.

## Handoff

For each relevant recommendation:

1. Skip it explicitly if it is irrelevant to the actual change.
2. For a tiny check, read only its `handoff.guides` paths directly.
3. For a non-trivial independent check, create a fresh non-context sub-agent
   with the bounded changed paths, reason, and returned guide/tool paths.
4. Follow that skill’s own support and runtime claims; a location is not a
   claim that the tooling is language-neutral or independently installable.

Use `optional_install` only when the user explicitly chooses ambient
installation.

Skip irrelevant recommendations explicitly. Keep mutations serial even when
multiple read-only checks can run independently.

## Boundaries

- Advisory only; never edits production files or runs the selected skills.
- Does not load all skill bodies or a repository-wide execution runtime.
- Does not promise subsystem-specific routing without a separately installed
  project profile or task skill.
- The source checkout retains richer historical closeout scripts for its own
  development, but they are not part of this portable default path.
- The thin library bootstrap only materializes the source outside discovery;
  it is not a dispatcher, workflow coordinator, package manager, or trust
  layer.

## Failure handling

- No changed paths: report no recommendation and stop successfully.
- Invalid or conflicting scope flags: surface the usage error.
- Git unavailable for a diff scope: report an empty scope; ask for explicit
  paths rather than scanning the repository.
- Recommended skill unavailable or unsupported: report the source location and
  limitation; do not invent or inline its behavior.

## Files

```text
.claude/skills/which-cleanup/
├── SKILL.md
└── scripts/
    └── route.py       # portable stdlib-only installed router
```
