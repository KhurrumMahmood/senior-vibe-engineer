# find-duplication — learnings

Per-cluster war stories followed by the 12 rules distilled from them (see "Rules (expanded)" below). Read when making a judgment call during investigation (Step 4), when deciding whether to bend a rule, or when a finding's "shape" isn't obvious.

Each rule is backed by at least one cluster logged here.

## Cluster summaries

### Cluster 1 — `core/utils.py` export dedup (2026-04-09)

jscpd flagged two pairs: lines 11-60/103-138 and 409-468/500-557. Triage thought both were Type-1 duplicates and estimated ~1 hour, single-file, zero risk.

Reality:
- **First pair was dead code, not duplication.** `export_to_excel(crawl_job)` and `export_to_csv(crawl_job)` had zero import sites anywhere. A 10-second grep confirmed. 138 LOC deleted outright.
- **Second pair** was a genuine Type-1 duplicate between `export_product_data_to_excel` / `..._to_csv`. Extracted `_build_product_data_dataframe(uploaded_file) -> pd.DataFrame | None`; both wrappers became ~10 lines each.
- **Hidden bug (Cluster 1b):** the extracted helper body referenced `product.BrandName` and `product.PartDescription` — fields that don't exist on `ProductData`. At runtime → `AttributeError` → silent `except Exception` → HTTP 500. A pre-existing latent bug inherited by the refactor. **Preserved in the refactor commit; fixed in a separate Cluster 1b commit** per the behavior-preservation rule.
- A third broken field (`FanType`) was discovered later in the sibling `export_to_excel_comprehensive`. Also deferred to Cluster 1b.

**Rules from this cluster:** 4 (dead code at 5× multiplier), 9 (silent catches hide bugs), 10 (dormant is side-channel).

### Cluster 2 — Shadow `_safe_int` / `_safe_float` / `_safe_bool` (2026-04-09)

Triage saw identical signatures in two modules and estimated 5 minutes to unify into the canonical `safe_int` from `core.input_utils`.

Reality: 40 minutes. The two implementations had **different numeric-policy semantics** — one clamped out-of-range values silently, the other raised `ValueError`. Identical names masked load-bearing divergence in error handling. The canonical `safe_int` did neither (it returned a default). Unifying required deciding which policy was correct per caller, not a mechanical extract-and-replace.

**Rules from this cluster:** 3 (no effort estimate before Reading), 8 (read both bodies before classifying shadow helpers).

### Cluster 3 — `core/utils.py` top-of-file neglect (2026-04-10)

jscpd flagged a 42-line duplication mid-file. Reading the whole file surfaced **851 LOC of dead code at the top** that jscpd had never flagged (no duplication, so it was invisible to the lexical tool). Three dead helpers and a large dead class, all deletable with zero call sites.

The first cluster in a neglected file is a leading indicator — once one fragment is flagged, expect more dormant code nearby.

**Rules from this cluster:** 5 (grep upward).

### Cluster 4 — 17-LOC three-way cost-tracking clone (2026-04-10)

A tiny 17-LOC three-way clone touching cost-tracking code was ranked higher priority than Cluster 3's 851-LOC dead file. Reason: three copies of money-handling logic drift independently, and when they drift they cause silent accounting errors. LOC is a weak signal; **divergence risk × blast radius** wins.

**Rules from this cluster:** 1 (rank by multiplicity × divergence risk).

### Cluster 6 — Start/Reclassify progress-view overlap (2026-04-11)

jscpd reported three clone pairs. Collapsing by method identity: two pairs collapsed into a single Start/Reclassify finding, one survived as a progress-view finding. Reporting the raw three as separate work items would have tripled the apparent scope and confused the fix-workflow triage.

**Rules from this cluster:** 2 (collapse overlapping pairs before reporting).

### Cluster 10 — `core/scrapers.py` registry-dispatch false positive (2026-04-12)

The triage flagged `VendorCScraper` as "95% confidence dead, only 1 inbound reference." The grep used was `scrapers.VendorCScraper` — the dotted module form.

Reality: **8+ live call sites via string-key dispatch** through `SiteScraperFactory.SCRAPERS['Vendor C Parts']`. The codebase never writes `scrapers.VendorCScraper`; it imports `SiteScraperFactory` and indexes `SCRAPERS` by site display name. Every class in `core/scrapers.py` was reachable.

Also from this cluster: triage claimed "4 identical 17-line `search_part` bodies." Reading them showed **4 × ~45-line bodies** each with site-specific URLs, CSS selectors, and query parameters. Type-3 near-misses, not Type-1 clones. The line-count estimate was wrong by nearly 3×; the "identical" classification was wrong entirely.

**This cluster is the primary motivation for `false-positives.md`.** The registry-dispatch check was added as mandatory at Step 4c-bis.

**Rules from this cluster:** 11 (class-registry dispatch), 12 (verify identical bodies by reading them).

## Rules (expanded)

### 1. Rank by clone multiplicity × divergence risk, not LOC

Cluster 4 (17 LOC across 3 copies touching money) outranks Cluster 3 (851 LOC of dead code). The goal of dedup triage is "prevent bugs at synchronized call sites," which correlates with multiplicity and divergence risk, not with size.

### 2. Overlapping clone pairs are one finding

jscpd emits N×(N-1)/2 pairs for N copies of the same fragment. Collapse by method identity (not line range) before ranking. Cluster 6 went from 3 reported pairs to 2 findings this way.

### 3. Never quote an effort estimate before Reading the bodies

Cluster 2 budgeted 5 minutes; actual was 40. The planner assumed name collision implied semantic equivalence — it didn't. **Refuse to publish an effort estimate in the triage until Step 4d is complete.** Use "TBD — bodies not yet read" if asked prematurely.

### 4. Dedup finds dead code at ~5× the multiplier

Every time a cluster surfaces, expect ~5× the flagged LOC to turn up as adjacent dead code in the same file. Budget investigation time to include file-wide reading, not just the flagged range. Clusters 1 and 3 both demonstrated this.

### 5. Grep upward, not just around the clone pair

`Read` the whole file before reporting. Cluster 3's 851 LOC of dead code lived at the top of the file, far from the flagged duplication. Lexical tools see what's duplicated; they can't see what's orphaned. The agent must.

### 6. A short flagged pair is a smell for more copies nearby

A 14-line jscpd hit in a file with 3+ related methods is usually the **longest stretch jscpd could match verbatim**. The other methods probably duplicate the same logic with renames or minor variations below jscpd's threshold. Grep for distinctive strings from the snippet to find siblings jscpd missed.

### 7. Log format is behavior — do not lift log lines into a helper

Log strings are contracts with aggregators, dashboards, and humans reading tail output. Lifting identical-looking log lines into a helper breaks downstream parsers that match on format. If the bodies differ only in log format, lift the middle, not the logs. Keep the log line in the caller.

### 8. Read both bodies before classifying a shadow helper

Name collision is not semantic equivalence (Cluster 2). For every "shadow helper" finding, there are three possible outcomes:

- **True shadow** — strict mirror of the canonical. Delete the shadow, point callers at the canonical.
- **Canonical gap** — the shadow does something the canonical doesn't (extra validation, different policy). Promote the shadow's behavior into the canonical or add a parameter.
- **Module-local concept** — despite the name, the shadow is doing something genuinely different and local. Rename it; don't delete; don't unify.

Skipping the read gets these wrong in either direction.

### 9. Silent `except Exception` is a bug multiplier

Cluster 1b surfaced an `AttributeError` buried under a silent catch. The broken code had been live for months because the catch swallowed it. Grep for silent catches near every clone; if found, flag as "latent bug risk" in the report, and `/fix-workflow` will write a test against the catch before refactoring. **A correct refactor of broken code is still a correct refactor — but you must surface the bug separately.**

### 10. Dormant code found during investigation is a side-channel

When Step 4c surfaces a function with zero inbound references, emit it as a `dormant_findings` entry — separate from `duplication_findings`. Do not delete it as part of the dedup commit. Route through `/find-dormant` (or, if confidence is already high, directly to `/fix-workflow`) so the deletion gets its own commit and own authorization.

Mixing deletion into a refactor commit conflates behavior preservation with behavior change and makes bisection harder.

### 11. Class-registry dispatch defeats naive grep for dead code

Cluster 10. If the target file defines `CAPS_DICT = { ... }`, that dict is likely the dispatch table for consumers — classes appearing as values are reachable even though no call site writes the dotted form. **Always run the check in `false-positives.md`** before flagging a class or module-level callable as dead.

Known registries in this project are catalogued in `knowledge/` — consult that list when triaging classes in this codebase.

### 12. "Identical N-line bodies" must be verified by actually reading them

Cluster 10 claimed 4 × 17-line identical `search_part` bodies. Reality: 4 × 45-line near-misses. **Never trust a summary count from tool output.** Read both ends of every top-priority clone before writing the triage. The line-count estimate and the "identical / near-miss" classification are both unreliable until verified.
