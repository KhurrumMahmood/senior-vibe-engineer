# Scout report — /refactor-subsystem repair

Scouted 2026-06-12. All paths relative to repo root
`~/Projects/engineering-skills`. Skill root:
`.claude/skills/refactor-subsystem/`. Line numbers are from the files as
they stand on `main` (clean tree, HEAD 975362c). Companion documents:
`reports/skill-frame-review/refactor-subsystem.md` (findings F1–F9) and
`.claude/tasks/refactor-subsystem-repair/change-spec.md` (C1–C9).

Git-history fact (load-bearing for C1): across **every commit in this
repo** (`git ls-tree` over all revisions), `knowledge/` has only ever
contained `bootstrap.md`, `execution-playbook.md`, `learnings.md`,
`solid-gate-tests.md`. The fifth "operations" file never existed here —
it cannot be recovered from history; it must be assembled from the
fragments in §4 below.

## 1. Phase map

All from `SKILL.md` unless marked `[EP]` (= `knowledge/execution-playbook.md`).

| Phase | Name | Purpose | Line |
|---|---|---|---|
| — | Core beliefs (1–9) | Frame: spec-is-plan, bidirectional retrofit, unknowns STAY, two-commit, three-output scouts, read-toward-standard, deepen-don't-rearrange, ownership boundary, ownership-beats-file-count | 61 |
| — | Scope | Worktree, venv, cleanliness guard, spec-id argument | 103 |
| — | Mode detection | Standard / Decomposition / Packaging selection via §1.2.5 SOLID audit | 120 |
| — | Standard mode | Multi-file or 0–2 "and"s; IM → service extraction | 124 |
| — | Decomposition mode | Single file ≥2,000 LOC, 3+ "and"s; cluster → new file | 129 |
| — | Packaging mode | ≥3 same-prefix siblings; topology move table, prefix-strip | 145 |
| 0 | Bootstrap | Scaffold stub spec when `specs.py show` exits 1; reads `knowledge/bootstrap.md` (steps 0.1–0.4 at bootstrap.md:11,30,49,59) | 207 |
| 1 | Inventory | Know every file/symbol/edge; no interpretation | 223 |
| 1.1 | Load spec and ledger | `specs.py show/coverage`, `ledger.py list`, venv check | 228 |
| 1.1.5 | Inventory gate | `specs.py inventory-check`; drift/STUB/orphan-region outcomes | 253 |
| 1.2 | Convention docs | Resolve convention sources + path predicates → `convention-sources.md` | 279 |
| 1.2.5 | SOLID audit | Decomposition-mode only: SRP sentence, cluster map, DRY scan, linear flow → `phase-1-solid-audit.md` | 322 |
| 1.3.0 | Chunk oversized files | `chunk_file.py` for >2,000 LOC; basename-qualified chunk IDs (R35) → chunk map | 377 |
| 1.3 | Dispatch inventory scouts | Parallel scouts from `agents/inventory-scout.md`; Agent-tool vs `dispatch_scout.sh` subprocess | 427 |
| 1.4 | Git archaeology | Trigger-based commit-message excavation; "see knowledge/ for the full recipe" (recipe MISSING) | 488 |
| 1.5 | Consolidate inventory | `phase-1-inventory.md` + 4-condition gate for Phase 2 | 503 |
| 2 | Characterize + Extract | Freeze behavior + pull "why" into the spec, in parallel | 528 |
| 2.1 | Characterization tests | HEAD-passing temp tests; decomposition mode pins structure (L-44); shim-compat tests | 533 |
| 2.2 | Extraction pass | Consolidate scout `extracted/*` → `extracted-behaviors.md`; provisional→canonical IDs (R16); merge-by-summary | 581 |
| 2.3 | Findings consolidation | 2.3.1 cross-scout dedup (632), 2.3.2 P0–P3 tiering + `specs.py violations` adoption table (652) | 626 |
| 3 | Plan | Concrete split plan | 669 |
| 3.1 | Update spec | New IM/AR/EX/LR-T items land in spec BEFORE code moves | 674 |
| 3.2 | Write split plan | `phase-3-plan.md`, 11 numbered components (tree, symbol map, shim, endpoint matrix, renderer matrix, batches, test strategy, interface depth, guards, rollback, risks) | 692 |
| 3.2.1 | Decomposition plan structure | Cluster → file tree, atomic file→dir migration, common.py + `__all__`, lazy cross-cluster imports, Batch-1 consolidation | 728 |
| 3.3 | Triage Remove candidates | 5-check dormant verification; default keep-as-is | 792 |
| 4 | Approve | Human reviews 3 artifacts, blocks until approval | 821 |
| 4.1 | Present review package | plan / extracted-behaviors / findings, ≤5-line summaries | 826 |
| 4.2 | Wait for explicit approval | Token-anchored approval grammar; partial approval loops to Phase 3 | 840 |
| 4.3 | Record sign-off | §Sign-off block appended to `phase-3-plan.md` | 864 |
| 5 | Execute | Batch-at-a-time; read execution-playbook in full | 880 |
| 5.1 | Spec markers first | `[ ]`→`[~]`, `# spec:` comments before code | [EP] 13 |
| 5.2 | Batch execution | Step 0 concurrency re-check; move, shim, test, commit-or-revert | [EP] 28 |
| 5.3 | Two-commit discipline | Bug fixes are separate commits after the batch | [EP] 84 |
| 5.3.5 | Micro-fix swarm | 5+ mechanical fixes → parallel scouts, edit-only; serial `git commit --only`; pre-dispatch coverage check (R36) | [EP] 96 |
| 5.4 | Convention enforcement | `violations --json`, code_roots filter, 0/1–4/5–10/11+ decision table, decision-loop pseudo-code | [EP] 222 |
| 5.5 | Findings as ledger entries | P2 → `ledger.py update --decision monitor`, live not batched | [EP] 324 |
| 5.6 | Caller-update wave | Decomposition mode: private-symbol imports + mock-patch reclassification (R31) | [EP] 337 |
| 6 | Verify | Refactor complete, spec matches reality | 904 |
| 6.0 | Ownership-boundary scan | Scan shim, package, siblings, routes, templates/JS, new services; "target clean" vs "repo has findings" | 909 |
| 6.1 | Full verification suite | Baseline + subsystem + characterization suites | 931 |
| 6.1.5 | `__all__` export gate | star-imported new modules must declare `__all__`; GATE-FAIL blocks Phase 7 | 948 |
| 6.2 | Spec coverage gate | `specs.py coverage` — `is_clean: true` hard gate | 977 |
| 6.3 | SOLID quality gates | L1+L2 via `specs.py solid` (blocking), L3 sub-agent judgment (non-blocking) | 994 |
| 6.3.5 | Interface depth review | `phase-6-interface-depth.md`; pass-through/leaky/wrong-surface/hypothetical-seam block | 1044 |
| 7 | Crystallize | Durable end state | 1067 |
| 7.1 | Delete characterization tests | Delete or promote to LR-T/real tests | 1071 |
| 7.2 | Update ledger | Old shim + new files → `monitor` entries | 1084 |
| 7.2.5 | Update quality-tool memory | Retired-target notes in skills/scanners/maps/guards | 1100 |
| 7.3 | Append learnings log | Cluster entry in `reports/duplication/learnings.md` | 1115 |
| 7.4 | Final spec marker sweep | `coverage` must be `is_clean: true`; residuals noted in learnings | 1144 |
| 7.5 | Effectiveness log | `log_effectiveness.py` line in `reports/_meta/effectiveness.jsonl` | 1154 |
| — | Non-goals | 1173 | |
| — | Failure modes and recovery | 1193 | |
| — | Repository layout | Lists only FOUR knowledge files (contradicts line 34's "five") | 1220 |

## 2. Knowledge-pointer audit

Verdict key: **EXISTS** (content found, file:lines given), **MISSING**
(promised content found nowhere in the skill's files), **DRIFT**
(target exists but the claim about it is wrong).

### The bare-`knowledge/` pointer family (core defect — F1)

A directory path is cited as if it were a file, seven+ times. No file in
`knowledge/` contains the promised content in ANY of these cases.

1. SKILL.md:36–38 — "`knowledge/` — worktree paths, scripts, venv
   conventions, archaeology recipe, test matrix, report layout. Read at
   the start of Phase 1." → **MISSING.** No such file; none of the four
   real files contains worktree/venv rules, an archaeology recipe, a test
   matrix, or the report-directory layout as a unit.
2. SKILL.md:105 — "See `knowledge/` for exact paths, venv rules, and the
   cleanliness guard." → **MISSING.**
3. SKILL.md:114–115 — "**Cleanliness guard:** `code_roots` must be clean
   … Commands in `knowledge/`." → **MISSING.** The cleanliness-guard
   commands exist nowhere. Closest fragment: the §5.2 step-0 concurrency
   check, execution-playbook.md:34–37 (`git -C ~/Projects/your-project
   status --porcelain | grep -E '<code_roots regex>'`). That is a
   *main-worktree collision* check, not a *current-worktree dirty-files*
   check — the guard as described ("no unrelated uncommitted edits before
   Phase 1 AND before every Phase 5 batch") has no command anywhere.
4. SKILL.md:490 — "See `knowledge/` for the full recipe." (git
   archaeology, §1.4) → **MISSING.** No recipe file. The only recipe
   material is the §1.4 inline summary itself (see §4).
5. SKILL.md:500–501 — "Record findings in
   `reports/refactor/<spec-id>/archaeology/<basename>.md` per the schema
   in `knowledge/`." → **MISSING.** No archaeology report schema exists
   anywhere in the skill (and the `archaeology/` report subdirectory is
   named only here).
6. SKILL.md:586–587 — "(see `knowledge/` "Report directory layout" and
   the completeness contract in `agents/inventory-scout.md`)" →
   **MISSING** for the layout half (no "Report directory layout" section
   anywhere); **EXISTS** for the completeness contract
   (agents/inventory-scout.md:203–224).
7. agents/inventory-scout.md:25 — `{{venv}}` placeholder source column:
   "`knowledge/`" → **MISSING** (the example value `.venv/bin/python`
   (or `$PYTHON_VENV_PATH/bin/python`) on the same row is the only
   surviving content).
8. agents/micro-fix-scout.md:28 — `{{venv}}` source: "`knowledge/`" →
   **MISSING** (same).
9. knowledge/learnings.md:549 — L-index row L-1: "(`knowledge/`) |
   Worktree venv resolution — never fall back to a sibling worktree's
   venv" → **MISSING** (the one-liner is the only surviving content of L-1).
10. knowledge/learnings.md:562 — L-index row L-16: "(`knowledge/`) |
    Don't silently fall back to `.venv/` in the wrong worktree" →
    **MISSING** (one-liner only).

### Named-file pointers

11. SKILL.md:39–41 — "`knowledge/execution-playbook.md` — Phase 5 batch
    execution protocol, two-commit discipline, micro-fix swarm dispatch,
    convention enforcement decision loop, caller-update wave. Read at
    Phase 5 start." → **EXISTS**: §5.1 at EP:13, §5.2 at EP:28, §5.3 at
    EP:84, §5.3.5 at EP:96, §5.4 at EP:222, §5.5 at EP:324, §5.6 at EP:337.
12. SKILL.md:42–44 — "`knowledge/solid-gate-tests.md` — pass/fail rubric
    for the three-level SOLID quality gate plus the Phase 1.2.5 worked
    example." → **EXISTS**: Gates 1–6 at solid-gate-tests.md:10–113, mode
    scenarios at 115–126, worked example at 128–172.
13. SKILL.md:45–46 — "`knowledge/bootstrap.md` — Phase 0 stub-scaffolding
    playbook." → **EXISTS** (bootstrap.md:1–79; steps 0.1–0.4 at lines
    11, 30, 49, 59 — matches SKILL.md:211's "steps 0.1–0.4").
14. SKILL.md:47–49 — "`knowledge/learnings.md` — 36 rules (R1–R36) …
    An L-number index at the bottom." → **DRIFT** (F8): learnings.md's
    own title says "(R1-R43)" (learnings.md:1) and the file actually
    contains R1–R44 (R44 at learnings.md:504–541; note R36 at line 376
    appears BEFORE R35 at line 397). L-index **EXISTS**
    (learnings.md:543–582). SKILL.md:1141 repeats the wrong "R1-R36"
    count; SKILL.md:196 cites R44, contradicting its own line 47.
15. SKILL.md:34 — "Procedural detail lives in five knowledge files"
    heading SIX bullets, of which only FOUR are knowledge/ files →
    **DRIFT**; Repository layout block (SKILL.md:1220–1233) honestly
    lists only the four real files, contradicting line 34.
16. SKILL.md:50–53, 1044–1046, 717–718 —
    `.claude/skills/_common/interface-depth.md` → **EXISTS** on disk.
17. SKILL.md:56–59, 432, 1226–1227 — `agents/inventory-scout.md`,
    `agents/micro-fix-scout.md` → **EXIST**.
18. SKILL.md:485–486 — "The same pattern applies to Phase 5.3.5's
    micro-fix swarm — see `knowledge/execution-playbook.md` for the
    swarm-specific wrapper." → **MISSING.** EP §5.3.5 (96–220) describes
    Agent-tool dispatch and points to `agents/micro-fix-scout.md`; it
    contains NO subprocess/`dispatch_scout.sh` wrapper for the swarm.
19. execution-playbook.md:138 — "See `agents/micro-fix-scout.md` for the
    full scout brief." → **EXISTS** (micro-fix-scout.md:33–66).

### Script / command / flag pointers (verified against argparse)

20. `python3 scripts/specs.py show|coverage|inventory-check|solid|violations`
    (SKILL.md:209, 231–232, 260, 686–687, 980, 1003, 664; EP:107, 244)
    → **EXIST** (scripts/specs.py argparse: show :2141, coverage :2148,
    inventory-check :2190 incl. `--strict` :2195, solid :2173 incl.
    `--json` :2175, violations :2201 incl. `--json` :2206).
21. `scripts/ledger.py list --decision split_queued,monitor`
    (SKILL.md:233) and `update --decision --rationale` (SKILL.md:1088–1097;
    EP:331–334) → **EXIST** (ledger.py :584, :603–615). **DRIFT:** EP:333
    passes `--next-review <+180d>`; the real flag is `--next-review-days
    <int>` (ledger.py:613). No `--next-review` flag exists.
22. `scripts/chunk_file.py --token-budget --loc-budget --loc-hints
    --format --output` (SKILL.md:340, 383–387, 392, 401) → **EXIST**
    (chunk_file.py:352–368).
23. `.claude/skills/_common/dispatch_scout.sh` (SKILL.md:452, 465) →
    **EXISTS**; its header confirms the claimed contract (substitution
    via `scripts/_subst.py`, exit 0 only if output written).
24. SKILL.md:475 — dispatch loop reads
    `reports/refactor/${SPEC_ID}/inventory/chunks.jsonl` → **MISSING
    producer.** §1.3.0 writes `<basename>__chunks.json` and
    `<basename>__chunks.md` (SKILL.md:383–387); no step produces a
    consolidated `chunks.jsonl`.
25. EP:317–322 — "`--enforce-inline` flag … pass `--enforce-inline` to
    pre-commit to the inline-fix branch" → **MISSING** (F6). Grep over
    `scripts/` finds no such flag anywhere (`grep -rn enforce.inline
    scripts/` → no hits); the sentence is also ungrammatical.
26. SKILL.md:1158 — "Schema in `.claude/skills/_common/skill-conventions.md`"
    → **EXISTS** (effectiveness schema + `log_effectiveness.py` usage at
    skill-conventions.md:~61–89).
27. SKILL.md:1164 — `scripts/log_effectiveness.py` → **EXISTS**.
28. SKILL.md:1021–1023 — L3 scout "reads … `phase-6-solid.json` (L1+L2
    output)" → **DRIFT**: SKILL.md:1005 shows `specs.py solid` with
    "`--json` emits structured output" but no command ever redirects it
    to `reports/refactor/<spec-id>/phase-6-solid.json`; the file's
    production is implied, never instructed.
29. EP:113–127 vs EP:249–251 — two CONTRADICTORY claimed JSON shapes for
    `specs.py violations --json`: §5.3.5 claims `{"AR-2": {"canonical":…,
    "by_file": {...}}}`; §5.4 claims `{"spec": <id>, "items": [{"item_id",
    …, "violations": [{"file","line","text"}]}]}`. The REAL shape
    (specs.py:1679–1694) is §5.4's — flat `violations` list, **no
    `by_file` key**. The §5.4 pseudo-code (EP:290–310) then iterates
    `violations_json.items()` and reads `violations["by_file"]` — matching
    NEITHER the real shape nor §5.4's own documented shape.

### Other content pointers

30. SKILL.md:286–296 — §1.2 conditional doc list names
    `.claude/docs/pipelines.md`, `known-issues.md`, `ptid-pipeline.md`,
    `custom-site-data.md`, `architecture.md`, `configuration.md` →
    **MISSING in this repo** (host-project docs; F9/C8 territory).
31. SKILL.md:935–936 — Phase 6.1 baseline names
    `tests.test_site_capabilities tests.test_hydration_detector` →
    **MISSING in this repo** (host-specific; F9/C8).
32. SKILL.md:337 — "See `knowledge/solid-gate-tests.md` for worked
    examples." → **EXISTS** (SRP scenarios :14–26, worked example :128–172).

## 3. Load-bearing audit

"Consumed by" = a later step that reads/gates on the artifact. [EP] =
execution-playbook.md; [IS] = agents/inventory-scout.md.

| Artifact | Produced at | Consumed by |
|---|---|---|
| Phase 0 stub spec + single-file commit | bootstrap.md:30–46, 59–71 | Phase 1.1 `specs.py show` (SKILL:231); 1.1.5 STUB branch (SKILL:272–274) |
| `phase-1-inventory-gate.md` (drift delta log) | SKILL:268 | Weakly: "inventory-gate delta" count in phase-1-inventory.md (SKILL:514). No gate reads the file itself |
| `convention-sources.md` | SKILL:299–300 | Scout briefs (SKILL:301, [IS]:80–83) |
| `phase-1-solid-audit.md` | SKILL:373–374 | Phase 3 split plan (SKILL:374–375, 731); `specs.py solid` L1 artifact gate (SKILL:1008) |
| `inventory/<basename>__chunks.json` / `__chunks.md` (chunk map) | SKILL:383–387, 414–425 | Scout dispatch placeholders (SKILL:434, [IS]:18–23); Phase 1.5 chunk table + coverage gate (SKILL:508–519); archaeology-owner routing (SKILL:438–441) |
| `inventory/chunks.jsonl` | **NOTHING produces it** | Subprocess dispatch loop reads it (SKILL:475) — **broken edge (producer missing)** |
| Scout primary brief `inventory/{chunk}__L{s}-L{e}.md` | [IS]:66–73 | Phase 1.5 gate cond. 2/4 (SKILL:520–523); chunk-map corrections reconciled at 2.2 (IS:56–57) |
| Scout `findings/{chunk}__….md` | [IS]:75–112 | Phase 2.3 consolidation (SKILL:628–630) |
| Scout `extracted/{chunk}__….md` | [IS]:114–187 | Phase 2.2 consolidation (SKILL:583–584) |
| `archaeology/<basename>.md` | SKILL:499–501 | Phase 1.5 gate cond. 3 — "≥3 LR-T candidates" (SKILL:520–522); §3.3 entry field "**Archaeology:**" (SKILL:813). No schema exists to validate it against |
| `phase-1-inventory.md` | SKILL:505–515 | Phase 2 gate lives inside it (SKILL:517–526); Phase 3 "informed by inventory" (SKILL:671) — loose |
| `tests/test_<spec-id>_characterization.py` | SKILL:533–548 | HEAD run (SKILL:573–575); per-batch re-run ([EP]:60–64); Phase 6.1 (SKILL:943–945); deleted/promoted 7.1 (SKILL:1071–1082) |
| `extracted-behaviors.md` (consolidated) | SKILL:584 | Phase 3.1 spec update (SKILL:676–678); Phase 4 review item 2 (SKILL:831) |
| `findings.md` (consolidated, tiered) | SKILL:629–666 | Phase 4 review item 3 (SKILL:832); swarm trigger ([EP]:97–98); adoption-table update ([EP]:312–315) |
| Convention Adoption table (in findings.md) | SKILL:660–664 | Post-fix re-measure ([EP]:312–315) |
| `phase-3-plan.md` (11 components) | SKILL:694–726 | Phase 4 review item 1 (SKILL:830); §Sign-off appended (SKILL:866); batch/test scope drives 5.2 ([EP]:53–54); rollback (SKILL:724) |
| §Sign-off block | SKILL:866–878 | 5.3 immediate-fix scope ([EP]:86); 5.4 repo-wide enforcement scope ([EP]:236–239); 5.5 monitor approvals ([EP]:326) |
| `phase-5-violations.json` | [EP]:244–247 | code_roots filter + decision loop ([EP]:252–310); swarm dispatch input |
| Micro-fix scout return summary | micro-fix-scout.md:72–84 | Orchestrator serial `git commit --only` ([EP]:181–202) |
| Batch commits `[spec-id:batch-N]` | [EP]:69–82 | Phase 7.5 `findings_total` = batch-commit count (SKILL:1159–1161) |
| "COLLISION"/"clear" echo (concurrency check) | [EP]:34–37 | Stop/proceed decision ([EP]:38–43) |
| Phase 6.0 ownership-boundary scan result ("target clean" vs "repo still has known findings") | SKILL:921–924 | **NOTHING** — no artifact file named, no gate, 6.1 runs regardless, Phase 7 never reads it (= F3) |
| 6.1.5 `GATE-FAIL` lines | SKILL:962–971 | Blocks Phase 7 (SKILL:974–975) |
| `specs.py coverage` output (6.2) | SKILL:979–981 | Hard gate `is_clean: true` (SKILL:983–992); re-run 7.4 (SKILL:1146–1151) |
| `phase-6-solid.json` (L1+L2 output) | Implied by SKILL:1005 (`--json`), **no command writes it** | L3 scout reads it (SKILL:1022–1023) — **broken edge (producer unmandated)** |
| `phase-6-solid-agent.md` (L3 verdicts) | SKILL:1023–1024 | Orchestrator reads, flags FAILs "as Phase 7 follow-ups" (SKILL:1026–1027) — but see next row |
| "Phase 7 follow-ups" (from 6.3 at SKILL:998, 1027, 1041–1042; from 6.3.5 at SKILL:1063–1065) | Phase 6 | **NOTHING** — Phase 7 (7.1–7.5) has no follow-up intake step (= F4) |
| `phase-6-interface-depth.md` | SKILL:1048–1050 | Blocking-failure decision is in-phase (SKILL:1051–1060); no Phase 7 consumer for non-blocking entries (folds into F4) |
| Ledger `monitor` entries (5.5, 7.2) | [EP]:330–334; SKILL:1086–1097 | Next run's Phase 1.1 `ledger.py list` (SKILL:233) — cross-run consumer |
| Quality-tool memory updates (7.2.5) | SKILL:1100–1113 | **NOTHING in-run** (cross-run by design; no checklist artifact) |
| Learnings cluster entry (7.3) | SKILL:1117–1142 | 7.4 residual items noted into it (SKILL:1150–1152) — otherwise cross-run |
| `reports/_meta/effectiveness.jsonl` line (7.5) | SKILL:1156–1171 | External dashboard (`scripts/skill_effectiveness.py` per skill-conventions.md:89) — cross-run |

**Flagged NOTHING rows:** Phase 6.0 boundary-scan result (F3 — the
skill's most novel belief, output feeds nothing); Phase-7 follow-ups
from 6.3/6.3.5 (F4 — verdicts paid for via dedicated sub-agent dispatch,
then dropped at the phase boundary). **Flagged broken edges:**
`chunks.jsonl` (consumed, never produced) and `phase-6-solid.json`
(consumed, production never instructed). `phase-1-inventory-gate.md` is
weakly consumed (one count cited; nothing reads the file).

## 4. Archaeology fragments inventory

Everything that exists about the git-archaeology mechanism, verbatim.
The missing `knowledge/` recipe must be assembled from THESE — and only
these — fragments.

### In SKILL.md

- SKILL.md:72–75 (Core belief 3): "If you read a function and cannot
  explain why it exists — via a spec item, an `extracted-behaviors.md`
  entry, or git archaeology — it **stays**."
- SKILL.md:488–501 (§1.4, the entire inline summary):
  > ### 1.4 Git archaeology (trigger-based, NOT optional)
  >
  > See `knowledge/` for the full recipe. Summary:
  >
  > - **≤ 500 LOC AND ≤ 20 commits** → scout runs it inline.
  > - **Everything else** → orchestrator runs it in parallel with scouts.
  > - **≥ 50 commits** → archaeology is **mandatory** (R17). The archaeology
  >   file must include at least 3 load-bearing LR-T candidates with
  >   `<!-- archaeology: <hash> -->` tags.
  >
  > The recipe uses a subject-word filter (`fix|retry|timeout|crash|...`) to
  > find high-signal commits. Record findings in
  > `reports/refactor/<spec-id>/archaeology/<basename>.md` per the schema
  > in `knowledge/`.
  NOTE: `fix|retry|timeout|crash|...` is the ONLY surviving piece of the
  subject-word regex anywhere in the repo — the full list exists nowhere
  (repo-wide grep for `fix|retry`, "subject-word", "subject_word" finds
  only this line, the frame review quoting it, and the change-spec).
  Per change-spec C1: state the known four terms and mark the regex
  `<!-- host-adapter: extend subject-word list -->`.
- SKILL.md:421–424 (chunk-map columns): "| Chunk ID | Lines | LOC |
  ~Tokens | Declarations | Archaeology owner |" with example rows all
  showing "orchestrator" as owner.
- SKILL.md:438–441 (§1.3 dispatch): "Archaeology: if the chunk map marks
  the archaeology owner as "scout", the brief tells the scout to run
  `git log --follow` on its range. If marked "orchestrator", the
  orchestrator handles Phase 1.4 for that file in parallel with scout
  dispatch. (Ownership split by churn — L-7.)"
- SKILL.md:470–471 (dispatch loop): `archaeology_owner="$(jq -r
  '.archaeology_owner' <<<"$chunk")"` — owner travels in the chunk JSON.
- SKILL.md:520–522 (Phase 1.5 gate cond. 3): "**Archaeology present
  where required** — every ≥ 50-commit file has ≥ 3 LR-T candidates;
  every ≤ 500 LOC / ≤ 20 commits file has inline archaeology or a note."
- SKILL.md:813 (§3.3 REM entry field): "**Archaeology:** <last
  meaningful commit>".

### In agents/inventory-scout.md

- :23 (placeholder table): "| `{{archaeology_owner}}` | Chunk map row |
  `scout` or `orchestrator` |"
- :168–170 (Bucket 4 definition): "**LR-T** candidate — technical lesson
  (the "why" behind a defensive block). If the "why" came from a git
  commit message (i.e., archaeology), add `<!-- archaeology: <hash> -->`
  inline so Phase 7's crystallization can preserve the invariant's
  origin."
- :189–195 (scout-side recipe — the only concrete COMMANDS anywhere):
  > **Archaeology (only if this scout owns archaeology for its range).** If
  > {{archaeology_owner}} == "scout" (set when the whole file is ≤ 500 LOC
  > AND ≤ 20 commits — see Phase 1.4), run:
  >     git log --follow --oneline {{file}} | head -50
  >     git log --follow -p {{file}} | head -500
  > and add rationale entries to Output 3 as LR-T candidates. Otherwise skip
  > archaeology — the orchestrator is handling Phase 1.4 for {{file}} in parallel.
- :211–213 (completeness contract item 4): "Plus (conditional on
  `{{archaeology_owner}} == "scout"`): 4. Archaeology entries as LR-T
  candidates in Output 3."

### In knowledge/learnings.md

- :41–49 (R4, full text): "## R4 — Git archaeology before split /
  `git log --follow -p` is worth 1000 commits of future confusion.
  Capture rationale BEFORE the split destroys blame history, not after.
  **How to apply:** Phase 1.4 is mandatory for files with ≥ 50 commits —
  at least 3 load-bearing LR-T extractions per file with
  `<!-- archaeology: <hash> -->` cross-references."
- :174–183 (R17, full text): "## R17 — Archaeology is mandatory for
  high-churn files / ≥ 50 commits triggers Phase 1.4 as non-optional
  with ≥ 3 load-bearing LR-T extractions and `<!-- archaeology: <hash>
  -->` cross-references in the final spec. Commit messages on high-churn
  files encode invariants that live nowhere else. **How to apply:**
  Skipping archaeology on a high-churn file is indistinguishable from
  the "discards load-bearing code" failure mode (R12)."
- L-index rows (:554, :556, :560, :570):
  - "| L-7 | — | Archaeology ownership split by churn (scout vs
    orchestrator) |"
  - "| L-8 | R4 | Subject-word-biased `git log` recipe for archaeology |"
  - "| L-13 | R17 | ≥ 50 commits → mandatory archaeology, ≥ 3
    load-bearing LR-T extractions |"
  - "| L-25 | R4 | Subject-word recipe validated on
    `core/views_crawling.py` (102 commits → 7 load-bearing) |"
  L-25 is a usable calibration datum for the recipe: 102 commits filtered
  to 7 load-bearing LR-T candidates.

### In knowledge/ otherwise

- Nothing. `bootstrap.md`, `execution-playbook.md`, `solid-gate-tests.md`
  contain zero archaeology content (grep-verified).

### In _common

- `.claude/skills/_common/skill-conventions.md:114` — "**Exceptions:**
  stack traces, git-archaeology commit references (pinned" — confirms the
  `<!-- archaeology: <hash> -->` pinned-hash convention is recognized as
  an ecosystem-level exception (to a line-length/staleness rule).

### Wider-repo grep ("archaeology" in .claude/docs/, docs/, ai-docs/, reports/, scripts/)

- `.claude/docs/skill-catalog.md:246` — "/refactor-subsystem (Phase 1
  only) | Excavates the inventory as the first phase of a multi-file
  refactor. Has archaeology, chunking, SOLID audit." — confirms
  archaeology is part of the skill's advertised contract; no recipe.
- `reports/skill-frame-review/refactor-subsystem.md:91–93` — quotes the
  elided regex and names the missing pieces ("archaeology recipe with
  the full subject-word regex, archaeology schema"); :66–68 restates the
  thresholds ("≥50 commits → ≥3 LR-T candidates with `<!-- archaeology:
  hash -->` tags"). Derivative of SKILL.md — adds no new recipe content.
- All other hits (`architectural-smells.md:76`, ADR 0034:136,
  `find-dead-route-surface`/`find-skill-intent-drift`/`find-stale-artifacts`
  SKILL.md hits, `.claude/contracts/skills/*.yaml`,
  `.claude/tasks/derive_skill_facts.py`, `_fanout_brief.md`,
  `reports/avatars/lost-prototype-hunt.md:4`) use "archaeology" as a
  generic figure of speech — **no recipe content**.
- Git history: no deleted knowledge file in any commit (checked
  `git ls-tree` across all revisions); recipe is not recoverable from
  history.

### Authoring summary for the recipe

The complete set of true, sourced facts available: triggers (≤500 LOC ∧
≤20 commits → scout inline; otherwise orchestrator-parallel; ≥50 commits
mandatory), the success bar (≥3 load-bearing LR-T candidates per
mandatory file, `<!-- archaeology: <hash> -->` tags carried into the
spec), ownership mechanics (chunk-map `Archaeology owner` column,
`archaeology_owner` JSON key, L-7 "split by churn"), scout-side commands
(`git log --follow --oneline | head -50`; `git log --follow -p | head
-500`), R4's base command (`git log --follow -p`), the partial
subject-word filter (`fix|retry|timeout|crash|…` — full list lost), the
output path (`reports/refactor/<spec-id>/archaeology/<basename>.md`),
the L-25 calibration point (102 commits → 7 load-bearing), and the
LR-T destination (Output-3 Bucket 4 → spec via Phase 2.2/3.1). NOT
available anywhere: the report schema (must be newly defined — the
change-spec authorizes deriving it from inventory-scout's output
contract, i.e. LR-T entry shape with file:line, summary, behavior,
hash tag), the full subject-word list, and the orchestrator-side command
variant (only the scout-side `head`-limited commands exist).

## 5. Decomposition-mode anatomy

**Trigger and frame.** Single file ≥2,000 LOC with 3+ SRP "and"s
(SKILL:130–132); mode is determined by the §1.2.5 SOLID audit
(SKILL:121–122, 322–375). Dominant-file edge case at SKILL:140–143.
"The 7-phase workflow and safety net are unchanged" (SKILL:137–138) —
the claim F2 undercuts.

**What changes vs standard mode (SKILL:135–137):**
1. Phase 1 adds the SOLID audit (§1.2.5, SKILL:322–375) — SRP sentence
   test, responsibility-cluster map via `chunk_file.py`, intra-file AST
   DRY scan, linear-flow trace → `phase-1-solid-audit.md`, which feeds
   the Phase 3 plan and the L1 artifact gate (SKILL:1008).
2. Phase 3 organizes the plan by domain cluster, not IM→service
   (§3.2.1, SKILL:728–790): target tree `<basename>/<domain>.py` with
   `__init__.py` re-export shim (permanent, SKILL:775–777); atomic
   file→directory migration in a single commit (SKILL:753–762);
   `common.py` carrying the full original import block with mandatory
   `__all__` (R30/R32, SKILL:779–790); lazy cross-cluster imports
   (SKILL:789–790); cross-cutting consolidation as Batch 1 (R26,
   SKILL:770–773).
3. Phase 5 adds the caller-update wave (EP §5.6:337–374): enumerate
   callers, verify shim coverage, fix private-symbol imports, reclassify
   every `@patch('core.<original>.…')` as `.delay()`-safe vs
   synchronous-needs-retarget (R31), full test suite after the wave.

**What it pins (the F2 core).** SKILL:551–556: "**Decomposition-mode
characterization pins *structure*, not *behavior* (L-44).** The right
test shape is a `TaskImportabilityTest` (every public symbol importable
from the original path), `TaskSignatureTest` (function signatures
unchanged), and `TaskRegistrationTest` (Celery tasks still registered
with their original names + options). Behavior tests are the domain
test suites' job." Plus shim-compat import pins for Django module splits
(SKILL:558–569).

**What tests it runs or delegates.** Per batch: the plan's batch test
scope + characterization suite (EP:53–64); Phase 6.1: baseline +
subsystem suites named by the spec/plan (SKILL:933–945). Behavior
verification is thus DELEGATED to "the domain test suites" — chosen by
name in plan item 7 (SKILL:720, "Test strategy per batch — which
modules' tests need to pass") with no evidence requirement.

**Where a behavior change passes undetected (F2 chain).** A batch moves
N-thousand LOC into `tasks_<domain>.py`; structure tests pass
(symbols importable, signatures unchanged, Celery names registered);
the named per-batch suite is green but never imports/patches the
destination module, so the moved code paths never execute under test;
Phase 6.1 re-runs the same suites; 6.2 checks spec markers, 6.3 checks
SOLID shape, 6.3.5 checks interface depth — none executes behavior. The
guard that closes exactly this hole exists ONLY for the micro-fix swarm:
R36 / EP:157–179 ("Mandatory pre-dispatch coverage check… Never
dispatch a sub-agent with a `verification_cmd` that does not touch its
target file"; learnings.md:376–395 "Never trust 'green' from a test
suite that has no path into the edited code"). It is not mandated for
Phase 3 item 7, Phase 5.2 step 4, or Phase 6.1 — the repair (C2)
generalizes it to batch level.

**Ownership-boundary scan (Phase 6.0, SKILL:909–929).** Inputs: the
whole ownership family named by the plan — old shim, new
package/directory files, same-prefix siblings, registered public AND
prototype routes, templates/JS loaded by those routes, newly created
services (SKILL:911–919; operationalizes belief 8 at SKILL:92–96 and
R37/R38 at learnings.md:418–440). Output: a verbal classification —
"Report the result as `target clean` vs `repo still has known
findings`" (SKILL:921–922) plus a lint-surface distinction
(diff-scoped vs whole-file legacy, SKILL:926–929). **No artifact file
is named, and nothing reads the result**: 6.1 runs unconditionally next;
Phase 7's steps never reference it; there is no gate wired to "repo
still has known findings" beyond the in-prose instruction "Do not
declare a split complete while the same responsibility still lives in a
registered sibling/prototype path" (SKILL:923–924), which has no
enforcement artifact. This is F3; the repair (C3) adds
`phase-6-boundary.md` + a Phase 7 entry gate with a Phase 4 sign-off
waiver.

---

**Repair-relevant surprises.** (1) Beyond the headline F1 pointers, two
artifact edges are silently broken and not in the frame review:
the §1.3 subprocess dispatch loop reads `inventory/chunks.jsonl` that no
step produces (SKILL:475 vs 383–387), and the Phase 6.3 L3 scout reads
`phase-6-solid.json` whose production is never commanded (SKILL:1005 vs
1022) — C1's report-directory-layout section should canonize both
(define who writes them) or the repair should fix the references.
(2) execution-playbook §5.3.5 documents a `violations --json` shape
(`by_file`-keyed, EP:113–127) that does not match the script's real
output (flat `items[].violations` list, specs.py:1679–1694, matching
§5.4's description at EP:249–251), and the §5.4 pseudo-code reads
`violations["by_file"]` — so fixing F5's threshold branch alone still
leaves pseudo-code against a phantom shape; align both while editing
that block. (3) EP:333 uses a phantom ledger flag `--next-review
<+180d>`; the real flag is `--next-review-days <int>` (ledger.py:613) —
same Band-A class as F6, one-word fix. (4) learnings.md has R36 placed
before R35 (lines 376 vs 397) — harmless but will trip a count/order
sweep; and the C1 count fix must touch FOUR surfaces: SKILL.md:34
("five knowledge files" over six bullets), SKILL.md:47 and :1141
("R1–R36"), learnings.md:1 ("R1-R43"), and the Repository layout block
(SKILL:1222–1233, which must gain operations.md). (5) The cleanliness
guard (Scope, SKILL:113–115) and the §5.2 concurrency check (EP:32–43)
are DIFFERENT checks — current-worktree dirty-files vs main-worktree
collision — and only the second has a command; operations.md must
author the first without conflating them, and the §5.2 command
hardcodes `~/Projects/your-project` (host-specific, C1 says generalize).
(6) `.claude/contracts/skills/refactor-subsystem.yaml` exists; if the
repair changes advertised behavior/artifacts, that contract and
`.claude/docs/skill-catalog.md:246` may need a consistency pass
(`/check-ecosystem-consistency` is the named tool).
