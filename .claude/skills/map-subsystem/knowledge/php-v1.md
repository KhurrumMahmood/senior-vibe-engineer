# PHP v1: native syntax + Composer PSR-4 static map

This branch maps one production PHP directory under a validated Composer
`autoload.psr-4` source root. It is intentionally a small, copied,
family-local provider: PHP 8.1+, Composer 2.2+, and
`scripts/map_php.php` are its only runtime dependencies.

## Established facts

- Native `php -l` succeeds for every eligible production PHP source below the
  configured production PSR-4 roots.
- `composer validate --no-check-publish --no-interaction` accepts the host's
  manifest without installation, update, or network acquisition.
- The provider reads only production `autoload.psr-4`, never `autoload-dev`.
  A class-like declaration is Composer-PSR-4-confirmed only when its fully
  qualified class name maps back to its actual first-party file.
- A resolved `use` import is a static first-party class-file edge only when
  the imported class is declared at that Composer-PSR-4 expected path. The
  map reports selected-directory outbound edges and project-root inbound
  importers.

## Deliberate boundary

Composer PSR-4 is a class-file lookup contract, not a PHP semantic analyzer.
This branch does not claim type facts, dynamic or reflective call targets,
runtime loading, framework behavior, trait dispatch, function imports, or a
complete project call graph. Project-owned PHPStan or Psalm remains the next
tool for analyzer-backed semantic claims.

The pinned tree-sitter PHP grammar was evaluated against the final-outcome
pilot and **rejected** for this production closure. Its cached grammar can
provide declarations, imports, calls, spans, and parse-problem syntax facts,
but it cannot establish Composer PSR-4 class-file identity or inbound project
edges. Syntax spans are not semantic resolution. Depending on the ignored
tree-sitter cache would also make a copied/on-demand skill incomplete. Native
PHP lint plus Composer configuration therefore provides the narrower,
self-contained contract here.

## Source roles and terminal states

- Test, generated, vendor, build, declaration/stub, and symlinked source do
  not enter the eligible production inventory. Direct excluded targets are
  `unsupported`; a selected symlink source is `unsupported`; unrelated
  symlinked PSR-4 source remains visible and makes the inventory `partial`.
- Missing or old PHP/Composer, absent/unsafe `composer.json`, no PSR-4 root,
  an excluded/missing target, or no eligible target source writes an explicit
  `unsupported` map when the PHP launcher itself can run. A missing PHP
  launcher is detected by the installed command and writes no artifact.
- Invalid PHP source or failed Composer validation writes a `failed` Markdown
  and JSON artifact and exits non-zero. Valid-to-failed and failed-to-valid
  runs replace the same two destinations atomically.
- A missing declared class for a first-party target import, an unverified
  selected declaration, duplicate declaration, missing PSR-4 source root, or
  excluded non-selected symlinked source writes a `partial` map. The remaining
  static records are useful but are not presented as a complete project map.
