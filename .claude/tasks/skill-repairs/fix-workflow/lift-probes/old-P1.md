Based on my reading of the skill files, here's exactly what Step 3 and Step 4 mandate:

## Step 3: Tests to Run

**Source:** `fix-shapes.md` §2a, step 5 (line 66)
> "Run the targeted test suite (see `knowledge/` test matrix) before committing"

**Which tests:** Per `SKILL.md` Step 3 (lines 199-200):
> "The matrix lives in `knowledge/` (baseline + per-subsystem rows). If unsure, run the superset for the file's subsystem"

Since the file is `core/services/parsing.py` (services/parsing subsystem), I will run:

1. **Baseline tests** (shown in `fix-shapes.md` §2c, lines 183-186):
   ```bash
   .venv/bin/python manage.py test \
     tests.test_site_capabilities tests.test_hydration_detector \
     tests.test_parsing \
     --settings=app.settings_test_sqlite -v 2
   ```

2. **Deletion test** (per §2a, step 1 and interface-depth guidance): verify that the extracted helper passes inline deletion testing — i.e., removing it would require changes at all calling sites.

**Stop condition** (from §2a, line 73): "Targeted test suite passes"

---

## Step 4: Commit Message Conventions

**Source:** `SKILL.md` line 219-221
> "Verb conventions (`Dedup` / `Delete` / `Fix` / `Promote` / `Migrate`) and the commit-message template live in `knowledge/`"

**For this cluster (pure-duplication extract-helper):**
- **Verb:** `Dedup` (used for extract-helper shape 2a clusters)
- **Template format:** (shown implicitly in learnings.md R8 and R1):
  ```
  Dedup: <brief description of the extracted helper>

  <details about what was duplicated, why extraction is safe, any behavioral notes>
  ```

**Stop condition** (from §2a, line 78): "`git diff --stat` shows only the files you planned to touch"

---

Would you like me to proceed with Step 3 verification now, or do you need clarification on which specific test modules exist in your project for the parsing subsystem?
