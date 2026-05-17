# PNCI Complexity Hotspot Reading Notes

Use these notes to interpret `find-complexity-hotspots` findings.

## High-value paths

- Exports and row builders: large product sets magnify nested loops,
  repeated mapping, brand normalization, and PartShare lookups.
- Site Intelligence discovery/extraction: repeated page/sample loops,
  image URL processing, and prompt-input construction can grow quickly.
- Scrapers and custom-site imports: network retries are often slower
  than Python loops; distinguish CPU complexity from I/O cost.
- Dashboard/status providers: repeated ORM calls are user-visible when
  they run during page render or polling.

## Django checks

For `django-query-in-loop`, read the whole loop and verify:

- the query depends on the loop item,
- filters include the same site/job/brand/visibility constraints,
- `.select_related()` or `.prefetch_related()` would actually cover the
  accessed relation,
- missing-record behavior stays the same,
- ordering and pagination are preserved,
- caching has an invalidation story.

Prefer a bulk fetch keyed by stable IDs when the loop body repeatedly
looks up rows from the same model. Prefer service-layer precomputation
when several callers need the same grouped data.

## Refactor checks

For `high-branch-function`, do not split purely by line count. First
identify the hidden contract: state machine, pipeline phase, row
builder, adapter, or validation gate. Use `/explain-code` when the
contract is unclear and `/refactor-subsystem` only when there is a
spec-backed boundary to move toward.
