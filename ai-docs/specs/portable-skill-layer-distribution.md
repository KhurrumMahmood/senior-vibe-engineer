---
id: portable-skill-layer-distribution
title: "Portable skill layers, bindings, discovery, and installation"
status: draft
last_audited: 2026-07-16
motivating_decision: "0042"
# Documentation and skill-body work remains checklist- and audit-marker-backed.
code_roots:
  - scripts/_lib/skill_catalog.py
  - scripts/_lib/binding_loader.py
  - scripts/installer_selection.py
  - scripts/distribution_probe.py
  - scripts/wp3_move_gate.py
  - scripts/lint/no_core_framework_leakage.py
  - scripts/skill_meta.py
  - scripts/_lib/skill_activation.py
  - scripts/_lib/distribution_contracts.py
  - scripts/_lib/distribution_legacy.py
  - scripts/_lib/skill_bundle.py
  - scripts/skill_bundle.py
  - scripts/_lib/skill_dispatch.py
  - scripts/_lib/portfolio_snapshots.py
  - scripts/manifest.py
  - .claude/skills/_common/distribution
  - tests/test_skill_catalog_layers.py
  - tests/test_binding_loader.py
  - tests/test_extract_enum_binding.py
  - tests/test_distribution_surfaces.py
  - tests/test_distribution_contract_schemas.py
  - tests/test_distribution_reference_tables.py
  - tests/test_skill_bundle.py
  - tests/test_skill_dispatch.py
  - tests/test_portfolio_snapshots.py
  - tests/test_wp3_move_gate.py
  - tests/test_core_framework_leakage.py
---

# Portable skill layers, bindings, discovery, and installation

## Provenance

This is the dependency-sized executable successor specification for WP3 and
AC-3.1–AC-3.7 of
`ai-docs/plans/portable-skill-ecosystem-completion.md`. The master plan remains
the completion ledger and controls if this spec is ambiguous. This spec adds
characterization oracles, implementation boundaries, sequencing, and evidence
interfaces without narrowing or substituting for any master criterion.

ADR 0034 supplies placement rules, ADR 0038 the canonical per-root host
profile, ADR 0041 the versioned surface matrix, and ADR 0042 the selected
projection/offline-bundle architecture. ADRs 0024 and 0028 remain **proposed**
and are safety-only inputs to the WP3-local move gate. WP3 neither changes
their status or `embodied_by` fields nor counts this use as W5 implementation
or formal disposition.

## Controlling acceptance criteria

The following text is preserved verbatim from the master plan.

- **AC-3.1:** A complete catalog inventory assigns every skill exactly one
  proposed validated layer, while this package migrates only the foundation
  and exemplar needed by WP6. Placement validation enforces ADR 0034's N=1
  allowance for shipping-contract layers, ≥3 threshold for domain cohesion
  folders, concept+binding default, and `/plan-skill` placement question. For
  the predecessor's incidentally coupled set—the plan-* chain,
  `refactor-subsystem`, `prevent-regression`, and every inventory sibling with
  the same shape—the universal procedure remains in core, Django-specific
  examples/defaults move to a declared binding or non-core appendix, and
  `language:`/`framework:` frontmatter is corrected to the validated honest
  values. A core-layer `SKILL.md` body may not name Django or Celery; that
  content may exist only in its declared file under `bindings/`.
  Compatibility/migration prose belongs in non-core documentation, not an
  inline exception. A diff-scoped lint and
  good/bad fixtures enforce both the content boundary and frontmatter truth.
  Full catalog rollout is gated by AC-8.7 after the TypeScript exemplar.
- **AC-3.2:** The selected discovery mechanism works in every supported agent
  surface in the versioned matrix from AC-1.6. Existing skill invocation names
  resolve unchanged or through tested aliases, and contracts/catalog links
  remain reference-clean.
- **AC-3.3:** A binding loader selects bindings from the canonical host profile,
  rejects ambiguous/incompatible bindings, and exposes the selected binding
  in execution evidence. Core procedure text is not duplicated into bindings.
- **AC-3.4:** `extract-enum` is split into a framework-neutral invariant and a
  Django binding. Before implementation, a pinned input/output baseline and
  allowed normalization rules define semantic equivalence. On the Django
  fixture the post-split result matches that oracle and existing tests pass.
- **AC-3.5:** A core-only install exposes zero Django/framework-native skills;
  a TypeScript portfolio exposes core + TypeScript + selected bindings; a
  Django portfolio preserves the current applicable catalog. Snapshot tests
  cover all three.
- **AC-3.6:** On clean fixture hosts, install, verify, update, and uninstall are
  idempotent and do not overwrite host-owned files. A newcomer reaches one
  useful verified skill run in 20 minutes or less using only documented steps
  and without reading the quality-coordination kernel document.
- **AC-3.7:** Before any WP3 foundation or exemplar commit moves/renames a
  tracked path, a WP3-local move gate applies ADR 0024 and ADR 0028 without
  waiting for the generalized WP7 tooling. Every retired concept phrasing is
  added to a distinctively scoped `avoid:` entry; both
  `superseded_co_occurrence` and `avoid_term_hit` are clean; affected prose is
  substantively corrected; and the evidence records the exact two-band
  commands/output. For every moving self-anchored path the proposal inventory,
  target pin, tractable rewrite/unhandled report, per-batch import smoke, and
  full-diff disk scan are complete and clean; the move-tool non-rewrite list is
  read, and any fired rule is captured in the running lessons log. A fixture
  move containing retired prose and a broken self-anchored path proves this
  gate blocks the commit. AC-7.1/AC-7.2 later generalize the same behavior; they
  are not permission to defer it from WP3. This is a safety-only application of
  existing ADR 0024/0028 rules to early moves: it neither changes either ADR's
  status/`embodied_by` nor counts as W5 implementation or formal disposition.

## Non-weakening interpretations

- AC-3.6's “verified skill run” means a locally verified execution artifact:
  the installed invocation is discovered, selected, run, and checked against a
  deterministic useful-output oracle. It does not promote the skill or surface
  to `verified` support state; ADR 0042 reserves that issuer-owned promotion for
  WP8.
- AC-3.5's TypeScript portfolio proves correct core + TypeScript + selected
  binding projection and selection. It does not claim the end-to-end
  TypeScript `extract-enum` behavior owned by WP6. An empty or mislabeled
  projection cannot pass merely because it contains no Django text.
- Structural projection checks are necessary but not sufficient for AC-3.2.
  Cursor and Augment runtime discovery at the versions pinned by AC-1.6 remain
  named completion risks. WP3 cannot replace unavailable tool-observed proof
  with file-existence, schema-only, or self-reported simulation evidence.
- The complete inventory is required in WP3, but only rows explicitly marked
  foundation-ready or exemplar-ready may be physically migrated. Deferred
  rows stay governed by AC-8.7 and cannot enter a portable portfolio through
  inferred legacy metadata.
- Canonical skill roots remain under flat `.claude/skills/` during WP3 unless
  actual discovery evidence first proves a move safe. Binding extraction does
  not itself require moving the canonical `extract-enum` root.
- Installation and ambient activation are separate contracts. The default
  install exposes only `which-shape` and `which-skill`; all other selected
  procedures remain content-addressed in a non-discovered catalog store and
  are loaded only after deterministic routing. `full-discovery` is an explicit
  compatibility mode. Substantial routed work uses a fresh no-context worker
  when available, with selected-only parent execution as the context/authority
  or no-sub-agent fallback.
- “Loaded only after deterministic routing” does not exclude ADR 0042's
  explicit named-activation path. The two paths are disjoint: routed execution
  reads selected content directly from the store without changing discovery;
  explicit activation changes the manifest-owned public discovery set and then
  preserves the surface's unchanged invocation form.
- `which-shape` remains a shape recommender and `which-skill` remains a skill
  ranker. Neither is silently redefined as an executor. The versioned
  dispatcher owns the exact-one selection, clarification, direct-work, error,
  pack, lane, and result decisions.
- The router-only count is the toolkit-owned discovery set. Host-owned
  instructions remain untouched and are recorded separately. Bootstrap
  headers that the surface injects outside a worker pack are not pack members
  but must be enumerated in context evidence.

## Architecture

The canonical catalog inventory joins each skill invocation to exactly one
proposed layer, declared binding compatibility, migration readiness, current
profile applicability, and placement rationale. It supplements rather than
duplicates the WP1 capability registry. All catalog, installer, projection,
and binding decisions consume this inventory; legacy language/framework
inference cannot make a deferred skill distribution-ready.

Binding selection is evaluated separately for each canonical host-profile
root. Precedence is `core → language → framework → domain → host`. Zero
required matches, incompatible explicit choices, and multiple candidates at
one precedence without an explicit profile choice fail closed. Registry or
directory order is never a tiebreaker. Selection evidence records profile,
core, binding, and rendered hashes and cannot cross root boundaries.

The installer consumes a checksummed offline bundle, stages into a temporary
root, validates every owned target, then atomically switches the toolkit-owned
manifest. Install, verify, update, and uninstall operate only on manifest-owned
paths. Host collisions, modified owned files, traversal, symlink escape,
corrupt manifests, duplicate targets, or failed validation stop without
overwriting or deleting host data.

Each supported surface receives a deterministic projection from the same
bundle inventory. A surface adapter separates projection validation from
runtime discovery evidence. Invocation names remain stable; aliases are
versioned manifest data and are accepted only with collision, cycle, and
stale-target checks. Projection has separate storage and activation views: the
storage view contains the selected portfolio outside automatic discovery; the
default activation view contains exactly the two routers. The router emits a
bounded dispatch record containing the selected canonical name, source and
rendered hashes, bindings, task-local inputs, execution lane (`fresh-worker` or
`selected-only-parent`), and result-artifact hash. No dispatch pack may contain
metadata or bodies for an unselected skill.

ADR 0042's surface table is normative. The bundle records the exact public
identity and generated path for each surface, including Codex's
`engineering-skills:` namespace. Augment, Cursor, and Gemini must prove the
literal `use skill <public-name>` explicit request selects an activated
instruction; they cannot substitute file existence for invocation evidence.
For each portfolio/mode/surface, evidence records both the exact sorted
canonical procedure set and exact sorted public-name set including aliases.
Host-owned discoveries are a third, preserved set and never contribute to a
toolkit count.

The bootstrap embeds the complete `which-shape` and `which-skill` procedures,
their declared non-skill runtime files, surface identity, fixed
`schema_version: 1`, a manifest-relative locator, and release-root/bundle-index
hashes; it never embeds a manifest digest. The installed manifest hashes every
generated bootstrap file's raw bytes, including the bytes encoding that fixed
schema-version field, and the tree digest of all and only those files. Their
procedure/runtime bytes derive from bundle-indexed immutable blobs or recipes.
The forward trust graph binds inventory, registry, profile, router, and
generated-manifest content. The dispatcher reads
only that manifest-selected catalog, uses the pinned normalization/scorer/
threshold, and takes an explicit root or ordered root set. It returns exactly
`selected`, `clarification_required`, `proceed_directly`, or `error`.
Automatic selection requires one compatible candidate strictly above every
runner-up with score `>= 5`. A tie, low-confidence shape, or simultaneous
multi-procedure need asks one user question without loading candidate bodies.
`proceed_directly` loads nothing; all invalid trust/profile/binding states are
errors. One canonical procedure can carry an independently ordered ADR 0041
binding sequence for each selected root. Sequential loop skills receive
separate selections and packs.

Bootstrap never embeds a manifest digest. An out-of-band digest roots
`release-root-v1.json`; that hashes the bundle index, installer, surface
contract, schemas, and exact alias/legacy/compatibility tables; the bundle
index hashes immutable catalog/router/procedure/binding/asset blobs and
projection recipes; the self-hashed installed manifest points only forward to
that verified release and hashes generated projections. All JSON is exact-
schema RFC 8785 canonical UTF-8; files hash raw bytes; tree digests use sorted
NFC relative POSIX `{path,size,sha256}` rows; self-digests omit exactly their
own digest field. Duplicate/unknown keys, non-integer numbers, invalid Unicode,
non-NFC/traversing/duplicate/symlink paths, noncanonical JSON, or backward
digest edges fail.

Structured routers use checked-in `WhichShapeResultV1` and
`WhichSkillResultV1` schemas. IDs and constants are exactly those in ADR 0042:
`ascii-wordset-v1`, `which-shape-lexical-v1` with `+12/+4/-10`, context `-4`,
high/medium boundaries `40/24`, and `which-skill-overlap-v1` with
`+5/-10/+2/+8/+3/+6` and threshold `5`. The total outcome table covers
malformed/error, explicit valid/invalid names, shape ties/low confidence, zero
compatible candidates, below-threshold direct work, strict unique winners,
skill ties, and answered clarification. An answered clarification is evaluated
before generic explicit-name input so `selection_basis=user_confirmed` is
reachable. Unlisted combinations fail; no order is a tiebreaker.

Activation records have exact shape `{public_name, canonical_target}`.
Persistent records are cumulative, project-scoped, and idempotent; temporary
records require an invocation id and recoverably disappear at every terminal
outcome. Alias activation preserves the alias as the discovered name while
validating the canonical target. Router execution never creates an activation
record. The mode enum is exactly `router-only|full-discovery`; there is no named
or temporary mode. The router-only public set is the two routers plus requested
persistent/temporary activation records; full discovery is the exact selected
canonical portfolio plus all aliases and deduplicates activation records by
public name. Activating the canonical name and one alias creates two public
entries backed by one stored procedure by design.

Temporary activation requires a registry-verified per-surface terminal wrapper
and pre-discovery startup recovery. It correlates a lowercase UUIDv4 invocation
through `created/exposed/running/terminal/cleaned`, accepts every terminal
result, removes under the lifecycle lock, and proves the name is no longer
discovered before `cleaned`. If either callback or crash cleanup cannot be
proved, that surface declares temporary activation unsupported rather than
best-effort.

The capability registry must declare verified or unsupported fresh-worker
support per surface, including launcher, version range, zero-conversation-turn
proof, injection, cancellation, result, and enforceable budget mechanisms.
Catalog inventory rows declare `execution_class: inline|substantial` and any
parent requirement. A substantial task uses a verified worker unless the
record has one ADR 0042 fallback reason. Runtime launch/capacity/timeout/
cancellation/budget failures never invent parent authority; they fail until
the user explicitly authorizes a retry or parent execution. A surface unable
to inject one selected skill remains unsupported and cannot turn on full
discovery implicitly. Post-worker continuation binds a schema-valid terminal
result with status `failed` or `cancelled`, failure kind, consumed budget,
side-effect disposition, prior dispatch id, workflow pack ordinal, and attempt
ordinal one. `failed` permits only spawn/capacity/timeout/budget/worker failure
kinds; `cancelled` requires the cancelled kind. `unknown` side effects prohibit
continuation; `committed_known` permits only a selected-only parent continuation
with a hashed `resume_without_repeating` plan; `none|rolled_back` permit either
a fresh-worker retry or selected-only parent continuation. Both use a new
dispatch id, same workflow id and pack ordinal, attempt ordinal two, prior id,
and only remaining cumulative budget. Worker retry pins lane `fresh-worker`,
null fallback, and reason `user_confirmed_worker_retry`; parent continuation
pins lane `selected-only-parent`, fallback
`user_confirmed_after_worker_failure`, and reason
`user_confirmed_parent_continuation`.

Exact checked-in draft-2020-12 schemas for `DispatchPackV1` and
`DispatchResultV1` recursively reject additional properties and enforce ADR
0042's RFC-8785 serialization, UUID/id/hash/path/string/list/body/dependency and
131,072/65,536-byte bounds. The pack explicitly carries the selected inline
procedure and ordered inline bindings; supporting assets are verified read-
only store dependencies, never ambient instructions. Results enforce bounded
summary/error fields and at most 16 contained regular-file artifacts using
`artifact://sha256/<digest>`, 16-MiB each/64-MiB aggregate, with raw-byte
verification and no symlink/hard-link escape. Invalid/oversize records fail,
not truncate.

The one-lane limit is project-wide across worker and parent workflows and uses
a dispatch lock. The monotonic 1,200-second workflow deadline begins before
router execution and never pauses or resets. The cumulative 32,768 input-plus-
output token and 8,192 output-token budgets include platform/system/tool,
failed, cancelled, worker, and parent usage across every serial pack and its
possible failure continuation. The same wrapper enforces parent and worker
lanes; unavailable accounting fails closed. Depth is one and each dispatch has
one attempt. A user-confirmed ordinary sequence has at most 16 packs with
strictly increasing `workflow_pack_ordinal`, new dispatch ids, attempt one, and
`initial_selection|confirmed_sequence_step`; it is not a retry or fallback.
Only a confirmed worker-terminal-failure continuation may create attempt two
for the same pack ordinal. No pack has a third attempt, and no detached,
activation, redispatch, or child-spawn behavior is allowed.

The lifecycle manifest implements ADR 0042's complete state tuple and separate
ownership for store, bootstrap, activation/full-discovery projections, activation records,
journal, and generated links. One lifecycle lock and generation transaction
covers all requested surfaces. Success requires post-commit native discovery
on each through the adapter's declared offline non-model check; a surface
without that check is unsupported for transactional lifecycle acceptance. A
separate pinned-runtime/model invocation probe remains required for support but
is outside the deterministic lifecycle command. Any failure or interrupted
command restores the exact previous state before another command runs.
Update/downgrade preserves only still-valid
activations, rollback retains exactly the current and previous validated
generation, and garbage collection removes only unmodified, unreferenced,
owned objects. Modified owned content stops the entire operation. Host
symlinks/escapes fail; an owned internal link is permitted only when manifest-
hashed, contained, and discovery-proven for that surface.

In IM-14 phase 1, before lifecycle code consumes them, exact schema-closed `aliases-v1.json`,
`legacy-layouts-v1.json`, and `compatibility-v1.json` are checked in. Alias rows
declare every surface spelling and lifetime even when the table is empty;
legacy rows declare exact layouts, versions/ranges, paths, known release/tree
hashes, ownership markers, and action. Compatibility uses ADR 0042's exact v1/
registry-1/profile-1/router-ID and five exact surface-version bounds. No value
is inferred. Migration adopts/removes only a listed byte-identical entry;
modified known or host/unknown content stops with a diff, router-only cannot
pass while a legacy toolkit header remains ambient, and unsupported/side-by-
side versions fail closed. Explicit local-bundle downgrade uses the same
transaction and validation.

Every deterministic lifecycle, activation, catalog, and routing operation is
network-, package-manager-, download-, and model-call-free under a denied-
network harness. Persisted records contain hashes/lengths and routing metadata,
not raw prompts, conversation, source/result bodies, or credentials. Raw
pack/body/input/output/result/artifact staging uses umask `077`, `0700`
directories, and `0600` files with no links, and is deleted after handoff for
all five terminal statuses plus startup recovery. Cleanup failure blocks new
dispatch. The `0600` closed journal holds only ids/states/relative paths/hashes/
lengths/budgets/cleanup state. Explicit retention promotes a verified artifact
to a separate `0700`/`0600` user-confirmed root with expiry/deletion policy and
leaves no raw copy. Canary-secret fixtures enforce absence from durable output
and post-terminal staging.

## Characterization requirements

- [ ] AR-1: **Complete pre-change catalog oracle.** Record the exact 76-skill
  name/path/metadata set, every current path reference, and the exact
  Django-applicable name set before body, metadata, catalog, or routing edits.
- [ ] AR-2: **Placement inventory.** Give every discovered skill exactly one
  proposed layer, declared binding IDs, placement rationale, and one of
  `inventory-only`, `foundation-ready`, `exemplar-ready`, or
  `deferred-to-wp8`. Reject missing, duplicate, unknown, or multiply layered
  rows.
- [ ] AR-3: **Foundation-set oracle.** Freeze the exact plan-* members and every
  “inventory sibling with the same shape” covered by AC-3.1 before any
  de-flavoring. No implementation-time wildcard interpretation is allowed.
- [ ] AR-4: **Placement-rule oracle.** Pin N=1 shipping-contract acceptance,
  ≥3 domain cohesion, concept+binding default, invalid N=2 domain grouping,
  and the `/plan-skill` placement question. If a domain layer is selected,
  register and test its IDs and loader semantics; otherwise record that none
  qualified.
- [ ] AR-5: **Core-boundary oracle.** Characterize framework names in proposed
  foundation bodies and pin good/bad frontmatter/content fixtures, including
  prose, links, code fences, case variants, inline compatibility prose, and
  allowed declared binding files.
- [ ] AR-6: **Binding-selection oracle.** Pin per-root profile selections and
  failures for zero match, same-precedence ambiguity, incompatible override,
  root leakage, tool-as-framework inference, and directory-order dependence.
- [ ] AR-7: **`extract-enum` semantic oracle.** Before splitting, pin a Django
  input and final output covering target symbol/path, literals and counts,
  case variants, current keyword arguments, caller classifications/sites,
  member/wire values, migration risks, and stop decision, plus existing invalid
  routing behavior.
- [ ] AR-8: **Allowed normalization oracle.** Permit only temporary absolute
  roots, timestamps/scan IDs, Markdown whitespace, and semantically irrelevant
  deterministic table ordering. Missing or changed identifiers, literals,
  counts, sites, classifications, wire values, risks, or stop decisions remain
  semantic failures.
- [ ] AR-9: **Surface oracle.** Record the AC-1.6 surface/version matrix,
  projection path and format, actual available discovery command, source hash,
  and current invocation result. Explicitly record unavailable Cursor/Augment
  proof rather than treating it as clean.
- [ ] AR-10: **Cold-host ownership oracle.** Pin complete tree hashes for clean
  core-only, TypeScript/React, Django, and mixed fixtures, including sentinel
  host instructions, settings, hooks, ignore files, collisions, and existing
  toolkit-owned files.
- [ ] AR-11: **Move-safety oracle.** Inventory every foundation/exemplar path
  proposal and self-anchored expression. Pin old and proposed targets, read the
  current move tool non-rewrite list, and characterize its inability to repair
  a `Path(__file__)…parents[N] / asset` anchor automatically.
- [ ] AR-12: **First-value oracle.** Freeze one useful, read-only,
  foundation-ready invocation, its deterministic output oracle, documented
  command sequence, timing boundary including installation, and a deny-read
  assertion for `.claude/docs/quality-coordination-kernel.md`.

## Implementation

The slices are dependency ordered. Each IM lands its tests and machine-readable
evidence contract in the same logical change.

### Slice 1 — Catalog and placement contract

- [x] IM-1: **Authoritative inventory reader.** Add
  `.claude/skills/_common/skill-catalog-inventory.yml` and a shared reader that
  validates exact discovered-skill coverage, registered layer/binding IDs,
  readiness, one-layer placement, N=1/≥3 rules, and AR-3 membership.
  <!-- spec:portable-skill-layer-distribution::IM-1 -->
- [x] IM-2: **Honest authoring contract.** Extend skill metadata validation and
  `/plan-skill` placement questions without forcing deferred WP8 rows to claim
  completed migration. <!-- spec:portable-skill-layer-distribution::IM-2 -->

### Slice 2 — Early-move safety gate

- [x] IM-3: **WP3-local move gate.** Before any tracked foundation/exemplar
  move, require scoped retired/avoid terms, exact ADR 0024 two-band evidence,
  substantive prose review, self-anchor inventory and target pins,
  tractable/unhandled classification, per-batch import-and-asset smoke,
  full-diff disk scan, non-rewrite-list acknowledgment, and fired-rule lesson
  capture. Do not mutate ADR status or embodiment metadata.
  <!-- spec:portable-skill-layer-distribution::IM-3 -->
- [x] IM-4: **Blocking move fixture.** Prove a fixture containing stale retired
  prose and a broken self-anchored asset path cannot pass the gate; identifier-
  only cleanup and file-exists-only smoke also fail.
  <!-- spec:portable-skill-layer-distribution::IM-4 -->

### Slice 3 — Foundation boundary

- [x] IM-5: **Core leakage lint.** Add a diff-scoped lint that rejects Django
  or Celery in a migrated core `SKILL.md` body, including examples and links,
  while permitting declared files under `bindings/`; reject dishonest
  frontmatter and duplicated core procedure text.
  <!-- spec:portable-skill-layer-distribution::IM-5 -->
- [x] IM-6: **Foundation de-flavoring.** Migrate exactly the AR-3 set:
  universal procedure in core, framework examples/defaults in declared
  bindings or non-core appendices, and honest language/framework metadata.
  Compatibility prose cannot be an inline lint exception.
  <!-- spec:portable-skill-layer-distribution::IM-6 -->

### Slice 4 — Binding selection and exemplar

- [x] IM-7: **Per-root binding loader.** Implement explicit precedence,
  ambiguity/incompatibility rejection, root isolation, registry validation,
  rendered-content deduplication, and deterministic execution evidence.
  <!-- spec:portable-skill-layer-distribution::IM-7 -->
- [x] IM-8: **`extract-enum` split.** Keep the canonical invocation/root stable;
  extract the closed-vocabulary and wire-identity invariant into core and put
  Python mechanics and Django `TextChoices`/migration behavior in declared
  bindings. The core body may not name Django or Celery.
  <!-- spec:portable-skill-layer-distribution::IM-8 -->
- [x] IM-9: **Final-boundary equivalence.** Run the Django fixture through the
  final proposal/output boundary and compare it semantically to AR-7 using only
  AR-8 normalizations. Existing extraction/routing tests remain green.
  <!-- spec:portable-skill-layer-distribution::IM-9 -->

### Slice 5 — Surface discovery and compatibility

- [x] IM-10: **Five-surface projection.** Generate complete procedures and
  metadata for Claude Code, Codex, Augment, Cursor, and Gemini from one bundle
  inventory; validate canonical hashes, expected locations/formats, and
  reference-clean contracts/catalog entries.
  <!-- spec:portable-skill-layer-distribution::IM-10 -->
- [ ] IM-11: **Runtime discovery evidence.** At the exact AC-1.6 versions,
  capture tool-observed invocation discovery bound to source revision, bundle
  hash, host-fixture hash, projection path, command output, and output hash.
  Externally executed Cursor/Augment evidence is acceptable only with all those
  bindings; structural checks cannot satisfy this item.
  <!-- spec:portable-skill-layer-distribution::IM-11 -->
- [x] IM-12: **Compatibility aliases.** Preserve invocation names unchanged or
  emit versioned tested aliases; reject alias collisions, cycles, stale
  targets, and surface-specific divergence.
  <!-- spec:portable-skill-layer-distribution::IM-12 -->

### Slice 6 — Portfolios and transactional installer

- [x] IM-13: **Three portfolio snapshots.** Assert name, source hash, rendered
  hash, layer, selected binding, and alias sets for core-only,
  TypeScript/React, and Django. Core-only has zero framework-native content;
  TypeScript proves projection/selection without WP6 behavior; Django
  preserves the exact AR-1 applicable set. For every portfolio, separately
  snapshot the non-discovered catalog contents and default activation set;
  default activation is exactly `which-shape` plus `which-skill`, with no other
  skill header exposed. For every surface and portfolio also snapshot the exact
  sorted canonical-procedure set, exact sorted public-name set including
  aliases, and preserved host-owned discovery set in router-only, initial named
  activation of a non-router, named alias activation, cumulative canonical+
  alias activation, and full-discovery states. If the checked-in production
  alias table is empty, the two alias states are instead the exact typed
  unavailable record `{available: false, reason: no_alias_declared,
  activation_records: []}` on every surface/portfolio; no release alias is
  invented. A separate fixture-only `plan-feature-v1` → `plan-feature` row
  with identical five-surface spellings, introduced release 1, and null
  retirement must exercise the available named-alias and cumulative states
  without entering any release/bundle/catalog/projection/runtime set. The mode field remains exactly
  `router-only|full-discovery`; activation records are orthogonal. Canonical router-only count is
  two; initial non-router named activation count is three; all other counts are
  derived from and must equal the checked-in exact sets rather than a loose
  total. Pin ADR 0042's public syntax/path/namespace table, including Codex's
  `engineering-skills:` namespace and literal instruction requests on
  instruction-backed surfaces.
  <!-- spec:portable-skill-layer-distribution::IM-13 -->
- [ ] IM-14: **Offline bundle contract.** Add a checksummed versioned manifest
  containing inventory/registry hashes, owned paths and hashes, projections,
  invocations, aliases, required canonical profile, catalog-store paths,
  activation mode, explicitly activated names, and delegation/fallback policy.
  Base install performs no network or package-manager action and defaults to
  router-only activation; `full-discovery` requires an explicit manifest mode.
  Phase 1 checks in and validates all eight exact schemas—release-root,
  bundle-index, installed-manifest, surface-activation-contract,
  `WhichShapeResultV1`, `WhichSkillResultV1`, `DispatchPackV1`, and
  `DispatchResultV1`—before installer or dispatcher code consumes them. Schema
  authoring is the first IM-14 implementation phase and is not blocked by this
  prerequisite. Then implement
  ADR 0042's exact acyclic external-root trust graph, RFC-8785/digest domains,
  raw-file/tree/self-digest algorithms, and no bootstrap→manifest digest edge.
  The generated bootstrap contains surface identity, fixed
  `schema_version: 1`, locator, release/bundle digests, both complete router
  procedures, and their declared runtime files; it never contains a manifest
  digest. The manifest hashes every bootstrap file's raw bytes, including that
  fixed schema-version field, and the exact tree digest over all and only those
  files. Check in the exact closed
  `WhichShapeResultV1`/`WhichSkillResultV1` schemas and pin
  `ascii-wordset-v1`, `which-shape-lexical-v1` (+12/+4/-10, -4 context,
  40/24 confidence), and `which-skill-overlap-v1`
  (+5/-10/+2/+8/+3/+6, threshold 5). Exercise the total outcome table for
  malformed, explicit valid/invalid, zero compatible, below threshold, unique,
  tie, low-confidence, and answered-clarification inputs. Manifest schema
  pins the surface activation contract, `{public_name, canonical_target}`
  activation records, temporary invocation ids, per-surface verified/
  unsupported worker capability, catalog `execution_class`/parent
  requirements, allowed fallback reasons, and `DispatchPackV1`/
  `DispatchResultV1`. Check in their exact recursive-additional-properties-
  false draft-2020-12 schemas and enforce canonical serialization, per-field
  UUID/id/hash/root/binding/task/dependency/body/result/error/artifact bounds,
  explicit inline procedure/bindings, verified store assets, workflow pack and
  attempt ordinals, lane/reason combinations, and artifact URI/
  containment/hash rules. Enforce the exact 131,072-byte pack, 65,536-byte
  result, project-wide lock, depth-one/one-attempt-per-dispatch, monotonic
  1,200-second workflow deadline, cumulative 32,768 input+output/8,192 output-
  token budgets across every ordinary serial pack and worker/parent
  continuation, at most 16 confirmed sequence packs, at most two dispatches
  per pack only after a typed terminal worker failure, and no-detached/no-child/
  no-redispatch defaults. Persist only
  hashes, lengths, routing metadata, budgets, status, and artifact hashes; raw
  task/conversation/source/result/credential content is not manifest or
  telemetry data.
  <!-- spec:portable-skill-layer-distribution::IM-14 -->
- [ ] IM-15: **Transactional lifecycle.** Stage, validate, and atomically
  install/update; verify all owned content; uninstall only unmodified owned
  paths. Reject host collisions, modified-owned content, traversal, symlink
  escape, duplicate targets, corrupt checksums/manifests, and interrupted
  staging without host mutation. Prove every lifecycle command idempotent.
  Activation/deactivation and router-only↔full-discovery transitions use the
  same ownership/collision/rollback guarantees and never copy a procedure into
  an automatically discovered path without explicit activation. Implement the
  full lifecycle tuple and separate ownership classes from ADR 0042. One
  project lock and recovery journal cover the complete requested surface set;
  no success is published before native discovery agrees on every surface, and
  startup recovery restores the exact prior manifest/tree/discovery/
  activations after any interruption. Add cumulative persistent activation,
  invocation-scoped temporary activation only on surfaces with a verified
  correlated terminal wrapper/pre-discovery crash cleanup (otherwise explicit
  unsupported), exact
  deactivation, explicit local-bundle downgrade and rollback, update-time
  activation/alias/binding validation, current+previous generation retention,
  owned-reference garbage collection, all-or-nothing modified-owned handling,
  same-namespace side-by-side rejection, and the manifest-contained generated-
  link policy. As IM-14 phase 1, before lifecycle consumer code, check in exact closed
  `aliases-v1.json`, `legacy-layouts-v1.json`, and `compatibility-v1.json` with
  ADR 0042's concrete v1/registry-1/profile-1/router and exact five-surface
  bounds. Characterize and migrate every supported pre-amendment ambient
  layout and prior manifest from that inventory: adopt/retire only known byte-identical toolkit
  content; modified known or host/unknown content stops with a diff; no
  router-only success may leave a legacy toolkit header ambient. Pin reader/
  bundle/catalog/router/delegation/surface compatibility ranges. Every
  deterministic lifecycle, activation, catalog, and routing command runs under
  denied network and proves no package manager, download, or model call.
  <!-- spec:portable-skill-layer-distribution::IM-15 -->
- [ ] IM-16: **Cold-host matrix.** Exercise v1→v2→uninstall and repeated
  operations in isolated `HOME`/XDG/Codex roots for all four AR-10 fixtures;
  compare host-owned hashes before and after every operation. On every surface,
  inspect actual discovery after each lifecycle step: router-only exposes two
  headers, a named activation exposes only that additional skill, and explicit
  full-discovery exposes the selected portfolio without changing the catalog
  store or host-owned files. Run the exact-set matrix from IM-13 through
  activate-repeat/deactivate-repeat, canonical+alias cumulative activation,
  temporary success/failure/cancellation/startup recovery, router-only↔full-
  discovery transitions with zero/one/multiple activation records, v1→v2 with preserved and stale activation, compatible
  downgrade, rollback, interrupted multi-surface commit, concurrent-lock
  rejection, modified-owned stop, host namespace collision, host symlink/
  escape, allowed owned-link discovery, and uninstall. Native evidence must
  enumerate the expected set; where a runtime has no list command it must
  positively invoke every expected public name and negatively invoke an
  unselected name. That separately recorded invocation probe is outside the
  denied-network/model lifecycle command, performs no lifecycle mutation, and
  cannot make a failed lifecycle check pass. Structural output cannot satisfy
  any of the five surfaces.
  <!-- spec:portable-skill-layer-distribution::IM-16 -->

### Slice 7 — First value and release evidence

- [ ] IM-17: **Timed useful run.** From a clean fixture, replay only documented
  steps, including installation and verification, discover/select/run the
  AR-12 skill, validate useful output, finish within 1,200 seconds, and prove
  the kernel document was not read. Record local execution verification only;
  do not issue WP8 support-state promotion. Begin from router-only activation;
  route through `which-shape`/`which-skill`, then run the selected skill in a
  fresh no-context worker with a bounded task pack. Also prove the selected-only
  parent fallback on a no-sub-agent fixture. Neither lane may receive an
  unrelated skill header or body. Exercise all dispatcher outcomes: strict
  unique winner, user-confirmed tie/low confidence, `proceed_directly`, and
  trust/profile/binding `error`. Prove per-root ordered bindings for a mixed-
  root single-skill selection and separate serial packs when two procedures are
  user-confirmed. Worker evidence binds the registry capability declaration,
  zero conversation turns, enumerated platform/bootstrap context, exact pack/
  result bytes and hashes, budgets, result status, and absence of unselected
  skill content. Parent fallback must use one allowed reason and the identical
  schemas. Spawn/timeout/capacity/cancellation/budget failures must not fall
  back or retry without an exact confirmation record binding the terminal
  `failed|cancelled` dispatch/result, status-consistent failure kind,
  time/tokens, side-effect disposition, plan hash, new dispatch id, same pack
  ordinal, attempt ordinal two, exact retry/parent lane and continuation reason,
  parent-only `user_confirmed_after_worker_failure` fallback reason, and
  remaining cumulative budget. Unknown side effects and parent-lane enforcement/accounting failures
  stop. Oversize, recursion,
  redispatch, activation, child-spawn, detached-work, and unenforceable-budget
  attacks fail. A canary secret is absent from manifest, logs, evidence,
  stdout, and errors; retained raw artifacts require explicit mode-`0600` local
  retention and a deletion policy. Verify umask `077`, `0700` directories,
  `0600` files/journal, no links/raw journal content, deletion after handoff for
  every terminal status, pre-discovery startup cleanup, cleanup-failure lockout,
  and no raw copy after explicit artifact promotion.
  <!-- spec:portable-skill-layer-distribution::IM-17 -->
- [ ] IM-18: **Reference and regression gate.** Require clean metadata,
  contracts/index, intent/artifact drift, decision links, catalog references,
  focused tests, Ruff, and the full suite. Evidence is content-addressed and
  generated checks have read-only stale detection. Also require read-only
  surface-contract, catalog-locator, dispatcher-schema, privacy, compatibility-
  matrix, migration-inventory, activation-state, recovery-journal, denied-
  network, and exact-discovery-set checks. Generated evidence cannot retain raw
  task/result content or self-report freshness, worker capability, discovery,
  budget enforcement, or network denial.
  <!-- spec:portable-skill-layer-distribution::IM-18 -->

## Code and fixture surface

| Surface | Required change or evidence |
|---|---|
| `.claude/skills/_common/capability-registry.yml` | selected layer/binding/domain vocabulary only; no consumer-local enum |
| `.claude/skills/_common/skill-catalog-inventory.yml` | exact 76-row placement/readiness authority |
| `.claude/skills/_common/distribution/{release-root-v1,bundle-index-v1,installed-manifest-v1,surface-activation-contract-v1,which-shape-result-v1,which-skill-result-v1,dispatch-pack-v1,dispatch-result-v1}.schema.json` | exact closed schemas, canonical digest domains, lifecycle, router, and dispatch wire contracts |
| `.claude/skills/_common/distribution/{aliases-v1,legacy-layouts-v1,compatibility-v1}.json` | exact aliases, migratable legacy releases/layouts, and closed compatibility bounds |
| `.claude/skills/_common/skill-frontmatter.md` | honest layer/binding/readiness authoring contract |
| `.claude/docs/skill-catalog.md` | invocation and binding links generated/reference-checked |
| `.claude/skills/plan-skill/SKILL.md` | N=1, ≥3, and concept+binding placement question |
| `.claude/skills/extract-enum/` | stable canonical root, neutral core, Python/Django binding artifacts |
| `scripts/_lib/skill_catalog.py` | inventory discovery and placement validation |
| `scripts/_lib/binding_loader.py` | per-profile-root selection and execution evidence |
| `scripts/_lib/skill_installer.py`, `scripts/skill_installer.py` | offline bundle and transactional lifecycle |
| `scripts/_lib/skill_dispatch.py` | trusted catalog locator, exact-one dispatcher, pack/result schemas, worker/fallback policy |
| `scripts/_lib/distribution_legacy.py` | closed exact-known legacy layout and ownership-marker semantics |
| `scripts/distribution_probe.py` | projection plus separate runtime-evidence verification |
| `scripts/wp3_move_gate.py` | ADR 0024/0028 safety-only pre-move gate |
| `scripts/lint/no_core_framework_leakage.py` | diff/all-mode content and frontmatter guard |
| `scripts/skill_meta.py`, `scripts/_lib/skill_activation.py`, `scripts/manifest.py` | consume authoritative inventory where readiness/selection matters |
| `tests/fixtures/wp3/hosts/{core-only,typescript-react,django,mixed}` | cold hosts, ownership sentinels, collisions, lifecycle states |
| `tests/fixtures/wp3/surfaces/{claude-code,codex,augment,cursor,gemini}` | exact-version projection and runtime evidence fixtures |
| `tests/fixtures/wp3/activation/{legacy-ambient,prior-manifest,collisions,symlinks,interrupted,temporary-callback}` | migration, ownership, recovery, temporary cleanup, and version-transition fixtures |
| `tests/fixtures/wp3/dispatch/{unique,tie,no-match,error,malformed,explicit,mixed-root,worker-failure,privacy}` | total dispatcher outcomes, per-root packs, fallback/side-effects, bounds, and canary fixtures |
| `tests/fixtures/wp3/extract-enum` | pinned input, raw output, semantic oracle, invalid form |
| `tests/fixtures/wp3/move-gate` | retired prose and broken self-anchor negative fixture |
| `tests/fixtures/wp3/bundles/{v1,v2,corrupt}` | update, rollback, corruption, and idempotence cases |

Existing flat-glob readers migrate only where the new inventory must become
authoritative. WP3 does not introduce physical nesting solely to force reader
changes. No host home/global path is used in tests without explicit isolated
environment variables.

## Evidence protocol

Every slice writes deterministic evidence under the WP3 report directory. Each
record contains source revision, exact command, exit status, tool/runtime
versions, fixture and input hashes, output hash, and generated-at time. A clean
verifier recomputes hashes and outcomes; it does not trust a boolean `passed`.

| Criterion | Required evidence |
|---|---|
| AC-3.1 | exact inventory/hash, frozen foundation set, placement validator output, leakage/frontmatter fixtures, `/plan-skill` assertion |
| AC-3.2 | five exact-version runtime discovery records, unchanged-name/alias outcomes, contracts/catalog/index reference checks |
| AC-3.3 | per-root selection JSON with ordered overlays and negative ambiguity/incompatibility/root-leak outputs |
| AC-3.4 | pre/post semantic oracle hashes, normalization report, final Django proposal output, existing test results |
| AC-3.5 | three name/content/selection snapshots, exact canonical/public/alias/host discovery sets for every mode and surface, and negative cross-layer/unselected-content scans |
| AC-3.6 | release-root/trust-graph/digest recomputation; exact schema/table hashes; lifecycle state/tree/ownership hashes; migration/version/rollback/collision/recovery/temporary-cleanup diffs; idempotence and denied-network runs; total dispatcher/pack/result/fallback/side-effect/cumulative-budget/privacy records; terminal raw-deletion and permission proof; timed useful-run transcript; canary-secret absence; and deny-read proof |
| AC-3.7 | exact two-band commands/output, substantive review, proposal/self-anchor inventory, pins, rewrite/unhandled report, import-and-asset smoke, full-diff scan, non-rewrite acknowledgment, fired-rule lesson, blocking fixture |

Runtime discovery evidence from a different machine must additionally carry
the pinned surface binary version, platform identity, source-tree hash, bundle
hash, fixture hash, command transcript, and raw-output hash. Cursor/Augment
evidence missing any field leaves IM-11 and AC-3.2 open.

## Deterministic interfaces and acceptance commands

The current Slice 5 implementation provides a read-only matrix verifier.
Acceptance commands below name only implemented commands and existing tests;
later installer slices must extend this block when their interfaces land.
Checks must fail on stale artifacts rather than silently rewriting them.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_skill_catalog_layers.py \
  tests/test_binding_loader.py \
  tests/test_extract_enum_binding.py \
  tests/test_distribution_contract_schemas.py \
  tests/test_distribution_reference_tables.py \
  tests/test_portfolio_snapshots.py \
  tests/test_distribution_surfaces.py \
  tests/test_wp3_move_gate.py \
  tests/test_capability_consumers.py \
  tests/test_skill_activation.py \
  tests/test_skill_meta_jobs.py

.venv/bin/python scripts/skill_meta.py lint --strict --quiet
.venv/bin/python scripts/lint/no_core_framework_leakage.py --all
.venv/bin/python scripts/distribution_probe.py verify-matrix \
  . --fixtures "$WP3_SURFACE_FIXTURES" --evidence "$WP3_SURFACE_EVIDENCE" \
  --runtime-root "$WP3_RUNTIME_ROOT"

.venv/bin/python \
  .claude/skills/find-skill-intent-drift/scripts/scan.py \
  --strict --no-index
.venv/bin/python \
  .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate
.venv/bin/python scripts/decisions.py audit
.venv/bin/python scripts/decisions.py link-check
.venv/bin/python scripts/plans.py audit
.venv/bin/python scripts/specs.py coverage portable-skill-layer-distribution
.venv/bin/python scripts/specs.py inventory-check \
  portable-skill-layer-distribution
.venv/bin/ruff check <exact changed Python paths>
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest
```

Before any real WP3 tracked-path move, evidence must also retain these exact
tool invocations with concrete old/new terms and fixture/project paths:

```bash
.venv/bin/python \
  .claude/skills/find-concept-divergence/scripts/scan.py \
  --project-root <project-root> \
  --glossary <project-root>/.claude/contracts/concepts.yaml \
  --output <report-dir>/findings.jsonl \
  --report <report-dir>/report.md .
.venv/bin/python \
  .claude/skills/rename-concept/scripts/assess.py \
  --project-root <project-root> <retired-term> <replacement-term>
.venv/bin/python \
  .claude/skills/move-path/scripts/move_path.py \
  --project-root <project-root> --plan <move-plan> \
  --report-dir <report-dir> --check --json
.venv/bin/python scripts/wp3_move_gate.py check \
  --project-root <project-root> --plan <move-plan> \
  --report-dir <report-dir>
```

The move-gate record must identify the scan output rows corresponding to both
`superseded_co_occurrence` and `avoid_term_hit`, even though one scan command
produces both bands.

## Adversarial acceptance matrix

| Criterion | Attacks that must fail |
|---|---|
| AC-3.1 | missing/duplicate/unknown skill; two layers; N=2 domain; unregistered domain; Django/Celery in prose, link, or code fence; case variant; inline compatibility exception; dishonest frontmatter; core text copied into binding; missing placement question |
| AC-3.2 | projection exists but runtime cannot discover/invoke it; omitted surface; wrong version; wrong public syntax/path/namespace; Codex loses `engineering-skills:`; instruction surface treats file presence as invocation; source/hash-only instruction with no procedure; renamed trigger without alias; alias loop/collision/stale or changed target; dangling contract/catalog path |
| AC-3.3 | global mixed-stack selection; first-installed winner; two same-precedence candidates; incompatible explicit choice; zero required match silently falls back; Vite inferred as React; malformed/tampered profile; root A binding selected for root B; evidence omits overlay |
| AC-3.4 | comparator normalizes a missing literal/site/risk; Django remains in core; wire values, ordering, or case variants change; invalid routing starts passing; only collector intermediate output is compared; absent binding passes |
| AC-3.5 | snapshots check counts but not exact canonical/public/alias/host sets; router-only exposes an alias or third toolkit header; named activation exposes canonical and alias unexpectedly; full discovery omits aliases; host skill counted as toolkit; structural file counted as runtime discovery; inferred legacy core leaks framework content; TypeScript portfolio is empty or includes Django; Django loses an AR-1 name; mixed-root selection broadens globally |
| AC-3.6 | bootstrap↔manifest/bundle digest cycle or mutable mutual attestation; wrong digest domain/canonicalization/path ordering/self-field; unknown/duplicate JSON field; missing exact schema/alias/legacy/compatibility table; unbounded/inferred version; ambient scan or checkout-relative catalog lookup; unverified hash/locator; wrong normalizer/scorer/weight/threshold; uncovered outcome; ranking tie broken by order; shape treated as procedure; no-match loads a body; router error becomes direct work; mode outside exact two-value enum; alias activation changes public name; temporary activation without verified terminal wrapper/pre-discovery recovery or survives a terminal outcome; routed work changes discovery; undeclared/forged worker capability; disallowed fallback; worker failure fallback lacks prior result/new id/side-effect disposition/plan hash or resets budget; unknown side effects continue; two project lanes; deadline starts late/pauses; token counter omits input/system/tool/failed/parent usage; parent accounting unenforced; inherited conversation; selected procedure not explicitly delivered; unselected skill/dependency in pack; schema/per-field/artifact bound bypass; artifact URI/hash/containment/link attack; oversize/truncated pack/result; recursion/redispatch/activation/child/detached worker; raw prompt/result/secret in manifest/journal/evidence; wrong file/dir permissions; terminal/startup raw staging survives; cleanup failure permits new dispatch; retained artifact leaves raw copy; canary leak; host file overwritten; traversal/host symlink/escape; corrupted checksum; partial multi-surface update; missing lifecycle lock/recovery; retired owned path remains; modified owned file overwritten/deleted; stale activation silently dropped/remapped; legacy ambient header remains; unknown legacy content adopted; incompatible reader/surface silently uses full discovery; side-by-side namespace; second lifecycle operation changes state; hidden network/package/model/download; timing excludes setup; starter reads kernel |
| AC-3.7 | generic noisy `avoid:`; only one findings band checked; identifiers renamed while prose stays stale; unhandled self-anchor omitted; import smoke never reads the asset; staged-only rather than full-diff scan; directory accepted where file required; no fired-rule lesson; path moved before gate; ADR status/embodiment changed |

## Completion risks and stop conditions

- **Cursor/Augment discovery:** if exact-version tool-observed discovery cannot
  be produced, structural projection work may land but WP3 and AC-3.2 remain
  open. No simulation waiver exists in this spec.
- **Routed activation:** if any surface lacks an exact public identity,
  manifest-relative trusted locator, enforceable worker declaration, selected-
  only injection path, native exact-set proof, or safe explicit-activation
  path, router-only work for that surface may not claim completion and may not
  fall back to full discovery.
- **Wire/trust prerequisites:** IM-14 phase 1 is to check in and validate the
  acyclic release trust graph, all eight exact JSON Schemas, and exact alias/
  legacy/compatibility tables. Schema/table creation itself is permitted and
  is not self-blocked; installer, dispatcher, and lifecycle code that consumes
  those contracts may not begin until phase 1 passes. Prose examples or
  implementation-owned defaults cannot substitute for those artifacts.
- **Legacy migration:** if an ambient entry cannot be proven byte-identical to
  a known toolkit release, migration stops and leaves it host-owned. No
  ownership guess or partial router-only success is permitted.
- **Tracked moves:** if IM-3/IM-4 are not already landed and green, no
  foundation or exemplar tracked-path move may proceed. Keeping canonical
  roots flat is the preferred WP3 course.
- **Domain placement:** assigning a domain layer without registered IDs and
  selection semantics is a stop, not an inventory-only convention.
- **TypeScript claims:** failure to produce a nonempty, correctly selected
  TypeScript projection is a WP3 failure; absence of WP6 end-to-end behavior is
  not. No unsupported behavior may be fabricated to fill the snapshot.
- **Support-state claims:** WP3 evidence may say a local run was verified. It
  may not mark a surface or skill `verified`; that remains WP8-owned.
- **Reference generation:** any generator lacking a read-only stale-check mode
  must gain one before final clean verification; acceptance cannot depend on a
  verifier mutating the checkout.

## Exceptions

- Physical layer-directory moves are intentionally avoided in WP3 when logical
  inventory, declared binding artifacts, and generated surface projections
  satisfy the acceptance criteria. This follows ADR 0042 and reduces discovery
  risk; it does not waive AC-3.7 for any move that does occur.
- Full-catalog body migration is deferred only where the inventory explicitly
  marks the row `deferred-to-wp8`. Inventory completeness, placement validity,
  honest readiness, and the foundation/exemplar boundary are not deferred.
- Externally executed surface evidence is permitted for a runtime unavailable
  locally only when content-addressed as specified above. Structural checks
  alone remain insufficient.
- No network, package manager, model call, or host-global installation is
  permitted in deterministic installer and fixture acceptance.

---

## Known symbol inventory

The distribution probe now exceeds the narrative-inventory threshold. Its
structural helpers are `_sha256_bytes`, `_canonical_bytes`, `_tree_hash`,
`_git_output`, `_is_cache_artifact`, `_git_tree_files`,
`_dirty_tracked_paths`, `_require_clean_tracked_sources`,
`_require_exact_worktree_sources`, `_directory_tree_hash`, `_path_is_clean`,
`_row_hash`, `_bundle_hash`,
`_document_hash`, `_reference_paths`, `_validate_reference_semantics`,
`_source_file_sets`, `_load_catalog_from_git`, `build_bundle_inventory`,
`_alias_targets`, `validate_bundle_inventory`, `_resolved_aliases`,
`_alias_skill`, `_expected_projection_files`, `build_projections`, and
`validate_projections`.

Runtime collection and validation are `_run`, `_command_record`,
`_git_revision`, `_git_tree`, `_platform_record`, `_reset_directory`,
`_prepare_claude_marketplace`, `_prepare_codex_marketplace`,
`_claude_detail_names`, `_nested_strings`, `_codex_prompt_names`,
`collect_runtime_evidence`, `_validate_command_record`,
`_expected_runtime_version`, `_probe_observed_version`, and
`validate_runtime_evidence`. CLI entry points are `_load_json` and `main`.

The offline trust-bundle module's byte/path helpers are `_freeze_json`, `raw_sha256`,
`validate_relative_path`, `_root_path`, `_safe_path`, `_read_file`,
`_write_file`, `_row`, `tree_rows`, `tree_sha256`, `_verify_row`,
`_strict_json_bytes`, `_unique_pairs`, `_reject_number`, and `_surface_map`.
Its recipe/release graph is `_validate_recipe`, `_build_release_bundle`,
`build_release_bundle`, `_verify_release_bundle`, `verify_release_bundle`,
`_load_recipe`, and `_load_recipe_set`. New-image production and verification
are `_materialize_install_image`, `materialize_install_image`,
`_verify_surface_bootstrap`, `_verify_install_image`, `verify_install_image`,
and `recipe_from_json`.

The deterministic dispatcher module's input and scoring helpers are `_utf8`,
`_require_id`, `_require_digest`, `_token_array`, `_parse_shape`,
`_validate_shape_boosts`, `_parse_skill`, `_parse_roots`, `_task_bytes`,
`normalize_task`, `_normalize_text`, `_task_sha256`, `_boost_condition`,
`_boost_rules`, `_literal_boost_cues`, `route_shape`, `_infer_signal`,
`_score_skill`, and `route_skill`. Its decision boundary is `_decision`,
`_validate_router_result`, `_load_selected`, and `dispatch_selection`.

The phase-1 contract-schema test module also exceeds that threshold. Its
validator/exemplar helpers are `_unique_object`, `_resolve_ref`, `_is_type`,
`_validation_errors`, `_assert_valid`, `_file_row`, `_release_root`,
`_bundle_index`, `_surface_contract`, `_installed_manifest`, `_shape_result`,
`_skill_result`, `_dispatch_pack`, `_dispatch_result`, and `_walk_schemas`.
Its structural/table cases are
`test_im_14_phase_1_checks_in_exact_closed_contract_set`,
`test_im_14_schemas_are_draft_2020_12_recursively_closed`,
`test_im_14_schema_accepts_its_closed_v1_exemplar`,
`test_im_14_schema_rejects_unknown_and_missing_top_level_fields`,
`test_im_14_deep_negative_contract_attacks_fail_closed`,
`test_surface_contract_accepts_fully_evidenced_verified_capabilities`,
`test_surface_contract_rejects_inexact_identity_for_every_surface`,
`test_verified_temporary_activation_rejects_null_proof_fields`,
`test_verified_fresh_worker_rejects_null_proof_or_enforcement_fields`,
`test_im_14_strict_loader_rejects_duplicate_json_keys`,
`test_im_14_alias_and_legacy_tables_are_explicitly_empty_and_closed`, and
`test_im_14_compatibility_table_pins_every_closed_bound`. Its semantic helper
and cases are `_assert_semantically_invalid`,
`test_im_14_router_semantics_enforce_confidence_thresholds_and_ordering`,
`test_im_14_dispatch_pack_semantics_enforce_selection_and_digest_domains`,
`test_im_14_dispatch_result_semantics_bind_pack_tuple_attempt_and_prior_result`,
`test_im_14_semantic_validator_enforces_non_schema_byte_and_artifact_limits`,
and `test_im_14_installed_manifest_semantics_enforce_surface_and_path_coherence`.
Its production-gate repair cases are
`test_production_validator_runs_structural_unknown_field_gate`,
`test_attempt_two_requires_a_new_dispatch_id`,
`test_dispatch_pack_hashes_actual_inline_content`, and
`test_manifest_rejects_cross_surface_router_paths_after_coherent_rehash`.
