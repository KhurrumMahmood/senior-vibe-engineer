# Cross-Tool Agent Governance

Status as of 2026-04-28. This document captures how this repo should give
consistent instructions to Claude Code, Codex, and Augment without pretending
that prompt context is the same thing as enforcement.

## Operating Principle

Repo architecture docs, tests, lints, and CI are the durable source of truth.
Tool-specific instruction files are adapters that help each coding agent notice
the source of truth.

**Content placement is governed by ADR 0005**
(`ai-docs/decisions/0005-agent-rules-design.md`). That ADR carries the
decision tree for *which surface* a new rule belongs on (lean root vs.
load-on-demand `.claude/docs/` vs. `lessons.md` vs. ADR vs. memory) and
the soft size budget for the always-loaded surface. This document
continues to own the *enforcement ladder* (advisory → guardrail → hook
→ permission) and the cross-tool sync mechanics. Read 0005 when adding
content; read this doc when promoting a rule into an executable check.

Rules in shared files apply to Claude Code, Codex, and Augment by default.
Use agent-specific blocks only for rare cross-tool bridge cases, such as Codex
launching `claude -p` or Claude Code invoking `/codex:review`. Canonical block
names:

- `[Codex-Specific]...[/Codex-Specific]`
- `[Claude-Code-Specific]...[/Claude-Code-Specific]`
- `[Augment-Specific]...[/Augment-Specific]`
- `[Codex-Launching-Claude-CLI]...[/Codex-Launching-Claude-CLI]`

Do not tag ordinary shared rules. Untagged means every agent follows it.

Use this ladder for every durable rule:

1. Document the architectural rule in `.claude/CLAUDE.md` or `.claude/docs/`.
2. Mirror the practical instruction into each tool's advisory context.
3. Add a repo-level guardrail when the rule protects correctness, data safety,
   AI-provider routing, production writes, or benchmark validity.
4. Add tool hooks or permissions for fast local feedback where the tool supports
   them.
5. Use managed/org policy only for boundaries that must remain hard even when a
   local user changes repo files.

Advisory context is useful, but it is not a quality gate. If a rule matters, it
needs an executable check or a tool permission/hook that can fail the action.

## Capability Matrix

| Tool | Advisory context | Enforceable controls | Repo pattern |
|---|---|---|---|
| Claude Code | `CLAUDE.md`, nested `CLAUDE.md`, `.claude/rules/*.md`, skills, slash commands, subagent prompts | settings permissions, permission modes, hooks, sandboxing, MCP restrictions, managed policy | Keep root `.claude/CLAUDE.md` and narrow local `CLAUDE.md` signposts. Add settings/hooks examples only when we also have repo tests/lints for the same rule. |
| Codex | `AGENTS.md`, nested `AGENTS.md`, optional override project docs | sandbox modes, approvals, command rules, MCP allow/deny lists, hooks, managed requirements | Root `AGENTS.md` is a symlink to `.claude/CLAUDE.md`. If a directory needs Codex-local guidance, add or mirror a nested `AGENTS.md`; do not rely on Claude-only nested files. |
| Augment | `.augment/rules/*.md`, `.augment-guidelines`, imported `AGENTS.md`/`CLAUDE.md`, user rules | CLI permissions, CLI hooks, MCP/tool permissions, `.augmentignore`, code-review guidelines | Keep official always-apply rules under `.augment/rules/imported/`. Treat `.augment/context.md` and `.augment/requirements.md` as repo-maintained context docs, not official special rule files. |

Important caveats:

- Claude/Codex/Augment memory files are prompt context. They guide decisions but
  do not prove behavior.
- Claude skills and tool allow-lists can preapprove useful paths, but hard
  blocking belongs in permissions, hooks, sandbox settings, or repo checks.
- Codex hooks are useful guardrails, but documented hook behavior should not be
  treated as the only security boundary.
- Augment CLI permissions and hooks do not necessarily apply identically inside
  every Augment surface, so critical rules still need repo-level checks.

## Current Repo Adapters

| Purpose | Files |
|---|---|
| Root Claude/Codex context | `.claude/CLAUDE.md`; `AGENTS.md` symlink |
| Augment long-form context | `.augment/context.md`; `.augment/requirements.md` |
| Augment official always-apply rules | `.augment/rules/imported/*.md` |
| Cursor / Gemini context | `.cursor/CURSOR.md`, `.gemini/GEMINI.md` symlinks to `.claude/CLAUDE.md` |
| Durable architecture docs | `.claude/docs/*.md` |
| Executable repo guardrails | `scripts/lint/*.py`, project tests, CI |

When a rule changes, update the durable architecture doc first, then update the
tool adapters that point to it. For Augment, prefer adding or updating files
under `.augment/rules/imported/` because those are official rule files. Add
nested `AGENTS.md` files (or nested `CLAUDE.md` signposts) when a directory
needs local guidance that the root doc shouldn't carry.

## Enforcement Strategy

Use repo-level checks for rules that should survive any coding tool:

- isolated runtime packages may not construct model providers outside the
  canonical AI runtime facade
- isolated runtime packages may not write production rows or dispatch
  background tasks
- prompts may not contain scorer-only truth or holdout values
- benchmark gates may not pass failed jobs or ineligible ablations
- new AI workflows need registry entries before provider calls or prompts
- architectural smells that recur should become diff-scoped lints

Use tool hooks for faster local feedback:

- block finishing a substrate change when required architecture tests were
  not run or were not acknowledged
- block direct edits to production defaults when work is supposed to be
  artifact-only
- warn when adding a prompt/model call without touching the workflow registry

Use permissions and sandboxing for hard operational safety:

- require approval before network calls, live external requests, migrations,
  or destructive Git operations
- restrict tool/browser access for agents that only need local fixtures
- keep model-provider credentials out of prompts and artifacts

## Parallel Agent Context Budgeting

Parallel agents are useful when the work is genuinely independent, but each
agent should receive the smallest context that can let it succeed. The default
pattern is a concise, self-contained task brief plus the relevant files or
directories; do not fork or paste the full conversation unless the task truly
depends on it.

For long-running or multi-track work, write durable briefs under
`.claude/tasks/` and have workers write findings there or under an explicit
artifact path. This keeps the main thread from absorbing long scout reports and
keeps follow-up agents from replaying stale history.

Tool-specific guidance:

- Codex sub-agents should usually use `fork_context: false` and receive a
  narrow prompt with project root, `.venv/bin/python`, file ownership, expected
  output, and tests to run.
- Claude CLI workers launched with `claude -p` are useful no-shared-context
  scouts or reviewers because they only see the prompt and files they inspect.
  They should be used for bounded tasks and their output is advisory until the
  main coordinator verifies it locally. Prefer Haiku for simple inventories,
  Sonnet for focused code review or low-risk implementation suggestions, and
  Opus for unclear architecture. If sandboxing blocks Claude auth/keychain or
  workspace access, request elevated permission for that command rather than
  bypassing repo guardrails.
- Claude CLI is an external model path. Codex must not send private repo source
  or diffs to `claude -p` as a workaround for local review unless the user has
  explicitly approved that exact bounded context. The safer default workaround
  is to write a small local context pack or task brief that lists goals, file
  paths, test commands, and redacted/hand-authored summaries, then either run a
  Codex-local review against the real code or ask the human to run the Claude
  command outside Codex if they intentionally want external review with their
  credentials.
[Codex-Launching-Claude-CLI]
Use a neutral working directory such as `/private/tmp` and pass repo access
deliberately with `--add-dir <project-root> -- <prompt>`. The `--` matters
because `--add-dir` accepts multiple paths. Use `--no-session-persistence`, a
budget cap, and narrow tools/permissions for scouts. Treat missing-`simdjson`
SessionEnd hook warnings as non-fatal when the scout's explicit output contract
succeeded.
Only use `--add-dir` for private repo paths after explicit user approval for
that specific external-code-sharing task. For routine adversarial review,
prefer Codex-local review or a redacted context pack.
[/Codex-Launching-Claude-CLI]

[Claude-Code-Specific]
When already inside Claude Code, prefer native sub-agents and skills. Use
`claude -p` subprocess scouts only for nesting-safe fan-out; the Codex
`/private/tmp` workaround is not inherently required in native Claude Code
sessions.
[/Claude-Code-Specific]

[Augment-Specific]
Augment rules and reviews should point to the same durable brief or task file
  instead of relying on another tool's transcript.
[/Augment-Specific]

Fan-out is acceptable; shared-context fan-out is expensive and usually
unnecessary. Six independent workers are fine when they have disjoint ownership
and bounded prompts. Six workers inheriting a large transcript should be treated
as a design smell.

## Local Agent Policy

This repo has a shared policy layer under `scripts/agent_policy/`. Claude Code
and Codex call it through project hooks. Augment receives the same behavior
through workspace rules, code-review guidelines, and the installable
`.augment/settings.example.json` for Auggie CLI users.

The policy layer checks (host project supplies the specifics):

- unsafe shell commands, including bare `python` invocations that bypass
  `.venv/bin/python`
- direct model-provider construction outside the canonical AI runtime
- production writes and background-task dispatch from artifact-only packages
- prompt-truth leakage in resolver/planner additions
- finishing sensitive AI/agent-policy work without tests or an explicit
  "not run and why" note

Every non-allow decision appends sanitized JSONL to
`logs/agent_policy/friction.jsonl`. Raw friction logs are local and ignored.
Agents and humans can report excessive friction with:

```bash
python3 scripts/agent_policy/friction.py report --rule <id> --message "<why this is too much friction>"
```

Review recent friction with:

```bash
python3 scripts/agent_policy/friction.py summarize --since 14d
```

Optional periodic review can use cron or launchd. Do not install this
automatically; each developer or deployment owner should opt in.

Example cron entry:

```cron
0 9 * * 1 cd /path/to/repo && python3 scripts/agent_policy/friction_review.py --since 14d >> logs/agent_policy/review.log 2>&1
```

Example launchd command target:

```bash
cd /path/to/repo && python3 scripts/agent_policy/friction_review.py --since 14d
```

## Directory Guidance

Local `CLAUDE.md` files should stay small. They are signposts to package rules,
not design archives. If a package-specific rule becomes important enough to
enforce, add a test or lint in the repo and mention that guardrail from the local
file.

For Codex, local `CLAUDE.md` is not the portable directory-rule mechanism. If a
directory needs Codex-specific local loading, add a nested `AGENTS.md` or keep
the root `AGENTS.md` guidance explicit enough that Codex will read the canonical
doc before editing that area.

For Augment, keep condensed operational rules in `.augment/rules/imported/` with
frontmatter such as:

```markdown
---
type: "always_apply"
---
```

Longer background documents can remain in `.augment/context.md` and
`.augment/requirements.md`, but they should not be the only copy of a rule that
an Augment agent must follow.

## Sources Checked

The research pass used each vendor's official docs:

- Claude Code: [memory](https://code.claude.com/docs/en/memory),
  [configuration](https://code.claude.com/docs/en/configuration),
  [permissions](https://code.claude.com/docs/en/permissions),
  [hooks](https://code.claude.com/docs/en/hooks),
  [sandboxing](https://code.claude.com/docs/en/sandboxing),
  [skills](https://code.claude.com/docs/en/skills),
  [MCP](https://code.claude.com/docs/en/mcp)
- Codex: [AGENTS.md](https://developers.openai.com/codex/guides/agents-md),
  [configuration](https://developers.openai.com/codex/config-reference),
  [sandboxing](https://developers.openai.com/codex/concepts/sandboxing),
  [approvals and security](https://developers.openai.com/codex/agent-approvals-security),
  [rules](https://developers.openai.com/codex/rules),
  [hooks](https://developers.openai.com/codex/hooks),
  [MCP](https://developers.openai.com/codex/mcp)
- Augment: [rules](https://docs.augmentcode.com/cli/rules),
  [guidelines](https://docs.augmentcode.com/setup-augment/guidelines),
  [workspace context](https://docs.augmentcode.com/cli/setup-auggie/workspace-context),
  [indexing](https://docs.augmentcode.com/setup-augment/workspace-indexing),
  [permissions](https://docs.augmentcode.com/cli/permissions),
  [hooks](https://docs.augmentcode.com/cli/hooks),
  [review guidelines](https://docs.augmentcode.com/codereview/review-guidelines)
