---
name: diagnose
description: Build a trustworthy debugging loop for hard bugs, regressions, and intermittent failures before changing code. Use when a symptom is unclear, a bug has not been reproduced, a performance regression needs measurement, or a fix would otherwise be based on guesswork.
argument-hint: "<symptom-or-bug-description>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: maintenance
job: diagnose
best_for: |
  Hard bug, failing command, performance regression, intermittent
  failure, missing reproduction, and "something is broken but we do not
  know why" work. Best when the first valuable output is a fast feedback
  loop and a root-cause explanation, not a refactor plan.
not_for: |
  Obvious one-line fixes with an already reproduced test - fix directly.
  Known cleanup clusters from a find-* report (use /fix-workflow or
  /refactor-subsystem). Broad architecture improvement without a live
  symptom (use /gut-check, /architecture-fit, or a matching find-* skill).
escalate_to: |
  /fix-workflow once the root cause is understood and the fix shape
  matches an existing cleanup playbook; /prevent-regression when the
  final post-mortem identifies a repeatable guardrail.
language: any
framework: any
lanes: [incident, maintenance]
stage: execute
entrypoint: true
consumes: [symptom, logs_or_report, repo_context]
produces: [diagnosis_report, reproduction_loop, regression_test_or_seam_gap_finding]
evidence_required: [reproduction_or_reason, root_cause, fix_verification, cleanup_check]
risk_triggers: [production, customer, performance_regression, intermittent]
max_overhead: "Stop after 30 minutes without a credible loop; write what was tried and what artifact/access is missing."
---

# /diagnose

You are the debugging orchestrator. Your first job is to create a
feedback loop that can prove the user's symptom exists. Code changes
come after that loop, not before it.

Write an index report under `reports/diagnose/scan-<TS>/diagnosis.md`,
plus the evidence files listed below. Use the host project's normal
runtime (`.venv/bin/python` when this ecosystem is running its own
scripts). Read `CONTEXT.md` and relevant ADRs when domain terms or
architectural choices affect the symptom.

## Phase 0 - Frame

Record:

- the user-visible symptom;
- what "fixed" would look like;
- affected subsystem/workflow, if known;
- whether the risk triggers include production, customer impact,
  performance, data corruption, or intermittency;
- evidence already in hand: tracebacks, logs, prior fix attempts, and
  exact commands from the conversation;
- the reporter's suspected cause - recorded as one hypothesis among
  several, never as a finding.

If the symptom uses fuzzy domain language, resolve it against the host
project's glossary before writing tests or probes.

## Phase 1 - Build The Loop

Spend disproportionate effort here. A usable loop is fast, specific,
repeatable, and runnable by an agent.

Try loop shapes in this order:

1. Focused failing test at the nearest public interface.
2. Management command, CLI, service call, or script with fixture input.
3. HTTP/curl check against a local server.
4. Headless browser script for UI-visible failures.
5. Replay of a captured artifact: request payload, cached HTML, export,
   log excerpt, fixture, or traceback.
6. Minimal harness around one service with mocked external edges.
7. Stress loop for intermittent failures.
8. Differential loop: old/new config, branch, data sample, or provider.

If no credible loop is possible, stop and write `reproduction.md` (the
`reproduction_or_reason` evidence) with what was tried and which
artifact, access, or environment is missing. Do not continue into
speculative fixes.

## Phase 2 - Reproduce And Minimize

Run the loop enough times to trust it.

Confirm:

- it fails for the same symptom the user reported;
- it is deterministic, or the reproduction rate is high enough to debug;
- the assertion captures the precise failure, not a nearby crash;
- setup cost is low enough to rerun after every probe.

Minimize only while preserving the real failure mode. A tiny test that
does not exercise the production call path is a trap, not evidence.

Record the loop in `reproduction.md`: the exact loop command and one
pasted failing run. For intermittent symptoms, also record the observed
fail rate as N failures over M runs. Assertion without a transcript
does not count.

## Phase 3 - Hypotheses

Before probing, write three to five ranked hypotheses. Each one must be
falsifiable:

```text
If <cause> is true, then <probe/change> will make <observable outcome>.
```

Prefer hypotheses that distinguish between boundaries: input shape,
query/filtering, state transition, external provider, cache, async
lifecycle, permissions, or presentation layer.

## Phase 4 - Probe

Probe one hypothesis at a time. Use the least noisy tool that can
falsify it:

- debugger/shell inspection when practical;
- narrowly tagged debug logs at boundary points;
- timing/profile/query-plan measurements for performance bugs;
- differential runs for config, provider, or data-dependent behavior.

Every temporary debug line must include one unique prefix such as
`[DIAG-YYYYMMDD-a1]`. Remove it before done, and grep for the prefix in
the cleanup phase.

Before any fix, name each remaining hypothesis and the observation that
rules it out. Any hypothesis that cannot be ruled out is named in
`root-cause.md` as residual uncertainty. Consistent evidence is not
discriminating evidence.

If every hypothesis is falsified, return to Phase 3 and re-rank the
hypotheses using the new observations. After two full cycles without a
confirmed cause, stop and write up the eliminated space as partial
findings.

## Phase 5 - Fix

Write or preserve the regression test before the fix when there is a
correct seam. A correct seam exercises the same bug pattern through the
interface that real callers use.

If no correct seam exists, document that as an architecture finding in
the report, then make the smallest safe fix and recommend the follow-up
skill that should create the missing seam.

Do not broaden into adjacent cleanup unless the cleanup is necessary to
make the fix correct or testable.

## Phase 6 - Verify And Learn

Before declaring done:

- rerun the original loop and the minimized regression, and paste the
  passing rerun output of the same command into `verification.md`;
- run the narrowest meaningful touched tests;
- remove every `[DIAG-...]` probe, then grep for the prefix and record
  the grep command and its output in `cleanup-check.md`;
- delete throwaway harnesses or move them under an explicit report path;
- write `root-cause.md`: the falsifiable Phase 3 statement that was
  satisfied, the confirming probe's exact command and its pasted
  observed output, and - where feasible - a cause-toggle demonstration
  (the loop fails with the cause present, passes with it neutralized)
  recorded before the fix was written. A one-sentence narrative without
  a pasted probe is not a root cause;
- answer: what would have prevented this?

If verification fails, the root cause is unconfirmed - return to
Phase 3; do not patch the fix.

If the answer is "a lint/test/pattern would have caught it", recommend
`/prevent-regression`. If the answer is "the code had no durable test
surface", recommend the matching EXPLAIN or REFACTOR skill.

## Evidence Manifest

The report directory must contain:

```text
reports/diagnose/scan-<TS>/
├── diagnosis.md
├── reproduction.md
├── root-cause.md
├── verification.md
├── cleanup-check.md
└── evidence.json
```

```json
{
  "skill": "diagnose",
  "scan_id": "scan-<TS>",
  "evidence": {
    "reproduction_or_reason": "reproduction.md",
    "root_cause": "root-cause.md",
    "fix_verification": "verification.md",
    "cleanup_check": "cleanup-check.md"
  }
}
```

Then run:

```bash
.venv/bin/python scripts/evidence_gate.py check --skill diagnose --scan-dir reports/diagnose/scan-<TS>
```

The gate must exit 0 before the diagnosis is reportable. On exit 1, fix
the named gap and re-run; do not proceed past a failing gate. Paste the
gate's summary line in your final reply.

## Diagnosis Index Shape

```markdown
# Diagnosis: <symptom>

## Symptom
## Reproduction
## Root cause
## Fix
## Prevention follow-up
```
