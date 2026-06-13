# Standards triage — batch 3 (delivered via final reply; orchestrator-landed)

Here is the complete triage report returned by Codex:

---

## Frame-Review Triage — 13 find-* Skills

### Verdict Table

| skill | verdict | one-line reason |
|---|---|---|
| find-implicit-state | MINOR | Script flags match; add explicit replay evidence for the full detect/collapse/report path. |
| find-incomplete-sweep | NEEDS-REPAIR | Documented project-root anchoring and scout verdict flow do not execute as written. |
| find-layer-violation | MINOR | Script flags match; add replay evidence for the full pipeline. |
| find-omnibus | MINOR | Script flags match; one bucket-count typo plus missing replay evidence. |
| find-orphaned-ideas | NEEDS-REPAIR | Success gate and stale-plan/effectiveness contracts drift from real script behavior. |
| find-perimeter-gaps | NEEDS-REPAIR | Multiple activation-standard elements are missing, and script help contradicts real coverage behavior. |
| find-query-mutation | MINOR | Script flags match; add replay evidence and tighten declared dispatch judging. |
| find-route-sprawl | NEEDS-REPAIR | `--root-urls` is advertised but not passed; emitted pattern list is stale. |
| find-rule-surface-drift | NEEDS-REPAIR | Multiple standard gates are missing, and the argument hint uses stale size defaults. |
| find-semantic-duplication | NEEDS-REPAIR | Confirm stage requires a missing sibling report and guidance names a dead artifact. |
| find-skill-artifact-drift | NEEDS-REPAIR | Smoke fixtures exist, but success and failure-path standard gates are missing. |
| find-skill-intent-drift | NEEDS-REPAIR | Claims no contract edits while default scan rewrites `_index.yaml`; dogfood enum prose is stale. |
| find-stale-artifacts | NEEDS-REPAIR | Script flags match, but several required activation-standard elements are absent. |

---

### NEEDS-REPAIR Defect Specs

#### find-incomplete-sweep
- **F1:** Project-root anchoring is documented for all relative paths (`.claude/skills/find-incomplete-sweep/SKILL.md:97` "Relative paths anchor on `--project-root`"), but the placeholder band drops that value (`.claude/skills/find-incomplete-sweep/scripts/scan.py:567` "`_ph.run(args.paths, args.max_age_days)`").
- **F2:** The placeholder scanner then resolves raw paths from the current process directory (`.claude/skills/find-incomplete-sweep/scripts/placeholder.py:219` "`root = pathlib.Path(p)`"), so SKILL.md invocations can scan the wrong tree.
- **F3:** Scout verdict output is under-specified: the skill says to "Dispatch one investigation per packet" (`.claude/skills/find-incomplete-sweep/SKILL.md:186`) and later "Write `<scan-dir>/triaged.md`" (`.claude/skills/find-incomplete-sweep/SKILL.md:208`), but gives no per-judge artifact path or merge contract.

#### find-orphaned-ideas
- **F1:** The success gate requires "the seven modes separated" (`.claude/skills/find-orphaned-ideas/SKILL.md:49`), but `--all` is documented as "the three ledger-native modes" while naming only stale and harvest (`.claude/skills/find-orphaned-ideas/SKILL.md:82`); argparse flow only runs stale/harvest for `args.all` (`.claude/skills/find-orphaned-ideas/scripts/find.py:805` "`if args.stale or args.all:`").
- **F2:** Stale-plan prose says only `proposed` plans without a ledger intake qualify (`.claude/skills/find-orphaned-ideas/SKILL.md:170` "status `proposed`"), but the script accepts five statuses (`.claude/skills/find-orphaned-ideas/scripts/find.py:287` "`{"draft", "proposed", "scoped", "impacted", "architected"}`").
- **F3:** Effectiveness logging is not executable from text alone: the command uses undefined shell values (`.claude/skills/find-orphaned-ideas/SKILL.md:352` "`--count "$TOTAL"`") with no prior assignment.

#### find-perimeter-gaps
- **F1:** The skill goes from beliefs to pipeline (`.claude/skills/find-perimeter-gaps/SKILL.md:32` "## Core beliefs"; `.claude/skills/find-perimeter-gaps/SKILL.md:48` "## Pipeline") with no declared "How success is judged" gate.
- **F2:** Honest failure paths and replay evidence are absent from the pipeline section; Stage 3 only says to "Write the matrix and operator notes" (`.claude/skills/find-perimeter-gaps/SKILL.md:77`).
- **F3:** Script help says `language: any` covers everything (`.claude/skills/find-perimeter-gaps/scripts/scan.py:13` "where ``any`` covers everything"), but the actual detector logic says it covers nothing (`.claude/skills/find-perimeter-gaps/scripts/scan.py:172` "`language: any deliberately covers nothing.`").

#### find-route-sprawl
- **F1:** The skill advertises `--root-urls` (`.claude/skills/find-route-sprawl/SKILL.md:4` "`[--root-urls <path/to/urls.py>]`"), but the documented pipeline never forwards it (`.claude/skills/find-route-sprawl/SKILL.md:41` "`python3 .../detect.py`").
- **F2:** The script supports that flag (`.claude/skills/find-route-sprawl/scripts/detect.py:126` "`--root-urls`"), so the written invocation silently ignores the user's root URL override.
- **F3:** The findings list omits an emitted pattern: SKILL.md lists four types (`.claude/skills/find-route-sprawl/SKILL.md:53` "Findings include:"), while the detector emits `scattered_route_family` (`.claude/skills/find-route-sprawl/scripts/detect.py:90` "`pattern="scattered_route_family"`").

#### find-rule-surface-drift
- **F1:** The argument hint is stale: SKILL.md says `--max-root-chars 12000 --max-doc-chars 25000` (`.claude/skills/find-rule-surface-drift/SKILL.md:4`), while the script defaults are 30K/50K (`.claude/skills/find-rule-surface-drift/scripts/detect.py:32` "`DEFAULT_MAX_ROOT_CHARS = 30_000`").
- **F2:** The skill has replay fixtures (`.claude/skills/find-rule-surface-drift/SKILL.md:124` "## Replay fixtures") but no declared "How success is judged" block, despite the activation standard requiring a "Declared verdict" (`.claude/skills/repair-skill/knowledge/skill-standard.md:13`).
- **F3:** The skill also lacks an honest failure-path table, despite the standard requiring "Honest failure paths" (`.claude/skills/repair-skill/knowledge/skill-standard.md:33`).

#### find-semantic-duplication
- **F1:** Confirm instructions require a sibling report that is not in the repo: `.claude/skills/find-semantic-duplication/agents/confirm.md:40` says "Also check `reports/duplication/latest/triage.md`"; that path is absent on disk.
- **F2:** False-positive guidance names a dead artifact (`.claude/skills/find-semantic-duplication/knowledge/false-positives.md:3` "`confirmed_pairs.json`"), while the current pipeline produces `scout/`, `ranked.json`, and `triage.md` (`.claude/skills/find-semantic-duplication/SKILL.md:181` "Expected outputs:").
- **F3:** Cross-domain instructions conflict: SKILL.md makes it conditional (`.claude/skills/find-semantic-duplication/SKILL.md:149` "If focus cuts across domains"), while learnings says "always run the cross-domain pass" (`.claude/skills/find-semantic-duplication/knowledge/learnings.md:41`).

#### find-skill-artifact-drift
- **F1:** The skill has a fixture smoke contract (`.claude/skills/find-skill-artifact-drift/SKILL.md:117` "## Fixture smoke contract"), but no declared "How success is judged" block, despite the standard requiring a "Declared verdict" (`.claude/skills/repair-skill/knowledge/skill-standard.md:13`).
- **F2:** Honest failure paths are missing, despite the standard requiring "Honest failure paths" (`.claude/skills/repair-skill/knowledge/skill-standard.md:33`).
- **F3:** The skill's own frontmatter requires artifact evidence (`.claude/skills/find-skill-artifact-drift/SKILL.md:32` "`evidence_required: referenced_path_exists`") but does not say how to fail when evidence is absent.

#### find-skill-intent-drift
- **F1:** The skill claims it never edits contracts (`.claude/skills/find-skill-intent-drift/SKILL.md:39` "This skill never edits skills or contracts"), but Stage 3 says the scan regenerates `_index.yaml` (`.claude/skills/find-skill-intent-drift/SKILL.md:106` "`_index.yaml` is regenerated").
- **F2:** The script really writes that file by default (`.claude/skills/find-skill-intent-drift/scripts/scan.py:318` "`out.write_text(...)`"), so the read-only frame is false unless `--no-index` is used.
- **F3:** Dogfood-kind prose is stale: SKILL.md lists four values (`.claude/skills/find-skill-intent-drift/SKILL.md:132` "one of: `subsystem-refactor`, `self-installed-guard`, `fixture-pair`, `none-found`"), while the script also accepts `host-attested` (`.claude/skills/find-skill-intent-drift/scripts/scan.py:45` "`"host-attested"`").

#### find-stale-artifacts
- **F1:** The skill defines scope (`.claude/skills/find-stale-artifacts/SKILL.md:56` "## Scope") and then begins the pipeline (`.claude/skills/find-stale-artifacts/SKILL.md:64` "## Pipeline") without a declared "How success is judged" block.
- **F2:** Honest failure paths are missing; the later operator section is only "Notes for the orchestrator" (`.claude/skills/find-stale-artifacts/SKILL.md:140`) and does not state what to do for unreadable manifests, missing reports, or zero-evidence candidates.
- **F3:** Replay evidence is absent despite the standard requiring a "Replay case" (`.claude/skills/repair-skill/knowledge/skill-standard.md:37` "Replay case.").

---

### MINOR Fix List

- **find-implicit-state:** Add replay/campaign evidence for the successful detect/collapse/report workflow; current gates cover success and sideways only (`.claude/skills/find-implicit-state/SKILL.md:36` "How success is judged"; `.claude/skills/find-implicit-state/SKILL.md:248` "When things go sideways").
- **find-layer-violation:** Add replay evidence for the full detector/scout/report path; current gates stop at success and sideways handling (`.claude/skills/find-layer-violation/SKILL.md:36` "How success is judged"; `.claude/skills/find-layer-violation/SKILL.md:240` "When things go sideways").
- **find-omnibus:** Fix the bucket-count typo (`.claude/skills/find-omnibus/SKILL.md:37` "The three buckets" while naming four buckets) and add replay evidence.
- **find-query-mutation:** Add replay evidence and make the scout verdict merge contract explicit; current success gate requires "final output separates confirmed mutations" (`.claude/skills/find-query-mutation/SKILL.md:32`) but does not include a replay case.
