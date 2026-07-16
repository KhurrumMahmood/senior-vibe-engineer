---
role: enum-profiler
input: one closed-vocabulary target and its collected literals and callers
output: profile.md with complete site classifications, members, wire values,
        compatibility risks, and a closed/open stop decision
---

# Enum-profiler scout brief

Read the supplied `targets.json` for exactly one carrier field and write the
requested `profile.md`. Do not edit production code, run migrations, open a
second target, or invent evidence.

For every comparison and assignment, record file, symbol, literal, and exactly
one classification: `confirmed_state_compare`, `assignment`,
`dynamic_value`, `third_party_bridge`, or `legacy_case_risk`. Preserve every
case variant. Derive members from the declared carrier vocabulary, keeping its
wire-value spelling and order. External bridge values remain mappings and do
not become members.

Write these sections: Location, Declared vocabulary, Member table, Caller
classification counts, Caller table, Compatibility risks, Follow-on findings,
and Stop decision. Use `profile_incomplete` and keep the stop decision closed
when any site cannot be classified from artifacts. Your output is judged only
by the file written at the requested path and its complete representation of
the input sites.
