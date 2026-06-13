Perfect. I've located the directive files. Here's what the skill mandates:

## (1) **Step 3 Verification — Tests to run:**

**Directive source:** `~/Projects/engineering-skills/.claude/skills/fix-workflow/knowledge/verification.md` (lines 30–50)

The verification test matrix is **unfilled/absent** on this project. Per the **absence fallback** (mandatory when the table is unfilled):

> "Do NOT invent rows or report 'the matrix says'. Run the narrowest meaningful suite for the touched files (the host's `docs/testing.md` or project adapter names it), and **state in the execution plan that the matrix was absent and which suite you chose.**"

**Action:** I must:
- Read `docs/testing.md` in the project to identify the narrowest meaningful test module covering `core/services/parsing.py`
- Run that suite
- Record in the learnings entry that the matrix was absent and which suite was executed

---

## (2) **Step 4 Commit conventions:**

**Directive source:** `~/Projects/engineering-skills/.claude/skills/fix-workflow/knowledge/verification.md` (lines 52–65)

**Verb:** `Dedup` (for pure-duplication extract-helper cleanup)

**Template:**
```
Dedup <what>: <cluster name or target>

- Behavior preserved (R1); a latent bug left in place is named:
  "Behavior preserved, including <bug>".
- Reordered side effects name the new order and the crash
  implication (R8).
```

The commit title must **start with the verb** `Dedup`, followed by what was deduplicated and the cluster reference (P0-3).

Ready to proceed with Step 3 verification. Should I read `docs/testing.md` to identify the correct test suite for `core/services/parsing.py`?
