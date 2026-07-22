# Staged-work queue contract

The queue at `.engineering/local/queue/` holds **packet-compatible work
items** — the first executable implementation of ADR 0036's packet
concept, placed per ADR 0037 (gitignored local zone; agent-neutral plain
JSON). One file per item, `<id>.json`.

## Item format

```json
{
  "recipe": "what to do, self-contained — the executor reads nothing else",
  "scope": ["app/a.py", "app/b.py"],
  "verification": ".venv/bin/python -m pytest tests/test_a.py -q",
  "expected_delta": "2 findings fixed, 0 new (manifest diff)",
  "token_budget": 35000,
  "origin": "reports/unify-shadows/SC-3/proposal.md",
  "status": "staged",
  "staged_at": "2026-06-12T00:00:00+00:00"
}
```

The first five fields are ADR 0036's packet fields (scope file list,
recipe, verification command, expected delta, token budget); `origin`,
`status`, `staged_at` are queue metadata. `status` moves
`staged → picked → done` — the picker edits the file in place (queue
items are per-run scratch, not append-only history).

Per ADR 0036, an executor's self-reported success is not verification:
whoever drains an item re-runs its `verification` command (and, for
sweep-originated items, re-scans and diffs the manifest).

## Reading and writing

- **Stage:** `python3 scripts/queue_status.py stage <id> --recipe ... --scope ...`
- **Manual-pickup floor (any agent, any tool):**
  `python3 scripts/queue_status.py list`
- **Claude Code session-start hook (optional convenience):** add to
  `settings.json`:

  ```json
  {"hooks": {"SessionStart": [{"hooks": [
    {"type": "command", "command": "python3 scripts/queue_status.py hook"}
  ]}]}}
  ```

  The hook prints one line when items are staged and nothing when the
  queue is empty or absent. It also surfaces non-terminal plans silent
  >14 days (`[plans] …`) — the cheap session-start surfacer behind the
  `consistency-session-execution` W-G assurance loop;
  `/find-orphaned-ideas --stale-plans` remains the authoritative
  detector. Codex/Augment users rely on the manual-pickup floor — the
  data is agent-neutral; only the hook is Claude-specific.

The status projection (`scripts/status.py`) reports the queue as its
`queue` section; the dashboard renders it with the pickup command as a
copy-paste action.

Source decision: `core:status-projection-schema` (ADR 0037).
