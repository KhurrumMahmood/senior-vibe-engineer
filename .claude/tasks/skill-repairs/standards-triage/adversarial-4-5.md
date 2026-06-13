# Adversarial refutation pass — batches 4 & 5

Independent cross-model lane. Method: re-derived every checked verdict from
ground truth (read the SKILL.md, ran the real script `--help`/dry
invocations with `.venv/bin/python`, read the argparse source). Read-only
against all skills. Standard applied:
`.claude/skills/repair-skill/knowledge/skill-standard.md`.

**Report-integrity note on batch 4.** `batch-4.md` is a recovered transcript
whose verdict table and defect specs were never written (sandbox blocked the
write; only the summary counts and the NEEDS-REPAIR list survived, lines
242-244). Consequences: (a) the three batch-4 OK skills are **unidentifiable**
— the OK-attack lane for batch 4 cannot bind to skills; (b)
`find-workflow-state-gaps` is in batch 4's **NEEDS-REPAIR** list, not OK;
(c) batch-4 NEEDS-REPAIR verdicts are verified below as *supportable or not*
from independent evidence, since no cited defects survive to mark TRUE/FALSE.

## Flips

| Skill | Original | My verdict | Evidence |
|---|---|---|---|
| plan-spec (b5) | OK | **MINOR** | Stage 4 claims "six standard sections (Goals / Architecture / Implementation / Learnings / Exceptions / Lifecycle)" and "**Lifecycle** ← `proposed` (the scaffold default)"; ground truth: the scaffold in `scripts/specs.py:1878-1907` emits exactly five `##` sections — there is no `## Lifecycle` — and `lifecycle:` frontmatter is written only `if lifecycle:` (`specs.py:1847-1848`), which `plans.py promote` (`scripts/plans.py:261-277`) **never passes**. Stage 6 then tells the executor to report `lifecycle: proposed`, a value nothing wrote. Secondary: Stage 5 uses `${SPEC_ID}` never assigned in any prior block. Script flags themselves all verified real (`promote --spec-id/--code-roots/--allow-missing/--force`, `audit`, `inventory-check`). |
| project-interview (b5) | OK | **NEEDS-REPAIR** (below standard) | Materially missing skill-standard elements: no "How success is judged" block (element 1) and no failure-path guidance anywhere in the 123-line file (element 7) — the standard's triage rule: "a skill missing elements is BELOW-STANDARD even with zero prose defects". Plus an execution-time drift: pipeline step 1 parameterizes `--artifact-root "${ARTIFACT_ROOT}"`, but step 5 hardcodes `evidence_gate.py check ... --scan-dir reports/project-interview/latest` — in the documented `--no-host-write --artifact-root <outside>` dogfood form (Forms block, line 56) the gate points at a directory the run never wrote. Script flags verified real. |
| which-skill (b5) | OK | **MINOR** | Stage 1 and Stage 3 document bare-`python3` invocations (`SKILL.md:96`, `:170`), but `scripts/match.py:36` imports `_lib.yaml_frontmatter`, which does unconditional `import yaml` (`scripts/_lib/yaml_frontmatter.py:37`, no fallback). Repo doctrine (CLAUDE.md "Python Environment") is explicit that PyYAML-backed `scripts/_lib/` parsing needs `requirements.txt` deps via `.venv/bin/python`. The documented command works only where system python3 happens to carry PyYAML (it does on this machine, which is presumably why the reviewer's check passed). Everything else verified: JSON keys incl. `recommendation`/`task_packet`/`candidates`, exit codes 0/1/2 (`match.py:286,366,404`), `log_effectiveness.py` flags all real. |
| query-patterns (b5, spot-check) | MINOR | **NEEDS-REPAIR** | Both reviewer-cited facts verified TRUE, but jointly they break the skill's most common fresh-install path, which is repair-grade: on an empty library the SKILL mandates "exit 0 with a message" (`SKILL.md:97`) while `scripts/query.py:263` is `return 0 if results else 1` (the script's own docstring, line 9: "1 no match (zero patterns OR all scores at zero)") — the declared gate is wrong; and the message the executor must deliver routes to `/promote-idea-to-pattern` at `SKILL.md:39,98,156,198`, a skill that does not exist (`.claude/skills/promote-idea-to-pattern`: no such directory). Wrong exit-code contract + nonexistent handoff at the same decision point = the no-match path is unexecutable as documented, not cosmetic. |

## Batch 5 NEEDS-REPAIR verdicts vs ground truth

| Skill | Original | My verdict | Evidence |
|---|---|---|---|
| triage-debt | NEEDS-REPAIR | **TRUE** | All four citations verified verbatim: `SKILL.md:4` argument-hint `"[--top N]"`; `SKILL.md:108` `TOP_N="${1:-5}"` (with `--top 10`, `$1` is the literal `--top`); consumed at `SKILL.md:251` (`## Top <TOP_N>`) and `SKILL.md:286` — where `"top_n": ${TOP_N}` would render `"top_n": --top`, invalid JSON passed to `log_effectiveness.py --buckets`. The reviewer's compression was accurate. |
| unify-shadows | NEEDS-REPAIR | **TRUE** | `SKILL.md:188` "see `knowledge/` for the exact per-shape body templates"; `SKILL.md:207-209` requires the shape-specific body (`keep_separate_document_why \| share_utilities \| complete_migration \| merge_at_workflow`); `knowledge/` directory verified empty (zero files). The most load-bearing part of the proposal must be invented. |

## Batch 4 NEEDS-REPAIR verdicts (cited defects lost — independent re-derivation)

| Skill | Original | My verdict | Evidence |
|---|---|---|---|
| introduce-fk | NEEDS-REPAIR | **SUPPORTABLE (defect re-found)** | `SKILL.md:93-96`: "Project-specific defaults ... `knowledge/`. The scout reads that file" — `knowledge/` is empty; "that file" exists nowhere. Same load-bearing reference at `SKILL.md:277` ("see `knowledge/` for guidance") and `:415` ("See `knowledge/` for project-specific gotchas the proposal's risk section must cover"). Same defect class as unify-shadows. `collect.py` argparse itself matches the documented forms. |
| map-subsystem | NEEDS-REPAIR | **SUPPORTABLE (defects re-found)** | (1) `scripts/render_doc.py` requires `--name --target --scratch --output` and the repo-layout comment (`SKILL.md:287`) says it implements Stages 6-7, yet **no pipeline stage ever invokes it** — Stage 6 reads as a hand-render per `knowledge/output-format.md`; orphan script / element-4 violation. (2) Stage 0 contract self-contradicts: Post-condition says "`reports/map/<name>/` scratch dir exists" (`SKILL.md:124`) while its own bash sets `SCRATCH=$(mktemp -d)` (`SKILL.md:129`). |
| find-transaction-overreach | NEEDS-REPAIR | **SUPPORTABLE (defect re-found)** | The Stage 3 default dispatch path ("Use the cheap subprocess by default", `SKILL.md:~190`) shells `dispatch_scout_cheap.sh`, which executes `"$VENV_PYTHON" -m tools.code_agent` (`_common/dispatch_scout_cheap.sh:106`). No `tools/` package exists anywhere in this repo; verified live: `.venv/bin/python -m tools.code_agent --help` → `ModuleNotFoundError: No module named 'tools'`. The documented-default fan-out is unexecutable as shipped. (Class defect: 9 skills reference this helper.) The skill's own three script contracts (detect/collapse/report) all match argparse. |
| find-standard-gaps | NEEDS-REPAIR | **SUPPORTABLE (weaker)** | Documented invocations match argparse (`scan_coverage.py --ideas/--project-root/--output-dir`; `census.py --concern/paths/--json`). But the SKILL.md contains **zero** mentions of `--project-state`, `scripts/project_state.py`, `gated_out`, or activation gating — while `scan_coverage.py`'s own contract emits a `gated_out` per-standard status computed from declared (maturity, stakes). Orphan helper script + an output band the executor has no doctrine for. Default `standards/standards.json` absent is declared (ships as `standards.example.json`, `SKILL.md:85-87`) — not a defect. |
| find-workflow-duplication | NEEDS-REPAIR | **PARTLY (standards-grounds only)** | Both documented script invocations verified flag-for-flag against argparse (`detect.py --min-active-owners/--output`; `report.py` all five flags) — no execution-time defect found. Support is standards-shaped: missing element 1 (no "How success is judged") and element 7 (no sideways table); host-descriptor dependency (`.engineering/docs/product-workflows.md`) is declared honestly. If the lost defect spec claimed a script-contract break, it was wrong. |
| find-workflow-state-gaps | NEEDS-REPAIR (not OK — see integrity note) | **PARTLY (standards-grounds only)** | `run.py` contract verified: positional `<paths...>` matches; output dir `reports/find-workflow-state-gaps/scan-<TS>/` matches `product_health.write_scan_outputs` (`_common/product_health.py:177`). No execution defect found. Support: 52-line skill missing elements 1, 2, and 7 entirely, and a host-specific `/sites` scope baked into frontmatter/body of a shipped kit skill. |

## MINOR spot-checks (remaining two)

| Skill | Original | My verdict | Evidence |
|---|---|---|---|
| which-cleanup | MINOR | **CONFIRMED-MINOR** | Claim TRUE: `SKILL.md:~92` prose says the floor adds `find-doc-link-rot` on doc changes; `scripts/select_scanners.py:56` `DOC_SHAPE_FLOOR: list[str] = []` with comment "find-doc-link-rot not in this repo's skill set". Script behavior is correct; prose overpromises — severity right. |
| propose-boundary | MINOR | **CONFIRMED-MINOR** | Both claims TRUE: `scripts/propose.py:90` returns target kind `"subsystem"` while `SKILL.md:204` lists only `file \| directory \| skill_directory`; `SKILL.md:166` documents `call_edges` as `{caller, callee, count}` while `propose.py:659-661` emits `{file, caller, callee}` (no count). Schema-doc drift, not an execution break — severity right. |

## OK verdicts confirmed

| Skill | Original | My verdict | What I checked |
|---|---|---|---|
| rename-concept (b5) | OK | **CONFIRMED-OK** | `assess.py` argparse matches the documented form exactly (`old new [--min-blast] [--project-root]`); live dry run (`assess.py oldfoo newbar`) executes clean from text alone, self-reports the missing-glossary case, and renders the documented GREEN/HALF-APPLIED verdict; prose claims verified in source — band-3 skip on `coverage_lint` (`find-concept-divergence/scripts/scan.py:289-298`), guard-lint glob `no_*<old>*references.py` under `scripts/lint/` (`assess.py:127`). Declared verdict present as the "Definition of done" gate; no sideways table, but the single read-only script self-reports its failure states, so the gap is not material. |
| Batch 4's three OK skills | OK | **UNVERIFIABLE** | The verdict table never survived the sandbox-blocked write; the three OK names are unknowable among {find-test-obligation-drift, gut-check, harvest-learnings, impact-feature, map-product-workflow, mature-existing-ideas, orient}. Batch 4 should be re-run or its table reconstructed before its OK/MINOR verdicts are consumed by any sweep. |

## Reviewer blind spots (calibration for the other batches)

The reviewer is strong on argparse-surface equivalence — every flag-level
citation I checked in batch 5 was verbatim-accurate, and none of its
NEEDS-REPAIR verdicts collapsed to FALSE. Its systematic misses cluster in
three classes. **(1) Runtime-dependency depth:** it verifies that a script or
helper *exists* and that flags match, but not that the invocation *resolves*
— the bare-`python3`-vs-PyYAML trap in which-skill passed because the
reviewer's machine has global PyYAML, and helper-existence checks
(`ls dispatch_scout*.sh`) never reached `tools.code_agent`, which is missing
repo-wide. Expect other batches' OK verdicts to hide interpreter/dependency
defects on any skill whose scripts import `scripts/_lib/`. **(2) Scaffold- and
artifact-content claims:** it checks command contracts but not what the
produced artifact actually contains — plan-spec's nonexistent `## Lifecycle`
section and never-written `lifecycle: proposed` default survived an OK because
nobody diffed the SKILL's description of the scaffold against the scaffold
generator. **(3) Standards-element triage is inconsistently applied:** thin
skills got NEEDS-REPAIR in batch 4 while project-interview — missing the
declared-verdict and failure-path elements entirely — got OK in batch 5,
suggesting element checks were applied only when prose defects were already
suspected. A milder fourth pattern: severity under-calls when two small TRUE
facts compound on one decision path (query-patterns' no-match path has both a
wrong exit-code gate and a nonexistent handoff — each "minor", jointly
unexecutable). Conversely there is no evidence of over-calling: every
NEEDS-REPAIR I could test was real or independently supportable, so the
fleet's risk with this reviewer is missed defects behind OK verdicts, not
false alarms.
