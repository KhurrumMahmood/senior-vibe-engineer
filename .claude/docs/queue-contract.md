# Staged-work queue contract

The queue at `.engineering/local/queue/` holds agent-neutral JSON work items.
Legacy flat items remain readable. New sweep-originated items contain a
validated, judgment-bound **sweep packet** — the executable implementation of ADR 0036's packet
concept, placed per ADR 0037 (gitignored local zone; agent-neutral plain
JSON). One file per item, `<id>.json`.

## New sweep-item format

```json
{
  "queue_schema_version": 1,
  "kind": "sweep_packet",
  "packet": {
    "schema_version": 1,
    "finding_ids": ["f2_0123456789abcdef01234567"],
    "scope": ["app/a.py", "app/b.py"],
    "recipe": "what to do, self-contained — the executor reads nothing else",
    "verification": ".venv/bin/python -m pytest tests/test_a.py -q",
    "expected_delta": {
      "fixed": ["f2_0123456789abcdef01234567"],
      "allowed_new": [],
      "metrics": []
    },
    "token_budget": 35000,
    "manifest_hash": "<64 lowercase hex characters>",
    "judgment_hash": "<64 lowercase hex characters>"
  },
  "origin": "reports/unify-shadows/SC-3/proposal.md",
  "status": "staged",
  "staged_at": "2026-06-12T00:00:00+00:00"
}
```

The nested `packet` has a closed schema: finding IDs, sorted repository-relative
scope, recipe, verification command, structured expected manifest delta,
deterministically bounded token budget, and exact source manifest/judgment
hashes. `origin`, `status`, and `staged_at` are separate queue metadata. `status` moves
`staged → picked → done` — the picker edits the file in place (queue
items are per-run scratch, not append-only history).

Legacy flat items created by `stage` remain listable for compatibility. They
are not sweep packets and cannot enter sweep execution or harness verification.

Per ADR 0036, an executor's self-reported success is not verification:
the sweep harness—not the executor—runs `packet.verification`, rescans, checks
the bound manifest delta and scope, and emits verification evidence.

## Reading and writing

- **Stage a new sweep packet:** first generate it with
  `python3 -m scripts.sweep packet ... --out /tmp/packet.json`, then run
  `python3 scripts/queue_status.py stage-sweep <id> --packet /tmp/packet.json`.
  Invalid, loose, or over-budget packet JSON is rejected.
- **Stage a legacy item:** `python3 scripts/queue_status.py stage <id> --recipe ... --scope ...`.
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
