Based on the `/fix-workflow` skill files:

## Tests to run (Step 3)

**Source file:** `knowledge/verification.md` lines 30–50 (Verification test matrix section)

The matrix table in `verification.md` is unfilled with a host-adapter comment. Per the **Absence fallback** (mandatory when the table is unfilled):
- Run the **narrowest meaningful suite for the touched files** — check `docs/testing.md` or project conventions to identify the test module for `core/services/parsing.py`
- State in the plan that the matrix was absent and name which suite was chosen
- If unsure, run the superset for the service subsystem

Since this is a pure-duplication refactor (§2a shape), after tests pass I must also run the **jscpd re-scan** (lines 67–77):
```bash
.venv/bin/python scripts/lint/run_jscpd.py core/services \
  --output reports/duplication/rescan --offline-ok
```
Then diff clone counts against `reports/duplication/latest/jscpd/` to confirm fewer clones post-refactor.

## Commit conventions

**Source file:** `knowledge/verification.md` lines 52–65 (Commit verbs & message template)

Template:
```
<Verb> <what>: <cluster name or target>

- Behavior preserved (R1); a latent bug left in place is named:
  "Behavior preserved, including <bug>".
- Reordered side effects name the new order and the crash
  implication (R8).
```

**Verbs:** `Dedup` / `Delete` / `Fix` / `Promote` / `Migrate`

For this pure-duplication extract-helper, the verb is **`Dedup`**. Example:
```
Dedup parse_helper extraction: cluster:P0-3

- Behavior preserved (R1).
```
