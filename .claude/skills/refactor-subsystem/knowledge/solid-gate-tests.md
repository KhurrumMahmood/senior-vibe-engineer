# SOLID gate test scenarios

Worked examples for verifying that the Phase 6.3 SOLID quality gates (and Phase 1.2.5
SOLID audit) produce the expected outcomes. Use these as a calibration rubric when
running the gates — if your judgment disagrees with a scenario marked PASS or FAIL,
that's a signal to recheck your reasoning.

Referenced from SKILL.md §1.2.5 and §6.3.

## Gate 1 — SRP (single responsibility principle)

### Test: one-sentence description, count "and"s

| Scenario | Description | "and" count | Expected | Why |
|----------|-------------|-------------|----------|-----|
| SRP-PASS-1 | "This file handles all crawling operations for bulk and single-URL paths." | 1 (facets of one job) | PASS | Bulk and single-URL crawling are two execution paths of the same domain. |
| SRP-PASS-2 | "This file manages export generation including pivot table assembly and Excel formatting." | 1 (facets) | PASS | Pivot assembly and Excel formatting are sequential steps in one pipeline. |
| SRP-PASS-3 | "This file implements the crawl job lifecycle: creation, pause/resume, cancellation, and progress tracking." | 0 (list items) | PASS | All are facets of one domain object's lifecycle. Comma-separated lists about one topic count as 0 "and"s. |
| SRP-FAIL-1 | "This file handles product imports and interchange lookups and crawling and discovery and extraction and export." | 5 | FAIL | Six separate domain responsibilities. Each "and" separates an independently understandable domain. |
| SRP-FAIL-2 | "This file manages crawling configuration and image downloading and PTID classification." | 2 (genuinely separate) | FAIL | Crawl config, image downloads, and PTID classification have no shared domain concept. |
| SRP-EDGE-1 | "This file handles discovery field matching and validation feedback refinement." | 1 | PASS | Refinement-via-feedback is how matching works — not separable without breaking the algorithm. |
| SRP-EDGE-2 | "This file handles user authentication and session management." | 1 | PASS | Auth and sessions are tightly coupled by protocol — splitting them creates import cycles. |

**Evaluation rule:** "and"s that connect facets of a single domain (different execution paths,
sequential pipeline steps, object lifecycle phases) count as 0. "And"s that connect independently
understandable domains (you could explain one to a new hire without mentioning the other) count as 1.

## Gate 2 — DRY (no duplication within or across new files)

### Test: pattern repetition check

| Scenario | Pattern | Count | Expected | Why |
|----------|---------|-------|----------|-----|
| DRY-PASS-1 | Each domain file has one try/except with domain-specific recovery logic | 1 per file | PASS | Each instance has different recovery logic — structurally similar but semantically different. |
| DRY-PASS-2 | Two files both `from core.services.proxy_crawl import ProxyCrawlService` and call `.fetch_html()` | N/A | PASS | Using a shared service is the OPPOSITE of duplication — it's the consolidated form. |
| DRY-FAIL-1 | 94 identical `try/except Exception as e: logger.error(e); obj.status='failed'; obj.save()` blocks | 94 | FAIL | Same structure, same recovery, same side effects. Should be a decorator or context manager. |
| DRY-FAIL-2 | 11 copies of proxy-setup: `session = requests.Session(); session.proxies = {...}; session.headers = {...}` | 11 | FAIL | Identical setup code. Should be a factory function or service method. |
| DRY-FAIL-3 | Each new domain file defines its own `_get_progress_key(task_id)` with identical logic | 4 | FAIL | Cross-cutting concern cloned per domain. Belongs in a shared module. |
| DRY-EDGE-1 | Two files have similar but not identical retry logic (different backoff, different max_retries) | 2 | PASS | Parameterized differences. Consider a shared function with config args, but don't fail the gate. |

**Evaluation rule:** duplication means "same structure AND same semantics." Two try/except blocks
with different recovery strategies are not duplicates. Two try/except blocks with identical recovery
(only the wrapped call differs) are duplicates.

## Gate 3 — Linear flow (trace one function in one file)

### Test: can a reader follow start-to-finish?

| Scenario | Structure | Expected | Why |
|----------|-----------|----------|-----|
| LINEAR-PASS-1 | `bulk_crawl_task` calls `_prepare_batch()` and `_process_item()`, both in same file | PASS | All helpers co-located. Reader scrolls, doesn't file-hop. |
| LINEAR-PASS-2 | `bulk_crawl_task` calls `ProxyCrawlService.fetch_html()` from a shared service | PASS | Calling a shared service is expected — stable interface, no need to read internals. |
| LINEAR-PASS-3 | `export_task` calls `PivotService.build_pivot()` then `ExcelFormatter.write()` | PASS | Two service calls with well-defined contracts. Flow is linear despite delegation. |
| LINEAR-FAIL-1 | `bulk_crawl_task` in `tasks_crawling.py` calls `_apply_rate_limit()` from `tasks_export.py` | FAIL | Private helper in a different DOMAIN module. Should move to caller's file or become a shared service. |
| LINEAR-FAIL-2 | `export_task` calls `_format_row()` defined 3000 lines away past 4 unrelated clusters | FAIL (pre-split) | Linearity failure the SOLID audit (§1.2.5 Step 4) should catch. After split, both land in same file. |
| LINEAR-EDGE-1 | `task_A` in `tasks_crawling.py` calls `task_B.delay()` in `tasks_discovery.py` | PASS | Async task dispatch across domain boundaries is fine — it's a message, not a synchronous call. |

**Evaluation rule:** "leaving the file" to call a shared service or dispatch an async task is fine.
"Leaving the file" to call a private helper in a sibling domain module is a linearity failure.

## Gate 4 — Size advisory

### Test: LOC thresholds and re-check triggers

| Scenario | LOC | Gates 1-3 | Expected | Why |
|----------|-----|-----------|----------|-----|
| SIZE-PASS-1 | 566 | All pass | PASS (no action) | Under 800, all gates pass. Cohesive file. |
| SIZE-PASS-2 | 820 | All pass | PASS (after re-check) | Over 800 triggers re-check, but all gates pass. |
| SIZE-PASS-3 | 400 | All pass | PASS | Well under any threshold. |
| SIZE-FAIL-1 | 400 | Gate 1 fails (3 "and"s) | FAIL | LOC is fine but file covers 3+ domains. LOC alone would miss this. |
| SIZE-FAIL-2 | 1100 | All pass | ESCALATE | Over 1000 hard ceiling. Escalate to user even with passing gates. |
| SIZE-RECHECK-1 | 850 | Gate 2 fails (6 duplicated blocks) | FAIL | Over-800 re-check caught duplication that should have been consolidated. |

**Evaluation rule:** LOC never approves a file by itself. Passing Gates 1–3 approves a file up
to 1000 LOC. Above 1000, human judgment required regardless of gate results.

## Gate 5 — Interface depth advisory

Use `.claude/skills/_common/interface-depth.md` for the full rubric. This
gate applies to new public service methods, shared helpers, and adapter
seams created by the refactor.

| Scenario | Interface shape | Expected | Why |
|----------|-----------------|----------|-----|
| DEPTH-PASS-1 | One service method hides retry policy, transaction shape, and failure return from 4 callers | PASS | Deleting it would spread policy back across callers. |
| DEPTH-PASS-2 | A helper builds a provider-specific request payload used by 3 providers, while callers keep their retry policy | PASS | It hides real repeated knowledge without collapsing load-bearing divergence. |
| DEPTH-FAIL-1 | Helper only wraps `Model.objects.get(pk=x)` and is called once | FAIL | One-call pass-through; deletion removes ceremony. |
| DEPTH-FAIL-2 | New port has one production adapter and tests mock internal methods instead of using a fake adapter | FAIL | Hypothetical seam plus wrong test surface. |
| DEPTH-EDGE-1 | Domain file created by decomposition has a broad import surface but no new service interface | ADVISORY | Decomposition can improve locality without creating a deep public module; note follow-ups rather than blocking. |

**Evaluation rule:** new interfaces should remove caller knowledge. If
callers still need the same invariants, ordering constraints, error modes,
and resource policy, the interface is shallow even if LOC went down.

## Gate 6 — Post-extraction service shape

Use this after a view/task refactor creates or significantly grows a
service. The goal is to catch "fat view became god service" without
blocking legitimate transitional consolidation.

| Scenario | Service shape | Expected | Why |
|----------|---------------|----------|-----|
| SERVICE-PASS-1 | `SiteStatusService` owns one canonical status producer used by dashboard, polling, sidebar, and prototype presenters | PASS | Multiple renderers consume one concept; the service is the shared producer, not a grab bag. |
| SERVICE-PASS-2 | `SettingsProxyService` owns proxy validation and credential normalization only | PASS | Credentials and network validation are one focused boundary. |
| SERVICE-ADVISORY-1 | One service temporarily owns setup dashboard, polling payload, sidebar status, and prototype presentation but exposes separate methods and has renderer parity tests | ADVISORY | Healthier than view duplication, but monitor for future split once the canonical producer is stable. |
| SERVICE-FAIL-1 | One service owns settings credentials, email diagnostics, raw curl commands, profile persistence, and unrelated admin UI JSON | FAIL | Independent authorities with different security and side-effect rules were moved into a new omnibus. |
| SERVICE-FAIL-2 | Service methods mostly return template-ready dictionaries while callers still know retry, auth, transaction, and resource policy | FAIL | The interface is shallow and the old caller knowledge leaked through. |

**Evaluation rule:** services may coordinate multiple presenters of the
same concept, but they should not become a parking lot for every block
removed from a view. When a service fails only by size but passes SRP,
DRY, linear-flow, and interface-depth checks, record a Phase 7 monitor
entry instead of forcing an immediate split.

## Mode detection scenarios

### Test: when to activate decomposition mode

| Scenario | code_roots | LOC | SRP "and"s | Expected mode | Why |
|----------|-----------|-----|------------|---------------|-----|
| MODE-STD-1 | 3 files (views, service, model) | 600+300+200 | N/A | Standard | Multiple files, no single dominant file. |
| MODE-STD-2 | 1 file | 1500 | 1 | Standard | Under 2000 LOC threshold. |
| MODE-STD-3 | 1 file | 2500 | 2 | Standard | Over 2000 LOC but only 2 "and"s — facets of one domain. |
| MODE-DECOMP-1 | 1 file | 10453 | 5 | Decomposition | Classic case: massive file with many separate domains. |
| MODE-DECOMP-2 | 1 file | 2651 | 4 | Decomposition | Medium-large file with clear domain separation (crawling-views dogfood). |
| MODE-MIXED-1 | 5 files (1x8000, 4x200) | 8000 dominant | 4 | Decomposition (dominant) + Standard (satellites) | Edge case: decompose the big file, standard-mode the rest. |

## Worked example: `core/tasks.py` SOLID audit

This is the analysis from the crawling-views dogfood (2026-04-13) that motivated
decomposition mode. Use it as a reference for how the §1.2.5 audit should read.

### Input
- File: `core/tasks.py` — 10,453 LOC, 41 tasks, 152 commits

### Step 1 — SRP sentence test
"This file handles product imports and interchange lookups and crawling and discovery
and extraction and export and image downloading and health checks."
→ **5 "and"s** → clear decomposition candidate.

### Step 2 — Responsibility clusters

| Cluster | Tasks | LOC | Target file |
|---------|-------|-----|-------------|
| Import & Validation | 2 | 171 | `tasks_import.py` |
| Interchange Lookup | 4 | 459 | `tasks_interchange.py` |
| Crawling (bulk/single) | 11 | 1,983 | `tasks_crawling.py` |
| Discovery | 3 | 530 | `tasks_discovery.py` |
| Extraction & AI | 5 | 1,382 | `tasks_extraction.py` |
| Export & Reporting | 4 | 1,245 | `tasks_export.py` |
| Images & Downloads | 5 | 1,557 | `tasks_images.py` |
| Health/PTID/ExternalSource | 6 | 230 | `tasks_health.py` |

### Step 3 — Intra-file DRY scan

| Pattern | Count | Proposed consolidation |
|---------|-------|----------------------|
| `try/except Exception → logger.error → obj.status='failed' → obj.save()` | 94 | `@task_lifecycle(status_field='crawl_job')` decorator |
| Proxy setup sequence | 11 | `ProxyCrawlService.fetch_html` (partially done) |
| Progress tracking (Celery `update_state` vs cache-based) | 2 systems | Unified progress abstraction |

### Step 4 — Linear flow test
- **`bulk_crawl_sitemap_products_task`** (large): calls `crawl_with_direct_requests()` defined
  8000 lines away, past 5 unrelated clusters. **FAIL** — helper must move with caller.
- **`import_products_task`** (small): self-contained except for model imports. **PASS**.
- **`extract_pricing_data_task`** (medium): calls `save_html_to_file()` from the helpers block
  (675 LOC at lines 42-718). **FAIL** — storage helper is cross-cutting, belongs in a service.

### Audit verdict
Decomposition mode. 8 clusters. 3 cross-cutting concerns for Batch 1. 675 LOC of helpers
at file top to extract into services as part of the domain split.
