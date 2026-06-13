# Standards triage — batch 1 (delivered via final reply; orchestrator-landed)

| Skill | Verdict | One-line reason |
|---|---|---|
| adapt-project | NEEDS-REPAIR | Missing success-judged block and no failure-path table around script/evidence-gate failures |
| architecture-fit | OK | Script calls match `decisions.py`/`plans.py`; success gates, failure paths, and handoff rules are explicit |
| audit-decisions | NEEDS-REPAIR | Emits invalid `/decide --status` and `/decide --renumber` commands that don't exist |
| brainstorm-ideas | MINOR | Routes to missing `/promote-idea-to-pattern` skill and omits `--external-research` from argument hint |
| check-ecosystem-consistency | NEEDS-REPAIR | No verdict block, no staged pipeline gates, no failure table for bad refs or write errors |
| converge | NEEDS-REPAIR | Missing success-judged block; hardcoded `repair` bucket emits wrong verdict for other phase statuses |
| decide | MINOR | ADR template predates current `decisions.py init` scaffold (`namespace`, quoted `id`, `embodied_by`) |
| design-it-twice | OK | Divergence, dispatch, synthesis, handoff, and failure modes are all executable from text |
| engineer-init | MINOR | Good pipeline/failure table but missing the "How success is judged" block near top |
| explain-code | MINOR | Sidecar `unexplained.txt`/`surprises.txt` are consumed by logging but not explicitly mandated |
| extract-cotton-primitive | NEEDS-REPAIR | Profiler abort-on-zero-callsites contract is documented but not implemented — script exits 0 on empty |
| extract-enum | MINOR | `implicit-state:` prefix handling and `recommendation_hint` check are under-specified |
| extract-existing-ideas | NEEDS-REPAIR | Approved-survivor narrowing in Stage 3 is never written back; unapproved candidates reach the writer |
| extract-state-type | NEEDS-REPAIR | Form A `implicit-state:` resolver is advertised but no `--from-finding` flag exists in the helper |

---

## NEEDS-REPAIR

### adapt-project

F1. `.claude/skills/adapt-project/SKILL.md:49` — `## Forms` starts immediately after the intro; the standard requires a "How success is judged" block before execution steps.

F2. `.claude/skills/adapt-project/SKILL.md:86` — "Before claiming done, run the evidence gate" is the only artifact-truth gate, buried late with no upfront declaration.

F3. `.claude/skills/adapt-project/SKILL.md:187` — `## Inspiration` is the final section; no "When things go sideways" table covers `project_adapt.py` or `evidence_gate.py` failures.

---

### audit-decisions

F1. `.claude/skills/audit-decisions/SKILL.md:161` — `Resolution: /decide --status accepted 0007` names a `/decide` form that does not exist.

F2. `.claude/skills/audit-decisions/SKILL.md:288` — `recommend renumbering one via /decide --renumber` is another nonexistent `/decide` command.

F3. `.claude/skills/decide/SKILL.md:83` — Supported forms are `new`, `supersede`, `amend`, `list`; no `--status` or `--renumber` form.

F4. `scripts/decisions.py:352` — Real subcommands: `init`, `list`, `show`, `rebuild`, `audit`, `link-check`; no `status`/`renumber` subcommand exists.

Orchestrator spot-verify: occurrences are wider than cited — `/decide --status` also at SKILL.md:21, :162, :210, :256.

---

### check-ecosystem-consistency

F1. `.claude/skills/check-ecosystem-consistency/SKILL.md:42` — `## Forms` appears with no "How success is judged" block preceding it.

F2. `.claude/skills/check-ecosystem-consistency/SKILL.md:51` — "Script form:" documents only the bare invocation; `--changed-from`, `--staged`, `--update-state` forms lack a staged execution contract.

F3. `.claude/skills/check-ecosystem-consistency/SKILL.md:83` — "`--update-state` writes state" depends on reviewed findings but there is no mandated review gate before state is mutated.

F4. `.claude/skills/check-ecosystem-consistency/SKILL.md:88` — `## Relationship To /which-shape` is the final section; no failure-path table covers bad git refs, schema errors, write failures, or missing baseline.

---

### converge

F1. `.claude/skills/converge/SKILL.md:53` — `## Stage 1` starts the pipeline with no "How success is judged" block.

F2. `.claude/skills/converge/SKILL.md:73` — "find the strongest available evidence and cite it" permits assertion-by-citation without requiring pasted command/output artifacts.

F3. `.claude/skills/converge/SKILL.md:124` — `--buckets '{"status_repair": 1}'` hardcodes `repair` even when `phase_status` is `advance`, `branch`, `park`, or `discard`.

F4. `.claude/skills/converge/SKILL.md:139` — `## Known limits` replaces but does not provide the required "When things go sideways" failure table.

---

### extract-cotton-primitive

F1. `.claude/skills/extract-cotton-primitive/SKILL.md:150` — "If zero callsites can be loaded, exit 1" is the load-bearing abort condition documented in the skill.

F2. `.claude/skills/extract-cotton-primitive/scripts/profile.py:147` — `callsites = gather_callsites(...)` is accepted without a zero-count check.

F3. `.claude/skills/extract-cotton-primitive/scripts/profile.py:166` — `return 0` fires after writing the profile even when `callsite_count: 0`.

F4. Script-contract mismatch: SKILL.md says exit 1 on empty; script always exits 0, silently emitting an empty profile.

---

### extract-existing-ideas

F1. `.claude/skills/extract-existing-ideas/SKILL.md:101` — Documented pipeline command writes to `/tmp/extract-candidates.json`, not a project-local artifact.

F2. `.claude/skills/extract-existing-ideas/SKILL.md:150` — "Ask the user which to drop, rewrite, or send unchanged" creates an approved survivor set.

F3. `.claude/skills/extract-existing-ideas/SKILL.md:160` — Handoff still passes the original `/tmp/extract-candidates.json`; the approved survivors are never written back before the writer runs.

F4. `.claude/skills/extract-existing-ideas/scripts/extract.py:83` — Real helper has `--out` for a durable artifact; the SKILL.md pipeline bypasses it.

F5. `.claude/skills/extract-existing-ideas/SKILL.md:49` — "A candidates JSON plus a report exist" is listed as the success gate but no pipeline step writes the report.

---

### extract-state-type

F1. `.claude/skills/extract-state-type/SKILL.md:93` — `### Form A — finding reference` advertises an `implicit-state:` invocation path.

F2. `.claude/skills/extract-state-type/SKILL.md:97` — "Resolve against `reports/implicit-state/latest/candidates.jsonl`" is not backed by any Stage 1 invocation.

F3. `.claude/skills/extract-state-type/SKILL.md:153` — Stage 1 only documents `collect_target.py --file ... --symbol ...`.

F4. `.claude/skills/extract-state-type/scripts/collect_target.py:318` — `--file` is a required positional/flag; no `--from-finding` or candidates-jsonl resolver exists.

F5. `.claude/skills/extract-state-type/scripts/collect_target.py:320` — `--symbol` is also required; Form A's claimed resolution path has no implementation.

---

## MINOR

### brainstorm-ideas

Add `--external-research` to the argument hint; mark `/promote-idea-to-pattern` as future/planned since `.claude/skills/promote-idea-to-pattern/` does not exist.

### decide

Refresh the embedded ADR template to match `scripts/decisions.py init`: quote `id`, add `namespace: core`, add `embodied_by: []`.

### engineer-init

Add a near-top "How success is judged" block naming the runtime gates already present in Stage 5.

### explain-code

Either explicitly mandate `unexplained.txt` and `surprises.txt` output in Stage 3, or remove the Stage 4 sidecar counters that reference them.

### extract-enum

State that the orchestrator strips the optional `implicit-state:` prefix before passing `--from-finding`, and add an explicit `recommendation_hint` check before calling `collect.py`.
