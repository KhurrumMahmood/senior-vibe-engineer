# Lift report — Got `source/` discovery

Verdict: PASS

| Condition | Predicted | Observed | Grounded result |
|---|---:|---:|---|
| Frozen old skill | 1 | 1 | Evidence passed, but the adapter said JavaScript and emitted no production source root/count; npm tests were preserved and the host stayed clean |
| Current skill | 3 | 3 | Adapter said TypeScript, reported `source=25`, preserved both npm tests, added `npm install`, passed evidence, and left the pinned host clean |

The current probe initially reported Git status from the product worktree
instead of the host. A bounded follow-up ran the exact host command and appended
the correction; it returned no output. This was probe-reporting friction, not a
skill or host mutation regression.

Headline lift: `+2` points at the known defect site, with no command, evidence,
or host-safety regression. Both scores are based on generated artifact facts
and exact command results rather than inferred behavior.
