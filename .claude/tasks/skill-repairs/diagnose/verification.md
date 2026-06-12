# Verification — /diagnose repair (independent, fresh-context)

Date: 2026-06-12. Verifier shared no context with the implementer.
Method: read repaired `.claude/skills/diagnose/SKILL.md` and formed the
defect-by-defect read BEFORE opening `scout.md`; diffed against
`/tmp/skill-repairs-old/diagnose/SKILL.md`; ran the script checks; then
audited every added sentence against change-spec + scout + review text.

## 1. Verdict table

Line numbers refer to the repaired SKILL.md.

| Item | Verdict | Resolving text (quoted) |
|---|---|---|
| F1 — root cause assertable with no discriminating artifact | **RESOLVED** | Phase 6, lines 165–170: "write `root-cause.md`: the falsifiable Phase 3 statement that was satisfied, the confirming probe's exact command and its pasted observed output, and - where feasible - a cause-toggle demonstration (the loop fails with the cause present, passes with it neutralized) recorded before the fix was written. A one-sentence narrative without a pasted probe is not a root cause" |
| F2 — confirmation without elimination | **RESOLVED** | Phase 4 tail, lines 132–135: "Before any fix, name each remaining hypothesis and the observation that rules it out. Any hypothesis that cannot be ruled out is named in `root-cause.md` as residual uncertainty. Consistent evidence is not discriminating evidence." Sits between Phase 4 and Phase 5 as specified (C2). |
| F3 — no Phase 0 evidence inventory / reporter-theory quarantine | **RESOLVED** | Phase 0, lines 56–59: "evidence already in hand: tracebacks, logs, prior fix attempts, and exact commands from the conversation;" + "the reporter's suspected cause - recorded as one hypothesis among several, never as a finding." |
| F4 — probe loop has no stop condition / back-edges | **RESOLVED** | Lines 137–140: "If every hypothesis is falsified, return to Phase 3 and re-rank the hypotheses using the new observations. After two full cycles without a confirmed cause, stop and write up the eliminated space as partial findings." Plus lines 173–174: "If verification fails, the root cause is unconfirmed - return to Phase 3; do not patch the fix." Both back-edges from the F4 smallest-fix present. |
| F5a — evidence-gate run is ceremony | **RESOLVED** | Lines 213–215: "The gate must exit 0 before the diagnosis is reportable. On exit 1, fix the named gap and re-run; do not proceed past a failing gate. Paste the gate's summary line in your final reply." Verified against the script: `cmd_check` returns 1 on fail and emits a single summary line (`"OK|FAIL: N/M required evidence shapes present."`, evidence_gate.py line ~165) and the text renderer names the failing token — "the named gap" and "summary line" both correspond to real output. |
| F5b — index omits Root cause / Reproduction | **RESOLVED** | Diagnosis Index Shape, lines 222–226 now reads `## Symptom / ## Reproduction / ## Root cause / ## Fix / ## Prevention follow-up`. Both mandated sections present; ordering was implementer's choice per scout. |
| F6 — reproduction/verification claimable by assertion | **RESOLVED** | Phase 2, lines 100–103: "Record the loop in `reproduction.md`: the exact loop command and one pasted failing run. For intermittent symptoms, also record the observed fail rate as N failures over M runs. Assertion without a transcript does not count." Phase 6, lines 159–160: "paste the passing rerun output of the same command into `verification.md`". Intermittent numerator/denominator now recorded. |
| D1 — evidence files produced by no phase | **RESOLVED** | All four files now named at producing phases: `reproduction.md` Phase 1 line 81 ("stop and write `reproduction.md` (the `reproduction_or_reason` evidence)") and Phase 2 line 100; `root-cause.md` Phase 6 line 165 (plus Phase 4 line 134 for residuals); `verification.md` Phase 6 line 160; `cleanup-check.md` Phase 6 line 163. The Phase 1 token-vs-file confusion ("write `reproduction_or_reason`") is gone. |
| D2 — `cleanup_check` declared but unwired | **RESOLVED** | Phase 6, lines 162–163: "remove every `[DIAG-...]` probe, then grep for the prefix and record the grep command and its output in `cleanup-check.md`". Tag→grep→artifact chain fully wired; the gate consumes the artifact. |
| D3 — `produces: regression_test` conditionally false | **RESOLVED** | Frontmatter line 29: `produces: [diagnosis_report, reproduction_loop, regression_test_or_seam_gap_finding]` — matches Phase 5's real conditional (test when a correct seam exists, architecture finding when not). Grepped all skills/docs/scripts: no other surface consumes the old `regression_test` token, so the rename dangles nothing. `evidence_gate.py show --skill diagnose` prints the new token cleanly. |
| D4 — stale "PR F/G will enforce" docstring | **RESOLVED** | evidence_gate.py docstring now: "The gate is run manually or by the skills that document it; nothing in CI consumes it." Accurate (no CI/hook reference to evidence_gate exists). |

**10/10 RESOLVED, 0 PARTIAL, 0 UNRESOLVED.**

## 2. Artifact-truth check

- **Gates state pass condition + failure path:** evidence gate (exit 0 =
  pass; exit 1 → fix named gap, re-run, do not proceed); elimination
  gate (pass = every remaining hypothesis ruled out or named as residual
  uncertainty; failure = all falsified → Phase 3; two cycles → stop with
  partial findings); Phase 6 verification (fail → Phase 3, no patching);
  Phase 1 abort (no credible loop → stop, write reproduction.md with
  reason). All four pass.
- **Producer AND consumer per artifact:** diagnosis.md (line 41 / final
  report, now consuming reproduction + root cause via index sections);
  reproduction.md (Phase 1+2 / gate + `## Reproduction`); root-cause.md
  (Phase 4+6 / gate + `## Root cause`); verification.md (Phase 6 /
  gate); cleanup-check.md (Phase 6 / gate). Pass.
- **root-cause.md standard is pasted-probe, not assertion:** yes —
  exact command + pasted observed output required, cause-toggle where
  feasible, and the explicit negative ("a one-sentence narrative without
  a pasted probe is not a root cause"). Textually un-fakeable; see
  residual R1 for the mechanical layer.

## 3. No-invention audit

Diffed old vs new; every added sentence traced:

| Addition | Source |
|---|---|
| Two Phase 0 bullets | C3 (near-verbatim) |
| `reproduction.md` named in Phase 1 abort | C7/D1 |
| Phase 2 recording paragraph (command + pasted run + N/M fail rate + "assertion without a transcript does not count") | C6 + scout F6 anchor 1 |
| Elimination-gate paragraph | C2 (near-verbatim, incl. "Consistent evidence is not discriminating evidence") |
| Falsified→Phase 3 / two-cycle stop paragraph | C4 (near-verbatim) |
| Phase 6 verification-paste bullet | C6 / scout F6 anchor 2 |
| Phase 6 cleanup-grep recording bullet | C7/D2 |
| Phase 6 root-cause.md bullet (a)(b)(c) | C1 (near-verbatim) |
| "If verification fails… do not patch the fix" | C4 |
| Gate exit-0 / exit-1 / summary-line paragraph | C5(a); "summary line" verified to exist in script output |
| `## Reproduction` + `## Root cause` index sections | C5(b) |
| `regression_test_or_seam_gap_finding` token | C7/D3 ("real conditional form"); scout D3 suggested exactly this phrasing |
| evidence_gate.py docstring sentence | C7/D4; content matches scout-verified reality |

**No invented sentences, thresholds, numbers, or names.** The only
numeric values added ("three to five" pre-existing; "two full cycles")
come from the review's F4 smallest-fix. Voice and phase numbering
preserved; no phase renumbered.

## 4. New-defect sweep (same classes)

- **Dangling pointers:** none. All file names, the gate command, flags,
  and skill references resolve. The renamed `produces` token has no
  external consumer (grepped `.claude/skills/`, `.claude/docs/`,
  `docs/`, `scripts/`).
- **Artifacts without producers:** none introduced; all five evidence
  files now have explicit producing instructions. (Pre-existing, out of
  scope: `evidence.json` itself has no imperative "write" verb — only
  "the report directory must contain" + the template; see R3.)
- **Contradictory thresholds:** none. The 30-minute `max_overhead`
  bounds Phase 1; the two-cycle stop bounds Phases 3–4; non-overlapping.
- **Ceremony stages:** none introduced; the gate paragraph, paste
  requirements, and index sections all create consumers for previously
  unconsumed outputs.
- **Hallucination-invited phrasing:** "paste the gate's summary line"
  and "fix the named gap" were verified against actual script output —
  both real. No new assertable-without-evidence claims added.

## 5. Script check

- `git diff scripts/evidence_gate.py`: single hunk, docstring lines
  26–27 only. No code change. Confirmed comment/docstring-only.
- `python3 scripts/evidence_gate.py --help` → exit 0.
- `python3 scripts/evidence_gate.py show --skill diagnose` → exit 0,
  parses frontmatter, prints all four `evidence_required` tokens and the
  new `produces` token correctly.

## 6. Residuals

| ID | Severity | Residual |
|---|---|---|
| R1 | Medium (acknowledged/ledgered) | The mechanical gate is still existence-only — the pasted-transcript standards are prose-enforced; a fabricated transcript passes `evidence_gate.py check`. Explicitly OUT OF SCOPE in the change spec (shared script, needs its own tested change). Not a repair failure, but the declared verdict's "un-fakeable" property holds only at the instruction layer until the content check ships. |
| R2 | Low | C1's parenthetical "(and where the file is first mentioned)": `root-cause.md` is now first mentioned in the Phase 4 elimination gate (residual-uncertainty content) while the full proof standard lives only at Phase 6. Defensible reading of the spec; F1 itself is fully resolved. |
| R3 | Low (pre-existing) | `evidence.json` has no imperative producing instruction (template + "must contain" only), and `verification.md`'s content has no index consumer (gate existence only). Both pre-date the repair and are outside F1–F6/D1–D4. |

## Overall verdict

**PASS** against the declared verdict. All ten findings resolved with
text traceable to the review, change spec, or scout fragments; no
inventions; no new defects of the audited classes; script edit is
docstring-only and the tool runs clean. Worst residual is R1, which the
change spec itself ledgered as out of scope.
