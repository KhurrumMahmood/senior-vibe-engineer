---
id: "0029"
namespace: core
title: View/page topology mirrors route structure; filenames strip the parent-folder prefix
status: proposed
date: 2026-06-09
provenance: "Promoted from a private host adaptation where this pattern is accepted and enforced; offered to core as a calibrated default."
revisit_when: ["find-folder-topology-drift route-axis Stage-2 bands are built in core"]
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [host:app/, .claude/skills/propose-folder-reorganization/, .claude/docs/folder-organization.md]
tags: [folder-organization, routes, topology]
related_smell: null
related_pattern: null
---

# View/page topology mirrors route structure; filenames strip the parent-folder prefix

> Proposed ADR — a calibrated starting point an adopting project confirms or supersedes. It
> is the route-axis **sibling** of `core:folder-organization`, which governs layer folders on
> the ≥3-sibling axis. This ADR adds the route-mirror axis for the layer reachable by a route.

## Context

A view/page layer — the directory whose modules render the responses a route resolves to —
has a property the rest of a codebase does not: every file in it already has a name in another
namespace, the **route**. When the on-disk shape and the route shape diverge, a reader who
knows one cannot predict the other, and each visit re-pays the cost of re-deriving "which file
serves this route?" (and its inverse).

Two skim-cost symptoms compound when the layer is grown flat:

- **Prefix-as-fake-folder.** A cluster of leaves names a coherent route area through a shared
  filename prefix (`<area>_overview`, `<area>_detail`, `<area>_settings`) rather than promoting
  that prefix to a folder. The prefix acts as a folder name without being one.
  `core:folder-organization` captures this for layer folders on the ≥3-sibling axis; it does
  not yet name the route-mirror axis where the prefix corresponds to a *route* segment.
- **Filename echoes its folder.** Even once `<area>_*` collapses into an `<area>/` folder, the
  leaves underneath can keep carrying the full prefix (`<area>/<area>_detail`). A reader
  scanning the listing re-reads the prefix at every leaf before reaching the variant. Once the
  folder boundary names the area, the prefix at the leaf carries zero additional information.

The governing principle: the folder topology of the view/page layer should **mirror the route
structure**, and a filename should **strip any prefix the parent folder already names** — so
the on-disk shape is predictable from a route, and a route is predictable from the on-disk
shape. This is the same property that makes a filesystem-routed framework's tree readable; the
point of this ADR is that the property is worth adopting **even where the framework does not
couple files to routes** — i.e. where the route table is the single source of truth and the
layout is free. That freedom is exactly the room this decision uses: the mirror is a convention
the team maintains, not a mechanism the framework enforces.

This ADR states the pattern for *any* route-mapped view layer. It does not assume
framework-specific routing (no file-based routing mechanism is a prerequisite, and no router
API is a hard dependency). Where a project's framework already couples files to routes, the
convention is already partly satisfied and this ADR is descriptive; where it does not, the
convention is prescriptive.

## Decision

The view/page layer's folder topology mirrors the route structure, and filenames omit any
prefix the parent folder already names. Four rules, in order of precedence:

1. **A top-level folder in the layer mirrors a route prefix.** A page/view folder maps to a
   route prefix one-to-one — route prefix `/<segment>/...` projects onto layer folder
   `<segment>/`. Folder names use the **route segment**, not internal jargon. The mapping is
   **informational, not strict**: not every folder must correspond to a route prefix (a one-off
   page below the cluster threshold may stay a single file), but every route prefix that owns
   **≥3** pages MUST have a matching folder — the same ≥3 `core:folder-organization` uses.
2. **Filenames inside a route folder OMIT the prefix the folder already names.** Under
   `<segment>/`, a leaf named `<segment>_detail` becomes `detail`. The full path is the
   namespace; the leaf is the variant. The path `<segment>/detail` reads the way the route
   `/<segment>/.../detail` reads.
3. **A file/sibling-asset pair collapses into a directory package.** Where the layer pairs a
   module (`<name>` source file) with a same-named sibling directory of associated assets
   (templates, co-located resources), the pair collapses so the folder is the unit: the module
   moves *into* the folder, and the asset root keeps the path any asset-discovery mechanism
   already expects. The mirror should not be defeated by a parallel file-beside-folder shape
   that repeats the area name twice.
4. **Parameter-level subfolders are adopted lazily, not pre-emptively, and use identifier-safe
   markers.** Where a route nests a parameter (`/<segment>/<id>/<child>/...`), a matching
   parameter subfolder is created **only when** the nesting depth makes the parameter
   load-bearing for skim. Do not create parameter folders pre-emptively for shallow routes. When
   one is warranted, the marker uses an **identifier-safe form** (e.g. `_id_/`) rather than a
   form whose characters are invalid module identifiers in the host language, so a parameter
   folder that later grows sibling modules imports cleanly. Independently, keep route parameters
   cleanly accessible to the views (a single resolution seam rather than per-view re-derivation),
   so the parameter-folder choice stays **cosmetic** — a skim aid — rather than changing how a
   parameter is read.

The rules apply to the route-mapped view/page layer specifically. `core:folder-organization`
governs layer folders generally, where the dominant axis is ≥3 same-prefix or same-domain
siblings; this ADR adds the **route-mirror** axis for the layer where the dominant axis is a
one-to-one route-prefix match.

## Alternatives considered

- **Status quo — flat layer with prefix-as-fake-folder names.** Rejected: the skim cost recurs
  on every visit and grows with the layer. `core:folder-organization`'s general ≥3-sibling rule
  doesn't name the route correspondence that makes the *right* folder name obvious — the route
  segment — so the route-mirror axis is worth stating explicitly.
- **Adopt a framework's file-based routing convention verbatim, including its parameter-bracket
  syntax.** Rejected as a hard rule: a convention using characters invalid as module identifiers
  forces every parameter folder to be asset-only and fragments the module tree. The
  navigability benefit survives without importing a foreign syntax — identifier-safe markers
  (Rule 4) keep the tree uniform. Adopt the *property* (path predicts route), not the *spelling*.
- **Create deep parameter folders now.** Rejected: adds depth before the value is real. The
  skim payoff rises with nesting depth; a layer whose routes are mostly shallow does not have
  that payoff yet. Defer — YAGNI.
- **Filename strip only, without the folder restructure.** Rejected as half the win: stripping
  the prefix from each leaf while the parent folder still carries the area prefix keeps the
  re-read cost.
- **Folder restructure only, without the filename strip.** Rejected as the inverse half-win:
  renaming the area folder to the route segment while leaves keep the prefix leaves the reader
  doing prefix arithmetic at every leaf to recover what the folder name already stated.

## Consequences

**Easier:**
- Skim-to-find: a listing of `<segment>/` shows the variants of the route (`detail`,
  `settings`, `overview`) with no prefix arithmetic. The path reads the way the route reads.
- Two-way navigability: a reader holding a route can locate the file by skimming the layer, and
  a reader holding a file can predict the route.
- One source of structure for both directions: a new page lands at `<segment>/<leaf>`; the route
  entry reads off the same path.

**Harder:**
- Every reference into the moved leaves updates — imports and any name-based asset references
  shift from the old prefixed name to the folder-relative name. The pair-collapse (Rule 3) is
  mechanical but cross-cutting (assets, includes, view code, the route table, any client that
  fetches an asset by name).
- Per `core:folder-organization`, conversions land **one cluster per route segment per change**,
  not as a single bulk move — a bulk reshape is unreviewable and clashes with in-flight branches.

**Now expected / now disallowed:**
- A new page lands at `<segment>/<leaf>`, where `<segment>` mirrors a route prefix — not named
  `<prefix>_<variant>` at the layer root when the prefix names a route shared with ≥2 other pages.
- A new leaf named `<prefix>_<variant>` under `<prefix>/` is disallowed (the prefix is implicit
  in the folder); a new root-level page sharing a prefix with ≥2 existing pages must collapse to
  a folder.

## Verification

- **Detector band.** `/find-folder-topology-drift` carries the route-axis bands as its deferred
  Stage-2 work (`route_folder_misalignment`, `same_domain_helper_sprawl`). This ADR is the
  case-law anchor those bands enforce when turned on: a route prefix owning ≥3 view modules not
  grouped under a matching `<segment>/` folder, and a leaf whose filename begins with its parent
  folder's name (`<segment>/<segment>_detail` → fail; rename to `<segment>/detail`). Read-only;
  output under `reports/find-folder-topology-drift/<scan-id>/`.
- **Proposal.** `/propose-folder-reorganization` consumes a confirmed route-axis finding and
  emits the per-segment current → proposed tree, file-move table, and reference-impact summary —
  the same EXPLAIN step the ≥3-sibling axis uses, applied to a route segment as the cluster unit.
- **Doc surface.** `.claude/docs/folder-organization.md` grows a "route-mirror axis" section
  beside its layer-folder rules — the rules, a generic worked example (`<segment>/detail` ↔ route
  `/<segment>/.../detail`), and the "adopt parameter folders lazily" guardrail — annotated as
  decided here and cross-referenced to `core:folder-organization` as its sibling.
- **Guard (deferred).** A commit-time lint that fires when a new leaf's filename begins with the
  same token as its parent folder. Promoted from detector band to hard guard only after the
  detector establishes the threshold is workable in practice — the same staging
  `core:folder-organization` uses for its cluster-collapse guard.
