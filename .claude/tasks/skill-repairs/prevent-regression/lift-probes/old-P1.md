I'll read the skill file to answer these precisely.

Based on **section "Invocation" (lines 38–48)** and **section "Phase 6 — Proposal + report" (lines 335–386)**, here are the answers:

## (1) File locations and working tree constraints

**Must exist when the run ends:**
- Rule script: `scripts/lint/<rule>.py` (created in working tree) — Phase 2, line 217
- Fixtures: `tests/lint/<rule>_bad.<ext>` + `tests/lint/<rule>_good.<ext>` (created in working tree) — Phase 3, line 240
- Proposal: `reports/prevent-regression/<id>/proposal.md` (created in reports directory) — Phase 6, line 339
- Effectiveness log: `reports/_meta/effectiveness.jsonl` (appended) — Phase 6, line 339

**What you must NOT do to the working tree:**

Do NOT actually modify `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, or `.claude/CLAUDE.md` in the working tree during the skill run. The preamble states (lines 14–15): **"Read-only against production code — never installs the guard unilaterally; the human reviews and executes."** And (lines 46–48): **"The skill produces a **proposal** ... and stops. The human reviews and executes."** Those wiring changes are proposed in `proposal.md` but executed by the human afterward, not by the skill.

## (2) Success gates

The run's success is judged on:

1. **Fixture pair verification** (Phase 3, line 262–263): `verify_rule.py` reports **BAD_RC=1** (violations fired) and **GOOD_RC=0** (no false positives). ✓ You stated this already passes.

2. **Historical regression check** (Phase 6 Verification, lines 365–366): "rule fires on `git show <anchor>^:<file>` for each pre-fix site."

3. **Clean on current HEAD** (Phase 6 Verification, line 366): Rule produces zero violations on the current codebase.

4. **Proposal completeness** (Phase 6, lines 341–372): `proposal.md` contains all required sections: source cluster, pattern, artifacts, verification results, follow-on findings.
