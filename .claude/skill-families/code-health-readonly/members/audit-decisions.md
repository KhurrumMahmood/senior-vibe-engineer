# Decision-reference lens

Purpose: find registry/link drift and resolve `decision:NNNN` references in
TypeScript/JavaScript comments without treating strings as references.

Dependency: `ai-docs/decisions/` must exist. Otherwise skip visibly.

The launcher runs the on-demand `audit-decisions/scripts/audit.py` against the
explicit target and a run-owned output directory. Exit 0 means no drift; exit 1
means drift was found and is still a successful scan; exit 2 is an execution
failure. Read `raw-drift.json` as the final artifact. Preserve both `drift` and
`references`; do not turn an absent registry, invalid JSON, unsupported source,
or missing artifact into clean evidence. This lane is read-only outside its
report directory.
