---
id: "0027"
namespace: core
title: Preserve external wire identifiers across internal package moves
status: proposed
date: 2026-06-09
provenance: "Promoted from a private host adaptation where this pattern is accepted and enforced; offered to core as a calibrated default."
revisit_when: ["the wire-identifier-preservation AST lint is built in core"]
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [host:app/, .claude/skills/refactor-subsystem/]
embodied_by: ["pending:portable-skill-ecosystem-completion AC-7.7 formal disposition"]
tags: [refactor, wire-identity, stability]
related_smell: null
related_pattern: null
---

# Preserve external wire identifiers across internal package moves

## Context

A common refactor renames or relocates an internal package, module, or directory to
improve the on-disk layout: a folder is split, a namespace is flattened, files move
between subpackages. The intuitive expectation is that everything named after the old
location should be renamed in lockstep with it.

That expectation is wrong for one specific class of name: the **wire identifier** — any
string an *external* system binds to and resolves independently of the source-tree path
it happens to live near. Examples:

- A **task / job name** a message broker publishes and consumes by literal string
  (`work.run_report`), where in-flight messages already in the queue carry the old name
  across the deploy boundary.
- A **serialized type discriminator** — a type string written into stored JSON, an event
  envelope, or a schema registry — that older and newer readers both deserialize by
  exact match.
- A **stored reference** — a foreign-key-style string, a routing key, a namespace token,
  or a registry key — persisted in a database or config and resolved by lookup, not by
  import.

These identifiers share three properties: (1) they are **already decoupled** from the
filesystem in any mature system — the framework that resolves them offers an explicit
override (a name argument, a label override, a registered alias) precisely so the wire
name can diverge from the code path; (2) renaming the source path **does not** rename
them — the resolver does not consult the source tree; and (3) a single missed rename does
not fail loudly at the rename site — it surfaces later as a dropped message, a
deserialization error, or a dangling stored reference in a code path that is hard to
enumerate ahead of time.

So the move forces a fork: rename the wire identifiers *with* the package (cosmetic
consistency, real risk, real coordination cost — a queue drain, a data migration with no
rollback, a fleet-wide sweep), or hold the wire identifiers byte-stable while only the
source path moves. The cosmetic option buys nothing the running system can observe; the
cost is asymmetric — each missed identifier is a latent correctness bug across the deploy
boundary.

## Decision

**Wire identity is not filesystem layout. When an internal package or layout is renamed or
moved, the external wire identifiers other systems bind to stay byte-stable. The source
path is the only thing that moves.**

For each refactor that relocates code:

1. **Enumerate the wire-identifier surfaces first.** Before moving anything, list every
   identifier an external system resolves by string: broker task/job names, serialized
   type discriminators, stored string references, routing keys, namespace/registry keys.
   This list is the conserved set.
2. **Pin each surface with an explicit override at the new location.** Where the framework
   defaults the wire name to the code path, replace the implicit default with an explicit
   override that hard-codes the original string (a `name=` argument, an explicit label, a
   registered alias). The override is mandatory even when the current default would
   *happen* to produce the same string — the explicit form documents the intent and
   survives a later move without silent drift.
3. **Update only the import / dotted paths that other *source* depends on.** Internal
   references that resolve by import follow the code to its new home. References that
   resolve by wire string do not move.
4. **No compatibility shim at the old location.** Do not leave a re-export stub at the
   vacated path. A shim re-creates the very coupling the move was meant to remove and
   becomes a magnet for compatibility debt. Internal callers update to the new import path;
   external callers were never bound to the path — they are bound to the preserved wire
   identifier.
5. **A future flip of the wire identifiers is a separate decision.** Changing a wire
   identifier is its own ADR with a written argument that the cleanup payoff exceeds the
   migration cost (queue drain, irreversible data rewrite, coordinated dual-read window).
   The default going forward is preservation, indefinitely. Renaming the source tree never
   *implies* renaming a wire identifier.

This governs layout-only refactors. It does not forbid ever changing a wire name; it
forbids changing one *as a side effect* of moving code.

## Alternatives considered

- **Flip the wire identifiers in lockstep with the package, backed by a migration.**
  Rejected. The cosmetic gain does not survive the cost ratio: a migration that rewrites
  persisted identifiers typically has no rollback path, and a single fixture, config
  literal, or external consumer still emitting the old string surfaces as a late runtime
  failure in a path that cannot be exhaustively enumerated from the diff.
- **Flip some surfaces but not others.** Rejected: manufactures multiple competing
  conventions for "what the thing is called" — source path says one name, the broker
  another, the database a third. The refactor was supposed to reduce naming axes, not
  multiply them.
- **Flip only the broker/job names.** Rejected: renaming a live task name requires
  coordinating in-flight messages across the deploy — drain the queue (a stop-the-world
  window) or accept dropped messages (a correctness cost). Not worth a cosmetic rename.
- **Keep a re-export shim at the old path.** Rejected: re-introduces the layout coupling
  the move exists to remove, and invites new code to bind to it — recreating the smell on
  the next refactor.

## Consequences

**Easier:**
- The refactor becomes a mechanical relocation plus an import-path update — no data
  migration, no queue drain, no fleet-wide string sweep across persisted state.
- No deploy-time window in which in-flight messages fail to route or stored references
  dangle. External systems keep resolving the same strings across the deploy boundary.
- Subsequent internal restructures inside the new home are pure source refactors with zero
  external-migration cost, because wire identity was never tied to the layout.

**Harder:**
- Contributors must internalize that *source path ≠ wire identifier*. This ADR is the
  artifact that teaches the decoupling; keep it discoverable.
- A new contributor may forget the explicit override when adding a broker task, a
  serialized type, or a stored reference and silently re-couple it to the code path — the
  lint below catches this before merge.

**Now expected / now disallowed:**
- New code that registers a broker/job name declares the wire name explicitly
  (`name="<preserved.string>"`), not by relying on the module-path default; new serialized
  types declare an explicit, layout-independent discriminator; new stored references use
  the preserved namespace/label string.
- Re-introducing a re-export shim at any vacated path is disallowed.
- Changing a wire identifier as a side effect of a layout move is disallowed absent a
  dedicated superseding ADR.

## Verification

- **Characterization tests**, one per wire-identifier surface, each asserting the preserved
  string is still observable at the new location (broker registration carries the explicit
  override; a type serializes to/from its original discriminator; a namespace token still
  resolves). These invert only when a future ADR deliberately supersedes the preservation.
- **Lint (pre-merge AST rule)** named for this decision, firing on: a broker/job
  registration whose explicit wire-name override is missing or mismatched; a type/registry
  declaration whose discriminator is layout-derived; a namespace/label set to anything
  other than the conserved string.
- **Discoverability:** a one-line entry in the repository's shared context — *"Source path
  renames; wire identifiers don't. See core:wire-identifier-preservation."* — so the
  decoupling is searchable from the place contributors look first.
