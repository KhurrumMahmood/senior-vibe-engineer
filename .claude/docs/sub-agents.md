# Sub-Agents

How to delegate to sub-agents (Claude Code Task / Codex sub-agent / Augment
worker / `claude -p` subprocess) without inheriting bloated context or
running into cross-tool sandbox quirks.

The always-loaded `CLAUDE.md` carries the three-bullet operating summary;
this file holds the full guidance and cross-tool bridging blocks.

## Core Rules

- **Use `.venv/bin/python`** in sub-agent Bash commands. Sub-agents don't
  inherit shell activation. The system Python causes `ModuleNotFoundError`
  — this is the #1 cause of sub-agent failures.
- **Treat context as a budget.** Do not fork or inherit the full
  conversation for routine sub-agent work. Use shared context only when the
  task genuinely depends on it; otherwise give the agent a short,
  self-contained task brief and the relevant file paths.
- **Keep prompts self-contained.** Include venv path, project root,
  platform, and framework setup instructions directly — sub-agents may not
  have read `CLAUDE.md`.
- **Use durable briefs instead of giant prompts.** For multi-agent work,
  write a concise plan or task brief under `.claude/tasks/` and have agents
  read that plus the files they own. Ask agents to write findings to files
  instead of returning long reports into the main thread.
- **Prefer file I/O over large outputs.** Have sub-agents write results to
  files rather than returning massive text.
- **Fan-out is fine; shared-context fan-out is not.** Six independent
  agents can be appropriate when the work is truly parallel, but each
  should receive a narrow scope, disjoint ownership, and no unnecessary
  transcript history.
- **Keep work bounded.** Use sub-agents for independent research, review,
  or parallel analysis. Give each sub-agent one clear task and, for code
  changes, a clear ownership boundary. Do not delegate the immediate
  blocking task when local progress depends on its answer.

## Claude CLI as Scout

`claude -p` starts from the prompt you pass rather than the parent agent's
current thread. It is useful for bounded read-only scouting or review when
avoiding inherited context matters, but it has its own usage limits and
outputs remain advisory until verified locally. It is not the default
adversarial-review lane for Codex; adversarial review is Codex-local unless
the user explicitly asks to send a bounded context pack to an external model.

**Pick Claude CLI models by task shape.** Use Haiku for straightforward
inventories, Sonnet for focused code review or low-risk implementation
suggestions, and Opus for unclear architecture or disagreement. If keychain
auth or workspace permissions are blocked by the sandbox, request elevated
permission for the Claude command instead of bypassing repo/tool
guardrails.

**External-code-sharing boundary.** When Codex is asked to use Claude CLI on a
private repo, first prefer a redacted or hand-authored context pack containing
the task, relevant file paths, invariants, and test commands. Do not pass raw
diffs, full source files, or `--add-dir <project-root>` unless the user has
explicitly approved that specific external-code-sharing task. If the sandbox
reviewer blocks the command, do not route around it; fall back to Codex-local
sub-agents/review or give the human the exact Claude command to run outside
Codex.

[Codex-Launching-Claude-CLI]
When Codex shells out to `claude -p`, prefer running it with
`workdir=/private/tmp`, `--no-session-persistence`, a small
`--max-budget-usd`, and explicit `--add-dir <project-root> -- <prompt>`
only when repo access is needed and explicitly approved. `--add-dir` is
variadic, so the `--` separator is required or the prompt can be swallowed as
another directory.
Sandbox runs may fail auth/keychain or debug writes; request escalation
for the Claude command. A SessionEnd hook warning about missing Homebrew
`simdjson` can be non-fatal if the scout's stdout/file-output contract
succeeded.
[/Codex-Launching-Claude-CLI]

[Claude-Code-Specific]
When already inside Claude Code, prefer native Claude Code sub-agents and
skills. Use `claude -p` subprocess scouts only when nesting-safe fan-out
is needed; the Codex `/private/tmp` workaround is not required unless
reproducing Codex sandbox constraints.

`claude -p` availability caveat (2026-06): Anthropic plans to remove
headless `claude -p` from subscription plans, so subscription sessions
should not treat it as a free substrate. When a fresh-context role is
needed and native sub-agents can't nest, the default is to hand the
user a ready-to-run command for a **separate Claude Code window**;
use `claude -p` only when the user opts in. Longer term, pooled
reusable workers may replace per-call spawning — see the idea ledger.
[/Claude-Code-Specific]

[Augment-Specific]
Augment rules and reviews should point to the same durable brief or task
file instead of relying on another tool's transcript.
[/Augment-Specific]

## See Also

- `cross-tool-agent-governance.md` — capability matrix per tool, how to
  decide whether a rule needs a hook/permission vs prompt context, and the
  parallel-agent context-budgeting policy.
