---
name: find-rule-surface-drift
description: Detect drift on the agent-rules surface — oversized always-loaded files, dormant load-on-demand docs, missing-but-referenced docs, unreferenced docs, and broken links from the human onboarding entry point. SUSPECT skill governing the placement convention defined in ADR 0005 (agent-rules-design).
argument-hint: "[--root .claude --onboarding-md ONBOARDING.md --max-root-chars 12000 --max-doc-chars 25000]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Auditing the agent-rules surface (CLAUDE.md + .claude/docs/) against
  ADR 0005's tiered-storage convention. Catches: always-loaded surface
  bloat, dormant docs that no longer earn their place,
  table-vs-filesystem drift, and docs registered but never referenced
  by any other artifact. Also scans /ONBOARDING.md (the human entry
  point) for broken links and registered docs the human path never
  mentions.
not_for: |
  Code-side drift (use /find-doc-route-drift for documented route
  drift, /find-frontend-contract-drift for template-to-JS drift).
  Decision-registry drift (use /audit-decisions). Authoring or amending
  the agent-rules ADR itself (use /decide). Acting on findings — that
  goes to /fix-workflow with the cluster id.
language: python
framework: any
---

# /find-rule-surface-drift

You are the orchestrator for a SUSPECT skill that audits the agent-rules
surface against ADR 0005's tiered-storage convention.

## Scope

- Default root: `.claude/`.
- Default `CLAUDE.md` path: `<root>/CLAUDE.md`.
- Default docs dir: `<root>/docs/` (top-level `.md` files only — nested
  package docs like `subsystems/<name>.md` are out of scope for this
  skill).
- Default ONBOARDING.md path: `<project-root>/ONBOARDING.md` (the human
  entry point; pass `--onboarding-md` to override or point at a missing
  path to skip the onboarding bands).
- Output: `reports/find-rule-surface-drift/<scan-id>/`.
- No code or doc edits; detection only.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-rule-surface-drift/$SCAN_ID"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-rule-surface-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-rule-surface-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --target ".claude/"
```

## Findings

- `oversized_root`: `.claude/CLAUDE.md` exceeds the soft size budget
  (default 30,000 chars, per ADR 0005). Demote content to load-on-demand
  docs; don't subdivide at root.
- `oversized_doc`: a `.claude/docs/*.md` exceeds the per-doc soft
  budget (default 50,000 chars). Decide whether it's one topic or two —
  legitimate inventories may warrant a higher threshold or an explicit
  exemption.
- `dormant_doc`: a file exists under `.claude/docs/` but has no row in
  CLAUDE.md's Supplementary Documentation table. Either add a trigger
  row or remove the doc — load-on-demand docs need an explicit "Read
  when…" entry to be reachable.
- `missing_doc`: a row in the Supplementary Documentation table
  references a file that does not exist on disk. Either fix the row or
  create the doc.
- `unreferenced_doc`: a doc is registered in the table but appears in
  no other artifact under `.claude/`. May be legitimately reachable
  only via its trigger; the recommendation reads "confirm or remove."
- `missing_link`: ONBOARDING.md links to a path that does not exist on
  disk. Treat as a real defect — broken links in the human entry point
  block onboarding directly. Either fix the link target or remove the
  link.
- `dormant_in_onboarding`: a doc registered in CLAUDE.md's
  Supplementary Documentation table is **not** linked from
  ONBOARDING.md. **Info-level only.** Most agent-targeted docs (oracle,
  model-tiering, deployment, sub-agents, etc.) legitimately stay
  unmentioned in human onboarding. Use this band when triaging
  newly-registered docs to decide whether the human path should
  reference them — never as a blocking signal.

## Calibration

`--max-root-chars` and `--max-doc-chars` are soft budgets. ADR 0005
sets the root soft budget at ~30K — high enough that legitimate
project context fits, low enough to push back when always-loaded
content drifts past the practical signal-density ceiling. The per-doc
ceiling defaults to ~50K; legitimate inventory docs (subsystem maps,
full catalogues) can exceed this and should either raise the threshold
project-wide or carry a documented exemption.

## Next Skills

- `/fix-workflow` for executing a single migration (e.g. demote one
  oversized section, register one dormant doc, prune one unreferenced
  doc).
- `/decide` if a finding reveals a tradeoff the ADR doesn't yet cover
  (e.g. "we keep accepting `oversized_doc` for `architecture.md` —
  raise the per-doc budget formally").
- `/prevent-regression` if a particular drift recurs often enough to
  justify a pre-commit check (the planned `oversized_root` hard
  guardrail in ADR 0005's Verification section).

## Notes for the orchestrator

- This is a Stage 1 skeleton. Cross-tool sync drift between
  `.claude/CLAUDE.md` and `.augment/rules/imported/*` is **not** yet
  detected — it requires content-level comparison heavier than a
  filename check. Add as a follow-up band when an actual drift
  incident motivates the cost.
- `find_unreferenced` excludes `worktrees/` and `__pycache__/` from
  its grep scan. Mirrored CLAUDE.md files inside agent worktrees would
  otherwise mask every doc as "referenced."
- Smoke-test fixtures live under `fixtures/exercise-all/`. Run them
  with output written **outside** the fixture root (e.g. to
  `reports/find-rule-surface-drift/_fixture-runs/exercise-all/`) so a
  prior run's output doesn't pollute the next run's `unreferenced_doc`
  check. With `--max-root-chars 200 --max-doc-chars 200`, all five
  bands should each fire exactly once.
- A second fixture under `fixtures/exercise-onboarding/` exercises the
  ONBOARDING.md bands. Invoke with `--root <fixture> --project-root
  <fixture> --onboarding-md <fixture>/ONBOARDING.md` and expect
  exactly one `missing_link` (the dead link to `docs/nope.md`) and
  one `dormant_in_onboarding` (the registered-but-unlinked
  `unmentioned.md`).
- The `unreferenced_doc` band uses `grep -l` across `.claude/`. Docs
  that are reached only via the supplementary table's trigger (and
  never named elsewhere) will fire here legitimately; treat the
  finding as "confirm reachability," not "delete on sight."
