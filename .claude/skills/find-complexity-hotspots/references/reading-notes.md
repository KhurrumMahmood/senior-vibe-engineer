# Complexity Hotspot Reading Notes

Use these notes to interpret `find-complexity-hotspots` findings. The
scanner emits leads, not verdicts — these notes help judge which leads
are worth a follow-up.

## High-value paths

Some areas magnify complexity findings; scan and weight them first:

- **Bulk data-shaping paths** — code that builds rows, exports, or
  transforms large collections. Nested loops, repeated mapping, and
  per-item normalization scale with the collection size.
- **Pipeline / discovery loops** — repeated per-page or per-sample
  passes, plus input construction that grows with the work set.
- **Network / retry code** — distinguish CPU complexity from I/O cost.
  Retries are usually slower than the surrounding Python loops, so a
  "hotspot" there may be an I/O-bound path, not an algorithmic one.
- **Render / poll paths** — repeated ORM calls are user-visible when
  they run during a page render or a status poll.

## Django checks

For `django-query-in-loop`, read the whole loop and verify:

- the query depends on the loop item,
- filters include the same tenant/owner/visibility constraints,
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
