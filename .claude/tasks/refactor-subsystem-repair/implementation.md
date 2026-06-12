# Implementation report — /refactor-subsystem repair (C1–C10)

Implementer run, 2026-06-12. All paths relative to repo root. Line
numbers refer to the files AFTER the edits. Working tree left dirty
(no commits), per instructions.

Files touched:

- `.claude/skills/refactor-subsystem/knowledge/operations.md` — NEW
- `.claude/skills/refactor-subsystem/SKILL.md`
- `.claude/skills/refactor-subsystem/knowledge/execution-playbook.md`
- `.claude/skills/refactor-subsystem/knowledge/learnings.md`
- `.claude/skills/refactor-subsystem/agents/inventory-scout.md`
- `.claude/skills/refactor-subsystem/agents/micro-fix-scout.md`

---

## C1 — Missing operations content (F1 + F8) — DONE

**Created `knowledge/operations.md`** (new file, ~200 lines). Every
sentence traces to scout.md §4 fragments, SKILL.md inline summaries,
or a script contract I verified against argparse/output code:

- *Worktree and venv rules* — from SKILL.md §Scope inline summary,
  the venv-check snippet (SKILL.md §1.1), and L-1/L-16 one-liners
  (learnings.md L-index). The `{{venv}}` example values come from
  inventory-scout.md:25.
- *Scripts* — subcommands/flags verified against `scripts/specs.py`
  (argparse :2141–2206), `scripts/ledger.py` (`--next-review-days`,
  :613; upsert note from SKILL.md 7.2), `scripts/chunk_file.py`
  (argparse :352–368). The "writes to stdout" notes verified against
  `cmd_solid` (specs.py:740–743) and `cmd_violations`
  (specs.py:1679–1696).
- *Cleanliness guard* — authored as the current-worktree dirty check
  in the "run from repo root" form (`cd "$(git rev-parse
  --show-toplevel)"`), with the grep shape generalized from the
  execution-playbook §5.2 fragment. Explicitly distinguished from the
  §5.2 main-worktree collision check (scout surprise 5 — the two are
  NOT conflated; the guard section cross-references the playbook for
  the second check).
- *Archaeology recipe* — triggers/thresholds (≤500 LOC ∧ ≤20 commits
  → scout inline; else orchestrator-parallel; ≥50 commits mandatory,
  ≥3 LR-T candidates) from SKILL.md §1.4 + R4/R17; ownership
  mechanics (chunk-map column, `archaeology_owner` JSON key, L-7
  churn split) from SKILL.md §1.3/§1.3.0; scout-side commands
  verbatim from inventory-scout.md:189–195; honest statement that no
  orchestrator-side variant survives (the orchestrator runs the same
  commands); tag convention from Bucket 4 + R4/R17 +
  skill-conventions.md:114; L-25 calibration point (102 commits → 7
  load-bearing).
- *Subject-word filter* — only the four known terms
  (`fix|retry|timeout|crash`); the regex is followed by an explicit
  `<!-- host-adapter: extend subject-word list ... the full list is
  lost -->` slot, per the change-spec (no complete list exists in any
  fragment — confirmed by the scout's repo-wide grep).
- *Archaeology report schema* — derived from inventory-scout.md's
  Output-3 LR-T entry shape (heading, `**File:** path:line`, italic
  one-line summary, `**Behavior:**`, `<!-- archaeology: <hash> -->`,
  `**Proposed text:**`) — exactly the derivation the change-spec
  authorizes. Notes the scout-run path (entries go to Output 3) and
  the §3.3 `**Archaeology:**` consumer.
- *Report directory layout* — Written-by/Consumed-by table derived
  from scout §3 (load-bearing audit). Canonizes the two
  previously-broken edges: `inventory/chunks.jsonl` (producer = 1.3.0
  orchestrator manifest, per C10) and `phase-6-solid.json` (producer =
  redirected `solid --json`, per C10); includes `phase-6-boundary.md`
  (C3). Outside-the-tree artifacts (characterization tests,
  duplication learnings, effectiveness.jsonl) listed from SKILL.md
  2.1/7.3/7.5.
- *Verification test matrix* — fragments supply no matrix, so the
  section is a `<!-- host-adapter: test matrix ... -->` slot with the
  origin project's baseline suites + runner command kept as the
  worked example, followed by three host-independent invariants all
  sourced from SKILL.md/playbook text.

**Pointer rewrites** (every bare `knowledge/` reference, scout §2
items 1–10):

- SKILL.md:50–52 (knowledge-file list bullet) → names
  `knowledge/operations.md` with its real contents.
- SKILL.md:118 (Scope intro), :129 (cleanliness guard), :550 (§1.4
  recipe), :560+:563 (§1.4 filter + schema), :651 (§2.2 report
  layout) → all now `knowledge/operations.md`.
- agents/inventory-scout.md:25 and agents/micro-fix-scout.md:28
  `{{venv}}` source column → `knowledge/operations.md`.
- learnings.md L-index rows L-1 (:549) and L-16 (:562) →
  `(knowledge/operations.md)`.

**Count fixes** (all four surfaces from scout surprise 4):

- SKILL.md:47–48: "five knowledge files (plus one shared rubric in
  `_common/`)" — now literally true (5 files in knowledge/, 6th
  bullet is the `_common` rubric, called out as such).
- SKILL.md:60: "44 rules (R1–R44)".
- SKILL.md 7.3 template: "R1-R44".
- learnings.md:1 title: "(R1-R44)".
- Repository layout block: gains `operations.md`, learnings comment
  now "R1–R44".

Judgment calls: (a) the guard command's grep target is written as the
placeholder `'<code_roots regex>'`, matching the playbook's existing
placeholder style, rather than inventing a concrete regex; (b) left
learnings.md's R36-before-R35 ordering untouched (harmless; "do not
restructure"); (c) the agents' `{{worktree}}` Example-column value
`~/Projects/your-project` was left as-is — it is an example output of
`git rev-parse --show-toplevel`, not a command, and C1's
generalization mandate targeted the guard commands.

## C2 — Decomposition behavior gate (F2) — DONE

- (a) SKILL.md §3.2 plan item 7 (:778–783): test strategy per batch
  now requires grep evidence that at least one named suite
  imports/patches each batch's destination modules (R36 generalized);
  the plan shows the grep output; the Phase 4 reviewer approves
  coverage, not suite names; empty grep = no test strategy yet.
- (b) execution-playbook §5.2 step 4 (:56–63): per-batch re-check of
  the coverage-path proof before running the suite (grep for import /
  `from ... import` / `patch("...")` into each destination module;
  empty grep → stop, fix the test strategy).
- (c) SKILL.md §2.1 decomposition-characterization paragraph
  (:616–618): added "Structure pinning is sufficient ONLY with the
  per-batch coverage-path proof (plan item 7, R36): never trust green
  from a suite with no path into the moved code."

## C3 — Ownership-boundary scan made load-bearing (F3) — DONE

- SKILL.md §6.0 (:991–1001): Phase 6.0 now writes
  `reports/refactor/<spec-id>/phase-6-boundary.md` (scan commands
  run, every hit, target-clean vs repo-has-findings classification).
  Gate sentence: known findings inside the named ownership family
  BLOCK Phase 7 unless explicitly waived in the Phase 4 sign-off
  block (reusing the existing **Approved scope** / **Not approved
  (deferred)** lines — no new machinery).
- SKILL.md Phase 7 head (:1162–1166): entry conditions name the
  artifact (`phase-6-boundary.md` exists and is clean or waived),
  plus the already-existing 6.1.5/6.2 gates.
- The artifact also appears in operations.md's layout table
  (consumer: Phase 7 entry gate) and the C9 preamble.

## C4 — Follow-up intake (F4) — DONE

- SKILL.md 7.2 (:1197–1200): "Every Phase 6.3 / 6.3.5 FAIL or
  ADVISORY verdict flagged as a follow-up becomes a ledger `monitor`
  entry here, or a named open item in the learnings entry (7.3), so
  the next maintainer knows what's still open."
- SKILL.md 7.3 (:1246–1248): verdicts not already routed to the
  ledger at 7.2 become named open items in the learnings entry —
  same "so the next maintainer knows what's still open" pattern
  copied from 7.4. Two sentences total; no new machinery.

## C5 — Threshold contradiction (F5) — DONE

execution-playbook §5.4 pseudo-code (:306–336) rewritten:
`count < 5` → `fix_inline_sequentially` (orchestrator, matching the
1–4 table row); `elif count <= 10` → micro-fix swarm; `else` (11+) →
ledger `split_queued` follow-up. Comments cite the decision table.

Judgment call (grounded in specs.py:1679–1694, flagged by scout
surprise 2): the pseudo-code previously iterated a phantom
`by_file`-keyed shape matching neither the script nor §5.4's own
documented shape. While editing the block I aligned it to the real
`--json` output (`violations_json["items"]`, flat
`item["violations"]` list, orchestrator-side `group_by_file` for
swarm dispatch) and fixed the latent `f"AR-{item_id}"` double-prefix
(item_id already carries "AR-"). I also replaced §5.3.5's documented
input JSON example (the other half of the same phantom shape, EP
:118–143) with the real shape plus the sentence "the orchestrator
groups each item's `violations` by `file` to build the per-file
dispatch tuples." Leaving either would have left documentation
contradicting the verified script contract inside the very block C5
edits.

## C6 — Phantom flag (F6) — DONE

execution-playbook §5.4 escape hatch (:354–361): the
`--enforce-inline` sentence is gone. Replacement: count-independent
inline enforcement is a Phase 4 sign-off scope item (the same §5.4
mechanism as repo-wide enforcement, recorded in **Approved scope**),
"never an executor-claimed flag; no script implements one." The
"use sparingly" caution is preserved.

## C7 — Resume protocol (F7) — DONE

- SKILL.md "Resuming mid-refactor" (:133–154), placed immediately
  after §Scope: (1) infer phase via `specs.py coverage` +
  `ls reports/refactor/<spec-id>/` against operations.md's layout;
  (2) re-read that phase's knowledge file (Phase 5 →
  execution-playbook IN FULL); (3) restate approved scope and waivers
  from phase-3-plan.md §Sign-off before any edit; (4) re-arm beliefs
  3/4 (unknown code STAYS; deletion needs recorded human approval);
  (5) re-run the cleanliness guard.
- Cross-referenced from the Phase 5 opening line (:952–954).

## C8 — Host-adapter slots (F9) — DONE

- SKILL.md §1.2 conditional doc list (:326–330): `<!-- host-adapter:
  conditional doc list ... Worked example: -->` comment above the
  origin project's mapping, which is kept as the worked example.
- SKILL.md §6.1 (:1011–1021): prose marks the baseline suite names as
  the ORIGIN project's worked example pointing at operations.md's
  host-adapter slot; a `# host-adapter:` comment sits directly in the
  bash block above the two suite names.
- operations.md carries the matching "Verification test matrix"
  host-adapter slot (see C1).

## C9 — Declared-verdict preamble — DONE

SKILL.md :34–45, directly after the deliverable statement: "**How
success is judged.**" block — characterization suite green at HEAD /
per batch / at 6.1; per-batch coverage-path proof (R36);
`phase-6-boundary.md` clean or waived; sign-off scope honored
token-for-token; knowledge pointers must resolve, dangling pointer →
STOP and flag, do not improvise. 12 non-blank lines; framed as the
optimization target, not a new section.

## C10 — Scout-found artifact drift — DONE (all four)

1. **`chunks.jsonl`** — inspected `scripts/chunk_file.py`
   (:280–298, :350–368): it emits ONE per-file JSON object with raw
   `chunks[].id` keys and no `archaeology_owner`/`chunk_id`/per-chunk
   `file` — it cannot produce the manifest the dispatch loop reads.
   Smallest edit matching reality: mandated an orchestrator step in
   §1.3.0 (SKILL.md :467–481) that writes
   `inventory/chunks.jsonl` from the chunk map in the same pass that
   basename-qualifies IDs (R35) and assigns archaeology owners. The
   example object's keys (`chunk_id`, `file`, `line_start`,
   `line_end`, `declarations`, `archaeology_owner`) match exactly the
   `jq` reads in the §1.3 dispatch loop. (Repointing the loop at the
   per-file `__chunks.json` files would have required reshaping every
   jq read and still lacked `archaeology_owner` — larger edit.)
2. **`phase-6-solid.json`** — inspected `cmd_solid`
   (specs.py:740–743): `--json` dumps to stdout, writes no file.
   SKILL.md §6.3 code block (:1088–1095) now mandates the redirect
   (`solid <spec-id> --json > reports/refactor/<spec-id>/
   phase-6-solid.json`, explicitly mirroring §5.4's violations
   pattern), and the L3 scout paragraph (:1111–1114) reads the full
   path "redirected above".
3. **Swarm wrapper** — SKILL.md :540–545 reworded: the same
   subprocess pattern works for the 5.3.5 swarm when nested
   (dispatch `agents/micro-fix-scout.md` through `dispatch_scout.sh`);
   the swarm's actual dispatch protocol and guardrails live in
   execution-playbook §5.3.5; "there is no separate subprocess
   wrapper script for it" — stated, not papered over.
4. **`--next-review`** — execution-playbook §5.5 (:411) now
   `--next-review-days 180`, verified against ledger.py:613
   (`--next-review-days`, type=int; no `--next-review` exists).

Bonus C1-scoped fix in the same area (scout surprise 5):
execution-playbook §5.2 step 0's hardcoded
`git -C ~/Projects/your-project` generalized to
`git -C <main-worktree-path>` with the derivation comment ("first
entry in `git worktree list`" — documented git behavior) and a
one-line note distinguishing it from the operations.md cleanliness
guard.

---

## Self-consistency sweep — PASSED

- `grep -rn 'knowledge/'` across the skill directory: every reference
  names one of the five real files (operations / execution-playbook /
  solid-gate-tests / bootstrap / learnings); zero bare-`knowledge/`
  pointers remain.
- `ls knowledge/` = exactly five files; SKILL.md:47 claims five (the
  sixth bullet is explicitly the `_common` rubric).
- No `R1-R36` / `R1-R43` / "36 rules" anywhere; learnings.md title,
  SKILL.md list bullet, 7.3 template, and Repository layout all say
  R1–R44 (the file's actual highest rule, R44 at learnings.md:504).
- No `--enforce-inline`, no `--next-review <+180d>`, no phantom
  `by_file` JSON shape (remaining `by_file` hits are the new local
  variable built by `group_by_file`).
- Producer/consumer pairs close: `chunks.jsonl` (1.3.0 → §1.3 loop),
  `phase-6-solid.json` (6.3 redirect → L3 scout),
  `phase-6-boundary.md` (6.0 → Phase 7 entry gate), all also listed
  in operations.md's layout table.
- Both agents/ templates source `{{venv}}` from
  `knowledge/operations.md`; learnings.md L-1/L-16 resolve there too.

## OPEN / flagged (not blockers)

- **Full subject-word regex** — unrecoverable; only
  `fix|retry|timeout|crash` survives anywhere in the repo. Handled as
  an explicit host-adapter slot in operations.md (authorized by the
  change-spec), with SKILL.md §1.4's summary un-elided to "known
  terms" + pointer to the slot. Honest gap, not filler.
- **Test matrix** — no fragment supplies one; host-adapter slot in
  operations.md with the origin baseline suites + runner as the
  worked example.
- **`.claude/contracts/skills/refactor-subsystem.yaml` and
  `.claude/docs/skill-catalog.md:246`** — checked both; neither
  names knowledge-file counts, R-ranges, or the repaired artifacts,
  so no consistency edit was needed. If a later change advertises the
  new boundary gate externally, `/check-ecosystem-consistency` is the
  named follow-up (scout surprise 6).
- Verification run: consistency greps only (this is a docs/skill
  surface; no automated test suite applies). Nothing committed —
  working tree left dirty for review.
