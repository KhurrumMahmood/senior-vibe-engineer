# Verification & commit reference

Verification machinery `SKILL.md` delegates here: worktree +
cleanliness guard commands, the test matrix, commit verbs + message
template, and the jscpd re-scan command. Host-specific content is
marked with a host-adapter slot, never guessed.

## Worktree & cleanliness guard

Run wherever invoked; confirm the root first:

```bash
git rev-parse --show-toplevel
```

Target files must not carry unrelated uncommitted edits:

```bash
git status --porcelain -- <target files>
```

Abort conditions:

- Any target file shows edits you did not make → abort and report
  the dirty files. Do not stash, discard, or commit around them.
- `git status` shows conflicting edits to the same files from
  another worktree (concurrency collision) → abort. Do not rebase
  or merge.

## Verification test matrix

Baseline + per-subsystem rows. The matrix is host-specific.

<!-- host-adapter: fill this table for the host project — one
baseline row (fast cross-cutting suite) plus one row per subsystem
mapping source paths to test modules, including any test-settings
flag. Birth-host example: baseline = tests.test_site_capabilities +
tests.test_hydration_detector under --settings=app.settings_test_sqlite. -->

| Subsystem / path | Test modules | Notes |
|---|---|---|
| _(unfilled — apply the absence fallback below)_ | | |

**Absence fallback (mandatory when the table is unfilled):** the
matrix does not exist on this host yet. Do NOT invent rows or report
"the matrix says". Run the narrowest meaningful suite for the
touched files (the host's `docs/testing.md` or project adapter names
it), and state in the execution plan that the matrix was absent and
which suite you chose. If unsure, run the superset for the file's
subsystem.

## Commit verbs & message template

Verbs: `Dedup` / `Delete` / `Fix` / `Promote` / `Migrate`. The
commit title starts with the verb (the §2c and §2d stop conditions
check this).

```
<Verb> <what>: <cluster name or target>

- Behavior preserved (R1); a latent bug left in place is named:
  "Behavior preserved, including <bug>".
- Reordered side effects name the new order and the crash
  implication (R8).
```

## Post-cluster jscpd re-scan (dedup shapes — R14)

```bash
.venv/bin/python scripts/lint/run_jscpd.py <touched-subdir> \
  --output reports/duplication/rescan --offline-ok
```

Diff the clone count against `reports/duplication/latest/jscpd/`.
Fewer clones = the refactor landed. Same-or-more = it didn't;
investigate before closing. Record the before/after counts in the
cluster entry's Tests section so a skipped re-scan is visible.
