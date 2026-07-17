# WP5 Slice 6 live evidence — IM-15

Evidence date: 2026-07-16.

Final exact reviewed revision:
`53778a4f652140fca774acc0d1770f78bbaa3c8f`, tree
`fe6f435ead02447b234bdfb3ac0e58a2fe68d0d8`. The functional live boundary
is commit `6be9234049888df6fd320e14cb9773f97ccf8df9`, tree
`643c3047d8c86cbec0e6a0296af5992a90ac94aa`; the final descendant changes
only the stale exact-command line in the successor spec. The fresh verifier
confirmed ancestry, used clean isolated detached checkouts, and left them
clean. Its actual model identity was GPT-5 Codex.

## Exact tool matrix

| Tool | Version |
|---|---|
| Python | 3.11.10 |
| Ruff | 0.6.9 |
| Node | 22.21.1 |
| npm | 10.9.4 |
| ESLint | 9.38.0 |
| TypeScript | 5.9.3 |
| rustc / Cargo | 1.89.0 |
| Clippy | 0.1.89 |
| Go / Go vet | 1.24.6 |

The verifier confirmed the workflow's setup/install pins match this matrix.
With `SWEEP_LIVE_REQUIRED=1`, missing discovery is a failure rather than a
skip.

## Exact live oracles

- Python: fixed `f2_79c0112b725363f5367a34d9`, new
  `f2_2deb160996a2b02d7891da7c`, persisting
  `f2_306c3f8e0d679aa8de104cf7`.
- TypeScript fixed `f2_485801a771ad1d85440ddbcd` and
  `f2_6a4cc33709ec5b3b1f6dfb40`; no new or persisting findings.
- Rust fixed `f2_0a30d4b2ed757586e5b2af8a` and
  `f2_2d64d3db8dba1ee27aeea997`; no new or persisting findings.
- Go fixed `f2_3ebb34b1a5167a9fcfa0599e`; no new or persisting findings.
- Mixed fixed the exact union
  `f2_0a30d4b2ed757586e5b2af8a`, `f2_1db54af1a533aac716464a57`,
  `f2_2d64d3db8dba1ee27aeea997`, `f2_3ebb34b1a5167a9fcfa0599e`,
  `f2_a49b292322bd714e190d40d0`, and
  `f2_b2d8d610eed0a5b6c897960d`; no new or persisting findings.

All five clean fixtures completed with zero findings. A missing Ruff
executable produced typed `missing_executable`, not a clean manifest. Live Go
1.24.6 diagnostics with the two-line `# ...` driver preamble crossed the final
manifest boundary successfully.

## Boundary proof

- Python, TypeScript, Rust, Go, and mixed fixtures traverse live native and
  parser providers, canonical manifest writing, judgment/digest, packet,
  public `python -m scripts.sweep` rescan, exact diff, and ratchet.
- CLI source revision, dirty flag, and dirty hash are Git-derived. Clean,
  tracked, staged, and untracked states, forged legacy assertions, source
  movement during scan, forged harness evidence, and self-attestation attacks
  all reject correctly.
- An exact-tree `git archive` replay reinitialized the same tree as Git and
  passed the live job. Separate equal-mtime/equal-size overlays across all five
  hosts produced the exact expected deltas, defeating the earlier Git stat-
  cache failure.
- Judgment failures and parser network/model isolation remain blocking; the
  harness independently rechecks source, provider battery, registry, scope,
  command evidence, and manifest bytes.

## Independent verification

```text
required CI-equivalent live command: 11 passed, 17 deselected, 0 skipped
focused provenance/CLI/manifest/pipeline/parser suite: 155 passed, 5 deselected
workflow tests: 7 passed
exact-tree archive live replay: 11 passed, 17 deselected, 0 skipped
same-mtime all-five delta replay: PASS
Ruff: PASS
P0/P1/P2: none
IM-15: PASS
```

The coordinator also ran the combined repository at a later descendant with
the same exact tools, bytecode disabled, and live skips forbidden: 814 passed.
That broad run is corroboration, not a substitute for the independent exact-
revision verdict above. This report claims IM-15 only; ADR embodiment IM-16
and complete WP5 acceptance remain separate.
