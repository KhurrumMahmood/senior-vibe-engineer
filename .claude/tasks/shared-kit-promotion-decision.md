# Shared-kit promotion decision and family-packet index

Status: accepted for P6/F1 closeout; Cohort A A1/A2 evidence appended

Evidence snapshot: `f9d14f077b158291a360e83c3db47aecab01e606`

This decision compares completed TypeScript, Java, PHP, Ruby, Swift, Rust, and Dart work.
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
| PHP A1 project/lexical provider | Five consumers; `62.43%` maintained-LOC reduction; maximum closure growth `0.32%`; median latency growth `1.86%` | Retain PHP-local in the external library; no cross-language schema follows |
| Ruby A1 project/lexical provider | Five consumers; `57.02%` maintained-LOC reduction; closure growth `0%`; median latency growth `-2.98%` | Retain Ruby-local in the external library; no cross-language schema follows |
| Swift A1 project/lexical provider | Six consumers; `62.80%` maintained-LOC reduction; closure growth `0%`; median consumer latency growth `-4.59%` | Retain Swift-local in the external library; no cross-language schema follows |
| PHP A2 syntax provider | Four consumers; `56.55%` maintained-LOC reduction; closure growth `0%`; median latency growth `3.70%` | Retain PHP-local in the external library; no cross-language schema follows |
| Ruby A2 syntax provider | Four consumers; `57.91%` maintained-LOC reduction; closure growth `0%`; median latency growth `1.068%` | Retain Ruby-local in the external library; no cross-language schema follows |
| Swift A2 syntax extension | Three new consumers on the existing provider; `45.53%` maintained-LOC reduction; closure growth `0%`; aggregate latency growth `2.81%` and median consumer change `-0.75%` | Retain the Swift-local extension; do not split or generalize its compiler-validated inventory |
| PHP A3 Composer-semantic provider | Five consumers; `62.65%` maintained-LOC reduction; maximum closure growth `0.00916%`; median latency change `-0.55%` | Retain PHP-local in the external library; direct Composer ownership is not a universal type/reference graph |
| Ruby A3 RBS-semantic provider | Five consumers; `58.76%` maintained-LOC reduction; union closure `-62.39%`; median repeated-provider latency `-78.22%` | Retain Ruby-local in the external library; authored RBS remains mandatory and runtime Ruby identity remains unresolved |
| Swift A3 SourceKit-semantic provider | Worker economics passed, but root copied replay exceeded 360 seconds in `textDocument/documentSymbol` and a one-query probe remained blocked after 137 seconds | Do not publish yet; require a predictably bounded cold/repeated protocol path before retaining or advertising the provider |
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
| Project/lexical | PHP — `ready-local` | `multilanguage-learnings/php-project-lexical-family.md`; `_php-project-lexical/php_project_lexical.php`; five named consumer adapters; `tests/test_php_project_lexical_family.py` | `tests/fixtures/php-project-lexical-family`; packet records copied closures, Composer/PHP native commands, lifecycle, economics, and five final outcomes. The earlier cross-language PHP/Java extraction remains rejected. |
| Project/lexical | Ruby — `ready-local` | `multilanguage-learnings/ruby-project-lexical-family.md`; `_ruby-project-lexical/ruby_project_lexical_facts.py`; five named consumer adapters; `tests/test_ruby_project_lexical_family.py` | `tests/fixtures/ruby-project-lexical-family`; packet records copied closures, frozen Bundler/Prism/native commands, lifecycle, economics, and five final outcomes |
| Project/lexical | Swift — `ready-local` | `multilanguage-learnings/swift-project-lexical-family.md`; `_swift-project-lexical/swift_project_facts.py`; six named consumer adapters; `tests/test_swift_project_lexical_family.py` | `tests/fixtures/swift-project-lexical`; packet records copied closures, restrictive SwiftPM/compiler/format/direct commands, lifecycle, economics, and six final outcomes |
| Syntax | Rust — `ready-local` | `rust-syntax-family.md`; `_rust-syntax/scripts/rust_syntax_facts.py`; four consumer adapters; `tests/test_rust_syntax_family.py` | `tests/fixtures/rust-syntax-family`; packet records exact closures, locked/offline Cargo/rustfmt commands, and audit/complexity/omnibus/standards artifacts; broader promotion waits on median A/B data |
| Syntax | Dart D2 — `ready-local` | `dart-d2-syntax-family.md`, `dart-d2-provider-extension.md`; `_dart/scripts/dart_syntax_facts.py`; analyzer tool; three consumers and two focused tests | `tests/fixtures/dart-d2-syntax`; packets record copied closures, offline locked analyzer setup, native analyze/format/test/smoke, and audit/comment/standards artifacts |
| Syntax | Dart D3 — `ready-local` | `dart-d3-declaration-body-family.md`; `_dart/scripts/dart_d3_snapshot.py`; four consumers; `tests/test_dart_d3_declaration_body_family.py` | `tests/fixtures/dart-d3`; packet records 60-file union closure, native commands, and explanation/complexity/duplication/omnibus artifacts |
| Syntax | TypeScript / Java — `family-local` | TypeScript per-skill learning JSON/Markdown; `java-j2-j3-expansion.json` and Java skill packets | Providers have different facts and final schemas; use the target skill's packet rather than inventing a shared parser |
| Syntax | PHP — `ready-local` | `multilanguage-learnings/php-a2-syntax-family.md`; `_php-syntax/run_php.py`; four consumer adapters; `tests/test_php_a2_syntax_family.py` | `tests/fixtures/php-a2-syntax`; packet records copied closures, Composer/PHP native gates, four independent final artifacts, lifecycle, and economics |
| Syntax | Ruby — `ready-local` | `multilanguage-learnings/ruby-a2-syntax-family.md`; `_ruby-syntax/ruby_syntax_facts.py`; four consumer adapters; `tests/test_ruby_a2_syntax_family.py` | `tests/fixtures/ruby-syntax-family`; packet records copied closures, frozen Bundler/Prism/native gates, four independent final artifacts, lifecycle, and economics |
| Syntax | Swift — `ready-local` | `multilanguage-learnings/swift-syntax-a2.md`; A2 extension to `_swift-project-lexical/swift_project_facts.py`; three new consumer adapters; `tests/test_swift_syntax_a2.py` | `tests/fixtures/swift-project-lexical`; packet records copied closures, restrictive Swift native gates, three independent final artifacts, lifecycle, and economics |
| Semantic/proposal/mutation | TypeScript — `ready-family-local` | TypeScript map, semantic-duplication, unify-shadows, and move-path packets plus their named adapters/tests | Corresponding fixtures record Compiler API identity, decoys, offline npm/typecheck or `node --check`, copied closure, report/proposal/move artifacts |
| Semantic/proposal/mutation | Java — `ready-family-local` | Java semantic-relationship, proposal, state-chain, and move packets plus Java-focused tests | Corresponding fixtures record JDK compiler facts, malformed/reflection/framework decoys, `javac --release 17 -proc:none`, copied closure, proposal/mutation boundaries |
| Semantic/proposal/mutation | PHP — `ready-family-local` | `php-a3-semantic-family.json`; `_php-semantic/php_semantic_facts.php`; five A3 adapters; prior `php-map-subsystem.md` and `php-move-path.md` | `tests/fixtures/php-semantic-family` and `tests/test_php_a3_semantic_family.py` freeze copied closures, Composer/native gates, five final review artifacts, lifecycle, and economics; pilot fixture retains map/move evidence |
| Semantic/proposal/mutation | Ruby — `ready-family-local` | `ruby-a3-semantic-read-only.md`; `_ruby-semantic/ruby_semantic_facts.py`; five A3 adapters; prior Ruby map packet | `tests/fixtures/ruby-semantic-family` and `tests/test_ruby_semantic_family.py` freeze authored RBS, copied closures, native gates, five final review artifacts, lifecycle, economics, and dynamic boundaries |
| Semantic/proposal/mutation | Swift — `repair-required` | `swift-semantic-a3.md`; `_swift-semantic-readonly/swift_semantic_facts.py`; five candidate consumers | Worker evidence is retained, but root cold/repeated copied execution timed out in SourceKit-LSP. Do not publish coverage until a bounded repair and root replay pass. |
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
