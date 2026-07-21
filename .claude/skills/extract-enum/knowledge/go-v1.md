# Go typed-state proposal contract

This branch consumes the exact JSONL emitted by
`find-implicit-state/scripts/detect_go_state.py`. It accepts one resolved
built-in `string` field and refuses empty, mixed-field, named-authority, or
low-evidence results. Because repeated literals do not prove a closed Go
domain, every proposal remains `review_required` and includes a stop condition.

```bash
REPORT_DIR="reports/extract-enum/go-state"
python3 .claude/skills/extract-enum/scripts/collect_go_state.py \
  --findings reports/implicit-state/go.jsonl \
  --project-root "$(pwd)" \
  --output "$REPORT_DIR/targets.json" \
  --proposal "$REPORT_DIR/proposal.md"
```

The proposal preserves serialized string values, introduces a named string
type plus typed constants, inventories every covered direct caller and
convention-attributed boundary candidate, and requires `gofmt` plus the host's
`go test ./...`. It never edits Go source. Stop if a reviewer cannot establish an intentionally finite domain,
valid states are computed dynamically, or external callers require raw
strings.
