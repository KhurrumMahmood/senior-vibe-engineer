# Swift accepted state proposal and guard

Status: bounded Swift 6.3.3 downstream evidence.

The enum proposal and exact-property guard consume accepted A3 artifacts; they
never rerun semantic detection. One content-addressed review accepts an exact
resolved String property, its observed raw values, and one compiler-identified
existing String-backed enum. The case mapping preserves raw values explicitly
when Swift case names differ. A second review binds the migrated source
inventory and an exact buildable String reversion.

The proposal edits no source. The guard is staged but not installed. Its
same-module function is derived from the accepted owner, member, and enum, and
typechecks only while that property retains the accepted enum type. The
migrated tree passes restrictive SwiftPM build, strict format, direct check,
smoke, and guard typecheck. A disposable String reversion passes the same native
gates without the guard and fails with it. Atomic terminal replacement removes
stale positive artifacts on refusal and permits valid-invalid-valid recovery.

The copied proof covers both `Job.state`/`JobState` with identity case names and
`Download.phase`/`DownloadPhase` with distinct case names and hyphenated raw
values. Both traverse proposal, migrated native gates, exact guard typecheck,
and buildable String reversion rejection under Apple Swift 6.3.3. This does not
prove runtime closure, raw-value or Codable compatibility,
Objective-C/dynamic identity, protocol/existential dispatch, external or
framework callers, generated/macros/plugins, conditional variants, ABI, or
release safety.
