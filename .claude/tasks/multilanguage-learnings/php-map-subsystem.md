# PHP `map-subsystem` P4 learning packet

## Accepted outcome

The PHP cohort adds one bounded, copied/on-demand PHP map command. Given one
production directory inside a validated Composer `autoload.psr-4` root, it
writes both of the required final artifacts without changing host source:

- `.claude/docs/subsystems/<name>.md`
- `reports/map/<name>/php-map.json`

The locked PHP pilot reaches `billing.md` and `php-map.json` for `src/Billing`.
It reports `Acme\\Billing\\InvoiceService`, its Composer-PSR-4-confirmed
`Acme\\Shared\\Clock` import, and the
`Acme\\Consumer\\CheckoutService` inbound importer. Those are static
class-file/import facts, not dynamic-call or type-resolution claims.

## Tool and closure decision

Selected provider: `scripts/map_php.php`, run by PHP 8.1+ and a host-owned
Composer 2.2+. It is family-local and uses:

- native `php -l` for every eligible production PSR-4 source;
- `composer validate --no-check-publish --no-interaction`, with no install,
  update, or network acquisition; and
- native PHP tokenization plus the validated `autoload.psr-4` declaration to
  match class-like declarations and `use` imports to expected first-party
  files.

The runtime never reads `autoload-dev`, `vendor`, a toolkit Python runtime,
the pinned tree-sitter cache, a sibling skill, or a shared graph/schema. The
copied command resolves only the copied `map-subsystem` directory and the
host's PHP/Composer executables.

### Tree-sitter decision: rejected for this provider

The pre-existing pinned tree-sitter PHP experiment was replayed read-only
against the invoice fixture using the supplied 1.13.2 environment/cache with
the `deny-network` marker: it parsed a `program` with `has_error: false` and
one namespace-use capture. The frozen experiment also proves declarations,
imports, calls, spans, and parse-problems are stable offline.

That is useful syntax evidence only. It cannot establish Composer PSR-4
class-file identity, inbound project edges, symbol identity, types, resolved
calls/imports, or a project graph. Its 7,455,120-byte cached grammar is not a
copied-skill dependency. The provider therefore rejects tree-sitter for this
semantic/project closure: syntax spans are not semantic resolution.

## Outcome and safety contract

- `complete`: PHP lint, Composer validation, production PSR-4 inventory, and
  all selected first-party import/class-file matches are established.
- `partial`: selected first-party imports cannot be matched, selected
  declarations are not at their expected PSR-4 path, declarations collide,
  a configured PSR-4 root is absent, or unselected symlink source leaves
  project inventory incomplete.
- `unsupported`: missing/old PHP or Composer, missing/unsafe Composer
  metadata/PSR-4 topology, excluded/missing target, no eligible target source,
  or a selected symlink target/source. A missing PHP launcher is caught by the
  documented shell command before artifacts exist.
- `failed`: malformed PHP and failed Composer validation write terminal JSON
  and Markdown and exit non-zero. Valid → failed → valid runs replace the same
  two destinations atomically, so a stale successful map cannot survive.

Generated, test, vendor, build, stub, and symlink paths are excluded before
the eligible inventory. Artifact destinations are constrained below
`.claude/docs/subsystems/` and `reports/map/` and reject symlink traversal.

## Measured closure and maintenance cost

Measured after the PHP provider and knowledge/runbook landed:

| Metric | Value |
|---|---:|
| Copied `map-subsystem` regular files | 11 |
| Copied closure bytes | 208,684 |
| Closure manifest SHA-256 | `573366add44f347ff53fde9dd8c66f181a0acfa532b51d3afd88549895349bf7` |
| PHP adapter physical LOC | 1,123 |
| PHP adapter nonblank LOC | 1,066 |
| PHP final-outcome test physical LOC | 390 |
| PHP final-outcome test nonblank LOC | 344 |
| Adapter + test physical / nonblank LOC | 1,513 / 1,410 |

The closure figure is the whole selected `map-subsystem` directory, with
regular files only and no `__pycache__`; the manifest hashes sorted relative
path + NUL + content SHA-256 + newline rows. The adapter/test figure is scoped
only to `map_php.php` and `test_map_subsystem_php.py`, not shared docs or
other language providers.

## What generalized and what stayed PHP-local

Generalized mechanics:

- final-artifact tests rather than parser-only assertions;
- source fingerprints and native before/after verification;
- root-relative source-role exclusions and symlink refusal;
- atomic paired Markdown/JSON lifecycle with explicit complete/partial/
  unsupported/failed states; and
- copied-skill command replay plus unsafe artifact-path tests.

PHP-local mechanics:

- Composer production `autoload.psr-4` rather than `autoload-dev` as the
  first-party class-file contract;
- `php -l` and PHP token rules for namespace, class-like declaration, and
  `use` extraction;
- Composer version/manifest validation and its no-install invocation; and
- PHP's explicit dynamic-call, runtime-loading, type, framework, trait, and
  function-import limits.

No shared parser, resolver, graph, or schema is justified. A future consumer
must demonstrate the same Composer static class-file contract, terminal
lifecycle, source-role policy, final artifacts, and copied closure before any
shared utility is considered.

## Verification

Using the supplied tools:

```text
.venv/bin/python \
  -m pytest -q tests/test_map_subsystem_php.py
# 7 passed

.venv/bin/python \
  -m pytest -q tests/test_map_subsystem_php.py \
  tests/test_map_subsystem_typescript.py tests/test_map_subsystem_go.py \
  tests/test_map_subsystem_java.py
# 25 passed

.venv/bin/python \
  -m pytest -q tests/test_skill_taxonomy.py tests/test_skill_comply.py
# 7 passed

/opt/homebrew/bin/php -l .claude/skills/map-subsystem/scripts/map_php.php
# No syntax errors detected

/opt/homebrew/bin/php tests/lint.php
/opt/homebrew/bin/php tests/smoke.php
/usr/local/bin/composer validate --no-check-publish --no-interaction
# passed in the locked host fixture before and after mapping
```

Composer 2.4.0 emits PHP 8.4 deprecation notices on this machine, but the
validate command exits successfully; the mapper records command success/fail
status and does not suppress, install, or upgrade Composer.
