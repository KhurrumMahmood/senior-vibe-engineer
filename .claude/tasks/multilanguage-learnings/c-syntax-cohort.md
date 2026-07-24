# C17 syntax-cohort final-value learning

## Outcome

Four read-only skills now have independent, value-tested C outcomes over one
bounded Clang 21 and compilation-database contract. They share only
`.claude/skills/_c-syntax/scripts/c_syntax_facts.py`; the selected skill keeps
its own final artifacts, verdict, lifecycle, and downstream action.

| Skill | Bounded useful outcome |
|---|---|
| `audit-decisions` | Real Clang comment tokens retain resolved `decision:0001` and orphan `decision:9999`; string-shaped decoys never become references. |
| `find-complexity-hotspots` | `route_invoice` reaches `measure-first` at direct-body score 8; a called function body and macro-origin `&&`/`||` nodes do not inflate the score. |
| `find-omnibus` | Four paired function-name clusters nominate `src/omnibus.c`; only supplied, schema-valid scout evidence turns it into an explicit `confirmed_omnibus` finding. |
| `find-standard-gaps` | One configured `enclosed_by: "if"` direct-call condition finds two `parse_invoice` sites, one syntactic gap, and 50% coverage. |

The reports deliberately do not collapse into one generic “C parsed” result.
Decision integrity, complexity measurement, domain judgment, and declared
standard coverage remain separate user values.

## Producer and compile-command boundary

The C-local producer reuses the accepted C spine rather than introducing a
language platform:

- host-owned Clang 21+ only;
- non-empty `compile_commands.json` rooted in the copied host;
- exact first-party translation-unit coverage;
- explicit `-std=c17`, `-c`, and the same version-gated Clang executable;
- Clang `-MM` dependency ownership and freshness against the Makefile,
  translation units, and owned headers;
- raw comment tokens for exact line/block comment spelling;
- AST JSON for function definitions, direct-body branches, and direct spelled
  calls;
- before/after project manifest proof excluding report and native-build output.

`complete` means that exact compile-command snapshot passed dependency, AST,
and raw-token analysis without changing source. A missing/old tool or missing,
foreign, or non-C database is `unsupported`; incomplete/stale database evidence
is `partial`; malformed database/source, analyzer failure, malformed AST, or
source mutation is `failed`. Consumers replace stale final artifacts in every
state.

The fixture separately proves the host-owned restrictive C17 warnings-as-errors
build, Make test, and executable smoke output `c-syntax:7`. Analyzer success is
not represented as native or runtime proof.

## Fact contract and exclusions

The producer emits only:

- real line/block comment spelling and exact source location from raw tokens;
- declared function name/span/LOC;
- a direct-body score for C `if`, loop, switch, conditional-operator, `&&`, and
  `||` syntax;
- direct `CallExpr` spelling whose callee is a function declaration, containing
  function, and syntactic `if` enclosure.

Macro-origin AST subtrees are pruned and counted as omitted. ISO C17 has no
nested function body; the direct-body walk also stops at any nested
`FunctionDecl`, and a wrapper calling a branch-heavy function receives only its
own body score. Test, generated, vendor, build, report, tool-internal, and
symlink roles do not enter the exact first-party translation-unit census.

## Copied closure and interface depth

Each selected skill was copied beneath `.agents/skills/<skill>` with the single
sibling `.agents/skills/_c-syntax` dependency, then launched under isolated
Python from outside the repository and host. All four reached their real final
artifacts without a checkout import.

- **Deletion test:** without the producer, compile-database trust, dependency
  ownership, raw-token parsing, AST pruning, tool states, and source manifests
  would be duplicated four times.
- **Caller knowledge removed:** consumers know only comments, functions,
  scores, calls, statuses, and claim boundaries; they do not reconstruct Clang
  commands or location rules.
- **Test surface:** the producer CLI is tested directly and every consumer is
  tested again through its final artifact and copied layout.
- **Adapter reality:** four real consumers share the same facts; their wrappers
  retain distinct report meaning.
- **Decision:** one bounded C-local helper is deep enough; there is no shared
  multi-language provider or schema.

## Verification summary

Focused coverage includes positive results, a bounded clean complexity target,
malformed-source same-destination replacement for all four consumers,
missing/old/failing Clang states, malformed/incomplete/stale compilation
databases, copied closures, role exclusions, source preservation, native build,
native test, and executable smoke. Ruff covers the producer, four adapters, and
the focused test. No tool or dependency was installed and no network access was
used.

## Explicit limitations

These outcomes are advisory syntax evidence for one exact C17 compile-command
snapshot. They do not claim:

- macro expansion meaning, macro-generated declarations, or inactive branch
  completeness;
- arbitrary build variants, cross compilation, target/sysroot equivalence, or
  generated-build provenance;
- function-pointer target resolution, aliases, whole-program call identity,
  linkage correctness, ABI/layout, undefined-behavior analysis, or runtime
  control flow;
- runtime complexity, performance, error handling, or policy compliance;
- that name clusters are domains or that a decomposition is safe—the scout
  remains mandatory;
- C++, Objective-C, Objective-C++, CUDA, OpenCL, assembly, framework, or build
  system support beyond this fixture-owned Make flow.

The frozen standards condition is only direct call spelling plus syntactic
`enclosed_by: "if"`. A different handling rule requires a new bounded outcome,
not a broadened runtime claim.

## Root integration instructions

Root owns publication. Integrate serially by documenting the four C adapter
commands and the sibling `_c-syntax` copied dependency, then update the C
coverage/matrix/catalog/router surfaces with the integrated revision and these
limits. Preserve the omnibus scout gate and the standards `if`-only condition.
This implementation lane intentionally does not edit those shared surfaces or
the already accepted C map/comment providers.
