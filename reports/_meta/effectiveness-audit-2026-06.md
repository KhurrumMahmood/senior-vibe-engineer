# Effectiveness-system audit — findings & fixes

**Scope:** the skill-effectiveness measurement system (`reports/_meta/`,
`scripts/skill_effectiveness.py`, `scripts/log_effectiveness.py`) and the VISION
claim it underwrites.
**Date:** 2026-06-08.
**Method:** a disinterested external lens-set audited a digest of this slice; every
claim below was then re-verified against actual source (file:line cited).
Interpretive findings (#4, #5) are labelled as such — they are analysis, not source facts.

## Bottom line

The system named "effectiveness" measures **activity**, not **outcome**: it records
how much each skill *fires*, never whether firing led to a fix that *landed and held*.
By construction it cannot record an ineffective skill — runs only ever add findings.
Three issues are mechanical (fixable now); two are architectural (need an ADR). The
deepest is conceptual: the instrument is applied to the very system it is meant to
vindicate, which makes every self-scan sign-ambiguous.

## Findings

### 1 — No outcome/closure axis: "effectiveness" can only go up  · VERIFIED
`log_effectiveness.py:83-92` writes `{skill, scan_id, ts, target, findings_total,
buckets, notes}` — there is no `actioned`/`fix_landed`/`resolved`/`regression_held`.
`skill_effectiveness.py` aggregates purely by counts (`:71,74`), name-sorts skills
(`:92`), ranks targets by run-count (`:113`). A grep across `scripts/` + `.claude/skills/`
finds zero closure fields written to the log; the `buckets` keys are severity/category,
never closure state. `reports/_meta/README.md` even frames the intended signal as
"fewer findings over time" — yet the metric only accumulates and the dashboard ranks by
*total* findings, so "fewer is better" and "rank by most" pull in opposite directions.

- **Consequence:** a skill emitting 83 never-actioned findings scores identically to one
  that drove real repair.
- **Fix:** add a post-disposition field keyed back to each finding
  (`actioned`/`fix_landed`/`regression_held`); rank by durable-change rate.
- **Reuse — with a caveat the verification caught:** es2 *already ships* an outcome
  vocabulary — `VALID_OUTCOMES = {adopted, rejected, deferred, harvested, superseded}`
  (`.claude/skills/_common/ideas_lib.py:28`) with enforced `--outcome`
  (`track-idea/scripts/track.py:306,142-143`). **But it lives in the idea ledger, a
  separate subsystem, and is never connected to `effectiveness.jsonl`.** So the gap is
  not "es2 lacks the concept of outcomes" — it is "the findings log was never given an
  outcome field, and the existing outcome machinery was never wired to it." Until one
  exists, **rename the dashboard "activity / coverage," not "effectiveness."**

### 2 — Headline ranking sums actionable + advisory + false-positive into one number  · VERIFIED
`findings_total` is the ranking key, unweighted. In the logged data `find-comment-drift`
ranks **first at 83**, composed almost entirely of cosmetic buckets
(`detached_section_banner` 56, `obvious_narration_comment` 14,
`missing_public_class_docstring` 11); `find-rule-surface-drift`'s 14 is ~2 actionable;
`find-omnibus`'s 6 includes 4 false-positives. Ranking by volume **rewards the noisiest
detector.**

- **Fix:** rank by an above-floor count (false-positives subtracted, advisory
  down-weighted) — derivable from the `buckets` already logged; show `findings_total`
  only as a secondary "flag volume" diagnostic.

### 3 — Dashboard ~3 weeks stale and structurally unable to fall  · VERIFIED
`dashboard.md` (mtime May 17) says **"5 run(s)"** and shows newest ts 2026-05-16;
`effectiveness.jsonl` has **8 lines**, newest ts **2026-06-08**. Three entries are absent
from every table — `find-complexity-hotspots`, `map-product-workflow`, `which-cleanup` —
including `map-product-workflow`'s **0**, the one downward datum, which sits *outside* the
artifact that states the verdict. No `2026-06` column exists despite a June run.

- **Cause (verified):** regeneration is unenforced — only manual prose in
  `reports/_meta/README.md` ("Regenerate after appending runs — the file is otherwise
  stale"); no CI (`.github/workflows/ci.yml`) or pre-commit step touches it.
- **Fix:** regenerate on read or in CI; assert `run_count == jsonl line-count` and
  `max(ts) <= dashboard date`. Never publish an aggregate older than its inputs.

### 4 — Keystone: the instrument is the measured object  · INTERPRETIVE
Skills are validated *by running them on es2 itself*, and es2's success is *defined* as
having no debt (VISION). So one datum carries opposite meanings at once: an actionable
finding means both "the detector works" **and** "es2 is not at its destination," and
`find-stale-artifacts: 0` is equally "clean" or "detector insensitive." VISION calls this
self-application **"the strongest test of whether the skills work"** (`VISION.md:77-78`) —
placing maximum confidence on the least interpretable evidence. This sits *upstream* of
#1–#3 and survives even a perfect outcome metric, because measurer and measured are one
entity.

- **Fix:** validate each detector on an **external corpus with known-planted debt** to fix
  its *sign* before pointing it at es2; and state explicitly that a non-zero self-scan is
  a *failure of VISION's destination*, not a *success of the skill* — one run cannot claim
  both.

### 5 — VISION's gate is concluded before it is run  · INTERPRETIVE
VISION names the test (the "strongest test"; the newcomer one-liner) and, in the same
Status section, pre-states that "the machinery to reach this destination largely exists"
about a review only "begun 2026-05-25" (`VISION.md:77-79`). Nothing in the logged data
operationalizes the newcomer-comprehension criterion (the metrics are banner counts, doc
references, folder names).

- **Fix:** run a held-out cold-agent comprehension trial scored against the one-liner
  before any "largely exists" verdict — or restate the line as untested aspiration.

## What is *not* broken (so the critique stays calibrated)

The prompt-only judgment skills were checked and cleared: `gut-check` self-discloses
"signal, not verdict" and "no reactions is a valid output," and
`senior-engineer-posture.md` is a process norm with no estimand — neither claims to
*measure* anything, so the metric critique above does not apply to them. (Any concern with
those belongs to a separate "is the guidance a trigger or just aspiration" review, not to
the effectiveness metric.)

## Sequencing

- **Mechanical — reversible, safe to do now:** #3 (dashboard regen + CI freshness guard),
  #2 (re-rank from the existing `buckets`), the #1 rename to "activity / coverage."
- **Architectural — needs an ADR + human sign-off (do not let an agent rearchitect these
  unilaterally):** #1 (an outcome field threaded across skills + wiring in the idea-ledger
  vocabulary), #4 (the external-validation-corpus methodology), #5 (operationalizing the
  comprehension gate).

## Provenance

Produced by a disinterested multi-lens audit of a digest of this slice, then
**source-verified** against actual files (every `VERIFIED` claim carries a file:line).
The audit's own headline (activity ≠ outcome) was partly shaped by how the digest framed
it; that framing risk was controlled for in a separate re-test. Findings #1–#3 rest on the
source verification, not the audit's framing, and stand on the file:line evidence alone.
