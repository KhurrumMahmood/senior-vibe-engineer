# Implementation report — /scope-feature repair

Date: 2026-06-12. Target: `.claude/skills/scope-feature/SKILL.md`
(272 → 311 lines). `knowledge/` untouched — no cross-reference needed
alignment. Not committed.

## C1 — Stage 4.5 artifact-truth gate (F1)

- **Anchor:** inserted immediately before `### Stage 5 — Advance
  status` (per scout §2/F1).
- **Before → after:** no content gate existed between writing §1-2 and
  advancing status → new `### Stage 4.5 — Artifact-truth gate`:
  generate three hypothetical borderline changes (plausible adjacent
  work a future agent might propose), adjudicate each in/out strictly
  from the §1 text WITHOUT asking the user; ambiguous adjudication ⇒
  tighten §1 and re-test before advancing.
- **Judgment call:** verdict location — spec offered plan directory or
  reply and named the lighter consumed location (Stage 6 summary); the
  stage states "reported in the Stage 6 summary" and Stage 6 gained a
  matching bullet, so the gate is consumed on day one (scout §5 note).

## C2 — Frame re-activation at the write site (F2)

- **Anchor:** the `**In scope.**` block inside the Stage 4 markdown
  template (scout anchor (b)).
- **Before → after:** bare structural placeholders → an inline gate
  comment under `**In scope.**`: `<!-- gate: each bullet must let a
  stranger adjudicate a borderline change in/out two months from
  now -->`.
- **Judgment call:** chose the scout's comment-in-template form over
  appending to the lead-in sentence — it sits exactly at the write
  site (the In-scope bullets), per the spec's "at the In-scope
  bullets".

## C3 — Provisional tier flag at Q1 (F3)

- **Anchor:** Q1, "…the work is too vague — push back."
- **Before → after:** appended one sentence: if the one-sentence
  problem already smells single-workflow (Feature-tier) or one-line
  (Quick-tier), say so NOW as a provisional flag; Q6 remains the
  binding check. Q6 not moved.

## C4 — Stage 0.5 conversation inventory (F4)

- **Anchor:** inserted immediately before `### Stage 1 — Read priors`
  (scout §2/F4).
- **Before → after:** no phase-0 → new `### Stage 0.5 — Inventory
  conversation-supplied answers`: scan the invoking conversation for
  material answering Q1-Q5, present inferred answers for confirmation
  (marked inferred), ask only genuinely open questions; never
  re-interrogate, never silently fill.
- **Cross-reference:** Stage 2 opening now reads "…in order, skipping
  any confirmed in Stage 0.5" (the scout-flagged cross-reference);
  the "do not invent answers" line kept verbatim.

## C5 — Un-fakeable priors acknowledgment (F6)

- **Anchor:** Stage 1 "Read … end-to-end. These are the law-as-stated;
  scope must respect them."
- **Before → after:** appended: after the read, reply with one line
  naming the 2-3 priors (decision ids / pattern anchors / smell names)
  most binding on THIS scope — un-fakeable without the read, doubles
  as frame activation; consumed by Stage 3's checklist and the §1
  Prior constraints rows (load-bearing per the F5 rule).

## C6 — Executable dispatch contract (decision recorded)

- **Choice: option (a) — switch dispatch to `general-purpose`**, not
  option (b) (keep Explore, consume returned message). Why: (1) it is
  the smaller consistent edit — Stage 3's existing file-read +
  graceful-absence fallback stays intact verbatim, whereas (b) would
  rewrite Stage 3's whole consumption model around a background-
  completion message; (2) (b) would orphan the
  `scan-<TS>/exploration.md` path that C7 explicitly orders pinned
  via `TS=`; (3) matches the refactor-subsystem round-2 precedent
  ("a read-only agent type such as `Explore` cannot satisfy the
  three-file output contract" → general-purpose).
- **Site 1 (Stage 2):** prose "fire an `Explore` sub-agent" → "fire a
  `general-purpose` sub-agent … (a read-only agent type such as
  `Explore` cannot satisfy the file-output contract)";
  `subagent_type: "Explore"` → `"general-purpose"`; prompt path now
  `scan-${TS}` and gained "(write nothing else)" — the minimal form of
  the precedent's Write-restricted-to-output-path discipline.
- **Site 2 (Stage 3):** "the background `Explore` from Stage 2" → "the
  background exploration sub-agent from Stage 2"; "(Explore still
  running…)" → "(sub-agent still running…)"; checklist bullet "Did the
  background **Explore** surface…" → "**exploration**". Read path now
  `scan-${TS}`, matching the dispatch exactly.

## C7 — Artifact-reality drift

- **TS:** Stage 0 bash gained `TS=$(date +%Y%m%d-%H%M%S)` after
  `PLAN_PATH=` — exact mirror of impact-feature Stage 0 (its line 75).
  Both `scan-` references now use `${TS}`.
- **subsystems ls:** `ls .claude/docs/subsystems/` →
  `ls .claude/docs/subsystems/ 2>/dev/null || echo "no subsystem
  docs"`, plus a note: host-side, may be absent, absence fine before
  `/impact-feature`; when present, file names seed concrete subsystem
  names in Q2. This does both spec options (absence-marked AND
  consumed) at one-sentence cost, resolving the scout §5 ceremony
  verdict.
- **stdlib-only claim:** Scope bullet `**Python:** \`python3\`
  (stdlib-only).` → `**Python:** \`.venv/bin/python\` explicitly — the
  plan/decision scripts need PyYAML via \`scripts/_lib\`, so they are
  not stdlib-only.` (CLAUDE.md-standard wording.)
  - **Judgment call:** also swapped the three `python3 scripts/…`
    invocations (Stage 0 init, Stage 1 audit/list ×2, Stage 5 audit) to
    `.venv/bin/python` — leaving them at `python3` would contradict the
    corrected Scope line, and the sweep mandate forbids leftover
    contradictions. Mechanical, no wording change beyond the
    interpreter. (Siblings impact-feature/architecture-fit carry the
    same stdlib-only defect — out of scope here, not touched.)
- **Audit consumed:** Stage 5 "Confirm the plan loads cleanly." →
  "Paste audit's one-line result into the Stage 6 summary; on failure,
  fix before reporting. Note: audit checks registry-level
  links/status, not §1-2 content — the content gate is Stage 4.5."
  Stage 6 gained the matching "Audit result (Stage 5), one line"
  bullet.

## Stage 6 consumers

Two bullets added between "Active decisions…" and "Recommended next
command": borderline gate (the three Stage 4.5 changes + in/out
verdicts, one line) and the Stage 5 audit result. The "≤8 lines"
budget still holds (7 one-line bullets).

## Consistency sweep

- Stage 3 reads exactly what Stage 2 dispatches
  (`reports/scope-feature/scan-${TS}/exploration.md`); `TS` defined in
  Stage 0. grep "Explore": only remaining hit is the deliberate
  cannot-write explanatory note in Stage 2.
- Stage 6 consumes Stage 4.5's verdicts and Stage 5's audit line; both
  producer stages name Stage 6 as the destination.
- Stage 2 opening references Stage 0.5; Stage 5 note references
  Stage 4.5. No stage renumbering; no `python3` / `<TS>` /
  `stdlib-only` residue (grep-verified).
- Preserved per scout §6: priors-before-conversation, earliest-moment
  background survey + don't-wait + fallback, Core beliefs preamble,
  sideways table — all untouched.

## Residual (noted, not edited — outside spec)

Frontmatter `allowed-tools: Bash, Read, Grep, Glob, Write, Edit` does
not list `Agent`, yet Stage 2 dispatches one. Same unexecutable-
dispatch class as C6 but flagged by neither the review nor the scout;
per the no-invention constraint it is recorded here for a follow-up
adjudication rather than fixed.
