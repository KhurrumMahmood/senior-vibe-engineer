# find-semantic-duplication — false positives

Read during **Compare** (Step 3) and **Confirm** (Step 5). Mandatory before a
candidate can survive into `scout/<finding_id>.json`, `ranked.json`, and the
final `triage.md`.

Semantic duplication is a higher-variance signal than syntactic duplication. Many things *feel* like duplicates at the summary level but aren't. These are the recurring traps.

## The seven rejection classes

Apply in order. If any matches, reject the candidate — do not proceed to the capability matrix.

### 1. Caller-callee, not duplication

If function A calls function B inside its body, that's decomposition — B is a helper of A, not a parallel implementation. Check with `grep` before scoring.

```
Grep pattern: \b<callee_name>\s*\(    # inside caller's source
```

Note: transitive calls (A → X → B) are not decomposition; only direct calls count as caller-callee. A workflow can still have semantically-overlapping steps along the way.

### 2. Framework-mandated pattern

The sibling `knowledge/` lists Django/DRF framework patterns. Methods repeating across class-based views, DRF viewsets, or management commands because the framework dispatches by method name are **not** duplication. If both sides of the candidate are named `get` / `post` / `handle` / `form_valid` / etc., reject.

### 3. Different abstraction levels

One function is a thin wrapper around the other. The wrapper adds logging, metrics, error translation, or a simpler API — it doesn't re-implement the core logic.

Signals: short size (<20 lines), body is mostly a single call to the other, returns what the other returns after a trivial transform.

### 4. Test fixture or mock

One implementation lives under `tests/test_*`, `core/tests/`, `testing/`, or mentions `Mock`, `MagicMock`, `FakeClient`, `stub_`, `fixture_` in its name. Keep as documentation; do not flag as duplication.

### 5. Bodies are >70% token-similar

This belongs in `/find-duplication`, not here. This skill exists for **semantically** equivalent code that looks textually different. If a quick tokenized comparison shows heavy overlap, reject with a note that find-duplication should catch it (it may already — check `reports/duplication/latest/`).

Cheap check: if both bodies share >70% of their identifier tokens (variable
names, function calls), they're likely lexical duplicates. If
`reports/duplication/latest/triage.md` exists, cite the overlapping sibling
finding; if it does not exist, record that the sibling report was absent and
use the direct token-overlap check as the evidence.

### 6. Converging workflows with different end products

Two workflows that share a common sub-workflow but produce genuinely different outputs are **not** duplicates of each other; they're users of the shared infrastructure. Example: "export to export CSV" and "export to pivot Excel" both go through `build_product_data_dataframe` — the shared helper is correctly factored; the wrappers do different things.

Signal: the divergence is at the head (entry) or tail (output) of the workflow, and the middle is genuinely shared.

### 7. Load-bearing divergence that requires two implementations

Two functions with overlapping purpose may legitimately coexist because the **policy** differs: one raises on invalid input, the other clamps; one retries, the other fails fast; one writes through, the other batches. If merging would require either dropping a behavior or adding a flag that couples the callers, document the divergence in the capability matrix but mark the finding as "keep separate — load-bearing divergence."

This is the hardest judgment call. Prefer "keep separate" when in doubt — the triage is supposed to be conservative.

## Structural-level false positives

For **fragmented-concern** findings (single-home violations from artifact inventory), additional rejection classes apply:

### 8. Unit vs integration split (intentional)

`tests/test_X.py` and `testing/test_X.py` covering the same feature are **not** duplication — they're different test levels by design. See `knowledge/` "split-by-design."

### 9. Synchronous vs async variants

If the two homes are a sync service and an async agent-script version (e.g., in-process `FieldDiscoveryPipelineService` vs out-of-process agent bridge), they exist because the isolation requirements differ. Not duplication.

### 10. Staged/legacy migrations

If one home is marked deprecated (comment, docstring, or `# TODO: remove after X`), it's a migration in progress — list in the report but call it a **migration-in-progress** finding, not a semantic duplication. The remediation is "finish the migration," not "consolidate."

## How rejections are recorded

Confirm-stage scout writes:

```json
{
  "finding_id": "SC-1",
  "investigation_status": "false_positive",
  "reason_code": "caller_callee | framework_pattern | different_abstraction | test_mock | token_similar_belongs_in_find_duplication | converging_different_products | load_bearing_divergence | unit_vs_integration_split | sync_vs_async_variant | migration_in_progress",
  "notes": "2-3 sentence explanation citing file:line"
}
```

The report renders these in a **Rejected candidates** section so the human reader can sanity-check the rejection bar.

## When to escalate rather than reject

If the scout can't decide between "false positive" and "real finding" within 15 minutes of reading, write `investigation_status: "uncertain"` with notes. The orchestrator treats these as a separate bucket in the triage — they need human eyes, not a forced classification.

Better to flag uncertainty than to guess.
