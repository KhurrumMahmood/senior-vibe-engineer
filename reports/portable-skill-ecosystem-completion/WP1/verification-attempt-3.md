# WP1 fresh-context verification attempt 3

Verifier: `/root/wp1_final_reverification`, Codex/GPT-5. Revision:
`dde997df002d0fbc2d044fb7a8d712cbfdb74dbe` (implementation `e80456a`;
clean at start; automatic telemetry created by required commands was fully
reported and then removed by the coordinator). Platform: macOS 26.5.1 /
Darwin 25.5.0 / arm64.

Overall: **FAIL**.

| AC | Verdict | Finding |
|---|---|---|
| AC-1.1 | PASS | Registry separates all required versioned vocabularies; data-only Zig registration passed. |
| AC-1.2 | FAIL | Required literal/nested/constructor/split/zip/concatenation variants failed, but simple comprehensions, a generator tuple, a computed split receiver, and `dict.fromkeys(split)` escaped. |
| AC-1.3 | PASS | Invalid/shared/unexecuted subject evidence and incorrect scan attestations failed; a valid distinct two-subject experimental claim executed successfully. |
| AC-1.4 | FAIL | Normal-path fake native tools failed, but prepending the claimant directory to ambient `PATH` made fake `node`, `sg`, and `tsc` appear registry-discovered and allowed experimental promotion. |
| AC-1.5 | PASS | Accepted ADRs 0038–0042 and decision audits remain valid. |
| AC-1.6 | PASS | All 44 cells plus five surfaces remain blocked until the registry-pinned WP8 issuer becomes verified; claim fields and `--no-execute` cannot override it. |
| AC-1.7 | PASS | D3 rerun preserved the corpus, metrics, limitations, and all budgets. |

## Blocking reproductions

The guard returned zero errors for:

```python
WHATEVER = [x for x in "python typescript".split()]
WHATEVER = tuple(x for x in "python typescript".split())
WHATEVER = ("python" + " typescript").split()
WHATEVER = dict.fromkeys("python typescript".split())
```

Absolute claimant-owned fake `node`, `sg`, and `tsc` paths failed under the
normal process `PATH`. When the claimant directory was prepended to `PATH`,
each printed a forged allowed version and `evaluate_support` returned
`experimental, []`. No trusted discovery snapshot/root existed, so ambient
environment mutation redefined “registry-discovered.”

## Successful dependency-boundary probes

The verifier confirmed the WP8 issuer is load-bearing:

```text
id: cross-stack-conformance-v1
owner_wp: WP8
status: unavailable
path: scripts/cross_stack_conformance.py
sha256: null
```

- Distinct Python/TypeScript experimental evidence executed and passed.
- Claim-supplied issuer fields could not unlock `verified`.
- False and one-second-timeout fixtures demoted.
- Well-shaped, generic, reused, and structural-only floor claims all failed.

## Commands and evidence

```text
.venv/bin/python -m pytest -q
445 passed, 1 skipped in 14.70s

.venv/bin/python -m pytest -q tests/test_capability_registry_guard.py \
  tests/test_capability_registry.py tests/test_capability_consumers.py
35 passed in 1.30s

.venv/bin/python scripts/skill_meta.py lint --quiet
OK — 76 skills, 76 declaring new contract

.venv/bin/python scripts/plans.py audit
OK — 5 plans, no drift

.venv/bin/python scripts/decisions.py audit
OK — 34 decisions, no drift

.venv/bin/python scripts/decisions.py link-check
OK — 34 decisions, all links resolve, 22 host-scoped

.venv/bin/python scripts/check_capability_registry_consumers.py
OK — 7 consumers use the canonical capability registry

.venv/bin/ruff check scripts tests
All checks passed!
```

D1 projected the canonical source to all five surfaces and Codex plugin
validation passed. D3 corpus SHA-256 remained
`da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f`;
output SHA-256 was
`69246c29f2d3094e803921af7a66c7b5b166ca69b063e10b608b874a39dd2b55`.
Warm runtime/install size: Tree-sitter 0.038174 s / 5,089,280 bytes;
ast-grep 0.070767 s / 154,339,105 bytes; TypeScript API 0.613703 s /
23,625,066 bytes. All supported precision/recall values were 1.0.

Required corrections:

1. Inspect comprehension/generator bodies and receivers of safe computed
   constructors/methods, including `dict.fromkeys`, rather than only a bounded
   set of outer AST forms.
2. Snapshot trusted executable paths before reading claim evidence (or use
   explicit registry-pinned paths/hashes); claim-controlled `PATH` must not
   redefine tool discovery.

Final verdict: **WP1 FAIL; do not promote to verified.**
