# Probe old-P3 — Phase 5.3.5 dispatch decision at exactly 3 instances

**Skill version probed:** /tmp/refactor-skill-old/ (SKILL.md + knowledge/execution-playbook.md)
**Scenario:** Phase 5.3.5 / 5.4 convention enforcement. Scan found EXACTLY 3 instances of one
naming-convention violation (same convention, three call sites, three different files).

## Decision

**Fix the 3 instances sequentially in the orchestrator. Do NOT dispatch the micro-fix swarm.**

3 call sites falls below the swarm trigger (5+) and lands in the 1–4 band of the §5.4
enforcement table, which explicitly mandates sequential orchestrator fixes. The fact that
the instances span three different files does not change the band — the table keys on
violation count, not file count.

## Governing rule text (quoted exactly)

### 1. Swarm trigger — execution-playbook.md §5.3.5

Section opener:

> When findings.md contains **5+ instances of the same mechanical fix**
> (typically convention violations: bare `.delay()`, bare `int()` on request
> data, `get_or_create(site=...)` instead of `ensure_for_site`), do
> NOT fix them sequentially.

Explicit trigger line:

> **Trigger:** any finding cluster (same `convention-violated` value) with
> 5+ call sites, confirmed by `python3 scripts/specs.py violations <spec-id>`
> (R13).

3 < 5 → the swarm trigger is not met.

### 2. Enforcement decision table — execution-playbook.md §5.4

> | Violation count | Decision | Execution |
> |---|---|---|
> | 0 | No action | Already compliant. Note in findings.md and move on. |
> | 1–4 | **Inline fix** in this refactor | Fix sequentially in the orchestrator. Not worth swarm overhead. |
> | 5–10 | **Inline fix** in this refactor | Use Phase 5.3.5 micro-fix swarm (parallel sub-agents). |
> | 11+ | **Separate follow-up ledger entry** | Create a dedicated ledger `split_queued` entry, document the full violation list, and mark the refactor as "partial enforcement" in findings.md. |

3 violations → the 1–4 row → "Fix sequentially in the orchestrator. Not worth swarm overhead."

## Internal inconsistency noted (does not change the decision)

The per-convention pseudo-code in §5.4 contradicts the table:

> ```python
>     if count <= 10:
>         dispatch_micro_fix_swarm(item_id, canonical, violations["by_file"])
>         record_inline_fixed(item_id, canonical, count)
> ```

Taken literally, `count <= 10` would dispatch the swarm at count = 3. This conflicts with
both the table's 1–4 row and the §5.3.5 "5+ call sites" trigger. The prose table and the
explicit trigger govern; the pseudo-code is a lossy simplification of the decision loop
(it collapses the 1–4 and 5–10 bands into one branch). This is a latent skill-text drift
worth repairing in the new skill version.

## Non-factors checked

- **`--enforce-inline` escape hatch (§5.4):** not given in this scenario; and even when
  passed, it "pre-commit[s] to the inline-fix branch for all violations" — it forces the
  inline-fix *decision* regardless of count, it does not convert a sub-threshold cluster
  into a swarm dispatch obligation.
- **Heuristic softener (§5.4):** "The 10-violation threshold is a heuristic — err on the
  side of inline fix if the violations are mechanical and in a small number of files."
  This softens the 10/11+ boundary toward inline fixing; it does not authorize swarm
  dispatch below the 5+ trigger.
- **Three different files:** SKILL.md's swarm invariant ("Micro-fix swarm: sub-agents edit
  only, orchestrator commits serially") and the §5.3.5 dispatch pattern (one sub-agent per
  target file) describe *how* a swarm runs once triggered; file count never appears as a
  trigger condition.

## Verdict

Sequential orchestrator fix. Mandated by the §5.4 table (1–4 band) and consistent with the
§5.3.5 trigger (5+ call sites required for swarm dispatch).
