# Closeout — /fix-workflow repair campaign (Stage 8)

Date: 2026-06-12. Stages 0–2 pre-existed on disk; Stage 2's scout.md
was found to contain only a CLI spend-limit error and was re-run via
a fresh in-session sub-agent before Stage 3 (the change spec never
consumed the broken artifact). Stages 3–8 this session. No commits
made (campaign constraint); the working tree holds the repaired
skill + this record for the orchestrator to commit as two logical
units.

## Stage summary

- **Stage 3** — change-spec.md: C1–C11 (F1–F9 all scout-TRUE, plus
  D1–D3). D1 remediation (a) chosen on scout evidence: zero readers,
  path gitignored, promotion path to `knowledge/learnings.md` is the
  only consumed surface.
- **Stage 4** — implemented inline by the orchestrator (machine-local
  budget rule: fewer agent lanes); judgment calls in
  implementation.md; `skill_meta.py lint` OK.
- **Stage 5** — independent verification via the Codex lane (true
  cross-model independence; shares no implementer context).
  **Round 1 FAIL** (C2/C5 PARTIAL: shape-count language contradicted
  the grown table); fixed via Stage 4 on the failed sites only;
  **Round 2 PASS**, no invention findings.
- **Stage 6** — haiku probe pair at the Step-3 matrix site. Run 1
  invalidated (old-condition contamination — see lift-report.md
  harness note; lesson ledgered). Run 2 from neutral cwd: old =
  IMPROVISES-SILENT with a fabricated matrix row; new =
  FLAGS-AND-FALLS-BACK with real citations. **Lift positive, zero
  regressions.**
- **Stage 7** — no foreign host; substituted live script probes
  (dogfood.md): documented effectiveness invocation exit 0,
  invalid-buckets exit 1 per contract, jscpd wrapper surface matches
  the new `knowledge/verification.md` command.

## Class-lift gate (new classes only; D1–D3 already swept)

| Class | Detector | Hits | Disposition |
|---|---|---|---|
| Filename-stripped bare `knowledge/` reference | `grep -rn '\`knowledge/\`' .claude/skills/` | 78 raw (needs triage; extract-enum:84,97,309 CONFIRMED sibling — promises content in an empty knowledge/ dir) | batched → ledger intake `fix-workflow-repair-residual-sweeps` |
| Host-bound command without absence fallback | `grep -rln 'manage\.py' .claude/skills/*/SKILL.md .claude/skills/*/knowledge/*.md` | 9 files (1 = fix-workflow, now fallback-carrying by design) | 8 siblings batched → same intake |
| Handoff token without a Form A route/report map | `grep -rn '/fix-workflow [a-z]*:' .claude/skills/*/SKILL.md` | all 5 token kinds now route, BUT `cluster:<symbol>` from find-query-mutation / find-transaction-overreach / find-complexity-hotspots / find-incomplete-sweep resolves to `reports/duplication/latest/` while their reports live elsewhere — same class as the repaired `layer:` gap | batched → same intake (Form A report-source map keyed by detector) |
| Probe-harness cwd contamination (repair-skill Stage 6 itself) | manual (observed) | 1 | lesson on `repair-skill` ledger entry; repair-skill text edit deferred (outside this campaign's exclusive-ownership scope) |

## Residual triage (none dropped)

1. refactor-subsystem appends to dead `reports/duplication/learnings.md`
   (SKILL.md:1263, knowledge/operations.md:178) → ledgered (intake above).
2. Bare-knowledge-ref siblings (extract-enum confirmed) → ledgered.
3. Host-bound-command siblings (8 files) → ledgered.
4. `cluster:` report-routing gap (4 detectors) → ledgered.
5. Lift-harness neutral-cwd rule → lesson on `repair-skill`.
6. Verifier round-1 count defect → fixed in-campaign (round 2 PASS).

## Ledger writes

- `event repair-skill --kind note` — campaign result.
- `lesson repair-skill` — "Lift probes must run from a neutral cwd".
- `intake fix-workflow-repair-residual-sweeps` — four-class batch sweep spec.

## Limitations (for the orchestrator)

- Stage 3 spec and Stage 4 implementation share the orchestrator's
  context (single-lane budget mode). Independence was preserved
  where it matters most: the Stage 5 verifier ran on the Codex lane
  with no shared context and was told to refute — and did refute
  (round-1 FAIL was a real defect).
- Lift evidence is n=1 per cell, single tier, clean-context upper
  bound (per the locked protocol).
- Identity paths scrubbed from the record (`~`-relative); the only
  file touched by the scrub is the already-invalid run-1 transcript.
