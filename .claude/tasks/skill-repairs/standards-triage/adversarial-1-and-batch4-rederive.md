# Adversarial refutation (batch 1 remainder) + batch-4 OK/MINOR re-derivation

Independent cross-model lane, same method as `adversarial-4-5.md`:
re-derived every verdict from ground truth (read SKILL.md + referenced
files, ran real script `--help` / read-only dry runs, read argparse
source). Standard applied:
`.claude/skills/repair-skill/knowledge/skill-standard.md`. Calibration
applied: reviewer blind spots = runtime-dependency depth,
scaffold/artifact-content claims, internal contract consistency between
stages, inconsistent standards-element triage.

## Part 1 — remaining batch-1 OK verdicts + two MINOR spot-checks

| Skill | Original | My verdict | Evidence |
|---|---|---|---|
| architecture-fit | OK | **MINOR** | Scope block asserts "**Python:** `python3` (stdlib-only)" (`SKILL.md:81`) and Stages 1/5 document bare-`python3` invocations (`SKILL.md:105-106` `python3 scripts/decisions.py audit --json` / `list --json`; `SKILL.md:193` `python3 scripts/plans.py audit`). Ground truth: both scripts import `_lib.yaml_frontmatter` (`scripts/decisions.py:59`, `scripts/plans.py:53`), which does unconditional `import yaml` (`scripts/_lib/yaml_frontmatter.py:37`, no fallback) — the "stdlib-only" claim is false, and the commands work only where system python3 carries PyYAML. Same defect class as the which-skill flip in `adversarial-4-5.md`; severity matched to that precedent. Everything else verified clean: all three subcommands + `--json` flags match argparse; the plan scaffold (`scripts/plans.py:144-150`) really emits `## 5. Architecture Fit` and `## 6. Open Decisions`; `impacted`/`architected` are in `VALID_STATUSES` (`plans.py:55-62`); the "no constraining priors" cross-contract is real — `/plan-spec` Stage 1 demands exactly that note (plan-spec `SKILL.md:107-112`); `/decide` supersede form exists; sideways table present. |
| design-it-twice | OK | **CONFIRMED-OK** | What I checked: no scripts to mismatch; every referenced file exists (`CONTEXT.md` at repo root, `.claude/docs/canonical-patterns.md`, `.claude/docs/architectural-smells.md`, `ai-docs/decisions/`); Stage 2 brief's output naming (`design-axisN-<axis-slug>.md`) matches the Stage 3 template links; `${SCAN_DIR}` is assigned in Stage 0 before the brief uses it (unlike plan-spec's orphan `${SPEC_ID}`); the dispatch brief carries its judging criterion ("Do not produce a balanced compromise — that's not your job"), satisfying element 5; success block, sideways table, non-goals all present and mutually consistent; `scout_model: careful` is in-vocabulary (2 skills use it); handoff target `/decide <slug>` exists. Only nit found: frontmatter description says "Writes one comparative-design document" while the run writes 4 files — the Scope block corrects this explicitly, not material. |
| explain-code (spot-check) | MINOR | **NEEDS-REPAIR** | Internal contract contradiction at the load-bearing synthesis stage — the known blind spot. Stage 3 mandates "Write the top-level doc following `knowledge/explanation-format.md` ... (see knowledge file for the exact template)" (`SKILL.md:214-216`), while the layout section forbids it: knowledge/ is labeled "scout context, never loaded by orchestrator" (`SKILL.md:319`) and "The orchestrator (you) **never reads files in `knowledge/`**" (`SKILL.md:323-325`). The knowledge file itself is orchestrator-facing — `knowledge/explanation-format.md:4-5`: "This doc is the canonical reference for what Stage 3 emits." No compensating path: `agents/annotate.md` contains zero references to knowledge/ or the format file (grep verified), so the Scope claim "Scouts read that file" (`SKILL.md:92-94`) is also false. Every run necessarily violates one of the two mandates: honor the prohibition and invent the exact template, or follow Stage 3 and break the declared architecture. The originally-cited sidecar issue (`unexplained.txt`/`surprises.txt`) is real but guarded (`SKILL.md:241-250` defaults to 0) — that alone was MINOR; the contradiction is repair-grade. |
| extract-enum (spot-check) | MINOR | **NEEDS-REPAIR** | Same defect class that earned introduce-fk its NEEDS-REPAIR (confirmed supportable in `adversarial-4-5.md`): `knowledge/` is an **empty directory** (ls verified, zero files) while the SKILL makes it load-bearing three times — "Project-specific defaults ... `knowledge/`. The scout reads that file" (`SKILL.md:96-98`), "See `knowledge/` for project-specific gotchas the proposal's risk section should cover (third-party bridges, Celery resilience retries, legacy ExternalSource imports)" (`SKILL.md:309-311`), and the layout claims `knowledge/ └── (host-overlay specifics).md` (`SKILL.md:384-385`). Compounding internal inconsistency: the scout brief `agents/enum-profiler.md` contains zero knowledge/ references (grep verified), so "the scout reads that file" is unimplemented in the dispatch contract. The proposal's risk section — the part the skill calls load-bearing — must be invented. Severity parity with introduce-fk demands NEEDS-REPAIR. Everything else clean: `scripts/collect.py` argparse matches Forms A/B flag-for-flag (`--from-finding/--findings/--target/--model-class/--project-root/--output`), documented exit codes 0/1/2 match the script docstring, and `reports/implicit-state/latest/findings.json` is really produced by find-implicit-state (its `SKILL.md:199,206` + `latest` symlink at `:74`). |

## Part 2 — batch-4 OK/MINOR table, re-derived fresh (7 skills)

Batch-4's surviving NEEDS-REPAIR set (find-standard-gaps,
find-transaction-overreach, find-workflow-duplication,
find-workflow-state-gaps, introduce-fk, map-subsystem) is taken as
given; these are fresh ground-truth verdicts for the other 7. The lost
table claimed 4 MINOR / 3 OK for this set; I find 3 NEEDS-REPAIR /
2 MINOR / 2 OK — consistent with the calibrated blind spots
(element-triage inconsistency, orphan scripts, internal contract
consistency).

| Skill | Verdict | One-line reason |
|---|---|---|
| find-test-obligation-drift | NEEDS-REPAIR | 58-line skill missing standard elements 1, 2, and 7 entirely, with host-specific `/sites` scope baked into a shipped kit skill — same shape as find-workflow-state-gaps, which is already in the NEEDS-REPAIR set |
| find-workflow-state-gaps | (in batch-4 NEEDS-REPAIR set — not re-judged) | — |
| gut-check | MINOR | Self-contradictory mandate on the precedents-absent path: success gate says report the absence, Scope and sideways table say skip silently |
| harvest-learnings | OK | Success block, sideways table, and knowledge contract all verified; `knowledge/output-schema.md` really carries the translation test + ADR-0020 activation schema it promises; no scripts to mismatch; ADR 0020 exists |
| impact-feature | MINOR | False "stdlib-only" claim (Stage 5 bare-`python3 scripts/plans.py audit` needs PyYAML) plus a phantom `--subsystems` flag in the sideways table; all elements present, dispatch helper real |
| map-product-workflow | NEEDS-REPAIR | 73-line skill missing standard elements 1, 2, and 7 entirely; script contract itself is clean and the host-descriptor dependency is declared honestly |
| mature-existing-ideas | NEEDS-REPAIR | Orphan helper script contradicting the skill's own description of who writes events, plus a 3×-referenced handoff skill that does not exist |
| orient | OK | Strongest skill in the set — success block, sideways table, fixed-schema contract, knowledge file, and `infer_state_signals.py` argparse all verified consistent |

### NEEDS-REPAIR defect specs

**find-test-obligation-drift** — standards-grounds (no execution defect
found). F1: no "How success is judged" block and no artifact-truth
gates anywhere in the 58-line file — `## Pipeline` (`SKILL.md:38`)
follows the intro directly (elements 1, 2). F2: no "When things go
sideways" table; the file ends at the detector-band list
(`SKILL.md:49-58`) with no failure path for bad git refs, empty diffs,
or a missing testing-doc (element 7). F3: host-specific `/sites`
surface baked into shipped-kit frontmatter and body (`SKILL.md:15`
best_for "backend `/sites` code without tests"; `:34-36`; `:57`) —
same host-leak class as its NEEDS-REPAIR sibling
find-workflow-state-gaps. Script contract verified clean:
`scripts/run.py` argparse matches `[paths...] --staged
--changed-from REF` exactly.

**map-product-workflow** — standards-grounds (no execution defect
found). F1: no "How success is judged" block — `## Scope`
(`SKILL.md:28`) to `## Pipeline` (`:39`) with no declared gates
(element 1). F2: no artifact-truth gate — nothing demands the script's
`wrote <output>` lines or checks the map is non-empty when the host
descriptor is missing (element 2; the empty-map case is the skill's own
declared edge, `SKILL.md:31-33`). F3: no "When things go sideways"
table — the file ends at `## Next Skills` (`:67-73`); no doctrine for
descriptor-absent, unparseable descriptor, or zero-route workflows
(element 7). Script contract verified clean: `scripts/generate.py`
argparse matches (`workflow` positional, `--scan-id`), and it really
writes both documented artifacts (`generate.py:204-210`).

**mature-existing-ideas** — coherence defects, map-subsystem parity.
F1: orphan script — `scripts/mature.py` (argparse: `slug --summary
--sources --clear-needs-research --clear-underdeveloped --batch
--json`) is invoked by **no pipeline stage**; it appears only in the
layout (`SKILL.md:333-334`). Element 4/6 violation. F2: the
frontmatter description (`SKILL.md:3` "the helper script appends the
resulting note event(s) and marker transitions") and the layout coda
(`:337-338` "the script writes the events deterministically")
contradict the body: Stage 0 and Stage 2 route every read and write
through `track-idea/scripts/track.py` (`SKILL.md:146,255-257,264-266`)
— verified executable (track.py `list --marker` and `event --kind
note/marker --markers-removed --summary` all match argparse). F3:
`/promote-idea-to-pattern` is referenced three times (`SKILL.md:26`
escalate_to, `:40`, `:304`) but `.claude/skills/promote-idea-to-pattern/`
does not exist (same nonexistent-handoff defect confirmed for
query-patterns/brainstorm-ideas). F4 (minor contributor): argument-hint
(`SKILL.md:4`) omits `--external-research`, which all three documented
forms accept (`:103,113,123,130`).

### MINOR one-line fixes

- **gut-check** — align `SKILL.md:136-137` ("skip silently and rely on
  ADR matching only") and the sideways row at `:485` ("Skip precedent
  matching silently") with the declared success gate at `:85-87` and
  Stage 1 at `:206-208`, which both require the report to state that
  precedent matching was unavailable for the run.
- **impact-feature** — change `SKILL.md:74` "(stdlib-only)" and the
  Stage 5 invocation at `:227` to `.venv/bin/python` (or drop the
  stdlib claim; `scripts/plans.py:53` → `_lib/yaml_frontmatter.py:37`
  needs PyYAML), and either implement or remove the `--subsystems`
  re-run form cited in the sideways table at `:256` (no form defines
  it; argument-hint at `:4` is `<plan-name>` only).

## Calibration notes for the program

1. **The lost batch-4 table was too lenient on its OK/MINOR half.**
   Three of its seven OK/MINOR skills are independently NEEDS-REPAIR —
   two on the exact standards-element grounds (missing 1/2/7) the same
   reviewer used to fail find-workflow-duplication and
   find-workflow-state-gaps in the same batch, confirming blind spot
   (3): element triage was applied only where prose defects were
   already suspected.
2. **The empty-`knowledge/` class is bigger than introduce-fk and
   unify-shadows.** extract-enum has the identical defect (empty dir +
   "the scout reads that file" + load-bearing risk-section pointer),
   and explain-code has the inverted form (an orchestrator-facing
   knowledge file the orchestrator is forbidden to read). A class
   sweep over every `knowledge/` reference — does the dir have files;
   does the named consumer's brief actually read them — would be
   cheaper than per-skill loops.
3. **The bare-`python3`-vs-PyYAML trap now has three confirmed
   instances** (which-skill, architecture-fit, impact-feature) — any
   skill invoking `scripts/plans.py` or `scripts/decisions.py` with
   bare `python3` carries it; a one-line grep sweep
   (`python3 scripts/(plans|decisions)\.py`) closes the class.
