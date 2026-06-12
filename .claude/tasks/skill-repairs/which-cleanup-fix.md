# /which-cleanup — de-bake REPO_ROOT (kit vs target anchoring)

**Date:** 2026-06-12 · **Bug:** run.py/coverage.py hard-anchored `REPO_ROOT = parents[4]`
(the kit's own repo) and used it for both kit imports (legitimate) and target-project
operations (bug). Foreign-repo users needed a shim. Fix follows the de-baking convention
from `which-shape/scripts/route.py`: kit root for imports only; `--project-root`
(default: git toplevel of cwd, else cwd) for everything target-facing.

## REPO_ROOT use classification

### run.py (before fix)

| Line | Use | Class | Fix |
|---|---|---|---|
| 22 | constant definition `parents[4]` | kit | renamed `KIT_ROOT` |
| 23 | sys.path: `_common/`, `scripts/` | kit | stays on `KIT_ROOT` |
| 34 | `DEFAULT_REGISTRY` `.claude/subsystems.yaml` | **target** | `project_root / ".claude/subsystems.yaml"` (post-parse) |
| 35 | `DEFAULT_REPORTS_DIR` `reports/which-cleanup` | **target** | `project_root / "reports/which-cleanup"` (post-parse) |
| 36 | `DEFAULT_SPECS_DIR` `ai-docs/specs` | **target** | `project_root / "ai-docs/specs"` (post-parse) |
| 43 | `_relativize` `relative_to(REPO_ROOT)` | **target** | takes `root: Path` param |
| 51 | `_rel` `relative_to(REPO_ROOT)` | **target** | takes `root: Path` param |
| 58 | `resolve_scope`: `root = REPO_ROOT` (all git/diff/area resolution) | **target** | takes `root: Path` param |
| 93 | path to `scripts/log_effectiveness.py` | kit | stays on `KIT_ROOT` (helper ships with kit) |
| 96 | `cwd=REPO_ROOT` for log_effectiveness | **target** | `cwd=project_root` (its relative default log path `reports/_meta/effectiveness.jsonl` anchors on cwd) |
| 135 | `(REPO_ROOT / f).exists()` deleted-path filter | **target** | `(project_root / f).exists()` |

### coverage.py (before fix)

| Line | Use | Class | Fix |
|---|---|---|---|
| 26 | constant definition `parents[4]` | kit | renamed `KIT_ROOT` |
| 27 | sys.path: `_common/`, `scripts/` | kit | stays on `KIT_ROOT` |
| 36 | `DEFAULT_REGISTRY` `.claude/subsystems.yaml` | **target** | `_registry(project_root)` |
| 37 | `EFFECTIVENESS` `reports/_meta/effectiveness.jsonl` | **target** | `_effectiveness_path(project_root)` |
| 38 | `SKILLS_DIR` `.claude/skills` | kit | stays on `KIT_ROOT` — the recommendable skill catalogue ships with the kit (matches `select_scanners.SKILLS_DIR`, also kit-anchored) |
| 83 | `resolve_since(REPO_ROOT, …)` | **target** | `resolve_since(project_root, …)` |
| 86 | `run_git_name_only(REPO_ROOT, git log …)` | **target** | `run_git_name_only(project_root, …)` |

Out of scope (kit-only uses, unchanged): `select_scanners.py` `_REPO_ROOT`
(`scripts/_lib` import + kit skill frontmatter) and `smoke.py` (sys.path only).

## Fix per file

- **`.claude/skills/_common/diff_resolution.py`** — new shared helper
  `resolve_project_root(explicit)` (no existing helper shipped anywhere in
  `_common/` or `scripts/_lib/` — verified by grep for `rev-parse`/`show-toplevel`):
  explicit `--project-root` wins; else `git -C <cwd> rev-parse --show-toplevel`;
  else cwd. Additive only — no existing consumer touched.
- **`run.py`** — `REPO_ROOT` → `KIT_ROOT` (imports only, with a comment making
  target-path use visually wrong); added `--project-root`; `--registry`/
  `--reports-dir`/`--specs-dir` defaults become `None` and resolve against
  `project_root` post-parse; `_relativize`/`_rel`/`resolve_scope` take a root
  param; effectiveness logging runs with `cwd=project_root`; deleted-path
  filter checks `project_root / f`.
- **`coverage.py`** — same rename + comment; `--project-root` on both `audit`
  and `check` subcommands; `_registry`/`_recent_coverage`/`_range_files`/
  `audit`/`check` take `project_root`; `SKILLS_DIR` deliberately stays
  kit-anchored.
- **`SKILL.md`** — Pipeline usage line gains `[--project-root DIR]`; report/log
  paths documented as `<project-root>`-relative; new paragraph documenting the
  anchoring default for both scripts.
- **`tests/scripts/test_which_cleanup_roots.py`** — new (8 tests, see below).

## Before/after parity (invoked from ES repo root, no new flag)

Captured before-fix outputs via `git stash push` of the three changed files.

- `run.py --commit b974635 --emit-plan --json --skip-effectiveness-log --now parity3`
  (38-file **large** band): stdout, `closeout.json`, `closeout.md`,
  `*.workflow.js`, and the spec stub all **byte-identical** (after normalizing
  the distinct `/tmp` output dirs passed to the two runs).
- `run.py --commit HEAD` (trivial band): stdout identical, no scan dir either side.
- `coverage.py audit --last 30 --json --now 2026-06-12T00:00:00+00:00`: **byte-identical**.
- `coverage.py check` from ES root: still OK (CI invocation unchanged — runs from repo root).

## Foreign-repo run (/tmp/host-a-dogfood-clone) — the actual bug scenario

No shim needed; kit imports resolved via `KIT_ROOT` sys.path. Key lines:

```
$ cd /tmp/host-a-dogfood-clone && …/.venv/bin/python …/which-cleanup/scripts/run.py --commit HEAD --json --skip-effectiveness-log --now foreigntest
  "resolved_paths": ["start_server.sh"],          # host-a-dogfood's HEAD, not ES history
  "report_dir": "reports/which-cleanup/scan-foreigntest",
  "subsystems": [], "unmatched": ["start_server.sh"]
$ ls /tmp/host-a-dogfood-clone/reports/which-cleanup/    → latest  scan-foreigntest   # landed in target
$ ls …/engineering-skills/reports/which-cleanup/ | grep foreigntest → (empty) # no kit-repo leak
$ cd /tmp/host-a-dogfood-clone/documentation && … run.py --commit HEAD …
  "report_dir": "reports/which-cleanup/scan-subdirtest"   # subdir run → git-toplevel anchor
$ … run.py --project-root /tmp/host-a-dogfood-clone … (cwd=ES root) → scan-explicittest in host-a-dogfood
$ cd /tmp/host-a-dogfood-clone && … coverage.py audit --last 10 --json
  range: last 10 commits · subsystems_touched: [] · gaps: 5 · unmappable: 0
$ cd /tmp/host-a-dogfood-clone && … coverage.py check → "OK — every recommendable skill resolves."
```

**Missing-registry behavior** (host-a-dogfood ships no `.claude/subsystems.yaml`):
graceful by existing design — `load_registry` raises `FileNotFoundError`, run.py
catches it and degrades to `registry = {}` (universal floor + scope band only;
files land in `unmatched`); coverage.py's `_registry()` does the same. Confirmed
live: the foreign run produced the universal-floor checklist with `subsystems: []`,
no error.

## Tests

`tests/scripts/test_which_cleanup_roots.py` (new, 8 tests): `resolve_project_root`
unit tests (explicit wins / git-toplevel from subdir / cwd fallback outside git);
run.py from a tmp foreign git repo (kit imports work, scope from foreign history,
reports land in foreign repo, no kit-repo leak, graceful no-registry); default
resolution from a subdir; explicit `--project-root` overriding cwd; coverage.py
audit from foreign repo; coverage.py check still resolving against the kit catalogue.

```
.venv/bin/python -m pytest tests/scripts/test_which_cleanup_roots.py tests/scripts/test_which_cleanup.py
→ 24 passed, 1 skipped (pre-existing conditional skip)
```

`ruff check` clean on all three changed Python files. `pre-commit run --files`
on everything touched (incl. SKILL.md + new test): all hooks passed, including
`skill-artifact-drift` (SKILL.md flags vs argparse).

Not committed, per instructions. `/tmp/host-a-dogfood-clone/reports/` received disposable
scan dirs; nothing committed there.
