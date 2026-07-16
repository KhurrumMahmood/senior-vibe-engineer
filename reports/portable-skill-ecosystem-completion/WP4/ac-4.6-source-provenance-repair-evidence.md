# WP4 AC-4.6 source/provenance and measurement repair

Implementation and exact evidence revision:
`01874df5d8d73b5fc74bf7a6e04fa51936a694ff`.

Relevant source-tree SHA-256:
`92aca126917a35a078f4b3d40f72de46c2e707a4580def146094425cd4cc70f0`.

This is implementer evidence, not the independent PASS required to move WP4
to `verified`. It supersedes the current-evidence claims in
`ac-4.6-integrity-repair-evidence.md` and addresses every defect in
`verification-attempt-4.md`.

## Repairs delivered

1. One committed-source scope now covers the benchmark, cold probe,
   dependencies, adapter implementation, analysis goldens/provenance, and the
   consumed D3 portfolio corpus. Report generation rejects a dirty file in any
   of those paths.
2. Comparison resolves the declared revision as a real Git commit and
   re-derives the D3 corpus tree hash, external manifest, normalized source,
   normalized license, raw-upstream hashes, normalization contracts, sizes,
   lines, and safe paths from committed blobs. Coordinated two-report mutations
   with recomputed stable hashes are rejected.
3. The stable projection contains the corpus path/hash and complete external
   provenance contract. Runtime, memory, install, pass-state, budget, fixture,
   run-count, revision, source-tree, platform, and tool versions remain
   independently validated.
4. Toolchain provenance is schema-checked and must agree with both the actual
   execution record and the pinned platform contract. This closes an additional
   implementer-found inconsistency attack.
5. Warm runtime is measured without `tracemalloc` instrumentation; peak Python
   allocation is measured in a separate deterministic run. The old method
   mislabeled instrumentation overhead as provider runtime under x86 emulation.
   Cold time still uses a fresh subprocess and includes startup/provider load.
6. Fact serialization avoids recursive `dataclasses.asdict` deep copies. The
   stable fact/result hashes are unchanged.

## Exact environments

- Darwin-arm64: Apple M1, Darwin 25.5.0/macOS 26.5.1, Python 3.11.10,
  Tree-sitter 0.26.0, tree-sitter-language-pack 1.12.5.
- Linux-x86_64: Ubuntu 22.04.5 LTS under the existing Lima x86_64/QEMU VM,
  Linux 5.15.0-185, Python 3.11.15, Tree-sitter 0.26.0,
  tree-sitter-language-pack 1.12.5.
- Exact Git bundle SHA-256:
  `afc5dacdc8af9f0b657beb2f4a43152eaa73a248491b61bc1bc60ef91bac9e8c`.
  The Linux checkout was
  `/tmp/wp4-source-01874df`, preserving the commit object and avoiding the
  slower host-mounted/persistent-disk path.

The Linux benchmark was run only after terminating two accidental unbounded
host repository scans. While those scans consumed roughly 140% host CPU,
diagnostic reports missed the cold budget (2.0–2.8 seconds); those failed
diagnostics are intentionally disclosed and were not promoted as evidence.
With the benchmark host isolated from unrelated coordinator work, the first
exact-final-revision run passed with 0.629/0.633-second cold results and low
warm CV. This is the controlled-machine condition under which the predeclared
performance budget is evaluated.

## Exact commands and results

Focused contract suite on both exact-revision checkouts:

    PYTHONDONTWRITEBYTECODE=1 <python-3.11> -m pytest -q -p no:cacheprovider \
      tests/test_analysis_facts.py tests/test_lang_adapter.py \
      tests/test_omnibus_language_adapters.py

- Darwin-arm64: 65 passed in 1.54s.
- Linux-x86_64: 65 passed in 7.83s.

Full repository suite on Darwin after the final implementation/test changes:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
    519 passed, 1 skipped in 27.52s

Each platform ran:

    <python-3.11> scripts/analysis_fact_benchmark.py \
      --source-revision 01874df5d8d73b5fc74bf7a6e04fa51936a694ff \
      --output <platform-report>.json

Both returned `{"passed": true, "violations": []}`. The coordinator ran:

    .venv/bin/python scripts/analysis_fact_benchmark.py \
      --compare-platform-reports darwin-arm64.json linux-x86_64.json \
      --output platform-matrix.json

The matrix returned `{"passed": true, "violations": []}` with
`cross_platform_deterministic: true`.

The final integrity regression command selected ten tests and passed all ten,
including dirty consumed-corpus rejection and coordinated provenance/corpus
forgery rejection. The standalone replay in `adversarial-comparison.txt`
also rejects every attempt-3/4 comparator attack, including the additional
toolchain inconsistency attack.

## Budget and determinism result

| Platform / fixture | Cold | Warm mean | Warm CV | Peak Python | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Darwin-arm64 small | 0.048159s | 0.000475s | 0.049761 | 86,019 B | 33,177,600 B |
| Darwin-arm64 external | 0.050421s | 0.003554s | 0.014953 | 946,226 B | 34,996,224 B |
| Linux-x86_64 small | 0.629167s | 0.008987s | 0.019397 | 86,019 B | 29,224,960 B |
| Linux-x86_64 external | 0.632526s | 0.063796s | 0.002900 | 946,226 B | 31,408,128 B |

Every final evidence result is below the one-second cold/warm, 20% warm CV,
64 MiB traced-Python, 128 MiB RSS, and 25 MB install ceilings. Precision and
recall are 1.0. Both reports share:

- stable result SHA-256:
  `a8c3596589629e79af1a601ae14c620ddb0d0127887225245c30d543311e7674`;
- small facts SHA-256:
  `79ab49d20aa30bd684c96c3b052517a228410f2090473ea6fc639a7f35354f39`;
- external facts SHA-256:
  `6474a8c3e5b945e3d0d4e9269574f8e004a0df4957cc420d83c15c83aaf7a9e4`.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `darwin-arm64.json` | `9ed3d76ee0be2f77873f15ef06f9d6bfb05d98e630aa03596460b2fd94cce039` |
| `linux-x86_64.json` | `8a903bb629b0c27421362fb00faf4a5bfd97fde438ffcacea5f4194ea67c741d` |
| `platform-matrix.json` | `3d6a39aa395ab4c97d64e69448b986427787547c8f589d23cb160f7f2935ad55` |
| `darwin-focused-tests.txt` | `51a5ff71ee55c022deead1aa92b8426303254d798a84d5738fe52bf8f9061e9d` |
| `linux-focused-tests.txt` | `e302edd57c85903dc4d872ba7cce512aba14f82a2ec05faad280b9479531a63d` |
| `adversarial-comparison.txt` | `732a4c20152f3450c976fb8df3f724e65b09060a23107576193528fd0c7c53ec` |

## Acceptance boundary

The implementation now addresses every attempt-4 defect and preserves the
previous independent PASS findings for AC-4.1 through AC-4.5. WP4 may move to
`implemented` after these evidence artifacts and the tracker are committed.
It remains short of `verified` until a fresh read-only verifier launched with
`fork_turns="none"` independently replays AC-4.1 through AC-4.6 at the clean
evidence revision.
