# /explain-code — output format

Every `reports/explanations/<target-slug>.md` follows the same shape so
a reader can absorb it without the skill loaded. This doc is the
canonical reference for what Stage 3 emits.

For TypeScript v1, this format is intentionally honest about lexical limits:
the `Unexplained regions` section includes any `export { ... }`, `export *`,
or unresolved default export reported by `targets.json`. These entries are not
annotation failures; they are evidence that module resolution was not claimed.

## Structure

1. Target metadata (front-matter-ish, one code block).
2. Summary (≤5 sentences).
3. Public contracts — one `###` subsection per annotated symbol.
4. Unexplained regions — aggregated from scout outputs.
5. Follow-on findings — adjacent rot surfaced during annotation.
6. How to regenerate — one-line command.

## Target metadata

```markdown
# Explanation — core/services/agentic_discovery_service.py

| Field | Value |
|---|---|
| Target | `core/services/agentic_discovery_service.py` |
| Slug | `services-agentic-discovery-service` |
| LOC | 1635 |
| Public symbols (total) | 7 |
| Annotated this run | 5 |
| Overflow | 2 (see targets.json) |
| Regenerated | 2026-04-19T22:30:00Z |
```

LOC comes from `wc -l` on the file (or sum for a directory). Public-
symbol and annotated counts come from `targets.json`. Regenerated is
the UTC timestamp at the start of Stage 0.

If this is a refresh, the previous timestamp shows up as a
`| Prior run | 2026-03-22T14:10:00Z |` row. Do not attempt a diff
section — the git history of `<target-slug>.md` is the diff.

## Summary (≤5 sentences)

A paragraph-sized prose block. Writes to the reader's trust-building
goal: after reading this paragraph, what does the reader know that
they did not know before? Example:

```markdown
## Summary

`agentic_discovery_service.py` owns the agentic sitemap-discovery
pipeline. One public class (`AgenticDiscoveryService`) drives a
multi-phase loop that fetches `robots.txt`, calls LLMs to classify
sitemap URLs, samples candidate product URLs, and compiles a result
dict. State flows through an implicit dict (`state = {...}`) mutated
across ten private helpers. The class enforces budget caps on AI
calls, sitemap fetches, and page fetches — but does not enforce a
typed contract on the state dict itself, which makes every private
helper's precondition set implicit. Exports to callers are the
compiled result dict, not the live state.
```

Rules for this section:

- Must state **what it does** (job / behavior).
- Must state **what it enforces** (budget, timeouts, typed returns).
- Must state **what it does NOT enforce** — this is the paragraph's
  load-bearing line. Readers use it to anticipate pitfalls.

## Public contracts

One `###` subsection per annotated symbol, pulling fields directly
from the per-scout annotation files. Order matches `targets.json`
(rank-score descending).

```markdown
### AgenticDiscoveryService.discover

**Kind:** method.

**Intent.** Entry point for agentic sitemap discovery. Given a base
URL, fetches robots.txt, classifies sitemaps via an LLM, samples
product URLs, and returns a compiled result dict.

**Preconditions.**
- `base_url` is an http(s) URL; `urlparse(base_url).netloc` is non-empty.
- `progress_callback` is either None or a callable accepting one dict.
- `self.client` (OpenAI) is ready — set in `__init__`.

**Postconditions.**
- **Success:** returns `{sitemaps, patterns, samples, errors}` from
  `_compile_results(state)`.
- **Failure:** returns the same dict shape with partial fields; does
  NOT raise.
- **Side effects:** decrements `state['budget']['pages_remaining']`
  per page fetch; invokes `progress_callback(phase, detail)` at every
  phase boundary.

**Invariants.**
- `state['iteration']` is monotonically non-decreasing.
- `state['budget']` fields never go negative — exhaustion causes
  loop exit, not under-flow.

**Callers (2 total).**
- `core/views/sitemaps.py:RunAgenticDiscoveryView` — expects the
  compiled result dict.
- `core/tasks.py:agentic_discovery_task` — expects the same shape;
  forwards progress to the task status store.

**Surprises.**
- Mutates an implicit dict shape (`state = {...}`) with no typed
  contract — candidate for `/extract-state-type` (see smell 2,
  stringly-typed state sub-shape).
- The `_report` closure captures `state` by reference; callers of
  `progress_callback` read budget counters that can change between
  invocations.
```

The **Surprises** subsection is only rendered if the scout flagged
something. If all scouts returned "No surprises", the subsection is
omitted.

Every surprise also gets written as one line to
`${REPORT_DIR}/surprises.txt` so Stage 4 can count them without
re-parsing markdown. One line per entry, format
`- <symbol> — <surprise>`. Create the file even when there are no
surprises; an empty file means the count is zero.

## Unexplained regions

Aggregated from every scout's "Unexplained regions" block. Each entry
is one line with:

- Symbolic anchor (the scout's `where`).
- One-line reason.
- Suggested deeper target (concrete `/explain-code <path>` command).

```markdown
## Unexplained regions

- `_ai_analyze_robots` — calls a prompt-builder owned by
  `ai_training/_llm_kwargs.py`; unclear how kwargs interact with
  OpenRouter vs Fireworks routing. Re-run:
  `/explain-code core/services/ai_training/_llm_kwargs.py`.
- `_sample_candidate_urls` — depends on `SitemapService.download_xml`
  behavior under gzip + redirect; the scout could not confirm without
  reading `sitemap_service.py`. Re-run:
  `/explain-code core/services/sitemap_service.py`.
- `_normalize_robots_analysis_urls` — the URL normalization rules are
  scattered across three helpers; the scout flagged `_absolute_url`,
  `_strip_fragment`, and `_canonicalize_netloc` as follow-ons.
```

If no regions are unexplained across all scouts, omit the section
entirely — empty sections are noise.

Every entry also gets written as one line to
`${REPORT_DIR}/unexplained.txt` so Stage 4 can count them without
re-parsing markdown. One line per entry, format
`- <symbol> — <reason>`. Create the file even when there are no
unexplained regions; an empty file means the count is zero.

## Follow-on findings

Adjacent rot surfaced during annotation. These are candidates for
future `/find-*` runs or `/fix-workflow` executions, NOT TODOs this
skill owns. Every entry cites a concrete next command:

```markdown
## Follow-on findings

- Five private helpers mutate `state` directly without a helper —
  candidate for `/find-duplication` on this file to surface the
  pattern before extracting to a `DiscoveryState` dataclass.
- Zero-caller symbols: `_legacy_classify_robots` (scout found no
  inbound callers). Candidate for `/find-dormant`.
- `_call_llm` is one of the `keep_separate_document_why` shadows
  (SC-3 family). Already addressed; no action needed here.
```

Omit the section if all scouts returned zero follow-ons. Keep
bullets to one line each — deep details live in the per-scout
annotation files.

## How to regenerate

Literal single-line code block. Nothing else:

```markdown
## How to regenerate

```bash
/explain-code core/services/agentic_discovery_service.py
```
```

## Worked example (small target)

A complete rendered doc for a small single-function target — treat
as the canonical output shape.

```markdown
# Explanation — core/input_utils.py

| Field | Value |
|---|---|
| Target | `core/input_utils.py` |
| Slug | `input-utils` |
| LOC | 62 |
| Public symbols (total) | 3 |
| Annotated this run | 3 |
| Overflow | 0 |
| Regenerated | 2026-04-19T22:30:00Z |

## Summary

Three-function module owning safe coercion of untrusted request data.
`safe_int` clamps, `safe_load_json_body` decodes + returns None on
parse failure, `load_json_body_or_400` does the same but raises to an
HTTP 400. The module enforces the "no bare `int()` on request data"
canonical pattern; it does NOT enforce JSON schema — callers validate
fields after decode.

## Public contracts

### safe_int

**Kind:** function.

**Intent.** Coerce a value (usually a request-body string) to an
`int` with a fallback and an optional min/max clamp.

**Preconditions.** None beyond the signature types.

**Postconditions.**
- **Success:** returns an int in `[min_val, max_val]`.
- **Failure:** returns `default` on `ValueError`, `TypeError`, or
  `None`.
- **Side effects:** none.

**Invariants.** Returned value is always an int, never the raw
input string.

**Callers (34 total).**
- `core/views/crawling.py:CrawlJobDispatchView.post` — expects an int.
- `core/views/field_config.py:FieldConfigSaveView.post` — expects an int.
- + 32 more across `core/views/`.

### safe_load_json_body

… (one subsection per symbol)

## How to regenerate

```bash
/explain-code core/input_utils.py
```
```

## Rendering rules

- UTC timestamps in the metadata table. `YYYY-MM-DDTHH:MM:SSZ`.
- Tables use right-alignment on numeric columns.
- Never inline code from the subsystem into the doc — the explanation
  is about behavior, not about code bytes. If a reader needs the code,
  they read the file.
- If any section would be empty AND the scan ran without error, omit
  the section header entirely. Empty sections are noise.
- If a scout returned `not_found` or `annotation_incomplete`, render
  its subsection with:

  ```markdown
  ### <symbol>

  **Status:** annotation_incomplete — the scout timed out / could not
  locate the symbol. Re-run `/explain-code <target>` to retry.
  ```

  Do NOT omit failed scouts; the record of what failed is part of the
  doc's value.
