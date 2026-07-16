# WP4 AC-4.6 evidence-integrity repair

Implementation revision: `e45e009c7dfb3c9e4619ea2aaa5c3bc6ab1b5921`.
Relevant source-tree SHA-256:
`8927ef259c15221898187050ef81683cffc41bed39ed77f8cc4f3f23ee0b7361`.

This is implementer evidence, not the independent PASS required to move WP4
to `verified`. It supersedes the current-evidence claims in
`ac-4.6-repair-evidence.md` and closes all four defects reported by
`verification-attempt-3.md`.

## Repairs delivered

1. `scripts/analysis_fact_benchmark.py` now recomputes every precision,
   recall, cold-time, warm-time, variance, traced-memory, RSS, and install-size
   budget when comparing reports. It requires the exact declared budget set,
   fixture set, and run count, and rejects a report whose claimed
   `passed`/`violations` state disagrees with the recomputed result.
2. Report generation requires a clean relevant source scope at a full current
   Git commit. Comparison resolves each declared revision as a commit in the
   repository and recomputes the relevant source-tree hash from its raw Git
   blobs. Matching arbitrary 40-character labels are therefore rejected.
3. `implementation-evidence.md` and `ac-4.6-repair-evidence.md` explicitly
   mark their older schema-v1/synthetic or pre-attempt-3 AC-4.6 claims as
   historical. This file and its linked schema-v2 records are the current
   implementer evidence.
4. The external-corpus manifest records the raw upstream TypeScript license
   SHA-256
   `a7d00bfd54525bc694b6e32f64c7ebcf5e6b7ae3657be5cc12767bce74654a47`
   and validates both transformations in order: CRLF-to-LF conversion and
   trailing-whitespace removal. The normalized license SHA-256 is
   `527adf9d4c760f7367c2aeffed6a89afba8ba40ea1b0efbc8f56496ad30ea9cf`.

The focused tests reproduce the attempt-3 attacks by changing cold time, RSS,
install size, and both source revisions. The first three are rejected because
the recomputed violation set disagrees with the report; the forged revision is
rejected because it is not a repository commit. The captured result is
`adversarial-comparison.txt` and ends with `ALL ATTEMPT-3 ATTACKS REJECTED`.

## Exact source and environments

Both platform runs used implementation commit
`e45e009c7dfb3c9e4619ea2aaa5c3bc6ab1b5921` and independently obtained source
hash `8927ef259c15221898187050ef81683cffc41bed39ed77f8cc4f3f23ee0b7361`.
The working-tree and committed-tree source hash agreed before evidence
generation. The only dirty paths while assembling this record were the WP4
evidence artifacts and authoritative tracker update; no implementation path
changed after either platform execution.

- Darwin-arm64: Apple M1, Darwin 25.5.0/macOS 26.5.1, Python 3.11.10,
  Tree-sitter 0.26.0, tree-sitter-language-pack 1.12.5.
- Linux-x86_64: Ubuntu 22.04.5 LTS under Lima 2.1.4/QEMU 11.0.2, Python
  3.11.15, Tree-sitter 0.26.0, tree-sitter-language-pack 1.12.5. The official
  Ubuntu image SHA-256 was
  `7cd6b514bcc6c43180270f7817efecf140297edd0768351fddfbed9858bd21b7`.
  The exact source was transferred as Git bundle SHA-256
  `83d17539ca76b7d070e5eb0373e4b087dd4b98707317e684aec85578d7e4a379`,
  preserving the real commit object needed by the source-binding checks.

## Commands and results

Focused contract suite, run from the exact implementation revision on both
platforms:

    PYTHONDONTWRITEBYTECODE=1 <python-3.11> -m pytest -q -p no:cacheprovider \
      tests/test_analysis_facts.py tests/test_lang_adapter.py \
      tests/test_omnibus_language_adapters.py
    Darwin-arm64: 56 passed in 0.74s
    Linux-x86_64: 56 passed in 9.91s

Live performance is an acceptance command rather than a repeated unit-test
timing dependency. Each platform ran:

    <python-3.11> scripts/analysis_fact_benchmark.py \
      --source-revision e45e009c7dfb3c9e4619ea2aaa5c3bc6ab1b5921 \
      --output <platform-report>.json
    Both: passed true; violations empty

The coordinator then ran:

    .venv/bin/python scripts/analysis_fact_benchmark.py \
      --compare-platform-reports darwin-arm64.json linux-x86_64.json \
      --output platform-matrix.json
    Result: passed true; violations empty; cross_platform_deterministic true

The comparator unit tests exercise exact recomputation and tamper rejection
without depending on repeated QEMU performance measurements. The standalone
benchmark above is the live budget gate.

## Budget and determinism result

| Platform / fixture | Cold | Warm mean | Warm CV | Peak Python | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Darwin-arm64 small | 0.088782s | 0.004727s | 0.026014 | 124,953 B | 32,931,840 B |
| Darwin-arm64 external | 0.083894s | 0.048585s | 0.008685 | 1,183,586 B | 34,930,688 B |
| Linux-x86_64 small | 0.808382s | 0.081600s | 0.009251 | 125,601 B | 28,819,456 B |
| Linux-x86_64 external | 0.926453s | 0.865938s | 0.010670 | 1,183,588 B | 31,502,336 B |

Every result is within the predeclared one-second cold/warm, 20% CV, 64 MiB
traced-Python, 128 MiB RSS, and 25 MB install ceilings. Both reports share:

- stable result SHA-256:
  `63f4b893aba9b430a8956e90addc58fc3f169c9ba0722acbcad31286bb0f4272`
- small facts SHA-256:
  `79ab49d20aa30bd684c96c3b052517a228410f2090473ea6fc639a7f35354f39`
- external facts SHA-256:
  `6474a8c3e5b945e3d0d4e9269574f8e004a0df4957cc420d83c15c83aaf7a9e4`

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `darwin-arm64.json` | `030b97e855d5547cf9a86b9e5c65795a20abde1f8bd384ae87f940b2b2400718` |
| `linux-x86_64.json` | `425665043c13897f05a07e11adf0270102435264cc5928c4a6c70b0b3cd1d561` |
| `platform-matrix.json` | `bc93ec61eb8433794c3444c370ad8dd4b62837efedf0acfcee8e7daaa697ec4b` |
| `darwin-focused-tests.txt` | `aacfea503fe5fe2403a1d7e56062d25fe182d7dec1b382936e22c235c05ee608` |
| `linux-focused-tests.txt` | `e25a10ffe8d8c7b765ba86395909b5ecccd87616495b5b92c07c2900ddb01ede` |
| `adversarial-comparison.txt` | `d02d6b0e56378e508f851fa9d63274ffd9538f5a01381ea2fbc6c9a7b21de9c8` |

The report file hashes differ from the per-report projection hashes stored in
`platform-matrix.json`; the latter intentionally identify the stable report
projection used by the comparator. These artifact hashes identify the exact
durable files in this evidence revision.

## Acceptance boundary

The implementation now addresses every attempt-3 failure and retains the
previous independent PASS findings for AC-4.1 through AC-4.5. WP4 remains
`implemented` until a new read-only verifier launched with `fork_turns=none`
independently reruns the required gates and issues PASS for every AC-4.1
through AC-4.6 at the clean evidence revision.
