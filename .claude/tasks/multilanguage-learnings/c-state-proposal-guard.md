# C state proposal and exact-field guard packet

Base revision: `2f41d1582e7c3a89edcf8dcfc1d10ded5586498a`.

## Bounded outcomes

- `extract-enum` consumes, but never invokes or reimplements, the accepted
  `c-semantic-facts-v1` and `c-implicit-state-v1` artifacts. For exactly one
  `enum_review_only` `const char *` field, it verifies the fact-pack hash,
  current source manifest, resolved Clang declaration, and every accepted
  direct-assignment row. It emits a source-preserving `review_required`
  proposal with the exact field, current hashes, three literal-to-enumerator
  drafts, and the exact three caller functions.
- The proposal retains four independent human gates: ABI/layout, wire,
  storage/persistence, and external consumers/build variants. Observed direct
  strings do not close the domain, and the proposal neither applies a C edit
  nor authorizes a guard.
- `prevent-regression` requires a separately authored
  `c-enum-proposal-review-v1` with `status: accepted`, a SHA-256 binding to the
  proposal, all four approvals, current migrated-source hashes, native
  Make/smoke obligations, and a reviewed buildable regression plan. It stages,
  but does not install, one C17 `_Static_assert`/`_Generic` translation unit
  for the exact `job.state: job_state` authority.

These are final-outcome claims for one accepted direct-field shape, not general
C proposal or prevention coverage. No `SKILL.md`, router, matrix, coverage,
catalog, plan, shared provider, or detector surface is changed here.

## Native proof and human authority

The migrated overlay changes the accepted C semantic fixture's exact field to
`job_state`, migrates the three accepted writers, and adds an explicit
enum-to-wire adapter at the existing `printf` boundary. The accepted fixture's
Makefile remains the owner of C17 flags and build/test behavior. Both before
and after guard verification, the executable output remains exactly:

```text
semantic:running:us:112:1:legacy_status
```

The verifier works only on disposable copies. It first proves the accepted
migrated tree with `make clean`, `make compile-db test CC=<Clang 21+>`, the
exact smoke output, and standalone C17 compilation of the staged guard. It
then applies the accepted full reversion: the field returns to `const char *`,
the three writers return to string literals, and the wire adapter call returns
to the original direct string read. Make, native tests, and smoke still pass
without the guard. Compiling the same staged guard against that copy fails at
the exact diagnostic `job.state must remain job_state`; an include failure or
unrelated compiler error cannot satisfy the oracle.

Generation and verification preserve every host source/configuration hash and
never create the accepted `tests/guards/job_state_type_guard.c` destination.
Installation and future wiring remain human decisions.

## Closure and lifecycle

Copied execution is proved from standalone copies of the two existing skill
directories. The proposal collector is self-contained and contains no
detector/provider invocation. The guard generator and verifier share one
135-line C-local accepted-evidence helper copied beside them; they import no
repository package, upstream semantic code, or ambient Python dependency.

The focused tests cover ready output, partial detector evidence, a tampered
fact pack, stale current source, unapproved ABI authority, stale migrated
source, tampered staged guard, source preservation, and valid → refused →
valid artifact replacement. Refusal replaces prior success, so an old proposal
or guard cannot survive a failed rerun.

## Explicit limits

The proposal does not prove a closed runtime domain, alias/callback coverage,
macro or inactive-variant coverage, ABI/layout compatibility, enum underlying
representation, public-header compatibility, wire/storage/serialization
compatibility, or external-consumer safety. The guard protects only the
reviewed field type. It does not protect enumerator values, conversion
functions, assignments, aliases, runtime behavior, or any other field named
`state`, and it is not a Clang plugin or general lint.

## Implementation economics and verification

The implementation is 1,217 physical lines: a 517-line proposal consumer,
135-line evidence helper, 295-line generator, and 270-line verifier. Focused
proof is 636 lines across one pytest module and a three-file migrated overlay.
The language-local shape is deliberate: the accepted C provider already owns
Clang/C17 attribution, while the new code owns only downstream acceptance,
proposal, staging, and native-oracle behavior. No platform or shared
hardening layer is introduced.

Final focused and accepted-upstream results:

```text
7 passed in 10.49s (C proposal/guard plus accepted C semantic family)
Ruff: all changed Python files passed
Diff-scoped pre-commit hooks: passed
git diff --check: passed
```

The generic personal `skill-creator` validator was also attempted, but its
frontmatter schema rejects the ecosystem's pre-existing `job`, `tier`,
`language`, `scans`, and related keys. No `SKILL.md` was changed or weakened to
fit that unrelated schema.
