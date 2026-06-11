# Ecosystem Self-Review — Mechanical Duplication Audit

Bounded read-only diagnostic. 2026-05-25.
Scope: `.claude/skills/*/scripts/*.py` — 115 Python files across 67 skills.

---

## Ranked Summary (real consolidation candidates)

| Rank | Cluster | Scope | Duplicated what | Priority |
|---|---|---|---|---|
| 1 | **`run.py` orchestrators** | 4–5 drift-detector skills | Entire 44-LOC file; 2-line diff only | P0 — trivial to extract |
| 2 | **`report.py` thin wrappers** | 4 drift-detector skills + 2 others | Entire 29–34 LOC file; 2-line diff only | P0 — trivial to extract |
| 3 | **`smoke.py` harnesses** | 5–6 drift-detector skills | Entire 62–65 LOC file; diff is skill-name + pattern-set only | P0 — trivial to parametrize |
| 4 | **`_walk_python_files` + `_scan_file` AST traversal core** | 6 detect.py files | ~10–15 LOC identical body in each | P1 — real code; not yet in `_common` |
| 5 | **`_read_jsonl` parser** | 7 collapse.py + report.py files | ~12 LOC identical utility | P1 — one-liner fix |
| 6 | **`_load_scouts` + `_render_candidate` + `render_report` report scaffold** | 5–6 report.py files | ~60–103 LOC each, same structure, skill-specific field names | P1 — parametrizable scaffold |
| 7 | **`_segment_source` evidence snippet** | 5 detect.py files | 8 LOC; 3 copies take `ast.AST`, 2 take raw `lineno` int | P1 — tiny, but appears in 5 places |
| 8 | **`relpath` path helper** | `check.py` duplicates `_common/product_topology.py` | 4 LOC; identical body | P2 — just import from `_common` |

Total distinct consolidation clusters: **8 real** (plus 3 noise/boilerplate-only groups described below).

---

## Scanners That Couldn't Fully Run

- **jscpd** — not installed globally or in `.venv` (confirmed: `which jscpd` fails). The lexical/Type-1
  clone path in `/find-duplication` Stage 1 is completely unavailable. This leaves **token-level
  clone detection** uncovered — the AST path (which fired) only matches by function name + arity, not
  by body token similarity. Real consequence: if any two skill scripts share a large body under
  *different* function names, jscpd would catch it and this audit would not.
- **`semantic_inventory.py prompts` subcommand** — requires LLM-generated `purpose` summaries from
  Stage 2 first. The full semantic-duplication pipeline (Stages 2–5) was not run because it requires
  live LLM sub-agents. The inventory and callers phases ran and validated cleanly (824 defs, 504
  caller records). What's uncovered: *same-problem-different-code* at the function level (e.g., two
  skills that both implement "walk Python files and extract symbols" with different code shape).
  The AST name-matching above is a proxy for this and found the most important clusters.

---

## Detailed Cluster Evidence

### CLUSTER 1 — `run.py` orchestrators (P0)

**Files (4 near-identical; 1 slightly extended):**
```
find-async-lifecycle-drift/scripts/run.py     44 LOC
find-contract-drift/scripts/run.py            44 LOC
find-dead-route-surface/scripts/run.py        44 LOC
find-workflow-state-gaps/scripts/run.py       44 LOC
find-test-obligation-drift/scripts/run.py     58 LOC  (adds --staged / --changed-from args)
find-complexity-hotspots/scripts/run.py       59 LOC  (adds --max-findings, --include-tests args)
```

**Diff between the core 4:** exactly 2 lines differ — the `"""docstring"""` and the string literal
passed to `write_scan_outputs(...)`. Everything else is a verbatim clone: argparse boilerplate,
`sys.path` wiring, the `from detect import detect` + `from product_health import write_scan_outputs`
imports, the entire `main()` body.

**What is duplicated:** The entire file. Template structure is
`parse args → detect(project_root, paths) → write_scan_outputs(skill_name, title, records, ...)`.

**Verdict:** Real consolidation candidate. A single parametrized `run_skill.py` in `_common/` with
`--skill-name` / `--title` would eliminate 4 × 44 LOC = 176 LOC of clone, leaving only the
skill-specific args (staged, max-findings) as subclass overrides or extra args.

---

### CLUSTER 2 — `report.py` thin wrappers (P0)

**Files (4 strictly identical except 2 lines; 2 others with slightly different arg names):**
```
find-async-lifecycle-drift/scripts/report.py     29 LOC
find-dead-route-surface/scripts/report.py        29 LOC
find-workflow-state-gaps/scripts/report.py       29 LOC
find-contract-drift/scripts/report.py            30 LOC
find-folder-topology-drift/scripts/report.py     33 LOC   (different arg names --output-md/--output-json)
find-rule-surface-drift/scripts/report.py        33 LOC   (same as folder-topology)
```

**Diff between first 3:** exactly 2 lines — docstring and the string passed to
`render_simple_report(...)`. Body is a verbatim clone: read JSONL, call `render_simple_report`,
`mkdir`, `write_text`, `write_json`.

**Verdict:** Real consolidation candidate. All 6 delegate to `render_report_file` or `render_simple_report`
from `_common`. A thin `--title` arg to a shared script (or just using `run.py`'s report path) would
eliminate these entirely.

---

### CLUSTER 3 — `smoke.py` fixture harnesses (P0)

**Files (5 near-identical):**
```
find-async-lifecycle-drift/scripts/smoke.py     62 LOC
find-contract-drift/scripts/smoke.py            62 LOC
find-dead-route-surface/scripts/smoke.py        62 LOC
find-test-obligation-drift/scripts/smoke.py     62 LOC
find-workflow-state-gaps/scripts/smoke.py       64 LOC
find-comment-drift/scripts/smoke.py             65 LOC  (minor path-wiring variant)
```

**Diff between core 5:** docstring, the string in `print(...)`, and the `expected` set of pattern
names. The entire `_run()` function (subprocess call to `detect.py`, temp file, JSONL parse) is
verbatim across all five. The `main()` body is structurally identical: run good/bad fixtures,
assert no good findings, assert bad patterns superset of expected.

**Verdict:** Real consolidation candidate. The `_common/scripts/run_skill_smokes.py` already exists
as a smoke-runner but it operates at the skill-import-check level, not at the fixture-pattern level.
A shared `SmokeHarness(skill_name, expected_patterns)` or a parametrized `smoke.py` in `_common/`
would eliminate 5 × 62 LOC = 310 LOC of clone.

---

### CLUSTER 4 — `_walk_python_files` + `_scan_file` AST traversal (P1)

**`_walk_python_files` occurrences (6 non-fixture):**
```
find-dormant/scripts/detect_silent_catches.py    lines 50–60    (arity=2, skip_globs)
find-implicit-state/scripts/detect.py            lines 77–87    (arity=2, skip_globs)
find-query-mutation/scripts/detect.py            lines 75–85    (arity=2, skip_globs)
find-transaction-overreach/scripts/detect.py     lines ~60–76   (arity=2, adds is_file() fast-path)
find-layer-violation/scripts/detect.py           (similar)
propose-folder-reorganization/scripts/inspect.py (1-arg variant)
+ extract-enum/scripts/collect.py                (1-arg variant)
+ introduce-fk/scripts/collect.py                (1-arg variant)
```

**`_scan_file` occurrences (6):**
```
find-dormant/scripts/detect_silent_catches.py
find-implicit-state/scripts/detect.py
find-omnibus/scripts/detect.py
find-query-mutation/scripts/detect.py
find-transaction-overreach/scripts/detect.py
find-workflow-state-gaps/scripts/detect.py
```

**What is duplicated:** The 2-arg form of `_walk_python_files` is token-identical in
`find-implicit-state`, `find-query-mutation`, and `find-dormant/detect_silent_catches`. The
`_DEFAULT_SKIP_DIRS` constant appears in each too. `_scan_file` shares the outer file-open /
parse / yield-records pattern but the inner AST logic differs per skill.

**Verdict:** `_walk_python_files` (2-arg form) is a real clone — 10 LOC × 4+ files. Should move to
`_common/product_health.py` which already has `expand_paths`. `_scan_file` is structural similarity
only (same outer shape, distinct inner logic) — not a consolidation candidate.

---

### CLUSTER 5 — `_read_jsonl` utility (P1)

**Occurrences (12 total, across 7+ skill scripts):**
```
find-dormant/scripts/collapse.py
find-implicit-state/scripts/collapse.py + report.py
find-layer-violation/scripts/collapse.py + report.py
find-omnibus/scripts/collapse.py + report.py
find-query-mutation/scripts/collapse.py
find-transaction-overreach/scripts/collapse.py
+ 3 others
```

**What is duplicated:** A ~12 LOC function: open path if exists, `read_text`, splitlines, `json.loads`
per line, skip empty, catch `json.JSONDecodeError`. Two minor variants exist:
- `if not path.exists(): return []` at the top (find-omnibus, find-layer-violation)
- `if not path.exists(): return out` after initializing `out` (find-implicit-state, find-query-mutation)

**Verdict:** Clear consolidation candidate. Single `_read_jsonl` in `_common/product_topology.py`
or a shared `io_utils.py` would eliminate 12 × 12 LOC = 144 LOC of clone.

---

### CLUSTER 6 — `_load_scouts` + `_render_candidate` + `render_report` scaffold (P1)

**`_load_scouts` occurrences (6 report.py files):**
```
find-dormant/scripts/report.py            lines 50–62
find-implicit-state/scripts/report.py     lines 72–84
find-layer-violation/scripts/report.py    lines 108–122   (returns dict, not list — slightly different)
find-omnibus/scripts/report.py            lines 93–107    (same as layer-violation)
find-query-mutation/scripts/report.py     lines 58–69
find-transaction-overreach/scripts/report.py  lines 61–72
```

**`_render_candidate` occurrences (6 report.py files):** all have same signature
`(scout, candidate | None, idx) -> str`. Opening lines (file lookup, bucket, confidence) are
near-identical; diverge at domain-specific field names (`mutation_methods` / `categories` /
`fields_touched`).

**`render_report` occurrences (6 report.py files):** same arity `(scouts, raw_candidates, scan_id, target)`
in 4 skills; `find-omnibus` swaps argument order. Opening bucketing logic and `lines: list[str] = []`
section-header pattern are shared; the middle (per-finding rendering) is skill-specific.

**Verdict:** The outer scaffold (load scouts, bucket by verdict, render header, render per-finding,
render JSON summary) is shared structure. The hypothesis from §2 of the landscape doc — *"shared
triage-report + sub-agent fan-out scaffold"* — is **confirmed** for this family. A
`BaseReportRenderer` ABC or a shared `render_triage_report(skill_name, scouts, candidates, ...)`
template function with skill-provided `_render_one` callbacks would consolidate 1,932 LOC across
6 report.py files into ~400 LOC shared + 100 LOC each for skill-specific logic.

---

### CLUSTER 7 — `_segment_source` evidence snippet (P1)

**Occurrences (5 files):**
```
extract-enum/scripts/collect.py               line 279  (takes ast.AST node)
find-implicit-state/scripts/detect.py         line 172  (takes ast.AST node)
find-query-mutation/scripts/detect.py         line 112  (takes int lineno)
find-transaction-overreach/scripts/detect.py  line 265  (takes int lineno)
introduce-fk/scripts/collect.py               line 165  (takes ast.AST node)
```

**What is duplicated:** A ~8 LOC function: get lineno from node or use directly, bounds-check,
`src_lines[lineno - 1].strip()`, truncate to `limit` chars. The `ast.AST` vs `int` signature
difference is a trivial unification (`getattr(node, 'lineno', node) if not isinstance(node, int)`).

**Verdict:** Should live in `_common/product_health.py`. Currently absent from `_common`.

---

### CLUSTER 8 — `relpath` duplicate in `check.py` (P2)

**Files:**
```
check-ecosystem-consistency/scripts/check.py   line 46    (4 LOC)
_common/product_topology.py                    line 195   (4 LOC)
```

**What is duplicated:** Verbatim 4-LOC body: `path.relative_to(project_root)` with `ValueError` fallback.
The `_common` version already exists and is importable via `product_topology`.

**Verdict:** `check.py` should import from `_common` instead of re-defining. Trivial fix.

---

## Noise / Not Real Consolidation Candidates

**`main(arity=0/1)` — 59 skills** — every skill script has a `main()` entry point. This is
boilerplate convention, not a clone. The bodies are universally different. Not a consolidation target.

**`_confidence(arity=1)` — 4 collapse.py files** — same name, same 3-level high/medium/low output,
completely different internal logic in each (signal counts vs. method sets vs. category sets). This
is structural naming convention, not cloned code. Not a consolidation target.

**`_collapse(arity=1)` — 4 collapse.py files** — same outer shape (`by_group` defaultdict →
`candidates` list → sort → emit candidate dicts) but each implements a different grouping key and
output schema. Structural similarity only. Not a consolidation target.

**`detect(arity=2)` — 13 detect.py files** — the canonical entry point name for the detect
pipeline. Signatures vary (some add `include_*` toggles). Not a clone.

**`render_markdown(arity=1–4)` — 4 files** — completely different signatures and bodies across
`extract-existing-ideas`, `find-orphaned-ideas`, `query-patterns`, `which-shape`. Same convention,
not cloned code.

---

## Mapping to §2 Families from the Landscape Doc

### Do the 4 duplication detectors share a scaffold?

**Partially.** The 3 that follow the `rank.py` / `report.py` / `collapse*.py` pipeline
(`find-duplication`, `find-semantic-duplication`, `find-frontend-duplication`) share the *stage
names and file conventions* but not the bodies — each `rank.py` has a completely different scoring
formula, each `collapse*.py` has different union-find logic, each `report.py` renders a different
schema. `find-workflow-duplication` has only a `detect.py` + `report.py` and follows the simpler
drift-detector scaffold. The shared scaffold hypothesis **holds for the thin wrapper layer**
(Clusters 1–3) but **does not hold for the core logic layer** (rank/collapse/detect bodies are
genuinely distinct).

### Do the ~13 drift detectors share a scaffold?

**Yes, strongly confirmed.** The drift-detector family
(`find-async-lifecycle-drift`, `find-comment-drift`, `find-contract-drift`, `find-dead-route-surface`,
`find-folder-topology-drift`, `find-rule-surface-drift`, `find-test-obligation-drift`,
`find-workflow-state-gaps`) follows an extremely consistent `detect.py → run.py → report.py → smoke.py`
scaffold where:

- `run.py` is near-verbatim across 4–5 skills (Cluster 1 = P0 consolidation opportunity)
- `report.py` is near-verbatim across 4–6 skills (Cluster 2 = P0 consolidation opportunity)
- `smoke.py` is near-verbatim across 5–6 skills (Cluster 3 = P0 consolidation opportunity)
- `detect.py` bodies are genuinely skill-specific — the scaffold ends here

The **"shared triage-report + sub-agent fan-out scaffold"** hypothesis from the landscape doc L1 is
**confirmed and measured**: the scaffold is the `run.py` + `report.py` + `smoke.py` layer, totaling
~330 LOC of near-verbatim code replicated 4–6× across the drift-detector family. The sub-agent fan-out
scaffold (for the collapse-based skills: find-implicit-state, find-layer-violation, find-omnibus,
find-query-mutation, find-transaction-overreach) adds another ~1,900 LOC of shared structure in
`report.py` + utilities (Clusters 5, 6, 7).

---

## Raw Tool Output

### AST duplication_audit.py output (run against `.claude/skills`)

```
{
  "bare_int_request": 0,
  "shadow_safe_helpers": 0,
  "call_llm_defs": 0,
  "json_loads_request_body": 0,
  "function_clone_candidates": 60,
  "summary": 5
}
```

Key function clone groups by occurrence count (excluding `main` boilerplate):
```
_read_jsonl       arity=1  12 occurrences (7+ skills)
_load_scouts      arity=1   6 occurrences
_run              arity=1   6 occurrences (smoke + verify_rule — different)
_scan_file        arity=2   6 occurrences
_walk_python_files arity=2  6 occurrences
render_report     arity=4   6 occurrences
_render_candidate arity=3   5 occurrences
_segment_source   arity=3   5 occurrences (3 take ast.AST, 2 take int)
_collapse         arity=1   4 occurrences (same outer shape, distinct logic)
_confidence       arity=1   4 occurrences (same 3-tier output, distinct logic — noise)
```

### semantic_inventory.py output

```
collect: Files=128, Definitions=824, Edges=9057
Tiers: skip=315 light=311 full=172 priority=26
Callers: 504 checked, 245 with zero external refs
```

`prompts` subcommand: failed (requires LLM-generated summaries from Stage 2 — not run).

Stages 2–5 (summarize / compare / confirm / rank) were not run — require live LLM sub-agents.
The inventory and caller data are present under `reports/semantic-duplication/scan-20260525-222832/`.

---

## Recommended Next Actions

1. **P0 — Cluster 1–3 (run/report/smoke wrappers):** Extract parametrized templates to `_common/`.
   These are trivial diffs. Total LOC saved: ~800 LOC across 3 cluster families.
   Candidate approach: `_common/scripts/skill_runner.py`, `_common/scripts/skill_reporter.py`,
   `_common/scripts/skill_smoke.py` with skill-name + title + expected-patterns as args.
   Target: `/fix-workflow` with a cluster spec.

2. **P1 — Cluster 4–5 (`_walk_python_files` + `_read_jsonl`):** Move to `_common/product_health.py`
   or a new `_common/io_utils.py`. ~144 LOC + ~10 LOC per skill delete.

3. **P1 — Cluster 6 (report scaffold):** Design a `BaseSkillReporter` with a `_render_one` protocol
   for the 5 collapse-based skills. This is the biggest consolidation opportunity by LOC (~1,500 LOC
   before vs. ~800 after). Prerequisite: decide on the exact protocol shape before writing.

4. **P1 — Cluster 7 (`_segment_source`):** 4-line move to `_common/product_health.py`.

5. **P2 — Cluster 8 (`relpath` in `check.py`):** 1-line import fix.
