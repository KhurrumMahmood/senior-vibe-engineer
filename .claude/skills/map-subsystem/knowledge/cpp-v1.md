# C++20 v1: compile-database-backed subsystem map

This branch produces a durable subsystem map from compiler-attributed facts. It
is deliberately a snapshot of one host-owned C++20 build, not a whole-program
or all-configuration model.

## Evidence model

- A valid, current, complete `compile_commands.json` must cover every eligible
  first-party production translation unit exactly once. Every entry must use
  the version-gated Clang++ driver in C++20 mode. `compile_flags.txt`, inferred
  flags, mixed C/Objective-C++ entries, and compiler-driver substitutions are
  rejected.
- Clang++ `-MM` establishes project-header ownership and include edges. Clang's
  JSON AST establishes namespace-qualified declarations, overload signatures,
  template declarations, and direct compiler-resolved declaration/member
  references. All translation units are analyzed so references from outside
  the selected subsystem remain visible as inbound edges.
- `clangd --check` is an independent attribution gate. A zero exit without the
  recorded compilation-database command is not accepted and clangd is never a
  fallback fact source.
- A read-only Make database query supplements compile-command object outputs
  with project-local build-target prerequisite relationships. It does not
  infer link semantics for non-Make builds.
- Markdown and JSON share the source-snapshot digest. JSON also records the
  Markdown digest and a canonical evidence-payload digest. Re-run the command
  with `--verify-artifacts` to reject changed sources, Markdown, or JSON.

## Terminal states

- `complete` means the exact C++20 compile-command snapshot was current and
  complete, dependency emission and AST analysis succeeded for every entry,
  clangd attributed every entry to that database, and source bytes were stable.
- `partial` means the database is stale or does not exactly cover eligible
  production translation units. No semantic facts are retained.
- `failed` means malformed database data, compiler/dependency/AST/clangd
  failure, Make database failure, or observed source mutation. It exits 2 and
  replaces both final artifacts.
- `unsupported` means prerequisites or a safe supported topology are absent:
  missing/old tools, missing database, wrong language/mode/driver, mismatched
  root, excluded/unsafe target, or forbidden fallback attribution.

`status` and `diagnostic_state` are separate. `complete` describes coverage;
`clean` describes the accepted compiler diagnostics. A failed compiler run is
recorded as `failed` plus `errors`, never mislabeled clean.

## Deliberate semantic boundary

The mapper reports direct compiler-observed static references. It does not
claim virtual/dynamic call targets, reflection or runtime registrations,
macro/inactive-branch completeness, every possible template instantiation,
link-time behavior, ABI/layout, modules, Objective-C++, CUDA, or unrecorded
build variants. Template declarations remain useful public-surface facts while
their open-world instantiation boundary stays explicit.

The selected skill is a self-contained copied closure: Python standard library
plus host-owned Clang++, clangd, Make, `compile_commands.json`, and source. It
does not import repository providers or mutate host source.
