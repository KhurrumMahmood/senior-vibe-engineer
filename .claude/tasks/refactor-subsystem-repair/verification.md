# Verification report — /refactor-subsystem repair

Verifier run, 2026-06-12. Independent, no implementer context shared.
Inputs read in mandated order: frame review (F1–F9), change-spec
(C1–C10 + declared verdict), scout.md (§2/§3/§4), all repaired files,
implementation.md (claims verified, not trusted). Script contracts
re-verified directly against `scripts/specs.py`, `scripts/ledger.py`,
`scripts/chunk_file.py`. `git diff HEAD` reviewed in full for all five
modified files plus the new `knowledge/operations.md`. Read-only run;
this report is the only file written.

## Per-finding verdict table

| Finding | Verdict | Evidence (post-repair file:line) |
|---|---|---|
| F1 — dangling `knowledge/` pointer family | **RESOLVED** | `knowledge/operations.md` created (worktree/venv :11–34, scripts :36–50, guard :52–73, archaeology recipe :75–120, schema :122–144, layout :146–176, test matrix :178–197). All ten scout-§2 bare pointers rewritten: SKILL.md:49, :118, :128, :549, :557–562, :650, inventory-scout.md:25, micro-fix-scout.md:28, learnings.md:549, :562. Repo-wide grep: zero bare-`knowledge/` references remain (only the directory line in the layout tree, SKILL.md:1334). |
| F2 — decomposition pins structure, never verifies suite path | **RESOLVED** | (a) plan item 7 requires grep evidence, reviewer approves coverage not suite names, empty grep = no strategy (SKILL.md:778–783); (b) per-batch re-check before running the suite (execution-playbook:57–63); (c) L-44 paragraph: "Structure pinning is sufficient ONLY with the per-batch coverage-path proof … never trust green from a suite with no path into the moved code" (SKILL.md:616–618). R36 citation verified against learnings.md:376–395. |
| F3 — Phase 6.0 output feeds nothing | **RESOLVED** | 6.0 writes `phase-6-boundary.md` (commands, hits, classification) with explicit BLOCK-Phase-7 gate waivable only via the existing Phase 4 sign-off block (SKILL.md:991–1002); Phase 7 entry conditions name the artifact (SKILL.md:1162–1166); producer/consumer row in operations.md:166. |
| F4 — "Phase 7 follow-ups" had no intake | **RESOLVED** | 7.2: every 6.3/6.3.5 FAIL/ADVISORY → ledger `monitor` entry or named open item (SKILL.md:1197–1200); 7.3: not-yet-routed verdicts → named open items, copying 7.4's "so the next maintainer knows what's still open" pattern (SKILL.md:1246–1248). Two sentences, no new machinery — as specified. |
| F5 — §5.4 pseudo-code contradicts decision table | **RESOLVED** | Pseudo-code branches `count < 5` → `fix_inline_sequentially`, `elif count <= 10` → swarm, `else` → `split_queued` ledger entry, comments citing the table (execution-playbook:306–336). Matches the 1–4 / 5–10 / 11+ table at :292–297. |
| F6 — phantom `--enforce-inline` flag | **RESOLVED** | Sentence removed; replaced by "a Phase 4 decision, not a flag … never an executor-claimed flag; no script implements one" using the existing §5.4 sign-off mechanism (execution-playbook:343–350). Grep over the skill dir: zero `enforce-inline` hits. |
| F7 — no frame-resume protocol | **RESOLVED** | "Resuming mid-refactor" placed directly after §Scope with all five C7 steps — infer phase via `specs.py coverage` + `ls reports/refactor/<id>/` against the operations.md layout, re-read the phase's knowledge file (Phase 5 IN FULL), restate sign-off scope/waivers, re-arm beliefs 3/4, re-run cleanliness guard (SKILL.md:133–153). Cross-referenced from the Phase 5 opening line (SKILL.md:952–954). |
| F8 — count drift (five files / R1–R36 / R1-R43) | **RESOLVED** | All four scout-surprise-4 surfaces: "five knowledge files (plus one shared rubric in `_common/`)" now literally true (SKILL.md:46–47, `ls knowledge/` = 5 files); "44 rules (R1–R44)" (SKILL.md:60); 7.3 template "R1-R44" (SKILL.md:1243); learnings.md:1 title "(R1-R44)" (R44 verified present at learnings.md:503); Repository layout gains operations.md and says R1–R44 (SKILL.md:1335, :1339). Zero `R1-R36`/`R1-R43`/"36 rules" hits remain. |
| F9 — host-specific gates hard-coded | **RESOLVED** (declared scope) | §1.2 conditional doc list under `<!-- host-adapter: conditional doc list … Worked example: -->` (SKILL.md:326–329); 6.1 baseline marked as ORIGIN worked example with in-block `# host-adapter:` comment and pointer to operations.md's "Verification test matrix" slot (SKILL.md:1011–1020); matching slot at operations.md:180–186. See residual note 2 below. |
| C10.1 — `chunks.jsonl` no producer | **RESOLVED** | §1.3.0 mandates the orchestrator-built manifest with a worked example object (SKILL.md:467–480); keys `chunk_id/file/line_start/line_end/declarations/archaeology_owner` match the §1.3 loop's six `jq` reads exactly (SKILL.md:514–526). The inline claim about `chunk_file.py` verified against the script: it returns one per-file object with raw `chunks[].id` (`C-{i:02d}`) and no `archaeology_owner` (chunk_file.py:275–298) — repointing would indeed have been the larger edit. |
| C10.2 — `phase-6-solid.json` never written | **RESOLVED** | 6.3 code block mandates the redirect (SKILL.md:1093–1095); L3 scout paragraph reads the full path "redirected above" (SKILL.md:1112–1114). Verified `cmd_solid --json` dumps to stdout only (specs.py:740–743). |
| C10.3 — phantom "swarm-specific wrapper" | **RESOLVED** | Reworded to what exists: dispatch `agents/micro-fix-scout.md` through `dispatch_scout.sh` when nested; protocol/guardrails in playbook §5.3.5; "there is no separate subprocess wrapper script for it" — honest, not papered over (SKILL.md:540–545). |
| C10.4 — phantom `--next-review <+180d>` | **RESOLVED** | Now `--next-review-days 180` (execution-playbook:362). Verified against ledger.py:613 (`--next-review-days`, type=int; no `--next-review` flag; `update` is an upsert and no `add` subcommand exists — ledger.py:603, subparser list checked). |

C1–C9 are subsumed: C1 = F1+F8 rows; C2 = F2; C3 = F3; C4 = F4; C5 =
F5; C6 = F6; C7 = F7; C8 = F9; C9 verified separately below.

**C9 (declared-verdict preamble): RESOLVED.** "How success is judged"
block at SKILL.md:34–44, directly after the deliverable statement; 11
content lines (≤12). Every gate it names exists in the repaired text:
characterization at HEAD/per-batch/6.1 (2.1, EP §5.2.5, 6.1),
coverage-path proof (item 7 + EP §5.2.4), boundary artifact + waiver
(6.0/Phase 7 entry), token-anchored sign-off (4.2/4.3), and the
no-improvised-recipe STOP rule. No gate is claimed that doesn't exist.

## No-invention audit — `knowledge/operations.md`: PASS

Every substantive claim traced to a scout-§4 fragment, a SKILL.md
inline summary, or a script contract I verified directly:

- **Worktree/venv rules** — SKILL.md Scope summary (pre-existing at
  HEAD, confirmed via `git show`), the §1.1 venv-check snippet
  (verbatim), L-1/L-16 one-liners, `{{venv}}`/`{{worktree}}` example
  values from the agents' placeholder tables. Traced.
- **Scripts section** — all subcommands/flags verified against
  argparse: specs.py show/coverage/inventory-check(`--strict`)/
  solid(`--json`)/violations(`--json`) at specs.py:2141–2206; ledger
  `list --decision`, `update --decision --rationale
  [--next-review-days <int>]`, upsert/no-`add` (ledger.py:584–637);
  chunk_file `--token-budget/--loc-budget/--loc-hints/--format/
  --output` (chunk_file.py:350–368). The "writes to stdout" claims
  verified for both `solid --json` (specs.py:740–743) and
  `violations --json` (specs.py:1679–1696). All true.
- **Cleanliness guard** — authored content, but explicitly authorized
  by C1 ("generalize the hardcoded … to the run-from-repo-root form");
  uses the playbook's existing `'<code_roots regex>'` placeholder style
  rather than inventing a concrete regex; correctly kept distinct from
  the §5.2 main-worktree collision check (scout surprise 5 honored —
  the two checks are cross-referenced, not conflated).
- **Archaeology recipe** — triggers/thresholds from SKILL §1.4 + R4 +
  R17 (verbatim match); commands verbatim from inventory-scout.md
  scout-side block; honest statement that no orchestrator-side variant
  survives; tag convention from Bucket 4 + skill-conventions.md:114;
  L-25 calibration point. Subject-word regex contains ONLY the four
  surviving terms with the mandated `<!-- host-adapter: extend
  subject-word list … the full list is lost -->` slot — honest gap,
  not filler.
- **Archaeology report schema** — exact derivation the change-spec
  authorizes: the entry shape (### name / `**File:** path:line` /
  italic summary / `**Behavior:**` / hash comment / `**Proposed
  text:**`) matches inventory-scout.md's Output-3 R16-addendum format
  field-for-field, plus the Bucket-4 hash-tag rule. Not invented.
- **Report directory layout** — every Written-by/Consumed-by row
  traces to a scout-§3 audit row; the two previously-broken edges
  (`chunks.jsonl`, `phase-6-solid.json`) are canonized consistently
  with the C10 fixes, and `phase-6-boundary.md` consistently with C3.
- **Verification test matrix** — honest host-adapter slot (fragments
  supply no matrix); origin baseline + runner kept as worked example;
  the three host-independent invariants all trace to SKILL.md/playbook
  text.

Two minimal constructions, both acceptable, neither disguised:

1. The concrete filter command `git log --follow --oneline <file> |
   grep -iE 'fix|retry|timeout|crash'` (operations.md:105) — the
   fragments give the filter terms and the `--oneline` command but not
   the pipe-to-grep glue or the `-i` flag. This is the minimal faithful
   realization of "subject-word filter applied to commit subjects,"
   sits directly above the honest host-adapter slot, and adds no
   unsourced terms. Not a blocking invention.
2. EP:35's "`<main-worktree-path>` = the first entry in `git worktree
   list`" — not from a fragment, but a true, verifiable git contract
   (main worktree always listed first), used to generalize the
   hardcoded `~/Projects/your-project` C1 targeted. Acceptable
   real-contract grounding.

## New-defect sweep: PASS

- **Pointer integrity:** repo-grep of the skill directory — every
  `knowledge/` reference names one of the five real files; zero bare
  pointers. All section-name pointers resolve ("Report directory
  layout" and "Verification test matrix" exist as headings in
  operations.md). `_common/skill-conventions.md`,
  `_common/interface-depth.md`, both agents files exist.
- **Producer/consumer closure:** `chunks.jsonl` (1.3.0 → §1.3 loop),
  `phase-6-solid.json` (6.3 redirect → L3 scout),
  `phase-6-boundary.md` (6.0 → Phase 7 entry gate),
  `phase-6-solid-agent.md` / `phase-6-interface-depth.md` (→ 7.2/7.3
  intake) — all closed, and all consistent with operations.md's table.
- **Counts:** five knowledge files everywhere (list, `ls`, repo
  layout); R1–R44 on all four surfaces; R44 exists. SKILL.md:196's R44
  citation no longer contradicts anything.
- **Phantom flags/shapes:** no `--enforce-inline`, no `--next-review
  <+180d>`; the EP §5.3.5 input example and §5.4 pseudo-code now both
  match the script's real `--json` shape (re-derived independently
  from specs.py:1558–1696, incl. `violations[].{file,line,text}` keys
  and the absence of any `by_file` key); the implementer's extra
  shape-alignment edits and the `f"AR-{item_id}"` double-prefix fix
  were sanctioned by scout surprise 2 / the change-spec's
  align-with-executable-reality doctrine, and are correct.
- **Diff scope:** `git diff HEAD` over the skill directory contains
  only repair-scoped changes (C1–C10 + the two scout-flagged surprise
  fixes). bootstrap.md and solid-gate-tests.md untouched. No phase
  renumbering; voice/format preserved. External surfaces checked:
  `.claude/contracts/skills/refactor-subsystem.yaml` and
  `skill-catalog.md` carry no knowledge-file counts or R-ranges — no
  consistency edit owed.

### Non-blocking residual notes (pre-existing, outside declared scope)

1. **Same-class host literals survive outside C8's scope:** EP §5.3.5
   step 3's baseline suite (`tests.test_site_capabilities
   tests.test_hydration_detector`, EP:221), the §5.3.5
   verification-cmd cheap defaults, and the
   `--settings=app.settings_test_sqlite` runner strings throughout
   SKILL.md 2.1/6.1 and the playbook. F9 named only the 6.1 baseline
   and the §1.2 doc list; these were at HEAD and were not in C8. A
   future pass could route them at the operations.md test-matrix slot.
2. **§5.3.5 trigger "5+ instances → dispatch swarm" vs §5.4's 11+
   deferral row** — a pre-existing tension F5 did not cover; the §5.4
   table/pseudo-code now unambiguously govern the decision point, so
   the copyable form is correct.
3. **SKILL.md 7.2 invokes ledger via `.venv/bin/python` while
   Scope/operations.md say plain `python3`** — pre-existing at HEAD
   (verified via `git show`), harmless (script is stdlib-only).

## Overall verdict: **PASS (commit-ready)**

All of F1–F9 and all four C10 items RESOLVED against the declared
verdict: every knowledge pointer grep-resolves to real content, every
mandated artifact names a producer and a consumer, all counts match
the files, and operations.md contains nothing untraceable — its two
gaps (subject-word list, test matrix) are explicit host-adapter slots,
not disguised filler. The three residual notes above are pre-existing,
outside the change-spec's declared scope, and do not block commit.
