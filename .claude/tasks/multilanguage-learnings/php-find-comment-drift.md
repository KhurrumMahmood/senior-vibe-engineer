# PHP find-comment-drift learning

## Outcome

The copied/on-demand `find-comment-drift` closure now carries one bounded PHP
lexical/syntax path. On the frozen pilot it inventories 12 PHP files, analyzes
the six first-party `src/` files, excludes test/generated/vendor/build inputs,
and reports only the narration comment above `InvoiceService.issue()` to
`reports/find-comment-drift/php-pilot/detections.jsonl` and `report.json`.
Symlink inputs are inventoried but never followed.

The PHP path separates analysis status from the result inside a complete run:
`complete/advisory-findings` and `complete/clean-within-complete`. Malformed or
unreadable selected source is `partial/incomplete`; missing PHP, PHP below
8.1.0, no PHP, and all-excluded selections are `unsupported`; version/provider
process failures are concrete `failed` outcomes. Detect reruns remove stale
JSONL, scan, Markdown, legacy `findings.json`, and PHP `report.json` artifacts,
which the focused suite proves in both valid-to-failed and failed-to-valid
directions at one destination.

## What generalized

- The existing family-local source-role inventory/status pattern, JSONL
  finding shape, comment bands, reporter, copied-closure invocation, and
  stale-artifact lifecycle transferred without a repository runtime.
- Complete/partial/unsupported/failed remains the evidence-coverage axis;
  clean is a result only inside complete evidence.
- Independent SHA-256 maps before and after positive, malformed, and lifecycle
  runs remain the simplest trustworthy proof that an advisory scan preserved
  source.
- `report.py --output-json` adds the required `report.json` destination while
  retaining `findings.json` as the default for Python, JavaScript, TypeScript,
  Go, and Java callers.

## What stayed PHP/family-local

The 65-line `php_comments.php` provider uses native
`token_get_all($source, TOKEN_PARSE)`. It distinguishes comments from strings
and heredocs and turns PHP grammar errors into per-file partial evidence. The
PHP >= 8.1.0 probe, `.php` roles/naming, generated markers, and provider payload
stay inside `find-comment-drift`; no universal syntax schema or shared runtime
was introduced.

This cohort does not resolve Composer autoloading, symbols, types, traits,
framework behavior, call targets, or PHPDoc completeness. It does not classify
Blade/Twig templates as PHP. One native provider process receives all eligible
paths, which is appropriate for the frozen pilot but could reach the operating
system argument limit on a very large repository; batching should be added
only with a real large-host case. The provider has no separate timeout yet.

## Acquisition and setup

No dependency was installed and no network was used. Verification selected:

- the product checkout's `.venv/bin/python`
  (Python 3.11.10) for the copied stdlib-only launcher and pytest;
- `/opt/homebrew/bin/php` (PHP 8.4.2) for the native provider, fixture scripts,
  and `php -l`; and
- `/usr/local/bin/composer` (Composer 2.4.0) for offline
  `composer validate --no-check-publish --no-interaction`.

Composer emits PHP 8.4 deprecation notices but exits successfully. The host
`tests/lint.php` and `tests/smoke.php` pass, and native `php -l` rejects the
frozen malformed input as expected.

## Closure and counted LOC

Closure uses the frozen definition: every regular non-`.pyc` file below
`.claude/skills/find-comment-drift`, excluding `__pycache__`.

- Base: 17 files, 75,908 bytes.
- PHP result: 18 files, 93,488 bytes,
  `manifest_sha256=a0ea30a3d2b5721465e3b71b432cecb795e929bd1eb13ef55251423773b8264f`.
- Delta: +1 file, +17,580 bytes (+23.16% for this selected-skill closure).
  Against the frozen three-skill combined baseline of 385,347 bytes, this lane
  contributes 4.56 percentage points; the combined P4 gate cannot be concluded
  until the semantic and mutation closures are integrated.

Adapter-plus-test LOC is incremental physical added lines in the PHP runtime
path plus `tests/test_find_comment_drift_php.py`; skill prose and this learning
packet are excluded. Counted paths and additions are:

- `scripts/detect.py`: 173;
- `scripts/support.py`: 176;
- `scripts/report.py`: 9;
- `scripts/php_comments.php`: 65; and
- `tests/test_find_comment_drift_php.py`: 274.

Total: 697 physical added lines, 634 nonblank. The frozen Java lexical
comparison is 1,573 physical adapter-plus-test lines, so this lane is 55.69%
smaller (876 lines), clearing the 25% LOC-reduction gate. The per-skill closure
growth is not itself below 10%; only the frozen combined closure gate is the
declared decision boundary.
