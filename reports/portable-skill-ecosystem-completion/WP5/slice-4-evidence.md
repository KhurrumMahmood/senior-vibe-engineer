# WP5 Slice 4 evidence — IM-9 / IM-10 / IM-11

Evidence date: 2026-07-16.

Final reviewed revision: `02b66ee79dcd3b296b8cfea4436bb84a1671b2d6`,
tree `378e46b5f89a341ab1a3b2fd81094bcfdde4d8ca`. The independent
verifier used an isolated detached clone and left it clean. Its model identity
was Codex based on GPT-5; a more specific model or effort setting was not
exposed.

The verifier first reviewed revision
`ece14a8a8009e0f8070bc2472af4218b338c0c03`, tree
`0e4f2c8a788438e4349532a6a10972b418644ad0`. IM-10 and IM-11 passed;
IM-9 failed only because the parser-child isolation boundary omitted
`socket.getnameinfo`. Revision `02b66ee` changes exactly that isolation list
and its adversarial child-process test. A fresh follow-up at that exact child
revision passed IM-9 and the evaluated AC-5.7 slice with no P0/P1 findings.

## Delivered boundary

- Judgment input is bounded and either advances by at least one complete row
  or fails. Missing, stale, duplicate, unknown, uncertain, or failed outcomes
  block digest, ranking, dashboard, packet, and execution consumers.
- Parser-backed detection fails on DNS/network/model-provider access. The
  final child probe denied all 12 exercised surfaces, including
  `getnameinfo`, `getaddrinfo`, `gethostby*`, socket connect/send operations,
  `urlopen`, and OpenAI/Anthropic imports.
- Status consumes only schema-valid judged digests. The legacy queue remains
  readable; new sweep queue entries retain the closed packet contract.
- Packet ceilings are recomputed from actual regular-file bytes under the
  supplied root. One-byte scope produced ceiling `8001`; `8002` was rejected
  by both queue staging and harness validation.
- Harness verification owns the verification command and independent rescan,
  rejects self-attestation and stale bindings, rechecks exact scope/provider
  battery/registry version before diffing, and rejects out-of-scope edits,
  unexpected findings, or failed verification.
- Parser trusted-root/runtime identity propagates through manifest reads,
  judgment, digest, packet, diff/ratchet, and rescan. Missing or mismatched
  roots reject parser manifests.

## Independent verification

At `ece14a8`:

```text
focused judgment/status/queue/trust suite: 147 passed, 5 skipped
full suite: 758 passed, 10 skipped
Ruff: passed (two pre-existing invalid-noqa warnings in scripts/status.py)
capability registry: 7 consumers clean
skill lint: 76/76 clean
decisions: 34 clean; links resolve
plans: 7 clean
portable-batch-sweep inventory: clean
```

The ten full-suite skips were unavailable live native-tool executions owned by
pending IM-15, not this slice. At final revision `02b66ee`:

```text
targeted isolation tests: 3 passed
direct child isolation probe: 12/12 denied
IM-9: PASS
IM-10: PASS (retained exact-parent verdict)
IM-11: PASS (retained exact-parent verdict)
AC-5.5 evaluated surface: PASS
AC-5.7 evaluated surface: PASS
P0/P1 findings: none
```

This report claims IM-9 through IM-11 only. It does not claim the live
five-host CI boundary, ADR embodiment, or any complete WP5 acceptance
criterion.
