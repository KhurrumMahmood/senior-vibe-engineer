# parents[4] Root-Leak Audit — skill scripts

Read-only classification of every `.claude/skills/*/scripts/*.py` that computes a repo
root from `__file__` (`parents[...]`). Bug class: using the **kit's** repo root for
**target-project** operations. De-baked convention: `--project-root` (default `cwd`)
for all target-project operations (exemplar: `which-shape/scripts/route.py`).
`which-cleanup` excluded (being fixed in parallel). Audited 2026-06-12.

Severity vocabulary:
- **hard-leak** — target-project surface anchored at kit root with no CLI override.
- **default-only** — override flag exists; only the default points at the kit root.
- **kit-is-target** — the skill legitimately operates on the ecosystem repo itself.
- **clean** — root constant used only for KIT purposes (sys.path, kit's own files).

## Classification table

| skill/script | root uses: KIT / TARGET-LEAK / AMBIGUOUS | leaked surfaces | override flag exists? | severity |
|---|---|---|---|---|
| find-orphaned-ideas/scripts/find.py | 1 / 7 / 0 | registry (ledger), config (todo-tuning, importance-map), scan (TODO walk), plans (ai-docs/plans), reports (find-dormant) | no | **hard-leak** |
| rename-concept/scripts/assess.py | 2 / 4 / 0 | git (grep), config (concepts.yaml), scan (lint-guard glob, divergence run cwd) | no | **hard-leak** |
| find-concept-divergence/scripts/scan.py | 0 / 6 / 0 | scan (target anchoring + rel labels), config (glossary default) | partial (`--glossary` only; no root flag) | **hard-leak** |
| find-incomplete-sweep/scripts/scan.py | 0 / 3 / 0 | scan (relative `--paths` anchor, rel labels), git (blame cwd fallback) | no (`--paths` required but relative paths anchor at kit) | **hard-leak** |
| find-incomplete-sweep/scripts/scout.py | 0 / 1 / 0 | scan (manifest path anchoring) | no | **hard-leak** |
| track-idea/scripts/track.py | 1 / 1 / 0 | registry (ledger) | no | **hard-leak** |
| brainstorm-ideas/scripts/brainstorm.py | 1 / 1 / 0 | registry (ledger) | no | **hard-leak** |
| mature-existing-ideas/scripts/mature.py | 1 / 1 / 0 | registry (ledger) | no | **hard-leak** |
| extract-existing-ideas/scripts/extract.py | 1 / 3 / 0 | registry (ledger dedup), reports (out default + rel label) | partial (`root` positional + `--out`; ledger has none) | **hard-leak** |
| query-patterns/scripts/query.py | 1 / 2 / 0 | registry (.claude/patterns), reports (rel labels) | no | **hard-leak** |
| propose-boundary/scripts/propose.py | 0 / 1 / 0 | registry (skill-use telemetry log) | yes for main work (`--project-root`, default `.`); none for telemetry | **hard-leak** (telemetry only; best-effort write) |
| find-comment-drift/scripts/detect.py | 1 / 1 / 0 | scan (project-root default) | yes (`--project-root`, but default = kit root, not cwd) | **default-only** |
| check-ecosystem-consistency/scripts/check.py | 0 / 0 / 3 | registry (state file), reports (output root), labels | yes (`--project-root` default cwd, `--state-path`, `--output-root`) | **kit-is-target** / default-only (state/output defaults disagree with the cwd-based `--project-root`) |
| find-skill-artifact-drift/scripts/detect.py | 1 / 0 / 4 | scan (skills-dir default, doc-token resolution, rel labels) | partial (`--skills-dir`; token resolution + labels still anchored at kit root even when overridden) | **kit-is-target** / AMBIGUOUS |
| rename-concept/scripts/smoke.py | 0 / 0 / 4 | self-test probe under kit `tests/`, kit glossary, kit cwd | no (self-test by design) | **kit-is-target** (clean) |
| _common/scripts/run_skill_smokes.py | 2 / 0 / 1 | smoke subprocess cwd = kit root | yes (positional skills dir) | **kit-is-target** (clean) |
| which-shape/scripts/route.py | 3 / 0 / 0 | — (exemplar) | yes | **clean** |
| extract-enum/scripts/collect.py | 2 / 0 / 0 | — (kit `_common` + `scripts/_lib/artifact_scope.py` helper, degrades gracefully) | n/a | **clean** |
| unify-shadows/scripts/collect_shadows.py | 1 / 0 / 0 | — (kit `scripts/_lib/artifact_scope.py` helper) | n/a | **clean** |
| find-async-lifecycle-drift/scripts/{detect,run,report,smoke}.py | 1-2 / 0 / 0 each | — (`COMMON_DIR` only; detect has `--project-root` default cwd; smoke = fixture self-test) | yes | **clean** |
| find-complexity-hotspots/scripts/{detect,run}.py | 1 / 0 / 0 each | — (`COMMON_DIR` only; `--project-root` default cwd) | yes | **clean** |
| find-contract-drift/scripts/{detect,run,report,smoke}.py | 1-2 / 0 / 0 each | — (detect's extra PROJECT_ROOT use loads sibling kit detector = KIT) | yes | **clean** |
| find-dead-route-surface/scripts/{detect,run,report,smoke}.py | 1-2 / 0 / 0 each | — (sibling kit detector path = KIT) | yes | **clean** |
| find-test-obligation-drift/scripts/{detect,run,report,smoke}.py | 1-2 / 0 / 0 each | — | yes | **clean** |
| find-workflow-state-gaps/scripts/{detect,run,report,smoke}.py | 1-2 / 0 / 0 each | — (sibling kit detector path = KIT) | yes | **clean** |
| find-comment-drift/scripts/report.py, find-skill-artifact-drift/scripts/report.py | 1 / 0 / 0 each | — (`COMMON_DIR` only) | n/a | **clean** |
| 18 scripts using only `parents[2] / "_common"` sys.path inserts¹ | 1 / 0 / 0 each | — | n/a | **clean** |

¹ extract-workflow-registry/propose.py; find-doc-route-drift/{detect,report}.py; find-folder-topology-drift/{detect,report}.py; find-frontend-contract-drift/{detect,report}.py; find-frontend-duplication/cotton_inventory.py; find-layer-violation/detect.py; find-omnibus/report.py; find-route-sprawl/{detect,report}.py; find-rule-surface-drift/report.py; find-stale-artifacts/report.py; find-standard-gaps/project_state.py; find-workflow-duplication/{detect,report}.py; map-product-workflow/generate.py; orient/infer_state_signals.py.

## Leaking lines (evidence for every TARGET-LEAK verdict)

**find-orphaned-ideas/scripts/find.py** (REPO_ROOT = parents[4]):
- L36 `LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"`
- L780 `todo_config = _load_todo_tuning(REPO_ROOT)` (reads host `.engineering/docs/todo-tuning.md`)
- L805 `findings["todo"] = detect_todo_orphans(REPO_ROOT, ...)` (walks host source for TODOs)
- L812 `findings["stale_plans"] = detect_stale_plans(REPO_ROOT, records, ...)` (host `ai-docs/plans`)
- L818 `findings["dead_prototype"] = detect_dead_prototype(REPO_ROOT, args.from_report, ...)` (host `reports/find-dormant`)
- L824 `findings["attention_gap"] = detect_attention_gap(REPO_ROOT, records)` (host importance map)

**rename-concept/scripts/assess.py** (REPO_ROOT = parents[4]):
- L65 `cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,` (git grep over the kit's history, not the target's)
- L98 `p = REPO_ROOT / ".claude/contracts/concepts.yaml"` (target glossary read from kit)
- L119 `lint_dir = REPO_ROOT / "scripts" / "lint"` (checks the kit, not the host, for a guard lint)
- L149 `cwd=REPO_ROOT, capture_output=True, text=True, timeout=180)` (divergence scan run against kit)

**find-concept-divergence/scripts/scan.py** (REPO = parents[4]):
- L146 `p = (REPO / raw).resolve()` (positional scan targets anchored at kit root)
- L150/159/232/253/299 `rel = str(f.relative_to(REPO))` (crashes/mislabels for files outside kit)
- L339 `ap.add_argument("--glossary", default=str(REPO / ".claude/contracts/concepts.yaml"))`

**find-incomplete-sweep/scripts/scan.py** (REPO_ROOT = parents[4]):
- L124 `root = REPO_ROOT / root  # anchor relative --paths at the repo root`
- L393 `cwd=p.parent if p.parent.exists() else REPO_ROOT,` (blame fallback cwd; minor — primary cwd is correct)
- L457 `return str(pathlib.Path(path).resolve().relative_to(REPO_ROOT))` (graceful fallback, labels only)

**find-incomplete-sweep/scripts/scout.py** (REPO_ROOT = parents[3] of scripts dir):
- L72 `path = REPO_ROOT / path  # manifest paths are repo-root-relative` (target manifest paths anchored at kit)

**track-idea/scripts/track.py**: L42 `LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"`
**brainstorm-ideas/scripts/brainstorm.py**: L42 `LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"`
**mature-existing-ideas/scripts/mature.py**: L45 `LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"`

**extract-existing-ideas/scripts/extract.py**:
- L31 `LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"` (dedup runs against kit's ledger)
- L32 `DEFAULT_OUT = REPO_ROOT / ".claude" / "ideas" / "extract-candidates.json"`
- L109 `out_display = str(args.out.relative_to(REPO_ROOT))` (crashes for out paths outside kit)

**query-patterns/scripts/query.py**:
- L34 `PATTERNS_DIR = REPO_ROOT / ".claude" / "patterns"` (host pattern library read from kit)
- L174 `"path": str(rec.path.relative_to(REPO_ROOT)),`

**propose-boundary/scripts/propose.py**:
- L685 `log_path = repo_root / ".claude" / "skill-use" / "log.jsonl"` (telemetry written into kit repo even when `--project-root` targets another repo)

**find-comment-drift/scripts/detect.py**:
- L597 `parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)` (every sibling detector defaults to `Path.cwd()`; this one defaults to the kit root)

**check-ecosystem-consistency/scripts/check.py** (kit-is-target, noted for completeness):
- L24 `DEFAULT_STATE_PATH = REPO_ROOT / ".claude" / "ecosystem" / "last-state.json"` and L25 `DEFAULT_OUTPUT_ROOT = REPO_ROOT / "reports" / SKILL_NAME` — discovery follows `--project-root` (default cwd) but state/reports default to the kit root; vendored copies would read/write the wrong repo's state.

**find-skill-artifact-drift/scripts/detect.py** (kit-is-target/ambiguous, noted):
- L144/147 `candidates.append(PROJECT_ROOT / token...)` — documented-script token resolution stays anchored at kit root even when `--skills-dir` points at another repo's skills.

## Ranked fix list (hard leaks first)

1. **find-orphaned-ideas/scripts/find.py** — worst offender: 6 distinct target surfaces (ledger, two config docs, source walk, plans, dormant reports) all baked to kit root, no override. Add `--project-root` (default cwd) and thread it through every detector + `LEDGER`.
2. **rename-concept/scripts/assess.py** — git grep, glossary, guard-lint check, and divergence-scan cwd all run against the kit. Add `--project-root`; pass it to the delegated `find-concept-divergence` run too.
3. **find-concept-divergence/scripts/scan.py** — scan targets and rel-labels anchored at kit (`relative_to(REPO)` raises for outside files); glossary default kit-baked. Add `--project-root` (default cwd); anchor `iter_files` and the glossary default on it. (Fixing this also fixes assess.py's delegated scan.)
4. **find-incomplete-sweep/scripts/scan.py + scout.py** — relative `--paths` and manifest paths anchor at kit root; manifests written by scan are then re-anchored wrong by scout. Add a shared `--project-root`; record the root in the manifest.
5. **Ideas-family ledger bake-in** (track-idea/track.py, brainstorm-ideas/brainstorm.py, mature-existing-ideas/mature.py, extract-existing-ideas/extract.py, plus find-orphaned-ideas above) — all hardcode `REPO_ROOT/.claude/ideas/log.jsonl`. One shared shim (`--project-root` default cwd, or a `_common` `resolve_ledger(project_root)`) fixes five skills consistently. extract.py additionally needs `DEFAULT_OUT` and the `relative_to` display guard fixed.
6. **query-patterns/scripts/query.py** — `PATTERNS_DIR` kit-baked; same shim shape as the ideas family (`--project-root` default cwd). Keep the `REPO_ROOT/scripts` sys.path insert (KIT).
7. **propose-boundary/scripts/propose.py** — low-impact: derive the telemetry log path from `args.project_root` instead of `parents[4]` in `_log_skill_use`.
8. **find-comment-drift/scripts/detect.py** — default-only: change `--project-root` default from `PROJECT_ROOT` to `Path.cwd()` to match its seven sibling detectors.
9. **check-ecosystem-consistency/scripts/check.py** — default-only, kit-is-target: derive `DEFAULT_STATE_PATH`/`DEFAULT_OUTPUT_ROOT` from the resolved `--project-root` so a vendored copy doesn't read the kit's state.
10. **find-skill-artifact-drift/scripts/detect.py** — ambiguous: resolve doc tokens and report labels against `--skills-dir`'s repo root (e.g. `skills_dir.parents[1]`) instead of the kit's `PROJECT_ROOT`.

## Count summary

| severity | scripts |
|---|---|
| hard-leak | 11 (find-orphaned-ideas/find.py, rename-concept/assess.py, find-concept-divergence/scan.py, find-incomplete-sweep/scan.py, find-incomplete-sweep/scout.py, track-idea/track.py, brainstorm-ideas/brainstorm.py, mature-existing-ideas/mature.py, extract-existing-ideas/extract.py, query-patterns/query.py, propose-boundary/propose.py [telemetry only]) |
| default-only | 1 (find-comment-drift/detect.py) |
| kit-is-target / ambiguous | 4 (check-ecosystem-consistency/check.py, find-skill-artifact-drift/detect.py, rename-concept/smoke.py, _common/run_skill_smokes.py) |
| clean | 45 (which-shape/route.py exemplar; extract-enum/collect.py; unify-shadows/collect_shadows.py; 24 detector-family detect/run/report/smoke files with cwd-defaulted `--project-root` and KIT-only root uses; 18 `parents[2]/_common`-only scripts) |

Pattern worth noting: the newer detector family (find-async-lifecycle-drift, find-contract-drift, find-dead-route-surface, find-test-obligation-drift, find-workflow-state-gaps, find-complexity-hotspots) already follows the de-baked convention exactly (`--project-root`, default `Path.cwd()`; `__file__` root used only for `_common` imports). The leaks cluster in the **ideas/ledger family** and the **concept-rename family**, which were built around the assumption that the kit repo is the host repo.
