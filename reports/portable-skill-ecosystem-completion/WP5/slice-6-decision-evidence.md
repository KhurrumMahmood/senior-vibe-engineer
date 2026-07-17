# WP5 Slice 6 decision evidence — IM-16

Evidence date: 2026-07-16.

Exact final reviewed revision:
`b1aaba19a92cdeadbd04176e730262c8a38e7089`, tree
`9ca4c3b2683cee48cab4edb4062c6b28421c9f9b`. The substantive IM-16
implementation is parent commit `b177fa65c266fe787ee8bed040230e1b1f4487cf`;
the sole intervening commit restores checklist syntax for an unrelated status
spec and its existing test marker. The fresh verifier used a clean detached
checkout and made no edits. Its actual model identity was Codex on GPT-5.

## Embodiment result

- ADR 0036 now applies only to the productized `scripts/sweep/`, registry shim,
  status, and queue surfaces. Its `embodied_by` paths name the public CLI,
  commands, manifest, judgment/harness pipeline, consumers, and their exact
  contract tests. No pending productization claim remains.
- ADR 0036's identity statement now matches accepted ADR 0040 and runtime
  schema v2: provider, semantic rule key, language, repository-relative path,
  semantic anchor, and deterministic occurrence; location, severity, volatile
  metrics/messages, and tool versions are excluded.
- ADR 0040 now names both the identity helper and the productized manifest
  reader/writer plus their contract suites. It records explicit v1
  `legacy_ids` migration rather than a pending WP5 obligation.
- The historical `.claude/tasks/sweep-prototype/` remains tracked dogfood
  evidence but is not imported, read, or resolved by product runtime.
- ADR 0003 remains exactly `status: proposed` with
  `pending:portable-skill-ecosystem-completion AC-8.9 formal disposition`.
  WP5 does not take the ordered AC-8.9 ownership.

## Verification

```text
focused decision/identity/manifest implementation run: 62 passed
fresh IM-16 regression: 1 passed
decisions audit: 34 decisions, no drift
decision link-check: 34 decisions, all links resolve
repository-wide spec audit: all 5 specs OK
portable-batch-sweep: zero lag/orphans; IM-16 implementation-ahead before checkmark
status-projection-and-presentation: 10/10, zero lag/ahead/orphans
P0/P1: none
IM-16: PASS
```

This record closes only IM-16. Complete AC-5.1–AC-5.7 verification remains a
separate fresh-context gate.
