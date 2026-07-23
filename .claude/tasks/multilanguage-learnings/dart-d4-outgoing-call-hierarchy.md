# Dart D4 resolved outgoing-call provider extension

Status: isolated provider-only implementation candidate on exact base
`19f7bb27b7dcfcecd2625bcc931c99dc6f4a00ed`. No consumer, shared `SKILL.md`,
router, catalogue, matrix, coverage, profile, active-plan, installer, or
cross-language infrastructure is changed.

## Outcome and authority

The accepted `dart-lsp-facts-v1` provider now issues
`textDocument/prepareCallHierarchy` followed by
`callHierarchy/outgoingCalls` for every production callable whose name is in
the union `--query` set. Dart SDK LSP Analysis Server 3.12.2 remains the only
semantic authority. `server.info` preserves the initialize response name and
version, `tool` preserves the selected Dart executable/version, and no raw LSP
`data`, private analyzer API, syntax-inferred edge, return-shape judgment,
policy judgment, capability matrix, or consumer result is published.

This is sufficient provider material for a future
`find-semantic-duplication` implementation to compare server-resolved direct
callee identities without name matching. `unify-shadows` remains downstream
of a separately reviewed and accepted D5 finding; this batch does not bypass
that boundary or implement either consumer.

## Additive schema contract

The outer schema remains `dart-lsp-facts-v1`. Existing source inventory,
package configuration, definition/reference/rename/module facts,
`query_plan_sha256`, `fact_pack_sha256`, status vocabulary, and
`load_or_collect` source/configuration revalidation remain intact.

`query_plan.requests` adds exactly:

```text
textDocument/prepareCallHierarchy
callHierarchy/outgoingCalls
```

`call_hierarchy_queries[]` contains one normalized origin record per prepared
callable identity:

```text
caller
source_sha256
prepare.method
prepare.status
prepare.result_count
method
outgoing_status
status
outgoing_calls[]
uncertainties[]
```

`caller` and every `outgoing_calls[].callee` have these consumer-ready fields:

```text
symbol_id
name
kind
kind_name
detail
origin
role
path
uri_sha256
declaration_range
selection_range
```

- `symbol_id` is `dart:` plus the canonical SHA-256 of all other normalized
  identity fields. Same-spelled functions or methods in different owners are
  therefore distinct by resolved path and selection range, never by name.
- `origin` is `first-party`, `first-party-excluded`, or `external`. A
  first-party item has a project-relative `path`; an external/non-project item
  has `path: null` and a non-reversible `uri_sha256`. `role` preserves
  production/generated/test/vendor/etc. inventory classification.
- `declaration_range` and `selection_range` each contain `line`, `column`,
  `end_line`, and `end_column`. They are 1-based normalized LSP UTF-16
  positions; end positions remain exclusive.

Each `outgoing_calls[]` row contains:

```text
callee
call_sites[]
resolution
```

Every `call_sites[]` row contains the origin source `path` plus the same four
range coordinates normalized from the server's exact `fromRanges`.
`resolution` is `resolved-first-party`,
`resolved-excluded-first-party`, or `resolved-external`. External and excluded
targets are retained as explicit boundary rows rather than silently dropped,
so two functions cannot appear identical merely because a dependency or
generated callee was omitted.

`prepare.status` and `outgoing_status` make both request stages explicit.
`status` is `complete` only when that caller's prepare/outgoing requests and
all returned rows are well formed, all callees are production-scoped, and no
bounded dynamic signal is present. Otherwise it is `partial` and
`uncertainties[]` carries a typed reason. The outer pack becomes
`partial/call_hierarchy_uncertainty` when an explicitly queried caller is
partial. Missing call-hierarchy capability is also a missing required
capability; missing/old/broken Dart, LSP process/protocol failure, error
diagnostics, stale package configuration, and source mutation retain their
existing non-complete terminal paths.

`call_hierarchy_summary` exposes exact `callers`, `complete`, `partial`,
`resolved_edges`, and `unresolved` counts. It is a fact summary, not a lead or
equivalence score.

## Fixture, uncertainty, and native proof

The 11-file / 1,652-byte fixture manifest is
`bc3aed802c8f5e53ce8a02c2fae5ee3ba817e81e2f7c9bb3acc72cdbff5ab14b`,
using sorted fixture-relative `path + NUL + file-SHA-256 + LF` rows. It covers:

- four same-spelled `compute` declarations across two top-level owners and two
  class owners;
- relative and `package:` imports with aliases;
- exact function, method, and constructor targets plus exact qualified call
  spans;
- a `dynamic` receiver that produces no guessed edge and one caller-local
  `dynamic-type-syntax` uncertainty;
- an SDK method target retained as `resolved-external` with a URI digest;
- generated source excluded as a caller; and
- a clean direct native test plus a deliberate failing-test variant.

The clean host passes fatal analyze, check-only format, dependency-free direct
test, and exact `36` smoke output without changing audited bytes. Replacing
the direct test with the committed failing variant exits nonzero with the
expected deliberate failure. The provider does not claim runtime behavior;
this native D0 gate remains a separate required proof.

## Copied external-library closure

The copied test installs only:

```text
map-subsystem/scripts/dart_lsp_facts.py
```

under an external `.agents/skills` root, invokes it with product Python
`-I -S`, and obtains the same 9 callers, 11 resolved edges, and two explicit
partial callers without repository imports or host writes. The provider is
1,425 physical / 1,347 nonblank lines and 58,063 bytes; its file SHA-256 is
`45da40418c00f93d517d0c6557d4e32cc9b53a1c5c750718cdd1cfb1ec7783f1`.
The one-file install-relative closure manifest is
`ce5aaa2229745ba31c52519fab5694f224578e734d10c70dad80891cc797fe20`.

## Limitations

- Only callables whose exact names are in the union query set are prepared;
  candidate selection remains consumer-owned.
- The graph is the selected static package configuration, not runtime reachability.
- The bounded dynamic signal is literal `dynamic` syntax inside the caller;
  other runtime dispatch, `noSuchMethod`, reflection, registries, isolates,
  native/JS interop, generated callers, conditional configurations, parts,
  augmentations, Flutter behavior, and external consumers remain unresolved.
- SDK/dependency targets retain identity and boundary classification, not
  dependency internals or portable absolute paths.
- Calls do not prove matching return shape, side effects, error/async policy,
  protocol compatibility, behavioral equivalence, or safe consolidation.

## Verification

The focused extension suite passes 5 tests. The preserved D4/D5 suites pass
16 tests together, including valid -> failed -> valid replacement, missing /
old / broken analyzer states, stale source/configuration rejection, copied
closures, and both native matrices. The exact final-byte split replay passes
54 preserved D1-D3 tests in 421.17 seconds plus 21 focused/preserved D4-D5
tests in 72.51 seconds: 75 total. The final handoff also records every
diff-scoped pre-commit hook passing: Ruff, whitespace/EOF/YAML,
large-file and merge-conflict checks, all ecosystem AST rules, and the
always-run no-host-reference guard.
