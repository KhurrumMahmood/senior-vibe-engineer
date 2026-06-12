# Change spec — /refactor-subsystem repair

Inputs: `reports/skill-frame-review/refactor-subsystem.md` (findings
F1–F9; the defect spec) and `.claude/tasks/refactor-subsystem-repair/
scout.md` (anchors, pointer audit, archaeology fragments). Implementer
applies C1–C9 below. Doctrine applied: declared-verdict (gates
announced up front), artifact-truth gates, load-bearing-or-delete,
no invented content (where source fragments are insufficient, write an
explicit host-adapter slot, never plausible filler).

## How this repair will be judged (declared verdict)

A fresh, non-context-sharing verifier will re-run the frame-review
rubric (reports/skill-frame-review/scope-feature.md) against the
repaired skill and check, finding by finding, that F1–F9 are resolved
WITHOUT new defects of the same classes: every knowledge pointer must
resolve to real content (grep-checkable); every mandated artifact must
name its consumer; all counts must match the files; no content may be
invented beyond the collected fragments. Write to that test.

## C1 — Missing operations content (F1 + F8)

Create `knowledge/operations.md` assembled ONLY from collected
fragments (scout §4 + SKILL.md inline summaries + execution-playbook
partials), containing: worktree + venv rules; cleanliness-guard
commands (generalize the hardcoded `~/Projects/your-project` to the
"run from repo root" form used elsewhere in the skill); the git
archaeology recipe — triggers/thresholds (≤500 LOC & ≤20 commits →
scout inline; else orchestrator-parallel; ≥50 commits mandatory, ≥3
LR-T candidates), the FULL subject-word regex (un-elide the
`fix|retry|timeout|crash|...` — take the complete list from wherever
the fragments supply it; if no complete list exists in any fragment,
state the known terms and mark the regex `<!-- host-adapter: extend
subject-word list -->`), the `<!-- archaeology: <hash> -->` tag
convention, archaeology_owner rules; the archaeology report schema
(from inventory-scout.md's output contract); report directory layout
(`reports/refactor/<spec-id>/...` — enumerate what each phase writes,
derivable from scout §3); the test matrix IF fragments supply one,
else a host-adapter slot.
Then: rewrite every bare-`knowledge/` pointer in SKILL.md and agents/
to the correct named file (scout §2 has the full list); fix line-34
count to five files; fix "R1–R36" → "R1–R44"; fix learnings.md's own
title (R1-R43 → R1-R44); update the Repository layout block to the
five real files.

## C2 — Decomposition behavior gate (F2)

Generalize R36 to batch level: (a) Phase 3 plan item 7 (per-batch test
strategy) must include grep evidence that at least one named suite
imports or patches each batch's destination modules — the plan shows
the grep output, the Phase 4 reviewer approves coverage, not suite
names; (b) Phase 5.2 per-batch checklist re-verifies it before running
the suite; (c) the decomposition-mode characterization paragraph
(L-44 context) gains the sentence: structure pinning is sufficient
ONLY with the per-batch coverage-path proof; "never trust green from a
suite with no path into the moved code" (cite R36).

## C3 — Ownership-boundary scan made load-bearing (F3)

Phase 6.0 must write `reports/refactor/<spec-id>/phase-6-boundary.md`
(scan commands run, hits, classification). Gate: known findings inside
the named ownership family BLOCK Phase 7 unless explicitly waived in
the Phase 4 sign-off block (reuse the existing waiver mechanism).
Phase 7's entry conditions name this artifact.

## C4 — Follow-up intake (F4)

Phase 7.2/7.3: every 6.3/6.3.5 FAIL or ADVISORY verdict becomes a
ledger entry or a named open item in the learnings entry — copy 7.4's
residual-items pattern verbatim. One or two sentences; no new
machinery.

## C5 — Threshold contradiction (F5)

execution-playbook §5.4 pseudo-code: branch on `count >= 5` →
swarm; `else` → sequential inline fixes, matching the decision table.

## C6 — Phantom flag (F6)

Remove the `--enforce-inline` escape hatch sentence; replace with: a
repo-wide inline-enforcement decision is a Phase 4 sign-off scope item
(the §5.4 mechanism), never an executor-claimed flag.

## C7 — Resume protocol (F7)

New short section "Resuming mid-refactor" placed right after Scope:
on entering with a fresh context mid-run — (1) `python3
scripts/specs.py coverage <id>` + `ls reports/refactor/<id>/` to infer
the current phase; (2) re-read that phase's knowledge file (Phase 5 →
execution-playbook.md IN FULL); (3) restate the approved scope and
waivers from phase-3-plan.md §Sign-off before any edit; (4) re-arm
beliefs 3/4 (unknown code STAYS; deletion needs recorded human
approval); (5) re-run the cleanliness guard. Cross-reference it from
the Phase 5 opening line.

## C8 — Host-adapter slots (F9)

Phase 6.1 baseline suite names and §1.2 conditional doc list: mark as
host-adapter slots (`<!-- host-adapter: ... -->` with the origin
project's values kept as the worked example), so substitution is an
explicit configured choice, not a silent one.

## C9 — Declared-verdict preamble

Near the top of SKILL.md (after the deliverable statement), add a
compact "How success is judged" block — the gates the executor will
face, stated as the optimization target: characterization suite green
at HEAD, per batch, and at 6.1; per-batch coverage-path proof (C2);
boundary artifact clean or waived (C3); sign-off scope honored
token-for-token; knowledge pointers resolve (no improvised recipes —
if a pointer dangles, STOP and flag, do not improvise). Keep it ≤12
lines; it is a frame device, not a new section.

## C10 — Scout-found artifact drift (new, same classes as F1/F6)

All four are align-doc-with-executable-reality fixes — inspect the
actual script/file contract and repoint or mandate production; never
paper over:
- SKILL.md:475 dispatch loop reads `inventory/chunks.jsonl` which no
  step produces. Inspect `scripts/chunk_file.py`'s real output
  contract; either repoint the loop at the artifact that exists or add
  an explicit orchestrator step at chunking time that writes
  `chunks.jsonl` from the chunk map (whichever matches reality with
  the smallest edit).
- SKILL.md:1022–1023 L3 scout reads `phase-6-solid.json` which no
  command writes. Inspect what `scripts/specs.py solid` actually
  emits and align (repoint, or mandate the orchestrator write the
  file from the gate output).
- SKILL.md:485–486 promises a "swarm-specific wrapper" in
  execution-playbook.md that contains none. Repoint to the playbook's
  real swarm section and reword to what actually exists there.
- execution-playbook.md:333 `--next-review <+180d>` → the real flag
  `--next-review-days <int>` (verified against scripts/ledger.py).

## Constraints

- Smallest responsible edits; do not restructure phases or renumber.
- Preserve the skill's existing voice and formatting conventions.
- NOTHING invented: operations.md content traces to fragments; gaps
  become explicit host-adapter slots.
- Internal consistency sweep after edits: counts, file lists,
  cross-references (the F8 class) must agree everywhere, including
  agents/ templates and learnings.md L-index resolutions.
