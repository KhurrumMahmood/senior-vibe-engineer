# Dart D6 accepted-state consumer learning and economics packet

Status: isolated implementation candidate on exact base `d8b4755`; no
coverage, matrix, router, catalogue, active-plan, installer, profile, or
publication claim is made here.

## Dispositions and useful final outcomes

- `extract-enum` is an implemented read-only Dart proposal outcome. It
  consumes one `dart-accepted-evidence-v1` envelope for accepted D5
  `find-implicit-state` evidence, revalidates the D5 fact-pack, scan,
  candidate, review, source, configuration, and cited-span lineage, and writes
  `targets.json`, `profile.md`, and `proposal.md`. The positive fixture yields
  one six-edit `Job.state` plan with `JobState`, three wire-preserving values,
  explicit JSON conversion, a recorded breaking public field-type boundary,
  and a dependency-free native value/round-trip test. It never edits source.
  The exact plan applied only in a disposable copy passes the host-safe native
  matrix. Accepted typed-state evidence yields a complete explicit
  `no_proposal_already_typed` outcome.
- `prevent-regression` is an implemented staged-guard outcome. It consumes the
  same accepted D5 envelope without rechecking the intentionally changed
  pre-migration source, then requires a separately accepted, canonical-hash-
  and `targets.json`-SHA-bound `dart-enum-proposal-review-v1` record for the
  migrated field. It writes `pattern.md`, `proposal.md`, staged project-owned
  `tool/` and dependency-free `test/` files, `host-wiring.diff`,
  `authority.json`, and `verification.json`. Native verification copies the
  audited host to disposable good and bad trees. Good analyze, format, direct
  host test, enum-value test, direct guard, guard test, and exact smoke pass.
  A buildable reversion to the former String representation passes without
  the staged guard and fails with it at the exact typed field reader. The
  audited host is never installed into or otherwise mutated. An existing byte-
  equivalent guard is a complete outcome and stages no duplicate.

Both rows are recommended for `dart-supported` only after root replays their
copied closures and serial publication gates. The implementation does not edit
either skill's shared `SKILL.md` prose.

## Consumer-independent accepted-evidence boundary

`.claude/skills/_dart/dart_accepted_evidence.py` owns only the shared envelope
mechanics needed by D6 and the accepted D7 consumers:

- canonical `acceptance_hash` verification;
- producer/version/schema/terminal-status and selected JSON-pointer hash;
- content hashes for every named upstream artifact;
- project-relative source/configuration hashes and exact cited spans;
- an explicit accepted human verdict and reviewed-boundary payload; and
- structured native obligations.

The validator returns typed `partial` versus `failed` refusals. It never runs a
process, imports the D4 provider, launches LSP, imports `package:analyzer`, or
interprets proposal/guard semantics. `extract-enum` owns domain, authority,
wire/public compatibility, enum naming, and rewrite-plan rules.
`prevent-regression` owns migrated-authority, accepted-proposal, destination,
native-guard, and staged-install rules.

The validator always revalidates accepted artifact bytes. Its
`verify_current_sources=False` mode is intentionally narrower: it preserves
the original source/config/span lineage structurally after an authorized enum
migration, while the guard consumer separately validates the SHA-bound
migrated source. This is not permission to accept changed evidence artifacts.

## Honest stops and terminal lifecycle

The focused suite proves complete/partial-or-failed/complete replacement at
the same destination for both consumers. A refusal atomically removes stale
proposal, staged-guard, wiring, and clean-verification artifacts.

`extract-enum` stops on missing, partial, unaccepted, stale, or internally
inconsistent evidence; open/sparse domains; ambiguous identity; private or
generated authority; external ownership; unresolved serialization,
reflection, or public compatibility; enum-name/value collisions; and stale or
ambiguous rewrite spans. None produces `proposal.md`.

`prevent-regression` stops on missing or tampered accepted evidence; a missing,
unaccepted, stale, or unrelated proposal review; changed migrated source;
private/generated/external authority; an unavailable dependency-free direct
guard; unsafe destinations; and a conflicting existing guard. None leaves a
staged guard or `host-wiring.diff`.

## Fixtures, copied closures, and native values

The positive, clean, and refusal fixture family contains 18 files / 2,278
bytes. Its sorted `path + NUL + file_sha256 + LF` manifest is
`b76177659dc7b4c900f7ee84fe6e3d5b9482bab5bade33eae8edf9b451ac9ac5`.
Every fixture is plain Dart `>=3.12.0 <3.13.0`, has a tracked existing package
configuration, a dependency-free direct test, and exact `42` smoke output.
No Pub command or network/install step is used.

Copied-layout tests execute outside the repository and audited host:

- `extract-enum` closure: validator + collector, 2 files / 1,115 physical /
  996 nonblank LOC / 46,022 bytes; manifest
  `c04cb09dea1af0c2682aa435dfb9507867081b651a5392b80f899721f434e39f`.
- `prevent-regression` closure: validator + generator + verifier, 3 files /
  1,300 physical / 1,157 nonblank LOC / 53,631 bytes; manifest
  `4706662fd19cffd929f89866232a0f8f6f3bd20b83b68323ae88aa5a4e0dfd7c`.

The proposal after-tree and the staged guard both execute native value checks
for `done -> done`, `queued -> queued`, and `running -> running`, plus
`fromWire` round trips. Wire values are preserved rather than inferred from
enum member spelling.

## ML-025 economics

The D6-local comparison conservatively charges all shared validation code and
its focused contract tests:

- shared validation cost `H = 430 + 356 = 786` physical LOC;
- D6 collector/generator/verifier plus D6 focused tests
  `C = 685 + 513 + 357 + 989 = 2,544` physical LOC;
- two duplicated validators: `C + 2H = 4,116` LOC;
- one shared validator: `C + H = 3,330` LOC; and
- saved maintenance: 786 LOC / **19.10%**.

The two D6 consumers alone do **not** clear the 25% extraction threshold. Do
not claim that they do. D7 has two additional real accepted-evidence consumers;
its stopped `unify-shadows` row must not count. The combined `n = 4` calculation
was completed during root integration using D7's final `C = 2,288` physical
LOC. Combined consumer/test cost is `C = 4,832`; four duplicated validators
would cost `C + 4H = 7,976`, while one shared validator costs
`C + H = 5,618`. The shared seam saves 2,358 physical LOC, or **29.56%**, and
therefore clears ML-025 without counting the stopped fifth row.

For the runtime-only union, the five D6/D7 consumer scripts total 3,093
physical LOC. One shared 430-LOC validator yields 3,523 LOC versus 4,813 LOC
with four embedded copies, a **26.80%** closure reduction. The shared module
adds no process, cache, wrapper, or network operation: each consumer imports
and calls the same validation function once, so the shared and literally
embedded execution paths are structurally identical. No synthetic latency
benchmark is claimed.

Per-consumer copied layout adds no wrapper/cache/process relative to an
identical embedded validator: it copies the same validator bytes and calls it
once. Installing the D6/D7 skills together shares one sibling `_dart` file
instead of duplicating it. The passing combined gate justifies this bounded
Dart acceptance seam only; it does not justify a broader evidence platform.

## Verification evidence

The frozen runtimes are
`/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python` <!-- # host-ref-allow: required frozen P7 runtime -->
and `/opt/homebrew/bin/dart`. <!-- # host-ref-allow: required frozen P7 runtime -->

```text
python -m pytest -q \
  tests/test_dart_d6_accepted_state.py tests/test_dart_accepted_evidence.py
# 36 passed

python -m pytest -q tests/test_dart_d5_semantic_state_family.py
# 7 passed

python -m pytest -q \
  tests/test_b2t_typescript_closed_state.py \
  tests/test_javascript_mutation_guard_cohort.py \
  tests/test_find_implicit_state_go.py tests/test_java_state_chain.py \
  tests/test_rust_enum_guard_finish.py
# 20 passed

python -m ruff check <validator, three Dart D6 scripts, two focused tests>
# All checks passed
```

Focused tests run these native commands on the three source fixtures, the
exact disposable proposal after-tree, and guard good/bad trees as applicable:

```text
dart analyze --fatal-infos --fatal-warnings .
dart format --output=none --set-exit-if-changed <existing authored roots>
dart test/native_test.dart
dart test/dart_d6_enum_values.dart
dart tool/job_state_guard.dart
dart test/job_state_guard_test.dart
dart bin/smoke.dart
```

All clean/good commands pass; smoke prints exactly `42`, the guard prints
exactly `dart-state-guard-ok`, and the staged guard alone rejects the buildable
String regression. Ruff and every applicable pre-commit hook passed for the
owned implementation, tests, fixtures, and this packet.

## Reusable lessons and limitations

- Accepted evidence needs two freshness modes across a real migration: always
  validate the accepted artifact envelope; validate original host source only
  before proposal, then bind the reviewed migrated source separately.
- A review-only proposal is useful when it carries exact one-occurrence edits,
  native obligations, a disposable value test, and explicit wire/public
  boundaries. Prose without an executable after-tree is insufficient.
- A regression guard proves its value only when the seeded regression remains
  buildable without the guard. Reverting the exact field plus the former
  literal representation keeps the negative tree honest; retaining the enum
  declaration makes the guard's type error specifically cite `String` versus
  the accepted enum.
- Staging and installation are different authorities. The generator writes
  review artifacts only under `reports/prevent-regression/`; verification
  installs solely into disposable copies.
- The proposal does not prove an exhaustive runtime domain or authorize source
  edits. The guard covers one reviewed public field, not dynamic access,
  reflection, serialization/runtime invariants, generated code, external
  owners, a universal lint, or Flutter state management.

Root should integrate this batch after D5 and the shared validator commit,
replay both copied commands and lifecycle transitions, calculate final `n=4`
economics with the accepted D7 consumers, then publish only these two rows if
all serial gates remain green.
