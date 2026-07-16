---
id: "0042"
namespace: core
title: "Distribute one canonical catalog through versioned surface-specific installers"
status: accepted
date: 2026-07-16
deciders: [khurrum, codex]
assumes: ["supported agents do not share one native skill-discovery mechanism", "public invocation names and host-owned files must survive the migration", "ambient skill metadata consumes shared agent context"]
revisit_when: ["all supported agents adopt one compatible plugin/skill manifest", "a surface cannot consume a generated projection without hand-edited copies", "offline install/update/uninstall cannot be made transactional", "supported surfaces provide zero-cost lazy skill discovery with equivalent delegation"]
supersedes: []
superseded_by: null
applies_to: [.claude/skills/, host:.codex-plugin/, .augment/, .cursor/, .gemini/, .engineering/manifest.json]
embodied_by: ["script:scripts/installer_selection.py", "script:scripts/distribution_probe.py", "contract:tests/test_capability_consumers.py", "pending:WP3 builds the versioned installer, runtime discovery probes, aliases, update, and uninstall"]
tags: [distribution, installer, plugins, discovery, compatibility]
related_smell: product-topology-drift
related_pattern: null
---

# Distribute one canonical catalog through versioned surface-specific installers

## Context

ADR 0034 requires load-bearing layers, but supported agents discover skills and
instructions differently. Moving canonical skills into nested folders before
testing those mechanisms could hide invocations. Keeping manually synchronized
copies for Claude, Codex, Augment, Cursor, and Gemini would instead create a
permanent format-equivalence problem. Distribution must also work offline and
must not overwrite a host's instructions, manifest, hooks, settings, or ignore
rules.

## Decision

Use a composed distribution model:

1. The repository contains one canonical authored catalog and capability
   registry. During migration the source remains under `.claude/skills/`; its
   logical layer is registry/frontmatter data until discovery tests authorize
   physical moves.
2. A versioned installer reads an approved host profile, uses ADR 0041's
   selector, and materializes two distinct outputs: a content-addressed catalog
   store outside automatic discovery, and a surface-specific activation
   projection. Claude consumes a compatible skill directory; Codex consumes a
   plugin manifest/package; Augment consumes generated imported rules; Cursor
   and Gemini receive their supported project-instruction/discovery
   projections. Generated projections are never edited as canonical sources.
3. The supported-surface matrix and its discovery-contract versions live in
   ADR 0038's registry. “Supported everywhere” means exactly those pinned
   surfaces—not every current or future agent.
4. Release artifacts contain the core catalog, bindings, registry, installer,
   aliases, and checksums so base installation is offline. Optional analysis
   tools may require separately declared pinned packages and cannot silently
   downgrade a support claim when unavailable.
5. Install/update is staged and transactional: build in a temporary location,
   validate discovery/contracts, merge only owned files, then atomically switch
   the toolkit manifest. The manifest records every owned path and version.
   Uninstall removes only those owned paths. Host-owned collisions stop with a
   diff; they are never overwritten silently.
6. Public skill names stay stable. Path moves ship aliases for every supported
   surface until the compatibility matrix proves old and new invocation paths.
7. The default activation projection is **router-only**. It exposes
   `which-shape` and `which-skill` while keeping other selected portfolio
   procedures available in the catalog store without placing all of their
   headers into ambient agent context. A versioned `full-discovery` mode is an
   explicit opt-in compatibility choice, never the default.
8. Routing is deterministic and profile-aware. The router selects exactly one
   canonical procedure and its compatible binding set from the catalog. On a
   surface with local sub-agent support, substantial execution runs in a fresh,
   no-conversation-context worker that receives only the selected procedure,
   bindings, project root/runtime facts, and task-local inputs. The parent
   receives a bounded result or artifact, not the entire skill catalog.
9. Work requiring the parent's conversational state, user interaction, or
   authority may execute in the parent after loading only the selected
   procedure. Surfaces without sub-agents use the same selected-only local
   fallback. Direct public invocation remains available through explicit
   activation or `full-discovery` mode and retains alias compatibility.

## Normative routed-activation contract

The following requirements are part of this decision, not implementation
latitude. The successor spec may add tests and schemas but cannot choose
different public behavior without amending this ADR.

### Surface identities and bootstrap

Canonical logical names remain `which-shape` and `which-skill`. Surface syntax
and projection identity are fixed as follows; aliases substitute their public
name into the same syntax and location.

| Surface | Exact public bootstrap form | Exact generated identity | Native behavior |
|---|---|---|---|
| Claude Code | `/which-shape`, `/which-skill` | `.claude/skills/<public-name>/SKILL.md` | native named skill |
| Codex | `$engineering-skills:which-shape`, `$engineering-skills:which-skill` | plugin `engineering-skills`, `skills/<public-name>/SKILL.md` | native namespaced skill |
| Augment | `use skill which-shape`, `use skill which-skill` | `.augment/rules/imported/<public-name>/SKILL.md` | explicit prompt identifier backed by an imported rule |
| Cursor | `use skill which-shape`, `use skill which-skill` | `.cursor/rules/<public-name>/SKILL.mdc` | explicit prompt identifier backed by a project rule |
| Gemini | `use skill which-shape`, `use skill which-skill` | `.gemini/skills/<public-name>/SKILL.md` | explicit prompt identifier backed by a discovered skill |

The versioned surface registry must repeat this contract with the pinned
runtime version, projection format, discovery command/parser, alias form,
activation operation, and worker capability. A surface is not verified when
it can only prove file presence. Instruction-backed surfaces must demonstrate
that the exact explicit prompt identifier selects the named instruction and an
unselected identifier does not. Host-owned skills/rules remain visible but are
counted separately from the toolkit-owned set.

The bootstrap projection contains the two complete router procedures plus
their declared non-skill runtime files. Those supporting files are not skill
headers. It also contains a manifest-relative catalog locator, manifest schema
version, and the expected manifest, bundle, inventory, registry, profile, and
router hashes. Routers resolve the non-discovered catalog only through that
locator; they may not search ambient skill roots, assume a checkout-relative
`.claude/skills` path, or trust the working directory. They verify the locator,
manifest, selected catalog row, and rendered content before reading catalog
frontmatter or loading a procedure. Missing, stale, corrupt, traversing, or
incompatible data fails closed without loading a body or changing activation.

### Dispatcher and deterministic selection

`which-shape` remains an advisory shape router. It never counts as selecting a
procedure and may return alternatives or request clarification. `which-skill`
remains an advisory ranker. A versioned dispatcher consumes their structured
outputs and terminates in exactly one of `selected`,
`clarification_required`, `proceed_directly`, or `error`:

- `selected` contains one canonical procedure. It is automatic only when one
  compatible candidate is strictly highest by the pinned scorer and above its
  pinned threshold, or when the user explicitly supplies one canonical public
  name or alias. Directory, registry, discovery, and installation order are
  never tie-breakers.
- A score tie, low-confidence shape, or multiple procedures required at the
  same step returns `clarification_required`; the parent asks one
  discriminating question without loading candidate bodies. User selection is
  then recorded as the confirmation that authorizes one procedure.
- `proceed_directly` loads no procedure. Invalid profile/catalog data,
  incompatible binding selection, or router failure returns `error` and is
  never converted to `proceed_directly` or parent fallback.

Task input identifies one canonical project root or an explicit ordered root
set. The dispatcher selects one canonical procedure and ADR 0041's ordered
binding sequence independently for every selected root. Mixed-root work may
therefore use one procedure with different per-root overlays; if it requires
different procedures, the dispatcher serializes them as separate selections
and task packs after user confirmation. A selected procedure is loaded only by
the dispatcher after deterministic routing or by the explicit named-activation
path below. This resolves the earlier shorthand that said every non-router
body loads only after routing.

### Named activation and unchanged invocation

The offline installer exposes versioned `activate`, `deactivate`, `mode`, and
`rollback` operations on every surface adapter. `activate <public-name>` adds
one persistent activation record `{public_name, canonical_target}`;
activations are cumulative, project-scoped, and idempotent. `deactivate`
removes only the named public record. Alias input is canonicalized for profile
and binding checks while the requested alias remains the discovered public
name. Activating both a canonical name and an alias intentionally exposes two
public names backed by one canonical procedure.

`activate --temporary <public-name> --invocation-id <id>` creates a one-shot,
invocation-scoped projection and removes it after success, failure,
cancellation, or startup recovery. It does not alter the persistent set.
Router-selected worker execution reads directly from the store and never
changes ambient activation. Unknown, incompatible, collided, cyclic, stale,
or changed-target aliases fail before mutation. After activation, the user
invokes the exact unchanged surface form in the table; this two-step path is
the router-only interpretation of AC-3.2's invocation-compatibility promise.
`full-discovery` exposes the complete selected canonical portfolio plus every
declared public alias, while `router-only` exposes the two routers plus the
persistent/temporary named set.

### Delegation, task packs, and fallback

The surface registry declares `fresh_worker: verified|unsupported`, exact
launcher/API and version range, selected-procedure injection, cancellation and
result mechanisms, and a native proof of zero inherited conversation turns.
Runtime success may not invent this capability. Every distributable catalog
row declares `execution_class: inline|substantial` and enumerated parent
requirements. A substantial selection must use a verified fresh worker unless
the dispatch record contains exactly one allowed reason:
`conversation_state_required`, `user_interaction_required`,
`nondelegable_authority_required`, or `surface_worker_unsupported`.

Spawn failure, timeout, capacity exhaustion, cancellation, and budget
exhaustion are typed execution failures, not automatic parent-fallback
reasons. Retrying or moving such work into the parent requires explicit user
confirmation so side effects are not duplicated. A surface that cannot inject
one selected procedure without broad discovery is unsupported for this mode;
it may not silently switch to `full-discovery`. An allowed parent fallback
uses the same selected-only pack and result contract as a worker.

`DispatchPackV1` is canonical UTF-8 JSON of at most 131,072 bytes. It contains
schema/policy versions, canonical skill and public request, bundle/source/
rendered hashes, ordered per-root binding IDs and hashes, explicit roots,
normalized task arguments, allowlisted non-skill runtime dependencies,
execution lane and fallback reason, and budgets. It contains no frontmatter,
body, binding, example, or knowledge from another skill. The two bootstrap
headers and platform/system/host instructions that a surface injects outside
the pack are enumerated separately in evidence. “Fresh” means zero inherited
conversation turns, not absence of those declared platform instructions.

`DispatchResultV1` is canonical UTF-8 JSON of at most 65,536 bytes with one of
`success`, `needs_input`, `needs_authority`, `failed`, or `cancelled`, a bounded
summary, content-addressed artifact references, hashes, and error metadata.
Large result bodies remain out-of-band. Oversize packs fail before launch;
oversize results become `failed` and are never silently truncated. Default
policy is one worker, delegation depth one, one attempt, a 1,200-second
deadline, at most 32,768 total model tokens and 8,192 output tokens, and no
detached work. A worker cannot activate skills, redispatch routers, or spawn a
child. A surface unable to enforce and report those limits is not a verified
fresh-worker surface. Multi-skill loops return to the dispatcher and create a
new bounded pack for each serial selection.

### Lifecycle, migration, offline scope, and privacy

Lifecycle state is the tuple `(bundle_version, catalog_hash, mode,
activation_records, surface_set, manifest_generation)`. The manifest owns and
hashes catalog-store objects, bootstrap projections, named/full projections,
activation records, recovery journal, and generated internal links separately.
The transaction boundary is the complete requested surface set. Every install,
local update/downgrade, rollback, uninstall, activation/deactivation, and mode
transition holds one project lifecycle lock, stages and validates the full next
generation, then commits one manifest generation. No command reports success
until each adapter's declared offline, non-model post-commit discovery check
matches the requested set; a surface without such a check is unsupported for
the transactional lifecycle. Separate exact invocation evidence may use the
pinned surface runtime/model outside the deterministic lifecycle command, but
is still required before support verification and cannot repair a failed
transaction. Failure restores the exact prior manifest, tree, discovery set,
and activation records; startup recovery completes that restoration before
accepting another command.

Updates preserve activation records only when public name, alias target,
applicability, and binding hashes still validate; otherwise they stop before
mutation with a diff. Modified owned content causes an all-or-nothing stop.
Rollback retains the current and immediately previous validated generation.
Garbage collection removes only unreferenced, unmodified, manifest-owned store
objects after a successful commit; uninstall follows the same rule. Side-by-
side versions in one surface namespace are rejected. Every target and ancestor
is checked with `lstat`: host-owned symlinks and symlink escapes are rejected.
Toolkit-generated links are allowed only when the manifest records link and
resolved-target hashes, the target stays inside an owned store, and the pinned
surface discovery probe proves link traversal; otherwise the adapter must use
owned directories plus the recovery journal.

Migration recognizes each supported pre-amendment ambient layout and previous
toolkit manifest. Preview classifies every path as known byte-identical toolkit
content, modified known content, or host/unknown content. Only the first class
may be adopted or retired automatically; either other class stops with a diff.
A router-only migration cannot succeed while legacy toolkit headers remain
ambient. The bundle pins compatible manifest-reader, catalog, router,
delegation-policy, and surface-version ranges. Unsupported versions fail
closed and never select full discovery. Downgrade uses an explicitly supplied
compatible local bundle and the same validation; changed alias targets or
stale activations stop before mutation.

Install, verify, local-bundle update/downgrade, rollback, uninstall, activate,
deactivate, mode transition, catalog lookup, and deterministic routing perform
no network access, package-manager action, model call, or download. Selected
procedure execution is outside that installer-offline claim and must separately
declare any network/tool requirement.

Persistent manifests, telemetry, and acceptance evidence contain only task/
result hashes and lengths, schema versions, canonical/public names, bindings,
lane, status, budgets, and artifact hashes—not raw prompts, conversation,
source snippets, procedure bodies, credentials, or result bodies. Raw task or
result artifacts are ephemeral by default and deleted after result handoff.
Explicit user-requested retention is host-local, mode `0600`, and records its
retention/deletion policy; telemetry never transmits it. Acceptance includes a
canary secret that must be absent from manifests, logs, evidence, stdout, and
errors.

`scripts/installer_selection.py` is the WP1 selection prototype. WP3 builds the
filesystem materializer and surface discovery probes before any catalog-wide
move; WP8 performs the rollout only after the exemplar invalidation window.

## Alternatives considered

- **Codex plugin only.** Rejected because it abandons the other named surfaces
  and makes the taxonomy depend on one vendor mechanism.
- **One nested directory layout for every agent.** Rejected until discovery is
  proven; current surfaces do not promise identical recursion/manifest rules.
- **Keep the flat catalog forever.** Rejected because layers would remain
  decorative and hosts could not install only applicable bindings.
- **Hand-maintain one copy per surface.** Rejected because drift is inevitable
  and fixes would need N edits.
- **Online bootstrap that downloads current files.** Rejected as the only path
  because it is not reproducible or offline and makes rollback/uninstall
  ambiguous.
- **Overwrite host configuration with toolkit defaults.** Rejected because
  host-owned instructions and safety settings are outside installer authority.
- **Expose every installed skill through automatic discovery.** Rejected as the
  default because even metadata-only headers consume shared context and make
  unrelated work pay for the whole catalog. Retained only as an explicit
  compatibility mode.
- **Always execute routed work in the parent.** Rejected because independent
  maintenance workflows can be isolated with a bounded task pack. Parent-local
  execution remains the fallback when context or authority cannot be delegated.

## Consequences

The catalog has one authored source while each agent receives a native-enough
projection. Offline installs, upgrades, rollback, and uninstall can be tested
from manifests. The installer becomes a critical compatibility component and
must maintain surface adapters, checksums, merge semantics, and aliases.
Physical layer moves are delayed until discovery evidence exists. Manual
projection edits, untracked owned paths, and destructive host-file replacement
are disallowed. Installation no longer implies ambient activation: manifests
must separately own the catalog store, bootstrap projection, optional explicit
activations, and delegation/fallback policy. This adds routing and context-budget
tests to the release boundary.

## Verification

The WP1 prototype and consumer test prove registry-driven selection. WP3 must
add cold-host fixtures for every supported surface, offline install, update,
uninstall, collision preservation, alias invocation, and discovery. Those
tests replace the pending embodiment before this decision is considered fully
productized. The default fixture must expose only `which-shape` and
`which-skill`, prove all other portfolio procedures remain selectable from the
non-discovered store, demonstrate selected-only fresh-worker execution and
selected-only parent fallback, and show `full-discovery` requires an explicit
mode change.
