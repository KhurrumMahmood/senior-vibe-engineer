# Idea-tracking harness

Validates `.claude/skills/_common/ideas_lib.py` (the engine behind every
idea-tracking skill) against scenario fixtures. Each fixture exercises
one library function with a deterministic input and expected output.

## Run

```bash
python3 .claude/tests/ideas/run_harness.py              # all fixtures
python3 .claude/tests/ideas/run_harness.py stalled-spike # one
```

Exit code 0 if every non-skipped fixture passes.

## Layout

```
fixtures/
├── stalled-spike/             find_stalled
├── plan-dropout/              find_plan_dropouts
├── harvest-ready/             find_harvest_opportunities
├── promotion-eligible/        promotion_eligible
├── supersession-chain/        supersession_chain
├── resurrection/              project + reconcile_lineage
└── extraction-truth-set/      extract_candidates (skipped until P5)
```

## Adding a fixture

1. `mkdir fixtures/<name>/`
2. Write `README.md` describing the scenario
3. Write `ledger.jsonl` (and any extra input files) for the starting state
4. Write `scenario.json` with the function call:

```json
{
  "function": "find_stalled",
  "ledger": "ledger.jsonl",
  "kwargs": {"now": "2026-05-13T00:00:00Z", "stale_days": 14},
  "expected": ["my-idea-id"]
}
```

The library function is invoked with `kwargs`; if `"ledger": "..."` is
present, the loaded record list is passed as the first positional argument.

## Skip semantics

A scenario with `"skip": "<reason>"` reports SKIP. Fixtures whose target
function does not yet exist (e.g. `extract_candidates` until P5) also
skip with `"ideas_lib.<fn> not yet implemented"`.

## What the harness does NOT cover

- Skill-level orchestration (the SKILL.md instructions to the agent)
- End-to-end runs against the real ledger
- Pattern-library frontmatter parsing (P3+)
- Bootstrap extraction against a real repo (P5)

The harness covers the *library* — the deterministic core. Skill-level
behavior is exercised in P3-P5 against synthetic and real projects.
