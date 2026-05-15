# scenario-resurrection

`old-rejected-attempt` was tried in early 2026, rejected, and carries a
lesson explaining why. Months later, `revived-attempt` re-opens the
question with `lineage_parents: [old-rejected-attempt]`.

Tests via `reconcile_lineage`: the back-pointer map should show that
`old-rejected-attempt` has child `revived-attempt`. This is what
`audit-ideas` uses to keep the chain navigable in both directions.

(A second assertion path — `project(records, "revived-attempt")`
producing a projection with `lineage_parents=["old-rejected-attempt"]`
— is exercised by other fixtures and the library's self-test.)
