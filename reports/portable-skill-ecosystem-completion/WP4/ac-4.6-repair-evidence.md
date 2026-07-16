# WP4 AC-4.6 repair evidence

> **Superseded after verification attempt 3:** This report preserves the first
> AC-4.6 repair at implementation revision `c4f18fe` and its associated
> platform replay. Attempt 3 found four remaining evidence-integrity defects.
> The authoritative repaired implementation and exact-revision platform
> evidence are recorded in `ac-4.6-integrity-repair-evidence.md`; this file is
> historical and must not be used as the current acceptance record.

Implementation revision: c4f18fed2aac709856069fd952ed13ddc838128b.

This is implementer evidence for fresh-context verification. It does not move
WP4 to verified. The previous independent verifier passed AC-4.1 through
AC-4.5 and failed AC-4.6; this repair addresses its two remaining findings:
execution-derived cross-platform evidence and a representative external-shaped
large fixture.

## Delivered repair

- scripts/analysis_fact_benchmark.py now derives the running platform from the
  executing system, embeds an exact source revision and source-tree hash,
  hashes a stable timing-independent result projection, and rejects missing,
  duplicate, stale, malformed, wrong-version, or divergent platform records.
- tests/fixtures/analysis_facts/platform-contract.json requires executed
  Darwin-arm64 and Linux-x86_64 records with Python 3.11, Tree-sitter 0.26.0,
  and tree-sitter-language-pack 1.12.5. Windows is outside this release
  contract.
- The repeated-function fixture was retired. The large benchmark is Microsoft
  TypeScript v5.9.3 src/compiler/symbolWalker.ts, upstream revision
  c63de15a992d37f0d6cec03ac7631872838602cb, raw SHA-256
  6aec8fecf7d57abd557bdbd4a9744ba2a1f3d8fcc9e9b84721158bd4f284300a,
  normalized SHA-256
  f468759c595c804f5c1ac171814ee43de0b030fa6d08c527525d6e3a24493306,
  7,961 bytes and 216 lines. Its Apache-2.0 license, normalizations, hashes,
  size, and selection rationale are validated before execution.

## Exact source and environments

The Darwin report was generated from the clean implementation checkout before
evidence files were added. The Linux guest received a git archive of the same
commit; archive SHA-256:
6554a53181095e79b6c65bc8d4f776663d8c28cb34336fed0ef0a42a7f46a250.
Both reports independently computed source-tree SHA-256
d37f8dccebe14660a3332dd77ab4e67e2b0a27561b5647a96265a3680925aefc.

Darwin: Apple M1, macOS 26.5.1 / Darwin 25.5.0 arm64, Python 3.11.10.
The full record is darwin-machine.txt.

Linux: Ubuntu 22.04.5 LTS, kernel 5.15.0-185, x86_64, Python 3.11.15,
executed in Lima 2.1.4 with QEMU 11.0.2. The official Ubuntu Jammy x86_64
image SHA-256
7cd6b514bcc6c43180270f7817efecf140297edd0768351fddfbed9858bd21b7
matched Ubuntu's downloaded SHA256SUMS. Python came from the Deadsnakes Jammy
PPA (fingerprint F23C5A6CF475977595C89F51BA6932366A755776); runtime packages
came from the exact requirements.txt. The full record is linux-machine.txt.

At evidence creation the only dirty paths were these new WP4 artifacts and the
tracker update. No implementation path changed after platform execution.

## Commands and results

Implementation-state gates before the implementation commit:

    .venv/bin/ruff check scripts/analysis_fact_benchmark.py tests/test_analysis_facts.py
    All checks passed

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
      tests/test_analysis_facts.py tests/test_lang_adapter.py
      tests/test_omnibus_language_adapters.py
    55 passed

    .venv/bin/python -m pytest -q
    509 passed, 1 skipped

    .venv/bin/python scripts/specs.py coverage portable-analysis-substrate
    9 implemented, 5 documented, 0 partial/lag/ahead/orphans

    .venv/bin/python scripts/specs.py inventory-check portable-analysis-substrate
    CLEAN

Exact clean-archive focused command on both platforms:

    PYTHONDONTWRITEBYTECODE=1 <python-3.11> -m pytest -q -p no:cacheprovider
      tests/test_analysis_facts.py tests/test_lang_adapter.py
      tests/test_omnibus_language_adapters.py
    Darwin-arm64: 55 passed in 1.32s
    Linux-x86_64: 55 passed in 34.18s

Exact report and comparison commands:

    <python-3.11> scripts/analysis_fact_benchmark.py
      --source-revision c4f18fed2aac709856069fd952ed13ddc838128b
      --output <platform-report>.json
    Both: passed true, violations empty

    .venv/bin/python scripts/analysis_fact_benchmark.py
      --compare-platform-reports darwin-arm64.json linux-x86_64.json
      --output platform-matrix.json
    Result: passed true, violations empty

## Budget and determinism result

| Platform / fixture | Cold | Warm mean | Warm CV | Peak Python | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Darwin-arm64 small | 0.078612s | 0.004544s | 0.017285 | 125,333 B | 32,587,776 B |
| Darwin-arm64 external | 0.083036s | 0.048137s | 0.008607 | 1,183,452 B | 34,439,168 B |
| Linux-x86_64 small | 0.829035s | 0.083732s | 0.025295 | 125,265 B | 28,508,160 B |
| Linux-x86_64 external | 0.919692s | 0.878388s | 0.015647 | 1,183,586 B | 31,256,576 B |

Every row passes the predeclared 1.0-second cold/warm, 20% CV, 64 MiB traced
Python, and 128 MiB RSS ceilings. Both platforms produced stable-result
SHA-256 63f4b893aba9b430a8956e90addc58fc3f169c9ba0722acbcad31286bb0f4272.
The small fact SHA-256 is
79ab49d20aa30bd684c96c3b052517a228410f2090473ea6fc639a7f35354f39;
the external fact SHA-256 is
6474a8c3e5b945e3d0d4e9269574f8e004a0df4957cc420d83c15c83aaf7a9e4.
The executable comparison reports cross_platform_deterministic true.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| darwin-arm64.json | 4c8c6944c3051f05cd5700cfe912846878b97524481ff8343e90f06eab367179 |
| linux-x86_64.json | 7b43953f29db1fe6817c68542e47ad8d6556614b2f6b98536af78c417fa3386c |
| platform-matrix.json | 9fba8d663a67b2956cd58d2e468329fb01e54a92415fd6e3ba5adf1c9edf24de |
| darwin-machine.txt | 5dd3491b820aba6293aca43d94c6f2662ce6022367e7a1b0757a089357e4d254 |
| linux-machine.txt | d631965689effb66944b86ae0b7c3ea1cd726bc556f156794b84332d5d8253a4 |
| darwin-focused-tests.txt | 708c95675a07bc7a7b4333c239df98867761a53c2f26ed572df9c93107a2d508 |
| linux-focused-tests.txt | 343aae74be788814d7f713cb5d345146bc0af5649d1617379d4a4e40db75bc12 |
| linux-benchmark-command.txt | 700001fc896f3a9ccb9e482749308dccf00fc713c7739cecc43f082d12a90f40 |

## Remaining acceptance boundary

This supports implementer completion of AC-4.6 and preserves the previous
independent PASS evidence for AC-4.1 through AC-4.5. WP4 remains implemented
until a new fork_turns:none read-only verifier reruns and issues PASS for every
AC-4.1 through AC-4.6 at the clean evidence revision.
