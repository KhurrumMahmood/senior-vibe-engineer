# Python binding

Use this overlay for Python carrier and caller mechanics. The runtime language
of the toolkit is not itself evidence that this overlay applies; require the
selected root's binding evidence.

## Collect

Candidate form:

```bash
.venv/bin/python .claude/skills/extract-enum/scripts/collect.py \
  --from-finding "${FINDING_ID}" \
  --findings reports/implicit-state/latest/findings.json \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/targets.json"
```

Explicit form:

```bash
.venv/bin/python .claude/skills/extract-enum/scripts/collect.py \
  --target "${FILE}::${FIELD}::${MODEL_CLASS}" \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/targets.json"
```

The collector parses source without importing the host application. It records
field keyword arguments, a referenced two-column choice constant, literals,
comparison and assignment sites, and caller counts. It skips tests, generated
trees, environments, dependencies, and migrations.

For a plain class/dataclass string attribute, render the deterministic Python
endpoint:

```bash
.venv/bin/python .claude/skills/extract-enum/scripts/propose_python.py \
  --targets "${REPORT_DIR}/targets.json" \
  --output "${REPORT_DIR}/proposed_enum.py" \
  --semantic-output "${REPORT_DIR}/semantic.json"
```

The renderer emits `enum.StrEnum` next to the carrier, preserves every member
wire value, and fails closed on unsupported carriers or member-name collisions.
This binding does not authorize schema or data edits.

## Failure contract

- Exit 1 means the target resolved but has no literal comparison/assignment.
- Exit 2 means routing or target resolution failed.
- A candidate whose category is not `extract_enum_candidate` must exit 2
  before repository scanning and must not create the requested output.
