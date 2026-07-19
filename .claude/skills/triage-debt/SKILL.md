---
name: triage-debt
description: Cross-cutting aggregator that scores accumulated debt across the maintenance loop's outputs (find-* report stacks, spec drift, decision drift, hard-size-overflow specs, recurring same-target hits) and produces a ranked queue at `reports/triage-debt/scan-<TS>/queue.md`. Each entry names the recommended next skill to invoke (refactor-subsystem / fix-workflow / extract-* / decide). Top-5 highlighted. Pure read — never edits production code, never runs find-*; reads the cached evidence those skills already produced.
argument-hint: "[--top N]  (default top=5; raise to see more)"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: triage
best_for: |
  Periodic (weekly / pre-cleanup-sprint) view of "what's accumulating".
  Surfaces three signals a single find-* skill cannot: (a) recurrence
  across runs (same skill+target hit repeatedly), (b) spec drift (IM-N
  unchecked > 60d), (c) decision drift (proposed > 30d, broken chains).
  Use when you have a maintenance window and want to know where it's
  best spent, not which one cleanup to do next.
not_for: |
  Detection of new smells (use a find-* SUSPECT skill — triage-debt only
  reads existing reports). Single-cluster execution (use /fix-workflow,
  /refactor-subsystem). One-off "is this file healthy" reads (use
  /map-subsystem). Decision-registry hygiene specifically (use
  /audit-decisions, which is narrower and more authoritative for that
  axis).
escalate_to: |
  None — this is a read-only aggregator. Each top-5 entry ALREADY names
  the next skill to invoke; the user picks one and proceeds.
delegate_from: |
  /which-skill recommends /triage-debt for vague prompts like "what
  should I clean up next" or "what's the worst tech debt right now".
language: any
framework: any
---

# /triage-debt

You are the **orchestrator** for the cross-cutting triage skill. The
deliverable is a ranked debt queue at
`reports/triage-debt/scan-<TS>/queue.md` whose top-N entries each
recommend a concrete next-skill invocation. You do NOT detect new
smells, do NOT run any `/find-*` skill, do NOT edit production code.

The whole point of this skill is to make accumulating debt **visible**
across the maintenance loop's outputs. A single find-* run sees one
slice; this skill compounds them so the user can prioritize without
re-running every detector.

## How success is judged

- `queue.md` is ranked by the Stage 2 score, and every top-N entry
  carries a one-line "why ranked here" rationale plus a concrete
  recommended-next skill invocation.
- The inputs that fed the ranking are declared — which find-* `latest`
  reports, `specs-audit.json`, `decisions-audit.json`, and
  `effectiveness.jsonl` were read, and which were missing.
- The final reply names the cached input path, the copied input files, and any
  unavailable axis from `inputs.md`. Claims without that provenance do not
  satisfy the gate.
- No new detection ran; no production code, spec, or decision status
  was touched — the run writes only under `reports/triage-debt/scan-<TS>/`.

## Core beliefs

1. **Recurrence is the strongest signal.** If `find-omnibus` has flagged
   `core/views/sites.py` three scans in a row and nothing has been done,
   that's worth more than a single P0 from a fresh scan elsewhere.
2. **Spec drift is debt.** A spec with IM-N items unchecked for 60+ days
   is either abandoned, blocked, or wrong — surface it so the user can
   decide which.
3. **Decision drift is debt.** A `proposed`-status ADR older than 30
   days means the team didn't actually decide; either accept, deprecate,
   or supersede.
4. **Hard size overflow is non-negotiable.** A spec with `loc >=
   SIZE_HARD_LOC` (1000) is over the architectural cliff; weight it
   heavily so it cannot be ignored.
5. **Parking is real.** A decision saying "leave foo alone until
   2026-Q3" is a legitimate park; subtract score so the queue doesn't
   keep nagging.
6. **Mass findings mean a missing standard.** When a single detector
   band yields ≥5 findings on one surface in its latest scan, the debt
   is one missing shared abstraction or convention — not N local bugs.
   Per-item fixes leave the generator in place; the queue entry must
   route to standardize-and-enforce instead (see Stage 3).

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Read:** `reports/_meta/effectiveness.jsonl`, `reports/<smell>/latest/*.md`
  (on-disk dirs use the smell name without the `find-` prefix —
  `reports/omnibus/`, not `reports/find-omnibus/`),
  host-provided cached `specs-audit.json`, `specs-size.json`,
  `decisions-audit.json`, and `effectiveness.jsonl`,
  `ai-docs/decisions/` (for `parked_until:` annotations).
- **Write:** `reports/triage-debt/scan-<TS>/queue.md` and its input
  provenance record.
- **MAY write (debug only):**
  `reports/triage-debt/scan-<TS>/raw-scores.json` (the score breakdown
  per entry) — write only when debugging the scoring heuristic; no
  downstream stage or skill reads it.

### Installed cache contract

This selected skill is an aggregator, not a copy of a host's spec or decision
registry. A copied install therefore consumes a host-owned cache directory
instead of invoking a repository checkout's audit or log scripts. Set
`TRIAGE_CACHE` to that directory; its default is
`reports/triage-debt/cache/current`. The cache may have been produced by the
host's own tools, but the installed skill does not require or import those
tools.

The exercised cache contains these plain-data files:

```text
effectiveness.jsonl   # skill, scan_id, target, findings_total, buckets, ts
specs-audit.json      # spec path, last_modified, coverage summary
specs-size.json       # hard-size overflow rows, or an empty list
decisions-audit.json  # drift rows, or an empty list
```

Missing cache files are a declared unavailable input, not permission to infer
that an axis is clean. Copy the files that exist into the scan directory and
write `inputs.md` naming both present and missing inputs. Do not silently
recreate a registry audit or effectiveness logger from a partial checkout.

## Pipeline

### Stage 0 — Setup

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/triage-debt/scan-${TS}"
mkdir -p "${REPORT_DIR}"
ln -sfn "scan-${TS}" reports/triage-debt/latest
TOP_N=5
while [ "$#" -gt 0 ]; do
    case "$1" in
        --top)
            shift
            if [ -z "${1:-}" ]; then
                echo "error: --top requires N" >&2
                exit 2
            fi
            TOP_N="$1"
            ;;
        --top=*)
            TOP_N="${1#--top=}"
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            exit 2
            ;;
    esac
    shift
done
case "${TOP_N}" in
    ''|*[!0-9]*)
        echo "error: --top must be a positive integer" >&2
        exit 2
        ;;
    0)
        echo "error: --top must be > 0" >&2
        exit 2
        ;;
esac
```

### Stage 1 — Collect inputs

Use the host's retained, read-only cache. This keeps the selected closure
self-contained and lets a maintenance window triage retained evidence without
re-running detectors:

```bash
TRIAGE_CACHE="${TRIAGE_CACHE:-reports/triage-debt/cache/current}"
{
    echo "# Triage input provenance"
    echo
    echo "Cache: ${TRIAGE_CACHE}"
    for input in effectiveness.jsonl specs-audit.json specs-size.json decisions-audit.json; do
        if [ -f "${TRIAGE_CACHE}/${input}" ]; then
            cp "${TRIAGE_CACHE}/${input}" "${REPORT_DIR}/${input}"
            echo "- present: ${TRIAGE_CACHE}/${input}"
        else
            echo "- missing: ${TRIAGE_CACHE}/${input}"
        fi
    done
} > "${REPORT_DIR}/inputs.md"
```

Then enumerate per-skill `latest` symlinks:

```bash
# On-disk report dirs use the smell name without the find- prefix
# (reports/omnibus/, reports/dormant/, …). Keep find-<name> in the echo
# so the originating skill stays visible in the audit trail.
for smell in dormant duplication semantic-duplication \
             omnibus implicit-state layer-violation \
             query-mutation doc-route-drift route-sprawl \
             frontend-contract-drift workflow-duplication; do
    if [ -L "reports/${smell}/latest" ]; then
        echo "find-${smell} → $(readlink reports/${smell}/latest)"
    fi
done
```

### Stage 2 — Score every candidate

A "candidate" is a `(skill, target)` pair. Build the candidate list by
walking the effectiveness log AND the latest find-* reports.

For each candidate, compute:

```text
score = recurrence_count * 100
      + p0_finding_count * 50
      + spec_drift_days * 30        # if a spec mentions this target
      + decision_drift_days * 20    # if a decision applies_to this target
      + hard_size_overflow * 200    # if specs.py size-check flags it
      + age_weeks                   # tiebreak — older = slightly heavier
      - parked_score                # explicit park reduces priority
```

**Definitions:**

- `recurrence_count` — number of distinct scan_ids in
  `effectiveness.jsonl` for this `(skill, target)` over the past 90
  days. ≥3 = persistent.
- `p0_finding_count` — count of `findings_total` from the most recent
  scan that landed in P0 buckets. The P0 bucket name varies per skill;
  use this map:

  | Skill | P0 bucket key |
  |---|---|
  | find-omnibus | `confirmed_omnibus` |
  | find-layer-violation | `extract_service` |
  | find-duplication | `merge_required` (or `cluster:P0-*` in triage.md) |
  | find-semantic-duplication | shape ≠ `keep_separate_document_why` |
  | find-implicit-state | `extract_enum_candidate` + `introduce_fk_candidate` |
  | find-query-mutation | `split_required` + `rename_required` |
  | find-dormant | `certain_delete` |
  | find-doc-route-drift | `broken_redirect` + `documented_only` |
  | find-route-sprawl | `cross_workflow_module` |
  | find-frontend-contract-drift | `contract_break` |
  | find-workflow-duplication | `authority_violation` |

  If a skill's report doesn't fit this map (older format), fall back to
  `findings_total` * 5 (lower weight, since uncategorized).

- `spec_drift_days` — for each spec where `coverage.summary.checkmark_lag
  > 0` OR `not_started > 0`, the days since the spec's `last_modified`
  in `specs-audit.json`. Cap at 60 (so a spec drifting 200 days doesn't
  swamp); below 60d, score 0 (drift is normal during active work).
- `decision_drift_days` — for each entry in `decisions-audit.json.drift`
  with kind `proposed_too_long`, the days past 30. For `broken_supersedes`
  / `applies_to_missing`, score a flat 30 days.
- `hard_size_overflow` — 1 if cached `specs-size.json` lists this target as
  `loc >= 1000`, else 0.
- `age_weeks` — weeks since the most recent `effectiveness.jsonl` entry
  for this candidate. Pure tiebreak.
- `parked_score` — read `ai-docs/decisions/*.md` for any ADR with a
  `parked_until: YYYY-MM-DD` field whose `applies_to:` overlaps the
  target AND the date is in the future. Score = 500 (effectively kicks
  it off the top-N).

Optionally write per-candidate breakdowns to
`${REPORT_DIR}/raw-scores.json` — only when debugging the scoring
heuristic; nothing downstream reads it.

### Stage 3 — Build the queue

Sort all candidates by `score` descending. Highlight the top-N. For
each entry, determine the recommended next skill:

| Source skill | Recommended next |
|---|---|
| find-omnibus | `/refactor-subsystem` (decomposition mode) |
| find-layer-violation | `/fix-workflow layer:<id>` |
| find-duplication | `/fix-workflow cluster:<id>` |
| find-semantic-duplication | `/unify-shadows` then `/fix-workflow semantic:<id>` |
| find-implicit-state (extract_enum) | `/extract-enum` |
| find-implicit-state (introduce_fk) | `/introduce-fk` |
| find-query-mutation | `/fix-workflow cluster:<symbol>` |
| find-dormant | `/fix-workflow delete:<id>` |
| find-doc-route-drift | `/prevent-regression topology:doc-route-drift` |
| find-route-sprawl | `/prevent-regression topology:route-ownership` |
| find-frontend-contract-drift | `/prevent-regression topology:frontend-boot` |
| find-workflow-duplication | `/extract-workflow-registry` then `/prevent-regression topology:workflow-registry` |
| spec drift | `/refactor-subsystem <spec-id>` Phase 2b (Crystallize) |
| decision drift (proposed too long) | `/decide --status accepted <slug>` OR `/decide --status deprecated <slug>` |
| decision drift (broken chain) | `/audit-decisions` to inspect, then manual fix |
| hard size overflow | `/find-omnibus <file>` then `/refactor-subsystem` |

**Mass-finding escalation (overrides the table).** Before emitting an
entry, check the candidate's latest scan buckets (in
`effectiveness.jsonl`): if any single bucket holds **≥5 findings on one
surface**, do NOT recommend per-item execution. The recommended next
becomes the standardize-and-enforce route:

1. `/decide` — name the standard or shared primitive the cluster
   implies (one ADR, not N tickets);
2. extract the primitive (the source skill's extract-* / refactor
   path);
3. `/prevent-regression` — pin the band so the cluster cannot regrow.

Annotate the entry `escalated: mass-finding (<bucket> × <count>)`.
The canonical failure this prevents: a lifecycle scanner returns the
same missing-guard band 19 times across one route surface, and triage
emits 19 tickets — when the right shape was one shared primitive plus
one guard.

### Stage 4 — Write `queue.md`

```markdown
# Triage queue — scan-<TS>

_Aggregated from <N> find-* reports, <M> specs, <K> decisions over the
past 90 days._

## Top <TOP_N> (recommended next actions)

### 1. <target> — score <S>
- **Source:** `<skill>` (last seen <date>, hit <recurrence_count> times)
- **Why ranked here:** _one-line reason — recurrence / hard-size /
  drift / etc._
- **Recommended next:** `/<skill> <args>`
- **Escalation:** _(when triggered)_ standardize-and-enforce — band `<bucket>` × <count>
- **Evidence:** `reports/<smell>/latest/<file>`

### 2. ...

## Full queue

| Rank | Target | Source skill | Score | Recurrence | P0 | Drift | Park |
|---|---|---|---|---|---|---|---|
| 1 | ... | ... | 350 | 3 | 5 | 60d | — |

## Park notes
- `<target>` parked by ADR `NNNN` until `<date>` — `<reason>`

## Stale find-* reports
_Reports older than 30 days where re-running the detector would refresh
the signal._
- `find-omnibus` last ran <date> on `<target>` — consider re-running.
```

### Stage 5 — Record provenance

The output's `inputs.md` is the run record for a copied install. Do not append
to a host effectiveness log unless that host explicitly offers its own logging
command and the user asked to use it. The queue must state the cache path and
every unavailable axis, so an old or partial cache cannot look like a clean
audit.

### Stage 6 — Summarize

Report to the user in ≤8 lines:

- Path to `queue.md`.
- Total candidates / top-N called out.
- 1-line for each top-3 with the recommended next command.
- Stale-report count (re-run signals).
- Name the Stage 1 cache path and any unavailable input axis from `inputs.md`.

## Non-goals

- Detecting new smells (each `/find-*` skill owns its detection).
- Editing production code.
- Mutating decision or spec status.
- Running `/refactor-subsystem` or `/fix-workflow` for the user — the
  recommendation is the deliverable; the user invokes the next skill.

## When things go sideways

| Symptom | Action |
|---|---|
| `effectiveness.jsonl` is empty | Note "no run history yet" in queue.md; rely on latest find-* reports only |
| No find-* `latest` symlinks exist | Note "no recent detection runs"; recommend running the SUSPECT skills first |
| Cached `specs-audit.json` is absent | Record it in `inputs.md`; do not score spec drift or claim it is clean. |
| Cached `decisions-audit.json` is absent | Record it in `inputs.md`; do not score decision drift or claim it is clean. |
| Every top-5 entry is the same target | Real signal — that target is the worst debt; recommend `/refactor-subsystem` if it's a file, `/decide` if it's a missing decision |
| Top score is < 50 | Note "no urgent debt — maintenance loop is healthy"; queue.md still useful as a snapshot |
| Candidate has no recommended-next mapping | Default to `/which-skill <target>` so the user can hand-pick |

## Replay case

For parser or scoring changes, replay the smallest executable boundary:

```bash
set -- --top 10
TOP_N=5
while [ "$#" -gt 0 ]; do
    case "$1" in
        --top)
            shift
            if [ -z "${1:-}" ]; then
                echo "error: --top requires N" >&2
                exit 2
            fi
            TOP_N="$1"
            ;;
        --top=*)
            TOP_N="${1#--top=}"
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            exit 2
            ;;
    esac
    shift
done
case "${TOP_N}" in
    ''|*[!0-9]*)
        echo "error: --top must be a positive integer" >&2
        exit 2
        ;;
    0)
        echo "error: --top must be > 0" >&2
        exit 2
        ;;
esac
printf '{"top_n": %s}\n' "${TOP_N}" | python3 -m json.tool
```

The replay passes only when `TOP_N` is `10`, the JSON parses, and the
transcript is pasted into the repair or closeout report.
