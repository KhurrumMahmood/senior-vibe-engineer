# Phase 3 Batch 3 Test Strategy — email_dispatch decomposition

**Batch 3:** Move `tasks/email_dispatch.py` (1,950 LOC of Celery task code) → `services/dispatch/`

## Test scope

The following modules' tests must pass for this batch:

1. **Primary:** `tests.test_email` (domain test suite)
   - Status at HEAD: green
   - Scope: covers email dispatch behavior, task registration, retry/error handling

2. **Secondary coverage (behavioral baseline):**
   - `tests.test_celery_dispatch` (if exists; covers generic task dispatch patterns)
   - `tests.test_services` (if the services module is under test; catches import errors in dispatch service layer)

## Coverage-path proof (R36 — mandatory before Phase 4 approval)

Before this batch runs, execute the following grepping against the test modules above to prove at least one suite imports or patches the batch's destination module(s). A batch whose grep comes back empty **blocks Phase 4** — fix the test strategy before approval.

**Destination modules for Batch 3:**
- `services/dispatch/` (new package, or new file `services/dispatch.py` depending on extraction shape)
- `services/dispatch/__init__.py` (if package) or the module re-exports from this location
- Celery task re-export shim at original `tasks/email_dispatch.py` (or via `tasks/__init__.py` if flat → package migration)

**Mandatory grep checks:**

```bash
# Check 1: tests.test_email imports from destination
grep -r "from services.dispatch import\|from tasks.email_dispatch import\|import services.dispatch\|import tasks.email_dispatch" \
  tests/test_email.py

# Check 2: tests.test_email patches dispatch task functions
grep -r "patch.*services\.dispatch\|patch.*tasks\.email_dispatch" \
  tests/test_email.py

# Check 3: If secondary suite exists, repeat checks 1–2 against tests/test_celery_dispatch.py
grep -r "from services.dispatch import\|from tasks.email_dispatch import" \
  tests/test_celery_dispatch.py 2>/dev/null || echo "skipped (suite may not exist)"
```

**Pass criteria:** At least ONE of the grepped files (test_email.py + any secondary suite) must have:
- A line matching `from services.dispatch import ...` or `from tasks.email_dispatch import ...`, OR
- A line matching `patch("services.dispatch....")` or similar mock directive

If ALL grepped results are empty, the test suite has no path into the moved code and **cannot serve as the coverage-path proof for this batch**. The test strategy must be revised (either existing suite lacks coverage, or new test module must be written before Phase 5 execution).

## Acceptance criteria before Phase 4

1. **Grep output included in plan:** Show the actual `grep` output for each check above. Paste the line(s) that prove path coverage.

2. **Named suite explicitly listed:** The plan entry names the test module(s) by full path (`tests.test_email`, `tests.test_celery_dispatch`, etc.).

3. **Coverage proof is NOT speculative:** Do not write "tests will mock this" or "the service layer is tested elsewhere." The grep output is the evidence — it either exists in the test file or it doesn't.

4. **All destination modules have a path:** If Batch 3 creates multiple modules (`services/dispatch/__init__.py`, `services/dispatch/sender.py`, `services/dispatch/retry_handler.py`), then each must appear in at least one grep hit across the named test suites. If a destination module passes are empty, add a test-coverage clarification note or defer that module to a subsequent batch.

## Behavior-preservation mechanism

- Characterization tests from Phase 2.1 (`tests.test_<spec-id>_characterization`, if written) still pass after this batch.
- Domain tests (`tests.test_email`) remain green — this is the primary behavioral gate.
- If Batch 3 introduces a new service layer (e.g., `EmailDispatchService`), shim compatibility tests verify that callers importing from the old `tasks.email_dispatch` path still work (or a deliberate caller-update wave lands first per §5.6).

## Risks and mitigations

- **Risk:** Task registration name collisions if tasks are re-exported with different module paths.
  - **Mitigation:** Celery task names are frozen in the spec as-is; re-export shim preserves original import paths.

- **Risk:** Circular imports if new service layer imports task modules.
  - **Mitigation:** Lazy imports inside function bodies if cross-cluster calls are needed (R32 from SOLID audit).

- **Risk:** Tests pass but code path is not exercised (coverage depth issue).
  - **Mitigation:** The grep proof requirement ensures the test file explicitly references the destination; silent stub tests will fail the grep check.

## Rollback plan

If Batch 3 tests fail:
1. Revert the batch commit.
2. Characterization tests still pass (they were not edited in this batch).
3. Re-read the plan's batch structure — batches were not independent.
4. Re-plan Batch 3 scope or merge with an adjacent batch.

---

## Plan reviewer checklist (Phase 4)

- [ ] Grep output is present for each destination module.
- [ ] At least one named test suite has a hit for each destination.
- [ ] Test suite names are explicit (full path, e.g., `tests.test_email`).
- [ ] No empty-grep destinations are marked "will be tested later."
- [ ] Characterization test plan is clear (Phase 2.1 naming convention understood).
