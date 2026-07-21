---
id: "0039"
namespace: core
title: "Route proven read-only journeys through bounded skill families"
status: accepted
date: 2026-07-21
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [.claude/skill-families/code-health-readonly/, .claude/skills/which-skill/, scripts/benchmark_code_health_family.py]
embodied_by: ["skill:which-skill", "contract:tests/test_code_health_family.py", "contract:tests/test_code_health_family_benchmark.py"]
tags: [skills, routing, context-efficiency, batching, sub-agents]
related_smell: null
related_pattern: null
---

# Route proven read-only journeys through bounded skill families

## Context

ADR 0038 keeps only three routers ambient and loads task skills from an
on-demand library. That solves discovery-context cost but does not solve the
repeated guidance and serial latency incurred when one user request genuinely
needs several complementary lenses. ML-009 showed the three deterministic
read-only tools could run concurrently, but it did not measure model execution,
synthesis, or tokens and therefore did not justify product routing.

ML-020 compared the existing full skills with a compressed shared core and
member contracts over five real model/tool/synthesis trials. The bounded family
preserved every canonical finding, incomplete state, native check, and source
byte while materially reducing controlled context, reported tokens, and wall
time. An unseen host and two invalid-input sentinels passed.

## Decision

`which-skill` may return the `code-health-readonly` coverage family for an
explicit broad, read-only JavaScript/TypeScript health request. It retains
`find-complexity-hotspots` as the primary recommendation and additionally
returns:

- the fixed `audit-decisions`, `find-complexity-hotspots`, and
  `find-standard-gaps` coverage set;
- the shared family core and concise member contracts;
- each member's independent capability-backed on-demand closure;
- host dependencies, runnable members, and explicit skips; and
- the family-local max-three read-only launcher and one synthesis owner.

No member becomes ambient or receives a family-wide install command.
Individual skills remain directly invocable. Explicit individual-skill and
mutation requests do not activate the family. A request must resolve to exactly
one of JavaScript or TypeScript because the launcher owns one language per run.
User-decision stages and every mutation remain serial.

This decision authorizes one family-specific launcher, refining ADR 0038's
rejection of a general launcher/workflow platform. It does not authorize a
universal DAG, shared context cache, retry service, autonomous mutation engine,
or blanket compression. Shared coordination may be extracted only after a
second family demonstrates the same execution invariants and the extraction
reduces total maintained code.

## Alternatives considered

- **Keep invoking all full skills serially.** Rejected for this journey: the
  measured family reduced controlled context 78.84%, reported aggregate tokens
  22.23%, and median wall time 52.68% without losing outcomes.
- **Install the three member skills together.** Rejected because it violates
  router-only ambient discovery and makes a one-shot coverage set permanent
  context.
- **Teach `which-skill` to select arbitrary complementary sets.** Rejected
  until more than one proven family supplies deterministic composition rules.
- **Build a general workflow coordinator.** Rejected because this single fixed
  read-only journey does not justify the abstraction or its maintenance cost.
- **Use deterministic tools without model execution.** Retained as the family
  launcher's evidence layer but rejected as the acceptance benchmark; it would
  not prove that compressed guidance still directs agents and synthesis.

## Consequences

Broad supported health requests gain one bounded, dependency-aware handoff and
can use fresh non-context lanes without loading three full skills. Narrow work
continues to route to one skill.

The family adds a 551-line launcher and a separate 931-line resumable benchmark
harness. Those sizes are visible costs, not a template to repeat. The benchmark
records exact injected prompt bytes and structured token usage but cannot claim
Codex system-context bytes or OS filesystem-read bytes.

## Verification

`tests/test_code_health_family.py` checks family activation, exclusions,
dependency/inactive skips, compressed guard preservation, real final artifacts,
synthesis, source immutability, exact natural prompt routing, invalid standards,
excluded-only targets, mixed-language rejection, and host opt-out preservation.
`tests/test_installed_routers.py` proves the
installed router returns on-demand family paths while discovery remains exactly
three routers. `tests/test_code_health_family_benchmark.py` checks the resumable
measurement, frozen-baseline resume guard, and hidden completeness contracts.

The completed live benchmark directly constructed member commands; it did not
exercise `which-skill` on each timed prompt. That route boundary is separately
proved by the product regressions, and future benchmark preparation records a
route projection for every exact prompt before model calls begin.

The compact live evidence is `.claude/tasks/ml020-code-health-results.json`;
raw per-call checkpoints are gitignored under
`reports/ml020-code-health-run/`.
