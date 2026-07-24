# Swift accepted state proposal and guard

Status: bounded Swift 6.3.3 downstream evidence.

The enum proposal and exact-property guard consume accepted A3 artifacts; they
never rerun semantic detection. One content-addressed review accepts
`Job.state`, its three exact raw values, and reuse of the existing `JobState`.
A second review binds the migrated source inventory and an exact buildable
String reversion.

The proposal edits no source. The guard is staged but not installed. Its
same-module function typechecks only when `Job.state` has the accepted
`JobState` type. The migrated tree passes restrictive SwiftPM build, strict
format, direct check, smoke, and guard typecheck. A disposable String reversion
passes the same native gates without the guard and fails with it. Atomic
terminal replacement removes stale positive artifacts on refusal and permits
valid-invalid-valid recovery.

This proves one exact dependency-free SwiftPM target under Apple Swift 6.3.3.
It does not prove runtime closure, raw-value or Codable compatibility,
Objective-C/dynamic identity, protocol/existential dispatch, external or
framework callers, generated/macros/plugins, conditional variants, ABI, or
release safety.
