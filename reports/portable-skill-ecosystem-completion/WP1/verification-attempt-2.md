# WP1 fresh-context verification attempt 2

Verifier: `/root/wp1_reverification`, Codex/GPT-5. Revision:
`4519e6a4d731147a9c41ae7d4dc9cb62e09f31f1` (clean at start; required
pytest/Ruff commands appended only automatic telemetry, whose full patch and
hashes were reported by the verifier and then removed by the coordinator).
Platform: macOS 26.5.1 / Darwin 25.5.0 / arm64.

Overall: **FAIL**.

| AC | Verdict | Finding |
|---|---|---|
| AC-1.1 | PASS | The versioned registry separates every required vocabulary; a copied registry accepted a data-only Zig addition without validator edits. |
| AC-1.2 | FAIL | Literal/nested/constructor guards improved, but `"python typescript".split()` and `dict(zip(...))` duplicate registries escaped with zero errors. |
| AC-1.3 | FAIL | A shared print-only test satisfied Python and TypeScript `language: any` evidence, and an unrelated nonempty `scripts/unrelated.py` satisfied a TypeScript scan implementation claim. |
| AC-1.4 | FAIL | Most forged/stale/timeout/path/platform probes failed correctly, but a claimant-owned fake executable named `node` printed an allowed version and promoted to `verified`; generic evidence remained capability-agnostic. |
| AC-1.5 | PASS | Accepted ADRs 0038–0042 resolve D1–D5 with alternatives, compatibility/migration, costs, and revisit triggers; audits passed. |
| AC-1.6 | FAIL | Bare/omitted/unsupported/old-version/structural-only claims failed, but one generic print-only file was relabeled and rehashed for all 44 stack cells plus five agent surfaces and the executable CLI returned PASS. |
| AC-1.7 | PASS | Fresh D3 rerun preserved corpus hash, 1.0 precision/recall, explicit unsupported candidates, and every budget; spike evidence preceded D3 acceptance. |

## Exact adversarial reproductions

The consumer guard returned no errors for either duplicate registry:

```python
MY_CATALOG = "python typescript rust go".split()
MY_CATALOG = dict(zip("python typescript".split(), ({}, {})))
```

The strict skill contract accepted one shared test containing only
`print("verified-fixture")` under both Python and TypeScript subject keys and
executed it once. It also accepted this unrelated scan implementation merely
because it was a nonempty recognized script:

```python
# scripts/unrelated.py
print("I do not scan anything")
```

A claimant-owned executable at `<evidence-root>/fake/node` returned
`v22.99.0`; the `node-runtime` probe accepted it because native executable
policy checked only the basename. `evaluate_support` returned `verified`.

Finally, one claim-bound envelope per required floor cell/surface all pointed
at the same generic print-only file and recomputed the canonical hash. The
default executable gate returned:

```json
{"status": "pass", "errors": []}
```

Structural-only mode remained correctly non-promotable with exit 3.

## Baseline and decision evidence

```text
.venv/bin/python -m pytest
439 passed, 1 skipped in 16.38s

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

D1 projected the canonical `which-skill` source to all five surfaces and the
Codex plugin validator passed. The D3 corpus SHA-256 remained
`da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f`.
Warm runtime/install size: Tree-sitter 0.040419 s / 5,089,280 bytes;
ast-grep 0.072832 s / 154,339,105 bytes; TypeScript compiler API 0.630662 s /
23,625,066 bytes. Precision and recall were 1.0 for every supported family.

Key hashes reported by the verifier:

```text
b1635234f7aff520143945ba2b9a84de045f980d1ff05af866b5c73cab824d87  capability-registry.yml
e39f012a230fabd5c3df3bb1a2212833793ad2ab1c8abf862fbd96c0d662f831  capability_registry.py
a2bd9a97890d43f33496fa688ecc5caf8fe8005c12289b5464775192f9b67472  support_evidence.py
16f4445f37765f586563a8b2eba1393b0c4b6cf07767f3f8d7e7e30055e9862d  consumer guard
eaec37c970c564483f8d0ca02325d6b570593b9b627c18865767d862ab922de1  committed D3 report
3143ac45e7f56c99d5fde281fb1709b379381a8e03bfcff755acff9fb6aa2da9  regenerated D3 report
39671f0640ead40ec0c9fbf60df9a4bcad2047d4238c24ea92345cfb0ec8632f  attack-results.json
11b23d44152e2f1c1c8a427590d964aeacfbb7ca6da7880c9d239dbf5be9bad8  generic_claims.json
8399ddb08b844042aa800364287572721408edb04a8c62714ed85dba2984831b  generic print-only test
```

The verifier flagged ADR 0038's generic/cross-cell evidence rejection and the
implementation record's “all four corrected” language as overstated.

Required corrections before a third verification:

1. Reject computed hard-coded stack enumerations such as split/zip/dict forms.
2. Require distinct subject-specific executable evidence for `language: any`
   and an explicit attested scan implementation mapped to every scan target.
3. Resolve native tool probes to registry-discovered executables, not a
   claimant-controlled path with an allowed basename.
4. Reject one artifact/digest reused across unrelated completion-floor cells
   and agent surfaces; floor evidence must be capability/surface-specific.

Final verdict: **WP1 FAIL; do not promote to verified.**
