---
name: portable-analysis-substrate
title: "Portable multi-language analysis substrate"
status: promoted
date: 2026-07-16
authors: [khurrum, codex]
motivating_decision: "0039"
successor_spec: portable-analysis-substrate
subsystems: [language-analysis, adapters, parser-portfolio, normalized-facts]
workflows: [code-analysis, detector-input, refactor-evidence]
---

# Portable multi-language analysis substrate

## 1. Scope & Bounds

Dependency-sized execution plan for WP4 of
`portable-skill-ecosystem-completion`. It owns AC-4.1–AC-4.6 exactly; the
master remains authoritative.

In scope: a versioned fact/capability interface, the D3-selected parser/query/
native portfolio, real TypeScript parsing, regression-pinned Python behavior,
the Rust/Go fact subset needed by accepted shims/perimeter claims, typed
unsupported failures, deterministic golden fixtures, and budget enforcement.
Out of scope: routing (WP2), installation/bindings (WP3), detector product
slices (WP6), and refactor application/guard compilation (WP7).

## 2. Success Criteria

- **AC-4.1:** A versioned interface exposes only named-consumer facts—symbols,
  imports, definitions, references, calls, writes—with per-adapter capability
  discovery; framework facts remain bindings.
- **AC-4.2:** Implement ADR 0039's selected Tree-sitter, optional ast-grep, and
  native compiler portfolio; rerun the pinned AC-1.7 corpus and meet every
  predeclared precision, runtime, platform, license, and install budget.
- **AC-4.3:** Real TypeScript parsing handles export functions/consts, classes,
  arrows, nested scopes, JS/TS extensions, malformed input, and locations.
- **AC-4.4:** Python behavior remains regression-pinned; Rust/Go expose the
  subset required by accepted consumers and name every remaining gap.
- **AC-4.5:** Unsupported/missing/broken/corrupt capability requests produce a
  typed adapter/file/capability failure, never a clean zero-finding result.
- **AC-4.6:** Golden facts are deterministic across supported versions/
  platforms and meet cold/warm runtime and memory budgets on small/large
  fixtures with machine/variance evidence.

Verification and evidence protocol is inherited unchanged from the master.

## 3. Impact Map

| Surface | Change / evidence |
|---|---|
| `scripts/_lib/lang_adapter/` | versioned interface, facts, adapters, typed failures |
| `scripts/analysis_portfolio_spike.py` | promoted benchmark/oracle inputs, not runtime dependency |
| D3 package/tool setup | pinned deterministic Tree-sitter/ast-grep/TypeScript portfolio |
| detector/refactor consumers | capability requests only; no universal AST coupling |
| `tests/fixtures/analysis_portfolio_spike/` | frozen semantic oracle retained |
| new small/large golden fixtures | JS/TS/Python/Rust/Go facts, failures, performance variance |

## 4. Blast Radius

Preserve Python adapter output, finding identity inputs, stable locations, and
the D3 corpus/hash/budgets. Keep unsupported capabilities explicit. Do not
introduce framework routes into universal facts, a giant language-neutral AST,
network/model calls, or runtime dependency on report/prototype paths. Trace all
adapter/fact consumers before changing shapes.

## 5. Architecture Fit

Implements accepted ADR 0039 and conforms to ADR 0032's concept/adapter
separation plus ADR 0038 capability/support states. Tree-sitter is the syntax
baseline; ast-grep remains optional/on-demand; stable TypeScript Compiler API
is used only for named semantic consumers; SCIP/LSP remain unsupported until a
consumer justifies their lifecycle. A budget miss reopens ADR 0039. No accepted
smell or silent fallback.

## 6. Open Decisions

No unresolved P0 fork. D3 was accepted only after the pinned spike. Any tool or
budget substitution requires an ADR 0039 amendment, not an implementation
shortcut.

## 7. Promotion Notes

Promoted to `ai-docs/specs/portable-analysis-substrate.md`. Provenance is the
master plan's WP4 and AC-4.1–AC-4.6. Audited code roots are
`scripts/_lib/lang_adapter`, `scripts/analysis_portfolio_spike.py`, and
`tests/fixtures/analysis_portfolio_spike`. No acceptance wording was weakened
during transcription.
