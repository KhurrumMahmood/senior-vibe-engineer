# Change spec — /scope-feature repair

Inputs: `reports/skill-frame-review/scope-feature.md` (F1–F4, F6; F5 is
a cross-skill design rule, no direct edit) + `scout.md` here (F1 TRUE
and understated; F2 PARTLY — ~148 not ~200 lines, substance holds; new
defects: Explore-write contradiction, unset `<TS>`, phantom
subsystems-dir ls, false stdlib-only claim, unconsumed Stage 5 audit).
Doctrine: declared verdict, artifact-truth gates,
load-bearing-or-delete, no invention, smallest responsible edits.

## Declared verdict

A fresh verifier re-runs the rubric finding-by-finding against the
repaired skill: every gate tests a property (not existence), the frame
is re-stated at the write site, conversation-rich invocations have a
phase-0, the dispatch contract is executable as written, and nothing
is invented. Write to that test.

## C1 — Stage 4.5 artifact-truth gate (F1)

New short stage between Stage 4 and Stage 5: generate three
hypothetical borderline changes (plausible adjacent work a future
agent might propose) and verify §1 adjudicates each in/out WITHOUT
asking the user; if any adjudication is ambiguous, tighten §1 and
re-test before advancing status. The three changes and their verdicts
are recorded in the plan directory or the reply (state where — pick
the lighter, consumed location: the Stage 6 summary).

## C2 — Frame re-activation at the write site (F2)

Inside the Stage 4 §1 template (at the In-scope bullets), embed the
gate question inline: each in-scope bullet must let a stranger
adjudicate a borderline change two months from now.

## C3 — Provisional tier flag at Q1 (F3)

At Q1: if the one-sentence problem already smells single-workflow
(Feature-tier) or one-line (Quick-tier), say so NOW as a provisional
flag; Q6 remains the binding check.

## C4 — Stage 0.5 conversation inventory (F4)

New Stage 0.5: inventory which of Q1–Q5 the conversation already
answers; present the inferred answers for confirmation (marked
inferred); ask only the genuinely open questions. Never re-interrogate
answers already given; never silently fill one.

## C5 — Un-fakeable priors acknowledgment (F6)

Stage 1's "read end-to-end" gains: reply with one line naming the 2–3
priors (decisions/patterns/smells) most binding on THIS scope —
un-fakeable without the read; doubles as frame activation.

## C6 — Executable dispatch contract (scout; F8 class)

The Stage 2 background exploration block: `subagent_type: "Explore"`
cannot write files in this harness, yet the prompt orders a file
write. Fix as in the refactor-subsystem round-2 precedent: dispatch
`general-purpose` (note that read-only agent types cannot satisfy a
file-output contract) — or, equally small, keep Explore and have
Stage 3 consume its returned final message instead of a file; pick
whichever is the smaller consistent edit given Stage 3's existing
file-read + fallback text, and align both sites.

## C7 — Artifact-reality drift (scout)

- Set `TS` in the Stage 0/2 bash so `scan-<TS>` is a real path
  (mirror how sibling skills set it).
- `ls .claude/docs/subsystems/`: mark host-adapter (dir is host-side
  and may be absent; absence is fine pre-/impact-feature) or fold into
  a step that consumes it — do not leave an unconsumed command.
- Fix the "stdlib-only" Python claim (scripts need PyYAML via
  `scripts/_lib`; use the venv interpreter wording the repo standard
  uses).
- Make Stage 5's `plans.py audit` consumed: paste its one-line result
  in the Stage 6 summary; on failure, fix before reporting. Note
  honestly (per scout) that audit checks registry-level links/status,
  not content — the content gate is C1.

## C8 — Addendum (implementer-flagged, applied by orchestrator)

Frontmatter `allowed-tools` lacked `Agent` despite the Stage 2
dispatch — same artifact-drift class as C7. One-token fix: add
`Agent` to the list.

## Constraints

Smallest edits; no stage renumbering beyond the two new x.5 stages;
preserve voice; nothing invented; internal-consistency sweep after
edits.
