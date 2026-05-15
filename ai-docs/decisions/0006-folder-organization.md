---
id: "0006"
title: Layer folders use route-prefix and tests-folder grouping over flat naming
status: proposed
date: 2026-05-07
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to:
  - app/
  - app/pages/
  - app/api/
  - app/tasks/
  - app/services/
  - app/
  - app/views/
tags: [folder-organization, topology, decomposition, tests]
related_smell: folder-topology-drift
related_pattern: null
---

# Layer folders use route-prefix and tests-folder grouping over flat naming

## Context

Django's flat-app convention plus AI-grown breadth has produced a
directory the eye cannot navigate. Concrete state, today:

- `app/` holds 142 entries at root level. ~80 of them are `tests_*.py`
  files (`tests_ai_sidecar_apply.py`, `tests_extraction.py`,
  `tests_external_quality.py`, …) sitting next to production code.
  Tests are grouped by *naming convention*, not by *folder*.
- `app/views/` holds 41 entries with two unmistakable prefix clusters:
  eight `site_config_*.py` files (`site_config_dashboard.py`,
  `site_config_context.py`, `site_config_save.py`,
  `site_config_lifecycle.py`, `site_config_mappings.py`,
  `site_config_crawl.py`, `site_config_normalized.py`, plus the
  shim `site_config.py`) and eight `settings_*.py` files
  (`settings_access.py`, `settings_diagnostics.py`, `settings_email.py`,
  `settings_global.py`, `settings_pages.py`, `settings_external.py`,
  `settings_proxy.py`, plus the shim `settings.py`). Both clusters
  shipped as decompositions out of former omnibus modules; the
  decomposition stopped at file rename rather than continuing into a
  folder package.
- `app/` root carries seven scraper modules naming the same domain
  axis (`vendor_a_scraper.py`, `vendor_a_playwright_scraper.py`,
  `vendor_a_enhanced_stealth_scraper.py`,
  `vendor_a_rotating_residential_scraper.py`, `vendor_e_enhanced_scraper.py`,
  `general_site_scraper.py`, `scrapers.py`). The "scraper" domain is a
  recognizable cluster but has no folder.
- Successful counter-examples already exist in this repo:
  `app/views/brand_downloads/` and `app/views/crawling/` are folder
  packages over what used to be flat omnibus modules; `app/services/`
  has well-organized subfolders (`brand/`, `external_source/`, `visual/`,
  `ai_sidecar/`, `extraction_compiler/`, …); `app/tasks/`
  has `crawling/`. The pattern works in this codebase when applied
  consistently.

This is **folder-topology drift** — a smell distinct from the omnibus
file (smell 1, *one file with too many domains*) and from
product-topology drift (smell 6, *one workflow scattered across
routes/views/templates/JS/docs*). Folder-topology drift is the
*intra-layer* version: many files inside one folder that should have
been subdivided. The pain is navigational, not behavioural — agents and
humans alike re-derive "where does this live?" on every visit.

The decompositions documented in `architectural-smells.md` §1 (omnibus)
already produce the file-level fix. Without an explicit folder-grouping
rule, those fixes plateau at "rename `foo.py` → `foo_bar.py`,
`foo_baz.py`" and stop short of the package step that would actually
make the result navigable.

## Decision

Layer folders (`app/views/`, `app/tasks/`, `app/services/`,
`app/management/commands/`, …) use **route-prefix and tests-folder
grouping over flat naming**, applied as a **graduated, evolving
discipline**: the convention is symmetric — folders *earn* packaging
when a cluster forms and *lose* packaging when a cluster dissolves.
The threshold (≥3 same-prefix siblings, or ≥3 same-domain helpers)
is the same in both directions. Topology is re-validated by the
SUSPECT detector, not set once and forgotten.

Five rules, in order of precedence:

1. **Tests live in `tests/` subfolders, not `tests_*` prefix at root.**
   New tests are added to `<package>/tests/test_<area>.py`, not to a
   sibling `tests_<area>.py` at the package root. Existing
   `tests_*.py` files are not renamed in bulk; they migrate alongside
   the code they exercise when that code itself moves into a folder
   package. The Django test runner discovers `tests/` packages
   identically to flat `tests_*` files, so the naming change is
   discovery-neutral.

2. **Same-prefix sibling clusters of N≥3 collapse to a directory
   package** once the prefix names a coherent domain. Threshold is
   *three* siblings sharing the same `<prefix>_` token, not two —
   pairs are not yet a pattern. Once collapsed, the folder gets a
   thin `__init__.py` that re-exports the public symbols the prior
   flat module(s) named, so callers don't churn until they're touched.
   Worked example: the eight `app/views/site_config_*.py` files
   collapse into `app/views/site_config/{dashboard,context,save,
   lifecycle,mappings,crawl,normalized,__init__}.py`. The shim
   `site_config.py` at the parent layer is allowed to remain as a
   compatibility re-export under ADR 0002's two-commit refactor
   discipline; it does not count toward the cluster.

3. **Same-domain helper clusters of N≥3 collapse to a domain folder**,
   regardless of common prefix. Worked example: the seven
   `app/*scraper*.py` files name a shared "site-scraper" domain;
   their natural home is `app/scrapers/{vendor_a,vendor_e,general,
   __init__}.py` (or `app/services/scraping/` if the broader review
   reveals layer-violation overlap). The discriminator is the SRP
   sentence test from smell 1 applied at folder level: *can this group
   of files be described in one sentence without "and"?*

4. **Routes-folder alignment is the dominant axis for `views/`.**
   URL prefixes in `app/urls.py` (`/sites/`, `/api/sites/`,
   `/brand-downloads/`, …) project onto folder names under
   `app/views/`. If a URL prefix has ≥3 view modules, it gets a
   matching folder. This is the convention that makes the layer
   navigable from a URL — the same property that makes Next.js's
   `app/` directory readable. The reverse-mapping is informational, not
   strict: not every folder must correspond to a URL prefix
   (`app/views/dashboard.py`, `app/views/auth.py`, … remain
   single-file as long as they stay below the cluster threshold).

5. **Folder packages that fall below the threshold collapse back to
   flat — packaging is earned, not preserved.** A folder that started
   as a ≥3-sibling cluster but has since shrunk (files merged,
   deleted, or moved out) below ≥3 source modules at its top level
   loses its package status: the survivor(s) move up to the parent as
   sibling files, the folder is removed, and the parent's
   `__init__.py` re-exports collapse to direct imports. Threshold
   symmetry is the point — the same "≥3 is a pattern, fewer is a
   coincidence" rule that gated promotion gates demotion. The
   guardrails for *not* demoting:
   - A 1-file or 2-file folder whose contents are about to grow back
     above threshold (e.g. an explicit migration in flight) stays as
     a package; the proposal records the in-flight reason.
   - A 2-file folder where one file is a `tests/` subfolder counts as
     a 1-source-module package — still below threshold, still
     candidate for demotion.
   - Folders required by a framework convention (Django's
     `migrations/`, `management/commands/`, the project's own
     `tests/` subfolders) never demote — they exist for runtime
     discovery, not for cluster grouping.

   Worked example: if `app/services/sitemap/` ends up with one
   `service.py` after `import.py` and `operations.py` merge into
   it, the folder's `service.py` migrates back to
   `app/services/sitemap.py` and the folder disappears. Under
   ADR 0002's two-commit discipline this is the same shape as a
   promotion — behaviour-preserving move + any latent fix as a
   separate commit.

**Pragmatic floors and exemptions.** This decision is *not* a license
to fragment. Four explicit guardrails:

- **Singletons stay flat.** A single 400-LOC cohesive module like
  `app/views/dashboard.py` does not become `app/views/dashboard/`.
  Folder packaging is for clusters, not for individual files.
- **The 500-LOC soft limit (project memory) is advisory.** Cohesion
  beats LOC. A coherent 600-LOC module is preferable to four
  fragmented 150-LOC modules whose split is arbitrary.
- **Conversion is opportunistic, not bulk.** A single PR that moves
  every cluster at once is unreviewable and clashes with every
  in-flight branch. Conversions land **one cluster per PR**, gated by
  the SUSPECT detector below so the team can see when the queue is
  drained.
- **Custom-job and scratch code (per project memory:
  `project_core_vs_scratch_code.md`) get lighter treatment.** Files
  like `VendorABrandCrawlView` are explicitly noted as not "the site's
  core code"; a finding against them is informational, not actionable.

## Alternatives considered

- **Status quo (no convention).** The flat structure plus
  decompositions-by-rename. Rejected — already painful at 142 entries
  in `app/` and the trajectory is upward, not downward. Naming
  prefixes (`tests_`, `site_config_`, `settings_`, `vendor_`)
  already act as folder names; promoting them to actual folders
  costs a one-time import update but yields permanent navigability.
- **Per-Django-app split.** Break `app/` into multiple Django apps
  (`crawling/`, `extraction/`, `pricing/`, …) so each `app/` directory
  is the natural folder. Rejected — disruptive at this scale (model
  migrations, `INSTALLED_APPS` reshuffling, foreign keys across apps,
  signal wiring), and orthogonal to the navigability problem. Apps
  could be a future ADR if the boundaries calcify naturally; this
  ADR is the cheaper precursor that does not lock us in.
- **One-folder-per-feature regardless of count.** Aggressive packaging
  that puts every module in its own folder, e.g.
  `app/views/dashboard/views.py`, `app/views/auth/views.py`. Rejected
  — fragments singletons into navigation noise, and "go look in the
  folder" becomes "go look in 41 nearly-empty folders" which is
  worse than the flat starting point.
- **Just rely on `grep` and IDE jump-to-symbol.** Rejected — works for
  the author who wrote it, fails for AI agents and onboarding
  humans. The whole point of the maintenance loop in
  `skill-catalog.md` is to convert hidden structure into explicit
  structure; declining to express folder grouping when grouping is
  the obvious unit is a contradiction of the loop's mantra.
- **Hard threshold (e.g. *every* prefix cluster of N≥2 must collapse).**
  Rejected — pairs are not yet a pattern; over-fragmenting on the first
  duplicate manufactures false signal. Three is the same threshold the
  cotton-primitive convention uses for "extract a primitive" (`/extract-
  cotton-primitive` Core Beliefs §1) — the floor where shared shape
  becomes a real pattern, not a coincidence.

## Consequences

**Easier:**

- Folder names answer "where does X live?" before the agent or
  reader has to grep. The path `app/views/site_config/save.py`
  carries the same information as `app/views/site_config_save.py`
  but localizes the cluster — siblings are visible in one `ls`,
  unrelated views (`auth.py`, `dashboard.py`) don't intrude on the
  scan.
- Tests follow code through refactors. When `app/views/site_config_*`
  becomes `app/views/site_config/`, the matching `tests/test_site_*`
  files have a clear destination (`app/views/site_config/tests/`),
  removing the "but where do the tests go?" friction every
  decomposition currently hits.
- AI agents that understood `app/views/brand_downloads/` and
  `app/services/ai_sidecar/` will understand the rest of the
  layer once the convention is uniform. The drift detector below makes
  the gap visible automatically.

**Harder:**

- Every cluster collapse churns imports. `from app.views.site_config_save
  import …` becomes `from app.views.site_config.save import …` (or
  `from app.views.site_config import save_handler` if the package
  `__init__.py` re-exports). One-PR-per-cluster keeps the diff
  reviewable; the EXPLAIN skill's migration table makes the import
  delta explicit before the move.
- The "is this a cluster?" judgment is a real decision per group, not
  an automatic transform. The threshold (≥3, prefix names a domain)
  catches the obvious cases; ambiguous cases (`auth.py` + `auth_*`
  helpers, where the helpers are private utilities not separate
  workflows) need a human call.

**Now expected:**

- New tests for `<package>` go to `<package>/tests/test_<area>.py`,
  not `<package>/tests_<area>.py`. The Django test runner picks up
  both, so this is a placement convention enforced by code review and
  the SUSPECT detector — not by import machinery.
- Existing `tests_*.py` files migrate alongside the code they
  exercise, not in a one-shot rename PR. A test next to its subject
  beats a test in the right *folder* if the subject hasn't moved yet.
- A new view module that would be the third sibling of an existing
  prefix triggers the cluster collapse: ship the new module into the
  collapsed folder, not as a fourth sibling at the parent level. The
  collapse is the cheaper move at PR-time than after.
- A folder package that drops below ≥3 source modules (file merged,
  deleted, or moved out) triggers Rule 5 demotion at the *next* PR
  that touches the survivor — same opportunistic discipline as the
  promotion direction. The SUSPECT scan keeps the queue visible.

## Verification

- **Doc surface.** `.claude/docs/folder-organization.md` carries the
  load-on-demand convention reference (rules + worked examples + the
  "when not to split" guardrails) and is registered in CLAUDE.md's
  Supplementary Documentation table with the trigger row "Read when
  decomposing a flat folder; placing tests; or proposing a directory
  package."
- **Smell entry.** `architectural-smells.md` adds smell §8
  *Folder topology drift* with `Decided in: 0006` and points at the
  detection / proposal / refactor skill chain below. The smells doc
  remains the single problem-recognition catalogue; this ADR is its
  case-law anchor.
- **SUSPECT detector.** `.claude/skills/find-folder-topology-drift/`
  scans for: (a) flat folders with ≥3 same-prefix sibling files,
  (b) `tests_*.py` populations of ≥3 next to a package that has no
  `tests/` subfolder, (c) URL prefixes in `app/urls.py` whose views
  are not grouped under a matching folder, (d) same-domain helper
  clusters at root level, (e) folder packages whose source-module
  count has fallen below ≥3 (the demotion direction — Rule 5).
  Read-only; output to
  `reports/find-folder-topology-drift/scan-<TS>/`.
- **EXPLAIN proposal.** `.claude/skills/propose-folder-reorganization/`
  consumes a finding and emits a per-cluster proposal with current →
  proposed tree, file-move table, import-impact summary, and
  characterization-test matrix. Read-only; hands off to
  `/refactor-subsystem` (decomposition mode, ADR 0002 spec-first
  discipline) for execution.
- **Refactor execution.** `/refactor-subsystem` per cluster, one PR.
  The spec carries the import migration; the two-commit discipline
  (behaviour-preserving move + any latent bug fix) is unchanged from
  ADR 0002.
- **Guardrail (Stage 2 — deferred).** A pre-commit lint that fires
  when a new file lands as the third sibling of an existing prefix
  cluster without a matching folder package. Promote from soft
  detector to hard guard only after the SUSPECT scan establishes the
  threshold is workable in practice (same approach ADR 0005 takes for
  the CLAUDE.md size budget).
- **No bulk migration.** Conversion is opportunistic, gated by the
  detector's queue. The ADR is satisfied when the queue drains, not
  when every cluster has shipped — singletons and exempted
  scratch-code findings stay open as informational items.
