# Probe old-P2 — Phase 3 plan item 7 (per-batch test strategy), Batch 3

Skill basis: SKILL.md §3.2 item 7 ("Test strategy per batch — which
modules' tests need to pass"), execution-playbook §5.2 steps 4–6,
§5.6, and learnings R6, R8, R31, R36, R44, L-44.

---

## 7. Test strategy — Batch 3 (`tasks/email_dispatch.py` → `services/dispatch/`)

### Test scope for this batch

Per execution-playbook §5.2, every batch runs TWO suites and both must
be green before the batch commits:

1. **Batch-specific domain suite** (step 4):

   ```bash
   .venv/bin/python manage.py test tests.test_email \
     --settings=app.settings_test_sqlite -v 2
   ```

2. **Characterization tests from Phase 2.1** (step 5 — mandatory for
   every batch, not optional):

   ```bash
   .venv/bin/python manage.py test tests.test_<spec-id>_characterization \
     --settings=app.settings_test_sqlite -v 2
   ```

If any test in either suite fails: **stop** (§5.2 step 6). Fix the
batch or revert it (R6 — batches commit-or-revert atomically; do not
accumulate broken state). The batch commit message lists the suites
run and their result, per the §5.2 step 7 commit template.

(The always-baseline pair `tests.test_site_capabilities` +
`tests.test_hydration_detector` is the Phase 6.1 gate, not a per-batch
requirement; it is named here only so the reviewer can see it was not
silently substituted for the batch scope.)

### Why this scope is ACCEPTABLE as behavior-preservation evidence

Green output is evidence only if all of the following hold; each is a
skill mandate, not a preference:

1. **Green-on-HEAD baseline exists for both suites.**
   `tests.test_email` passes on HEAD (confirmed in the scenario), and
   Phase 2.1 requires the characterization tests to pass on HEAD
   before any code moves. Behavior preservation is a *delta* claim —
   "same tests, green before and green after" — so the before-state
   must be recorded in this plan entry. If a characterization test
   fails on HEAD, the test is wrong (fix it) or the behavior is
   already broken (flag P0, do NOT adjust the test — R8: we preserve
   current behavior, including broken behavior).

2. **The domain suite demonstrably exercises the moved code (R36).**
   "Never trust 'green' from a test suite that has no path into the
   edited code." Before this batch can be approved, the orchestrator
   greps `tests/test_email*.py` for a reference to the target module:

   ```bash
   grep -lE "from tasks\.email_dispatch|import email_dispatch|patch\(['\"]tasks\.email_dispatch" \
     tests/test_email.py
   ```

   At least one import / `from ... import` / `patch("tasks.email_dispatch...")`
   reference must be found, and the grep evidence is recorded in this
   plan entry. If the grep returns empty, `tests.test_email` is a
   false green for this batch — the entry is NOT approvable as
   written; either swap in / add a test module that does reference the
   file, write a one-test characterization module first, or escalate
   as a P1 finding so a real regression test exists before code moves.

3. **Characterization tests pin the right things for decomposition
   mode (L-44): structure, not behavior.** This is a 1,950-LOC Celery
   task module, so the characterization file must contain, for the
   `email_dispatch` public surface:
   - **TaskImportabilityTest** — every public symbol still importable
     from the ORIGINAL path `tasks.email_dispatch` (the old module
     becomes a re-export shim; shim compatibility tests are mandatory
     for Django module splits), plus parent-package imports if
     `tasks/` re-exports them.
   - **TaskSignatureTest** — function signatures unchanged.
   - **TaskRegistrationTest** — every Celery task still registered
     under its ORIGINAL broker name and options. This is the R44
     wire-identifier bucket: `@shared_task(name=...)` strings are
     frozen identity, queried by the broker, and must NOT follow the
     `tasks/ → services/dispatch/` move. Behavior tests remain
     `tests.test_email`'s job.

4. **Independence and revertability.** The scope above must pass with
   only Batches 1–3 applied (no dependence on later batches), so
   Batch 3 is individually revertable per plan item 6. If Batch 3
   breaks an earlier batch's tests, revert Batch 3 and re-plan.

### What must be verified / included before the Phase 4 reviewer can approve

- [ ] **R36 grep evidence pasted into this entry** showing
      `tests.test_email` references `tasks.email_dispatch` (import,
      `from ... import`, or `patch(...)`). No reference → entry not
      approvable; remediation path named above.
- [ ] **Named characterization module** (`tests.test_<spec-id>_characterization`)
      exists, is marked `# spec:<spec-id>::characterization`, covers
      the email_dispatch importability / signature / Celery-registration
      surface, and **passes on HEAD** (command + result recorded).
- [ ] **Green-on-HEAD result for `tests.test_email`** recorded
      (already established in this run).
- [ ] **Mock-patch classification (R31 / playbook §5.6.4):** grep all
      test files for `@patch(...tasks.email_dispatch...)` and classify
      each hit — `.delay()` patches work through the shim (no change);
      synchronous-call patches must be retargeted to the new module in
      the **caller-update wave**, a separate later batch, not bundled
      into Batch 3. The classification table (or "none found") goes in
      this entry so the reviewer can see the test suite will not
      silently bypass mocks after the move.
- [ ] **Wire-identifier confirmation (R44):** explicit note that
      Celery task `name=` strings (and any other wire identifiers)
      stay frozen across the move, with TaskRegistrationTest named as
      the guard.
- [ ] **Stop condition stated:** any failure in either suite halts the
      batch (fix or revert; never proceed broken — §5.2 step 6 / R6).
