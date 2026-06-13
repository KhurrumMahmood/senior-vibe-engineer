Based on reading the `/fix-workflow` skill:

## (1) Tests for Step 3 Verification

**Which tests:** According to `knowledge/verification.md` (lines 30-50), the verification test matrix is **unfilled** ("_(unfilled — apply the absence fallback below)_"). Therefore, the skill mandates the **absence fallback**: run the narrowest meaningful suite for the touched subsystem (`core/services/parsing.py`) and state the choice in the plan.

**Where this is specified:** `knowledge/verification.md` lines 30-50 (the "Absence fallback" section), delegated from `SKILL.md` lines 231-241.

Since the matrix is absent, I must:
- Identify the test module(s) covering `core/services/parsing.py` in the host project's `docs/testing.md` or testing conventions
- Run that narrowest suite
- Explicitly state "the matrix was absent and which suite you chose" in the execution plan

Additionally, **for this dedup-shape cluster**: post-cluster jscpd re-scan (command at `verification.md` lines 67-77; jscpd rerun mandatory for dedup clusters per `SKILL.md` line 248 and learnings R14).

## (2) Commit Message Conventions

**Conventions and template:** `knowledge/verification.md` lines 52-65

- **Verbs:** `Dedup` / `Delete` / `Fix` / `Promote` / `Migrate`
- **Template:**
  ```
  <Verb> <what>: <cluster name or target>

  - Behavior preserved (R1); a latent bug left in place is named:
    "Behavior preserved, including <bug>".
  - Reordered side effects name the new order and the crash
    implication (R8).
  ```

For this cluster (pure-duplication extract-helper), the verb is **`Dedup`**, and the commit message starts with that verb per the template.

**Where specified:** `SKILL.md` lines 250-262 (Step 4 — Commit discipline) delegates to `knowledge/verification.md` lines 52-65.
