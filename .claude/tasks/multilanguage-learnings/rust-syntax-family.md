# Rust syntax-family final-value learning

## Outcome

Four read-only skills now have independent, value-tested Rust outcomes over one
bounded stable-Cargo syntax contract. They share only
`.claude/skills/_rust-syntax/scripts/rust_syntax_facts.py`; each selected skill
retains its own final artifact, verdict, lifecycle, and downstream action.

| Skill | Disposition | Exact useful outcome |
|---|---|---|
| `audit-decisions` | supported within the bounded syntax contract | `drift.md` and `raw-drift.json` retain a resolved `decision:0001` Rust comment and surface orphan `decision:9999`; registry and link compatibility artifacts remain distinct |
| `find-complexity-hotspots` | supported, advisory | reports only `route_invoice` at syntactic branch score 9 with `measure-first`; a branch-heavy nested closure does not inflate its enclosing function |
| `find-omnibus` | supported through the existing scout gate | four paired head-noun domains produce one candidate; supplied Stage 3 evidence grades it `confirmed_omnibus`, and the final report hands off to `/refactor-subsystem <spec-id>`; the cohesive invoice module stays absent |
| `find-standard-gaps` | supported for one Rust condition | a direct `parse_invoice` call handled by `match` and one unhandled call produce a 2-site/1-gap/50% coverage cell; strings and declarations do not become sites |

These are four final-value claims, not one generic “Rust parsed” claim. Audit
answers registry integrity; complexity offers a measurement lead; omnibus
requires human domain judgment; standard gaps measures application of a
declared syntactic baseline.

## Shared producer contract

The shared producer inventories project-root Rust roles, analyzes only the
explicit target's first-party source, and emits:

- exact real line/block/doc comments with strings, raw strings, characters,
  and nested block-comment text masked;
- declared function name/span/LOC and direct-body syntactic branch score;
- direct spelled calls, containing function, and `match` enclosure;
- source hashes, whole-project before/after manifest, tool probes, native
  commands, exclusions, and ambiguities.

It requires Cargo and rustc 1.85+, probes rustfmt and Clippy, and runs Cargo
metadata/check/test/Clippy with `--locked --offline --workspace --all-targets
--all-features` where applicable, `cargo fmt --all -- --check`, plus
per-selected-file rustfmt parse checks with child loading disabled. Cargo home
and target output are temporary and outside the host. The producer writes no
project artifact; consumer adapters atomically replace their own final files.

`complete` means all selected first-party source parsed, native checks passed,
no bounded ambiguity remained, and the project manifest was byte-preserved.
Missing/old tools, missing Cargo project metadata, cfg, macro/build-output, or
symlink boundaries are `partial`, never permanent unsupported. Broken probes,
malformed/native failure, invalid paths, or source mutation are `failed`.

## Source and must-not-fire policy

Production `.rs` source is eligible. Test/spec/fixture source, examples,
benches, `build.rs`, generated trees/markers, vendor/dependency trees,
`target`/build/report output, and symlinks are inventoried with roles but do not
produce facts. The fixture proves excluded decision references do not leak into
audit results and a comment-shaped ordinary/raw string does not become a
reference, call, or finding.

Any selected `#[cfg]`/`#[cfg_attr]`, macro invocation/definition, `include!`,
build-script output signal, or symlink prevents a clean result. This is
deliberately conservative: stable Cargo all-feature evidence does not prove all
target triples, and lexical source does not prove expanded items.

## Native tools and acquisition

- Python: explicitly supplied product virtualenv, 3.11.10
- Cargo: 1.97.1
- rustc: 1.97.1
- rustfmt: 1.9.0-stable
- Clippy: 0.1.97
- Tools/dependencies installed or updated: none
- Network: disabled by Cargo offline mode and dead proxy values

The dependency-free Cargo 2024 fixture has a library, smoke binary, integration
test, example, bench, and custom build target. The native boundary checks
project configuration and compile/test policy; the reports do not infer
runtime cost or behavior from a passing native command.

## Artifact lifecycle and copied execution

Every adapter deletes its own prior final artifacts before analysis and writes
a complete, partial, or failed replacement at the same destination. Tests run
complete -> malformed/failed for all four consumers and assert prior findings
cannot survive. Every positive path proves source preservation outside report
and build-output directories.

Each selected skill was copied under `.agents/skills/<skill>` together with the
single sibling `.agents/skills/_rust-syntax` dependency, then invoked from a
working directory outside both the source repository and host. All four reached
their real final artifact. Deleting `_rust-syntax` from each copied layout
produced `partial/rust_fact_producer_missing`; no consumer silently reported
clean or carried a local lexer/native-command fallback.

## Interface-depth and deletion proof

- **Deletion test:** removing the producer makes all four consumers lose role,
  lexer, tool, native, ambiguity, and preservation evidence; that complexity
  would otherwise be copied four times.
- **Caller knowledge removed:** consumers do not know raw-string delimiters,
  nested comments, function-body matching, closure exclusion, call spelling,
  source-role exclusions, tool versions, Cargo environment isolation, or the
  native command matrix.
- **Test surface:** the producer CLI proves facts directly; every durable
  consumer test then proves a different final report, and deletion tests hit
  the public copied-layout boundary.
- **Adapter reality:** four production consumers use identical facts. Their
  wrappers contain only final-value interpretation and report lifecycle.
- **Decision:** the shared module is deep enough; report schemas and judgments
  stay consumer-local.

## LOC, closures, and ML-025 economics

The shared producer is 732 physical / 664 nonblank lines and 27,997 bytes. The
four adapters total 574 physical / 515 nonblank lines and 23,161 bytes. The
focused test is 396 physical / 333 nonblank lines and 15,364 bytes. Maintained
adapter-plus-test cost is therefore 1,702 physical / 1,512 nonblank lines and
66,522 bytes.
With the 253-line fixture and this 184-line packet, the isolated owned branch
adds 2,139 physical lines / 81,772 bytes and changes no shared publication file.

Duplicating the same proven producer into all four skills would be 3,898
physical lines including the unchanged adapters/tests. Sharing removes 2,196
lines, a 56.34% reduction, exceeding the ML-025 25% gate. On nonblank lines the
reduction is 56.85% (3,504 to 1,512). A selected skill still carries the exact
same producer bytes in its copied closure, so per-skill closure size does not
increase relative to local duplication; the installed four-skill union stores
the producer once.

Exact source-checkout closures use sorted
`repository-relative-path + NUL + file-SHA-256 + LF` rows:

| Selected closure | Files | Bytes | Delta vs base | Manifest SHA-256 |
|---|---:|---:|---:|---|
| `audit-decisions` + shared producer | 7 | 110,332 | +33,577 | `b9a025179f4f8b5901b6d47241bca97aa3f72e08f696341ef27f5d167572d175` |
| `find-complexity-hotspots` + shared producer | 13 | 131,222 | +32,656 | `0880147c9831d401c31038a1291f6e437288c7a932484ec87fc36b66b36cfb14` |
| `find-omnibus` + shared producer | 12 | 162,275 | +34,800 | `c33b99d742d0c52dd192d8f75f8663523ad04addbd591f4a2bb22c111d76755c` |
| `find-standard-gaps` + shared producer | 12 | 184,616 | +34,116 | `22ef501b26e86fdec5640d7b8a1bd1ae62e061216de7e732e944564a145da10d` |
| four-skill union | 41 | 504,454 | n/a | `ed44fd2a54a52d4f0df90f51d0afb947d5fa63d7f050ecc817cff5d510c16380` |

The frozen fixture is 24 files, 253 physical / 236 nonblank lines, and 4,775
bytes. Its relative-path manifest is
`070d2cb76483cb8282db32c4def50f410bab574070fdd0ab837436ccde911eae`.

Focused verification passed 24 tests in 109.87 seconds (110.09 seconds wall).
Rust spine plus skill conformance passed 9 tests in 39.97 seconds. Ruff,
py_compile, fixture rustfmt, source-preservation oracles, and native checks are
also clean. Slow unrelated language-native families were intentionally not run.

## Explicit limitations

The producer is a fail-closed Rust-aware lexer and bounded delimiter parser,
not rustc's AST. It does not claim:

- macro/procedural-macro expansion or hygiene;
- cfg/feature/target/profile completeness beyond the commands run;
- import, alias, receiver, type, trait, overload, or symbol identity;
- call graphs, async execution, monomorphized paths, unsafe/FFI meaning, or
  runtime cost/behavior;
- build-script output, `OUT_DIR`, generated includes, nightly/private rustc
  APIs, non-Cargo builds, no_std, cross compilation, or external dependencies;
- that a name cluster is a domain (the omnibus scout remains mandatory); or
- that a direct call spelling identifies the intended API (standards remain
  syntax-only).

The complexity score counts direct-body `if`, `for`, `while`, `loop`, `match`,
`&&`, and `||`, excluding nested function and braced closure bodies. The
standard-gaps v1 condition is only `enclosed_by: "match"`. Broader conditions
or facts require a new bounded cohort.

## Root integration instructions

Root owns all publication surfaces. Integrate serially by:

1. Adding Rust to the `scans`/description/scope of exactly these four skill
   entries without changing their distinct final-value semantics.
2. Documenting each new adapter command and the sibling `_rust-syntax`
   copied dependency; the projection/install manifest must include that helper
   whenever any of the four Rust adapters is selected.
3. Publishing the statuses above in the Rust coverage matrix with this packet,
   the integrated revision, native checks, and explicit limitations. Missing
   tools remain partial/pending, not unsupported.
4. Preserving the omnibus Stage 3 scout requirement and the standard-gaps
   `match`-only condition; do not collapse the four report schemas into the
   producer schema.
5. Running the four existing skill-family regressions serially after shared
   publication, then router/catalog/projection checks. This lane intentionally
   did not run unrelated Go/Java/TypeScript/Swift native families.
