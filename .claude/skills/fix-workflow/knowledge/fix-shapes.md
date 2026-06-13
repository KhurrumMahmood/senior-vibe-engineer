# Fix-shape playbooks

The orchestrator reads only the section matching the classified
shape. Shapes map to sections:

| Shape                                   | Section         |
|-----------------------------------------|-----------------|
| Pure duplication / three-way clone      | [2a](#2a-extract-helper-shapes) |
| Policy-flag clone                       | [2a](#2a-extract-helper-shapes) |
| Template triplication                   | [2a](#2a-extract-helper-shapes) |
| Shadow helper                           | [2b](#2b-shadow-helper-shapes) |
| Dead code                               | [2c](#2c-dead-code-deletion) |
| Quasi-dead / broken                     | [2d](#2d-quasi-dead--broken-fix) |
| Workflow registry cleanup               | inline checklist in `SKILL.md` Step 2 |
| Extract service (layer violation)       | [2a](#2a-extract-helper-shapes) applied at service scope |

Each section ends with a "stop condition" — if you can't satisfy it,
abort and report to the user rather than committing half-done work.

---

## 2a. Extract-helper shapes

Covers pure duplication, three-way+ clones, policy-flag clones, and
template triplication.

Before creating a helper, apply
`.claude/skills/_common/interface-depth.md`. The helper should hide a
real repeated invariant, failure shape, resource policy, or data-shaping
rule. If the deletion test says the helper would mostly vanish rather
than spread complexity back across callers, don't extract it — document
why the duplication is intentionally local or pick a smaller target.

### Order of operations

1. **Write the helper first.** Add it at module scope (default) or
   as a `@staticmethod` on the class (only if the class has stateful
   methods the helper genuinely belongs with — see R6 in
   `learnings.md`). Leading underscore if private to the file; no
   underscore if importable.

2. **Lift only the truly-identical middle.** Keep log lines, error
   handling semantics, and prompt/parameter construction in the
   callers. Log format is behavior (R3) — do not unify log strings
   for "cleanliness", that's a behavior change.

3. **Helper contract guidelines:**
   - **Policy flags go keyword-only** (R4): `def _helper(a, b, *, reclassify: bool):`.
   - **Failure is a value, not a control-flow action** (R5): return
     `None` on failure rather than raising, so callers compose with
     their own `continue` / `return None` / `raise` policy.
   - **Return tuples for three-piece results** (`(result, cost, cost_dict)`),
     or a small dataclass if the call surface is wider than three
     sites.
   - **Private helpers can return mutable dicts** for ergonomic
     augmentation at call sites (`result['column_used'] = ...`);
     public helpers should return immutable structures.
   - **Tests cross the caller-facing interface.** Prefer tests that
     exercise the public caller or public helper behavior over tests
     that pin private implementation steps.
   - **No adapter unless variation is real.** A single production
     implementation plus no realistic fake is usually not a seam.

4. **Refactor the callers to delegate to the helper.** Keep the
   caller's surrounding scaffolding (logging, error handling, input
   prep, output augmentation) in place.

5. **Run the targeted test suite** (see `knowledge/verification.md`
   test matrix) before committing. If any test fails, **do not commit** —
   fix the issue first. If you can't figure out the fix, abort and
   report the exact test+assertion to the user.

### Stop condition

- Targeted test suite passes.
- Helper is called from every caller the triage report flagged.
- Helper passes the deletion test or the learnings entry explains why
  local duplication is intentionally retained.
- Call-site log lines are byte-identical to the pre-refactor lines.
- `git diff --stat` shows only the files you planned to touch.

---

## 2b. Shadow-helper shapes

Three sub-cases. Determine which by **Reading both the shadow body
and the canonical body and diffing them carefully** (R7).

### 2b-i. True shadow

Bodies semantically identical, same default, same return type.

1. Delete shadow definition.
2. Add canonical import at top of file if not present.
3. Migrate all call sites to canonical (simple rename).
4. Run tests.

### 2b-ii. Canonical gap

Shadow fills a role canonical doesn't (e.g., `None` sentinel where
canonical requires a numeric default).

1. Write a new helper in the canonical module that fills the gap.
   Name it distinctively (e.g., `maybe_int` next to `safe_int`). Add
   a docstring explaining **when to use which**.
2. Add tests for the new helper in the canonical module's test file.
3. Migrate shadow call sites to the new canonical helper.
4. Delete shadow.

**Two-commit cluster** (R8-shaped split):
- Commit 1: add new canonical helper + tests (Promote).
- Commit 2: migrate shadow + delete it (Migrate).

Keep them separate so bisect can isolate a regression.

### 2b-iii. Module-local concept

Shadow encodes a concept that belongs only in one file (e.g., takes
a module-private dataclass).

**Skip.** Not a dedup target. Document the decision in the commit
message (or learnings log if you're skipping without a commit);
don't touch the file.

### Stop condition

- Sub-case is decided before you start editing (don't discover
  mid-refactor that 2b-ii applies when you thought it was 2b-i).
- Canonical module's tests still pass.
- Every shadow call site migrated — `git grep` for the shadow name
  returns zero results inside the target file.

---

## 2c. Dead-code deletion

Only proceed if the `/find-dormant` report for this candidate is in
the "Certain delete" or "Orphan endpoint" bucket AND the user has
authorized the deletion.

1. **Re-verify freshness AND dispatch-registry references.** The
   dormant report is a snapshot — new callers may have landed since
   it was written, and some dispatch paths use string literals that
   `git grep -w` alone can miss. Run BOTH checks. The roots below
   are the birth host's (Django) — if the host lacks them,
   substitute the host's source/template/static roots and name the
   substitution in your execution plan:

   ```bash
   # 1a. Word-boundary re-grep (catches direct symbol references):
   git grep -w '<name>' -- core/ templates/ static/ urls.py admin.py \
       management/commands/ frontend/

   # 1b. String-literal search (catches registry-style dispatch):
   #   - Celery task names (`current_app.send_task("core.tasks.<name>")`)
   #   - Django URL names (`{% url '<name>' %}`, `reverse('<name>')`)
   #   - JS fetch paths that reference the view's route
   #   - getattr / importlib-style indirect lookups
   git grep -E "['\"]<name>['\"]|['\"][a-z_.]+\\.<name>['\"]" -- \
       core/ templates/ static/ frontend/
   ```

   If *either* grep surfaces a reference not in the original dormant
   report, **abort** and escalate to the user. Deletion is no longer
   safe until the new reference is investigated — it may be a live
   caller that landed between the `/find-dormant` run and now, or a
   string-dispatched entry point the scanner missed.

2. **Delete the function/class/view.**

3. **Prune alongside:**
   - `__all__` entries in the module
   - Import sites that pull the now-dead name
   - URL patterns in the host's URL modules (birth host:
     `core/urls.py`) if it was a view
   - Admin registrations (birth host: `core/admin.py`) if it was a
     model admin
   - Management command references
   - Tests that exercised the deleted code (Cluster 3's lesson:
     don't keep `@skip`'d dead tests as cargo-cult coverage)

4. **Check for file-level deletion opportunity.** If the file had
   one dead function and now has none, fine. But if deleting
   revealed the whole file is dead, delete the file and remove it
   from `__init__.py` imports.

5. **Run the full baseline test matrix** — dead code deletion is
   high blast radius. The command below is the birth host's; no
   `manage.py` on the host → run the host's baseline equivalent per
   the `knowledge/verification.md` absence fallback and name the
   substitution:
   ```bash
   .venv/bin/python manage.py test \
     tests.test_site_capabilities tests.test_hydration_detector \
     <any_other_relevant_from_matrix> \
     --settings=app.settings_test_sqlite -v 2
   ```

6. **Run the framework's dangling-reference check** (birth host:
   `django-admin check`) to catch dangling URL patterns:
   ```bash
   .venv/bin/python manage.py check
   ```
   No host equivalent → state that explicitly in the stop-condition
   check; do not claim the check passed.

### Stop condition

- Fresh re-grep returned zero new inbound references.
- The framework's dangling-reference check passes (birth host:
  `manage.py check`) — or the named host substitute, or its absence
  is stated.
- Baseline + subsystem tests pass (substitutions named).
- Commit title starts with `Delete`.

---

## 2d. Quasi-dead / broken fix

Use when the function is quasi-dead (silently broken, no callers)
AND the user chose "fix" over "delete" in the `/find-dormant`
escalation.

1. **Write a failing test first.** The test should reproduce the
   bug — e.g., if the function blows up with `AttributeError` on a
   non-existent field, write a test that exercises the field and
   assert the expected value.

2. **Run the test and confirm it fails** with the exception you
   expect. If it passes, your test is wrong — the bug is elsewhere
   or the function wasn't as broken as reported. Investigate before
   writing fix code.

3. **Fix the code.** Small blast radius: rename the field, restore
   the missing attribute, repair the broken import. Do **not**
   refactor adjacent code (R11).

4. **Rerun the test and confirm it passes.**

5. **Add additional regression tests** for the other code paths in
   the function — the bug probably hid because nobody tested any of
   them.

6. **Commit the fix + tests in one commit.** This is the exception
   to the "refactor and fix in separate commits" rule — for a pure
   fix with no refactor, one commit is right.

7. **Escalate deletion separately.** The fix was in-scope;
   deletion of the now-working-but-unreferenced endpoint is a new
   decision. Report it to the user as a follow-on finding; don't
   delete in the fix commit.

### Stop condition

- New failing test → passes after the fix.
- No non-fix edits in the commit diff.
- Commit title starts with `Fix`.
- Deletion of the now-working endpoint surfaced to the user, not
  executed.
