---
id: portable-batch-sweep
title: "Portable batch sweep, stable manifests, and native shims"
status: draft
last_audited: 2026-07-16
motivating_decision: "0036"
code_roots:
  - scripts/sweep
  - scripts/sweep_shims.py
  - scripts/check_wp5_wp4_entry_gate.py
  - scripts/_lib/finding_identity.py
  - scripts/status.py
  - scripts/queue_status.py
  - .claude/docs/queue-contract.md
  - .claude/skills/_common/capability-registry.yml
  - .claude/skills/find-complexity-hotspots/scripts/detect.py
  - .claude/skills/find-complexity-hotspots/scripts/smoke.py
  - .claude/skills/find-omnibus/scripts/detect.py
  - .claude/skills/find-omnibus/SKILL.md
  - ai-docs/decisions/0036-batch-sweep-harness.md
  - ai-docs/decisions/0040-stable-finding-identity-v2.md
  - tests/fixtures/sweep
  - tests/test_sweep_slice0_characterization.py
  - tests/test_sweep_manifest.py
  - tests/test_sweep_native_shims.py
  - tests/test_wp5_wp4_entry_gate.py
  - tests/test_sweep_pipeline.py
  - tests/test_sweep_ecosystem_members.py
  - tests/test_finding_identity.py
  - tests/test_capability_consumers.py
  - tests/test_status.py
  - tests/test_queue_status.py
  - tests/test_render_status.py
  - tests/test_omnibus_language_adapters.py
  - .github/workflows/ci.yml
---

# Portable batch sweep, stable manifests, and native shims

## Provenance and authority

This is the dependency-sized executable successor specification for WP5 of
`ai-docs/plans/portable-skill-ecosystem-completion.md`. The master plan remains
the completion ledger and controls whenever this spec is ambiguous. ADR 0036
defines the pipeline, ADR 0038 the canonical capability/scan-target registry,
ADR 0039 the native-versus-parser portfolio, ADR 0040 finding identity v2, and
ADR 0037 the existing dashboard and packet-compatible queue seams.

The master tracker currently records WP1 and WP2 as `verified` and WP4 as
`in_progress`, not `verified`. Therefore Slices 0–4 below are dependency-ready;
Slice 5 is a hard gate. No parser-backed ecosystem battery member, associated
support promotion, or final WP5 verification may use WP4 merely because its
code exists. Slice 5 starts only after the master tracker says WP4 `verified`
and links fresh AC-4.1–AC-4.6 PASS evidence for the exact substrate revision.

This file does not promote or close the master plan. Implementation still
follows the master plan's tracker, evidence, dirty-state invalidation, and
fresh-context verification protocol.

## Controlling acceptance wording

The following wording is copied verbatim from the authoritative plan. It is
controlling; the detailed requirements below add executable precision and may
not narrow it.

- **AC-5.1:** The ADR 0036 prototype is promoted from `.claude/tasks/` to a
  supported `scripts/` package with CLI help, schema versioning, deterministic
  output order, stable IDs, unit/integration tests, and no dependency on
  prototype evidence paths at runtime.
- **AC-5.2:** Shims normalize Ruff, ESLint plus TypeScript compiler diagnostics,
  Clippy, Go vet/staticcheck (ADR-selected portfolio), and ecosystem detectors
  into the shared manifest while retaining native rule IDs, locations,
  severity, tool versions, and raw-output provenance.
- **AC-5.3:** Missing binaries, nonzero tool exits, parse failures, timeouts,
  truncated output, and schema mismatches fail loudly and distinguish tool
  failure from a clean zero-finding result. Fault-injection tests cover each.
- **AC-5.4:** `scan`, `digest`, `diff`, and `ratchet` commands reproduce ADR
  0036 semantics using D5's canonical identity rules: fixed/new/persisting sets
  are correct; deliberate accepts are auditable; improvement tightens rather
  than loosens the baseline. Adversarial/property tests cover multiple
  symbol-less instances of one native rule in one file, normalized/renamed
  paths, case behavior, hash collision handling, tool-version semantic
  changes, and manifest-schema migration without false deduplication.
- **AC-5.5:** Agents consume bounded digests and finding IDs, not raw full-repo
  findings. The harness, not the executor, performs the post-change rescan and
  rejects self-attested success without manifest evidence.
- **AC-5.6:** Python, TypeScript, Rust, Go, and mixed fixtures run through the
  final manifest/diff boundary in CI. ADR 0036 `embodied_by` points to the
  productized paths and contains no productization-pending reference.
- **AC-5.7:** Detection performs no model or network calls. Every finding that
  can enter ranking, a dashboard, a planner packet, or a fix has a recorded
  judgment outcome; judge failure/uncertainty blocks execution; raw counts
  cannot directly drive ranking, dashboards, or fixes. Planner packets contain
  finding IDs, bounded scope, recipe, verification command, expected manifest
  delta, and a bounded budget. Bypass and judge-failure integration tests prove
  each gate, and network/model-call instrumentation proves the detection stage
  is agent-free.

## Goals

- Replace the prototype with a registry-driven, agent-free package whose completed empty scan differs from failure; normalize native tools and, after WP4 verification, ecosystem detectors.
- Make identity, migration, diff, digest, ratchet, judgment, packets, and harness-owned verification deterministic and testable.
- Prove the final boundary on all five host fixtures and migrate status/queue consumers so no dashboard, packet, or execution path bypasses judgment or consumes raw findings.

## Architecture and boundaries

### Product boundary

`scripts/sweep/` owns the public library and
`.venv/bin/python -m scripts.sweep` CLI. It has one manifest model/writer, one
provider execution contract, and command services for `scan`, `digest`,
`diff`, `ratchet`, judgment import, packet creation, and packet verification.
The package may be split into modules once the interfaces are exercised; it
must not create a second registry or identity function.

`scripts/sweep_shims.py` remains a thin compatibility/resolution facade over
ADR 0038's registry or is retired after every import and command call site is
migrated. It never owns language, tool, support, or provider enums.
`scripts/manifest.py` remains the distinct skill-activation manifest CLI; it
must not become a sweep-manifest writer merely because the filenames overlap.

The productized runtime must not import, execute, discover relative to, or read
`.claude/tasks/sweep-prototype/`. That directory remains historical evidence.
Before replacement, the eligible prototype behavior is captured into ordinary
test fixtures; no test or production default points back to the prototype.

### Pipeline

```text
validated host/sweep profile + declared scope
  -> registry-selected provider preflight
  -> isolated native/parser detector execution (agent-free)
  -> validated provider observations + raw-output hashes
  -> single manifest writer + finding identity v2
  -> raw manifest
  -> bounded judgment input -> validated run-local judgments
  -> judged digest / dashboard projection / planner packet
  -> executor changes declared scope only
  -> harness runs verification command, rescans, diffs, and ratchets
```

Detection ends at the raw manifest and has no model/network dependency. A
separate judge may be model-backed, but it receives bounded data and writes a
validated outcome keyed by finding ID. Only a judgment-specific bounded view
may contain pending findings; ordinary digests, rankings, dashboards, packets,
and execution reject missing, uncertain, or failed outcomes.

### Manifest contract and stable invariants

The first productized sweep manifest is `schema_version: 1` and embeds
`finding_id_schema: 2` plus the capability-registry version. Writers emit only
the newest schema. During one documented migration window, readers may accept
the unversioned prototype fixture and schema 1; every other version fails.
The manifest records:

- repository-relative POSIX scope, explicit case policy, canonical roots and
  exclusions, source revision/dirty-state evidence, and completion state;
- every selected provider, subject language, provider kind, command contract,
  tool version, exit classification, raw stdout/stderr artifact hashes, and
  complete/failed status;
- findings with `id`, the full ADR 0040 identity payload, `legacy_ids`, native
  rule ID, canonical rule semantic key, native and normalized severity,
  repository-relative location, message/summary, metrics, and raw provenance;
- deterministic counts derived from validated findings, never supplied by a
  provider as an independent source of truth; and
- canonical semantic and artifact hashes so consumers can bind judgments,
  packets, baselines, and evidence to the exact manifest.

Canonical ordering is provider, language, canonical rule semantic key, path,
semantic anchor, occurrence, then finding ID. Object serialization uses sorted
keys and a terminal newline. Volatile run time and machine fields are retained
as provenance but excluded from the semantic hash. A successful zero-finding
manifest requires every declared provider to complete over the declared scope;
the presence of any provider error makes the run failed and prevents publishing
the success manifest or tightening a baseline.

Identity is exactly ADR 0040's canonical payload and `f2_` 96-bit public ID.
The writer rejects duplicate IDs with unequal payloads. Equal anonymous anchors
receive deterministic zero-based occurrences after stable source-order sorting.
Tool-version-only changes preserve identity. A real rule-semantics change must
bump the canonical rule semantic key while retaining the native rule ID, so it
appears as fixed plus new instead of false persistence.

Path moves change v2 identity. A declared, one-release `legacy_ids` alias may
join old to new only when the mapping is unique and one-to-one; ambiguous,
cyclic, duplicate, or cross-payload aliases fail. Case behavior comes from an
explicit sweep/host profile field and is recorded in the manifest; the runner
never infers it from the machine executing the scan.

### Failure and subprocess contract

Every provider declares executable discovery, argv, timeout, output format,
diagnostic-complete exit classification, version probe, and raw-output byte
ceiling. Native tools whose documented diagnostic exit differs from zero are
classified only after complete schema-valid output is present; every
unrecognized nonzero exit is a tool failure. The runner captures complete
stdout/stderr to temporary files, validates them, hashes them, then atomically
publishes artifacts. A timeout kills the process group. A missing executable,
unexpected exit, malformed/truncated payload, output over the declared bound,
missing completion sentinel, or schema mismatch produces a typed failure and
nonzero sweep exit; no prefix is parsed as a clean result.

The ADR 0039-selected Go member for this spec is `go vet`; staticcheck is not a
second mandatory implementation unless the canonical registry/ADR portfolio is
amended before its slice. Ruff, ESLint, TypeScript compiler diagnostics,
Clippy, and Go vet each retain their native rule/code, location, severity,
version, and raw-output hash. Saved-output unit fixtures do not replace the
live final-boundary CI run.

### Judgment, packet, and AC-8.9 seam

Run-local judgment outcomes use the stable finding ID and exact manifest hash.
The minimum outcome vocabulary is `actionable`, `not_actionable`, `uncertain`,
and `failed`, with reason, judge identity/version, and evidence reference.
Only `actionable` findings may enter a ranked digest or planner packet;
`not_actionable` remains auditable but is excluded; any selected `uncertain`,
`failed`, missing, stale-manifest, or unknown-ID outcome blocks packet creation
and execution.

A sweep-originated packet is schema-versioned and contains nonempty
`finding_ids`, sorted repository-relative `scope`, a self-contained `recipe`,
`verification`, structured `expected_delta`, positive `token_budget`, source
manifest hash, and judgment hash. Its budget ceiling is deterministic:
`min(100000, max(8000, 8000 + ceil(scope_bytes / 4)))`; the requested budget
must not exceed it. `scripts/queue_status.py` may continue to list legacy queue
items, but newly generated sweep packets use this contract and the executor
rejects hand-authored bypasses.

The executor cannot set a verified outcome. The harness runs the packet's
verification command, performs the post-change scan itself, checks the
structured expected delta, rejects out-of-scope edits and new findings, and
only then emits verification evidence. Deliberate ratchet accepts require the
exact finding ID, reason, operator, revision, and timestamp; stale/unknown
accepts fail, and an accepted increase is visible in the rewritten baseline.

WP5 deliberately does not accept, reject, supersede, or mark ADR 0003 embodied.
Its judgments and packets are run-local artifacts with stable-ID extension
points, not the canonical cross-skill outcome ledger. Cross-skill path queries
and finding -> judgment -> packet -> fix/commit -> verification lifecycle
linkage remain exclusively AC-8.9 work, after AC-8.8 and the binding ADR order.
WP5 verification must assert ADR 0003 still points to AC-8.9.

## Characterization oracles

- [ ] AR-1: Capture one deterministic prototype fixture before replacement:
  candidate families, bounded top-N digest, fixed/new/persisting set arithmetic,
  ratchet growth/fix behavior, improvement tightening, and explicit accept.
- [ ] AR-2: Mark prototype SHA1 identity, hard-coded ecosystem paths, silent
  detector/JSON failures, raw-count consumption, and executor-adjacent
  verification as defects to reverse, not compatibility behavior.
- [ ] AR-3: Preserve ADR 0040 line/tool-version stability, anonymous
  multiplicity, provider/language namespace, explicit case, path escape,
  rename/legacy-alias, and collision-rejection oracles.
- [ ] AR-4: Preserve registry-driven resolution in `sweep_shims.py` and prove
  no local stack/tool/support enum or activation-manifest coupling appears.
- [ ] AR-5: Preserve the Python complexity and omnibus good/bad/cohesive/skip
  behavior through adapter wiring; parser failures become loud instead of
  `None`, skipped rows, or successful zero.
- [ ] AR-6: Preserve status projection read-only behavior and queue
  hook/list compatibility while proving structural-health/dashboard data and
  new sweep packets are judgment-gated.
- [ ] AR-7: Pin the activation manifest and sweep manifest as separate schemas,
  writers, paths, and commands; one cannot validate or overwrite the other.
- [ ] AR-8: Pin a clean-zero oracle for every host fixture and a failed-scan
  oracle with identical empty findings; only the completed scan is clean.
- [ ] AR-9: Pin exact native provider outputs, version probes, rule/location/
  severity preservation, path normalization, and raw stdout/stderr hashes.
- [ ] AR-10: Pin agent-free detection by denying socket/DNS/HTTP and model
  facade calls while all native and ecosystem detection fixtures still pass.
- [ ] AR-11: Pin harness ownership: an executor success claim without a new
  harness-produced manifest/diff is rejected even when its verification text
  says PASS.
- [ ] AR-12: Pin predecessor order: ADR 0036/0040 embodiment may change in WP5;
  ADR 0003 status/embodiment and AC-8.9 ownership may not.

## Dependency-ordered implementation

### Slice 0 — freeze executable oracles (WP1/WP2 ready)

- [x] IM-1: Add `tests/fixtures/sweep/prototype-oracle/` and the AR-1–AR-12
  characterization tests before product code. The fixture is copied evidence,
  not a runtime import from `.claude/tasks/`. <!-- spec:portable-batch-sweep::IM-1 -->
- [x] IM-2: Define manifest, provider observation, diff, judgment, packet, and
  typed-failure schemas plus deterministic JSON/hash helpers in
  `scripts/sweep/`; validate adversarial bad fixtures before accepting good
  ones. <!-- spec:portable-batch-sweep::IM-2 -->

### Slice 1 — manifest core and identity migration (WP1/WP2 ready)

- [x] IM-3: Implement the single manifest writer on ADR 0040 identity v2,
  deterministic anonymous occurrence assignment, collision rejection,
  explicit case policy, semantic-rule versioning, schema-1 write path, and
  prototype legacy aliases. <!-- spec:portable-batch-sweep::IM-3 -->
- [x] IM-4: Implement read-old/write-new migration and property tests for
  fixed/new/persisting correctness across normalized/renamed paths, ambiguous
  aliases, case modes, tool upgrades, semantic rule changes, digest collisions,
  and manifest versions without false deduplication.
  <!-- spec:portable-batch-sweep::IM-4 -->

### Slice 2 — native provider execution (WP1/WP2 ready)

- [x] IM-5: Make `sweep_shims.py` resolve providers from the canonical registry
  and implement Ruff, ESLint, TypeScript compiler-diagnostic, Clippy, and Go vet
  adapters through the shared execution contract. <!-- spec:portable-batch-sweep::IM-5 -->
- [x] IM-6: Add saved raw-output fixtures and live minimal projects for each
  provider; retain native IDs/locations/severity/versions/provenance and inject
  missing binary, unexpected exit, parse failure, timeout, truncation, output
  overflow/corruption, and schema mismatch. <!-- spec:portable-batch-sweep::IM-6 -->

### Slice 3 — public commands, digest, diff, and ratchet (WP1/WP2 ready)

- [x] IM-7: Implement CLI help and `scan`, `digest`, `diff`, and `ratchet` with
  deterministic ordering, typed exit codes, atomic output, 64-KiB/50-finding
  digest bounds, correct sets/metrics, auditable accepts, and automatic
  tighten-on-improvement that never runs after a partial scan.
  <!-- spec:portable-batch-sweep::IM-7 -->
- [x] IM-8: Prove the library and CLI produce the same canonical artifacts and
  that no runtime path depends on prototype evidence, current working directory,
  an activated shell, or machine-local tool lookup order.
  <!-- spec:portable-batch-sweep::IM-8 -->

### Slice 4 — judgment, consumers, packets, and harness (WP1/WP2 ready)

- [ ] IM-9: Implement bounded judgment input/import and gate every ordinary
  digest, rank, dashboard projection, packet, and execution path on fresh
  recorded outcomes. Instrument detection to fail tests on any network/model
  call. <!-- spec:portable-batch-sweep::IM-9 -->
- [ ] IM-10: Migrate `status.py`, `queue_status.py`, and the queue contract:
  status reads only judged digest fields; new sweep packets contain all AC-5.7
  fields and pass deterministic bounds; legacy queue listing remains readable.
  <!-- spec:portable-batch-sweep::IM-10 -->
- [ ] IM-11: Implement harness-owned packet verification: validate packet and
  scope, run the verification command, rescan independently, diff against the
  bound manifest, enforce expected delta/no-new/out-of-scope rules, and reject
  executor self-attestation or stale evidence. <!-- spec:portable-batch-sweep::IM-11 -->

### Slice 5 — parser-backed ecosystem members (blocked until WP4 verified)

- [x] IM-12: Gate entry by inspecting the master tracker and WP4 final
  verification. Record the exact verified substrate revision and rerun the
  analysis fact, adapter, failure, deterministic-golden, and budget contracts;
  stop if any AC-4.1–AC-4.6 evidence is absent/stale.
  <!-- spec:portable-batch-sweep::IM-12 -->
- [ ] IM-13: Only after IM-12, wire the characterized complexity-hotspot and
  omnibus detectors through the provider observation contract, replace
  prototype inline parser ownership where facts support it, and return typed
  provider failures rather than clean zero. Do not invent facts outside the
  verified WP4 interface. <!-- spec:portable-batch-sweep::IM-13 -->
- [ ] IM-14: Add parser-backed Python and TypeScript observations to single and
  mixed fixture manifests without weakening native Rust/Go shims or claiming
  parser-backed Rust/Go detector support. <!-- spec:portable-batch-sweep::IM-14 -->

### Slice 6 — final CI boundary and decision embodiment

- [ ] IM-15: Run Python, TypeScript, Rust, Go, and mixed before/after fixtures
  through live tools, manifest writing, judged digest/packet gates, harness
  rescan, diff, and ratchet in CI; assert exact fixed/new/persisting IDs and
  clean-zero/failure distinction. <!-- spec:portable-batch-sweep::IM-15 -->
- [ ] IM-16: Update ADR 0036 and ADR 0040 `applies_to`/`embodied_by` to only
  accurate productized script/contract paths, remove productization-pending
  references, and assert ADR 0003 remains proposed with AC-8.9 ownership.
  <!-- spec:portable-batch-sweep::IM-16 -->

## Fixture and attack matrix

`tests/fixtures/sweep/` contains authored source fixtures, checked-in lockfiles
or version contracts, saved native outputs, schema attacks, and exact oracles:

| Fixture | Required providers | Final oracle |
|---|---|---|
| `hosts/python/{before,after,clean}` | Ruff; parser members after IM-12 | one fixed, no new, stable persisting IDs; clean completed zero |
| `hosts/typescript/{before,after,clean}` | ESLint + compiler diagnostics; omnibus after IM-12 | native IDs retained; exported ESM/TS declarations reach manifest/diff |
| `hosts/rust/{before,after,clean}` | Clippy | warning finding fixed; tool failure never appears clean |
| `hosts/go/{before,after,clean}` | Go vet | vet finding fixed; tool failure never appears clean |
| `hosts/mixed/{before,after,clean}` | all native providers plus eligible ecosystem members | per-root composition; no cross-language/provider ID collision |
| `raw/<provider>/` | saved valid, empty, malformed, truncated, oversized, unexpected-exit envelopes | typed completion or exact loud failure |
| `schema/` | prototype, v1, future-version, duplicate-ID, alias-cycle/ambiguity, corrupt judgment/packet | only allowed migration succeeds |
| `attacks/` | line drift, duplicate anonymous anchors, case variants, path escape/move, semantic-rule bump, fake executor PASS | identity and harness gates hold |

The before/after roots use identical repository-relative paths so diffs test
content change rather than fixture-directory identity. Mixed-host oracles name
the exact selected roots, providers, findings, judgment outcomes, packet scope,
and expected delta. Good and near-miss cases are predeclared before provider or
detector tuning.

## Evidence and verification protocol

Each completed slice writes a durable record under
`reports/portable-skill-ecosystem-completion/WP5/` naming the ACs advanced,
revision, dirty files, platform/architecture, Python/native tool versions,
fixture and oracle hashes, command and exit status, generated artifact hashes,
current action, and last completed AC. Dirty-state evidence includes a hash for
every dirty file and a full patch; any content change invalidates it. Final
verification uses a clean committed revision and a fresh-context read-only
verifier with one PASS/FAIL row for AC-5.1–AC-5.7.

The verifier inspects artifacts, reruns deterministic commands, compares
manifest/diff content, faults every failure class, and confirms no unsupported
promotion. IM-12 records the linked WP4 verifier,
revision, platform/tool matrix, and evidence hashes. IM-16 records the ADR
ordering inspection separately from implementation success.

### Exact focused commands

Run from the repository root with the checked-in environment/tool versions:

```bash
.venv/bin/python -m pytest -q \
  tests/test_finding_identity.py \
  tests/test_capability_consumers.py \
  tests/test_sweep_manifest.py \
  tests/test_sweep_native_shims.py \
  tests/test_sweep_pipeline.py \
  tests/test_status.py \
  tests/test_queue_status.py

.venv/bin/python -m scripts.sweep --help
.venv/bin/python -m scripts.sweep scan \
  --root tests/fixtures/sweep/hosts/mixed/before \
  --profile tests/fixtures/sweep/profiles/mixed-case-sensitive.json \
  --out /tmp/wp5-mixed-before.json
.venv/bin/python -m scripts.sweep scan \
  --root tests/fixtures/sweep/hosts/mixed/after \
  --profile tests/fixtures/sweep/profiles/mixed-case-sensitive.json \
  --out /tmp/wp5-mixed-after.json
.venv/bin/python -m scripts.sweep diff \
  /tmp/wp5-mixed-before.json /tmp/wp5-mixed-after.json \
  --out /tmp/wp5-mixed-diff.json
.venv/bin/python -m scripts.sweep digest \
  --manifest /tmp/wp5-mixed-after.json \
  --judgments tests/fixtures/sweep/judgments/mixed-after.json \
  --purpose dashboard --top 50 --out /tmp/wp5-mixed-digest.json

.venv/bin/python -m pytest -q \
  tests/test_analysis_facts.py \
  tests/test_lang_adapter.py \
  tests/test_omnibus_language_adapters.py \
  tests/test_sweep_ecosystem_members.py
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/smoke.py
```

The parser-backed block is forbidden before IM-12 passes. The live native-tool
matrix is explicit and must not be replaced by saved outputs:

```bash
.venv/bin/python -m pytest -q -m sweep_live tests/test_sweep_pipeline.py
.venv/bin/python -m pytest -q tests/test_render_status.py
.venv/bin/ruff check \
  scripts/sweep scripts/sweep_shims.py scripts/_lib/finding_identity.py \
  scripts/status.py scripts/queue_status.py \
  tests/test_sweep_manifest.py tests/test_sweep_native_shims.py \
  tests/test_sweep_pipeline.py tests/test_sweep_ecosystem_members.py
.venv/bin/python scripts/check_capability_registry_consumers.py
.venv/bin/python scripts/skill_meta.py lint
.venv/bin/python scripts/decisions.py audit
.venv/bin/python scripts/decisions.py link-check
.venv/bin/python scripts/plans.py audit
.venv/bin/python scripts/specs.py coverage portable-batch-sweep
.venv/bin/python scripts/specs.py inventory-check portable-batch-sweep --strict
.venv/bin/python scripts/specs.py audit
.venv/bin/python -m pytest -q
```

CI must record the invoked Ruff, Node/npm, ESLint, TypeScript, Rust/Cargo/
Clippy, Go, and Go-vet versions. A skipped/missing live provider, browser, or
parser job cannot prove AC-5.6 or AC-5.7.

## Exceptions and explicit deferrals

- Parser-backed ecosystem battery members are deferred only until WP4 is
  independently `verified`; native shims, manifest/identity, commands,
  judgment, packet, and harness work are not blocked by WP4.
- Rust and Go parser-backed refactoring/non-native structural detectors remain
  outside WP5. Their verified completion floor here is native sweep, loud
  failure, stable mixed-host identity, and final manifest/diff composition.
- Staticcheck is optional under the currently accepted ADR 0039 portfolio;
  `go vet` is mandatory. Adding staticcheck requires canonical registry/version
  evidence and the same normalization/fault suite, not a local enum or claim.
- The status projection remains derived/read-only, and the queue remains
  agent-neutral. WP5 changes their sweep inputs/contracts only; it does not
  redesign status presentation or queue lifecycle.
- ADR 0003 formal disposition, canonical cross-run outcome storage, cross-skill
  path queries, and commit linkage remain deferred to AC-8.9 in the binding
  order. A WP5 implementation of those features is a scope/order violation.

## Learnings

### User-facing

_(Append only after executable implementation evidence exists.)_

### Technical

_(Append only after executable implementation evidence exists.)_

---

## Known symbol inventory

No declared Python code root is expected to exceed the inventory threshold;
the AR/IM checklist, exact roots, and audit markers maintain the inventory.
