# WP4 fresh-context verification attempt 3

Verifier: `/root/wp4_final_verifier`, Codex/GPT-5; exact deployed model
variant not exposed.

Evidence revision: `d5fb5f03680cbaf16171b003a76823d3d676222a`, tree
`2e981d6f9a4d70d7284741f2e387110daab99869`. Implementation revision:
`c4f18fed2aac709856069fd952ed13ddc838128b`, tree
`fe0933a3e06763530249ea8a247ea70e51cb546f`.

Overall: **FAIL**. AC-4.1 through AC-4.5 pass; AC-4.6 fails evidence-integrity
attacks. WP4 must remain `in_progress`.

## Verdicts

- **AC-4.1 PASS:** interface v1 exposes the six bounded fact families with
  per-adapter discovery and no framework facts.
- **AC-4.2 PASS:** pinned Tree-sitter runtime and fresh D3 replay preserved
  corpus `da03a77d…`, precision/recall 1.0, and all budgets.
- **AC-4.3 PASS:** real parser coverage passed exports, const arrows, classes,
  nested scopes, JSX, malformed input, locations, and required extensions.
- **AC-4.4 PASS:** Python compatibility/spans, Rust/Go subsets, and explicit
  unsupported capability behavior passed.
- **AC-4.5 PASS:** all prior malformed-root/traversal, missing/broken parser,
  timeout, corrupt-output, unknown-extension, and registry-routing attacks
  returned typed contextual failures.
- **AC-4.6 FAIL:** actual platform execution passes, but the evidence contract
  remains gameable and stale evidence remains active.

## Required repairs

1. `compare_platform_reports()` accepted reports whose cold time, RSS, or
   install size was changed above the declared budget because it trusted
   `passed` and `violations` without recomputing budget compliance.
2. Changing both reports to the same arbitrary 40-character revision label was
   accepted. The label is not bound to a real Git commit and its relevant
   source tree.
3. The tracker still linked `implementation-evidence.md`, which calls the old
   schema-v1 synthetic `analysis-fact-benchmark.json` current. Supersession is
   not explicit.
4. The normalized TypeScript license matches upstream only after CRLF-to-LF
   conversion and trailing-whitespace removal. Provenance records only the
   latter and omits the upstream raw license hash.

The comparator did reject missing, duplicate, stale-tree,
stable-payload-tampered, wrong-tool-version, different-revision, and divergent
stable-result reports.

## Independent execution

Clean evidence-revision archive: full suite 508 passed/2 archive-only skips;
focused suite 55 passed; Ruff, spec coverage/inventory, plan audit, decision
audit, and link check passed. A fresh D3 rerun retained 1.0 precision/recall.

Fresh exact-implementation platform replay:

| Platform | Small cold/warm | External cold/warm | Result |
|---|---:|---:|---|
| Darwin-arm64 | 0.082462 / 0.004664s | 0.089216 / 0.048355s | PASS |
| Linux-x86_64 | 0.835955 / 0.082760s | 0.916737 / 0.890150s | PASS |

Both produced source tree `d37f8dcc…`, stable result `63f4b893…`, small facts
`79ab49d2…`, and external facts `6474a8c3…`. The independently regenerated
matrix passed. The verifier began from a clean live repository; its read-only
commands generated four automatic telemetry lines, which the coordinator
removed exactly before recording this report.
