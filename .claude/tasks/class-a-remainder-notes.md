# Class-A remainder: remove baked host paths from two skill scripts

Goal: skills carry **no hardcoded host-project paths**. Two scripts still
baked `core/` into matching logic / lookups; those branches were dead on any
non-`core` repo and silently broke the skill there. Fixed both to be
location-independent (Django-suffix convention for inspect.py; ignore-first
scope walk for collect.py). Touched ONLY these two files. Changes left
unstaged for review.

---

## File 1 — `.claude/skills/propose-folder-reorganization/scripts/inspect.py`

### What changed
1. **`FRAMEWORK_CONVENTION_PARENTS` (exact-match set, `core/`-only) →
   `FRAMEWORK_CONVENTION_SUFFIXES` (suffix tuple) + `_is_framework_convention()`.**
   A parent is now a framework-convention dir if it **equals or ends with**
   `management/commands`, `management`, `migrations`, or `templatetags` — for
   ANY app root (`core/`, `app/`, `src/x/`, …). This is the sanctioned "assume
   the Django convention, not a specific directory" case. Ordering puts
   `management/commands` before `management` (harmless: both return True; the
   loop just short-circuits).
2. **`SCRATCH_CODE_PREFIXES` (`startswith`, `core/.../_experiments/` literal) →
   `SCRATCH_CODE_SEGMENTS` (segment tuple) + `_is_scratch()`.** Now a **path
   segment** match anywhere in the parent path. Dropped the `core/` literal;
   kept the generic names (sandbox, scratch, experiments, tmp, _archive) and
   added `_experiments` so the original experiments folder still trips
   regardless of app root. Segment match (not substring) so `experimental_helpers`
   does NOT false-positive on `experiments`.
3. **`_defer_signals()`** rewired from the two removed collections to
   `_is_scratch()` / `_is_framework_convention()`. Behavior preserved.
4. **`_matched_tests()`**: the hardcoded `core = project_root / "core"` branch
   (find tests piled at the `core/` root for a `core/*` cluster) → derive the
   parent's **own top-level segment** (`parent.relative_to(project_root).parts[0]`)
   and look there. So a `<app>/views/<prefix>_*` cluster finds `<app>/tests_<prefix>_*.py`
   for any `<app>`, and the original `core/views/...` → `core/...` case still works.
5. **Comments / docstrings / argparse help** genericized: `core/views` → `<package>/views`,
   the "99 tests at core/ root" complaint → neutral "many tests piled at the
   repo root", absolute-import example `from core.views...` → `from pkg.views...`.
   Remaining `core/` mentions are only inside new comments where they appear as
   ONE example among `app/`, `src/x/` illustrating the location-independent
   behavior — not baked paths.

### Why
Exact-string `core/management/commands` and `startswith("core/...")` are dead on
`app/`-rooted repos: the framework-convention / scratch defer signals never fire,
so the skill would happily propose collapsing a Django command dir or an
experiments folder it should defer on. Suffix/segment matching encodes the
*convention* instead of the *directory*.

### Callers accounted for
- `_defer_signals` was the only consumer of both removed collections (grep for
  `SCRATCH_CODE_PREFIXES` / `FRAMEWORK_CONVENTION_PARENTS` → RC=1, no refs left).
- `_matched_tests` is called from `inspect()`; its return shape is unchanged
  (same dict keys), so downstream JSON is unaffected.
- No skill markdown references the renamed constants (grep RC=1).

---

## File 2 — `.claude/skills/extract-enum/scripts/collect.py`

### What changed
1. **Added the scope import idiom** (matches the find-duplication exemplar):
   `sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))` +
   `import scope as _scope  # noqa: E402`.
2. **`_find_model_declaration_file()`** rewritten: was a `core/models` →
   `core/` rglob with a regex `^\s*class X\b`. Now an **ignore-first scope
   walk** — iterates `_scope.iter_paths(project_root, _scope.Scope(),
   extensions=frozenset({".py"}))` (already sorted) and returns the first file
   whose text contains `f"class {model_class}("`, else `None`. Dropped the
   `import re` (substring match is sufficient and matches the exemplar's
   `class X(` needle convention).
3. **Docstrings / usage example / sample JSON / help / fallback comment**
   genericized: `core/models/crawl_jobs.py` → `<pkg>/models/crawl_jobs.py`,
   `core/views|tasks/crawling.py` → `<pkg>/views|tasks/...`, "Fall back to
   searching core/models/" → "searching the in-scope tree".

### Why
`core/models` / `core/` rglob finds nothing on an `app/`- or `src/`-rooted
repo, so the caller-site → declaration fallback silently failed there
(returning None and erroring out as "no Model subclass declares the field").
The scope walk uses the host-authored ignore-first universe instead — and as a
bonus correctly skips `migrations/` (the builtin scope skip), which the old
`core/` rglob also nominally skipped via `_DEFAULT_SKIP_DIRS`.

### Caller accounted for
- Sole caller is in `main()` (the `if decl is None and model_class:` fallback,
  ~line 785). It only checks `if alt_path is not None:` and otherwise proceeds
  to the existing `if decl is None:` error path — so returning `None` when not
  found is handled exactly as before. Confirmed by reading the caller.

### Note on the `_scope.Scope()` default
Passing an empty `Scope()` (no roots, no ignore) means the lookup obeys only the
builtin skip floor + any repo-wide `ignore.md`, NOT a per-skill
`extract-enum-scope.md` `## Roots` narrowing. That is intentional and correct
here: model declarations can legitimately live outside a skill's analysis
narrowing, and the old code also ignored any such config. If a host ever wants
to constrain this lookup, the right knob would be `load_scope(project_root,
"extract-enum")` — out of scope for this change.

---

## Verification

All commands run with `python3` (stdlib-only; no venv/Django in ES2).
`cwd` for runs: repo root `~/Projects/engineering-skills-2`.

### 1. Parse checks
```
python3 -c "import ast; ast.parse(open('.../inspect.py').read())"   # inspect.py parses OK
python3 -c "import ast; ast.parse(open('.../collect.py').read())"   # collect.py parses OK
```

### 2. Synthetic unit harness (`/tmp/es2_verify.py`)
Loads both modules via `importlib.util.spec_from_file_location` and exercises
the changed functions. **30/30 PASS, exit 0.** Highlights:

inspect.py — framework-convention:
- PASS app/management/commands IS framework-convention   ← core/ assumption GONE
- PASS src/myapp/migrations IS framework-convention
- PASS app/templatetags / billing/management IS framework-convention
- PASS core/management/commands|migrations|templatetags|management STILL framework-convention  ← preserved
- PASS app/views / core/services NOT framework-convention (negatives)
- PASS app/commands NOT framework-convention (suffix guard: bare `commands` ≠ `management/commands`)

inspect.py — scratch:
- PASS app/management/commands/_experiments IS scratch    ← core/ literal GONE
- PASS core/management/commands/_experiments STILL scratch (original)
- PASS experiments/foo, src/sandbox/x, app/scratch, tmp, _archive/old IS scratch
- PASS app/views NOT scratch; app/experimental_helpers NOT scratch (segment guard, not substring)

inspect.py — `_defer_signals` integration:
- PASS flags framework_convention for app/management/commands
- PASS flags scratch_code for app/scratch
- PASS still flags framework_convention for core/management/commands (preserved)
- PASS clean (`== []`) for app/views

collect.py — `_find_model_declaration_file` (tmp dirs):
- PASS model under app/models/foo.py IS located          ← core/ assumption GONE
- PASS model under src/pkg/domain/order.py IS located
- PASS model under core/models/crawl_jobs.py STILL located (preserved)
- PASS absent model returns None                          ← caller handles same as before
- PASS class only in migrations is NOT located (scope prunes migrations)
- PASS duplicate class resolves to first sorted file (aaa.py — deterministic)

Run:
```
python3 /tmp/es2_verify.py    # FINAL_EXIT=0, RESULT: ALL CHECKS PASSED
```

### 3. End-to-end CLI test of collect.py `main()` (app/ layout, no core/)
Subprocess invocation through the real argparse boundary, findings.json whose
`file` is a CALLER site (`app/services/crawling.py`) + a
`recommendation_hint_symbol`, forcing the `_find_model_declaration_file`
fallback. The caller constructs the model locally so `job.status` is
attributable to CrawlJob (the collector's model_class filter requires it):
```
stderr: [collect_extract_enum] note: 'app/services/crawling.py' is a caller
        site; resolved CrawlJob.status declaration in app/models/crawl_jobs.py
        [collect_extract_enum] wrote .../targets.json: CrawlJob.status —
        3 literals (0 case-variants) across 1 files (2 comparisons, 1 assignments)
exit:   0
field_file:  app/models/crawl_jobs.py
model_class: CrawlJob
literals:    ['done', 'pending', 'running']
E2E_RESULT: PASS   (E2E_FINAL_EXIT=0)
```
(First pass of this E2E used an unattributable `job` var in the fixture and
returned exit 1 at "zero comparisons" — a bug in the *test*, not the code; the
declaration-resolution note already proved the genericized lookup worked. Fixed
the fixture; re-ran green.)

### 4. Existing ES2 test suite for these skills
**None present.** `.claude/tests/` contains only `ideas/` (run_harness.py +
fixtures). `grep -rln 'propose-folder-reorganization|extract-enum' .claude/tests`
→ no matches. No skill-local `*test*` files for either skill. Nothing to run.

### 5. Residual `core` scan
```
grep -n '\bcore\b|core/' collect.py   → RC=1 (none)
grep -n 'core/'           inspect.py  → only the 2 illustrative comment lines
                                         (core/ shown alongside app/, src/x/)
```

---

## Uncertainty / judgment calls
- **Illustrative `core/` in inspect.py comments kept.** Two comment lines name
  `core/` as one example among `app/`/`src/x/` to explain the location-independent
  behavior. Not a baked path; matches the exemplar's framing. Remove if you'd
  rather have zero `core` tokens.
- **`_matched_tests` app-root branch** generalizes the old `core/`-root branch
  to "the parent's own top-level segment". For a parent already AT the repo
  root, `parent_rel_parts` has len ≤ 1 so the branch no-ops (the repo-root
  loop above already covers it) — no double-add.
- **`_scope.Scope()` (not `load_scope`)** for the model lookup — see "Note on
  the `_scope.Scope()` default" above. Intentional; flag if you'd prefer the
  per-skill descriptor to constrain it.
