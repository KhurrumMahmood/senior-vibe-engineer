# meta-failure-audit kit — port report

Date: 2026-06-12
Destination: `scripts/meta_failure_audit/` in engineering-skills (this repo)
Pattern followed: skill-comply port (`.claude/tasks/skill-repairs/skill-comply-port.md`) — verbatim parity first, gaps documented verbatim, repo wiring proposed second.

## Source

`~/Projects/experiments/claude-instructions/meta-failure-audit-kit/`
(read-only; 4 files, ~40K). The kit is prose + one Claude Code
Workflow-tool script — no Python, no fixtures, no self-test. Inventory
matches the README's "Files" section exactly; what does NOT ship is the
investigation data behind the headline numbers (+1.3/+0.3 trigger-vs-note,
"~doubled unwarranted challenge") — only the workflow's `DEFAULT_TARGET`
summary describes it.

## Files ported (4, byte-identical; `diff -r` verified)

| Source | Destination |
|---|---|
| README.md | scripts/meta_failure_audit/README.md |
| SKILL.md | scripts/meta_failure_audit/SKILL.md (stored artifact — NOT installed under `.claude/skills/`; `/meta-audit` is not invocable here) |
| LENS-CHECKLIST.md | scripts/meta_failure_audit/LENS-CHECKLIST.md |
| meta-failure-audit.workflow.js | scripts/meta_failure_audit/meta-failure-audit.workflow.js |
| — | scripts/meta_failure_audit/DESIGN.md (new — provenance, verbatim gap ledger, wiring proposal) |

Zero content adaptation was needed: the kit contains no absolute paths,
no Python invocations, no host-identity strings (grep for the forbidden
tokens over the source returned nothing).

## What runs

- `node --check scripts/meta_failure_audit/meta-failure-audit.workflow.js` → exit 0 (Node v22.21.1).
- `node --input-type=module --check < …` → `SyntaxError: Illegal return statement` — expected: the script targets the Claude Code **Workflow tool** evaluator (injected `args`/`phase`/`parallel`/`agent` globals, top-level await + return) and is not standalone JS. No Workflow tool exists in this environment, so the fan-out mode is not runnable here; the checklist mode (`LENS-CHECKLIST.md` as prose) and skill-wrapper mode need no runtime.
- `.venv/bin/ruff check scripts/meta_failure_audit/` → "No Python files found" + All checks passed (exit 0).
- `.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate scripts/meta_failure_audit/SKILL.md` → exit 0 (the pre-commit hook matches any `SKILL.md` path, so this was checked deliberately; other skill tooling globs only `.claude/skills/*/SKILL.md` and ignores the stored copy).
- `.venv/bin/python scripts/lint/no_host_references.py` with the ported files staged via `git add -N` → **OK — identity tier scanned 737 tracked files**; staging then reverted.
- The kit ships no self-test; nothing further is mechanically verifiable.

## Gaps found (7 — full verbatim ledger in DESIGN.md)

1. Workflow script only parses under the Workflow-tool evaluator; mode 1 (fan-out) not runnable in this repo today.
2. Stale lens-count in the novel-critic prompt: "falls BETWEEN the four named lenses" — v3 residue; the v4 set is six.
3. Both "v3 (this file)" and "v4 (this file)" version notes — in-place-evolution residue.
4. `--quick` declared in `argument-hint` with prose-only semantics; no script defines it.
5. Headline findings unreproducible from kit contents; source's own Limits concede it verbatim ("It doesn't measure its own outcomes — fix this first"; "The harness leaks; it isn't transfer-proven").
6. `.../` scriptPath placeholder left as-is in README + workflow header.
7. SKILL.md stored, not installed — deliberate (task constraint: proposal only).

None were fixed — parity first; gaps 2/4/6 are the candidates to resolve upstream-and-here together at installation time.

## Proposed wiring (stub in DESIGN.md; nothing edited)

Adversarial-review lane for reasoning artifacts: a named step **at the
decision point** inside `/repair-skill` (six-lens pass over the drafted
change spec before applying — lenses 5/6 hit the author-evaluates-own-skill
failure mode) and `/decide` (six-lens pass over the ADR draft before
acceptance). Lane stays local (fresh-context sub-agent, no external LLM),
output is signal-not-verdict. Installation goes through `/plan-skill`
intake; the kit's own validated finding (trigger-at-decision-point +1.3 vs
aspirational note +0.3) is the argument for wiring it as an in-body step
rather than a CLAUDE.md disposition note.

## Suggested follow-ups

1. `/plan-skill` intake for `/meta-audit` (checklist mode first; decide whether the fan-out mode warrants a runtime).
2. Fix gaps 2 and 4 upstream-and-here together when installing.
3. Source's own "fix this first": a judged-closure loop tracking per-finding confirmed/false-positive — natural fit for `.claude/skill-use/` telemetry if installed.
