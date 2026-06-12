# Class 2 + small edits — five-skill batch

Date: 2026-06-12. Source spec: `.claude/tasks/skill-repairs/class-sweeps-spec.md`
(Class 2 confirmed hits, Class 3 borderline, Class 1 hit-table rows, diagnose
class-lift rollout). Skills touched (exclusive ownership): audit-decisions,
triage-debt, find-standard-gaps, propose-boundary, diagnose. Paths are
repo-relative. Verification: `.venv/bin/python scripts/skill_meta.py lint` →
`OK — 74 skills, 74 declaring new contract` (exit 0).

---

## A. Class-2 ceremony-stage fixes

### A1. audit-decisions — `raw-drift.json` false consumer claim

`.claude/skills/audit-decisions/SKILL.md` Stage 5 (now ~:239).

Before:

> For every drift row, capture the full evidence in a JSON sibling file
> so the heuristic is debuggable and downstream skills (e.g.,
> `/triage-debt`) can consume the structured form:

After:

> For every drift row, capture the full evidence in a JSON sibling file
> so the heuristic is debuggable. This is a debug artifact with no
> downstream consumer yet — `/triage-debt` reads `decisions-audit.json`
> from `scripts/decisions.py audit --json` directly, not this file:

Secondary mention made consistent — Scope "Write" line (~:85):

Before:

> `reports/audit-decisions/scan-<TS>/raw-drift.json` (per-row evidence).

After:

> `reports/audit-decisions/scan-<TS>/raw-drift.json` (per-row evidence;
> debug artifact, no downstream consumer yet).

Consistency grep (`grep -n "raw-drift" .claude/skills/audit-decisions/SKILL.md`):
only the two rewritten sites remain (:85 area, :239 area). Remaining
`/triage-debt` mentions in the file (:28 delegate_from, :223 drift.md template
note) describe triage-debt's decision-drift signal, which truly comes from
`decisions-audit.json` — no false raw-drift consumer claim survives. Repo-wide
grep over `.claude/skills/ scripts/ docs/ .claude/docs/` finds no other
`raw-drift` reference.

### A2. triage-debt — `raw-scores.json` demoted to optional debug output

`.claude/skills/triage-debt/SKILL.md`, two sites kept consistent.

Output contract (~:92, was :81). Before:

> - **Write:** `reports/triage-debt/scan-<TS>/queue.md`,
>   `reports/triage-debt/scan-<TS>/raw-scores.json` (the score breakdown
>   per entry, for debugging the heuristic).

After:

> - **Write:** `reports/triage-debt/scan-<TS>/queue.md`.
> - **MAY write (debug only):**
>   `reports/triage-debt/scan-<TS>/raw-scores.json` (the score breakdown
>   per entry) — write only when debugging the scoring heuristic; no
>   downstream stage or skill reads it.

Stage 2 (~:197, was :184). Before:

> Write per-candidate breakdowns to `${REPORT_DIR}/raw-scores.json` so
> the heuristic is debuggable.

After:

> Optionally write per-candidate breakdowns to
> `${REPORT_DIR}/raw-scores.json` — only when debugging the scoring
> heuristic; nothing downstream reads it.

Consistency grep: `raw-scores` appears only at the two rewritten sites; both
now say optional/debug-only. No other repo reference exists.

### A3. find-standard-gaps — `coverage.json` reserved-not-consumed

`.claude/skills/find-standard-gaps/SKILL.md` Stage 1 (~:112, was :101).

Before:

> `scan_coverage.py` runs each standard's detector against the tree and
> writes `coverage.md` (human report) and `coverage.json` (machine). It

After:

> `scan_coverage.py` runs each standard's detector against the tree and
> writes `coverage.md` (human report) and `coverage.json` (machine —
> reserved for query_planner v1.0, not yet consumed; Stage 2 reads only
> `coverage.md`). It

Consistency grep: this is the SKILL.md's only `coverage.json` mention. The
skill-local `scripts/query_planner.py:24` already frames it as a future v1.0
consumer — now consistent with the stage text.

---

## B. Class-3 borderline wording fix

### B4. propose-boundary — Stage 2 dispatch mechanism named

`.claude/skills/propose-boundary/SKILL.md` Stage 2 (~:174, was :163).

Before:

> Stage 2 — **scout callers (optional).** For each `proposed_public_api`
> symbol in the top candidate seam, the orchestrator dispatches a cheap
> read-only scout (Bash + grep) to confirm the call sites in
> `callers_into_private_helpers`. ...

After:

> Stage 2 — **scout callers (optional).** For each `proposed_public_api`
> symbol in the top candidate seam, the orchestrator dispatches a cheap
> read-only scout via `.claude/skills/_common/dispatch_scout_cheap.sh`
> (Bash + grep — no Agent tool; the allowed-tools list stays
> read-only-tight) to confirm the call sites in
> `callers_into_private_helpers`. ...

Agent was NOT added to `allowed-tools` (spec's read-only-tight option).
`dispatch_scout_cheap.sh` verified present at
`.claude/skills/_common/dispatch_scout_cheap.sh`; same mechanism
`/which-cleanup` already mandates (its SKILL.md:119). Consistency grep:
Stage 2 is the file's only scout-dispatch site; no other sub-agent/fan-out
mandate exists in the body.

---

## C. Class-1 declared-verdict blocks

All five inserted after the intro, before `## Core beliefs` (diagnose: before
`## Phase 0 - Frame`, its first section), as `## How success is judged`,
matching the repair-skill exemplar (`.claude/skills/repair-skill/SKILL.md:45`).
Artifacts named were grep-verified against each body before writing.

### C1. audit-decisions (:46)

> - `drift.md` carries one row per drift symptom, each with a severity
>   and a concrete resolution command the user can run next.
> - The summary table accounts for every symptom class
>   (broken-supersession, code-ref-orphan, applies-to-missing,
>   proposed-too-long, unreferenced-decision) — none silently dropped.
> - The registry, ADRs, and production code are untouched — the run
>   writes only under `reports/audit-decisions/scan-<TS>/`.

### C2. triage-debt (:46)

> - `queue.md` is ranked by the Stage 2 score, and every top-N entry
>   carries a one-line "why ranked here" rationale plus a concrete
>   recommended-next skill invocation.
> - The inputs that fed the ranking are declared — which find-* `latest`
>   reports, `specs-audit.json`, `decisions-audit.json`, and
>   `effectiveness.jsonl` were read, and which were missing.
> - No new detection ran; no production code, spec, or decision status
>   was touched — the run writes only under `reports/triage-debt/scan-<TS>/`.

### C3. find-standard-gaps (:47)

> - `coverage.md` enumerates every standard's coverage cells —
>   situation-site count, gap count, coverage % — with no standard
>   silently dropped (`manual`/`skill` standards reported as skipped).
> - Each standard carries an explicit analyzability verdict:
>   `language_unsupported` is surfaced as "could not analyze", never
>   passed off as 0 gaps / compliant.
> - Clean standards (0 gaps) are named as positive results.
> - No production edits — the run writes only under
>   `reports/standard-gaps/scan-<TS>/`.

### C4. propose-boundary (:47)

> - `proposal.md` is complete per the template: candidate seams with raw
>   scores, proposed public API table, backward-compat shim shape,
>   caller-impact summary, and characterization-test matrix.
> - When `inspection.json` carries `defer_signals`, the proposal front
>   matter records `recommendation: defer_<reason>` — never a forced
>   refactor recommendation.
> - Zero production edits — the run writes only under
>   `reports/propose-boundary/<target-slug>/`; the hand-off to
>   `/refactor-subsystem` is named, not executed.

### C5. diagnose (:47) — surfaces existing `evidence_required` frontmatter

> - A trusted reproduction loop is demonstrated before any fix - or
>   `reproduction.md` records why none was possible and the run stops.
> - The four `evidence_required` artifacts exist with pasted transcripts:
>   `reproduction.md` (reproduction_or_reason), `root-cause.md`
>   (root_cause, with the confirming probe's exact command and output),
>   `verification.md` (fix_verification, the passing rerun),
>   `cleanup-check.md` (cleanup_check, the `[DIAG-...]` grep).
> - `scripts/evidence_gate.py check` exits 0; its summary line is pasted
>   in the final reply.

---

## D. Class-lift rollout to diagnose

The spec said "Phase 7 (closeout)" — diagnose has no Phase 7; its phases run
0-6 and the closeout is **Phase 6 - Verify And Learn**. The bullet was added
there, immediately after "answer: what would have prevented this?", adapted to
diagnose's voice (plain hyphens, bug-class-across-codebase as the lifted unit,
hit counts land in `root-cause.md`, diagnose's existing evidence artifact).

Added (Phase 6, ~:184):

> - run the class-lift gate: name the bug's class in one sentence, define
>   the cheapest detector for it (usually a grep), and RUN it across the
>   codebase; paste the hit counts in `root-cause.md`. Sibling sites
>   found: batch them into one sweep, not N future bug reports. A
>   mechanizable class routes to `/prevent-regression`. A bug fixed only
>   where it was reported is a recurring tax.

---

## Verification summary

- `.venv/bin/python scripts/skill_meta.py lint` → `OK — 74 skills, 74
  declaring new contract`, exit 0 (run after all edits).
- All five files carry exactly one `## How success is judged` block at the
  declared positions (grep-verified).
- Repo-wide greps confirm no surviving false-consumer text: `raw-drift` and
  `raw-scores` exist only at the rewritten sites; `coverage.json` only at the
  annotated site in the SKILL.md plus the already-correct future-consumer
  comment in `scripts/query_planner.py`.
- Nothing committed. Only the five owned SKILL.md files plus this report were
  written; other dirty files in `git status` belong to parallel agents.
