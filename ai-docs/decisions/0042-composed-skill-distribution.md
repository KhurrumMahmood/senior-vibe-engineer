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
applies_to: [.claude/skills/, .augment/, .cursor/, .gemini/]
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
