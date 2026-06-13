---
type: "always_apply"
---

# Agent Governance

- Durable repo rules live first in `.claude/CLAUDE.md` and `.claude/docs/`.
  Tool-specific files are adapters, not the source of truth.
- Shared instructions apply to Claude Code, Codex, and Augment unless wrapped
  in an agent-specific block such as
  `[Codex-Specific]...[/Codex-Specific]`,
  `[Claude-Code-Specific]...[/Claude-Code-Specific]`,
  `[Augment-Specific]...[/Augment-Specific]`, or
  `[Codex-Launching-Claude-CLI]...[/Codex-Launching-Claude-CLI]`. Use these
  blocks rarely, mainly for cross-tool bridge cases.
- Prompt context is advisory. Rules that protect correctness, data safety,
  provider routing, sidecar write boundaries, or benchmark validity need tests,
  lints, CI, hooks, permissions, or sandbox restrictions.
- Cross-tool governance is documented in
  `.claude/docs/cross-tool-agent-governance.md`. Read it before changing agent
  rules, hooks, permissions, or local package guidance.
- For Augment, official repo rules belong under `.augment/rules/*.md`.
  `.augment/context.md` and `.augment/requirements.md` are repo-maintained
  context docs and should not be the only copy of a must-follow rule.
- Keep root `AGENTS.md` / `.claude/CLAUDE.md`, package signposts, and
  `.augment/rules/imported/` in sync when durable project instructions change.
- Commit only your own work: when parallel agents or lanes share a working
  tree, stage by the explicit file list your lane owns (never a broad
  `git add <dir>`) and check the staged set against that list first.
- Machine-local rules (tool/plugin choices, dispatch lanes, spend limits)
  live in `.claude/CLAUDE.local.md` (gitignored, optional) — never in
  shipped files.
- Skill ecosystem changes go through `/plan-skill` unless they are tiny wording
  edits. New skills need adversarial requirements, a trigger contract,
  evidence/dogfood plan, and `scripts/skill_meta.py lint` before cataloging.
- The kit is held to its own standard first (it exports standards): skills
  meet `.claude/skills/repair-skill/knowledge/skill-standard.md`; text that
  cannot be trusted at execution time is a defect even without an incident.
- After significant skill ecosystem changes, run
  `/check-ecosystem-consistency` and review stale counts, catalog coverage,
  and possible `/which-shape` registry updates before updating its state.
- Concrete bug investigations with no trusted reproduction should use
  `/diagnose` before implementation: feedback loop, hypotheses, root cause,
  verification, and cleanup check.
- For vague, messy, or multi-step requests where the operating mode is
  unclear, route with `/which-shape` first (then `/which-skill` once the
  shape is known) instead of picking skills ad hoc or proceeding unrouted.
  Tiny obvious edits are exempt.
- Treat agent context as a budget. Parallel workers should receive concise,
  self-contained task briefs and relevant file paths, not inherited full
  transcripts. Use `.claude/tasks/` briefs and file-based findings for
  multi-agent work.
- `claude -p` can be used as a no-shared-context scout or reviewer for bounded
  tasks, but its output is advisory until verified locally, it has its own
  usage limits, and it is an external model path. Do not send private repo
  source, raw diffs, or broad project access to it unless the user explicitly
  approves that specific bounded context.
- In this repo, "adversarial review" means a Codex-local independent review
  lane by default. Use external Claude review only when explicitly requested
  and approved for the exact context being shared.
[Codex-Launching-Claude-CLI]
- The `/private/tmp` + `--add-dir <project-root> -- <prompt>` Claude CLI
  launch pattern is specifically for Codex launching Claude CLI under
  sandbox/approval constraints. Use `--add-dir` for private repo paths only
  after explicit approval for that external-code-sharing task; otherwise use a
  redacted task brief/context pack.
[/Codex-Launching-Claude-CLI]

[Claude-Code-Specific]
- Native Claude Code sessions should prefer Claude Code sub-agents and skills
  unless subprocess fan-out is intentionally needed.
[/Claude-Code-Specific]
- If sidecar AI work adds providers, prompts, production hooks, or workflow
  behavior, update `app/services/ai_sidecar/use_cases.py` and add a
  fixture-backed benchmark or architecture test before treating it as complete.
- Cross-tool guardrails write sanitized local friction logs under
  `logs/agent_policy/`. If a rule is too noisy, run
  `python3 scripts/agent_policy/friction.py report --rule <id> --message "<reason>"`.
