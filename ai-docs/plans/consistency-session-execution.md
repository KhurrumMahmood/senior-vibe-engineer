---
name: consistency-session-execution
title: "Consistency-session execution assurance: every commitment lands, gets watched, or gets parked"
status: scoped
date: 2026-06-12
authors: [khurrum, claude-code]
motivating_decision: null
successor_spec: null
subsystems: [skills, scripts, docs, ledger, plans]
workflows: []
---

# Consistency-session execution assurance

Coordination plan, not a feature plan. The 2026-06-12 "Consistency"
session produced 22 ledger intakes, one scoped feature plan, landed
rules, and a pyramid synthesis. This plan exists so that none of it
silently evaporates — the session's own diagnosis was that the
ecosystem wins the *remembering* battle and loses the *acting* one
(`skill-catalog-reorganization` idled in the ledger while its finding
waited to be rediscovered by a 4-minute pyramid). This file is the
counter-mechanism: one watched artifact enumerating every commitment,
its route, and its done-criterion. `/find-orphaned-ideas --stale-plans`
is the enforcement teeth — if this plan goes silent, it gets flagged.

That enforcement claim was initially FALSE: the detector fired only on
a status the plan tooling can't produce, skipped untracked files, and
exempted any ledgered slug — three kill switches the adversarial
review (`reports/adversarial-review/consistency-execution/findings.md`)
verified in source. Fixed 2026-06-12: detector widened to all
non-terminal statuses, filesystem-mtime fallback for untracked plans,
exemption narrowed to in-flight ledger ideas only, regression tests at
`tests/test_find_orphaned_ideas.py`. The interim watcher is
deliberately INDEPENDENT of Track A; when Track A's projection lands,
takeover happens via an explicit handover event recorded against this
plan, not by assumption. Of the 22 intakes, 13 carry no quality marker
and are visible only to manual ledger review until the projection
lands — accepted, dated risk, not an oversight.

## 1. Scope & Bounds

**Problem.** A long strategy session produced more decisions and ideas
than any single follow-up task will carry; without an enumerated,
machine-watched commitment list, an even-odds outcome is a plan that
never fully executes and a project that never reaches coherent form.

**Commitment inventory (the scope).**

- **W-A — Track A: status projection & presentation.** In motion.
  Plan `status-projection-and-presentation` (scoped); next
  `/impact-feature`, then `/architecture-fit` (placement fork →
  `/decide`), `/plan-spec`, execution. *Done when:* spec promoted,
  landed, all six §2 success criteria green.
- **W-B — Routing + harvest rules.** DONE (commit c2e5680): CLAUDE.md
  route-before-working + sweep-before-ending, Augment mirrors, README
  pointer.
- **W-C — Pyramid follow-ups into the reorganization track.** Fold the
  seven-subsystem emergent grouping, `drift-scan-framework`,
  immune-system tier naming, memory-map decision table,
  `execution-funnel.md` doctrine, and convention-quad codification into
  the `shareable-core-reorganization` plan (amend its W1/W5 or add a
  W7) the next time that plan is touched — with the recorded cautions
  (ADR 0023 dispatcher boundary is deliberate; `orient` is not an
  orphan). *Done when:* shareable-core plan §1 names them, or each is
  parked with a reason in the ledger.
- **W-D — Standing skill candidates from this session.**
  `summary-pyramid-skill` and `port-meta-audit` each reach a
  `/plan-skill` intake (or explicit park). The kit-gap analysis
  (reports/meta-audit-kit-gaps.md) feeds the port. *Done when:* both
  slugs leave `proposed` state.
- **W-E — Goal layer.** No skill owns "what is this project trying to
  become, and are we converging?" — `converge` is per-phase, `orient`
  is lifecycle state, `project-interview` is intent capture; nothing is
  the standing goal artifact with a drift check. Route: `goal-skill`
  ledger intake; cheapest first embodiment is a `goals` section in
  Track A's `status.json` reading a small goal artifact, so the
  dashboard renders "stated goal vs. current trajectory."
  *Done when:* goal artifact shape decided (possibly inside Track A's
  schema ADR) or explicitly parked.
- **W-F — Track B research brief (content/comic project).** Operator
  cards retrofitted onto the ~8 proven operators; the state-journal
  reader experiment specified against the pairwise instrument; lens
  battery (cached-sequential triage vs independent-parallel verdict)
  written up. Lives in the comic/content project, but closure is bound
  LOCALLY: *done when* a ledger event on `operator-composition-ledger`
  in THIS repo links the brief's path and first-experiment result —
  cross-repo memory is not a mechanism.
- **W-G — The assurance loop itself.** Operator direction (2026-06-12):
  **execution-first** — the cadence for THIS project is "the pending
  work gets done, then dogfooded on a meaningful target," not new
  watcher machinery. Mechanism: Track A's session-start hook (already
  in W-A scope for queue items) is extended to also surface
  non-terminal plans silent >14 days — one mechanism, built once,
  inside the work already scheduled. Until it lands: manual biweekly
  sweep (`/find-orphaned-ideas --stale-plans`, now regression-tested
  to actually fire). *Done when:* the hook exists and its path is
  recorded here, via an explicit handover event on this plan.

**Out of scope.** Executing W-C/W-E/W-F work themselves (each has its
own vehicle); any new feature work not enumerated above.

**Non-goals.** Not a second backlog — every W-item points at the ledger
slug or plan that owns it; this file only assures routing + closure.

## 2. Success Criteria

- By 2026-07-12, every W-item is `done`, in-flight with a **qualifying**
  ledger event dated within 14 days, or parked — zero silent items.
  A qualifying event is a state transition or carries an artifact link
  (commit sha, report path, spec path); free-text notes do not qualify.
  A park record must name a revisit trigger or date. If more than half
  of W-C..W-F close by park, this plan cannot close successfully — it
  becomes `abandoned` with a successor named.
- `/find-orphaned-ideas --stale-plans` run on/after 2026-07-12 reports
  no stale finding attributable to this session's slugs or plans —
  meaningful now that the detector demonstrably fires on `scoped`
  plans (regression-tested).
- Track A reaches `promoted` (spec exists) — the leading indicator
  that the session converted to execution, not just capture.
- **Outcome criterion (not gameable by activity):** the W-E goal
  artifact exists, and the 2026-07-12 review states in one written
  paragraph whether the project is converging toward it — measured
  against the goal, not against event counts.
- Every confirmed adversarial finding is fixed in this file or carries
  its own one-line accepted-risk statement (blanket acceptance
  disallowed). Disposition log lives at the end of
  `reports/adversarial-review/consistency-execution/findings.md`.

## 3.–7.

Not applicable — coordination plan; never advances past `scoped`.
Closed via `abandoned` with a successor/outcome note when §2 holds or
fails (the plan tooling has no `complete` status — extending
`VALID_STATUSES` for coordination plans is a `/decide` candidate, not
something this plan asserts into existence).
