---
name: unify-shadows
description: Turn one confirmed semantic-duplication finding into an evidence-cited, read-only proposal. Python retains the profile-scout workflow; TypeScript/TSX, checked-JavaScript, Go, Java, PHP, Ruby, bounded Rust, and Dart consume accepted structured evidence and emit proposal.md, evidence.json, and scope.json with source/caller impact, native tests, stop conditions, human approval, and an honest template for all four consolidation shapes.
argument-hint: "<semantic:SC-N | semantic:TS-SD-NNNN | semantic:JAVA-SD-NNNN | explicit target spec>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  One confirmed Python, TypeScript, checked-JavaScript, Go, or Java semantic-duplication finding from
  /find-semantic-duplication (shape =
  keep_separate_document_why | share_utilities | complete_migration |
  merge_at_workflow). Produces an implementation-ready proposal at
  `reports/unify-shadows/<finding-id>/proposal.md` with migration
  plan, caller impact, test matrix, and stop condition.
not_for: |
  Fresh candidate discovery belongs to /find-semantic-duplication. Lexical
  near-clones belong to /find-duplication and their downstream fix workflow.
  Source mutation begins only after human acceptance of this artifact.
language: any
framework: any
scans: [python, typescript, javascript, go, java, php, ruby, rust, dart, c]
---

# /unify-shadows

## C17 branch

Use `scripts/propose_c.py` with current accepted `c-semantic-duplication-v1`
facts and hash-bound human acceptance; run the script with `--help` for the
exact CLI. It emits exactly `proposal.md`, `evidence.json`, and `scope.json`;
keep-separate is complete. Static direct-call evidence is not equivalence, ABI
or external-consumer authority, survivor selection, or mutation approval.

## PHP and Ruby

For PHP, read `_php-proposal/GUIDE.md`; for Ruby, read
`_ruby-semantic/PROPOSAL-GUIDE.md`. Consume only current accepted semantic
evidence; keep-separate is a valid outcome and no equivalence is implied.

## Dart v1

Dart v1 consumes one content-addressed human acceptance from the Dart branch
of `/find-semantic-duplication`. It revalidates the source/configuration
snapshot, selected finding and review hashes, capability matrix, consolidation
shape, and every member/caller citation before writing exactly `proposal.md`,
`evidence.json`, and `scope.json`. It launches no Dart process and never reruns
detection or edits host source.

```bash
SKILL_ROOT=".agents/skills/on-demand/unify-shadows"
python3 "${SKILL_ROOT}/scripts/propose_dart.py" \
  --project-root "$PWD" \
  --evidence-dir "$PWD/reports/semantic-duplication/dart" \
  --acceptance "$PWD/reports/semantic-duplication/dart/reviews/DART-SD-0001.json" \
  --output-dir "$PWD/reports/unify-shadows/DART-SD-0001"
```

Missing, pending, partial, tampered, or stale evidence produces a visible
three-artifact refusal. `keep_separate_document_why` is a successful proposal
outcome; no equivalence, survivor, refactor-safety, runtime, external-consumer,
generated/part/conditional, Flutter, or framework claim is implied.

## Rust v1

Read `knowledge/rust-v1.md`. Consume one accepted Rust semantic-duplication
record, its matching content-addressed fact pack, and capability matrix. Select
one consolidation shape explicitly and render a read-only proposal; never
rerun detection or claim behavioral equivalence. No runtime `map-subsystem`
companion is needed once accepted evidence exists.

```bash
SKILL_ROOT=".agents/skills/on-demand/unify-shadows"
python3 "${SKILL_ROOT}/scripts/propose_rust.py" \
  --analysis "$PWD/reports/semantic-duplication/rust/findings.json" \
  --facts "$PWD/reports/semantic-duplication/rust/facts.json" \
  --finding-id RUST-SD-0001 --shape share_utilities \
  --project-root "$PWD" \
  --proposal "$PWD/reports/unify-shadows/RUST-SD-0001/proposal.md" \
  --evidence "$PWD/reports/unify-shadows/RUST-SD-0001/evidence.json"
```

You are the **orchestrator** that narrows a semantic-duplication finding into
an actionable proposal. `/find-semantic-duplication` classified the cluster's
**shape** (keep separate / share utilities / complete migration / merge at
workflow) and wrote a capability matrix. Your job is to produce the
implementation spec `/fix-workflow semantic:<id>` will execute.

You do not write production code in this skill. The Python branch reads the
shadows in full, dispatches a scout per member, and consolidates their
profiles. The TypeScript branch validates and renders the accepted structured
finding without re-detection. The human reviews either proposal before
authorizing `/fix-workflow`.

## Go v1

For a Go finding, read and follow `knowledge/go-v1.md`; load it only for Go
work. The Go branch validates one complete, confirmed upstream artifact and
renders a proposal without re-detection or source mutation. It preserves the
upstream warning that a static review lead is not behavioral equivalence.

## Java 17 v1

For a Java finding, read `knowledge/java-v1.md`. The Java branch consumes one
complete accepted finding and its capability matrix, validates current member
and direct-caller citations, and writes a read-only proposal. It never reruns
detection or upgrades matching record construction into behavioral equivalence.

## How success is judged

- In the Python branch, `reports/unify-shadows/<finding-id>/proposal.md` exists with every
  shadow member profiled at `profiles/<member-key>.md` — divergences
  in signature, callers, return contract, and retry/resource semantics
  are documented per member, never asserted equivalent without
  evidence.
- The scan's `consolidation_shape` is respected; in-tree "INTENTIONAL
  shadow" comments are cited, not overridden.
- One proposal per finding; the handoff target `/fix-workflow
  semantic:<id>` can execute it. Zero production-code edits here.
- Scout profiles and final proposal claims cite artifacts: current
  `file:line` references, capability-matrix rows, or pasted scout
  output. Equivalence claims without citations do not satisfy the gate.
- A Python final reply pastes the exact Stage 1 collection output and the
  Stage 4 effectiveness-log output, or states the command and exit code
  that prevented logging.
- A TypeScript run accepts exactly one `confirmed`, function-level record
  from the accepted `findings.json` schema. Missing, uncertain, rejected,
  wrong-skill, wrong-language, wrong-level, malformed-source, or unsupported-
  shape input exits 2 before any proposal artifact exists.
- A TypeScript run writes `proposal.md`, `evidence.json`, and `scope.json`
  beneath `reports/unify-shadows/<finding-id>/`, cites every member source
  span and the capability-matrix rows, includes honest caller limitations and
  host-native typecheck/test commands, and leaves all `.ts`/`.tsx` source
  bytes unchanged.
- `keep_separate_document_why` is complete when it documents separation. Its
  proposed-action body contains no consolidation or caller-move plan. The
  other three shapes include source/caller impact, native tests, a stop
  condition, explicit human approval, and a read-only handoff.
- A Java run consumes one complete `JAVA-SD-*` record, preserves upstream and
  consumer fingerprints, and rejects stale/unconfirmed/partial evidence before
  creating any proposal directory.
Write toward these gates from Stage 0.

## Core beliefs

1. **Shape is load-bearing.** The scan's `consolidation_shape` field decides
   what "done" looks like. Don't propose merging shadows the scan classified
   `keep_separate_document_why` — the team already made that decision and
   documented it in-tree. Shape-specific proposal bodies live in
   `knowledge/proposal-templates.md`; project-specific exceptions come from
   the triage notes, capability matrix, and in-tree comments.
2. **One proposal per finding.** If you open a second cluster mid-run,
   stop — emit a follow-on finding and let the user invoke the skill
   again.
3. **Respect in-tree comments.** "INTENTIONAL shadow — Do not unify"
   comments are authoritative; the proposal cites them rather than
   overriding.
4. **Scouts read, orchestrator consolidates.** Each shadow gets its own
   scout (`agents/shadow-profiler.md`). The orchestrator merges profiles
   into the proposal.
5. **Share utilities must be deep enough.** A tractable helper should
   hide repeated behavior without forcing a shape collapse. Apply the
   deletion test from `.claude/skills/_common/interface-depth.md` before
   proposing any new shared helper or seam.

## Scope

- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` for repo scripts and Django-touching
  reads.
- **Worktree guard:** `/fix-workflow` will check the worktree before
  editing; this skill is read-only — no guard required here.
- **Proposal templates:** `knowledge/proposal-templates.md`. The
  orchestrator reads the section for the scan's `consolidation_shape`
  during Stage 3; scouts do not read it.

## TypeScript / TSX and checked-JavaScript v1 — structured proposal consumer

This branch consumes the final machine-readable output from the accepted
TypeScript or checked-JavaScript path of `/find-semantic-duplication`. It does not parse the legacy
triage Markdown, run scouts, re-detect duplication, or infer framework/runtime
behavior. The input must have:

- `skill: "find-semantic-duplication"` and matching `language: "typescript"` or
  `language: "javascript"` selected with `--language`;
- exactly one selected record in both `confirmed` and the accepted public
  `findings` list;
- `investigation_status: "confirmed"`, `level: "function"`, at least two
  `.ts`/`.tsx` members with current source spans, and one of the four supported
  `consolidation_shape` values;
- a readable capability matrix beside `findings.json` with the static return,
  returned-fields, direct-call, and exception/async evidence rows.

The typed-source detector's `caller_count` covers compiler-resolved incoming
calls from its eligible candidate graph. It does **not** carry complete
project caller locations. The proposal renders `null`/`-1` as unknown and
requires a full language-service/reference inventory before approval; it
never converts unknown or zero into a claim that no host callers exist.

The runner is intentionally skill-local and uses only the host's Node runtime
plus filesystem/JSON APIs. It writes no host source and needs no toolkit venv,
repository script, sibling skill, shared TypeScript service, or network call.
It records the host's declared `npm run typecheck` and `npm test` commands in
the test matrix without executing the refactor or tests itself.

Checked JavaScript accepts only current `.js`, `.jsx`, `.mjs`, and `.cjs`
member spans from a `language: "javascript"` confirmed finding. It preserves
the finding's complete/partial evidence boundary: partial, uncertain, malformed,
or unsupported input exits 2 before synthesis; it never upgrades an inferred
or lexical duplicate into a consolidation proposal.

### Installed TypeScript commands

Set `UNIFY_SHADOWS_SOURCE` to the pinned source/ref and install exactly this
selected skill from the target TypeScript host root.

<!-- installed-command:stock-install:start -->
```bash
: "${UNIFY_SHADOWS_SOURCE:?Set this to the pinned skill source/ref}"
npx --yes skills@1.5.19 add "${UNIFY_SHADOWS_SOURCE}" \
  --skill unify-shadows --agent codex --copy -y
```
<!-- installed-command:stock-install:end -->

Run the next block from that host root after the confirmed semantic scan. It
writes only beneath `reports/unify-shadows/`.

<!-- installed-command:typescript-proposal:start -->
```bash
: "${UNIFY_FINDINGS:?Set UNIFY_FINDINGS to the confirmed typed-source findings.json}"
: "${UNIFY_LANGUAGE:=typescript}" # typescript | javascript
: "${UNIFY_FINDING_ID:?Set UNIFY_FINDING_ID to one confirmed TS-SD identifier}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/unify-shadows" \
  ".claude/skills/unify-shadows"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "unify-shadows is not installed in .agents/skills or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/propose_typescript.mjs" \
  --findings "${UNIFY_FINDINGS}" \
  --finding-id "${UNIFY_FINDING_ID}" \
  --project-root "$(pwd)" \
  --language "${UNIFY_LANGUAGE}" \
  --proposal "reports/unify-shadows/${UNIFY_FINDING_ID}/proposal.md" \
  --evidence "reports/unify-shadows/${UNIFY_FINDING_ID}/evidence.json"
```
<!-- installed-command:typescript-proposal:end -->

The script resolves logical and physical paths before synthesis. Inputs must
stay inside the project root; outputs must stay beneath
`reports/unify-shadows/`; symlink traversal is rejected. Validation completes
before the output directory is created, so an invalid finding cannot leave a
partial proposal.

## Argument parsing

The forms below are the retained Python/scout branch. Typed-source uses the
installed structured proposal command above and requires a `TS-SD-*` finding
ID plus its exact `findings.json` path.

Two forms:

### Form A — Semantic finding ID
Pattern: `semantic:SC-N` or `SC-N`. Resolves against
`reports/semantic-duplication/latest/triage.md`. The skill reads:

- member list (file path, symbol, line, caller count)
- `consolidation_shape`
- `capability_matrices/<id>.md`
- the triage's `notes` block

If the scan file is missing, abort and tell the user to run
`/find-semantic-duplication` first — do NOT fall back to scanning.

### Form B — Explicit target spec
A JSON-ish block the user writes when the scan is stale or the pattern
wasn't surfaced. Required fields:

```json
{
  "id": "adhoc-<short-name>",
  "shape": "share_utilities",
  "members": [
    {"file": "core/services/foo.py", "symbol": "Cls.method", "lineno": 123},
    ...
  ],
  "notes": "Why this cluster matters, link to commit or memory if relevant."
}
```

Present the parsed spec back to the user and wait for approval (same
approval-token contract as `/fix-workflow`: first non-whitespace token
must be `approved`, `approve`, `go`, `lgtm`, `proceed`, `yes`).

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** `${REPORT_DIR}` exists, `latest` symlink.

```bash
FINDING_ID="<sc-N or adhoc-...>"
REPORT_DIR="reports/unify-shadows/${FINDING_ID}"
mkdir -p "${REPORT_DIR}/profiles"
ln -sfn "${FINDING_ID}" reports/unify-shadows/latest
```

`reports/unify-shadows/` uses finding IDs directly (not timestamps) so
successive runs against the same cluster overwrite — the shape is
stable per cluster, and re-runs should converge.

### Stage 1 — Collect targets

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/targets.json` with
one entry per shadow (file, symbol, lineno, caller_count, shape, scan
notes).

For **Form A**:

```bash
.venv/bin/python .claude/skills/unify-shadows/scripts/collect_shadows.py \
  --triage reports/semantic-duplication/latest/triage.md \
  --finding-id "${FINDING_ID}" \
  --output "${REPORT_DIR}/targets.json"
```

For **Form B**: hand-write the targets.json file from the user's spec.
Validate the same fields the Form A path produces.

### Stage 2 — Profile each shadow (parallel fan-out)

**Pre:** `targets.json`. **Post:**
`${REPORT_DIR}/profiles/<member-key>.md` for every member.

For each target, expand `agents/shadow-profiler.md` (substitute
`{{finding_id}}`, `{{member_key}}`, `{{file_path}}`, `{{symbol}}`,
`{{lineno}}`, `{{shape}}`, `{{project_root}}`, `{{skill_root}}`,
`{{output_path}}`, `{{capability_matrix_path}}`) and dispatch each scout
with `subagent_type=general-purpose`. Send every Agent call in a
**single message** so they run concurrently.

Declared-verdict dispatch: tell each scout its output will be judged only
by whether `{{output_path}}` exists, uses the required profile sections,
and cites current `file:line` evidence or capability-matrix rows for
signature, callers, return contract, resource ownership, retry/error
policy, load-bearing divergence, and tractable share opportunity. A
claim like "same behavior" without an artifact citation is unusable.

Each profile captures:

- **Signature** — parameters, types, defaults.
- **Return contract** — success shape, failure shape, raises.
- **Callers** — list of `file:symbol` plus "what they expect back".
- **Resource ownership** — does the shadow own its own client / semaphore /
  DB rows, or is it a pure function over inputs?
- **Retry + error policy** — provider rotation, typed exceptions, silent
  catch, etc.
- **Load-bearing divergence** — the one-line reason merging costs more
  than it saves (cites the capability matrix).
- **Tractable share opportunity** — the chunk that COULD be extracted
  without forcing a shape collapse. Cite the exact symbols.

If a scout returns `profile_incomplete`, re-dispatch once. If it fails
twice, proceed with partial profiles and flag the gap in the proposal.

### Stage 3 — Synthesize the proposal

**Pre:** all profiles on disk. **Post:** `${REPORT_DIR}/proposal.md`.

Read every profile, the capability matrix, and the matching section of
`knowledge/proposal-templates.md`. Write `proposal.md` with this
structure, substituting the selected shape-specific body under
`## Proposed action`:

```markdown
# Proposal — {{finding_id}}: {{cluster_title}}

## Shape
{{shape}} — from scan-<timestamp>.

## Summary (≤5 sentences)
What the cluster is, why the shape was chosen, what the proposal does.

## Members
- `path/to/file.py:lineno` — `Cls.method` ({{caller_count}} callers)
- ...

## Load-bearing divergence
One paragraph citing the capability matrix's non-merge-safe axes.

## Proposed action
<shape-specific body — keep_separate_document_why | share_utilities |
complete_migration | merge_at_workflow>

## Caller impact
Table: caller file → what changes, zero if none.

## Test matrix
Baseline + per-subsystem suites from `.claude/skills/_common/skill-conventions.md`.
New test modules required, if any.

## Stop condition
What has to be true before `/fix-workflow semantic:{{finding_id}}` can
commit. A checklist.

## Follow-on findings
Adjacent rot the profiling pass surfaced but this proposal does NOT
address. These are seeds for future `/find-*` runs, not TODOs.

## Authorization
One line: "Human review required before `/fix-workflow semantic:{{finding_id}}`."
```

### Stage 4 — Effectiveness log

**Pre:** proposal written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
SHAPE="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["shape"])' "${REPORT_DIR}/targets.json")"
.venv/bin/python scripts/log_effectiveness.py \
  --skill unify-shadows \
  --scan-id "${FINDING_ID}" \
  --target "$(.venv/bin/python -c 'import json,sys; print(",".join(m["file"] for m in json.load(open(sys.argv[1]))["members"]))' "${REPORT_DIR}/targets.json")" \
  --findings-total "$(.venv/bin/python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["members"]))' "${REPORT_DIR}/targets.json")" \
  --buckets "{\"shape_${SHAPE}\": 1}"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- Finding ID + shape.
- Members (count; one-line list).
- Load-bearing divergence (one sentence).
- Proposed action (one sentence).
- Path to `${REPORT_DIR}/proposal.md`.
- Recommended next command: `/fix-workflow semantic:{{finding_id}}`.
- Exact Stage 1 collection output and Stage 4 log output.

Do NOT start `/fix-workflow` yourself. The proposal is the handoff
artifact; the human authorizes the execution step separately.

## Non-goals

- Executing the refactor (that's `/fix-workflow`).
- Detecting new duplication (that's `/find-semantic-duplication`).
- Overriding `keep_separate_document_why` with a merge proposal when
  the scan classified the cluster that way. The proposal documents the
  separation and may propose a narrow share-utility — it does not
  silently re-open the merge debate.
- Touching files outside `reports/unify-shadows/<id>/`.
- Running tests — the proposal lists the matrix; `/fix-workflow` runs it.
- Re-analyzing TypeScript/Java, inventing full caller locations, or turning a
  static function-level lead into workflow/framework authority.

## When things go sideways

| Symptom | Action |
|---|---|
| Triage file missing for Form A | Abort; tell user to run `/find-semantic-duplication` |
| `targets.json` lists 0 members | Finding ID wrong — list the IDs present in the triage so user can pick again |
| Scout returns `profile_incomplete` on first try | Re-dispatch once with a stricter "respond only with file-write confirmation" nudge |
| Two scouts produce contradictory caller lists | Both may be right (private method shadowed under same name) — note the conflict in the proposal and move on |
| Capability matrix missing | Proceed without — base the divergence paragraph on the triage's `load_bearing_divergence` field and note the matrix gap |
| `knowledge/proposal-templates.md` missing or empty | Abort before writing `proposal.md`; the per-shape body is load-bearing and must not be invented |
| Shape is `keep_separate_document_why` but no in-tree comment | The proposal's primary action is "add the documenting comment" plus the optional share-utility; DO NOT invert to a merge |
| TypeScript finding is absent from `confirmed` but present under `uncertain` or `rejected` | Exit 2 before synthesis; re-run or review `/find-semantic-duplication`, never promote the record locally |
| TypeScript `caller_count` is `null`, `-1`, or zero | Render the candidate-graph fact exactly and require a full project reference inventory; never claim there are no callers |
| TypeScript matrix/source span is missing or stale | Exit 2 before synthesis; refresh the semantic scan instead of fabricating citations |
| TypeScript proposal path escapes `reports/unify-shadows/` or crosses a symlink | Exit 2 without writing; choose a contained, physical report directory |

## Repository layout

```
.claude/skills/unify-shadows/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   ├── collect_shadows.py           # Python Stage 1 (stdlib-only)
│   ├── propose_java.py               # Structured Java proposal consumer
│   └── propose_typescript.mjs       # Structured TypeScript proposal consumer
├── agents/
│   └── shadow-profiler.md           # Stage 2 scout brief
└── knowledge/
    └── proposal-templates.md        # Stage 3 shape-specific bodies
```

The orchestrator reads only `knowledge/proposal-templates.md`, and only
the section matching the scan's `consolidation_shape`. Scouts use
`agents/shadow-profiler.md`, the target source file, and the capability
matrix path they were handed.

## Replay case

For Python template or dispatch changes, replay with the smallest fixture
triage that has one finding for each shape. The replay passes only when
`collect_shadows.py` writes `targets.json`, four profile stubs can be
placed under `profiles/`, `proposal.md` uses the matching template
section verbatim under `## Proposed action`, and the Stage 4 log command
prints `logged to reports/_meta/effectiveness.jsonl: unify-shadows / <id>`.

For TypeScript consumer changes, replay the locked
`tests/fixtures/unify-shadows-typescript/host` finding through the installed
command. All four shapes must reach a cited final proposal; missing,
unconfirmed, and wrong-kind records must leave no output directory;
`keep_separate_document_why` must contain no consolidation/caller-move plan;
native `npm run typecheck` and `npm test` must pass before and after; source
hashes must not change; and escape/symlink outputs must fail.

For Go consumer changes, replay the copied skill against the locked Go fixture;
the accepted finding must reach all three proposal artifacts, `go test ./...`
must pass before and after, source hashes must not change, and unconfirmed or
partial input must leave no proposal directory.

For Java consumer changes, replay the copied skill with `python3 -I -S` against
the locked Java semantic fixture. All four shapes must preserve citations and
the approval boundary; unconfirmed/partial/stale input must leave no output,
native Java 17 tests must pass, and source hashes must not change.
