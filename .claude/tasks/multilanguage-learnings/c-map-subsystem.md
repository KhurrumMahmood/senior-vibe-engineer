# C `map-subsystem` P7 learning packet

## Accepted bounded outcome

The C semantic cohort earns one final map for the frozen Make fixture when the
host supplies a valid, current, complete, C17-mode `compile_commands.json`.
The copied, stdlib-only `scripts/map_c.py` writes and atomically replaces:

- `.claude/docs/subsystems/<name>.md`
- `reports/map/<name>/c-map.json`

The accepted fixture has exactly two eligible translation units,
`src/invoice.c` and `src/main.c`. Public Clang `-MM` output owns
`include/cpilot/invoice.h`, `src/invoice_internal.h`, and
`src/pilot_mode.inc`; it leaves `include/orphan.h` and `include/orphan.inc`
explicitly ambiguous. Clang AST JSON supplies declarations and the public
header surface. The only cross-translation-unit relation is a conservative
shared-dependency edge through `include/cpilot/invoice.h`. It is not a call
graph.

`clangd --check` is a gate, not the semantic producer. Every eligible
translation unit must report the public `Compile command from CDB is` fact.
Process exit zero without that attribution is `unsupported`; the provider
never accepts clangd's inferred fallback command as semantic completeness.

## Terminal-state contract

| State | Bounded meaning |
|---|---|
| `complete` | Exact first-party TU inventory equals the database; every command is explicit C17, current, rooted in the copied host, dependency emission and AST JSON succeed, and clangd attributes every TU to that database. |
| `partial` | The database is stale or incomplete. No declarations or semantic graph are published from that rejected snapshot. |
| `unsupported` | Clang/clangd is missing or old; the database is missing, rooted in another directory, non-C, or replaced by `compile_flags.txt`/clangd fallback; the target is absent, excluded, symlinked, or contains no selected TU. |
| `failed` | The database JSON/shape is malformed, Clang dependency/AST analysis rejects source, clangd reports a real check failure, AST output is malformed, or a read-only source fingerprint changes. |

The focused lifecycle proof runs complete -> malformed C/failed -> clean
complete at the same Markdown and JSON destinations. Generated, vendor, test,
and build sources are inventoried but excluded. Artifact destinations are
contained below the two allowed host directories and reject symlink traversal.
All `.c`, `.i`, `.h`, and `.inc` fingerprints are identical before and after a
successful run. Malformed CLI/path input exits before writing artifacts.

## Native tool and copied-closure proof

No install or network access was used. The provider uses the host-owned Apple
Clang 21 and clangd 21 public CLIs and Python 3.11 standard library only; it
does not import libclang, `clang.cindex`, compiler-private APIs, a shared
semantic schema, or another repository runtime. The focused test copies the
whole selected `map-subsystem` skill into a disposable host and runs the copied
`map_c.py` without a checkout dependency.

The fixture's restrictive C17 warnings-as-errors Make build/test passes before
and after the positive map, and its executable prints
`invoice:INV-42:1:pilot`. The mapper records this as a separate host-owned
native obligation rather than claiming that Clang/clangd analysis exit alone
is the native test.

Measured after the provider and focused tests:

| Metric | Value |
|---|---:|
| Copied `map-subsystem` regular files | 13 |
| Copied closure bytes | 262,371 |
| Closure manifest SHA-256 | `9835faf4e6cca4bbb9c895288efc1aecce0ac313cf3a80584dff5f8255e6f982` |
| C adapter physical / nonblank LOC | 602 / 532 |
| C final-outcome test physical / nonblank LOC | 331 / 282 |
| Adapter + test physical / nonblank LOC | 933 / 814 |
| Final focused runtime | 4.21 s wall; 12 passed in 3.95 s |

The closure manifest hashes sorted regular-file paths relative to the selected
skill as `path + NUL + content_sha256 + LF`; `__pycache__` is excluded. The
focused command used the repository-owner-supplied runtime explicitly:

```text
<product-repo>/.venv/bin/python \
  -m pytest -q tests/test_map_subsystem_c.py
```

## Honest semantic limits and mutation decision

The accepted facts do not cover macro expansion or macro-generated
declarations, inactive preprocessor branches, function-pointer call targets,
ABI or object layout, arbitrary build variants, C++, Objective-C, CUDA,
OpenCL, assembly, Apple/framework semantics, or whole-program runtime
behavior. `.h` and `.inc` files stay ambiguous unless this exact compiler
dependency closure owns them. A successful native build or a zero analyzer
exit does not remove these limits.

This lineage is safe enough to authorize a **separate bounded mutation pilot**
on the frozen fixture: one source/header move with preview, include and Makefile
updates, source fingerprint, bounded diff, rollback, and native build/test.
It is not sufficient for general C mutation support, and this cohort performs
no mutation.

## What generalized and what stayed C-local

Atomic paired artifacts, explicit terminal states, same-destination stale
replacement, role exclusions, source fingerprints, unsafe-path refusal,
copied-closure replay, and native final-output verification generalized from
earlier languages. Compile-command trust, C-mode validation, `-MM` ownership,
Clang AST declaration attribution, clangd CDB-attribution gating, and
owned-versus-orphan header ambiguity remain C-local. They do not justify a
universal semantic graph or a shared provider schema.
