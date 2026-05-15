# scenario-extraction-truth-set

Contract for `extract-existing-ideas` (P5). A synthetic micro-repo
containing:

- `BACKLOG.md` with three open items
- `lessons.md` with one harvested lesson
- `plans/feature-a.md` with two plan items
- `decisions/0001-foo.md` (a synthetic ADR)
- `scratch/half_done_prototype.py` (a likely file-orphan)

The expected output is a list of candidate intake records that
`extract-existing-ideas` should propose. The list is not exhaustive —
it captures the items the extractor MUST surface from each source
type.

Skipped until P5 lands `extract_candidates` in `ideas_lib`.
