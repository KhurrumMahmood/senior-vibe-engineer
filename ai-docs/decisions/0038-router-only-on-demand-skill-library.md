---
id: "0038"
namespace: core
title: "Only routers are ambient; task skills load from an on-demand library"
status: accepted
date: 2026-07-19
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [README.md, .claude/skills/which-skill/, .claude/skills/which-shape/, .claude/skills/which-cleanup/, .claude/tasks/productization-restart-plan.md]
embodied_by: ["skill:which-skill", "skill:which-shape", "skill:which-cleanup", "script:.claude/skills/which-skill/scripts/bootstrap_library.py", "contract:tests/test_installed_routers.py"]
tags: [skills, routing, installation, progressive-disclosure, context-efficiency, sub-agents]
related_smell: null
related_pattern: null
---

# Only routers are ambient; task skills load from an on-demand library

## Context

Skill metadata is ambient context on agents that discover a skill directory.
Installing all 76 skills—or installing each recommendation into that same
directory—makes unrelated headers compete with the user task and encourages the
primary agent to carry workflow context it does not need. The desired product
journey has three always-available routing capabilities and a much larger body
of specialized guidance used only after routing.

The stock Agent Skills CLI already installs an exact selected set, but it has
no concept of a non-discovered guide/tool library. The previous local journey
therefore installed a selected follow-up skill after routing. That proved the
closure was portable, but it made ambient installation the normal execution
path rather than an explicit user preference.

## Decision

Only `which-shape`, `which-skill`, and `which-cleanup` are installed into agent
skill-discovery directories by default.

The complete repository is materialized in the project-scoped sibling cache
`<project-parent>/.engineering-skills/<project-name>` by a thin stdlib
bootstrap bundled with `which-skill`. This is a normal source checkout outside
both the target repository and standard discovery roots, containing guides,
skill-local scripts, shared tooling, and references.
The bootstrap reuses an existing valid library and refuses to overwrite an
incomplete destination; it is not a package manager or execution service.

Router results make an on-demand `handoff` primary. It contains the exact skill
closure, local guide and tool paths, availability, and a default execution mode
of `fresh_non_context_subagent`. Small tasks may load the returned guides in
the primary agent. Non-trivial tasks should give a fresh non-context sub-agent
the task, project root, task packet or bounded paths, and only the returned
guide/tool paths. Mutating lanes remain serial.

The pinned stock selected-skill command remains under `optional_install`, but
agents do not run it unless the user explicitly asks for ambient installation.

## Alternatives considered

- **Install all skills by default.** Rejected because even metadata-only
  discovery spends ambient context and weakens routing discipline.
- **Install the selected skill after every route.** Retained only as an
  explicit option; it needlessly changes host state for one-shot work.
- **Fetch individual guides remotely at execution time.** Rejected as the
  default because script-backed work needs a coherent local tool/reference
  closure and should not require network access after bootstrap.
- **Build a launcher, workflow coordinator, trust system, or custom package
  manager.** Rejected. Routers return paths and a bounded handoff; native agent
  delegation and direct script execution remain the execution mechanisms.

## Consequences

Default discovery stays fixed at three small router headers. A routed agent can
load one exact closure or isolate it in a sub-agent, and the same library can
serve many tasks without repeatedly installing skills.

The quick start gains one bootstrap command and the library consumes local
disk space. Guides that still assume ambient `.agents/skills` paths or a
vendored repository runtime must be interpreted using the router's absolute
paths or remain honestly unsupported until generalized. A path is not itself a
capability claim.

New router work must not make `optional_install` the primary next action, and
new task skills must not be added to the default ambient set without
superseding this decision.

## Verification

`tests/test_installed_routers.py` proves that bootstrap leaves discovery at
exactly three routers while producing valid local guide and tool paths.
Router-focused tests require `handoff` to be primary and `optional_install` to
be explicit. The TypeScript `rename-concept` journey routes through both
`which-skill` and `which-shape`, executes the selected closure from the library,
reaches its final outcome, and asserts no task skill was installed.
