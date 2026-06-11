# Inward Pass — 02: Does the ecosystem embody its own vision?

Capstone of the combined inward pass, 2026-05-25. Read-only diagnostic, ES3
sandbox corpus (67–68 skills + `_common`).

This pass answers VISION.md's own stated self-test (VISION.md:76):

> The ecosystem must embody this destination in its own structure — that is the
> strongest test of whether the skills work… early finding: the machinery to
> reach this destination largely exists but has never been pointed at the
> ecosystem itself.

So we pointed it. Two layers, three pillars:

| Pillar | Question | File | Result |
|---|---|---|---|
| Structural — ideas | Are the real ideas explicit & de-dup-able? | `02c-ideal-shape-and-ideas.md` | 68 skills → **~10 ideas**; flat → **~7–8 packages** |
| Structural — code | Do the idea *families* share **code**, or just names? | `02a-mechanical-duplication.md` | **8 clusters**, ~2,700 LOC near-verbatim clone; `_common` exists but bypassed |
| Behavioral | Do the skills actually **work** (graded by side-effect)? | `02b-behavioral-conformance.md` | Only **1 of 68** is provable as-is (bucket A); 26 B, 40 C |

## Triangulation — three axes, one finding

The three pillars measure independently — idea-cluster count, code-clone
families, behavioral gradeability — and **converge on the same imbalance**:

- 02c counts it structurally: **detect 27 : guard 1**.
- 02a shows the detectors are also the corpus's **worst-duplicated** code (the
  drift-detector `run/report/smoke` scaffold is cloned 4–6×).
- 02b shows that imbalance behaviorally: the lone **guard** is the **only**
  skill skill-comply can grade in its strongest "did it fire on a real bug"
  sense; the 27 detectors are advisory lists with no firing oracle.

Three lenses agreeing is itself the result: the finding is **structural, not a
lens artifact**.

## Scorecard — the 5 destinations

| # | Destination (VISION) | Verdict | Evidence |
|---|---|---|---|
| 1 | Ideas explicit + **DRY** | **Split** — concept-DRY ✓, code-WET ✗ | 02c: 68→~10 nameable ideas (explicit ✓). 02a: ~800 LOC P0 scaffold clone + ~1,900 LOC report scaffold + helpers cloned 6–12× (DRY ✗). The corpus can't even fully run its own `find-duplication` on itself — **jscpd not installed**. |
| 2 | Right ideas → standards, **activated** | **Weakest / unmet** | 02c: detect 27 : guard 1. 02b: only `prevent-regression` emits an *activated, re-runnable* guard; 26 could be activated with new oracles but aren't; `audit-decisions` is *labeled* `job: guard` yet emits an advisory report. |
| 3 | **Ideal shape** (SOLID) | **Latent, unrealized** | 02c: flat 68 → ~7–8 idea packages derivable *by hand*, but `propose-folder-reorganization` is scoped to underscore *module* siblings and **can't reach hyphen-dir grouping**. VISION:66 itself flags `audit-project-shape`/`propose-architecture` as "still-unbuilt." |
| 4 | **Instantly legible** | **Partial** | Idea/job taxonomy is legible *once surfaced*, but a newcomer landing on `.claude/skills/` sees **68 flat dirs, not 10 ideas**, and 02a's ~2,700 LOC of near-identical scaffold makes essential-vs-boilerplate undecidable on first read. |
| 5 | **Comprehension maintained** | **Served but self-undermining** | 13 drift detectors give strong self-maintenance coverage — but 02a shows those same detectors are the **most-cloned** part of the corpus. The machinery that keeps comprehension is the least DRY code in it. |

## The unifying meta-pattern

Across all five destinations the same shape recurs: **the ecosystem is strong at
DETECTION and weak at the CONSTRUCTIVE / ACTIVATION side.** One level down, the
recurring failure is sharper and more specific — **the mechanism exists but is
not adopted**:

- `_common/` exists (`product_health`, `product_topology`, `relpath`,
  `render_simple_report`, `run_skill_smokes`) → **9 detectors bypass it**;
  `check.py` re-defines a `relpath` already importable from `_common` (D1).
- the `guard` job exists → it holds **1 real skill**, and `audit-decisions`
  mislabels itself into the count (D2).
- `propose-folder-reorganization` exists → it **can't reach its own corpus's
  shape** (D3).
- 13 drift detectors exist → they've **never been comprehensively pointed at the
  ecosystem itself** (D5; VISION/README still uncommitted, no self-drift gate).

That is precisely the **activation gap the ecosystem is built to catch in host
projects, reproduced in the ecosystem itself.** It under-adopts its own
machinery — the exact "got it done, the machinery exists but was never wired"
failure VISION destination 2 names. VISION:78 predicted this in one line; this
pass measures it across all five destinations.

## Verdict

**The ecosystem has the engine but has not run it on itself.** It embodies the
*detection* half of its vision (D1-concept, D5-coverage) and not the
*construction / activation* half (D1-code, D2, D3). D4 sits in between, dragged
down by the unrealized shape and the scaffold clone.

The single highest-leverage move is **not building new skills** — it is
**adopting the machinery that already exists, on the corpus itself**: wire
`_common`, extract the scaffold, build the dir-grouping shape mode, and promote
1–2 bucket-B skills to activated guards. The vision is closer than it looks; the
gap is adoption, not invention.

## Dispositions

### fix-now candidates (trivial, but they touch the *canonical* corpus → need a go + a target call)

This pass is a read-only diagnostic in the **disposable es3 sandbox**; the real
corpus is **es2** (and whatever becomes v3). So these are surfaced for the user
to greenlight, not auto-executed — and they carry an open **es2-vs-es3 target
question** (the clones almost certainly exist in es2 too, since es3 derived from
it). Sequenced cheapest-first, all are "adopt your own `_common`":

1. **P2** — `check.py` import `relpath` from `_common` instead of re-defining (1 line).
2. **P1** — move `_walk_python_files` (2-arg form) + `_segment_source` into `_common/product_health.py`; `_read_jsonl` into a shared util (~300 LOC of clone deleted).
3. **P0** — extract the drift-detector `run/report/smoke` scaffold to parametrized `_common` templates (~800 LOC clone → skill-name/title/expected-patterns args).
4. **P1** — design a `BaseSkillReporter` / `render_triage_report(...)` for the 5 collapse-family `report.py` files (~1,900 LOC → ~800; needs the protocol shape decided first — a `design-it-twice` candidate, not a blind extract).

### log-later — recorded as evidence on EXISTING intakes (no new minting)

Reconciliation result: **both intakes this pass would have created already exist
in the es2 ledger under other names.** The ledger's own anti-duplication purpose
caught the inward pass about to commit the exact DRY violation it measures — a
clean dogfooding moment. Evidence was attached as `dev-note` events (+ `composes_with`
edges via `track.py`), not new intakes:

- D3 tool gap (02c) → **`skill-catalog-reorganization`** (already: "apply
  ≥3-sibling packaging to the flat `.claude/skills/`"). New evidence: 68 → ~7–8
  packages *measured*, the find-* sub-split, and the concrete blocker
  (`propose-folder-reorganization/inspect.py` is scoped to underscore module
  siblings and can't reach hyphen-dir grouping). Edged to `audit-project-shape` /
  `map-project-skill` / `propose-architecture-skill`.
- D1 code-DRY (02a) → **`ast-pipeline-detector-base`** (already: extract the
  detect→collapse→report triad to `_common`). New evidence *broadens its scope*:
  **two** scaffold families, not one — the collapse-triad (~1,900 LOC) **plus** a
  drift-quad `run/report/smoke` family (~800 LOC, P0-trivial) + orphan helpers
  (`_walk_python_files`/`_read_jsonl`/`_segment_source`) + the under-adopted
  `_common`. Edged to `skill-ecosystem-quality-gate` + `scout-batch-dispatch-wrapper`.
- smoke layer (02a) → **`skill-ecosystem-quality-gate`** (in-flight): the smokes
  it aggregates are themselves near-verbatim clones; a parametrized
  `_common/skill_smoke.py` collapse is adjacent to its planned backfill +
  catalog-vs-disk census.
- `audit-decisions` `job:guard`/advisory mismatch (02b) → **`instruction-artifact-coherence`**:
  a concrete smell-10 instance (frontmatter-claims-X / behavior-is-not-X),
  surfaced *behaviorally* rather than by text. Suggests a job-semantics axis — "a
  `job:guard` skill must emit a runnable guard."

Note: `skill-ecosystem-quality-gate`'s own summary already frames this pass's
meta-thesis ("a contract checker that runs nowhere protects nothing… turned
inward… 60+ host-project guards, almost no guards on the ecosystem's own
health"). The combined pass is **measured confirmation of an already-suspected
thesis**, not a novel claim.

### point-at-existing (do NOT mint duplicates)

- **Behavioral generality** → this pass IS the cross-skill-generality evidence
  (STAGE2 follow-up #4) for the **pnci** ledger's `skill-spec-conformance-validation`
  (parent; skill-comply is its realization) and `skill-comply-real-run-orchestration`
  (Stage 3 child). The buckets (A=1/B=26/C=40) and the **`antipattern_files`
  oracle blocker** are already owned by that lineage — cite, don't duplicate.
  (Not writing to pnci's ledger here: a co-located agent is active in pnci;
  avoid a concurrent jsonl-append race.)
- **Compiled-build fusion** → the "adopt your own machinery" finding is input to
  es2's `prod-build-compilation-pipeline` intake and the
  `explain-job-is-read-only-proposal.v1` precedent's compiled-build exception
  (a future build may deliberately fuse detect-propose-execute for speed; that
  does not supersede the source-regime split).

### monitor

- The **detect(27) : guard(1)** imbalance — re-measure as guard/construct skills
  land. It is the headline number for "does the ecosystem embody destination 2."
- The next behavioral pilots that would move bucket A past 1: `diagnose`
  (its `reproduction_loop` ≈ C4), `fix-workflow` (characterization tests),
  `find-standard-gaps` (`scan_coverage.py` is already deterministic).

## Cross-references

- Pillars: `02a-mechanical-duplication.md`, `02b-behavioral-conformance.md`,
  `02c-ideal-shape-and-ideas.md`.
- Prior self-review: `01-landscape-and-north-star.md` (§2 overlap clusters, §5
  "least-built corner," §7 F1 retraction, §8 the inward-pointing plan this
  closes).
- This session's es2 captures it leans on: `explain-job-is-read-only-proposal.v1`
  + `tests/test_skill_taxonomy.py` (the Record+Guard the taxonomy rests on),
  the `prod-build-compilation-pipeline` and `unguard-first-guard` intakes.
