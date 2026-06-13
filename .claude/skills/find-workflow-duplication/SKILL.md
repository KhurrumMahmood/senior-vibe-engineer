---
name: find-workflow-duplication
description: Detect duplicated product-step authority for the host-declared workflow labels, tab IDs, and route literals listed in `.engineering/docs/product-workflows.md`. The deterministic scanner reads the descriptor's `## Text-file globs`, classifies active executable owners versus docs/tests/routes/legacy surfaces, and reports repeated values that can drift across backend, templates, loaded JS, and docs. Detection-only; never edits production code.
argument-hint: "[--min-active-owners <n>]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Repeated host-declared workflow labels, tab IDs, and route literals
  duplicated across backend, templates, JS, and docs for one product
  workflow. SUSPECT skill for product topology.
not_for: |
  Generic code duplication across functions (use /find-duplication or
  /find-semantic-duplication). Route prefix sprawl (use
  /find-route-sprawl). Doc/route drift (use /find-doc-route-drift).
language: python
framework: django
scans: [python, javascript, templates, markdown]
---

# /find-workflow-duplication

You are the orchestrator for a product-topology SUSPECT skill. Detect
when the same workflow step knowledge is repeated across layers instead
of owned by a registry.

## How success is judged

- `report.md` and `findings.json` agree on finding count and bucket
  counts, and the closeout pastes the real `detect.py` and `report.py`
  output lines (`wrote ...`) as artifact truth.
- Findings are promoted only when at least two active executable owner
  layers can drift; docs, tests, route definitions, and unloaded legacy
  files are context unless paired with active executable repeats.
- Every finding names the proposed canonical owner: workflow registry
  for labels/tab IDs, or route helper/router for route literals. A
  repeated string without an owner
  decision is evidence, not a finding.
- The run is read-only: it writes only under
  `reports/workflow-duplication/<scan-id>/`.

## Scope

- Workflow is host-authored — read from
  `.engineering/docs/product-workflows.md`. With no descriptor the scan
  finds nothing (the toolkit assumes no product flow).
- Scans the host's declared `## Text-file globs`; templates declared
  under `## UI template globs` split loaded JS from legacy/unloaded.
- Output: `reports/workflow-duplication/<scan-id>/`.
- No code edits.
- Python: `python3` (stdlib-only scripts).

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/workflow-duplication/$SCAN_ID"
mkdir -p "$REPORT_DIR"
python3 .claude/skills/find-workflow-duplication/scripts/detect.py \
  --project-root "$(pwd)" \
  --min-active-owners 2 \
  --output "$REPORT_DIR/detections.jsonl"
python3 .claude/skills/find-workflow-duplication/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target "product workflow" \
  --project-root "$(pwd)"
```

The skill default is `--min-active-owners 2`; pass it explicitly. The
script's compatibility default is 0 and is too permissive for this skill
because it can surface docs/legacy repeats without active executable
drift. Leave `--min-owners` at its script default of 3 unless the user
asks for a broader diagnostic pass.

After the commands finish, paste the `detect.py` and `report.py` stdout
lines into the report or closeout. Do not claim findings from memory;
read `findings.json` for counts and `report.md` for the rows the user
will see.

## Findings

- `duplicated_workflow_label`: step label repeated across owner layers.
- `duplicated_workflow_tab_id`: tab key repeated across owner layers.
- `duplicated_route_literal`: route literal repeated across owner
  layers.
- `duplicated_workflow_knowledge`: fallback for any future
  descriptor-driven value kind; treat it as evidence until the owner is
  explicit.

Every finding includes surface classification:

- `active_executable`: current templates, loaded JS, views, or services
  that can change runtime behavior.
- `legacy_unloaded`: JS or templates in the workflow file family that
  are not loaded by current site-config templates.
- `route_definition`: URLconf definitions. These can stay literal when
  route names and consumers are registry-owned.
- `docs` / `tests`: reference material and regression coverage.

## Triage Rules

- Lexical repeats are evidence, not findings. A label, tab id, route
  prefix, or endpoint suffix appearing in docs/tests does not matter by
  itself.
- Start from active executable repeats. Treat legacy/unloaded files,
  docs/tests, and route definitions as context unless they are paired
  with two or more active executable owners that can drift.
- Use a two-pass migration lens for route-literal cleanup: first migrate
  consumers loaded by current templates, then sweep the remaining
  workflow-family static files. Dormant prototype JS should be deleted
  when it has no unique knowledge; otherwise quarantine it with an
  explicit reason instead of keeping silent compatibility debt.
- Promote to a finding only when multiple executable layers can change
  behavior independently: navigation, page tabs, status providers,
  route/URL generation, endpoint construction, feature visibility, or
  boot payload shape.
- Every finding must name the proposed canonical owner — the workflow
  registry for duplicated labels/tab IDs, or the route helper/router for
  duplicated route literals.
- Do not fold a distinct sub-workflow's rules into the primary
  workflow's findings unless the user explicitly scopes that work in.

Decision fork: when a duplicate value appears in active code plus docs or
tests, promote it only if the active code spans at least two owner
layers. When it appears in one active owner plus any amount of
docs/tests/route definitions/legacy unloaded files, report it as context
or ignore it; do not hand it to `/fix-workflow`.

## Next Skills

- Use `/extract-workflow-registry` to propose the explicit owner.
- Use `/fix-workflow` only after tests pin the current labels, tabs,
  redirects, and page rendering.

## When things go sideways

| Symptom | Action |
|---|---|
| `.engineering/docs/product-workflows.md` is absent | Report "descriptor absent; 0 findings expected" and stop. Do not infer another project's workflow |
| Descriptor exists but `## Text-file globs` is empty or matches no files | Report the empty scan surface and ask the host to declare text-file globs before treating 0 findings as health |
| `detect.py` writes 0 findings | Read the descriptor and command output. If active owners are below 2, this is a clean result; if no files were scanned, it is a descriptor/setup issue |
| Findings are only docs/tests/route definitions/legacy unloaded files | Do not promote them to cleanup. Keep them as context or follow-up unless two active executable owners also drift |
| `report.py` cannot write or `findings.json` is missing | Stop and report the exact failure. Do not summarize from `detections.jsonl` as though the final artifact exists |
| `scripts/log_effectiveness.py` fails during `report.py` | `report.py` uses `check=False`; the audit artifacts still count if `report.md` and `findings.json` were written. State that effectiveness logging failed or was not confirmed |

## Replay case

For future repairs, replay with a temporary project that declares one
workflow step in `.engineering/docs/product-workflows.md`, includes the
step label in one template and one service file listed under
`## Text-file globs`, then runs the two documented commands. Expected
evidence: `detect.py` writes at least one JSONL record only when active
owners meet the explicit threshold, and `report.py` writes both
`report.md` and `findings.json`.
