# Verification — /scope-feature repair

Date: 2026-06-12. Independent verifier, no shared context with the
implementer. Inputs: repaired `.claude/skills/scope-feature/SKILL.md`
(uncommitted, +65/−25), `change-spec.md` (C1–C8),
`reports/skill-frame-review/scope-feature.md` (F1–F4, F6), pre-repair
copy at `/tmp/skill-repairs-old/scope-feature/SKILL.md`, scout.md
(read after independent diff review).

## 1. Verdict table (C1–C8)

| Item | Maps to | Verdict | Resolving text (line) |
|---|---|---|---|
| C1 | F1 — artifact-truth gate | **RESOLVED** | L255–262 `### Stage 4.5 — Artifact-truth gate … adjudicate each in/out strictly from the §1 text written in Stage 4, WITHOUT asking the user. If any adjudication is ambiguous, tighten §1 and re-test before advancing status. The three changes and their verdicts are reported in the Stage 6 summary.` Sits before Stage 5 (status bump) — correct ordering. |
| C2 | F2 — frame at write site | **RESOLVED** | L232–233, inside the Stage 4 template at the In-scope bullets: `<!-- gate: each bullet must let a stranger adjudicate a borderline change in/out two months from now -->`. "Two months" traces to pre-existing belief 1 (L51–52). |
| C3 | F3 — provisional tier flag | **RESOLVED** | L141–144 (Q1): `If the one-sentence problem already smells single-workflow (Feature-tier) or one-line (Quick-tier), say so NOW as a provisional flag; Q6 remains the binding check.` Q6 unmoved (L186–189). |
| C4 | F4 — conversation inventory | **RESOLVED** | L97–103 `### Stage 0.5 — Inventory conversation-supplied answers … Present the inferred answers to the user for confirmation, each marked as inferred; ask only the genuinely open questions in Stage 2. Never re-interrogate an answer already given; never silently fill one.` Stage 2 opener cross-wired: `skipping any confirmed in Stage 0.5` (L129–130). |
| C5 | F6 — priors acknowledgment | **RESOLVED** | L121–125: `After the read, reply with one line naming the 2-3 priors (decision ids / pattern anchors / smell names) most binding on THIS scope — un-fakeable without the read … Stage 3's checklist and the §1 Prior constraints rows consume it.` Load-bearing per the F5 rule. |
| C6 | dispatch contract (F8 class) | **RESOLVED** | L150–153: `fire a `general-purpose` sub-agent … (a read-only agent type such as `Explore` cannot satisfy the file-output contract)`; L161 `subagent_type: "general-purpose"`; write path L167–168 `scan-${TS}/exploration.md`; Stage 3 reads the identical path (L196). `general-purpose` has Tools: * incl. Write — executable as written. Implementer chose the keep-file-contract option; both sites aligned, Stage 3 fallback (L198–201) retained. |
| C7 | artifact-reality drift | **RESOLVED** (all four sub-items) | (a) L84 `TS=$(date +%Y%m%d-%H%M%S)` in Stage 0 — byte-identical to 10+ sibling skills (e.g. find-dormant L67). (b) L112 `ls .claude/docs/subsystems/ 2>/dev/null \|\| echo "no subsystem docs"` + L114–117 host-side/absence note AND a consumer (`use the file names to seed concrete subsystem names in Q2`) — no longer unconsumed. (c) L70–71 `.venv/bin/python explicitly — the plan/decision scripts need PyYAML via scripts/_lib, so they are not stdlib-only`; all three bash invocations converted (L90, 110–111, 270). (d) L273–275 `Paste audit's one-line result into the Stage 6 summary; on failure, fix before reporting. Note: audit checks registry-level links/status, not §1-2 content — the content gate is Stage 4.5.` Honest scope note per scout. |
| C8 | allowed-tools | **RESOLVED** | L5 `allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent`. YAML parses (checked). |

Per-finding rollup: F1 ✓, F2 ✓, F3 ✓, F4 ✓, F6 ✓. F5 correctly has no
direct edit; its rule is honored — both new gates (4.5, audit paste)
are consumed by Stage 6 bullets (L284–287), so neither is day-one
ceremony.

## 2. Artifact-truth assessment

- **Stage 4.5 tests the property, not existence.** It generates
  borderline changes and adjudicates them "strictly from the §1 text"
  — this exercises belief 1's contract (stranger-adjudicable scope),
  which `plans.py audit` cannot. Failure mode has a repair path
  (tighten §1, re-test) gating the status advance.
- **Outputs consumed:** Stage 6 mandates `Borderline gate (Stage 4.5):
  the three changes and their in/out verdicts, one line` and `Audit
  result (Stage 5), one line` (L284–287). 7 bullets still fit the
  ≤8-line reply contract.
- **Priors line:** materially harder to fake (specific decision ids /
  anchors are spot-checkable; consumed downstream by Stage 3 + §1
  rows). Strictly, "un-fakeable" is the defect spec's own phrasing and
  is a slight overstatement — a fabricated-but-plausible id is
  possible, just detectable. Faithful to spec; see residual R1.
- **Dispatch executable:** `general-purpose` (Tools: *) can write the
  ordered file; Stage 2 dispatch and Stage 3 read use the same
  `reports/scope-feature/scan-${TS}/exploration.md` with TS pinned in
  Stage 0. Pre-repair, a strict harness made the Stage 3 fallback fire
  on every run (silent degradation); that is fixed.

## 3. No-invention audit

Every added hunk traced. Near-verbatim from change spec: C1, C2, C3,
C4, C5, C6 rationale parenthetical, C7(c)(d), C8. From scout: Q2
seeding consumer for the subsystems `ls` (scout §5 suggestion),
"registry-level, not content" audit honesty (scout §3). From
pre-existing text: "two months from now" (belief 1). Sibling-mirrored:
the `TS=` line (exact match to 10+ skills, per C7's "mirror how
sibling skills set it").

Two micro-additions without an explicit source line, both benign and
within change-spec intent:

1. `(write nothing else)` appended to the sub-agent prompt (L167–168)
   — a containment clause made newly relevant by switching to a
   write-capable agent type; serves C6's executable-contract intent.
2. `echo "no subsystem docs"` fallback string (L112) — standard
   graceful-absence idiom implementing C7(b)'s "absence is fine".

No invented numbers, names, paths, or claims. **No-invention: PASS.**

## 4. New-defect sweep (same classes)

- **Dangling pointers:** none introduced. Both `scan-${TS}` sites
  agree; `${TS}` is now defined. All file/skill refs in added text
  resolve (`scripts/_lib` exists; `/impact-feature` exists).
- **Unconsumed mandated steps:** none — both new verification outputs
  (4.5 verdicts, audit result) have a named Stage 6 consumer; the
  `ls` gained a Q2 consumer; the priors line has a named Stage 3
  consumer.
- **Stage cross-references:** numbering 0 → 0.5 → 1 → 2 → 3 → 4 → 4.5
  → 5 → 6, no renumbering (per constraints). Stage 0.5 forward-refs
  Q1–Q5 correctly; Stage 2 back-refs 0.5; Stage 4.5 forward-refs
  Stage 6; Stage 5 back-refs 4.5. No contradictions found (checked:
  0.5's never-silently-fill vs Stage 2's do-not-invent — consistent;
  L152 residual "Explore" mention is an explanatory negative, not a
  dispatch instruction).
- **Hallucination-invited phrasing:** none introduced; the edits
  convert two assertion-satisfiable steps (end-to-end read, "confirm
  the plan loads cleanly") into artifact-producing ones. The removed
  "Confirm the plan loads cleanly" was itself a false affordance
  (audit warn-and-skips parse failures, per scout §3) — good removal.

## 5. Mechanical checks

- Frontmatter YAML parses via `.venv/bin/python` + PyYAML: **OK**;
  `allowed-tools` includes `Agent`.
- Residue greps: no bare `python3` invocations; no `scan-<TS>` (unset
  placeholder); "stdlib-only" appears only as the corrective negation
  ("are **not** stdlib-only"); "Explore" appears only in the
  cannot-write rationale.

## 6. Residuals (severity)

| ID | Sev | Residual |
|---|---|---|
| R1 | Low | "Un-fakeable without the read" overstates: plausible prior ids could be fabricated; they are merely verifiable. Wording inherited verbatim from F6's prescription — not an implementer defect. |
| R2 | Low | Stage 4.5's "tighten §1 and re-test" loop has no iteration cap / stop condition (the rubric's own WORKFLOW TRAPS class). C1 specified it this way; flag for a future pass, not this repair. |
| R3 | Low | Sub-agent prompt uses a relative report path and `${TS}` / `<Q2 answers>` placeholders the orchestrator must substitute; no absolute project root despite CLAUDE.md's self-contained-prompt rule. Pre-existing class (unchanged convention), but now load-bearing since the agent can actually write. |
| R4 | Info | `plans.py audit` is registry-wide; "on failure, fix before reporting" can pull the executor into unrelated plans' drift, and exit 0 still cannot prove THIS plan parsed (warn-and-skip). The repaired text no longer claims it can; deeper fix (per-plan audit / placeholder-residue check) is a plans.py change outside this repair's scope. |
| R5 | Info | The C2 gate HTML comment will be copied into the written plan ("Use this shape") and persist in the artifact. Harmless — arguably useful for downstream adjudicators. |

## 7. Overall verdict vs declared verdict

The declared verdict — every gate tests a property not existence,
frame re-stated at the write site, phase-0 for conversation-rich
invocations, dispatch executable as written, nothing invented — is
**met on all five clauses**, finding-by-finding.

**OVERALL: PASS** (8/8 RESOLVED, 0 PARTIAL, 0 UNRESOLVED; no new
defects in the swept classes; residuals are low/info and either
inherited from the defect spec's own wording or pre-existing
conventions out of scope for this repair).
