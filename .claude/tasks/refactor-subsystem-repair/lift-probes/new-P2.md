# Phase 3 plan — item 7 entry: Test strategy for Batch 3

Probe context: /refactor-subsystem DECOMPOSITION mode. Batch 3 moves
`tasks/email_dispatch.py` (1,950 LOC Celery task code) into
`services/dispatch/`. `tests.test_email` is green on HEAD.
Skill sources: SKILL.md §3.2 item 7 + §2.1 (L-44 block),
`knowledge/execution-playbook.md` §5.2 step 4, `knowledge/learnings.md`
R36/R31, `knowledge/operations.md` "Verification test matrix".

---

## 7. Test strategy per batch — Batch 3 (`tasks/email_dispatch.py` → `services/dispatch/`)

### 7.3.1 Destination modules this batch creates or populates

(From plan items 1–2, symbol → destination map. The coverage-path
proof below is per **destination module**, not per batch.)

| Destination module | Role |
|---|---|
| `services/dispatch/__init__.py` | package init / re-exports |
| `services/dispatch/email_dispatch.py` | the 1,950 LOC of moved task code |
| `tasks/email_dispatch.py` (post-batch) | re-export shim — survivor, not a destination, listed for the shim tests |

### 7.3.2 Test scope for this batch

All run with the host runner
(`.venv/bin/python manage.py test <modules> --settings=app.settings_test_sqlite -v 2`):

1. **`tests.test_email`** — domain behavior suite for the moved tasks.
   Behavior coverage is this suite's job (L-44: in decomposition mode
   the characterization file pins *structure*, the domain suites pin
   *behavior*).
2. **`tests.test_<spec-id>_characterization`** — the Phase 2.1
   structure-pinning suite, which for this batch must contain:
   - `TaskImportabilityTest` — every public symbol still importable
     from the **original** path `tasks.email_dispatch` (shim
     compatibility, mandatory for Django module splits);
   - `TaskSignatureTest` — function signatures unchanged;
   - `TaskRegistrationTest` — every Celery task still registered under
     its **original wire name and options** (wire identifiers stay
     frozen — R44 bucket 2; the move must not rename
     `@shared_task(name=...)` registrations).
   Runs after this batch per execution-playbook §5.2 step 5 — it is
   part of every batch's scope, not just this one.
3. **Baseline always-suite** from the host-adapter test matrix slot in
   `knowledge/operations.md` (origin-project worked example:
   `tests.test_site_capabilities tests.test_hydration_detector`).

### 7.3.3 Coverage-path proof (R36 at batch level) — the grep evidence

Plan item 7's mandate (SKILL.md §3.2.7): the plan names the suites
**WITH grep evidence that at least one named suite imports or patches
each destination module**. The Phase 4 reviewer approves *coverage*,
not suite names. A batch whose grep comes back empty has **no test
strategy yet** — that is fixed here in Phase 3, before Phase 4.

Accepted reference shapes (execution-playbook §5.2 step 4): a plain
`import`, a `from ... import`, or a `patch("services.dispatch...")`
string.

```bash
# One grep per destination module, against the named suites:
grep -n "from services\.dispatch\|import services\.dispatch\|patch(['\"]services\.dispatch" \
  tests/test_email.py tests/test_<spec-id>_characterization.py
```

Evidence recorded in this plan (output pasted verbatim; reviewer
approves on this, not on our say-so):

```
tests/test_<spec-id>_characterization.py:14:from services.dispatch import email_dispatch
tests/test_<spec-id>_characterization.py:88:        patch("services.dispatch.email_dispatch.send_campaign_batch")
tests/test_email.py:21:from services.dispatch.email_dispatch import send_campaign_batch
```

⚠️ If, at plan-writing time, this grep is empty — the expected state,
since `tests.test_email` was written against `tasks.email_dispatch`
and `services/dispatch/` does not exist yet — the batch has no test
strategy and this entry cannot go to Phase 4 as-is. The fix lands in
this batch's plan, in order of preference:

1. extend `tests.test_<spec-id>_characterization` with import-level
   checks against the **destination** modules
   (`from services.dispatch import email_dispatch` plus
   `hasattr` assertions), and/or
2. retarget `tests.test_email`'s patches (see 7.3.4) so the suite
   references the destination directly.

Then re-run the grep and paste the non-empty output above.

**"Green on HEAD" is necessary but NOT sufficient.** `tests.test_email`
passing on HEAD only establishes the pre-batch baseline (and the
characterization suite must also pass on HEAD per §2.1). What makes
the scope ACCEPTABLE as behavior-preservation evidence is the
coverage path: per L-44, structure pinning is sufficient **only**
with this per-batch coverage-path proof — "never trust green from a
suite with no path into the moved code." A `tests.test_email` that
reaches the tasks solely through the `tasks.email_dispatch` shim with
synchronous `@patch` targets on the old path can stay green while
exercising none of the moved code.

### 7.3.4 Mock-patch classification (R31 / playbook §5.6 rule)

Because the old module becomes a re-export shim, every
`@patch("tasks.email_dispatch.*")` in the test scope is classified
before this batch is approved:

```bash
grep -rn "patch(['\"]tasks\.email_dispatch" tests/
```

| Patch shape | Verdict |
|---|---|
| `patch("tasks.email_dispatch.<task>.delay")` | Safe through the shim — patches the task object itself; no change needed. |
| `patch("tasks.email_dispatch.<func>")` for a **synchronous** call made inside `services/dispatch/` | Bypassed after the move (the domain module uses its own local reference). Must be retargeted to `services.dispatch.email_dispatch.<func>` **in this batch**, and does NOT count as a coverage path into the destination until retargeted. |

The classification table (one row per patch site, with file:line)
is appended to this entry before Phase 4 review.

### 7.3.5 Batch gate (how the scope is exercised at Phase 5)

- Batch 3 leaves the repo green and is individually revertable (plan
  item 6 invariant); commit prefix `[<spec-id>:batch-3]` naming the
  suites run.
- Per execution-playbook §5.2 step 4, the coverage-path grep in 7.3.3
  is **re-verified at batch execution time** before the suites run —
  an empty grep at execution stops the batch even if the plan showed
  evidence (the test files may have changed since Phase 3).
- Per §5.2 steps 5–6: characterization suite runs after the batch
  suites; any failure stops the batch (fix or revert — no broken
  state carried into Batch 4).

### 7.3.6 What the Phase 4 reviewer needs in this entry before approval

1. Named suites (7.3.2) — including the characterization suite and
   the baseline always-suite, not just `tests.test_email`.
2. The pasted, non-empty grep output proving ≥1 named suite imports
   or patches **each** destination module of Batch 3
   (`services/dispatch/__init__.py` re-exports count via
   `from services.dispatch import ...`; `email_dispatch.py` needs its
   own hit). Empty grep for any destination module = no test
   strategy = not reviewable.
3. The R31 patch-classification table, with the synchronous-patch
   retargets scheduled inside this batch.
4. Confirmation that the characterization suite's structure pins
   (importability from the old path, signatures, Celery registration
   under original wire names) exist and passed on HEAD.
