---
id: portable-analysis-substrate
title: "Portable multi-language analysis substrate"
status: draft
last_audited: 2026-07-16
motivating_decision: "0039"
# `coverage` scans Python `# spec:<id>::IM-N` markers inside
# these roots only. Doc / skill / script / ADR IM items will
# never auto-tick here; track them via the spec checklist and
# audit-only `<!-- spec: -->` markers in the changed files.
code_roots:
  - scripts/_lib/lang_adapter
  - scripts/analysis_portfolio_spike.py
  - scripts/analysis_fact_benchmark.py
  - tests/fixtures/analysis_portfolio_spike
---

# Portable multi-language analysis substrate

## Provenance

Promoted from `ai-docs/plans/portable-analysis-substrate.md`, the
dependency-sized execution plan for WP4 and AC-4.1–AC-4.6 of
`ai-docs/plans/portable-skill-ecosystem-completion.md`. The master plan remains
authoritative. This spec preserves every criterion while making the selected
ADR 0039 portfolio executable.

## Goals

- Expose a versioned interface containing only facts required by named
  consumers—symbols, imports, definitions, references, calls, and writes—with
  per-adapter capability discovery (AC-4.1).
- Implement the ADR 0039 parser/query/native-compiler portfolio and meet the
  pinned AC-1.7 precision, runtime, platform, license, and install budgets
  (AC-4.2).
- Replace TypeScript heuristics with real parsing across required declaration,
  scope, extension, malformed-input, and location cases (AC-4.3).
- Keep Python behavior regression-pinned and expose the accepted Rust/Go fact
  subset with explicit remaining gaps (AC-4.4).
- Return typed adapter/file/capability failures for unsupported, missing,
  broken, or corrupt analysis instead of successful zero findings (AC-4.5).
- Produce deterministic golden facts and cold/warm runtime and memory evidence
  on representative small and large fixtures (AC-4.6).

## Architecture

Consumers request named capabilities from a versioned `FactProvider` contract.
Providers advertise support before execution and return normalized immutable
facts with deterministic file locations and ordering. Unsupported capability,
tool discovery, parse corruption, and execution failures use typed results that
carry adapter, file, and capability context. There is no universal AST and no
framework-specific route model in this substrate.

Tree-sitter is the portable syntax baseline selected by ADR 0039. Optional
ast-grep is used only when its query/runtime value is demonstrated. The stable
TypeScript Compiler API supplies definitions/references/types only for named
semantic consumers. Python is wrapped behind the same capability contract
without changing its pinned results. Rust and Go initially expose only the
facts required by accepted sweep/perimeter consumers; every other request is
an explicit gap.

Golden fixtures and benchmark records are executable release evidence, not
informal reports. Tool versions, licenses, platform support, deterministic
installation, corpus hashes, machine identity, cold/warm timings, peak memory,
and variance are pinned. A budget miss reopens ADR 0039.

The AC-1.7 evidence predeclared precision/recall, warm-runtime, and install-size
ceilings but omitted the cold-runtime and memory ceilings later referenced by
AC-4.6. Before the productized-provider benchmark is run, this spec closes that
underspecification with additive gates: cold and warm analysis are each at most
1.0 second for both fixtures; peak process RSS is at most 128 MiB; peak traced
Python allocation is at most 64 MiB; and warm-run coefficient of variation is
at most 20%. These gates add constraints without weakening the master AC.

## Implementation

- [x] AR-1: **Python compatibility oracle.** Pin current Python symbols,
  imports, definitions, references, calls, writes, locations, and failure
  behavior consumed by repository tools.
- [x] AR-2: **Consumer inventory.** Trace every adapter/fact consumer and map
  each requested fact to a named capability before shaping the interface.
- [x] AR-3: **D3 oracle.** Preserve the AC-1.7 corpus hash, semantic oracle,
  selected portfolio, versions, and all predeclared budgets.
- [x] AR-4: **Identity oracle.** Pin fact ordering, source locations, and every
  input that downstream stable finding identities consume.
- [x] AR-5: **Failure oracle.** Characterize unsupported, missing-tool,
  broken-tool, malformed-file, and corrupt-output paths; none may equal clean.
- [x] IM-1: **Versioned fact contract.** Implement capabilities, normalized
  fact types, provider discovery, version negotiation, deterministic ordering,
  and typed contextual failures. <!-- spec:portable-analysis-substrate::IM-1 -->
- [x] IM-2: **Tree-sitter baseline.** Implement reproducibly pinned providers
  for the accepted languages and expose only the accepted capability subset.
  <!-- spec:portable-analysis-substrate::IM-2 -->
- [x] IM-3: **Real TypeScript parser.** Cover exported functions/consts,
  classes, arrows, nested scopes, JS/TS extensions, malformed input, and exact
  source locations in golden tests. <!-- spec:portable-analysis-substrate::IM-3 -->
- [x] IM-4: **TypeScript semantics.** Use the stable compiler API for only
  those definition/reference/type capabilities justified by named consumers.
  <!-- spec:portable-analysis-substrate::IM-4 -->
- [x] IM-5: **Python adapter.** Preserve the AR-1 oracle behind the common
  interface and reject unsupported facts explicitly.
  <!-- spec:portable-analysis-substrate::IM-5 -->
- [x] IM-6: **Rust/Go subset.** Implement facts required by accepted
  sweep/perimeter consumers and publish explicit capability gaps.
  <!-- spec:portable-analysis-substrate::IM-6 -->
- [x] IM-7: **Fault injection.** Test absent and broken tools, timeouts,
  malformed files, corrupt parser output, and unsupported capabilities with
  adapter/file/capability context. <!-- spec:portable-analysis-substrate::IM-7 -->
- [x] IM-8: **Golden corpus.** Add deterministic small/large fixtures and
  golden facts for Python, JS/TS, Rust, and Go, including stable locations and
  ordering. <!-- spec:portable-analysis-substrate::IM-8 -->
- [x] IM-9: **Budget gate.** Rerun the pinned D3 benchmark, record platform,
  machine, tool versions, license/install facts, cold/warm runtime, peak memory,
  and variance, and fail on any threshold miss.
  <!-- spec:portable-analysis-substrate::IM-9 -->

## Learnings

### User-facing

- A single pinned Python dependency pair provides real parsing for all five
  accepted subject languages; no language-specific runtime is required for
  syntax facts.
- Unsupported and failed requests now name the adapter, path, capability, and
  failure class, so users can distinguish “no findings” from “not analyzed.”

### Technical

- TSX's grammar accepts both `.ts` and JSX-bearing `.tsx`, avoiding a second
  extension-only provider while retaining separate JavaScript/TypeScript IDs.
- Syntax-reference occurrences exactly reproduce the pinned D3 reference
  oracle. ADR 0039's compiler API remains reserved for a future named semantic
  definition/reference/type consumer; none of the 21 inventoried consumers
  requires it.
- The initial baseline search omitted hidden skill paths. The corrected
  evidence records 21 production consumers and preserves the raw Python AST
  compatibility seam for 20 of them.

## Exceptions

- SCIP/LSP lifecycle infrastructure is deferred until a named consumer and
  budget evidence justify it.
- ast-grep remains optional and on-demand unless the pinned benchmark proves it
  necessary within budget.
- Framework concepts such as Django or React routes remain binding facts, not
  universal syntax facts.
- TypeScript semantic capabilities outside named consumers, and unsupported
  Rust/Go facts, remain explicit gaps rather than guessed results.
- No network or model call is permitted in deterministic analysis.

---

## Known symbol inventory

No declared Python code root exceeded the scaffold inventory threshold. The
implementation inventory is therefore maintained by the AR/IM checklist and
the audited `code_roots` list above.
