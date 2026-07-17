---
id: "0036"
namespace: core
title: Detection is batched into stable-id manifests; agents plan, judge, and converge over digests and diffs
status: accepted
date: 2026-06-11
deciders: [khurrum, claude-code]
provenance: "Dogfooded before being decided: prototype proven end-to-end on a foreign Python repo (full loop), precision-measured on an external 667k-LOC TypeScript corpus, calibration-tested on a disciplined Rust codebase. The design draft preceded the prior research notes; convergent elements were merged after."
assumes: ["the dominant compute cost of skill-driven cleanup is the agent sitting in the loop for deterministic work (reading skill prose, orchestrating scans, re-reading raw findings and code), and context compaction is caused by raw volume flowing through the orchestrator"]
revisit_when:
  - "a provider adapter shows the manifest schema cannot preserve required native semantics"
  - "judge-stage precision measured on a new corpus drops materially below the Atlas datum"
supersedes: []
superseded_by: null
applies_to:
  - scripts/sweep/
  - scripts/sweep_shims.py
  - scripts/status.py
  - scripts/queue_status.py
embodied_by:
  - "script:scripts/sweep/__main__.py"
  - "script:scripts/sweep/commands.py"
  - "script:scripts/sweep/manifest.py"
  - "script:scripts/sweep/pipeline.py"
  - "script:scripts/sweep_shims.py"
  - "script:scripts/status.py"
  - "script:scripts/queue_status.py"
  - "contract:tests/test_sweep_cli.py"
  - "contract:tests/test_sweep_manifest.py"
  - "contract:tests/test_sweep_pipeline.py"
  - "contract:tests/test_sweep_live_pipeline.py"
tags: [sweep, manifest, batch, compute, convergence, ratchet, guard, detection]
related_smell: null
related_pattern: null
---

# Detection is batched into stable-id manifests; agents plan, judge, and converge over digests and diffs

## Context

Using the skills to improve a vibe-coded host was measured-slow: each
detector run loaded skill prose into an agent, fanned out scouts, wrote
reports the orchestrator read back raw, and fixes proceeded
finding-by-finding — re-reading the same files repeatedly and driving the
context window into compaction. The root cause: **the agent sat in the loop
for work that does not need an agent**, with no compression between stages
and no machine-comparable before/after state.

The design was prototyped and dogfooded before this ADR was written:

- **Hermes (throughput):** 760-finding baseline over ~280k LOC in 8s and 0
  tokens; one Haiku executor packet (35k tokens) fixed a 30-branch dispatch
  chain; the manifest diff proved convergence by set arithmetic (2 fixed,
  0 new, 706 persisting).
- **Atlas (precision, external ground truth):** 43 omnibus candidates
  judged by 4 parallel Haiku judges against team-acknowledged debt — raw
  precision 30%, precision@5 100%, precision@10 80%, recall 7/9.
- **Daedalus (calibration):** the same raw signals on a disciplined
  codebase are mostly correct code; the judgment layer correctly disarms
  them. Raw counts are not debt.

## Decision

Six commitments, in pipeline order:

**1. Detection runs agent-free.** A battery of detector scripts (ecosystem
detectors + native-tooling shims like ruff/eslint/clippy) executes as one
batch process emitting a single **manifest**: normalized findings, severity,
per-rule counts. Zero tokens. SUSPECT skills remain the judgment/triage
wrappers; their scripts are the battery members.

**2. Finding identity is stable.** The prototype used
`hash(rule | path | symbol)`; the productized harness uses ADR 0040 identity
schema v2: provider, canonical rule semantic key, subject language,
repository-relative path, semantic anchor, and deterministic occurrence.
Line/column, severity, volatile metrics, messages, and tool versions remain
outside identity, so manifests diff cleanly into `fixed / new / persisting`.
This id is the unit of run-local outcome telemetry and attestation; canonical
cross-skill outcome linkage remains ADR 0003 / AC-8.9 work.

**3. Agents read digests, never raw findings.** The orchestrator/planner
consumes counts + top-N; full findings stay on disk addressable by id. The
planner emits **packets** (scope file list, recipe, verification command,
expected delta, token budget computed from manifest file sizes) clustered by
fix shape, locality, and independence; execution is tiered to the cheapest
model that can hold the recipe.

**4. Verification belongs to the harness, never the executor.** Executors
report; the harness re-scans the touched scope and diffs manifests. (The
Hermes executor fixed the code perfectly and still misreported its own
verification step — the deterministic-oracle thesis, observed live.)

**5. A judgment stage is mandatory between detection and ranking/fixing.**
Cheap-model judges apply the facet-vs-domain rule per finding family before
anything is ranked for humans or routed to executors. Grounds: the
Atlas precision curve and the Daedalus false-positive profile.
Raw manifest counts must never drive fixes or dashboards directly.

**6. The GUARD baseline and the sweep manifest are the same artifact.** The
**structural ratchet** (`sweep ratchet`) fails on new finding ids or grown
ratchet metrics (loc / clusters / counts) on persisting findings,
auto-tightens the baseline on improvement, and records deliberate increases
via `--accept <finding-id>` — an independent, MIT-compatible generalization
of the eslint-seatbelt mechanics from lint rules to structure. Under
agents, a baseline inverts from amnesty into a work queue: draining it IS
the batch sweep.

## Alternatives considered

- **Keep skills as agent-executed prose with an adherence harness.**
  Subsumed: adherence machinery (external completeness ledgers,
  declared-evidence checks) remains right for the *executor* tier, but
  removing the agent from detection entirely makes adherence moot for the
  scanning tier and saves the bulk of the compute.
- **Sum native linters only (no ecosystem detectors).** Rejected: native
  tooling misses the structural/integral smells (omnibus, semantic
  duplication) that are the toolkit's distinct value; shims and ecosystem
  detectors share one manifest schema instead.
- **Rank by raw finding counts.** Rejected with data: rewards the noisiest
  detector (the effectiveness audit's complaint) and inverts on disciplined
  codebases.
- **Hard structural gates instead of a ratchet.** Rejected: unworkable
  retroactively (Atlas could never adopt a 500-line cap); the ratchet
  holds the line wherever it currently is and only moves one way.

## Consequences

- **Easier:** a full-repo sweep costs seconds and zero tokens at the
  detection tier; an end-to-end fix loop ran at ~80k tokens (~85% Haiku)
  versus the ~1M-token frontier-heavy shape it replaces; the orchestrator
  context holds plans, digests, and diffs — never code — which removes the
  compaction spiral.
- **Easier:** adapting to a new language starts with a shim (native linter
  JSON → manifest) instead of porting detectors; the manifest schema is the
  portable core (ADR 0032 taken to its conclusion).
- **Easier:** convergence (`/converge`) gains objective evidence — the
  manifest diff — for its `demonstrated` node; outcome telemetry falls out
  of id set arithmetic.
- **Harder:** detectors must emit machine-parseable output with stable
  identity inputs; battery members must fail loudly (a silent zero from a
  misconfigured shim was observed and is the known failure mode).
- **Harder / honest limit:** the judge stage is itself a model under noise;
  its precision is measured (one corpus, one detector family) not proven
  generally — hence the revisit trigger.
- **Disallowed:** orchestrators reading raw finding lists or unchanged code;
  executor self-reported verification accepted as evidence; ranking or
  fixing from unjudged manifest counts.

## Verification

<!-- spec:portable-batch-sweep::IM-16 -->

- The productized CLI and library live under `scripts/sweep/`, with registry
  resolution retained in `scripts/sweep_shims.py`. Manifest, CLI, judgment,
  packet, harness, and ratchet contracts are exercised by
  `tests/test_sweep_manifest.py`, `tests/test_sweep_cli.py`, and
  `tests/test_sweep_pipeline.py`; judged-only status and queue consumption are
  covered by `tests/test_status.py` and `tests/test_queue_status.py`.
- `.github/workflows/ci.yml` runs the native and integrated live boundaries
  with `SWEEP_LIVE_REQUIRED=1`, so an unavailable provider cannot become a
  skipped success. `tests/test_sweep_live_pipeline.py` carries the exact
  Python, TypeScript, Rust, Go, and mixed-host manifest/diff/ratchet oracles.
- `.claude/tasks/sweep-prototype/` remains historical dogfood evidence only.
  Productized runtime and test defaults do not import or resolve through it.
