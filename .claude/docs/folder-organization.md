# Folder organization — route-prefix and tests-folder grouping

> **Decided in:** [ADR 0006](../../ai-docs/decisions/0006-folder-organization.md)
> **Detected by:** `/find-folder-topology-drift`
> **Proposed by:** `/propose-folder-reorganization`
> **Executed by:** `/refactor-subsystem` (decomposition mode, ADR 0002)

This file is the load-on-demand reference for *folder topology* — how
files group inside a layer. It pairs with three other surfaces:

- `architectural-smells.md` §8 *Folder topology drift* — the smell
  shape (one-paragraph problem recognition).
- ADR 0006 — the case-law anchor (rejected alternatives, the
  ≥3-siblings threshold rationale, refactor sequencing).
- `.claude/skills/_common/structural-design-principles.md` — the
  cross-skill, cross-project two-layer rule this convention rests on
  (framework norms are a floor; intuitiveness is the goal above it).
  Read that first if you are evaluating a structural choice and need
  the underlying design principle, not just the convention.

Read this doc when:

- You are about to add a new file that would be the third sibling of
  an existing prefix cluster (`tests_<X>.py`, `<domain>_<X>.py`).
- You are decomposing a flat module and need to decide whether the
  result lands as sibling files or as a folder package.
- You are proposing where tests belong for a new package.
- A `find-folder-topology-drift` scan flagged drift and you need the
  rules behind the finding.

## The five rules (canonical form)

The decision is in ADR 0006. The shorthand:

| # | Rule | Threshold |
|---|---|---|
| 1 | Tests live in `tests/` subfolders, not `tests_*` prefix at root. | New tests immediately; existing `tests_*.py` migrate when their subject moves. |
| 2 | Same-prefix sibling clusters collapse to a directory package. | N≥3 siblings sharing a `<prefix>_` token, where the prefix names a coherent domain. |
| 3 | Same-domain helper clusters collapse to a domain folder. | N≥3 modules naming the same domain (no shared prefix required). |
| 4 | URL-prefix views project onto folder names under `views/`. | A URL prefix with ≥3 view modules gets a matching folder. |
| 5 | Folder packages that fall below ≥3 source modules collapse back to flat. | The promotion threshold is also the demotion threshold — packaging is earned, not preserved. |

The threshold is **three**, not two. Pairs are not yet a pattern. This
matches the cotton-primitive threshold (`/extract-cotton-primitive`)
for the same reason — the floor where shared shape becomes a real
pattern, not a coincidence.

## Graduated topology — the convention runs in both directions

ADR 0006 frames folder organization as a **graduated, evolving
discipline**, not a one-shot reorg. The same threshold (≥3) gates
both promotion and demotion, and the SUSPECT detector re-validates
the topology on every scan:

- **Promote** (Rules 2 / 3 / 4): a flat parent crosses ≥3 same-prefix
  or same-domain siblings → collapse into a folder package. Triggered
  when a third sibling lands.
- **Demote** (Rule 5): a folder package shrinks below ≥3 source
  modules → collapse back to siblings at the parent. Triggered when
  a file inside the package merges away, deletes, or moves out.

Both directions are **opportunistic**, not bulk: the collapse-up or
collapse-back happens in the next PR that touches the surviving
file(s), one cluster per PR, under ADR 0002's two-commit refactor
discipline. The SUSPECT scan keeps the queue visible in either
direction.

The principle: a folder *earns* its packaging by carrying ≥3 cohesive
siblings, and *loses* its packaging when that earning evaporates.
Folders are not status symbols — they are organizational tools whose
job is navigability. A 1-file folder fails that job worse than a
1-file flat parent.

## Worked examples

### Cluster collapse — flat prefix cluster

**Before** (flat layout):

```
views/
├── feature.py                     # legacy shim or aggregator
├── feature_context.py
├── feature_dashboard.py
├── feature_lifecycle.py
├── feature_mappings.py
├── feature_save.py
└── feature_status.py
```

Six siblings, prefix `feature_`, prefix names a coherent domain.
Rule 2 applies: collapse.

**After** (target layout):

```
views/feature/
├── __init__.py            # re-exports public symbols (compatibility)
├── context.py
├── dashboard.py
├── lifecycle.py
├── mappings.py
├── save.py
├── status.py
└── tests/
    ├── __init__.py
    └── test_*.py          # migrated from tests/test_feature_*.py
                           # alongside the move (Rule 1)
```

The shim `views/feature.py` may remain at the parent layer
under ADR 0002's two-commit refactor discipline; it does not count
toward the cluster.

### Helper cluster — domain folder

**Before:**

```
core/
├── widget_advanced_scraper.py
├── widget_basic_scraper.py
├── widget_rotating_scraper.py
├── widget_scraper.py
├── general_scraper.py
└── scrapers.py
```

Six modules, no strict shared prefix, but they all name one domain —
scrapers. Rule 3 applies.

**After (one possible target — the proposal would justify the choice):**

```
core/scrapers/
├── __init__.py
├── widget.py             # consolidated from the four widget_* files
├── general.py
└── tests/
    └── test_*.py
```

The proposal explains *why* the four widget variants merge into one
file (or stay separate, in which case the structure has subfolders) —
the EXPLAIN skill is what carries that judgment, not this doc.

### Singleton stays flat

A 400-LOC cohesive module with no prefix siblings does **not** become
a folder. Rule 2's threshold is ≥3 siblings; a singleton is below it.
Folder packaging is for clusters, not for ceremony.

### Demotion — folder collapses back to flat

**Before** (a folder that shrunk over time):

```
services/sitemap/
├── __init__.py            # re-exports SitemapService
└── service.py             # the only survivor; import.py and
                           # operations.py merged in last quarter
```

One source module (`service.py`) plus an `__init__.py` is below the
≥3 threshold. Rule 5 fires.

**After** (collapse back to a sibling at the parent):

```
services/
├── …
├── sitemap.py             # ex-sitemap/service.py
└── …
```

The next PR that touches `service.py` does the migration:
`git mv services/sitemap/service.py services/sitemap.py`,
delete the empty `__init__.py`, update the parent's import surface
(`from .sitemap.service import SitemapService` →
`from .sitemap import SitemapService`). Same two-commit discipline as
the promotion direction. The proposal step
(`/propose-folder-reorganization` in demote mode — Stage 2) writes
the migration table.

The "in-flight" exemption (Rule 5's first guardrail) applies if the
team is *actively* growing the folder back above threshold (e.g. a
spec is open to add `sitemap_validation.py` and `sitemap_diff.py`).
That exemption is recorded in the proposal as `defer_in_flight` with
a pointer to the spec.

### Tests placement for new code

```
services/widgets/
├── __init__.py
├── service.py
└── tests/
    ├── __init__.py
    └── test_service.py
```

Not `tests/test_widgets.py`. Rule 1.

## When NOT to split

Four explicit guardrails (verbatim from ADR 0006):

1. **Singletons stay flat.** No folder for a single file.
2. **Cohesion beats LOC.** A coherent 600-LOC module is preferable to
   four arbitrary 150-LOC fragments. The 500-LOC soft limit is
   advisory, not a trigger.
3. **Conversion is opportunistic.** One cluster per PR, gated by the
   detector queue. Never a single bulk-rename PR.
4. **Scratch / experiment code gets lighter treatment.** A
   `find-folder-topology-drift` finding against scratch code is
   informational, not actionable.

If a finding fires but the cluster is *legitimately* one of these
exemptions, the proposal stage records it as
`defer_<reason>` and the queue drains it without a refactor.

## Tests-by-prefix vs tests-by-folder — the discovery story

Most test runners (pytest, Django's test runner, etc.) discover both
`tests_<x>.py` files and `tests/` packages. The naming convention is
what changes; discovery is unaffected. For runtime test selection:

```bash
# Both work today.
.venv/bin/python manage.py test tests.test_widgets
.venv/bin/python manage.py test app.services.widgets.tests.test_service
```

The convention picks the second form for new tests because:

- It localizes — the test sits inside the folder it exercises.
- It scales — a folder package can hold dozens of `test_*.py` files
  without polluting a sibling layer.
- It survives moves — when `views/feature_*` collapses to
  `views/feature/`, the matching tests collapse with it rather than
  orphaning at `tests/test_feature_*`.

## Migration sequencing

1. **SUSPECT** — `/find-folder-topology-drift` produces a queue of
   clusters at `reports/find-folder-topology-drift/scan-<TS>/`.
2. **EXPLAIN** — `/propose-folder-reorganization <cluster-id>` writes
   a proposal at `reports/propose-folder-reorganization/<target>/`
   with the current → proposed tree, file-move table, and import-
   impact summary.
3. **REFACTOR** — `/refactor-subsystem` (decomposition mode) executes
   the proposal under ADR 0002's spec-first, two-commit discipline.
   Behaviour-preserving move first; any latent bug fix is a separate
   commit.
4. **GUARD (deferred)** — Once the queue is mostly drained, install
   a pre-commit lint that flags a new file landing as the third
   sibling of an existing prefix cluster without a matching folder.
   Promote from soft to hard only after the queue establishes the
   threshold is workable in practice (same staging as ADR 0005's
   CLAUDE.md size budget).

The ADR is satisfied when the queue drains, not when every flat folder
has been packaged. Singletons and exempted scratch code stay open as
informational items.

## Relation to other docs

- **ADR 0006** — case-law anchor; rejected alternatives, threshold
  rationale, refactor sequencing.
- **ADR 0002** — the spec-first, two-commit refactor discipline that
  governs every cluster collapse.
- **`architectural-smells.md` §8 *Folder topology drift*** — problem
  recognition (one paragraph) with `Decided in: 0006` backref.
- **`architectural-smells.md` §1 *Omnibus module*** — the file-level
  smell that often precedes a topology fix. A flat decomposition
  exits omnibus but enters topology drift; folder packaging is the
  step that closes both.
- **`canonical-patterns.md`** — does not yet carry a positive form
  for this rule. Add when the convention is settled enough to lint
  (Stage 2 guardrail above).
