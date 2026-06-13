# Standards triage — batch 2 (delivered via final reply; orchestrator-landed)

Orchestrator spot-verify: tools/code_agent.py confirmed ABSENT while
_common/dispatch_scout_cheap.sh:106 hard-invokes `-m tools.code_agent`
— the kit-wide cheap-scout dispatch path is broken (affects
find-dormant, which-cleanup, and the propose-boundary Stage-2 fix
landed earlier today, which pointed at this dead path).
.engineering/docs/product-workflows.md confirmed absent; workflows.py
treats absence as empty-yield by design, but the three SUSPECT
SKILL.mds promise a "/sites route surface" default — host residue.
Calibration note for the merge: several NEEDS-REPAIR verdicts rest on
missing verdict-block/failure-path elements in single-script scanners
that the class-1 sweep deliberately exempted — reconcile before
queueing repairs.

## Verdict Table

| skill | verdict | one-line reason |
|---|---|---|
| extract-workflow-registry | NEEDS-REPAIR | Default map is missing, script ignores the documented map input, and registry fields drift from the promised contract. |
| find-async-lifecycle-drift | NEEDS-REPAIR | Default no-path run silently depends on an absent workflow descriptor, plus multiple standard gates are missing. |
| find-comment-drift | NEEDS-REPAIR | Script contract and fixtures exist, but declared verdict and honest failure-path elements are missing. |
| find-complexity-hotspots | NEEDS-REPAIR | Argparse contract matches, but standard gates and replay wiring are missing from `SKILL.md`. |
| find-concept-divergence | NEEDS-REPAIR | Script contract matches, but declared verdict, failure path, and replay-case elements are missing. |
| find-contract-drift | NEEDS-REPAIR | Default no-path run depends on an absent workflow descriptor and the skill lacks standard gates. |
| find-dead-route-surface | NEEDS-REPAIR | Default no-path run depends on an absent workflow descriptor and the skill lacks standard gates. |
| find-doc-route-drift | NEEDS-REPAIR | Argparse contract matches, but multiple activation-standard elements are absent. |
| find-dormant | NEEDS-REPAIR | Default cheap scout path calls missing `tools.code_agent`; read-only tool contract also still exposes `Edit`. |
| find-duplication | MINOR | Pipeline is mostly executable; small command/tooling text fixes remain. |
| find-folder-topology-drift | NEEDS-REPAIR | Documented default root contradicts the real parser default, plus standard gates are missing. |
| find-frontend-contract-drift | NEEDS-REPAIR | Documented template/JS defaults contradict the real whole-repo scoped default, plus standard gates are missing. |
| find-frontend-duplication | MINOR | Main pipeline is executable; Stage 1 postcondition conflicts with the valid empty-inventory case. |

---

## NEEDS-REPAIR Details

### extract-workflow-registry

F1. Missing artifact: `SKILL.md:52` documents `--workflow-map .claude/docs/workflows/sites.md`; that path is absent on disk.

F2. Input contract drift: `SKILL.md:25` says "Convert" a workflow map, but `scripts/propose.py:112` derives entries via `workflow_steps(project_root)`, not from `args.workflow_map`.

F3. Output contract drift: `SKILL.md:61` says "always includes these fields" including `api_endpoints` / `api_endpoint_templates` at lines 72-73; `scripts/propose.py:26` `REGISTRY_FIELDS` ends at `frontend_boot_keys` with no endpoint fields.

---

### find-async-lifecycle-drift

F1. Default target is not executable from text alone: `SKILL.md:8` promises "defaults to the /sites route surface", but `scripts/run.py:30` passes `args.paths or None`, and `.claude/skills/_common/product_health.py:62` falls back to `workflow_targets(project_root)`.

F2. The hidden default source is absent: `.claude/skills/_common/workflows.py:13` says a repo with no descriptor yields empty results; `.engineering/docs/product-workflows.md` is absent on disk.

F3. Standards gap: `SKILL.md:38` only says output is "advisory"; the read `SKILL.md` has no declared success gate, failure path, or replay/smoke instruction.

---

### find-comment-drift

F1. Multiple standard elements are missing despite good script wiring: `SKILL.md:117` starts "required artifacts are" and `SKILL.md:143` has a `## Smoke Test` block, but the read `SKILL.md` has no "How success is judged" gate and no "When things go sideways" failure path.

---

### find-complexity-hotspots

F1. Missing standard gates: `SKILL.md:95` starts `## How To Summarize` but the read `SKILL.md` has no declared verdict block or honest failure-path table.

F2. Replay wiring absent from skill text: `scripts/smoke.py:55` defines the smoke `main()`, but `SKILL.md:44` only names `references/reading-notes.md` as the conditional supplementary read — no smoke invocation is documented.

---

### find-concept-divergence

F1. Missing declared verdict/failure gates: `SKILL.md:110` starts `## Pipeline` and `SKILL.md:134` starts `## Output triage`; the read `SKILL.md` has no "How success is judged" or "When things go sideways" section.

F2. Replay-case element absent: no fixture, smoke command, or conformance case is named anywhere in the read skill.

---

### find-contract-drift

F1. Default target is not executable from text alone: `SKILL.md:9` promises "defaults to the /sites route surface", but `scripts/run.py:30` passes `args.paths or None`, and `.claude/skills/_common/product_health.py:62` falls back to `workflow_targets(project_root)`.

F2. The hidden workflow descriptor is absent: `.engineering/docs/product-workflows.md` is absent on disk.

F3. Standards gap: `SKILL.md:39` goes straight to `## Pipeline`; the read `SKILL.md` has no declared verdict, failure path, or replay/smoke instruction.

---

### find-dead-route-surface

F1. Default target is not executable from text alone: `SKILL.md:8` promises "defaults to the /sites route surface", but `scripts/run.py:30` passes `args.paths or None`, and `.claude/skills/_common/product_health.py:62` falls back to `workflow_targets(project_root)`.

F2. The hidden workflow descriptor is absent: `.engineering/docs/product-workflows.md` is absent on disk.

F3. Standards gap: `SKILL.md:32` goes straight to `## Pipeline`; the read `SKILL.md` has no declared verdict, failure path, or replay/smoke instruction.

---

### find-doc-route-drift

F1. Missing standard gates: `SKILL.md:26` starts `## Scope`, `SKILL.md:36` starts `## Pipeline`, and `SKILL.md:61` starts `## Next Skills`; the read `SKILL.md` has no declared success gate, failure path, or replay case.

---

### find-dormant

F1. Default Stage 3 path is broken on disk: `SKILL.md:187` mandates `tools/code_agent.py --read-only`, and `.claude/skills/_common/dispatch_scout_cheap.sh:106` runs `"$VENV_PYTHON" -m tools.code_agent`; no `tools/code_agent.py` module exists on disk.

F2. Second missing artifact: `SKILL.md:214` says "see `tools/agent-config.json`"; that file is absent on disk.

F3. Still-broken allowed-tools: `SKILL.md:5` includes `Edit`, while `SKILL.md:44` says "Nothing is deleted" and recommendations route elsewhere — the read-only intent contradicts the declared tool list.

---

### find-folder-topology-drift

F1. Default-root contract contradicts argparse: `SKILL.md:41` says "Default root: `app/`", but `scripts/detect.py:517-518` describes `--root` as "Optional subtree" with default "the whole repo".

F2. Frontmatter/scope also disagree: `SKILL.md:4` hints `--root core` while `SKILL.md:41` says default `app/`.

F3. Standards gap: `SKILL.md:64` starts `## Pipeline`; the read `SKILL.md` has no declared verdict, honest failure path, or replay case.

---

### find-frontend-contract-drift

F1. Default-root contract contradicts argparse: `SKILL.md:32-33` says "Default template root: `templates/`" and "Default JS root: `static/js/`"; `scripts/detect.py:721` and `:730` say default is "the whole repo".

F2. Pipeline omits the flags that would make the documented defaults true: `SKILL.md:43` runs `detect.py` with only `--output`.

F3. Standards gap: `SKILL.md:37` starts `## Pipeline`; the read `SKILL.md` has no declared verdict, failure path, or replay case.

---

## MINOR Details

### find-duplication

- fix: remove `Edit` from `SKILL.md:5` (`.claude/skills/find-duplication/`) because `SKILL.md:191` states "Editing files" is a non-goal.
- fix: change `SKILL.md:166` invocation `python3 scripts/log_effectiveness.py` to `.venv/bin/python` to match the repo's explicit venv discipline.

### find-frontend-duplication

- fix: relax Stage 1 "non-empty" postcondition wording at `SKILL.md:82` — `scripts/cotton_inventory.py:443` prints "empty inventory" as a valid outcome when `kind: none`, so the postcondition should not gate on non-empty.
