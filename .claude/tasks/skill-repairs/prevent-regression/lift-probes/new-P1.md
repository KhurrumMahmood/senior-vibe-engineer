Based on reading the SKILL.md file exactly, here are the precise answers:

## 1. Where artifacts must live & what NOT to do to the working tree

**Artifacts are staged in the proposal directory, never in the actual working tree:**

From the introduction (lines 50–58):
> "Guard artifacts are **staged, not installed**: author them under the proposal directory at their repo-relative destination paths (`reports/prevent-regression/<id>/scripts/lint/<rule>.py`, `reports/prevent-regression/<id>/tests/lint/<rule>_bad.<ext>`, …)"

**Specific locations:**
- Rule script: `reports/prevent-regression/<id>/scripts/lint/<rule>.py`
- Bad fixture: `reports/prevent-regression/<id>/tests/lint/<rule>_bad.<ext>`
- Good fixture: `reports/prevent-regression/<id>/tests/lint/<rule>_good.<ext>`
- Pre-commit/CI/CLAUDE.md changes: **emitted as diff blocks inside `proposal.md`**, not applied

**What NOT to do** (from "How success is judged," lines 62–64):
> "Guard artifact + verification recipe **emitted, never installed unilaterally** — no guard artifact or wiring edit lands in the working tree."

---

## 2. Success gates

From "How success is judged" (lines 60–74), the run is judged on:

1. **No working tree modification** (lines 62–64): "no guard artifact or wiring edit lands in the working tree"

2. **Verification passes** (lines 65–66): "`verify_rule.py` reports BAD_RC=1, GOOD_RC=0 (Phase 3)"

3. **Historical regression check** (lines 67–68): "the rule fires on each pre-fix site via `git show <anchor>^:<file>` and is clean on current HEAD (Phase 6)"

4. **Fixture completeness** (lines 69–72): "The bad fixture covers every anti-pattern variant and the good fixture proves the rule stays quiet on legitimate forms (Phase 3) — the precision/recall gates a conformance harness re-runs by side-effect"

5. **Test-only guard option** (lines 73–74): "the focused regression module runs green, with its run output in the proposal"

Human reviews the proposal and executes the installation manually — the skill stops before applying any changes.
