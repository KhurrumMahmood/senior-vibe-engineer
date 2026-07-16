---
id: "0039"
namespace: core
title: "Use tree-sitter for syntax, native compilers for demanded semantics, and optional ast-grep for rewrites"
status: accepted
date: 2026-07-16
deciders: [khurrum, codex]
assumes: ["normalized analysis facts are introduced only for named consumers", "host-native compiler, linter, and test commands remain the final correctness authority"]
revisit_when: ["WP4 cannot meet the pinned precision, recall, runtime, or install budgets", "two consumers require cross-project semantic indexing", "interactive refactoring requires continuously synchronized semantic state", "a selected package loses a compatible license or deterministic binary/wheel distribution"]
supersedes: []
superseded_by: null
applies_to: [scripts/_lib/lang_adapter/, scripts/analysis_portfolio_spike.py]
embodied_by: ["script:scripts/analysis_portfolio_spike.py", "script:scripts/spikes/tree_sitter_probe.py", "script:scripts/spikes/ast_grep_probe.py", "script:scripts/spikes/typescript_compiler_probe.cjs", "contract:tests/fixtures/analysis_portfolio_spike/oracle.json", "contract:reports/portable-skill-ecosystem-completion/WP1/analysis-portfolio-spike.json"]
tags: [analysis, tree-sitter, ast-grep, compiler, typescript, portability]
related_smell: missing-boundary
related_pattern: null
---

# Use tree-sitter for syntax, native compilers for demanded semantics, and optional ast-grep for rewrites

## Context

ADR 0032 separated concepts from language adapters, but the existing
JavaScript regex adapter misses ordinary ESM and TypeScript declarations.
Choosing a replacement by feature lists would risk a universal AST, a large
toolchain, or a stateful language service without a consumer.

The time-boxed D3 spike ran one pinned TypeScript corpus and oracle through
three viable candidates on macOS arm64. Tree-sitter plus the language pack
returned all syntax facts at precision/recall 1.0, occupied about 5.1 MB, and
ran warm in about 0.04 seconds. ast-grep returned the same syntax facts at
1.0/1.0, ran warm in about 0.07 seconds, but its platform package occupied
about 154 MB. TypeScript 5.9.3's compiler API returned syntax and semantic
references at 1.0/1.0, occupied about 23.6 MB, and ran warm in about 0.62
seconds. Exact values, corpus hash, commands, unsupported capabilities,
licenses, and platform limitations are in the spike report.

The spike also found a version boundary: TypeScript 7.0.2 ships a native
compiler and unstable APIs rather than the stable 5.x compiler API used by the
probe. No pinned SCIP indexer or TypeScript LSP was installed. Those candidates
were recorded as unsupported—not as zero-finding successes.

## Decision

Use a portfolio, not one universal analysis engine:

1. **Tree-sitter is the normalized syntax substrate.** WP4 may expose only
   facts with named consumers (initially symbols/imports/definitions/calls/
   writes and source locations). Grammars and runtime versions are pinned.
2. **Project-native compilers supply demanded semantics and final guards.** A
   TypeScript binding may use the host's pinned compiler API for references and
   type facts. Compiler/linter/test commands remain the executable guard, and a
   version without a compatible API fails loudly or uses a version-specific
   adapter.
3. **ast-grep is optional and on demand.** It is valuable for declarative
   structural queries and rewrites, but its native-package footprint is not a
   mandatory toolkit runtime cost. An installer includes it only for a binding
   or refactor recipe that names it.
4. **SCIP and stateful LSP services are deferred.** They become justified only
   when at least two accepted consumers require durable cross-project indexing
   or synchronized interactive semantics.
5. **Native Rust/Go tooling remains a sweep/guard shim.** WP5 may normalize
   cargo/clippy and Go tool output without waiting for parser-backed refactors.

WP4 must meet or improve the predeclared spike budgets: selected syntax and
semantic facts each require precision and recall 1.0 on the pinned corpus;
warm runtime is at most 1 second; Tree-sitter installation is at most 25 MB;
the TypeScript semantic adapter is at most 30 MB. The optional ast-grep lane
has a 6-second/200-MB ceiling. Recording a slower result does not satisfy the
gate.

## Alternatives considered

- **Regex/heuristic parsing.** Rejected for claimed structural support because
  current ESM/TypeScript misses are already known. It may remain an explicitly
  experimental fallback with no verified claim.
- **ast-grep for every syntax operation.** Rejected as the base runtime due to
  its much larger native distribution. Retained for its stronger query/rewrite
  ergonomics when selected.
- **SCIP as the universal semantic layer.** Deferred because it adds indexer,
  protocol, storage, and version ownership before a cross-file consumer earns
  them.
- **LSP as the universal semantic layer.** Deferred because process lifecycle,
  document synchronization, and nondeterministic server state create a service
  boundary that batch consumers do not need.
- **Compiler APIs only.** Rejected as the syntax substrate because it would
  couple every basic fact to each language's compiler and tool-version API.
- **Rewrite the toolkit runtime in Node/Rust/Go.** Rejected: runtime language is
  independent from subject analysis capability.

## Consequences

The common fact surface stays small, fast, and language-neutral, while semantic
depth remains idiomatic and version-aware. Optional transformations can use
ast-grep without imposing its footprint on every host.

WP4 must own grammar/version pinning and explicit capability failures. The
TypeScript binding must handle the 5.x/7.x API boundary rather than assuming
`require("typescript")` always exposes the same API. Adding SCIP/LSP or a new
fact without named consumers is disallowed.

## Verification

Rerun `scripts/analysis_portfolio_spike.py` using its exact pinned setup and
compare the corpus hash, per-family precision/recall, cold/warm timings,
installation sizes, licenses, and unsupported entries in
`reports/portable-skill-ecosystem-completion/WP1/analysis-portfolio-spike.json`.
WP4's conformance tests must enforce the stated budgets.
