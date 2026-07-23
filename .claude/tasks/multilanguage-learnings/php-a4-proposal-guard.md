# PHP A4 proposal and exact-guard learning/economics packet

Status: isolated language-local implementation for `extract-enum`,
`prevent-regression`, `propose-boundary`, `propose-folder-reorganization`, and
`unify-shadows`; shared publication surfaces remain untouched.

## Outcome contract

All five consumers validate a SHA-256-bound `php-a4-acceptance-v1` decision
against already-produced PHP evidence. They verify current cited source,
Composer identity, project-owned Composer lint/test obligations, PHP lint,
exact smoke output, and source preservation. They never invoke an A1/A2/A3
provider or detect their own candidate, seam, cluster, or shadow.

- `extract-enum` consumes one A3 `find-implicit-state` finding already promoted
  by its `extract_enum_candidate` human verdict. It emits a read-only exact
  field/caller/case proposal and retains a further migration-approval gate.
- `prevent-regression` consumes that accepted enum proposal plus a separately
  accepted migrated source fingerprint. It stages, but does not install, one
  Reflection-based exact-property enum-type guard. Its verifier proves the
  migrated tree passes, a string-type reversion still parses without the guard,
  and the staged guard catches that regression in a disposable copy.
- `propose-boundary` consumes accepted A3 Composer class/method facts plus a
  human-selected seam, public API, namespace, and compatibility plan.
- `propose-folder-reorganization` consumes the A3 source inventory plus a
  human-selected three-file move map, convention, namespace, and shim policy.
- `unify-shadows` consumes one A3 human-confirmed semantic-duplication finding
  plus a separately selected canonical member and consolidation shape.

Clean state, cohesive-boundary defer, no-convention defer, exact A3
`keep_separate`, and no-guard-policy defer remain successful terminal outcomes.
Partial, stale, tampered, unaccepted, source-diverged, tool-missing, native-
failing, unsafe, or symlinked inputs replace any prior ready artifact with a
visible refusal. Every ready proposal remains read-only and human-owned.

## Native, closure, and lifecycle proof

The native matrix is Composer-owned and runs without install/update/network:

```text
composer --no-plugins --no-scripts validate --no-check-publish --no-interaction
php -l <each cited PHP source>
php tests/lint.php
php tests/smoke.php
# exact stdout: php-semantic-ok
```

`tests/test_php_a4_proposal_guard.py` proves every positive final artifact,
non-positive outcomes, missing PHP/Composer, partial evidence, stale/tampered
acceptance, source preservation, valid -> refused -> valid replacement, the
native guard oracle, and copied execution from an `outside-checkout` skill
tree using this checkout's explicit `.venv/bin/python`. The copied contract is
the selected skill directory plus sibling `_php-proposal`; no repository
module, ambient Python package, detector, install, or network access is used.

Final copied closures (skill plus the 366-line helper) are:

| Skill | Files | Bytes | Manifest SHA-256 |
|---|---:|---:|---|
| extract-enum | 12 | 169,834 | `665a2c572380a91617410636eaa835dba45a9c403c9f41174bb36d14d022961d` |
| prevent-regression | 23 | 194,559 | `09b12425ff3632c6f82c0a5e5dcfca4388e046ae046c08fef581697ed956ba4d` |
| propose-boundary | 10 | 232,074 | `59a50aecbc39a0e065ee955aa98208abae48425740dc8340db4ce3cb23f8bf9a` |
| propose-folder-reorganization | 13 | 252,491 | `acef011e9304f12f42917d0866ae27a19ffabad070fb91cec2dc6e711cf1c5c8` |
| unify-shadows | 14 | 185,475 | `475ee93bee8e4cf9c42e987149f717e011f1524d0d462a6414d0d54ec7d09e4a` |

The manifest hashes sort `repository-relative path + NUL + file SHA-256 + LF`.
Putting identical helper bytes adjacent in a literal per-skill closure changes
neither closure files nor bytes, so measured closure growth is **0%**.

## ML-025 economics

The common helper owns only acceptance/path validation, PHP/Composer preflight,
current-source/native/source-preservation checks, and atomic terminal bundles.
All five skills consume it immediately; selection policy and final schemas stay
consumer-local.

- helper: 366 physical / 320 nonblank LOC;
- six adapters plus focused test: 1,453 physical / 1,280 nonblank LOC;
- one shared helper: 1,819 physical / 1,600 nonblank LOC;
- five literal per-skill helpers: 3,283 physical / 2,880 nonblank LOC; and
- reduction: **44.59% physical / 44.44% nonblank**, above the 25% gate.

Three alternating warm five-skill cohorts compared the canonical shared helper
with byte-identical helpers placed adjacent in each literal skill closure.
Shared times were `[9.425207, 9.220512, 9.425285]` seconds; literal times were
`[9.077840, 9.186508, 9.106710]` seconds. Medians were `9.425207` and
`9.106710` seconds: shared growth **+3.50%**, inside the +10% gate.

## Transferable boundary

The reusable mechanism is accepted-evidence hygiene, not a PHP proposal schema.
It is economical because all five consumers need the same refusal, native, and
artifact lifecycle while retaining different human decisions and outputs.
Composer PSR-4/direct-symbol evidence still does not prove framework wiring,
reflection, traits, inheritance, dynamic dispatch, external callers, behavioral
equivalence, domain closure, storage/wire compatibility, semver safety, or a
safe refactor. A future consumer needing those facts should require a stronger
accepted producer, not widen this helper or rerun detection downstream.
