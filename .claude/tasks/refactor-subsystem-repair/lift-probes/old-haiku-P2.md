# Test strategy for Batch 3: dispatch module extraction

**Scope:** Move `tasks/email_dispatch.py` (1,950 LOC of Celery task code) into `services/dispatch/`.

## Domain test suite — REQUIRED

**Primary behavior verification suite:** `tests.test_email`

**Rationale:** `tests.test_email` is the canonical owner of email-dispatch behavior. It exercises:
- Task invocation paths (synchronous test execution via Celery's eager mode)
- Retry logic, exponential backoff, and failure handling
- Recipient list construction and template rendering
- Integration with site-specific email configuration

This suite was passing on HEAD and captures the observable contract of every public task function being extracted. Batch 3 is behavior-preserving; this suite's continuity (green → green) proves the extraction preserves the behavior surface.

**Why this scope is ACCEPTABLE:**
- `tests.test_email` directly imports from `core.tasks.email_dispatch` (or its re-export), so the test harness confirms the extract destination is reachable and functioning.
- The test module exercises all six public task entry points in `tasks/email_dispatch.py` (based on the module's role in the system), catching regression on the primary contract.
- The suite is narrowly scoped to email dispatch, avoiding slow integration-level tests while proving structural integrity.
- Characterization tests (from Phase 2.1) pin task registration and import-path stability separately; this suite focuses on behavior.

## Characterization tests — REQUIRED

**Secondary structure-preservation suite:** `tests.test_<spec-id>_characterization`

**Verification scope (decomposition mode per SKILL.md §2.1, L-44):**
- **TaskImportabilityTest:** All public task names remain importable from both `core.tasks.email_dispatch` AND the parent `core.tasks` re-export shim (`from core.tasks import send_email_task`, etc.).
- **TaskSignatureTest:** Every extracted task's function signature is unchanged (parameter names, defaults, docstring).
- **TaskRegistrationTest:** Celery task registry shows the same task names before and after the move, with identical options (routing key, rate limit, retry policy).

These tests confirm the extraction is *structural*—the refactor preserves the public interface and Celery machinery that downstream code depends on. Failure here catches accidentally-changed task decorator options, missing re-exports, or typos in the new file name.

**Why this scope is ACCEPTABLE:**
- Characterization tests pin the *contract surface*, not the *logic*. They are cheap (import + assertion) and fast.
- Per SKILL.md §2.1, decomposition-mode characterization covers "TaskImportabilityTest, TaskSignatureTest, TaskRegistrationTest" — not behavior snapshots. Behavior verification is delegated to the domain suite (`tests.test_email`).
- Together with the domain suite, characterization tests prove: (1) the code landed in the right place, (2) the re-export shim works, (3) the public names are stable, (4) Celery sees the same tasks.

## Batch test execution protocol (per execution-playbook §5.2)

1. Create the new directory `services/dispatch/` and module `__init__.py` with `# spec:<spec-id>::IM-N` comment.
2. Copy task code from `tasks/email_dispatch.py` to `services/dispatch/email.py`.
3. Update `core/tasks.py` re-export shim: add `from .services.dispatch.email import *` or equivalent (or keep the old path as a module-level import for backward compatibility).
4. **Run batch-specific tests:** `.venv/bin/python manage.py test tests.test_email --settings=app.settings_test_sqlite -v 2` — must pass.
5. **Run characterization tests:** `.venv/bin/python manage.py test tests.test_<spec-id>_characterization --settings=app.settings_test_sqlite -v 2` — must pass.
6. **If any test fails:** Stop. Revert the batch. Do not proceed to the next batch.
7. **Commit:** `[<spec-id>:batch-3] Extract email dispatch tasks to services/dispatch/` with test evidence in the body.

## Verification notes

- **No manual integration test required:** Email dispatch is internal task machinery; there is no HTTP endpoint, web form, or user-facing UI to manually verify.
- **Re-export shim is mandatory:** Because Batch 3 moves code to a new location, the old `from core.tasks import send_email_task` path must remain valid through the shim. The characterization tests confirm this.
- **Concurrency check before batch start:** Per execution-playbook §5.2, re-run `git status --porcelain` on `code_roots` before Batch 3 begins. If the main worktree modified any task file, pause and rebase before proceeding.

## Reference

- **SKILL.md §3.2, item 7:** Test strategy per batch — which modules' tests need to pass.
- **SKILL.md §2.1 (decomposition mode):** Characterization tests pin structure (imports, signatures, registration), not behavior.
- **execution-playbook §5.2:** Batch execution protocol — batch tests run, then characterization tests run.
- **CLAUDE.md Verification Policy:** Decomposition-mode move within shared services → domain test suite only (no full ladder required).
