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
  - scripts/_lib/skill_installer.py
  - scripts/installer_selection.py
  - scripts/distribution_probe.py
  - scripts/skill_installer.py
  - scripts/wp3_move_gate.py
  - scripts/lint/no_core_framework_leakage.py
  - scripts/skill_meta.py
  - scripts/_lib/skill_activation.py
  - scripts/manifest.py
  - tests/test_skill_catalog_layers.py
  - tests/test_binding_loader.py
  - tests/test_extract_enum_binding.py
  - tests/test_distribution_surfaces.py
  - tests/test_skill_installer.py
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
stale-target checks.

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

- [ ] IM-7: **Per-root binding loader.** Implement explicit precedence,
  ambiguity/incompatibility rejection, root isolation, registry validation,
  rendered-content deduplication, and deterministic execution evidence.
  <!-- spec:portable-skill-layer-distribution::IM-7 -->
- [ ] IM-8: **`extract-enum` split.** Keep the canonical invocation/root stable;
  extract the closed-vocabulary and wire-identity invariant into core and put
  Python mechanics and Django `TextChoices`/migration behavior in declared
  bindings. The core body may not name Django or Celery.
  <!-- spec:portable-skill-layer-distribution::IM-8 -->
- [ ] IM-9: **Final-boundary equivalence.** Run the Django fixture through the
  final proposal/output boundary and compare it semantically to AR-7 using only
  AR-8 normalizations. Existing extraction/routing tests remain green.
  <!-- spec:portable-skill-layer-distribution::IM-9 -->

### Slice 5 — Surface discovery and compatibility

- [ ] IM-10: **Five-surface projection.** Generate complete procedures and
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
- [ ] IM-12: **Compatibility aliases.** Preserve invocation names unchanged or
  emit versioned tested aliases; reject alias collisions, cycles, stale
  targets, and surface-specific divergence.
  <!-- spec:portable-skill-layer-distribution::IM-12 -->

### Slice 6 — Portfolios and transactional installer

- [ ] IM-13: **Three portfolio snapshots.** Assert name, source hash, rendered
  hash, layer, selected binding, and alias sets for core-only,
  TypeScript/React, and Django. Core-only has zero framework-native content;
  TypeScript proves projection/selection without WP6 behavior; Django
  preserves the exact AR-1 applicable set.
  <!-- spec:portable-skill-layer-distribution::IM-13 -->
- [ ] IM-14: **Offline bundle contract.** Add a checksummed versioned manifest
  containing inventory/registry hashes, owned paths and hashes, projections,
  invocations, aliases, and required canonical profile. Base install performs
  no network or package-manager action.
  <!-- spec:portable-skill-layer-distribution::IM-14 -->
- [ ] IM-15: **Transactional lifecycle.** Stage, validate, and atomically
  install/update; verify all owned content; uninstall only unmodified owned
  paths. Reject host collisions, modified-owned content, traversal, symlink
  escape, duplicate targets, corrupt checksums/manifests, and interrupted
  staging without host mutation. Prove every lifecycle command idempotent.
  <!-- spec:portable-skill-layer-distribution::IM-15 -->
- [ ] IM-16: **Cold-host matrix.** Exercise v1→v2→uninstall and repeated
  operations in isolated `HOME`/XDG/Codex roots for all four AR-10 fixtures;
  compare host-owned hashes before and after every operation.
  <!-- spec:portable-skill-layer-distribution::IM-16 -->

### Slice 7 — First value and release evidence

- [ ] IM-17: **Timed useful run.** From a clean fixture, replay only documented
  steps, including installation and verification, discover/select/run the
  AR-12 skill, validate useful output, finish within 1,200 seconds, and prove
  the kernel document was not read. Record local execution verification only;
  do not issue WP8 support-state promotion.
  <!-- spec:portable-skill-layer-distribution::IM-17 -->
- [ ] IM-18: **Reference and regression gate.** Require clean metadata,
  contracts/index, intent/artifact drift, decision links, catalog references,
  focused tests, Ruff, and the full suite. Evidence is content-addressed and
  generated checks have read-only stale detection.
  <!-- spec:portable-skill-layer-distribution::IM-18 -->

## Code and fixture surface

| Surface | Required change or evidence |
|---|---|
| `.claude/skills/_common/capability-registry.yml` | selected layer/binding/domain vocabulary only; no consumer-local enum |
| `.claude/skills/_common/skill-catalog-inventory.yml` | exact 76-row placement/readiness authority |
| `.claude/skills/_common/skill-frontmatter.md` | honest layer/binding/readiness authoring contract |
| `.claude/docs/skill-catalog.md` | invocation and binding links generated/reference-checked |
| `.claude/skills/plan-skill/SKILL.md` | N=1, ≥3, and concept+binding placement question |
| `.claude/skills/extract-enum/` | stable canonical root, neutral core, Python/Django binding artifacts |
| `scripts/_lib/skill_catalog.py` | inventory discovery and placement validation |
| `scripts/_lib/binding_loader.py` | per-profile-root selection and execution evidence |
| `scripts/_lib/skill_installer.py`, `scripts/skill_installer.py` | offline bundle and transactional lifecycle |
| `scripts/distribution_probe.py` | projection plus separate runtime-evidence verification |
| `scripts/wp3_move_gate.py` | ADR 0024/0028 safety-only pre-move gate |
| `scripts/lint/no_core_framework_leakage.py` | diff/all-mode content and frontmatter guard |
| `scripts/skill_meta.py`, `scripts/_lib/skill_activation.py`, `scripts/manifest.py` | consume authoritative inventory where readiness/selection matters |
| `tests/fixtures/wp3/hosts/{core-only,typescript-react,django,mixed}` | cold hosts, ownership sentinels, collisions, lifecycle states |
| `tests/fixtures/wp3/surfaces/{claude-code,codex,augment,cursor,gemini}` | exact-version projection and runtime evidence fixtures |
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
| AC-3.5 | three name/content/selection snapshots and negative cross-layer leakage scans |
| AC-3.6 | lifecycle tree/ownership hashes, rollback/collision diffs, idempotence runs, timed useful-run transcript and deny-read proof |
| AC-3.7 | exact two-band commands/output, substantive review, proposal/self-anchor inventory, pins, rewrite/unhandled report, import-and-asset smoke, full-diff scan, non-rewrite acknowledgment, fired-rule lesson, blocking fixture |

Runtime discovery evidence from a different machine must additionally carry
the pinned surface binary version, platform identity, source-tree hash, bundle
hash, fixture hash, command transcript, and raw-output hash. Cursor/Augment
evidence missing any field leaves IM-11 and AC-3.2 open.

## Deterministic interfaces and acceptance commands

The implementation must provide read-only check modes. Acceptance commands
must fail on stale generated artifacts rather than silently rewriting them.

```bash
.venv/bin/python -m pytest -q \
  tests/test_skill_catalog_layers.py \
  tests/test_binding_loader.py \
  tests/test_extract_enum_binding.py \
  tests/test_distribution_surfaces.py \
  tests/test_skill_installer.py \
  tests/test_wp3_move_gate.py \
  tests/test_capability_consumers.py \
  tests/test_skill_activation.py \
  tests/test_skill_meta_jobs.py

.venv/bin/python scripts/skill_meta.py lint --strict --quiet
.venv/bin/python scripts/lint/no_core_framework_leakage.py --all
.venv/bin/python scripts/skill_installer.py catalog-check
.venv/bin/python scripts/skill_installer.py verify-bundle \
  --bundle tests/fixtures/wp3/bundles/v2
.venv/bin/python scripts/skill_installer.py exercise \
  --fixtures tests/fixtures/wp3/hosts \
  --bundle tests/fixtures/wp3/bundles/v2
.venv/bin/python scripts/distribution_probe.py verify-matrix \
  --fixtures tests/fixtures/wp3/surfaces \
  --evidence reports/portable-skill-ecosystem-completion/WP3/surface-matrix.json
.venv/bin/python scripts/wp3_move_gate.py fixture-check \
  tests/fixtures/wp3/move-gate
.venv/bin/python scripts/skill_installer.py replay-first-value \
  --fixture tests/fixtures/wp3/hosts/core-only \
  --max-seconds 1200 \
  --deny-read .claude/docs/quality-coordination-kernel.md

.venv/bin/python \
  .claude/skills/find-skill-intent-drift/scripts/scan.py \
  --strict --check-index
.venv/bin/python \
  .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate
.venv/bin/python scripts/decisions.py audit
.venv/bin/python scripts/decisions.py link-check
.venv/bin/python scripts/plans.py audit
.venv/bin/python scripts/specs.py coverage portable-skill-layer-distribution
.venv/bin/python scripts/specs.py inventory-check \
  portable-skill-layer-distribution
.venv/bin/ruff check <exact changed Python paths>
.venv/bin/python -m pytest
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
| AC-3.2 | projection exists but runtime cannot discover it; omitted surface; wrong version; source/hash-only instruction with no procedure; renamed trigger without alias; alias loop/collision/stale target; dangling contract/catalog path |
| AC-3.3 | global mixed-stack selection; first-installed winner; two same-precedence candidates; incompatible explicit choice; zero required match silently falls back; Vite inferred as React; malformed/tampered profile; root A binding selected for root B; evidence omits overlay |
| AC-3.4 | comparator normalizes a missing literal/site/risk; Django remains in core; wire values, ordering, or case variants change; invalid routing starts passing; only collector intermediate output is compared; absent binding passes |
| AC-3.5 | snapshots check counts but not names/content; inferred legacy core leaks framework content; TypeScript portfolio is empty or includes Django; Django loses an AR-1 name; mixed-root selection broadens globally |
| AC-3.6 | host file overwritten; traversal/symlink escape; corrupted checksum; partial update; retired owned path remains; modified owned file overwritten/deleted; second install/uninstall changes state; hidden network access; timing excludes setup; starter reads kernel |
| AC-3.7 | generic noisy `avoid:`; only one findings band checked; identifiers renamed while prose stays stale; unhandled self-anchor omitted; import smoke never reads the asset; staged-only rather than full-diff scan; directory accepted where file required; no fired-rule lesson; path moved before gate; ADR status/embodiment changed |

## Completion risks and stop conditions

- **Cursor/Augment discovery:** if exact-version tool-observed discovery cannot
  be produced, structural projection work may land but WP3 and AC-3.2 remain
  open. No simulation waiver exists in this spec.
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

This is a greenfield dependency-sized spec. The declared Python roots either
do not exist yet or are small existing prototypes. AR-1/AR-2 provide the
authoritative catalog inventory before implementation; `inventory-check` must
be rerun after the concrete symbols land.
