# PHP move-path cohort learning

## Outcome

The bounded PHP mutation cohort is complete for one Composer PSR-4 leaf
namespace-directory move. The frozen pilot move `src/Legacy/` to
`src/Archive/` reaches the final report and mutation boundary, rewrites
`Acme\Legacy` to `Acme\Archive`, updates the exact `tests/smoke.php`
require/use tokens, leaves no stale PHP source identity, and passes both
`php tests/lint.php` and `php tests/smoke.php`.

The implementation remains family-local. It does not justify a shared
mutation provider or universal rewrite schema.

## Toolchain and acquisition

- Python runner: the external product-worktree `.venv/bin/python` supplied by
  the P4 work packet (Python 3.11.10)
- PHP: `/opt/homebrew/bin/php`, 8.4.2; product minimum 8.1
- Composer validation: `/usr/local/bin/composer`, 2.4.0
- Dependency acquisition: none
- Network access: none

Composer 2.4.0 emits the PHP 8.4 deprecation notices recorded in the frozen
baseline, but `composer validate --no-check-publish --no-interaction` exits
successfully. The product adapter reads `composer.json` with the Python
standard library; it neither runs Composer nor installs/updates host
dependencies.

The frozen fixture remains unchanged: 14 files, 4,041 bytes, manifest SHA-256
`2ec21d6a1041218c050da7ff844a529bdce56a92116f705b0613a74f0fd1bad4`.

## Contract and terminal states

- `complete`: exactly one leaf directory remains under one unambiguous,
  string-valued production PSR-4 mapping; all eligible files tokenize; every
  exact rewrite span matches; configured native scripts and the whole-host
  fingerprint pass.
- `partial`: a dynamic old namespace/path occurrence remains in a comment,
  string, reflection identity, variable include, or other non-rewritable PHP
  token context.
- `unsupported`: the move shape, PSR-4 mapping, runtime/config, generated
  input, symlink shape, or excluded-file identity is outside the bounded
  contract.
- `failed`: concrete malformed Composer/PHP input, native verification
  failure, post-apply token failure, or exact-diff/fingerprint failure.

Generated, vendor, build, and Composer `autoload-dev` test files are excluded
from edits. Explicit verification scripts are the narrow exception: they are
tokenized so reviewed require/use references can follow the move and are run
before and after it. An old identity found in any other excluded PHP file
blocks apply as `unsupported`; exclusion never means silent stale state.

The same report destination was proven through complete -> failed -> complete
reruns. A native failure after mutation restores the moved file and consumer;
an injected mutation outside the intended diff is detected by the project
fingerprint and restored too. The copied skill runs with `python -I -S` and
only its own closure plus the explicitly selected PHP binary.

## Reused versus PHP-local mechanics

Reused unchanged from move-path:

- JSON plan loading and virtual after-tree construction;
- exact `Replacement` application and reference reporting;
- dry-run/apply/check lifecycle and report destination;
- git-aware directory movement and staged-path behavior; and
- transaction ordering established by the Go/Java cohorts.

Kept PHP-local:

- Composer production PSR-4 mapping and namespace derivation;
- source, verification-script, and excluded-role classification;
- `token_get_all(..., TOKEN_PARSE)` namespace/name/include/require spans;
- dynamic and excluded old-identity classification;
- PHP script preflight/postflight execution; and
- whole-host expected-manifest fingerprint and rollback.

The whole-host fingerprint mechanism could be reusable, but it has only one
real consumer here. Per the two-consumer and interface-depth gates, it stays
local until another mutation cohort proves identical policy and measurable
benefit.

## Size and economics

Counted adapter-plus-test paths:

- `.claude/skills/move-path/scripts/move_path.py`
- `.claude/skills/move-path/scripts/php_namespace_reference_spans.php`
- `tests/test_php_move_path.py`

Current counted size is 3,391 physical lines / 3,088 nonblank lines:

- shared mover with PHP integration: 2,806 / 2,566
- PHP token helper: 239 / 220
- PHP cohort test: 346 / 302

The PHP cohort adds 1,144 physical lines across those paths (559 mover
additions, 239 helper lines, and 346 test lines; three mover lines removed).
The frozen Java mutation implementation added 1,085 physical lines across its
equivalent paths, so PHP is 5.4% larger rather than at least 25% smaller.

The copied move-path closure is 9 files / 185,800 bytes with manifest SHA-256
`3e55305640614646a496e50d70cfa6f073359ac1bcd89d236a861674cc3e5cf7`.
Against the frozen Java-era closure of 150,367 bytes, this is 23.6% growth,
above the 10% promotion threshold.

Both economics gates therefore fail. That is a concrete reason to retain the
narrow family-local implementation and not promote a shared PHP/Java mutation
platform. The final-output and source-preservation correctness gates pass.

## Limits and next-language guidance

This cohort does not support array-valued/ambiguous PSR-4 mappings, source-root
migrations, nested namespace trees, autoload-dev mutation, dynamic includes,
Composer-generated autoload refresh, PHPStan/Psalm resolution, framework
containers, class renames, or reflection/string rewrites. Those cases remain
partial or unsupported rather than text-replaced.

For the next mutation language, reuse the outer move-path transaction only.
Keep identity derivation, exact syntax spans, excluded-role semantics, and
native proof local. Promote fingerprint or rollback mechanics only after a
second cohort demonstrates the same policy and can reverse the measured LOC
and closure regression seen here.
