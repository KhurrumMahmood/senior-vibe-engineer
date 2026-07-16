# Django binding

Use this overlay only when per-root evidence selects the `django` framework
binding after the Python language binding.

## Endpoint

For a model `CharField` or `TextField`, propose a `models.TextChoices` class,
not a tuple-style choices list. Preserve the declared choice order and wire
values, including each declared human label exactly. Preserve every literal-
safe field keyword such as `null`, `blank`, `db_index`, and `help_text`;
unsupported positional, unpacked, or dynamic options stop collection rather
than disappearing from the proposal. Change the field default to the matching enum member and set
`choices=<Enum>.choices` only during the later execution skill.

Render the deterministic proposal boundary:

```bash
.venv/bin/python .claude/skills/extract-enum/scripts/propose.py \
  --targets "${REPORT_DIR}/targets.json" \
  --output "${REPORT_DIR}/proposal.md" \
  --semantic-output "${REPORT_DIR}/semantic.json"
```

For a pinned replay, add:

```bash
  --oracle tests/fixtures/wp3/extract-enum/ar7-semantic-oracle.json \
  --normalization-report "${REPORT_DIR}/normalization.json"
```

The proposal must include:

- the ordered `TextChoices` members and unchanged wire values;
- every caller classification, including bridge and case-risk sites;
- a pre-deploy distinct-value audit;
- reconciliation of declared choices against collected literals;
- a schema-migration step and any required data-normalization migration;
- characterization and subsystem tests; and
- a closed stop decision until all sites migrate, production values are a
  subset of member wire values, characterization remains green, and the
  stringly-status lint is clean.

Do not treat bridge literals as members. Keep or map them at the boundary. A
case variant may represent persisted data, so audit and normalize it before
adding the choices validator.
