# PHP A2 syntax-family learning

## Final outcomes

The frozen members are `audit-decisions`, `find-complexity-hotspots`,
`find-omnibus`, and `find-standard-gaps`. They retain their existing distinct
artifacts and consume PHP token syntax facts only:

- Audit finds real comment `decision:0001` (resolved) and `decision:9999`
  (orphan), never strings or role decoys.
- Complexity reports only `routeInvoice` at direct-body score 9 and
  `measure-first`; an anonymous inner closure cannot inflate `closureDecoy`.
- Omnibus emits one four-domain name-cluster candidate, then requires fresh
  human scout evidence before `/refactor-subsystem <spec-id>` is surfaced.
- Standards measures two direct `parseInvoice` spellings: one lexical `try`
  enclosure, one gap, and 50% coverage.

The clean fixture produces no audit/hotspot/omnibus findings and a scanned
0-gap/100% standards cell. No syntax fact is presented as resolved identity,
behavior, Composer/framework truth, runtime cost, or refactor authority.

## Provider boundary and tests

`.claude/skills/_php-syntax/php_syntax_facts.php` stays separate from A1's
`_php-project-lexical`: A2 needs a different immediate-consumer fact boundary
for real comments, named function-body spans, branch tokens, direct calls, and
lexical `try` ranges. It owns source/test/generated/vendor/build/report/symlink
roles; PHP 8.1+/Composer 2.2+ probes; Composer validation; `php -l`;
`token_get_all(..., TOKEN_PARSE)`; source preservation; and terminal status.
Adapters own only their existing final report schema and lifecycle. Incomplete
facts replace artifacts with empty partial/failed output; omnibus additionally
defers until a candidate-id/hash matched human scout verdict is supplied.

Copied checkout closures use sorted `repository-relative-path + NUL +
file-SHA-256 + LF` rows:

| Closure | Files | Bytes | SHA-256 |
|---|---:|---:|---|
| `audit-decisions` + `_php-syntax` | 10 | 197,717 | `6e9c7e2c2213f4c412b80769f7ef2e72d62c169fc8ade4dda54be7d98cc19c87` |
| `find-complexity-hotspots` + `_php-syntax` | 15 | 150,271 | `e11278aea7d8781e4cb1582391a7f2d127febdf855ba505d1a391809ebb09ca4` |
| `find-omnibus` + `_php-syntax` | 14 | 187,053 | `238af5f0941ff41b230b0dfdc759a79ada02103f26d63fc6433a3f63fbb1dd23` |
| `find-standard-gaps` + `_php-syntax` | 14 | 206,453 | `71d3cf94aa368a75c8321c3787ff373cd1832b0e07ea11995a6126c7648149fe` |

`tests/test_php_a2_syntax_family.py` proves positive, clean/safe-defer,
must-not-fire roles/strings/closure/cohesive-module, missing/old/failing tool,
malformed-source, copied closure, source preservation, valid→failed→valid, and
provider-delete recovery cases. Native fixture checks are:

```text
composer validate --no-check-publish --no-interaction
php tests/lint.php
php tests/smoke.php
```

The smoke output is `php-syntax-ok`. No tool/dependency was installed or
downloaded. Frozen paths: PHP 8.4.2 `/opt/homebrew/bin/php`, Composer 2.4.0
`/usr/local/bin/composer`, and product Python 3.11.10 at
`/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python`. <!-- # host-ref-allow: required frozen F2 runtime -->

## ML-025 economics and fallback

Literal comparison copies the exact provider under each selected skill and
changes only its provider-relative path. Provider 827 LOC + adapters 618 +
focused test 461 = 1,906 shared LOC versus 4,387 literal LOC: **56.55%**
reduction (>=25%). Per-skill copied-closure growth is **0.00%** (<=10%).

Seven alternating warm four-artifact cohorts: shared `[3.214229, 3.309084,
3.511391, 3.443757, 3.381039, 3.615936, 3.592898]`; literal `[3.167378,
3.234216, 3.161292, 3.320956, 3.556574, 3.560057, 3.448980]`. Medians are
3.443757 and 3.320956 seconds, **3.6978%** growth (<=10%). If a later consumer
needs a different policy or a gate regresses, copy `php_syntax_facts.php` into
each affected skill, change only local provider paths, and delete `_php-syntax`.
Do not promote this seam across languages.

## Limits and integration

This is not semantic PHP: no imports/autoload aliases, receiver/type/callee
resolution, exception flow, dynamic dispatch/reflection, Composer execution,
PHPStan/Psalm, framework convention, or safe decomposition claim. Standards
supports only direct spelled calls plus lexical `enclosed_by: try`; omnibus
always requires human scout judgment.

Root should cherry-pick this lane, ship `_php-syntax` as a sibling on-demand
dependency for these four PHP adapters, then make the root-owned guide/matrix/
catalog/router/ledger changes. Preserve existing PHP outcomes and do not label
A2 semantic/framework support. Replay focused and preserved PHP checks:

```text
/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python -m pytest -q tests/test_php_a2_syntax_family.py tests/test_php_project_lexical_family.py tests/test_php_pilot_spine.py tests/test_find_comment_drift_php.py tests/test_map_subsystem_php.py tests/test_php_move_path.py <!-- # host-ref-allow: required frozen F2 runtime -->
```
