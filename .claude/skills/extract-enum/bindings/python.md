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

For a non-framework carrier, propose a string-valued enum (`enum.StrEnum` on
3.11+, or `class X(str, Enum)`) next to the carrier. Keep every member value
identical to the existing serialized string. This binding does not authorize
schema or data edits.

## Failure contract

- Exit 1 means the target resolved but has no literal comparison/assignment.
- Exit 2 means routing or target resolution failed.
- A candidate whose category is not `extract_enum_candidate` must exit 2
  before repository scanning and must not create the requested output.
