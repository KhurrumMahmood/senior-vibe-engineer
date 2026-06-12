# micro-fix-scout brief template

Dispatched at Phase 5.3.5 — one sub-agent per target file, in parallel
(one orchestrator message, N `Agent` tool calls with
`subagent_type="general-purpose"`). The orchestrator substitutes every
`{{placeholder}}` before dispatch.

**CRITICAL: Sub-agents must NOT stage or commit.** Parallel agents share
a single git index. If Agent A stages file A and Agent B stages file B,
Agent A's commit will include both files — producing wrong commits and
potential data loss. Sub-agents only edit files and report back; the
orchestrator handles all git operations serially after every scout
returns.

---

## Placeholders

| Placeholder | Source | Example |
|---|---|---|
| `{{file}}` | `scripts/specs.py violations` JSON | `core/views_crawling.py` |
| `{{violations}}` | Same JSON, per-file list | multiline `<line>  code snippet` list |
| `{{anti_pattern}}` | Spec frontmatter `items.<ID>.anti_pattern` | `\.delay\(\|\.apply_async\(` |
| `{{canonical}}` | Spec frontmatter `items.<ID>.canonical` | `TaskDispatchService.safe_dispatch` |
| `{{canonical_import}}` | Spec frontmatter or derived | `from core.services.task_dispatch import TaskDispatchService` |
| `{{verification_cmd}}` | Dispatch tuple per file | `tests.test_data_export tests.test_site_capabilities` |
| `{{worktree}}` | `git rev-parse --show-toplevel` | `~/Projects/your-project` |
| `{{venv}}` | `knowledge/operations.md` | `.venv/bin/python` |
| `{{branch}}` | `git branch --show-current` | `wip` |

---

## Prompt template

```
You are fixing convention violations in a SINGLE file. Other sub-agents are
fixing other files in parallel — do not touch anything outside your assigned file.

Worktree: {{worktree}}
Python:   {{venv}}
Branch:   {{branch}}
File to fix: {{file}}

Violations to fix (from scripts/specs.py violations <spec-id>):
{{violations}}

Canonical form: {{canonical}}
Anti-pattern regex: {{anti_pattern}}

Fix protocol:
1. Read the file.
2. For each violation, replace with the canonical form:
   - `<anti-pattern>` → `{{canonical}}(<args>)`
   - Preserve keyword args, ordering, and any result handling.
   - Add `{{canonical_import}}` at the top of the file if not already imported.
3. Run the verification suite for this file:
   {{venv}} manage.py test {{verification_cmd}} \
     --settings=app.settings_test_sqlite -v 2
4. Return a summary: file path, lines changed, test result (pass/fail).
   Do NOT run git add, git commit, or any git write operation.
5. If tests fail, revert your edits to the file and return the failure details.

Do not edit any other file. Do not rerun cross-file tests. Do not touch imports
beyond adding the single canonical-helper import.
Do not run any git commands (add, commit, stash, checkout, etc.).
```

---

## Return contract

The scout returns a short summary:

```
File: {{file}}
Lines changed: <list>
Test result: pass / fail
<if fail: failure details>
```

If the scout returns `pass`, the orchestrator stages and commits the file
serially (one commit per file). If the scout returns `fail`, the scout
has already reverted its own edits; the orchestrator flags the file for
hand-fix or escalation.

## Why the no-git rule matters

Parallel agents share the same git index. The following scenario is
indistinguishable from a pipeline bug:

- Agent A edits `views_crawling.py`, runs `git add`.
- Agent B edits `views_ptid.py`, runs `git add`.
- Agent A runs `git commit`.

Agent A's commit now contains both files. Agent B commits an empty diff.
The git log lies about the authorship and diff of each file. Bisect is
useless. Recovery requires `git reset` + redo. The rule is absolute: the
scout produces file edits, nothing else. The orchestrator is the only
process that touches the git index.
