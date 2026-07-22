# Productization archive value map

Archive branch: `archive/productization-platform-2026-07-18`

Archive revision: `95e2aec31cec0c43ca94eff5a460f687589448b3`

Restart branch: `codex/productization-restart` from `ad685e3`

Purpose: preserve a capability-level map of the archived experiment so useful
work can be evaluated later without merging the archive or putting it back on
the ordinary installer critical path.

## Recovery rule

The archive is read-only evidence and an experimental component library. Do
not merge it wholesale. A slice may return only when a current user journey
requires it, its production files are identified explicitly, and it is
revalidated on the restart branch without importing its historical planning or
receipt machinery by default.

## Capability inventory

| Slice | What is genuinely valuable | Maturity in archive | Explore when | Anchors |
|---|---|---|---|---|
| Multi-language analysis facts | Shared Python, JavaScript/TypeScript, Rust, and Go fact adapters plus small golden fixtures. This is the most directly reusable work for cross-language support. | Implemented and heavily tested, but not proven through an installed skill journey. | Milestone 2 begins and the first family needs common source facts. Extract code/fixtures, not reports. | `e30fcb4`; `scripts/_lib/lang_adapter/`; `tests/test_analysis_facts.py` |
| Host profiles and binding selection | Separates host facts and framework bindings from core skill logic. Useful for avoiding Django assumptions in generalized skills. | Implemented with tests; abstraction breadth may exceed the first family. | A second real family demonstrates the same host/binding seam as the first. | `38f9c6c` through `96ff0d8`; `7ef8df1` through `d38cc2d`; `scripts/_lib/{host_profile,binding_loader}.py` |
| `extract-enum` Python/Django exemplar | Concrete example of framework-neutral core plus language/framework bindings and native guard generation. | Substantive implementation with fixtures; TypeScript path is absent. | Use as the first cross-language family candidate after installation closes. | `7ef8df1`; `.claude/skills/extract-enum/`; `tests/test_extract_enum_binding.py` |
| Batch sweep pipeline | Deterministic multi-language scan pipeline, provider adapters, schemas, process isolation, and Python/TS/Rust/Go/mixed fixtures. | Broad and extensively tested; large, and not yet justified by a measured user workflow. | Milestone 3 measurements show repeated parsing/scanning dominates real cleanup work. | `1f5c9e0` through `8834b5a`; `scripts/sweep/`; `tests/fixtures/sweep/` |
| Dependency-closure analyzer | Finds repository-level imports, references, dynamic loads, and missing packaged dependencies. It identified exactly the class now blocking installed routers. | Strong adversarial test corpus; implementation is large and tuned to a richer package model. | Simple per-skill self-containment checks miss real dynamic/reference dependencies, or publication needs an automated closure audit. | `1bdfbfa` through `209ef25`; `scripts/_lib/catalog_closure.py`; `tests/test_i2_catalog_closure_scaffold.py` |
| Capability vocabulary and five-surface projections | Honest vocabulary for verified, experimental, unsupported, and unavailable surface capabilities; deterministic structural projections. | Structurally rigorous; native execution is incomplete and projections are not user journeys. | Native marketplace/plugin support becomes an explicit user requirement beyond the standard Agent Skills source. | `3531214`; `48a6cff`; `d1fa609`; `.claude/skills/_common/capability-registry.yml` |
| Content-bound bundle/release engine | Exact source-to-release byte binding, inventories, digests, and offline trust bundles. | High test rigor; no ordinary user need established. | A regulated/offline/untrusted distribution customer requires reproducible attestable packages. | `1fcf255`; `48a6cff`; `d1fa609`; `scripts/_lib/skill_bundle.py` |
| Transactional lifecycle and recovery | Install/update/remove transaction model, rollback, crash recovery, migration authority, and host-preservation checks. | Substantial implementation with failure-injection tests; not exposed through a usable public journey. | Standard package-manager semantics are demonstrably insufficient for a high-stakes host and the customer accepts a managed runtime. | `e292610` through `f7dd6ae`; `scripts/_lib/skill_installer.py`; `tests/test_skill_installer_lifecycle.py` |
| Deterministic dispatch runtime | Router result contracts, continuation state, protected launchers, and failure isolation. | Core mechanics implemented; production launcher registry intentionally incomplete. | A separate runtime must execute selected skills across controlled workers rather than handing off to the host agent. | `431c280`; `aebe78f` through `b296cbc`; `scripts/_lib/skill_{dispatch,dispatch_runtime}.py` |
| Gemini native discovery adapter | Version-pinned native discovery integration and capability reporting. | Verified bounded slice for one external surface. | Gemini-native distribution becomes a supported product surface. | `c2071cd`; `7b7f18c`; `scripts/_lib/native_discovery.py` |
| Skill expectation/oracle engine | Structured expectations, outcome/adherence distinction, evidence contracts, and adversarial oracle fixtures. | Mechanically rigorous, but built before representative installed journeys and therefore uncalibrated as a product. | At least one installed skill journey has a frozen task/outcome and needs repeatable quality evaluation or SkillOpt-style experiments. | `24ef189` through `1064745`; `scripts/_lib/skill_expectations.py`; `.claude/contracts/skill-expectations/` |
| Productization state/evidence control plane | Revision-bound state, receipts, phase gates, independent attestations, and dirty-tree preservation. | Highly developed governance machinery; it validated itself rather than the public product path. | As research into auditable autonomous program execution, not as a prerequisite for this repository's installer. | `43c2857` through `32cb351`; `scripts/_lib/portable_v1_state.py` |
| Adversarial fixtures and regression techniques | Red-before-green mutations, bypass probes, failure preservation, exact source-byte checks, and clean-worktree replay patterns. | Proven useful at finding defects in the mechanisms they target. | Any recovered slice needs a narrowly relevant regression test. Preserve the technique, not every historical receipt. | `tests/fixtures/i2/`; `tests/test_i2_*`; archived review reports |

## Product hypothesis

The accidental product is best framed as a **high-assurance skill supply-chain
and execution runtime**:

> Package an exact skill closure, project it honestly across agent surfaces,
> install or update it transactionally without corrupting host state, dispatch
> it through a capability-checked launcher, and produce auditable evidence that
> the declared bytes and execution obligations were honored.

That is a coherent product for a narrower, higher-stakes audience. It is not a
better default installer for a public Git repository. Its next step is customer
and threat-model discovery, not more implementation.

One boundary crosses back into the core product: **behavioral outcome
assurance**. Engineering skills should demonstrate that they produce the
declared analysis, change, guard, or advice on representative cases, and a
fixed composition should demonstrate its combined result. The optional product
starts at the stronger supply-chain and execution properties: exact-byte
identity, transactional lifecycle, controlled launchers, cross-surface
capability attestations, and auditable execution receipts.

The matching ledger entry is
`high-assurance-skill-distribution-runtime`, composed with
`skill-runtime-adherence-harness`, `skill-execution-planner`, and
`skill-run-state-resume`.
