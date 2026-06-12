# Phase 5.3.5 Convention Enforcement Decision — 3 Instances

## Scenario
Scan found exactly 3 instances of one naming-convention violation (same convention, three call sites, three different files).

## Decision
**Fix sequentially in the orchestrator.** Do NOT dispatch the micro-fix swarm.

## Authorizing Rule Text

From `/tmp/refactor-skill-old/knowledge/execution-playbook.md`, §5.4 Convention Enforcement, violation-count decision table (lines 276–281):

```
| Violation count | Decision | Execution |
|---|---|---|
| 0 | No action | Already compliant. Note in findings.md and move on. |
| 1–4 | **Inline fix** in this refactor | Fix sequentially in the orchestrator. Not worth swarm overhead. |
| 5–10 | **Inline fix** in this refactor | Use Phase 5.3.5 micro-fix swarm (parallel sub-agents). |
| 11+ | **Separate follow-up ledger entry** | Create a dedicated ledger `split_queued` entry, document the full violation list, and mark the refactor as "partial enforcement" in findings.md. |
```

**Precise rule:** "1–4 violations → **Inline fix** in this refactor: Fix sequentially in the orchestrator. Not worth swarm overhead."

At 3 instances, we fall in the 1–4 band. The rule explicitly states the execution path: sequential orchestrator fixes. Swarm dispatch (5.3.5) is reserved for the 5–10 band and higher, where the parallelism ROI justifies the complexity.

## Rationale
The playbook's heuristic recognizes that sub-agent spawn and coordination overhead is only justified when fixing 5+ violations. Below that threshold, the orchestrator's linear context is faster and simpler. The rule quote is the sole determining factor; no judgment required.
