# DOGFOOD-LOG — /refactor-subsystem Phase 0–1 on core/tasks.py

Run: 2026-06-12 · /tmp/host-a-dogfood @ detached fbbab742 · spec id
`tasks-decomposition` · executor: Claude (Fable 5), orchestrating per
`.claude/skills/refactor-subsystem/SKILL.md`.

## Step-by-step execution record

| # | Step (skill ref) | What I ran / wrote | Outcome |
|---|---|---|---|
| 1 | Pre-read (SKILL.md header) | Read SKILL.md, knowledge/bootstrap.md, knowledge/operations.md, agents/inventory-scout.md | OK — all pointers resolved to real content |
| 2 | Phase 0 trigger (§Phase 0) | `python3 scripts/specs.py show tasks-decomposition` | exit 1, "no spec with id" → bootstrap path, as documented |
| 3 | Bootstrap 0.1 scope confirm | Scope pre-confirmed by assignment (`core/tasks.py`) | OK (no human in loop; assignment substitutes) |
| 4 | Bootstrap 0.2 | `specs.py init tasks-decomposition --code-roots core/tasks.py` | exit 0; spec scaffolded with 18-symbol @shared_task stub inventory |
| 5 | Bootstrap 0.3 | `inventory-check` (exit 0, STUB) and `--strict` (exit 1) | Matches bootstrap.md expectations exactly |
| 6 | Bootstrap 0.4 commit | **SKIPPED — deviation D1** (assignment forbids `git commit`) | Stub left uncommitted |
| 7 | 1.1 load spec/ledger | `show` OK; `coverage` 0/0 clean; `ledger.py list --decision split_queued,monitor` → "no entries match", exit 1 | OK (see friction F2) |
| 8 | 1.1 venv check | No `.venv`, no `$PYTHON_VENV_PATH` | Proceeded — Phase 0–1 needs no Django command (friction F3) |
| 9 | 1.1 cleanliness guard (operations.md) | `git status --porcelain | grep core/tasks.py` | clean |
| 10 | 1.1.5 inventory gate | `inventory-check` → STUB | Expected outcome per §1.1.5; wrote `phase-1-inventory-gate.md` |
| 11 | 1.2 convention docs | Searched `.claude/CLAUDE.md`, `.claude/docs/`, `documentation/`, grep for worked-example helpers | **All absent** (friction F4); wrote `convention-sources.md` with generic-rule substitute, explicitly recorded |
| 12 | Mode detection + 1.2.5 SOLID audit | SRP sentence (6 "and"s), cluster map from chunker, `specs.py solid` Gate-2 DRY (4 groups / 8 instances), linear-flow trace ×3 (+1 corroborating) | Decomposition mode confirmed; wrote `phase-1-solid-audit.md` (frictions F5) |
| 13 | 1.3.0 chunking | `chunk_file.py --token-budget 8000 --format json/markdown --output inventory/tasks__chunks.{json,md}` | 9 chunks, contiguous 1–4782; 33 "orphan regions" — all blank lines (friction F6); rewrote chunk map in SKILL format over chunker output (friction F7); wrote `chunks.jsonl` manifest |
| 14 | 1.3 scout dispatch | 9 parallel Agent-tool scouts, one per chunk, brief = inventory-scout.md template fully substituted | All 9 returned; 27/27 output files written (deviations D2 Explore→general-purpose, D3 venv/branch placeholders; friction F8) |
| 15 | 1.4 archaeology | Orchestrator-owned (4782 LOC > 500). `git log --follow --oneline` (15 commits), subject filter (5 hits), `git show` on all 5 | Wrote `archaeology/tasks.md` with 5 tagged LR-T candidates (friction F11 on gate wording) |
| 16 | 1.5 consolidation + gate | Counted/verified all outputs; wrote `phase-1-inventory.md` | **Gate PASS** — coverage 4782/4782, 27/27 files, archaeology ≥3 LR-T, no empty briefs |
| 17 | STOP | Per assignment, no Phase 2 work started | — |

Headline inventory results: 93 scout findings (0 P0 / 10 P1 / 51 P2 /
32 P3), 141 extracted-behavior candidates (IM 25, AR 20, EX 46, LR-T
22, REM 18, INV 10), 5 orchestrator archaeology LR-T candidates, 4
chunk-map corrections, 1 orchestrator-level P1 (phantom
`brand_crawl_task` import at core/views.py:9489).

## Frictions

Each cites the text I was following.

- **F1 — bootstrap commit step collides with no-commit environments.**
  bootstrap.md §0.4 ("Commit the scaffolded spec as a single-file
  commit before starting Phase 1") and SKILL.md Phase 0 invariants
  ("Commit the stub as a single-file commit"). No alternative offered
  when committing is not permitted (review-only dogfood, CI sandbox).
  I skipped it (deviation D1); a literal executor would either violate
  its constraints or stall. Severity: low (environmental), but the
  invariant is stated as unconditional.
- **F2 — `ledger.py list` exits 1 on empty result.** SKILL.md §1.1
  gives the command with no note that "no entries match" is a normal
  exit-1. An executor applying "non-zero exit = abort signal" (the rule
  Phase 0 *does* state for specs.py) could misread this as a failure.
  Severity: low.
- **F3 — venv check block reads as a hard abort.** SKILL.md §1.1 /
  operations.md show an `exit 1` guard ("ERROR: no venv...") gated
  only by prose ("before Django commands"). Phase 0–1 runs zero Django
  commands; this clone has no venv at all. A literal executor aborts a
  run that needs nothing from the venv. The text never says "skip the
  guard if the phase issues no Django commands." Severity: medium.
- **F4 — no fallback when convention docs don't exist.** SKILL.md §1.2
  step 1 declares `.claude/CLAUDE.md` Canonical Patterns "always in
  scope"; this clone has no `.claude/CLAUDE.md`, no `.claude/docs/`.
  The host-adapter comment covers *substituting* docs, not their total
  absence. Worse, the worked-example rule table (AR-safe-dispatch,
  AR-ensure-site, AR-safe-int-user-input) names origin-project helpers
  that don't exist here — a naive executor would hand scouts rules
  about `TaskDispatchService` and `safe_int` and harvest false
  violations. I improvised a generic-hygiene rule table and recorded
  the absence. Severity: high (silent noise-injection risk into every
  scout).
- **F5 — §1.2.5 step 3 is circular about `specs.py solid`.** The step
  says to use `scripts/specs.py solid` (Gate 2) for the DRY scan, but
  `solid`'s Level-1 gate checks for `phase-1-solid-audit.md` — the very
  file Phase 1.2.5 is producing — and its mode detection reported
  `mode=standard` mid-audit. In practice L1 reports SKIP and Gate 2
  output is usable, but the text never says "expect L1 to skip/fail at
  this stage; you only want the Gate-2 section." A cautious executor
  could treat `Overall (L1+L2): FAIL, exit 1` as an abort. Severity:
  medium.
- **F6 — chunker "orphan regions" ≠ SKILL "orphan chunks", and the
  skill conflates them.** SKILL.md §1.3.0: "Orphan chunks from 1.1.5
  are first-class. Create `orphan-1`, `orphan-2`, ... for every orphan
  region." `chunk_file.py` emitted **33 orphan regions** for
  core/tasks.py — every one a 1–2-line blank separator *already inside
  the chunk line ranges*. §1.1.5's orphans are spec-unmentioned spans —
  a different concept that doesn't even arise on the STUB path. Literal
  compliance = dispatching 33 scouts at blank lines and double-covering
  lines. I inspected each region, confirmed blank lines, folded them in,
  and documented the disposition. Severity: high (text directly
  instructs a wasteful/wrong action on real chunker output).
- **F7 — chunk-map output path collision.** §1.3.0 directs
  `chunk_file.py ... --format markdown --output
  .../inventory/<basename>__chunks.md`, then says "Write the chunk map
  to .../inventory/<basename>__chunks.md" in a *different* format
  (basename-qualified IDs, Archaeology-owner column). Two formats, one
  path; the orchestrator must overwrite the file the script just wrote,
  and nothing says so. I rewrote the file, preserving the chunker's
  declaration tables (raw JSON kept at `tasks__chunks.json`). Severity:
  medium (an executor might dispatch scouts against the chunker-format
  map with raw `C-01` IDs, breaking R35 qualification).
- **F8 — scout brief requires writing files, but the named agent type
  (and the brief's own tool list) can't write.** inventory-scout.md
  header: dispatch with `subagent_type="Explore"`; brief body: "Produce
  THREE outputs, each written to a file" and "Use only Read, Grep,
  Glob, Bash." In this harness `Explore` is read-only (no Write tool),
  and even the brief's own allowed-tool list omits Write while
  demanding file outputs. I dispatched `general-purpose` scouts and
  added Write (restricted to the three output paths) to the brief.
  Severity: high (the dispatch contract is unexecutable as written in
  this environment; a literal executor gets 9 scouts that cannot
  produce their completeness-contract files).
- **F9 — `{{branch}}` placeholder assumes a branch.** inventory-scout
  template sources it from `git branch --show-current`, which returns
  empty on the detached HEAD this dogfood mandates. Substituted
  "(detached HEAD @ fbbab742)". Severity: trivial.
- **F10 — inventory-check counts only `@shared_task` symbols.** The
  Phase 0 scaffold + §1.1.5 gate track 18 task decorators; the file has
  32 top-level defs. The 14 plain helpers (incl. 600-LOC-adjacent
  hot-spots like `extract_data_from_html`) are invisible to the
  spec-reality gate — it can report "clean" while ~40% of symbols are
  untracked. Acceptable on the STUB path (scouts cover everything), but
  the gate's authority is narrower than §1.1.5's prose implies.
  Severity: medium, deferred (matters most on re-entry runs).
- **F11 — Phase 1.5 gate condition 3 doesn't cover the middle tier.**
  SKILL.md §1.5: "every ≥ 50-commit file has ≥ 3 LR-T candidates; every
  ≤ 500 LOC / ≤ 20 commits file has inline archaeology or a note."
  core/tasks.py (4782 LOC, 15 commits) is neither: orchestrator-owned
  per operations.md's "everything else" rule, but the gate text never
  states what artifact the middle tier must produce. I held myself to
  the ≥3-LR-T standard anyway. Severity: low-medium (gate is
  unenforceable as written for the most common case — big file, modest
  history).

## Deviations / improvisations

- **D1** — skipped bootstrap §0.4 stub commit (assignment forbids
  commits). Spec exists untracked on disk; everything downstream ran
  against it normally.
- **D2** — scouts dispatched as `general-purpose` Agent-tool sub-agents
  instead of `Explore` (F8: Explore is read-only here). Template text
  otherwise verbatim, with Write added to the allowed tools for the
  three output files only. Top-level run, so `dispatch_scout.sh`
  subprocess mode was correctly not used (SKILL.md says Agent tool at
  top level) — no deviation there.
- **D3** — placeholder substitutions for environment gaps: `{{venv}}` →
  "python3 (no venv in this clone; no Django commands needed)";
  `{{branch}}` → "(detached HEAD @ fbbab742)".
- **D4** — orphan regions: not promoted to orphan chunks (all blank
  lines; F6). Disposition documented in `phase-1-inventory-gate.md` and
  the chunk map.
- **D5** — convention sources: substituted a generic Python/Django/
  Celery hygiene table for the absent project docs (F4), recorded
  explicitly in `convention-sources.md` so Phase 4's human can audit
  the choice.
- **D6** — `tasks__chunks.md` overwritten from chunker format into the
  SKILL.md §1.3.0 orchestrator format (F7), chunker detail preserved
  in-file and in `tasks__chunks.json`.

## Verdict on the skill text

**Could a fresh executor run Phase 0–1 from the text alone without
improvising? NO — close, but no.** The phase ordering, gates, scripts,
and artifact paths are unusually precise and mostly executed verbatim
(Phase 0 was flawless; specs.py/chunk_file.py behaved exactly as
documented; the completeness gate was mechanically checkable). But
three frictions force improvisation on any real run shaped like this
one, and two of them would corrupt or stall the run if resolved
naively:

1. **F8 — scout dispatch contract is unexecutable as written.** The
   brief demands three written files from an agent type that cannot
   write (and omits Write from its own tool list). Worst because every
   downstream gate (1.5, 2.2, 2.3) depends on those files existing.
2. **F6 — orphan-region instruction misfires on real chunker output.**
   "Create an orphan chunk for every orphan region" meets a chunker
   that labels blank separator lines as orphan regions → 33 junk
   scouts. The two orphan concepts (spec-unmentioned spans vs chunker
   gaps) need disentangling in §1.3.0.
3. **F4 — no-convention-docs fallback is undefined.** On a host without
   `.claude/CLAUDE.md`/`.claude/docs/`, §1.2 leaves the executor to
   choose between inventing rules, importing the origin project's
   helpers as false rules (the worked example actively invites this),
   or proceeding ruleless. Any of the three changes every scout's
   findings output.

Honorable mentions: F5 (run a gate mid-phase that the gate's own L1
says shouldn't pass yet) and F3 (venv guard reads as a hard abort in a
phase that never needs the venv) would each stall a cautious literal
executor; F7 silently breaks R35 ID qualification if the executor
trusts the chunker's file.
