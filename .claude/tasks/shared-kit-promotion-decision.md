# Shared-kit promotion decision and family-packet index

Status: accepted for P6/F1 closeout

Evidence snapshot: `f9d14f077b158291a360e83c3db47aecab01e606`

This decision compares completed TypeScript, Java, PHP, Rust, and Dart work.
It applies the conjunctive gate from the active execution ledger: a newly
promoted component needs at least two immediate real consumers, at least 25%
maintained-LOC reduction, copied-closure growth no greater than 10%, and median
latency growth no greater than 10%. Missing evidence does not pass a gate.

## Decision

No new cross-language semantic, syntax, proposal, mutation, or execution
component is promoted. The useful new sharing is language-local and remains
there. The already-proven P3 profile/inventory/doctor/conformance foundation is
retained at its current boundary; it is not evidence for expanding into a
runtime platform.

| Candidate | Evidence | Decision |
|---|---|---|
| Strict language profiles used by inventory and doctor | Two production callers; P3 copied closure `-0.092%`; warm medians TypeScript `+0.949%`, Java `+3.690%` | Retain existing shared foundation; do not expand its schema without a concrete language need |
| Copied-journey conformance | TypeScript and Java final-outcome consumers; P3 integrated replay `141 passed` | Retain as a tests-only outer contract |
| Generic lifecycle module | Only atomic text output has a production caller | Reduce to that behavior; removed unused terminal enum, JSON writer, artifact clearer, and source-manifest API plus their tests (`231` to `79` implementation/test lines, `65.80%` reduction) |
| Dart project/lexical provider | Three consumers; `41.25%` maintained-LOC reduction | Retain Dart-local; closure/latency equivalence was structural, not an independent A/B measurement |
| Rust project/lexical provider | Five consumers; `59.21%` maintained-LOC reduction | Retain Rust-local; no cross-language schema follows |
| Rust syntax provider | Four consumers; `56.34%` maintained-LOC reduction; latency comparator missing | Retain Rust-local; defer any broader promotion |
| Dart D2/D3 syntax providers | Three/four consumers; `43.06%`/`58.12%` maintained-LOC reduction; D3 copied bytes `-24.38%`; repeated median comparator missing | Retain Dart-local; defer any broader promotion |
| Rust semantic and proposal evidence | Five semantic consumers at `53.77%` LOC reduction; two proposal consumers at `28.6%`; closure/latency comparisons incomplete | Retain Rust-local; defer broader promotion |
| Dart LSP and accepted-evidence providers | Multiple real consumers and LOC savings; final post-extension closure/median comparisons incomplete | Retain Dart-local; do not create a cross-language fact or proposal schema |
| PHP/Java shared pilot mechanics | LOC reduction `11.11%`; closure growth `26.63%`; aggregate warm latency growth `9.18%` | Reject: two mandatory gates fail; keep correct PHP outcomes local |
| TypeScript Compiler API service | No two consumers require an identical fact contract | Reject |
| Java JDK semantic runtime | No demonstrated identical second consumer; J4 packet is stale | Reject now; refreeze J4 only if a future Java consumer needs the same facts |
| Universal AST/call graph/result schema, workflow DAG, daemon/cache, package manager, cross-language mutation executor | No compatible two-consumer contract or complete economics; language identity, project resolution, partiality, native checks, and rollback differ | Reject and do not reopen without new measured evidence |

Language-semantic schemas, consumer verdicts, proposal formats, and mutation
rollback remain owned by their language/skill families. Shared profiles do not
claim semantic equivalence.

## Frozen family-packet index

Workers receive the relevant row plus the active ledger's binding rules. A row
is `ready` only when its packet names owned implementation, fixtures, copied
closure, native commands, and final artifacts. Paths are repository-relative.

| Family | Language / state | Authoritative packet and owned surface | Fixture, native, closure, and final-boundary source |
|---|---|---|---|
| Project/lexical | Dart — `ready` | `multilanguage-learnings/dart-d1-project-lexical-family.md`; `_dart/dart_project_snapshot.py`; Dart adapters in `adapt-project`, `find-concept-divergence`, `find-folder-topology-drift`; `tests/test_dart_d1_project_lexical.py` | `tests/fixtures/dart-d1-project-lexical`; packet records three copied manifests, fatal analyze/format/direct test/smoke, and all final adaptation/finding artifacts |
| Project/lexical | Rust — `ready` | `multilanguage-learnings/rust-lexical-filesystem-family.md`; `_rust/rust_lexical_facts.py`; five named consumer adapters; `tests/test_rust_lexical_family.py` | `tests/fixtures/rust-lexical-family`; packet records five closures, locked/offline Cargo commands, rustfmt, and final adaptation/explanation/divergence/duplication/topology artifacts |
| Project/lexical | TypeScript — `family-local` | `adapt-project-typescript.md`, `find-folder-topology-drift-typescript.md`, `map-subsystem-typescript.md` and their named adapters/tests | Each packet owns its fixture/closure/final artifacts; no shared provider contract exists |
| Project/lexical | Java — `refreeze-required` | `java-j4a-project-graph.json` and Java map/adapter tests | Current map implementation/test LOC drifted from the packet; refreeze hashes, closure, and latency before using it for economics |
| Project/lexical | PHP — `rejected-extraction` | `p4-baseline/php-pilot-baseline.json`, `php-pilot.md` | The baseline is the frozen fixture/native/final-output packet and the decisive failed economics comparison |
| Syntax | Rust — `ready-local` | `rust-syntax-family.md`; `_rust-syntax/scripts/rust_syntax_facts.py`; four consumer adapters; `tests/test_rust_syntax_family.py` | `tests/fixtures/rust-syntax-family`; packet records exact closures, locked/offline Cargo/rustfmt commands, and audit/complexity/omnibus/standards artifacts; broader promotion waits on median A/B data |
| Syntax | Dart D2 — `ready-local` | `dart-d2-syntax-family.md`, `dart-d2-provider-extension.md`; `_dart/scripts/dart_syntax_facts.py`; analyzer tool; three consumers and two focused tests | `tests/fixtures/dart-d2-syntax`; packets record copied closures, offline locked analyzer setup, native analyze/format/test/smoke, and audit/comment/standards artifacts |
| Syntax | Dart D3 — `ready-local` | `dart-d3-declaration-body-family.md`; `_dart/scripts/dart_d3_snapshot.py`; four consumers; `tests/test_dart_d3_declaration_body_family.py` | `tests/fixtures/dart-d3`; packet records 60-file union closure, native commands, and explanation/complexity/duplication/omnibus artifacts |
| Syntax | TypeScript / Java — `family-local` | TypeScript per-skill learning JSON/Markdown; `java-j2-j3-expansion.json` and Java skill packets | Providers have different facts and final schemas; use the target skill's packet rather than inventing a shared parser |
| Syntax | PHP — `no-completed-family` | `php-pilot.md`, tree-sitter evaluation evidence | Syntax spans did not reach a final semantic value claim; use project-owned analyzers when present |
| Semantic/proposal/mutation | TypeScript — `ready-family-local` | TypeScript map, semantic-duplication, unify-shadows, and move-path packets plus their named adapters/tests | Corresponding fixtures record Compiler API identity, decoys, offline npm/typecheck or `node --check`, copied closure, report/proposal/move artifacts |
| Semantic/proposal/mutation | Java — `ready-family-local` | Java semantic-relationship, proposal, state-chain, and move packets plus Java-focused tests | Corresponding fixtures record JDK compiler facts, malformed/reflection/framework decoys, `javac --release 17 -proc:none`, copied closure, proposal/mutation boundaries |
| Semantic/proposal/mutation | PHP — `ready-family-local` | `p4-baseline/php-pilot-baseline.json`, `php-map-subsystem.md`, `php-move-path.md` | `tests/fixtures/php-pilot`; Composer/`php -l`/lint/smoke commands and final map/move rollback artifacts are frozen there |
| Semantic/proposal/mutation | Rust — `ready-local` | `rust-semantic-family.md`, `rust-read-only-proposals.md`, `rust-unify-shadows.md`, `rust-enum-regression-guard.md`, `rust-move-path.md` | Named Rust fixtures/tests record Cargo/compiler/stable-LSP facts, cfg/macro/unsafe/stale decoys, locked/offline native matrix, copied closures, accepted evidence, proposals, guard, and rollback |
| Semantic/proposal/mutation | Dart — `ready-local` | D4/D5/D6/D7/D8 packets, `dart_lsp_facts.py`, `dart_accepted_evidence.py`, named consumer/move adapters and tests | Named D4-D8 fixtures record LSP/accepted-evidence facts, conditional/part/generated/dynamic/symlink/stale decoys, native analyze/format/test/smoke, copied closures, proposals/guard, and mode-aware rollback |

All packet paths above are below `.claude/tasks/` unless they begin with
`.claude/skills/` or `tests/`. The next language packet must copy the field
shape from `.claude/tasks/multilanguage-learning-template.json`, name exact
owned and forbidden paths, and include positive, must-not-fire, degraded-tool,
copied-layout, stale-artifact, and native final-boundary cases.

## Frozen verification commands

```text
.venv/bin/python -m pytest -q \
  tests/test_language_support_profile.py \
  tests/test_language_support_lifecycle.py \
  tests/test_source_inventory.py \
  tests/test_language_doctor.py \
  tests/test_language_support_conformance.py
```

Language-local packets own their heavier native replay commands. New shared
promotion is forbidden unless a criteria revision adds complete conjunctive
economics and the existing final outcomes remain unchanged.
