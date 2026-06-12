# Lift probe — new-P3: 3-instance convention violation at Phase 5.3.5/5.4

## Scenario

Phase 5 convention enforcement. Scan found EXACTLY 3 instances of one
naming-convention violation (same convention, three call sites, three
different files).

## Decision

**Fix them sequentially myself in the orchestrator. Do NOT dispatch the
micro-fix swarm.**

3 instances falls in the 1–4 band of the §5.4 decision table, which
explicitly routes to sequential orchestrator fixes. The swarm's own
trigger in §5.3.5 requires 5+ call sites, so the swarm is not even
eligible at 3.

## Rule text that determines it

### 1. The §5.4 decision table (execution-playbook.md, "Convention enforcement — refactor + adopt in one run (R20)")

> | Violation count | Decision | Execution |
> |---|---|---|
> | 0 | No action | Already compliant. Note in findings.md and move on. |
> | 1–4 | **Inline fix** in this refactor | Fix sequentially in the orchestrator. Not worth swarm overhead. |
> | 5–10 | **Inline fix** in this refactor | Use Phase 5.3.5 micro-fix swarm (parallel sub-agents). |
> | 11+ | **Separate follow-up ledger entry** | Create a dedicated ledger `split_queued` entry, document the full violation list, and mark the refactor as "partial enforcement" in findings.md. |

The governing row: **"1–4 | Inline fix in this refactor | Fix
sequentially in the orchestrator. Not worth swarm overhead."**

### 2. The §5.4 per-convention decision loop (pseudo-code, same section)

> ```python
> if count < 5:
>     # 1-4: fix sequentially in the orchestrator — not worth
>     # swarm overhead (decision table above).
>     fix_inline_sequentially(item_id, canonical, item["violations"])
>     record_inline_fixed(item_id, canonical, count)
> ```

count = 3 → `count < 5` → `fix_inline_sequentially`.

### 3. The §5.3.5 swarm trigger (execution-playbook.md, "Micro-fix swarm — parallel remediation of mechanical fixes (R19)")

> When findings.md contains **5+ instances of the same mechanical fix**
> (typically convention violations: bare `.delay()`, bare `int()` on request
> data, `get_or_create(site=...)` instead of `ensure_for_site`), do
> NOT fix them sequentially.

and:

> **Trigger:** any finding cluster (same `convention-violated` value) with
> 5+ call sites, confirmed by `python3 scripts/specs.py violations <spec-id>`
> (R13).

3 < 5, so the swarm trigger never fires.

## Notes / caveats applied with the decision

- The "three different files" detail does not change the band — the
  table keys on violation count, not file count. The 5–10 row's swarm
  dispatch is per-file, but that mechanism only activates at 5+.
- The count is taken AFTER the §5.4 `code_roots` filter ("Filter to
  `code_roots` files only (unless whole-repo enforcement was
  approved)") and should be confirmed via
  `python3 scripts/specs.py violations <spec-id>` per the §5.3.5
  trigger (R13).
- Sequential orchestrator fixes still follow Phase 5 invariants: the
  batch concurrency re-check (R6, §5.2 step 0), green tests before
  commit, and the SKILL.md success-gate that a named suite has a
  coverage path into edited code (R36) — the 1–4 band waives the
  swarm, not the verification discipline.
- The §5.4 escape hatch ("a Phase 4 decision, not a flag") only governs
  bypassing the 11+ deferral threshold downward into inline-fix; it
  does not promote a 3-count cluster upward into a swarm.
