# parents[4] sweep — de-bake kit root from 12 skill scripts

**Date:** 2026-06-12 · **Pattern:** which-cleanup fix (`which-cleanup-fix.md`) applied to
the `parents4-leak-audit.md` list: `parents[4]` kept ONLY for sys.path/kit resources and
renamed `KIT_ROOT`; every target-project surface anchors on `--project-root`, default
`resolve_project_root()` (shared helper in `_common/diff_resolution.py`: explicit flag >
git toplevel of cwd > cwd). Not committed, per instructions.

## Per-script results

Parity = cheapest read-only invocation from the ES root, before vs after (byte-identical
unless noted). Foreign smoke = run with cwd `/tmp/host-a-dogfood-clone` (disposable); pass =
graceful, anchored in host-a, zero ES-repo paths in output.

| script | leak surfaces fixed | parity (ES root) | foreign smoke (/tmp/host-a-dogfood-clone) |
|---|---|---|---|
| track-idea/track.py | `LEDGER` bake-in → `--project-root` (parent parser on all 5 subcommands); `log_event` artifact follows | `list` byte-identical | `list` → "(no ideas captured yet)" — host-a's (absent) ledger, not ES's 100+ ideas |
| brainstorm-ideas/brainstorm.py | ledger bake-in (dedup + write) → `--project-root` | dup-slug `--dry-run --json` byte-identical (`skipped_duplicate` proves ES-ledger read) | same batch → `written` (no dup) — deduped against host-a's empty ledger |
| mature-existing-ideas/mature.py | ledger bake-in → `--project-root`; `ledger` threaded through `mature_one`/`_append_*` | nonexistent-slug error path byte-identical (read-only: load_ledger + project, no write; resolution logic shared with track.py parity) | real ES slug → "no intake" exit 1 — reads host-a's ledger |
| extract-existing-ideas/extract.py | ledger dedup, `DEFAULT_OUT`, `relative_to` display crash → `--project-root`; out default `<project-root>/.claude/ideas/extract-candidates.json`; display falls back past project root | stdout + out-file byte-identical (only the differing /tmp out filenames) | `extract.py documentation` → 0 candidates, default out landed in host-a `.claude/ideas/` with host-a-relative label |
| query-patterns/query.py | `PATTERNS_DIR` bake-in, `relative_to(REPO_ROOT)` label → `--project-root`; `_common` added to sys.path | `--json` byte-identical | "No patterns recorded yet" — host-a's (absent) library |
| find-orphaned-ideas/find.py | 6 surfaces: ledger, todo-tuning, TODO walk, ai-docs/plans, find-dormant reports, importance map → one `--project-root` threaded through all detectors + `apply_stale` | `--all --json` identical modulo `now` timestamp | `--stale --harvest --stale-plans --attention-gap --json` → empty findings, `attention_gap: no_map`, zero ES paths |
| rename-concept/assess.py | git grep cwd, glossary, guard-lint dir, divergence-scan cwd → `--project-root` (delegated scan gets the flag + cwd); detector script path stays `KIT_ROOT` | `assess.py OldWidget NewWidget` byte-identical | graceful: 0 live files in host-a, `<no concepts.yaml>` (host-a's), bands UNAVAILABLE, INCONCLUSIVE; zero ES strings |
| find-concept-divergence/scan.py | scan-target anchor, glossary default, **`relative_to(REPO)` crash for outside files** → `--project-root`; new `_rel()` falls back to absolute path | findings.jsonl + report.md byte-identical | missing-glossary exit names `/private/tmp/host-a-dogfood-clone/...`, not ES; positive-path + outside-file cases covered by tests |
| find-incomplete-sweep/scan.py | relative `--paths` anchor, blame-fallback cwd, `rel()` labels → `--project-root`; **resolved root now recorded in manifest.json** | `--paths scripts --no-gate` stdout + gated findings.md byte-identical; manifest diff = the new `project_root` key only (by design) | scanned host-a's own `scripts/` (stragglers like `scripts/chunk_file.py`), manifest root `/private/tmp/host-a-dogfood-clone`, zero ES paths |
| find-incomplete-sweep/scout.py | manifest-path anchor (`parents[3]`) → precedence: `--project-root` flag > manifest's recorded `project_root` > cwd toplevel; threads root into `read_window` + `collect_callsites` | synthetic gated-in fixture: scout_packets.json byte-identical | empty-manifest run graceful ("nothing to scout", empty packets file) |
| propose-boundary/propose.py | telemetry log written into kit repo → `project_root / .claude/skill-use/log.jsonl` (existing `--project-root` flag, default "." kept — audit's only leak was telemetry) | inspection JSON byte-identical | telemetry appended to host-a's `.claude/skill-use/log.jsonl`; ES log size unchanged (verified) |
| find-comment-drift/detect.py | default-only: `--project-root` default kit-root → `resolve_project_root()` (matches sibling detectors) | `scripts/decisions.py` scan byte-identical (kit root == cwd toplevel from ES root) | default targets absent → "scanned 0 files" graceful; real host-a file → 1 finding with host-a-relative label |

**Stopped on: none.** All 12 scripts fixed; the kit-is-target ledger family keeps
byte-identical in-repo behavior because the cwd-toplevel default resolves to the ES root
when run from it (verified per script above).

**Adjacent fix:** `which-cleanup/scripts/smoke.py` called `coverage.check()` with the old
zero-arg signature (broken by the parallel which-cleanup fix, now commit c7fdc25) — fixed
to `coverage.check(REPO_ROOT)` (kit self-check ⇒ kit root is the project root). Smoke OK.

**Pre-existing, out of scope:** `find-contract-drift/scripts/smoke.py` fails on HEAD
(`module.detect() takes 0 positional arguments but 4 were given` — incompatibility with
`find-frontend-contract-drift.detect`'s signature; untouched since initial release).

## SKILL.md updates

`--project-root` added to the documented usage blocks + anchoring sentence: track-idea,
brainstorm-ideas, query-patterns, find-orphaned-ideas, rename-concept (also corrected the
"anchored at the repo root" prose), find-concept-divergence, find-incomplete-sweep (scan +
scout). find-comment-drift pipeline block gained the flag + default note. propose-boundary
already documents `--project-root`. mature-existing-ideas and extract-existing-ideas
SKILL.mds document no script-level flags (slash-command/inline-python level only), so no
flag block to extend.

## Tests & gates

- New: `tests/scripts/test_project_root_debaking.py` — 8 tests (helper git-toplevel
  default; track.py foreign-empty-ledger / foreign-write-no-kit-write / explicit-root-wins;
  cdiv foreign anchor+labels / missing-glossary names foreign path / outside-file no-crash
  regression; sweep manifest records foreign root). **8 passed.**
- Existing: `tests/test_find_orphaned_ideas.py` + `tests/scripts/` (incl. which-cleanup
  root tests) + taxonomy/detector-reads → **37 passed** combined run; ideas harness
  `.claude/tests/ideas/run_harness.py` → 7 pass; `tests/test_run_skill_smokes.py` 11 pass;
  `track.py --self-test` OK; import-floor smokes 43/43 OK.
- `ruff check` clean on all touched Python (one pre-existing invalid-noqa warning in
  propose.py, untouched line). `pre-commit run --files <all 22 touched>` — **all hooks
  passed**, including `skill-artifact-drift` (SKILL.md flags vs argparse).

/tmp/host-a-dogfood-clone received disposable smoke artifacts under `reports/`, `.claude/ideas/`,
`.claude/skill-use/`; nothing committed anywhere.
