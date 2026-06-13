---
name: extract-state-type
description: Read-only EXPLAIN skill that converts a function operating on an implicit mutable dict (or ad-hoc kwargs/namespace) into a typed @dataclass or TypedDict migration plan. Produces reports/extract-state-type/<target>/proposal.md with the current-shape table, proposed type definition, caller-by-caller migration plan, characterization-test matrix, and stop condition. Hands off to /fix-workflow or manual migration.
argument-hint: "<implicit-state:ID-or-explicit-target>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A function operating on an implicit mutable dict / ad-hoc kwargs /
  namespace that should become a typed @dataclass or TypedDict.
  Produces current-shape table, proposed type, caller-by-caller
  migration plan, characterization-test matrix.
not_for: |
  Stringly-typed status fields on a Django model (use /extract-enum).
  Tuple-inferred FK identity (use /introduce-fk). Refactor execution
  (use /fix-workflow).
language: python
framework: django
---

# /extract-state-type

You are the **orchestrator** for an EXPLAIN skill that converts an
implicit-dict state contract into a typed proposal. A function
operates on a dict whose shape lives in its reads and writes rather
than in a `@dataclass` or `TypedDict`; your job is to read the
function + callers, infer the shape, and emit a proposal that
`/fix-workflow` (or a human) can execute.

This skill pairs with `/find-implicit-state` (SUSPECT — detects the
smell) and hands off to `/fix-workflow` (REFACTOR — executes the
migration). You write the proposal; you do NOT edit production code.

Procedural detail lives in the knowledge files:

- `knowledge/state-conventions.md` — scout-facing rules for
  dataclass vs `TypedDict`, state-type location, and dynamic-key stop
  conditions.
- `knowledge/proposal-template.md` — the exact shape of
  `reports/extract-state-type/<target>/proposal.md`.
- `agents/state-profiler.md` — scout brief for dict-shape inference.

## How success is judged

- `proposal.md` matches `knowledge/proposal-template.md`: current-shape
  key table, complete `@dataclass` / `TypedDict` definition, one caller
  row per file from the scout's grep pass, and a stop condition.
- Stage 1 pasted output includes the exact `collect_target.py` command
  and its `wrote ... (dict_candidates=..., callers=...)` line; Stage 2
  is judged by the `profile.md` file the scout writes, not by a claim.
- The characterization-test section is present and concrete — the
  shape `/fix-workflow` must write before any edit is non-optional.
- One scout, one proposal, one target; extras go to Follow-on findings.
- Nothing outside `reports/extract-state-type/<slug>/` was touched —
  the proposal is the handoff artifact, never the execution.
Write toward these gates from Stage 0.

## Core beliefs

1. **The dict IS the contract.** Every read of a key is a caller
   promise; every write is an implementer commitment. The proposal
   writes those promises down in a type, nothing more, nothing less.
2. **`@dataclass` for mutable state, `TypedDict` for boundary state.**
   Mutable state flowing through a pipeline → `@dataclass` with
   `field(default_factory=...)`. State that crosses a boundary
   (API payload, cache entry, log record) → `TypedDict`. The
   profiler flags which shape applies; the proposal uses that flag.
3. **Caller impact is the migration's real cost.** A dataclass
   that's clean in the target but breaks ten callers is a worse
   proposal than a slightly messier dataclass that only touches the
   target. The proposal enumerates every caller and its change set.
4. **Characterization tests pin behavior.** The proposal names the
   test shape `/fix-workflow` must write BEFORE any edit. Same
   pattern as `/refactor-subsystem`'s Phase 2.1 — capture the
   current behavior, migrate, confirm unchanged.
5. **Scouts read, orchestrator synthesizes.** One scout profiles the
   function + callers; the orchestrator consolidates into the
   proposal.

## Scope

- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` for helper scripts.
- **Output:** `reports/extract-state-type/<target-slug>/`. Never
  touches any other file.
- **Project-specific conventions** (known implicit-state targets,
  dataclass location, naming): `knowledge/state-conventions.md`.
  Scouts read that file; the orchestrator does not.

## Argument parsing

Two forms:

### Form A — finding reference
Pattern: `implicit-state:<candidate-id>` (the candidate-id format
`/find-implicit-state` emits in its `candidates.jsonl`).

Resolve manually against `reports/implicit-state/latest/candidates.jsonl`;
`collect_target.py` does not implement `--from-finding`. Strip the
optional `implicit-state:` prefix, read the matching JSONL record,
extract its target `file` and `symbol`, and then continue as Form B by
calling `collect_target.py --file ... --symbol ...`.

```bash
RAW_FINDING="<implicit-state-id-or-prefixed-id>"
FINDING_ID="${RAW_FINDING#implicit-state:}"
.venv/bin/python -c '
import json, sys
from pathlib import Path
finding_id = sys.argv[1]
path = Path("reports/implicit-state/latest/candidates.jsonl")
for line in path.read_text(encoding="utf-8").splitlines():
    record = json.loads(line)
    if record.get("candidate_id") == finding_id or record.get("id") == finding_id:
        print(json.dumps({
            "file": record.get("file"),
            "symbol": (record.get("symbols") or [None])[0],
            "pattern": record.get("pattern"),
            "recommendation_hint": record.get("recommendation_hint"),
        }))
        break
else:
    raise SystemExit(f"finding not found: {finding_id}")
' "${FINDING_ID}"
```

Only candidates whose sub-shape is `implicit_dict_state` are valid
for this skill — other sub-shapes (stringly-typed state, tuple-
inferred identity) belong to `/extract-enum` or `/introduce-fk`.

Note: as of the current `/find-implicit-state` version,
`implicit_dict_state` is NOT surfaced as a distinct sub-shape — the
detector targets stringly-typed state and tuple-inferred identity
only. If the Form-A candidate's sub-shape isn't `implicit_dict_state`,
abort with a one-line error redirecting to `/extract-enum` or
`/introduce-fk`. If no matching detector ships, fall through to
Form B and ask the user to specify the target explicitly.

### Form B — explicit target
Pattern: `<file>::<function>` or `<file>::<Class>.<method>`.

Examples:
- `core/services/agentic_discovery_service.py::AgenticDiscoveryService.discover`
- `core/services/field_discovery_pipeline_service.py::discover_fields`
- `core/services/agentic_discovery_service.py::discover` (shorthand —
  the first function named `discover` in the file)

Derive the slug: `<file-stem>__<bare-symbol>`. Examples:
- `agentic_discovery_service__discover`
- `field_discovery_pipeline_service__discover_fields`

### Budget
One scout, one proposal, one target. This skill does NOT fan out
across N targets. If the finding references multiple implicit-dict
states (rare), pick the highest-confidence one and note the rest in
`## Follow-on findings`.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** `$REPORT_DIR` exists,
`latest` symlink updated.

```bash
TARGET_SLUG="<derived slug>"
REPORT_DIR="reports/extract-state-type/${TARGET_SLUG}"
mkdir -p "${REPORT_DIR}"
ln -sfn "${TARGET_SLUG}" reports/extract-state-type/latest
```

Target-keyed path (not timestamped) — re-runs against the same
target converge, and the git history of `proposal.md` is the
historical record.

### Stage 1 — Collect target + callers

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/targets.json` with
the function signature, the dict-state parameter (by inference), and
the caller list.

```bash
.venv/bin/python .claude/skills/extract-state-type/scripts/collect_target.py \
  --file "<file-path>" \
  --symbol "<qualified-symbol>" \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/targets.json"
```

The helper does three things:

1. Reads the function and records its signature, line range, and
   docstring.
2. Heuristically identifies the dict-state variable — the first
   local assignment in the body of the form `<name> = {...}` or
   `<name> = dict(...)`, or a parameter annotated as `dict` /
   `Dict[str, ...]`. If ambiguous, lists all candidates; the scout
   disambiguates at Stage 2.
3. Greps inbound callers (`from <module> import <symbol>`,
   `<Cls>().<method>(`, bare calls for module functions) and
   records file + symbol + approximate line for each.

Output schema is documented in the helper's module docstring.

If the helper returns zero callers, the proposal will note "no
external callers — migration affects only the target function and
its private helpers"; that's a valid and cheaper migration.

### Stage 2 — Profile (single scout)

**Pre:** `targets.json`. **Post:**
`${REPORT_DIR}/profile.md` — the full dict-shape inference + caller
impact.

Dispatch **one** scout with `agents/state-profiler.md`. Substitute
`{{target_slug}}`, `{{file_path}}`, `{{symbol}}`, `{{dict_variable}}`,
`{{callers_path}}`, `{{project_root}}`, `{{skill_root}}`,
`{{output_path}}`, `{{targets_json_path}}`.

Tell the scout its output is judged only by `{{output_path}}`: it must
write the profile shape from `agents/state-profiler.md`, including the
metadata status and caller impact table. A message saying the profile is
complete does not satisfy Stage 2 without the file.

The scout:

1. Reads the target function in full.
2. Walks the body AST (via `Read` + manual inspection), listing
   every key read (`state['k']`, `state.get('k')`, `state.get('k', d)`)
   and every key write (`state['k'] = v`, `state.setdefault('k', v)`,
   nested mutations like `state['budget']['k'] = v`).
3. Classifies each key as required (always written before first
   read) or optional (read via `.get` with a default, or written
   only on some branches).
4. Infers each key's type from the literal(s) assigned or the shape
   of the values written.
5. Detects nested dict structure — a key whose value is itself a
   dict with its own implicit shape becomes a nested dataclass or
   a nested `TypedDict`.
6. Greps every caller file listed in `targets.json` and records
   whether the caller constructs the dict, mutates it, reads keys
   from the return value, or all three.
7. Classifies the recommended shape: `dataclass` (mutable state),
   `TypedDict` (boundary state — crosses process / cache / log).
8. Writes `profile.md` per the template in the scout brief.

If the scout returns `profile_incomplete`, re-dispatch once with a
stricter "respond only with file-write confirmation" nudge. If it
fails twice, write a minimal proposal that documents the failure
and suggests re-running.

### Stage 3 — Synthesize the proposal

**Pre:** `profile.md` exists. **Post:**
`${REPORT_DIR}/proposal.md`.

Read `profile.md` and `targets.json`. Write `proposal.md` following
`knowledge/proposal-template.md` exactly. Top-level structure:

1. Target metadata (path, symbol, target kind, regenerated timestamp).
2. **Current shape (implicit dict)** — table of every key with
   type, required/optional, default, mutation sites.
3. **Proposed type definition** — a complete `@dataclass` or
   `TypedDict` block, ready to paste into a new
   `<module>/state.py` file. Include imports.
4. **Migration plan** — numbered steps, from "add type" through
   "update target" through "update each caller" through "remove
   dict-only code paths."
5. **Caller table** — one row per caller file with the exact
   change (construction, key read, key write). Pull from the
   scout's grep pass in Stage 2.
6. **Characterization tests** — the exact test shape `/fix-workflow`
   must write before migration. Based on the current return shape
   and side-effects. This section is non-optional.
7. **Test matrix** — baseline (from `_common/skill-conventions.md`) plus the
   file-specific suites from the `File(s) touched` table.
8. **Stop condition** — checklist. Must include: type added,
   imports updated, callers updated, characterization tests pass
   unchanged, `/find-implicit-state` re-run shows zero
   `implicit_dict_state` hits for this target.
9. **Follow-on findings** — adjacent implicit-dict-state candidates
   surfaced but not addressed here. Seeds for future
   `/extract-state-type` runs.
10. **Authorization** — one line: "Human review required before
    `/fix-workflow extract-state-type:<target>` or manual
    execution."

### Stage 4 — Effectiveness log

**Pre:** proposal.md written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
FIELD_COUNT=$(grep -c '^| `' "${REPORT_DIR}/proposal.md" || echo 0)
CALLER_COUNT=$(.venv/bin/python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["callers"]))' "${REPORT_DIR}/targets.json")
SHAPE=$(grep -oE '(dataclass|TypedDict)' "${REPORT_DIR}/proposal.md" | head -1 || echo unknown)

.venv/bin/python scripts/log_effectiveness.py \
  --skill extract-state-type \
  --scan-id "extract-state-type-${TARGET_SLUG}-$(date -u +%Y%m%d-%H%M%S)" \
  --target "<original-target-spec>" \
  --findings-total "${FIELD_COUNT}" \
  --buckets "{\"shape\": \"${SHAPE}\", \"fields\": ${FIELD_COUNT}, \"callers\": ${CALLER_COUNT}}"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- Target + shape (`dataclass` or `TypedDict`).
- Field count + caller count.
- Path to `${REPORT_DIR}/proposal.md`.
- Test matrix summary (baseline + per-subsystem).
- Stop-condition checklist count.
- Recommended next step: `/fix-workflow extract-state-type:<slug>`
  for the human-approved execution path, OR manual migration if
  the proposal reviewer prefers. Do NOT start `/fix-workflow`
  yourself — the proposal is the handoff artifact.

Do not enumerate fields in the summary — the proposal is the source
of truth.

## Replay / smoke

For a no-production-code replay, create a tiny Python fixture with one
function that initializes and mutates a `state = {...}` dict, then run
`collect_target.py --file <fixture> --symbol <function> --project-root
<fixture-root> --output <tmp>/targets.json`. Paste the command output
showing `dict_candidates=1` and the output JSON path. This replay proves
the executable Form-B contract that Form A resolves into.

## Non-goals

- Executing the migration (that's `/fix-workflow`).
- Detecting new implicit-dict states elsewhere (that's
  `/find-implicit-state`; the sub-shape isn't shipped yet — Form B
  remains the robust entry for now).
- Proposing a dataclass when the dict is a boundary object (use
  `TypedDict`); proposing a `TypedDict` when the dict is mutated in
  place across a pipeline (use `dataclass`). The scout classifies;
  the orchestrator respects that.
- Touching files outside `reports/extract-state-type/<slug>/`.
- Running tests — the proposal lists the matrix; `/fix-workflow`
  runs it.
- Rewriting the target's private helpers. The proposal covers the
  public contract (dict → type); private helpers change as a
  consequence, and their line-by-line edits belong to
  `/fix-workflow`.

## When things go sideways

| Symptom | Action |
|---|---|
| Form-A candidate sub-shape is not `implicit_dict_state` | Abort with a one-line error: "that candidate is a <sub-shape> — use /extract-enum or /introduce-fk"; don't silently fall back |
| Form-B target file doesn't exist | Abort with a one-line error + suggest correct path |
| Target function has no dict-state — it's just a function | Abort with a one-line "target has no implicit-dict-state; re-check the target"; don't produce an empty proposal |
| `targets.json` lists 0 callers | Proceed; the proposal notes "no external callers" in the caller table and the migration is cheaper |
| Scout returns `profile_incomplete` first try | Re-dispatch once with a stricter nudge |
| Scout disagrees on `dataclass` vs `TypedDict` between runs | Rare, but if it happens: prefer `dataclass` for any state that is mutated after construction; `TypedDict` only for state that is constructed once and read-only thereafter |
| The dict's shape is too dynamic to type (arbitrary string keys) | The scout flags it; proposal says "dict is dynamic — do NOT typeify; document the string-key convention in a docstring instead" and stops |
| Nested dict is deeply conditional (5+ branches each write different keys) | Propose a union of dataclasses discriminated on a single field; the scout's profile lists the discriminator candidates |

## Repository layout

```
.claude/skills/extract-state-type/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   └── collect_target.py            # Stage 1 target+caller inventory (stdlib-only)
├── agents/
│   └── state-profiler.md            # Stage 2 scout brief
└── knowledge/                       # scout context, never loaded by orchestrator
    ├── state-conventions.md         # shape decision rules
    └── proposal-template.md         # Stage 3 output template + worked example
```

The orchestrator (you) **never reads files in `knowledge/`**. Those
are for the scout sub-agent. Keeping them out of your context is the
whole point of this architecture.
