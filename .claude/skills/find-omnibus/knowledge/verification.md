# Verification procedure + bucket taxonomy for `/find-omnibus`

This file is loaded by **scouts**, not by the orchestrator. It tells a
verifier exactly how to classify an omnibus-module candidate.

## The four buckets

| Bucket | Criteria | Recommendation |
|---|---|---|
| **confirmed_omnibus** | File covers 3+ independently-understandable domains after collapsing facets. Decomposition would make each domain readable in one pass. | Recommend `/refactor-subsystem <spec-id>` in decomposition mode. Spec must be scaffolded first. |
| **borderline** | Exactly 2 confirmed domains. Could decompose, could leave as-is — depends on coupling and edit frequency. | Human call. Document the reasoning and revisit after the confirmed set clears. |
| **coordination_omnibus** | File coordinates a product workflow across routes, templates, sidebar/dashboard status, redirects, and boot context, while most domain behavior already lives in services. | Prefer `/map-product-workflow` and `/extract-workflow-registry` before any decomposition. |
| **facets_not_domains** | All clusters are facets of one job (execution paths, pipeline steps, lifecycle phases). OR the file is a known non-omnibus shape (re-export shim, URL router, etc.). | Drop from candidates. Note the false-positive reason so detection can be tuned. |

## The facet-vs-domain rule (refactor-subsystem §1.2.5)

The complete evaluation rule is bundled here so an installed scout needs no
other skill:

> **Evaluation rule:** "and"s that connect facets of a single domain
> (different execution paths, sequential pipeline steps, object
> lifecycle phases) count as **0**. "And"s that connect independently
> understandable domains (you could explain one to a new hire without
> mentioning the other) count as **1** each.

### Worked examples

| Sentence | "and" count | Verdict |
|---|---|---|
| "Handles bulk and single-URL crawling." | 0 (execution paths) | facet — one domain |
| "Handles pivot assembly and Excel formatting." | 0 (pipeline steps) | facet — one domain |
| "Handles create, pause/resume, cancellation, and progress tracking." | 0 (lifecycle phases) | facet — one domain |
| "Handles crawling config and image downloads and PTID classification." | 2 (genuinely separate) | 3 domains — FAIL |
| "Handles product imports and interchange lookups and crawling and discovery and extraction and export." | 5 | 6 domains — strong FAIL |
| "Handles discovery field matching and validation feedback refinement." | 0 (the latter is how the former works) | facet — one domain |

The test-for-facet:

1. Could you explain domain A to a new hire **without mentioning
   domain B**? If yes, they're separate.
2. Do A and B share data structures, status fields, or test
   fixtures? If heavily, probably facets.
3. If you split the file, would the two halves need to import from
   each other constantly? If yes, they're coupled facets — leave
   them.

## Verification steps (apply in order)

### V1. Read the file end-to-end

Open `{{project_root}}/<candidate.file>` and read it. Write your own
one-sentence description — do not copy the auto-generated
`srp_sentence`. The auto-generated version was derived from symbol
names and is often wrong.

### V2. Classify each detected cluster

For every cluster in `candidate.clusters`:

1. Name the domain concept the cluster addresses.
2. Decide: independent domain, or facet of another cluster's domain?
3. If facet, note which cluster it belongs to.

Record as:

```json
"domains_confirmed": ["brand", "download", "image", "export"],
"facets_collapsed": [
  {"cluster": "control", "belongs_to": "download"},
  {"cluster": "preview", "belongs_to": "import"}
]
```

### V3. Apply the bucket table

| Confirmed domain count | Bucket |
|---|---|
| 3+ | `confirmed_omnibus` |
| 2 | `borderline` |
| 0-1 | `facets_not_domains` |

If 3+ domains are confirmed but the file's main job is coordinating a
single product workflow surface rather than owning domain logic, use
`coordination_omnibus`. Example: a site-configuration view module that
assembles sidebar context, page templates, redirect compatibility, and
boot payloads while delegating domain work to services.

### V4. Check for known-not-omnibus shapes

Even with high cluster counts, these shapes are NOT omnibus:

| Shape | Reason key |
|---|---|
| Body is `from .foo import *` / `from .foo import Bar` with `__all__` only | `reexport_shim` |
| All symbols are `path()` / `re_path()` / `include()` | `url_router` |
| Module is `migrations/*.py` | `migrations` |
| Django `AppConfig.ready()` signal wiring | `django_app_wiring` |
| Custom-site scraper at `sites/*/scrape.py` | `custom_scraper` |
| Already-decomposed directory package (check for sibling `.py` files) | `already_decomposed` |

This is the complete bundled false-positive list for the installed skill.

### V5. Sketch a decomposition (confirmed_omnibus only)

For `confirmed_omnibus` candidates, propose 3–8 new files with which
symbols move to each. Follow the directory-package precedent:

```
<original>.py (omnibus)  →  <original>/__init__.py   # thin re-export
                           <original>/<domain1>.py
                           <original>/<domain2>.py
                           ...
```

This is a sketch — the human running `/refactor-subsystem` will
refine it during Phase 3 planning.

Apply the deletion test to every proposed file: if deleting that file would
push non-trivial domain logic back into callers or a sibling module, the file
earns its boundary. If deleting it would mostly remove imports, forwarding, or
other ceremony, collapse it into a neighboring file. Each retained file must
improve locality for one domain cluster without requiring routine private
cross-sibling calls.

For `coordination_omnibus`, sketch the missing workflow owner instead
of a file split: which registry/context/status modules would absorb the
coordination knowledge, and which behavior should stay as thin HTTP
wrappers.

## Output schema

Write one JSON file per candidate at
`${REPORT_DIR}/scout/<candidate_id>.json`:

```json
{
  "candidate_id": "omnibus-0001",
  "file": "core/views/sitemaps.py",
  "bucket": "confirmed_omnibus | borderline | coordination_omnibus | facets_not_domains",
  "domains_confirmed": ["discovery", "crud", "import", "filter_state"],
  "facets_collapsed": [
    {"cluster": "control", "belongs_to": "crawl_lifecycle"}
  ],
  "srp_rewrite": "This file handles sitemap discovery and sitemap CRUD and URL import and filter state.",
  "decomposition_sketch": [
    {"new_file": "core/views/sitemaps/discovery.py",
     "symbols": ["SitemapDiscoveryView"]},
    {"new_file": "core/views/sitemaps/imports.py",
     "symbols": ["..."]}
  ],
  "decomposition_depth_note": "Deletion test passes because each proposed file owns one independently-understandable domain.",
  "false_positive_reason": "reexport_shim | url_router | migrations | django_app_wiring | custom_scraper | already_decomposed | null",
  "notes": "1-3 sentence scout summary",
  "recommendation": "decompose | map_workflow | keep | borderline"
}
```

Rules:

1. `decomposition_sketch` is `[]` for non-`confirmed_omnibus` buckets
   unless the bucket is `coordination_omnibus`, where it should list
   registry/context/status ownership targets instead of moved symbols.
2. `false_positive_reason` is `null` unless bucket is
   `facets_not_domains`.
3. `recommendation` matches bucket: `decompose` for
   `confirmed_omnibus`, `map_workflow` for `coordination_omnibus`,
   `borderline` for borderline, `keep` for `facets_not_domains`.
4. Keep `notes` to 1-3 sentences. The evidence fields carry detail.
5. `decomposition_depth_note` is required for `confirmed_omnibus`;
   set it to `null` otherwise.
