# Scout verification — /fix-workflow frame review

**Date:** 2026-06-12
**Scout inputs:** `.claude/tasks/skill-repairs/fix-workflow/frame-review.md` (F1–F9) plus three pre-established campaign defects (D1–D3).
**Ground truth:** `.claude/skills/fix-workflow/SKILL.md` (369 lines), `knowledge/fix-shapes.md` (245 lines), `knowledge/learnings.md` (163 lines), `.claude/skills/find-layer-violation/SKILL.md`, `.claude/skills/find-duplication/SKILL.md`, `.claude/skills/repair-skill/SKILL.md`, `scripts/log_effectiveness.py`, `.claude/skills/track-idea/scripts/track.py`, filesystem checks, repo-wide greps. All line numbers below are re-derived from the files as they exist today.

---

## 1. CLAIM VERIFICATION

### F1 — TRUE (citations accurate; claim intact)

The knowledge directory contains exactly two files (`ls` verified):

```
.claude/skills/fix-workflow/knowledge/
├── fix-shapes.md
└── learnings.md
```

Exactly **eight** references point at a bare `knowledge/` with the filename visibly stripped. `grep -n 'knowledge/'` across all three files, bare hits only:

- `SKILL.md:42-43` — exact text:
  ```
  - `knowledge/` — worktree paths, test matrix,
    commit verb conventions, concurrency guard commands.
  ```
- `SKILL.md:116-117` (bullet starts at 115) — exact text:
  ```
  - **Cleanliness guard:** target files must not carry unrelated
    uncommitted edits before starting. `knowledge/`
    has the exact commands and abort conditions.
  ```
- `SKILL.md:199-200`:
  ```
  The matrix lives in `knowledge/` (baseline + per-
  subsystem rows). If unsure, run the superset for the file's subsystem.
  ```
- `SKILL.md:206`:
  ```
  Command + rationale in `knowledge/`. Fewer clones
  ```
- `SKILL.md:219-221` (bare ref is line 221):
  ```
  Verb conventions (`Dedup` / `Delete` / `Fix` / `Promote` /
  `Migrate`) and the commit-message template live in
  `knowledge/`.
  ```
- `SKILL.md:334-335`:
  ```
  - Running the full repo test suite (use `knowledge/`
    subsystem mapping).
  ```
- `knowledge/learnings.md:112` (R10):
  ```
  the test matrix in `knowledge/` — it maps cluster subsystems
  ```
- `knowledge/fix-shapes.md:66-67`:
  ```
  5. **Run the targeted test suite** (see `knowledge/` test
     matrix) before committing. If any test fails, **do not commit** —
  ```

Corroborating evidence the review did not cite — `SKILL.md:38` says **"Procedural detail lives in three knowledge files:"** yet the list that follows (lines 40–48) has four bullets, of which the second (line 42) is the filename-stripped one; the repository-layout block (`SKILL.md:362-368`) shows only `fix-shapes.md` and `learnings.md`. Both confirm a deleted third file rather than a typo. The execution-time-failure analysis is accurate: Step 3 is the only commit gate (`SKILL.md:195-196`: "**Pre:** edits complete, playbook's stop condition satisfied. / **Post:** targeted test suites green."), and `learnings.md` R14 (lines 155-157, under heading at 153) is quoted correctly: "The post-cluster jscpd re-scan in Step 3 is the only way to confirm / the clone actually dropped."

### F2 — TRUE (one line citation off by one)

- `layer:LV-2` is advertised in `best_for` at **`SKILL.md:12`**, not :13 as the review says:
  ```
  11	  cluster IDs (`cluster:P0-1`, `delete:foo`, `semantic:SC-1`,
  12	  `layer:LV-2`), file paths, or free-form descriptions. Writes
  ```
- Form A's pattern list (`SKILL.md:55-56`) recognizes only:
  ```
  Pattern: `cluster:<name>`, `delete:<name>`, `fix:<name>`,
  `semantic:<name>`, or a short id like `P0-1`, `P1-agent-extract`.
  ```
  No `layer:`.
- The report-loading bullets (`SKILL.md:58-68`) map `delete:`/`fix:` → `reports/dormant/latest/report.md` (58), `semantic:` → `reports/semantic-duplication/latest/triage.md` (59), `cluster:`/P0-P2 → `reports/duplication/latest/triage.md` (68). No `layer:` row.
- The Step-1 shape table (`SKILL.md:130-139`) has eight rows, none extract-service.
- Upstream `find-layer-violation/SKILL.md` hands off with that exact syntax in four places — line 12 ("hands off to `/fix-workflow layer:<candidate_id>`"), line 27 ("Refactor execution (use /fix-workflow layer:<id>)"), lines 54-55 ("their IDs resolve as `/fix-workflow layer:<candidate_id>` arguments"), lines 240-241 ("recommended next slash command — for the worst confirmed candidate, / `/fix-workflow layer:<candidate_id>`"). Its report dir is confirmed at lines 96-99:
  ```
  REPORT_DIR="reports/layer-violation/scan-${TS}"
  mkdir -p "${REPORT_DIR}/scout"
  ln -sfn "scan-${TS}" reports/layer-violation/latest
  ```
  Stage 4 (lines 207-219) writes `${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`; per-candidate verdicts live at `scout/<candidate_id>.json`.

### F3 — TRUE (one addendum: an ADR also mentions the path, as commentary)

- `SKILL.md:235`: ``Append a cluster entry to `reports/duplication/learnings.md`:``
- `SKILL.md:262-263`: "Also update the **running LOC delta table** at the bottom of / `reports/duplication/learnings.md` (the cross-cluster log — NOT the".
- `reports/duplication/` does not exist (`ls: reports/duplication: No such file or directory`).
- Repo-wide grep for `reports/duplication/learnings` (excluding campaign artifacts): hits only `fix-workflow/SKILL.md` (lines 3, 235, 263), `refactor-subsystem/SKILL.md:1263` ("Add a cluster entry to `reports/duplication/learnings.md`:"), `refactor-subsystem/knowledge/operations.md:178` ("appends to `reports/duplication/learnings.md` (7.3)"), and — missed by the review but immaterial — `ai-docs/decisions/0004-parallel-writers-shared-helper.md:155`, which is descriptive ("`reports/duplication/learnings.md` (host-project specific)"), not a producer or consumer. All real references are **appenders**, none are readers. `/find-duplication` Stage 0 (its SKILL.md:60-63) creates `reports/duplication/scan-${TS}` + `latest` symlink but never a `learnings.md`. No skeleton, no table-schema definition anywhere.

### F4 — TRUE (line cites accurate within ±1)

All named host paths are absent from this repo (checked at repo root): `manage.py` MISSING, `core/` MISSING, `templates/` MISSING, `static/` MISSING, `testing/` MISSING, `urls.py` MISSING, `admin.py` MISSING, `frontend/` MISSING, `management/` MISSING.

- Re-grep roots, `fix-shapes.md:146-147` and 154-155 (code block 144-156):
  ```
  git grep -w '<name>' -- core/ templates/ static/ urls.py admin.py \
      management/commands/ frontend/
  ```
- Baseline test command, `fix-shapes.md:183-186` (block 182-187):
  ```
  .venv/bin/python manage.py test \
    tests.test_site_capabilities tests.test_hydration_detector \
    <any_other_relevant_from_matrix> \
    --settings=app.settings_test_sqlite -v 2
  ```
- `fix-shapes.md:189-192`: "6. **Run `django-admin check`** to catch dangling URL patterns:" with `.venv/bin/python manage.py check` at 191.
- Stop condition, `fix-shapes.md:194-199`:
  ```
  ### Stop condition

  - Fresh re-grep returned zero new inbound references.
  - `manage.py check` passes (no dangling URLs / admin registrations).
  - Baseline + subsystem tests pass.
  - Commit title starts with `Delete`.
  ```
- Form B host-path detection, `SKILL.md:79-80` (review said :80; the rule sentence is line 79):
  ```
  Pattern: starts with `core/` or matches an existing path. Example:
  `core/services/parse_json_body_helper.py`.
  ```
- Registry checklist host paths, `SKILL.md:188-189` ("Verification must include the site workflow Django tests and, when a / dev server is running, `testing/test_site_pages.py`.") and `SKILL.md:190-191` ("Do not touch `core/services/ai_sidecar/` or unified AI / workflow behavior unless the user explicitly scopes that work in.").
- Additional same-class instances the review did not list: `fix-shapes.md:169-170` ("URL patterns in `core/urls.py` if it was a view" / "Admin registrations in `core/admin.py` if it was a model admin") and `knowledge/learnings.md:143-144` (R13's `tests_custom_site` host test module). Frontmatter `framework: django` is at `SKILL.md:21`.

### F5 — TRUE

- `SKILL.md:163-165`:
  ```
  Read the matching section of `knowledge/fix-shapes.md` (2a / 2b /
  2c / 2d) and follow it end to end. Each playbook has an explicit
  **stop condition** — do not commit unless you can check every box.
  ```
- Step 3 precondition, `SKILL.md:195`: `**Pre:** edits complete, playbook's stop condition satisfied.`
- Shape-table row, `SKILL.md:139`: `| **Workflow registry cleanup** | workflow step, boot payload, or endpoint knowledge repeated across executable layers | checklist below |`
- The checklist (`SKILL.md:167-191`, heading "### Workflow registry cleanup checklist") contains eight action bullets and zero stop-condition block; the next heading is `## Step 3 — Verification test matrix` at line 193.
- Corroboration: `fix-shapes.md`'s own shape→section table (lines 6-13) covers only the 2a–2d shapes — the registry shape is absent there too — and `fix-shapes.md:15-16` ("Each section ends with a 'stop condition' — if you can't satisfy it, / abort and report to the user") covers only the four playbook sections.

### F6 — TRUE

- `SKILL.md:83-84`:
  ```
  scratch. Run the Investigation sub-steps of `/find-duplication` on
  just that file. **Before any edits**, present the plan (file list,
  ```
- `find-duplication/SKILL.md` has no section named "Investigation". The nearest is line 112: `### Stage 4 — Investigate (parallel fan-out)`. Its contract (lines 114-116): "**Pre:** `ranked.json`. **Post:** `${REPORT_DIR}/scout/<finding_id>.json` for / every investigated finding; a single `${REPORT_DIR}/classified.json`". It dispatches per-finding sub-agents by expanding "the `agents/investigate.md` template (substitute / `{{finding_id}}`, `{{finding_json}}`, `{{project_root}}`, `{{skill_root}}`, / `{{output_path}}`)" (lines 131-133). It consumes Stage 1–3 artifacts (`collapsed.json` → `ranked.json`) and cannot run standalone on a single file. Verdict and failure analysis confirmed.

### F7 — TRUE (line citation off by one)

The missing-report abort path is `SKILL.md:70-73` (review said 71-74):

```
If the referenced report file does not exist, abort and tell the user
which detection skill to run first (`/find-dormant`,
`/find-duplication`, or `/find-semantic-duplication`) — do NOT fall
back to scanning the codebase.
```

Then `SKILL.md:75-76`: "Find the matching cluster, extract file list + fix shape + helper / name. Proceed to Step 1." There is no instruction anywhere in Form A for an ID that is not present in a loaded report, and Form A is the explicit no-confirmation path (`SKILL.md:31-33`; `SKILL.md:153`: "**Form A** → plan is a self-check; proceed after writing it.").

### F8 — TRUE (argparse range slightly understated; immaterial)

- `SKILL.md:285-286`: ``Where `<shape>` is one of: `dedup`, `delete`, `fix`, `promote`, / `migrate`, `shadow`.`` — six buckets.
- The Step-1 table (`SKILL.md:130-139`) defines eight shapes; `Template triplication` (135), `Quasi-dead / broken` (138), and `Workflow registry cleanup` (139) have no stated bucket mapping. (A defensible guess exists for some — e.g. quasi-dead → `fix` via the commit-verb convention — but it is nowhere stated.)
- Dashboard purpose at `SKILL.md:269-273` confirmed: "Append an effectiveness log entry so / `reports/_meta/dashboard.md` can track which shapes are being / cleaned up over time. `findings_total` is always 1 (one cluster per / run); `buckets` keys on the shape with value 1."
- The parenthetical defense of the invocation is correct — see §3 below. One precision fix: the argparse flag definitions span **lines 47-72** of `scripts/log_effectiveness.py` (the review says 47-67; `--ts` ends at 72); no flag is missing either way. The JSON-dict validation is at lines 75-81 as cited; the script is stdlib-only (`log_effectiveness.py:21-23` docstring; `skill_use.py` imports only `datetime`, `json`, `pathlib`, `typing`), so `python3` is fine.

### F9 — TRUE

- `SKILL.md:90-93` (Form C):
  ```
  The description is your brief. Produce an execution plan with:
  - Explicit list of files that will be modified
  - Fix shape (from the table in Step 1)
  - Expected changes per file
  ```
- `SKILL.md:153-156`:
  ```
  **Form A** → plan is a self-check; proceed after writing it.
  **Forms B/C** → plan is an internal record; the user already
  approved scope during argument parsing. Don't wait for a second
  confirmation.
  ```
The classification table and shape vocabulary live only in Step 1 (`SKILL.md:128-139`), which nominally runs after the Form B/C approval that requires naming a shape from that table (Form B likewise, `SKILL.md:84-86`: "present the plan (file list, / fix shape, helper name) to the user and wait for confirmation."). Ordering contradiction confirmed.

### D1 — TRUE: nothing in the repo reads `reports/duplication/learnings.md` or the LOC delta table

- Mandate quotes: `SKILL.md:235` (above) and `SKILL.md:262-267` — the complete statement of the relationship between the two learnings files:
  ```
  Also update the **running LOC delta table** at the bottom of
  `reports/duplication/learnings.md` (the cross-cluster log — NOT the
  skill-internal `knowledge/learnings.md`). If the cluster taught
  something not already in the skill's `knowledge/learnings.md`
  R1–R14, call it out in the entry — the user decides whether to
  update the skill.
  ```
  I.e. `reports/duplication/learnings.md` = "the cross-cluster log"; `knowledge/learnings.md` = "skill-internal" R1–R14; with a human-gated promotion path from the former's entries to the latter.
- Repo-wide grep for `reports/duplication/learnings` across skills, scripts, docs (excluding the campaign dir): hits = `fix-workflow/SKILL.md:3,235,263` (appender + description), `refactor-subsystem/SKILL.md:1263` + `refactor-subsystem/knowledge/operations.md:178` (appender), `ai-docs/decisions/0004:155` (descriptive, "host-project specific"). **Zero readers.** Repo-wide grep for `LOC delta`: `fix-workflow/SKILL.md:149,252,262` and `refactor-subsystem/SKILL.md:1279` — all writers/templates; no script or skill parses the table.
- `reports/duplication/` does not exist. Additionally `.gitignore:20-22`:
  ```
  # effectiveness meta under reports/_meta/ is committed (see README.md).
  /reports/*
  !/reports/_meta/
  ```
  — even when written, the cross-cluster log is gitignored and ephemeral; it cannot function as a durable cross-cluster ledger.
- What Step 7's next-cluster recommendation actually draws on (`SKILL.md:317-324`): "More clusters in the same triage → point at the next." / "Follow-on findings surfaced → suggest `/find-dormant` to validate / them." — i.e. the **current run's** triage report and the follow-on findings the run just produced (Step 6, `SKILL.md:301-303`: "Write these to a `## Follow-on findings` section in the learnings / entry. They are **not** TODOs for you — they inform the user's / next cluster choice (R11)."). Nothing in Step 7 — or any other skill — reads historical entries from the file.
- **Remediation the evidence better supports: (a)** — fold the cross-cluster entry into the `knowledge/learnings.md` promotion path. Reasons: (i) the only learnings surface with a real consumer is `knowledge/learnings.md`, which the skill itself reads (`SKILL.md:44-45`: "Read on ambiguity") and whose R-rules are load-bearing throughout `fix-shapes.md` (R3 at :43, R6 at :37, R7 at :85, plus R1/R11/R12/R14 cites in SKILL.md); (ii) the promotion path already exists verbatim at `SKILL.md:264-267`; (iii) the file is gitignored, so option (b)'s Step-1 tail read would manufacture a consumer for an artifact that does not survive clones and does not exist on any fresh host; (iv) Step 7's recommendation demonstrably needs only current-run inputs (current triage + just-produced follow-on findings), so no step is starved by retiring the file. Caveat for the spec: `refactor-subsystem` (SKILL.md:1263, operations.md:178) appends to the same dead path — repairing only fix-workflow leaves the sibling pointing at the orphan; the spec should at minimum note this residual.

### D2 — TRUE: no "## How success is judged" block exists

`grep -n '^## '` over fix-workflow SKILL.md yields: Argument parsing (50), Scope (110), Step 1 (119), Step 2 (158), Step 3 (193), Step 4 (209), Step 5 (233), Step 6 (288), Step 7 (305), Non-goals (330), Failure modes and recovery (341), Repository layout (360). No success-judgment block anywhere. The comparator exists at `repair-skill/SKILL.md:45-56`:

```
## How success is judged

- The **independent verifier** (Stage 5) passes every finding as
  RESOLVED with a clean no-invention audit — it shares no context
  with the implementer and is told to refute, not confirm.
- The **lift probe** (Stage 6) moves the headline defect site at the
  weakest supported tier, with zero regressions, against criteria
  locked before any probe returns.
- For execution-heavy skills, a **real-host dogfood** (Stage 7)
  completes from the text alone, without forced improvisation.
- Every residual is fixed or ledgered — never silently dropped.
Write toward these gates from Stage 0.
```

What currently sits between the frontmatter (closes with `---` at line 22) and the first `##` section (line 50), in full — `SKILL.md:24-48`:

```
# /fix-workflow

You are the **orchestrator** for a cleanup cluster. Unlike
`/find-duplication`, `/find-dormant`, and `/find-semantic-duplication`
— which are detection pipelines — this is the execution skill. It
writes code, runs tests, and produces commits.

**Invocation is not blanket authorization.** For Form A (cluster ID
from a triage report), the user has authorized the specific cluster
by referencing it. For Forms B and C, you must present an explicit
plan and wait for user confirmation before any edits — see
Argument Parsing below. Authorization for one cluster is never
authorization for follow-on clusters or adjacent fixes.

Procedural detail lives in three knowledge files:

- `knowledge/fix-shapes.md` — Step-2 playbooks for the seven shapes.
  Read only the section matching the classified cluster.
- `knowledge/` — worktree paths, test matrix,
  commit verb conventions, concurrency guard commands.
- `knowledge/learnings.md` — 14 rules from prior clusters (R1–R14).
  Read on ambiguity; don't front-load.
- `.claude/skills/_common/interface-depth.md` — read when the cluster
  extracts a helper/service, promotes a canonical interface, or adds an
  adapter seam.
```

Cleanest insertion anchor: between line 36 ("authorization for follow-on clusters or adjacent fixes.") and line 38 ("Procedural detail lives in three knowledge files:") — mirroring repair-skill, where the block precedes the procedural matter.

### D3 — TRUE (with one nuance the spec should preserve)

The closeout step is Step 7. Entire current text, `SKILL.md:305-328`:

```
## Step 7 — Recommend next action

End with a short recommendation that covers both **preventing
recurrence** and **what to fix next**:

1. **Prevent recurrence.** If the fix shape generalizes (silent-catch,
   bare-int-on-request, shadow helper, etc.), suggest:
   `/prevent-regression cluster:<id>` — it produces a proposal for a
   diff-scoped lint rule + fixture + CLAUDE.md Canonical Patterns
   entry, bundled into one commit. Skip this recommendation when the
   fix was obviously one-off (a single-site data bug, a typo) — two
   clusters justify one rule, not a family.
2. **Next cluster.** Then pick one of:
   - More clusters in the same triage → point at the next.
   - File is now fully dedup'd → suggest `/find-duplication` on an
     adjacent file or sub-package.
   - Follow-on findings surfaced → suggest `/find-dormant` to validate
     them.
   - Worktree blocking on concurrent edits in main → surface it
     explicitly.

**Do NOT start the next cluster automatically.** Each cluster is a
separate authorization — and `/prevent-regression` is its own
authorization too; it builds a proposal but does not commit.
```

There is no class-lift gate: the step never requires naming the defect class, never asks for the cheapest detector for that class, and never mandates running it across the codebase before closeout. Nuance: item 1 is an adjacent-but-weaker mechanism — an optional *suggestion* to propose a guard, with a deliberate threshold ("two clusters justify one rule, not a family"); a class-lift gate should be added without destroying that threshold language.

---

## 2. EDIT ANCHORS

All anchors verified unique within their file unless noted. Line numbers from current files.

### Complete bare-vs-proper `knowledge/` reference inventory (`grep -n 'knowledge/'`)

**Bare directory references (broken — F1), 8 sites:**

| File:line | Anchor text (exact) |
|---|---|
| SKILL.md:42-43 | `` - `knowledge/` — worktree paths, test matrix, `` ⏎ ``   commit verb conventions, concurrency guard commands. `` |
| SKILL.md:116-117 | ``   uncommitted edits before starting. `knowledge/` `` ⏎ ``   has the exact commands and abort conditions. `` |
| SKILL.md:199-200 | `` The matrix lives in `knowledge/` (baseline + per- `` ⏎ `` subsystem rows). If unsure, run the superset for the file's subsystem. `` |
| SKILL.md:206 | `` Command + rationale in `knowledge/`. Fewer clones `` |
| SKILL.md:220-221 | `` `Migrate`) and the commit-message template live in `` ⏎ `` `knowledge/`. `` |
| SKILL.md:334-335 | `` - Running the full repo test suite (use `knowledge/` `` ⏎ ``   subsystem mapping). `` |
| fix-shapes.md:66-67 | `` 5. **Run the targeted test suite** (see `knowledge/` test `` ⏎ ``    matrix) before committing. `` |
| learnings.md:112 | `` the test matrix in `knowledge/` — it maps cluster subsystems `` |

**Proper filename references (working):** SKILL.md:40 (`knowledge/fix-shapes.md`), SKILL.md:44 (`knowledge/learnings.md`), SKILL.md:163 (`knowledge/fix-shapes.md`), SKILL.md:263-265 (`knowledge/learnings.md` ×2), SKILL.md:365 (`└── knowledge/` — tree-diagram directory entry, structural, fine as-is).

### F1 supplementary anchors

- SKILL.md:38: `Procedural detail lives in three knowledge files:` (the count must change whether a file is restored or the blocks are inlined).
- SKILL.md:40-41: `` - `knowledge/fix-shapes.md` — Step-2 playbooks for the seven shapes. `` (also "seven" vs the 8-row table — see F5/F8).
- SKILL.md:362-368 repository layout block:
  ```
  .claude/skills/fix-workflow/
  ├── SKILL.md                    # this file — orchestrator
  └── knowledge/                  # loaded on demand, not front-to-back
      ├── fix-shapes.md           # Step-2 playbooks for the 7 shapes
      └── learnings.md            # R1–R14 from prior clusters
  ```
- If the jscpd re-scan command is restored, the repo's real wrapper is `scripts/lint/run_jscpd.py` (exists; find-duplication Stage 1 invokes `.venv/bin/python scripts/lint/run_jscpd.py <target> --output "${REPORT_DIR}/jscpd" --offline-ok`).

### F2 anchors

- SKILL.md:55-56 (Form A pattern list — quoted in F2).
- SKILL.md:58 (first loading bullet, insertion neighborhood for a `layer:` row):
  ```
  - `delete:<name>` / `fix:<name>` → load `reports/dormant/latest/report.md`
  ```
- SKILL.md:68 (last loading bullet):
  ```
  - `cluster:<name>` or P0/P1/P2 ID → load `reports/duplication/latest/triage.md`
  ```
- SKILL.md:139 (shape-table last row, for an extract-service row or an explicit re-route-to-/refactor-subsystem rule):
  ```
  | **Workflow registry cleanup** | workflow step, boot payload, or endpoint knowledge repeated across executable layers | checklist below |
  ```
- SKILL.md:11-12 (`best_for`, if `layer:LV-2` is instead deleted):
  ```
    cluster IDs (`cluster:P0-1`, `delete:foo`, `semantic:SC-1`,
    `layer:LV-2`), file paths, or free-form descriptions. Writes
  ```
- Upstream facts any new row must match: report at `reports/layer-violation/latest/` containing `report.md` + `findings.json` + `scout/<candidate_id>.json`; IDs are `candidate_id`s.

### F3 / D1 anchors

- SKILL.md:235: `` Append a cluster entry to `reports/duplication/learnings.md`: ``
- SKILL.md:262-263 (start of the LOC-table paragraph; full text quoted in D1):
  ```
  Also update the **running LOC delta table** at the bottom of
  `reports/duplication/learnings.md` (the cross-cluster log — NOT the
  ```
- SKILL.md:3 — frontmatter description contains ``updates `reports/duplication/learnings.md`,`` — must change in lockstep with whatever Step 5 becomes.
- Sibling residual (note in spec; separate scope): refactor-subsystem/SKILL.md:1263, refactor-subsystem/knowledge/operations.md:178.

### F4 anchors

- fix-shapes.md:146-147 and 154-155 (grep roots — quoted in F4).
- fix-shapes.md:183-186 (baseline test block) and :191 (`   .venv/bin/python manage.py check`).
- fix-shapes.md:189: `` 6. **Run `django-admin check`** to catch dangling URL patterns: ``
- fix-shapes.md:196-198 (stop-condition lines to re-state as host-neutral properties):
  ```
  - Fresh re-grep returned zero new inbound references.
  - `manage.py check` passes (no dangling URLs / admin registrations).
  - Baseline + subsystem tests pass.
  ```
- fix-shapes.md:169-170 (prune-alongside host paths — quoted in F4).
- SKILL.md:79-80 (Form B pattern — quoted in F4).
- SKILL.md:188-191 (registry-checklist host paths — quoted in F4; overlaps the F5 insertion, sequence the edits).

### F5 anchor (insertion point for the registry stop condition)

End of checklist / start of Step 3, SKILL.md:186-193:

```
- Add or update a diff-scoped guard when the migrated pattern can
  recur, e.g. JS endpoint-sprawl lint with good/bad fixtures.
- Verification must include the site workflow Django tests and, when a
  dev server is running, `testing/test_site_pages.py`.
- Do not touch `core/services/ai_sidecar/` or unified AI
  workflow behavior unless the user explicitly scopes that work in.

## Step 3 — Verification test matrix
```

Insert the stop-condition block after line 191, before line 193. Also reconcile SKILL.md:163-165 ("(2a / 2b / 2c / 2d)" + "Each playbook has an explicit **stop condition**") and, if the registry shape gets a real stop condition, fix-shapes.md:6-13/15 (its table omits the shape) plus the "seven shapes"/"7 shapes" counts at SKILL.md:40 and :366.

### F6 anchor

SKILL.md:82-86:

```
Treat the file as the scope. No triage context — investigate from
scratch. Run the Investigation sub-steps of `/find-duplication` on
just that file. **Before any edits**, present the plan (file list,
fix shape, helper name) to the user and wait for confirmation.
```

(Comparator for the inlined questions, if wanted: find-duplication's Stage 4 verdict dimensions live in its `agents/investigate.md`; the review's proposed four questions — callers, divergence, canonical equivalent, test coverage — are consistent with the 2a/2b playbook needs.)

### F7 anchor

SKILL.md:75-76:

```
Find the matching cluster, extract file list + fix shape + helper
name. Proceed to Step 1.
```

### F8 anchor

SKILL.md:285-286:

```
Where `<shape>` is one of: `dedup`, `delete`, `fix`, `promote`,
`migrate`, `shadow`.
```

The eight shape names that must map (SKILL.md:132-139): Pure duplication, Three-way+ clone, Policy-flag clone, Template triplication, Shadow helper, Dead code, Quasi-dead / broken, Workflow registry cleanup.

### F9 anchors

- SKILL.md:153-156 (anchor on `**Forms B/C** → plan is an internal record; the user already`).
- SKILL.md:90-93 (Form C plan bullets) and SKILL.md:84-86 (Form B plan sentence).

### D2 anchor (insertion)

Between SKILL.md:36 and :38:

```
authorization for follow-on clusters or adjacent fixes.

Procedural detail lives in three knowledge files:
```

### D3 anchor (insertion into Step 7)

Full step quoted in D3. Anchor on the opening of item 1:

```
1. **Prevent recurrence.** If the fix shape generalizes (silent-catch,
   bare-int-on-request, shadow helper, etc.), suggest:
```

and/or the closing paragraph:

```
**Do NOT start the next cluster automatically.** Each cluster is a
separate authorization — and `/prevent-regression` is its own
authorization too; it builds a proposal but does not commit.
```

---

## 3. SCRIPT CONTRACTS

### scripts/log_effectiveness.py (exists; the only script invocation in the skill text)

Argparse contract derived from source (flag definitions lines 47-72; validation 75-81):

| Flag | Required | Notes |
|---|---|---|
| `--skill` | required | str |
| `--scan-id` | required | str |
| `--target` | required | str |
| `--findings-total` | required | `type=int` |
| `--buckets` | optional | default `"{}"`; must `json.loads` to a dict, else stderr `error: --buckets must be a JSON dict: ...` and **exit 1** (lines 75-81) |
| `--notes` | optional | default `""`; omitted from the entry when empty (lines 91-92) |
| `--log` | optional | default `reports/_meta/effectiveness.jsonl` (line 41); parent dir auto-created (line 94) |
| `--ts` | optional | ISO-8601 backfill override; default now-UTC (lines 68-72, 86) |

Exit 0 on success, printing `logged to {log}: {skill} / {scan_id}` (line 97). Appends one sorted-key JSON line. Special case: `--skill refactor-subsystem` additionally calls `skill_use.log_event` (lines 98-104) — not triggered by fix-workflow. Stdlib-only by design (docstring lines 21-23: "Stdlib-only — runs under `python3`, no venv required."); the `skill_use` import (line 38) is itself stdlib-only (`datetime`, `json`, `pathlib`, `typing`).

**Documented invocation at SKILL.md:276-282 vs contract, flag-by-flag:** `--skill fix-workflow` ✓; `--scan-id "cluster-$(git rev-parse --short HEAD)"` ✓ (free-form string accepted); `--target <primary-target-file>` ✓; `--findings-total 1` ✓ (int); `--buckets '{"<shape>": 1}'` ✓ (valid JSON dict once `<shape>` is substituted); `--notes "..."` ✓ (optional, supplied). All four required flags present; no documented flag is absent from argparse. `python3` is correct per the docstring. **The invocation is sound — F8's defect is the bucket vocabulary only, not the command.**

### Other commands the skill text tells an executor to run

- `fix-shapes.md:183-186` — `.venv/bin/python manage.py test ... --settings=app.settings_test_sqlite -v 2` — **no `manage.py` in this repo** (F4); host-only, unrunnable here.
- `fix-shapes.md:191` — `.venv/bin/python manage.py check` — same.
- `fix-shapes.md:146-147, 154-155` — `git grep` commands over nonexistent roots (F4).
- jscpd re-scan (SKILL.md:202-207; learnings.md R14) — **no command exists anywhere in the skill** (F1). Repo's real wrapper: `scripts/lint/run_jscpd.py` (exists).
- `.claude/skills/find-semantic-duplication/scripts/collapse_candidates.py` (SKILL.md:63) — referenced as explanation only, never invoked; exists.

### .claude/skills/track-idea/scripts/track.py

Exists. Subcommands from argparse source (subparsers at line 299, `dest="form", required=True`): **`intake`, `event`, `lesson`, `list`, `show`**. **There is no `note` subcommand** — if the change spec plans a ledger note, the actual surfaces are:

- `intake <slug> --title* --origin* --subsystem-kind* --summary* [--state (default proposed, choices)] [--quality-markers] [--feeds-into] [--composes-with] [--lineage-parents] [--tags] [--hypothesis]` (lines 301-314)
- `event <slug> --kind* (choices) [--from-state] [--to-state] [--outcome] [--markers-added] [--markers-removed] [--edges-added] [--adoption-evidence] [--summary]` (lines 316-327)
- `lesson <slug> --title* --body* [--generalizes-to]` (lines 329-334)

(`*` = required. Plus `list [--state] [--marker] [--subsystem]` and `show <idea_id> [--quiet-on-list-fields]`.)

---

## 4. POINTER + ARTIFACT-DRIFT AUDIT

### SKILL.md pointers

| Pointer (line) | Status |
|---|---|
| `knowledge/fix-shapes.md` (40, 163) | EXISTS |
| bare `knowledge/` (42, 116, 199, 206, 221, 334) | directory exists; promised file does NOT (F1) |
| `knowledge/learnings.md` (44, 263-265) | EXISTS; R1–R14 present and complete |
| `.claude/skills/_common/interface-depth.md` (46) | EXISTS |
| `reports/dormant/latest/report.md` (58) | dir missing now — runtime artifact; **name correct** (find-dormant SKILL.md:80-82 creates `reports/dormant/scan-${TS}` + `latest`; writes `report.md` at :226/:232) |
| `reports/semantic-duplication/latest/triage.md` (59) | dir missing now — runtime artifact; **name correct** (find-semantic-duplication SKILL.md:68-71; `triage.md` at :220/:226) |
| `.claude/skills/find-semantic-duplication/scripts/collapse_candidates.py` (63) | EXISTS |
| `reports/duplication/latest/triage.md` (68) | dir missing now — runtime artifact; **name correct** (find-duplication Stage 0 :60-63; `triage.md` at Stage 5 :152/:159) |
| `core/services/parse_json_body_helper.py` (80) | host path — MISSING in this repo |
| `testing/test_site_pages.py` (189) | host path — MISSING |
| `core/services/ai_sidecar/` (190) | host path — MISSING |
| `reports/duplication/latest/jscpd/` (205) | runtime artifact of find-duplication; name correct |
| `reports/duplication/learnings.md` (3, 235, 263) | MISSING; no producer anywhere; parent dir missing; gitignored (D1/F3) |
| `reports/_meta/dashboard.md` (270) | EXISTS |
| `.claude/skills/_common/skill-conventions.md` (273) | EXISTS |
| `scripts/log_effectiveness.py` (276) | EXISTS |
| Skill names: `/find-duplication`, `/find-dormant`, `/find-semantic-duplication`, `/find-layer-violation`, `/refactor-subsystem`, `/decide`, `/prevent-regression` | all EXIST under `.claude/skills/` |
| Section refs `fix-shapes.md §2a/§2b` (66-67), `(2a / 2b / 2c / 2d)` (163) | sections EXIST (fix-shapes.md headings at 20, 82, 133, 203) |
| Rule refs R1 (215), R11 (303), R12 (354), R14 (207) | all EXIST in knowledge/learnings.md |

Internal-consistency drift found while auditing (useful to the spec): SKILL.md:38 says "three knowledge files" over a four-bullet list; SKILL.md:40 ("seven shapes") and :366 ("7 shapes") contradict the eight-row Step-1 table (130-139) — the registry shape was added without updating the counts; fix-shapes.md's own mapping table (6-13) omits the registry shape.

### knowledge/fix-shapes.md pointers

| Pointer (line) | Status |
|---|---|
| `.claude/skills/_common/interface-depth.md` (26) | EXISTS |
| `learnings.md` rule refs — R6 (37), R3 (43), R7 (85) | EXIST |
| bare `knowledge/` test matrix (66) | broken (F1) |
| `core/ templates/ static/ urls.py admin.py management/commands/ frontend/` (146-147, 154-155) | ALL host paths — MISSING here |
| `core/urls.py`, `core/admin.py` (169-170) | host — MISSING |
| `manage.py`, `app.settings_test_sqlite`, `tests.test_site_capabilities`, `tests.test_hydration_detector` (183-186, 191, 197) | host — MISSING |

### knowledge/learnings.md pointers

| Pointer (line) | Status |
|---|---|
| bare `knowledge/` test matrix (112) | broken (F1) |
| `reports/duplication/latest/jscpd/` (160) | runtime artifact; name correct |
| `tests_custom_site` (143) | host test module — MISSING here |
| "Step 3" cross-ref (155) | matches SKILL.md Step 3 / jscpd subsection (193/202) |

### reports/ ground truth

`reports/` exists with 24 subdirs (`_meta`, `which-cleanup`, assorted find-* outputs); **none of** `reports/duplication/`, `reports/dormant/`, `reports/semantic-duplication/`, `reports/layer-violation/` exist right now — all four are runtime products of their detection skills. Only `reports/duplication/learnings.md` is defective (no producer ever); the other three pointers are correct-by-construction handoff names, and the skill's missing-report abort (SKILL.md:70-73) already handles their absence. `.gitignore:21-22` ignores `/reports/*` except `/reports/_meta/`.

---

## 5. LOAD-BEARING AUDIT

Every mandated step in SKILL.md and its downstream consumer:

| Mandated step (SKILL.md lines) | Downstream consumer | Wired? |
|---|---|---|
| Form A report load (58-68) | Step 1 classification + file list | Wired; `layer:` route absent (F2) |
| Missing-report abort (70-73) | terminal user message | Wired; no ID-not-found branch (F7) |
| Form B/C plan + approval-token contract (84-86, 90-97, 99-108) | gate before any edit | Wired, self-contained; ordering contradiction with Step 1 (F9) |
| Cleanliness guard (115-117) | should gate start of work | NOT wired — delegated to nonexistent file (F1); improvisation point |
| Step-1 execution plan (141-151) | Step 4 `git status` + `git diff --stat` file-list check (230-231); 2a stop condition "`git diff --stat` shows only the files you planned to touch" (fix-shapes.md:78) | Wired |
| Interface-depth note in plan (146-148) | 2a stop-condition deletion-test box (fix-shapes.md:75-76) | Wired |
| Step-2 playbook stop conditions (163-165 → fix-shapes.md 71-78, 123-129, 194-199, 238-244) | Step 3 precondition (195) | Wired for 2a/2b/2d; 2c's boxes unexecutable off-host (F4); registry shape has NO stop condition (F5) |
| Registry checklist characterization tests (172-174) | nothing checks them — no stop-condition block | NOT wired (F5) |
| Step-3 test matrix (198-200) | commit gate ("**Post:** targeted test suites green", 196) | Gate exists, source artifact missing (F1) — hallucination point |
| jscpd re-scan (202-207) | R14 success judgment (learnings.md:153-162) | Half-wired: command missing (F1); no mandated artifact records before/after clone counts, so skipping is undetectable downstream |
| Step-4 git safety + diff check (223-231) | the commit itself | Wired (consumes Step-1 plan) |
| Step-5 learnings entry (235-260) | within-run: hosts Step 6's follow-on findings (301-303), which feed Step 7's recommendation (321-322) and the user's next choice (R11). Cross-run: **no consumer found** — zero readers of `reports/duplication/learnings.md`; file gitignored | Human-consumed within the run only (D1/F3) |
| Running LOC delta table (262-263) | **no consumer found** (repo-wide grep, scripts + skills + docs) | Pure ceremony as written (D1) |
| knowledge/learnings.md promotion callout (264-267) | human decision → `knowledge/learnings.md`, which future runs read (44-45) and fix-shapes.md cites (R3/R6/R7) | Wired — the only learnings surface with a real consumer |
| Effectiveness log (269-286) | `scripts/skill_effectiveness.py` (renders `reports/_meta/dashboard.md` — its docstring lines 2-5), `scripts/triage_audit.py`, `scripts/host_attest.py`, `/which-cleanup` (SKILL.md:104, 133-134; `scripts/run.py:86 _log_effectiveness`) | Wired, multiple consumers; bucket vocabulary under-covers the 8 shapes (F8) |
| Step-6 follow-on findings (288-303) | Step 7 recommendation + user's next-cluster choice | Wired within run; persisted only into the orphan file (D1 caveat) |
| Step-7 recommendation (305-328) | terminal user output | Wired as advice; no class-lift gate (D3) |

**Wired-vs-ceremony split:** the approval gates, Step-1 plan → Step-4 diff check, the 2a/2b/2d stop conditions, and the effectiveness log are genuinely wired. The cleanliness guard, test matrix, jscpd command, and commit template all dead-end into the missing knowledge file (F1). The cross-cluster learnings file and its LOC table have no consumer anywhere (D1). The registry checklist (F5) and the `layer:` entry point (F2) are gates/routes added or referenced upstream without being wired here.
