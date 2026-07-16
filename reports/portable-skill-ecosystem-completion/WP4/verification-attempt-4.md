# WP4 fresh-context verification attempt 4

Verifier: `/root/wp4_integrity_verifier`, Codex/GPT-5; exact deployed model
variant not exposed.

Evidence revision: `18e61845fb62fc779c98b4b690311d2d7b99d606`, tree
`daf24feed0728dcbe25799f318b3bc7b4b9b51b3`. Implementation revision:
`e45e009c7dfb3c9e4619ea2aaa5c3bc6ab1b5921`, tree
`70f04b87c6e8b3f475c8c7c39375621f5450d0a6`.

Overall: **FAIL**. AC-4.1 through AC-4.5 pass. AC-4.6 fails two
revision-binding attacks even though the real Darwin and Linux executions are
correct, deterministic, and within budget. WP4 must remain `in_progress`.

## Verdicts

- **AC-4.1 PASS:** interface v1 exposes exactly the six bounded fact families,
  immutable location-bearing facts, version/capability discovery, and no
  framework facts. The production inventory remains 21 consumers.
- **AC-4.2 PASS:** clean pinned D3 replay retained corpus SHA-256
  `da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f`,
  1.0 precision/recall, accepted timing/install/license results, and exact
  timing-independent equality with the WP1 oracle and WP4 record.
- **AC-4.3 PASS:** real-parser replay covered exported functions/const arrows,
  classes, methods, nested functions, JS/TS extensions, JSX/TSX, malformed
  input, and precise locations. The 41-fact TypeScript golden hash reproduced.
- **AC-4.4 PASS:** Python symbols and precise spans, Rust/Go accepted subsets,
  all language goldens, and explicit unsupported capability behavior passed.
- **AC-4.5 PASS:** every attempt-1 missing/malformed/raising tree, absent or
  broken parser, parser and blocking timeout, corrupt result, malformed source,
  unknown extension, registered-extension routing, and unsupported-capability
  attack returned the required typed contextual failure.
- **AC-4.6 FAIL:** platform budgets and the original attempt-3 attacks pass,
  but a consumed D3 input is outside `SOURCE_SCOPE`, and report provenance is
  not fully re-derived from raw committed blobs.

## Independent execution

The verifier began from a clean live evidence revision and used clean detached
evidence/implementation clones plus the disposable Linux VM.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
      -p no:cacheprovider tests/test_analysis_facts.py \
      tests/test_lang_adapter.py tests/test_omnibus_language_adapters.py
    56 passed in 0.77s

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
    510 passed, 1 skipped in 25.98s

Ruff, plan audit, decision audit/link-check, and portable-analysis-substrate
coverage/inventory all exited 0. The D3 candidate results were:

| Candidate | Warm | Install | Precision/recall | License |
|---|---:|---:|---:|---|
| Tree-sitter 0.26.0 / pack 1.12.5 | 0.062113s | 5,089,280 B | 1.0/1.0 | MIT |
| ast-grep 0.44.1 | 0.080364s | 154,339,105 B | 1.0/1.0 | MIT |
| TypeScript API 5.9.3 | 0.604275s | 23,625,066 B | 1.0/1.0 | Apache-2.0 |

Fresh exact-implementation platform results:

| Platform / fixture | Cold | Warm | CV | Peak Python | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Darwin small | 0.084841s | 0.004615s | 0.018057 | 125,288 B | 33,898,496 B |
| Darwin external | 0.084899s | 0.048677s | 0.011530 | 1,183,641 B | 36,028,416 B |
| Linux small | 0.808586s | 0.083060s | 0.008582 | 125,010 B | 28,930,048 B |
| Linux external | 0.957401s | 0.890334s | 0.007456 | 1,183,521 B | 31,490,048 B |

Darwin and Linux focused suites each passed 56 tests. Both used source hash
`8927ef259c15221898187050ef81683cffc41bed39ed77f8cc4f3f23ee0b7361`
and stable result hash
`63f4b893aba9b430a8956e90addc58fc3f169c9ba0722acbcad31286bb0f4272`.
Every cold/warm/CV/Python/RSS/install/precision/recall budget passed.

## Integrity bypass 1: incomplete source scope

`build_report()` consumes and hashes
`tests/fixtures/analysis_portfolio_spike`, but that directory is absent from
`SOURCE_SCOPE`. In a clean implementation clone, the verifier changed only
whitespace in `tests/fixtures/analysis_portfolio_spike/tsconfig.json` and ran:

    .venv/bin/python scripts/analysis_fact_benchmark.py \
      --source-revision e45e009c7dfb3c9e4619ea2aaa5c3bc6ab1b5921 \
      --output /tmp/out-of-scope-dirty-report.json

The command incorrectly passed while retaining source hash `8927ef25...` and
claiming the clean revision. The changed corpus hash was `afa84f5e...` and the
stable hash was recomputed to `40d6d06a...`. A relevant uncommitted benchmark
input can therefore produce passing evidence for a commit that does not
contain it.

## Integrity bypass 2: trusted provenance labels

The existing comparator correctly rejected timing, RSS, install, pass-state,
budget-key/value, fixture/run-count, forged/different revision, stale source,
tool-version, stable-payload, missing/duplicate-platform, and malformed-shape
attacks. It still accepted these one-sided Linux report mutations:

- forged `upstream_raw_sha256`;
- forged `license_upstream_raw_sha256`;
- forged source normalization list;
- forged license normalization list.

It also accepted coordinated two-report changes when the attacker recomputed
both stable hashes:

- `corpus_sha256 = "0" * 64`;
- forged normalized external source `source_sha256`;
- forged normalized external license `license_sha256`.

The comparator validates internal hash consistency but does not load the D3
corpus or external provenance manifest and normalized blobs from the declared
Git revision. Those report fields remain attacker-controlled labels.

## Factually correct committed provenance

Independent upstream replay of Microsoft TypeScript v5.9.3 resolved revision
`c63de15a992d37f0d6cec03ac7631872838602cb` and verified:

- raw `symbolWalker.ts` SHA-256 `6aec8fecf7d57abd557bdbd4a9744ba2a1f3d8fcc9e9b84721158bd4f284300a`;
- normalized source SHA-256 `f468759c595c804f5c1ac171814ee43de0b030fa6d08c527525d6e3a24493306`;
- raw license SHA-256 `a7d00bfd54525bc694b6e32f64c7ebcf5e6b7ae3657be5cc12767bce74654a47`;
- normalized license SHA-256 `527adf9d4c760f7367c2aeffed6a89afba8ba40ea1b0efbc8f56496ad30ea9cf`;
- CRLF-to-LF source normalization and CRLF-to-LF plus trailing-whitespace
  license normalization.

All durable WP4 artifact hashes matched `ac-4.6-integrity-repair-evidence.md`,
the matrix regenerated byte-identically, and every older AC-4.6 narrative is
explicitly superseded. The defect is acceptance integrity, not incorrect
current data.

## Required repair

1. Put every report input, including the D3 corpus, in one source scope used by
   both dirty-state checks and canonical raw-Git-blob hashing.
2. At comparison, derive the D3 corpus hash from raw blobs at the report's
   declared commit.
3. Load the external manifest and normalized source/license blobs from that
   commit, validate both pinned raw-upstream hashes and every transformation,
   and require the embedded report provenance to equal the derived record.
4. Include the entire provenance/normalization contract in the stable
   projection.
5. Add one-sided and coordinated regressions for forged corpus, source,
   license, raw-upstream, and normalization fields.

Automatic policy hooks added verifier/concurrent command telemetry to
`logs/agent_policy/test_runs.jsonl` and an untracked
`logs/agent_policy/friction.jsonl`; the verifier made no repository edits.
