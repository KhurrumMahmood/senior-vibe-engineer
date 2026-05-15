# find-duplication — false-positive detection

Read at **Step 4c-bis**. Mandatory before flagging any class or module-level callable as "dead" or "only 1 inbound reference."

## Why this file exists

The single most common false-positive in duplication triage is **class-registry dispatch**. A class can be "only referenced once by its dotted name" (`module.ClassName`) yet have 8+ live call sites via string-key registry lookup (`REGISTRY['name']`). A grep that only checks the dotted form will miss every reachable site.

Cluster 10 (see `learnings.md`) flagged `VendorCScraper` as "95% confidence dead." It was reachable via `SiteScraperFactory.SCRAPERS['Vendor C Parts']` from 8 call sites. This check catches that class of error.

## When to run the check

- Every time a class (or module-level callable: function assigned to a variable, factory-returned handler, etc.) is about to be flagged as `dormant_findings` in the triage.
- Every time the AST visitor reports "only 1 inbound reference" for a class.
- Before downgrading a duplication finding to "dead code" based on reference counts alone.

Cost: ~3 greps per flagged class. Cheap. Always do it.

## The check — two groups of greps

### Group A — how the class is referenced elsewhere

```
Grep pattern (bare name):                ClassName
Grep pattern (string-key registration):  '<ClassName>'|"<ClassName>"
Grep pattern (dict value):               :\s*ClassName[,\}\)]|=\s*ClassName[,\}\)]
Grep pattern (list value):               \[\s*ClassName\s*[,\]]|,\s*ClassName\s*[,\]]
```

**Filter the definition line itself.** The bare-name grep will match `class ClassName:` on its own definition line. Exclude the result that points at the `class <Name>(` or `def <Name>(` line in the target file — it's a self-reference, not evidence of reachability.

### Group B — the target file's own dispatch structures

```
Grep pattern: ^\w+\s*=\s*{             # any_case = { — registry dict (not just ALL_CAPS)
Grep pattern: ^[A-Z_]+\s*=\s*\[        # ALL_CAPS = [ — registry list
Grep pattern: register\w*\(            # register(), register_handler(), etc.
Grep pattern: getattr\(|globals\(\)|locals\(\)|importlib  # dynamic dispatch
```

If Group B matches anything in the target file, **trace the consumer** — find where the registry is imported and indexed. The classes that appear as values in the registry are reachable via that indexing, even if no call site writes their dotted names.

## Decision rule

- **ANY registry match found** → demote confidence to **"possibly dead, needs `/find-dormant` pass"**. Do not report as high-confidence dead code. `/find-dormant` has deeper verification (template URL-name grep, Django admin walking, management-command discovery).
- **No registry matches AND zero bare-name references outside the definition** → classify as dead, proceed with the finding.

## Dispatch patterns to recognize

Common forms where grep on the dotted module path fails to see reachability:

- `SCRAPERS = {'Vendor A': VendorAScraper}` — ALL_CAPS registry dict
- `scrapers = {'vendor_a': VendorAScraper}` — lowercase registry dict
- `register('field.type', FieldHandler)` — function-based registration
- `site.register(MyModel, MyModelAdmin)` — Django admin
- `VIEW_CLASSES = [FooView, BarView]` — list-based registry
- `handler = globals()[name]` — dynamic lookup by string
- `importlib.import_module(path)` — dynamic module loading
- Celery tasks invoked by string name (`'core.tasks.start_crawling_task'`)
- Management commands discovered by Django's loader (no explicit import)

For the specific registries known to exist in this codebase, see `knowledge/`.

## Cross-reference to `/find-dormant`

`/find-dormant` enforces this same check as its Rule 10 ("functions referenced via getattr or registered in a dispatch dict"). `/find-duplication` runs it **earlier** — before the dead-code flag is even written to the triage — because downstream consumers (`/fix-workflow`) trust the triage output.

If Group A or Group B matches and the class is demoted to "possibly dead," the recommended next step in the triage is `/find-dormant`, not `/fix-workflow`.
