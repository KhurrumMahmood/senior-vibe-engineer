# Declared-standard coverage lens

Purpose: find direct call sites where a host-declared syntactic standard should
apply but does not. A gap is triage evidence, not automatically a bug.

Dependency: an explicit host-owned standards JSON is required. Otherwise skip
visibly; never substitute the shipped example or invent policy.

The launcher runs the on-demand `find-standard-gaps/scripts/scan_coverage.py`
with the standards file, project root, and run-owned output directory. Read
`coverage.json` as the final artifact. Preserve every status:
`partial`, `language_unsupported`, `no_files_matched`, `gated_out`, `skipped`,
and `error` are non-clean. Only `scanned` with zero gaps and no skipped or
unsupported files is clean. Generated, vendor, dependency, test, fixture,
build-output, and symlink exclusions remain binding. This lane is read-only
outside its report directory and never fixes a gap.
