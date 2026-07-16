# WP5 Slice 0 evidence — executable oracles and artifact contracts

Functional implementation revision:
`84bd5ef9285138e89922347413f297bf4c84e08a`.

This record covers only IM-1 and IM-2. It does not claim any WP5 acceptance
criterion complete and does not cross the WP4 gate for parser-backed Slice 5.

## Delivered boundary

- A copied, machine-path-redacted prototype oracle freezes AR-1 through AR-12,
  including deterministic digest/set/ratchet semantics and the defects that
  must be reversed.
- Closed schema-version-1 validators cover the sweep manifest, provider
  observation, diff, judgment, packet, and typed failure envelopes. Missing and
  unknown fields, invalid cross-field states, identity collisions, unsafe paths,
  nullable packets, overlapping diff sets, oversized output, and executor
  self-attestation are rejected.
- Canonical JSON uses sorted compact UTF-8 with exactly one terminal newline,
  rejects non-finite/non-JSON values, and supplies deterministic SHA-256.
- Prototype evidence is never imported at runtime. The new package contains no
  provider execution, writer, CLI, migration, judgment application, harness, or
  parser-backed detector wiring.

The original prototype manifest SHA-256 remains recorded as provenance. Its
machine-local target was normalized to `/workspace/engineering-skills`; the
copied fixture has its own hash and an explicit normalization reason.

## Verification

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q       -p no:cacheprovider tests/test_sweep_slice0_characterization.py       tests/test_finding_identity.py tests/test_capability_consumers.py
    25 passed in 0.20s

    .venv/bin/ruff check scripts/sweep       tests/test_sweep_slice0_characterization.py
    All checks passed!

    .venv/bin/python scripts/specs.py coverage portable-batch-sweep
    Summary: 2/28 implemented; 0 checkmark lag, implementation-ahead, or orphan refs

    .venv/bin/python scripts/specs.py inventory-check portable-batch-sweep
    Status: CLEAN

Adversarial bad documents are evaluated before any good document in the test
loop. Unknown-field attacks cover all six top-level schemas, and nested objects
also use exact key contracts.

## Content addresses after coordinator binding

| Path | Bytes | SHA-256 |
|---|---:|---|
| `scripts/sweep/__init__.py` | 726 | `ae4d5bae6c67fb5f531d0d61aaaf00ad9db8c8f1fd0bd3c98d9478bfd3b22e2d` |
| `scripts/sweep/schemas.py` | 25,230 | `759f8b11b5a5f2a0c48007a680cac72c15a3a8d123efc76e980577092d1ef173` |
| `scripts/sweep/serialization.py` | 1,119 | `60279b553ed5f78864dfa76a09ad453089174f415da0f7e93e4afceed9e0d950` |
| `tests/test_sweep_slice0_characterization.py` | 11,293 | `295d5c993658726653834220e17270416d5ba02e4e20e7898ee8a2ad8f6cac4e` |
| `characterization.json` | 2,250 | `d9f049ab5e8bbb5bf54e0e49d274169bce7d202abb2734487b0e7668c7c5abfa` |
| `prototype-digest.md` | 312 | `0332e783c419099db5b721cb74f139ac90d2f7ee2161bd62609224b31ae189ea` |
| `prototype-manifest.json` | 2,161 | `0b94365c14880e80dce538e9e4a812d809d98b5aa224b2fa28721253885dafff` |
| `schema-cases.json` | 9,387 | `f280bfd4905b469da2c5a6229e3d475480c7ad237dd283af7eedd84f6e92bd13` |

## Deferred by design

IM-3 through IM-11 remain open. IM-12 through IM-16 remain hard-gated until the
master tracker records WP4 as verified with fresh evidence. ADR 0003 and AC-8.9
ownership remain unchanged.
