# Phase 5 execution playbook

The orchestrator reads this file at the start of Phase 5, not front-to-back
on every run. It contains the batch protocol, two-commit discipline, the
micro-fix swarm pattern, convention-enforcement decision loop, ledger update
rules, and the decomposition-mode caller-update wave.

Phase 5 goal: make the planned changes, one batch at a time, with spec
markers, tests, and commits landing in lockstep.

---

## 5.1 Spec markers BEFORE implementation

For the current batch, update the spec items the batch will touch. Mark IM
items as `[~]` (partial) when work begins, then `[x]` when the batch lands.
Add `# spec:<spec-id>::IM-N` comments in the new files **before** populating
them with code — the coverage tool scans comments, so this bootstraps the
code→spec link.

```bash
# Edit ai-docs/specs/<spec-id>.md: change [ ] IM-1 to [~] IM-1
# Then create core/<new-module>.py with:
#   # spec:<spec-id>::IM-1
#   """Module extracted from core/<old>.py per <spec-id>."""
```

## 5.2 Batch execution

For each batch in the plan:

0. **Re-run the concurrency check (R6; original lesson L-4)** before touching files. The main
   worktree's dirty set changes while the refactor runs:
   ```bash
   git -C ~/Projects/your-project status --porcelain | \
     grep -E '<code_roots regex>' && echo "COLLISION" || echo "clear"
   ```
   If any file in `code_roots` now shows `M` / `??` in the main worktree,
   **stop**. Do not start this batch. Either (a) wait for the main worktree
   to land its edit and rebase the refactor branch on top, or (b) abort the
   refactor and re-plan from a fresh Phase 1 inventory. Cost of the check:
   ~50ms. Cost of missing a mid-refactor collision: merge-conflict hell or
   a silently stale base. Run this before every batch, not just the first.

1. **Create the new files** (if any) with the `# spec` comment at the top.

2. **Move the code** — copy from the old location into the new file. Keep
   behavior identical.

3. **Update the shim** — if the old file becomes a re-export shim, add the
   `from .new_module import *` line. If not, update every caller.

4. **Run the batch's test scope** (from the plan's test strategy for that
   batch):
   ```bash
   .venv/bin/python manage.py test <batch-specific-tests> \
     --settings=app.settings_test_sqlite -v 2
   ```

5. **Run the characterization tests** from Phase 2.1 — they must still pass:
   ```bash
   .venv/bin/python manage.py test tests.test_<spec-id>_characterization \
     --settings=app.settings_test_sqlite -v 2
   ```

6. **If any test fails, stop.** Do not move to the next step. Fix the batch
   or revert it. Do not accumulate broken state across batches.

7. **Commit the batch** with a `[spec-id:batch-N]` prefix:
   ```
   [async-tasks:batch-1] Extract discovery tasks to tasks_discovery.py

   Moved discover_sitemaps_task, bulk_crawl_sitemaps_task,
   bulk_crawl_sitemap_products_task, bulk_extract_urls_task out of
   core/tasks.py into core/tasks_discovery.py. core/tasks.py continues
   to re-export them via a new `from .tasks_discovery import *` line.

   Marks spec:async-tasks::IM-1 as [x].

   Tests: tests_agentic_discovery, tests_run_discovery_limits,
   tests_async_tasks_characterization — all pass.
   ```

## 5.3 Two-commit discipline for bug fixes surfaced mid-refactor

If Phase 5 surfaces a P1 finding the user approved for "immediate fix commit"
at Phase 4, it gets its own commit AFTER the current batch lands cleanly.
Never bundle:

- Refactor commit: `[async-tasks:batch-3] Extract extraction tasks`
- Fix commit: `Fix AttributeError in run_visual_extraction_task — regression test added`

Each commit's test suite must be green independently. If the fix commit fails
tests, revert it, not the batch.

## 5.3.5 Micro-fix swarm — parallel remediation of mechanical fixes (R19)

When findings.md contains **5+ instances of the same mechanical fix**
(typically convention violations: bare `.delay()`, bare `int()` on request
data, `get_or_create(site=...)` instead of `ensure_for_site`), do
NOT fix them sequentially. The orchestrator burns context linearly, and
most of the fixes are independent. Dispatch a parallel sub-agent swarm
instead.

**Trigger:** any finding cluster (same `convention-violated` value) with
5+ call sites, confirmed by `python3 scripts/specs.py violations <spec-id>`
(R13).

**Input:** the violation list, grouped by target file.
`scripts/specs.py violations` emits JSON in this shape so it can drive
dispatch directly:

```json
{
  "AR-2": {
    "canonical": "TaskDispatchService.safe_dispatch",
    "anti_pattern": "\\.delay\\(|\\.apply_async\\(",
    "by_file": {
      "core/views_crawling.py": [
        {"line": 893, "code": "crawl_site_task.delay(site_id)"},
        {"line": 1023, "code": "..."}
      ],
      "core/views_ptid.py": [...]
    }
  }
}
```

**Dispatch pattern — one general-purpose sub-agent per target file, in
parallel** (one message, N tool calls):

**CRITICAL: Sub-agents must NOT stage or commit.** Parallel agents share a
single git index. If Agent A stages file A and Agent B stages file B, Agent
A's commit will include both files — producing wrong commits and potential
data loss. Sub-agents only edit files and report back; the orchestrator
handles all git operations serially.

See `agents/micro-fix-scout.md` for the full scout brief. Key guardrails:

- Sub-agents are scoped to a SINGLE file; they must not touch anything else.
- Sub-agents MUST run `.venv/bin/python` and the verification suite you hand
  them, not a broader one.
- Sub-agents must NOT run `git add`, `git commit`, `git stash`, `git checkout`,
  or any write-side git operation.
- If tests fail inside a sub-agent, that sub-agent reverts its own edits to
  the file and returns a failure summary — it does not escalate mid-stream.

**Verification command per file.** The dispatch tuple includes a per-file
`verification_cmd`. Cheap defaults:

- Views files → `tests.test_data_export tests.test_site_capabilities` + any
  test matching the view name.
- Service files → tests for direct callers of the service.
- Task files → `tests.test_agentic_discovery tests.test_product_downloads`
  + the task's test module if one exists.

**Mandatory pre-dispatch coverage check (R36).** For every `<file,
verification_cmd>` tuple, the orchestrator verifies BEFORE dispatch that
at least one test module in `verification_cmd` actually exercises the
target file. Batch-level green can otherwise hide a file whose tests
never ran at all — a false "all pass" for unedited code paths.

```bash
# For target file core/views_crawling.py + suite tests.test_data_export:
grep -l "from core\.views_crawling\|import views_crawling\|patch(['\"]core\.views_crawling" \
  tests/test_data_export.py tests/test_site_capabilities.py
```

The check must find at least one reference (import, `from ... import`,
or `patch("core.<module>")`). If the grep returns empty:

- Add a test module to `verification_cmd` that does reference the file
  (look for any `tests/test_<view-name>*.py` or write a one-test
  characterization module first).
- If no relevant tests exist, that file is NOT a micro-fix candidate
  — escalate to the orchestrator as a P1 finding so a proper
  regression test is written before the mechanical edit.
- Never dispatch a sub-agent with a `verification_cmd` that does not
  touch its target file.

**Orchestrator responsibilities after dispatch (serial git operations):**

1. Wait for all sub-agents to return. Collect per-file results (pass/fail
   + summary).
2. For each successful file, commit **one file at a time using
   `git commit --only <file>`**, NOT `git add <file>` followed by
   `git commit`. A bare `git add` + `git commit` picks up anything
   else already staged (a partially-staged unrelated edit, a file
   another sub-agent staged before this one if the discipline slips),
   producing mixed commits. `git commit --only <file>` ignores the
   index and commits only the specified path:
   ```bash
   git commit --only <file> -m "[<spec-id>:convention] Migrate <file> to <canonical-helper>

   <N> sites migrated: lines <list>. AR-<id> (<canonical>) enforcement.
   Tests: <suite names> — all pass."
   ```

   Before committing, run `git diff --cached --stat` — if it shows
   any file other than `<file>`, reset and investigate. Cross-
   contamination from a parallel sub-agent that ignored the
   "no staging" rule must never land in a commit.
3. Run the **full baseline verification suite** once all commits are in:
   ```bash
   .venv/bin/python manage.py test tests.test_site_capabilities tests.test_hydration_detector \
     --settings=app.settings_test_sqlite -v 2
   ```
4. If any sub-agent returned an error, review the partial state. Either
   (a) hand-fix the remaining file and add a commit, or (b) revert that
   sub-agent's edits and escalate.
5. Re-run `python3 scripts/specs.py violations <spec-id>` and confirm the
   violation count dropped to zero (or the deferred set, see 5.4).

**Why a swarm vs sequential:** 27 violations across 12 files → 12 parallel
edits in roughly the time of 1-2 sequential fixes, followed by 12 serial
commits from the orchestrator. Orchestrator context stays lean because each
sub-agent runs in its own context. The pattern only works when the fixes
are genuinely mechanical — if a fix needs judgment (e.g., restructuring
error handling around the call), it goes back to the orchestrator as a
P1 finding.

## 5.4 Convention enforcement — refactor + adopt in one run (R20)

**Architectural shift from the original skill charter.** `/refactor-subsystem`
used to be strictly behavior-preserving: extract, re-export, characterize,
verify. The shakedown found that `safe_dispatch` — one of the spec's
load-bearing AR items — had ~55% compliance across the repo. Leaving 45%
of call sites broken after a refactor whose whole point is to cement the
convention makes the refactor ceremonial. So convention enforcement is
now a first-class step of the refactor, guarded by a threshold.

**Scope restriction.** Convention enforcement is limited to files within
the spec's `code_roots` by default. `scripts/specs.py violations` greps the
whole repo, but the micro-fix swarm must only dispatch fixes for files
listed in `code_roots`. Violations outside `code_roots` are reported but
**not fixed** unless the human explicitly approves whole-repo enforcement
at Phase 4 sign-off (add `Approved scope: repo-wide convention enforcement`
to the sign-off block).

**Run at Phase 5 start**, right after Phase 4 sign-off and before the first
batch:

```bash
# violations writes to stdout — redirect to the phase-5 file yourself.
python3 scripts/specs.py violations <spec-id> --json \
  > reports/refactor/<spec-id>/phase-5-violations.json
```

The JSON shape is `{"spec": <id>, "items": [{"item_id", "canonical",
"anti_pattern", "compliant_count", "violating_count", "compliance_pct",
"violations": [{"file", "line", "text"}]}]}`. Filter to `code_roots`
files only (unless whole-repo enforcement was approved):

```python
# Filter violations to code_roots scope
code_roots = spec["code_roots"]  # e.g., ["core/views_crawling.py", "core/services/crawl_service.py"]

def _in_scope(path: str) -> bool:
    for root in code_roots:
        prefix = root.rstrip("/")
        if prefix.endswith(".py"):
            if path == prefix:
                return True
        elif path == prefix or path.startswith(prefix + "/"):
            return True
    return False

for item in violations_json["items"]:
    item["violations"] = [v for v in item["violations"] if _in_scope(v["file"])]
    item["violating_count"] = len(item["violations"])
```

For each spec item tagged with `items.<ID>.anti_pattern` in the spec
frontmatter, decide how to enforce:

| Violation count | Decision | Execution |
|---|---|---|
| 0 | No action | Already compliant. Note in findings.md and move on. |
| 1–4 | **Inline fix** in this refactor | Fix sequentially in the orchestrator. Not worth swarm overhead. |
| 5–10 | **Inline fix** in this refactor | Use Phase 5.3.5 micro-fix swarm (parallel sub-agents). |
| 11+ | **Separate follow-up ledger entry** | Create a dedicated ledger `split_queued` entry, document the full violation list, and mark the refactor as "partial enforcement" in findings.md. |

The 10-violation threshold is a heuristic — err on the side of inline fix
if the violations are mechanical and in a small number of files. Err on
the side of follow-up if fixes need judgment or span hot files the main
worktree is actively editing.

**Per-convention decision loop:**

```python
# Pseudo-code for the decision this phase runs
for item_id, violations in violations_json.items():
    canonical = violations["canonical"]
    count = sum(len(v) for v in violations["by_file"].values())

    if count == 0:
        record_compliant(item_id, canonical)
        continue

    if count <= 10:
        dispatch_micro_fix_swarm(item_id, canonical, violations["by_file"])
        record_inline_fixed(item_id, canonical, count)
    else:
        create_ledger_entry(
            decision="split_queued",
            rationale=f"AR-{item_id} convention enforcement deferred: {count} violations",
            files=list(violations["by_file"].keys()),
        )
        record_partial_enforcement(item_id, canonical, count)
```

**After the loop runs**, update
`reports/refactor/<spec-id>/findings.md`'s Convention Adoption table with
the post-fix numbers so the final state is measurable. Re-run
`violations <spec-id>` to confirm the new compliance rates.

**Escape hatch — `--enforce-inline` flag.** When the refactor author is
confident the violations are mechanical regardless of count, pass
`--enforce-inline` to pre-commit to the inline-fix branch for all
violations. This bypasses the threshold and forces 5.3.5 dispatch for
every tagged convention. Use sparingly — over-eager enforcement can
bloat the refactor with unrelated commits.

## 5.5 Findings as ledger entries

For P2 findings the user approved for `monitor` status at Phase 4, record
them in the ledger during Phase 5 (not at the end — the ledger is live
state, not a checkpoint):

```bash
python3 scripts/ledger.py update <file> \
  --decision monitor \
  --rationale "P2 finding from <spec-id> refactor: <summary>" \
  --next-review <+180d>
```

## 5.6 Caller-update wave (decomposition mode)

**Skip this step in standard mode.** When decomposition mode splits a file
that is imported widely, the re-export shim handles backward compatibility
for public symbols. But callers that reach into private helpers (prefixed
with `_`) or construct types defined in the original file may need direct
updates.

This gets its own wave — a separate batch with its own test verification —
after all domain-split batches have landed:

1. **Enumerate all callers:** `grep -r "from core.<original> import" --include="*.py"`
   across the whole repo.
2. **Verify shim coverage:** for each caller, confirm the import resolves
   via the re-export shim.
3. **Fix private-symbol imports:** callers that import `_private_helper`
   need updating to point to the new domain module directly (private
   symbols are not re-exported via `import *`). Alternatively, add explicit
   re-exports in the shim's `__init__.py` for widely-used private symbols.
4. **Fix mock patching in tests (R31):** `@patch('core.tasks.some_func')`
   has two behaviors after a split:
   - **`.delay()` patches work through the shim** —
     `@patch('core.tasks.some_task.delay')` patches the task object itself,
     which is the same object in both the shim and the domain module.
     These need no changes.
   - **Synchronous call patches must target the actual module** —
     `@patch('core.tasks.some_func')` patches the shim's reference, but a
     caller in `tasks_export.py` that calls `some_func()` synchronously
     uses its own module's local reference, bypassing the mock. Fix:
     `@patch('core.tasks_export.some_func')`. Grep for
     `@patch.*core\.<original>\.` across all test files and classify
     each as `.delay()` (safe) or synchronous (needs updating).
5. **Run the full test suite** after the wave — this is a high-blast-radius
   step.
6. **Commit:** `[<spec-id>:caller-fixup] Update imports for <original> split`.

If no callers import private symbols and no tests use synchronous mock
patches, this wave is a no-op and can be skipped.
