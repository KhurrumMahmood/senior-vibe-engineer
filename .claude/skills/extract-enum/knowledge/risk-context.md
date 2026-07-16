# Closed-vocabulary compatibility risks

- Treat spelling and case variants as possible persisted-data differences.
- Keep vendor, webhook, import, and other third-party literals at a mapping
  boundary unless the carrier owns them as states.
- Compare the declared vocabulary with collected literals in both directions.
- Flag values read but never written and values written but never read.
- Preserve member wire values exactly; symbolic member names may improve.
- Keep execution blocked while any site is dynamic, unclassified, or absent
  from the migration plan.
