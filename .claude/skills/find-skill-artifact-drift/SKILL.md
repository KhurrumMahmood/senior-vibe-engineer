---
name: find-skill-artifact-drift
description: |
  SUSPECT scan for instruction-artifact coherence: a SKILL.md that
  promises scripts, flags, tools, or evidence its files no longer
  provide. Band A is deterministic reference integrity (a documented
  script that exists nowhere, a documented --flag the script's argparse
  never defines, a bash block with no Bash in allowed-tools) and is safe
  to gate a commit on; Band B is heuristic structural proxies (orphan
  scripts, declared produces/evidence_required the body never wires in,
  a read-only not_for contradicted by editing tools) and stays advisory.
argument-hint: "[skill names / dirs / SKILL.md paths... - defaults to all skills]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Catching SKILL.md ↔ artifact drift after a skill is refactored:
  renamed or deleted scripts the prose still names, documented command
  flags the script dropped, a shell block whose Bash grant was never
  added, scripts that exist but the pipeline forgot, and evidence
  contracts the procedure never actually produces.
not_for: |
  Proving a skill's procedure is semantically correct, blocking commits
  on Band-B heuristics, or re-checking the frontmatter contract
  (required fields, enum values, name==dir) that scripts/skill_meta.py
  lint already owns. Band C semantic judgment belongs to /plan-skill.
language: python
framework: any
produces: [detections, report, findings]
evidence_required: [report, findings]
max_overhead: "Run one detect+report pass; treat Band B as a review queue, never an auto-patch list."
---

# /find-skill-artifact-drift

You are running an instruction-artifact-coherence (IAC) audit on the
skills themselves. A skill's SKILL.md is a procedure an agent will
follow literally: when its prose names `scripts/<name>.py --<flag>`, that
path and that flag must exist, or the agent's first step fails. This scan
finds the references that have drifted from reality.

`scripts/skill_meta.py lint` already validates the frontmatter *contract*
(required fields, enum values, name matches directory). This skill
validates the *references between the SKILL.md body and the files on
disk*, which that contract does not cover.

## Default Target

With no argument, scan every skill under `.claude/skills/`. Otherwise pass
skill names, skill directories, or `SKILL.md` paths — the same arg shapes
the pre-commit gate forwards from changed files:

```bash
.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py find-comment-drift
```

## Pipeline

Run with the project venv:

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-skill-artifact-drift/$SCAN_ID"
.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/report.py "$REPORT_DIR/detections.jsonl" --output "$REPORT_DIR/report.md" --target "all skills"
ln -sfn "$SCAN_ID" reports/find-skill-artifact-drift/latest
```

If symlinks or shell substitution are awkward in the current
environment, use any equivalent safe command. The artifacts are:

- `detections.jsonl` — one finding per line, each tagged with its band.
- `report.md` — grouped human-readable report.
- `findings.json` — machine-readable report summary.

## Detector Bands

**Band A — deterministic reference integrity (gate-worthy).** Low
false-positive checks the `--gate` subset enforces:

- `missing_script_ref`: the body references a `scripts/<file>.py` that
  resolves in neither the skill's own `scripts/`, the repo `scripts/`,
  nor a sibling skill (`<other-skill>/scripts/<file>.py`).
- `missing_documented_flag`: a fenced command runs a resolvable script
  with a `--flag` that script's argparse never defines.
- `bash_tool_undeclared`: the body has a `bash`/`sh`/`shell` code block
  but `allowed-tools` omits `Bash`.

**Band B — structural proxies for semantic claims (advisory only).**
Signals a human should read, never a commit blocker:

- `orphan_script`: a `scripts/*.py` exists (excluding `smoke.py`) that the
  SKILL.md body never names.
- `evidence_contract_unbacked`: a `produces:`/`evidence_required:`
  artifact the body never names as an output (matched on a normalized
  form, so `state_snapshot` is satisfied by "state snapshot").
- `not_for_tooltell_conflict`: `not_for` claims the skill does not edit,
  yet `allowed-tools` grants `Write`/`Edit`/`NotebookEdit`.

## Gate

Band A is wired two ways, following the coverage-ratchet pattern:

- **Pre-commit (hard, changed files only).** The `skill-artifact-drift`
  hook runs `detect.py --gate` over staged `SKILL.md` files and blocks
  the commit on any Band-A finding. It cannot block on drift in skills
  you did not touch, so it only ratchets forward.
- **CI (advisory, registry-wide).** The same `--gate` runs over every
  skill and emits a `::warning::` without failing the build, surfacing
  pre-existing Band-A drift until it is fixed.

`--gate` prints Band-A findings to stderr and exits 1 if any exist; it
never considers Band B.

## Smoke Test

Before trusting changes to the detector, run:

```bash
.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/smoke.py
```

The smoke scans the good/bad fixture skills and asserts every band fires
on the bad fixture, the good fixture stays clean, and `--gate` exits
non-zero on the bad fixture and zero on the good one.

## Judgment

Treat Band A as a fix-or-correct queue: repair the path, restore the
script, add the missing flag or `Bash` grant, or delete the stale
reference. Treat Band B as a senior-engineer review queue — an orphan
script may be a deliberate internal helper, and an unbacked evidence
artifact may simply need wiring into the prose. Fix the drift; do not
delete a script just to silence the orphan signal.
