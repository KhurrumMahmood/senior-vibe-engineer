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
headers. It also contains fixed `schema_version: 1`, a manifest-relative
catalog locator, and the externally rooted release-root and bundle-index
digests that bind inventory, registry, profile, and router content. It never
contains an expected installed-manifest digest. Routers resolve the non-
discovered catalog only through that locator; they may not search ambient skill
roots, assume a checkout-relative `.claude/skills` path, or trust the working
directory. They verify the locator,
manifest, selected catalog row, and rendered content before reading catalog
frontmatter or loading a procedure. Missing, stale, corrupt, traversing, or
incompatible data fails closed without loading a body or changing activation.

The trust graph is acyclic and has one external root. Installation requires an
out-of-band `expected_release_root_sha256` for canonical
`release-root-v1.json`; the root document has no self-digest and hashes
`bundle-index-v1.json`, the installer entrypoint, the surface contract, all
eight schemas—release root, bundle index, installed manifest, surface
activation contract, `WhichShapeResultV1`, `WhichSkillResultV1`,
`DispatchPackV1`, and `DispatchResultV1`—and the alias/legacy/compatibility
tables.
`bundle-index-v1.json` hashes raw catalog, registry, router, procedure, binding,
asset, and projection-recipe blobs. It does not hash the mutable installed
manifest or generated bootstrap projections. The installed manifest records
the verified release-root and bundle-index digests, state, and generated file
hashes; its `manifest_sha256` is computed over the document with only that
field omitted. A generated bootstrap's exact content set is its surface
identity, fixed `schema_version: 1`, relative manifest locator, release-root
and bundle-index digests, the complete `which-shape` and `which-skill` router
procedures, and every declared non-skill runtime file needed by those
procedures. Router procedure and runtime bytes are generated only from bundle-
indexed immutable blobs or projection recipes. The installed manifest hashes
every generated bootstrap file's raw bytes, including the bytes encoding
`schema_version: 1`, and a
bootstrap tree digest over all and only its `{path,size,sha256}` rows using the
tree-digest rule below. No bootstrap field or embedded file contains the
installed-manifest digest. The manifest may hash the bootstrap
because the bootstrap never hashes the manifest. Runtime
verification follows `out-of-band root → release root → bundle index → immutable
blobs/recipes → self-hashed installed manifest → generated projections`; no
edge points backward and no digest is accepted merely because two mutable
documents agree.

As IM-14 phase 1, before installer or dispatcher code consumes these
contracts, exact draft-2020-12 schemas with recursive
`additionalProperties: false` are checked in for all eight records: release root, bundle index,
installed manifest, surface activation contract, `WhichShapeResultV1`,
`WhichSkillResultV1`, `DispatchPackV1`, and `DispatchResultV1`. Authoring and
validating those schemas is the first implementation phase, not work blocked
by this prerequisite. The release root hashes each schema raw blob. The
installed-manifest schema requires exactly the forward digests, complete state
tuple, owned-path classes, generated-file rows, recovery/cleanup state, and its
single self-digest field; adapters cannot add private trust fields.

All schema-governed JSON uses RFC 8785 JSON Canonicalization Scheme UTF-8 bytes
after exact-schema validation; duplicate keys, unknown fields, non-integer
numbers, invalid Unicode, and non-canonical encodings are rejected. SHA-256 is
lowercase hexadecimal. Ordinary file digests cover raw bytes. A tree digest
covers the RFC-8785 serialization of a list of `{path, size, sha256}` records
sorted by the UTF-8 bytes of NFC-normalized, relative POSIX paths; empty,
absolute, dot-segment, backslash, duplicate, symlink, and non-NFC paths are
invalid. A self-digest domain omits exactly its named digest field and nothing
else. Evidence records use the same rule and name their digest domain. These
rules apply before any implementation-specific object parsing or rendering.

### Dispatcher and deterministic selection

`which-shape` remains an advisory shape router. It never counts as selecting a
procedure and may return alternatives or request clarification. `which-skill`
remains an advisory ranker. In IM-14 phase 1, before dispatcher code consumes
router output, the repository must check in exact additional-properties-false
JSON Schemas named
`WhichShapeResultV1` and `WhichSkillResultV1`; malformed or unknown-field router
output is an error.

Both routers use task normalizer `ascii-wordset-v1`: strict UTF-8 input is
lowercased, matched with `[a-z][a-z0-9_-]+`, filtered by the exact checked-in
v1 stopword array and tokens of length one, deduplicated, and serialized in
UTF-8 byte order. The shape scorer is `which-shape-lexical-v1`: shape-registry
strong/normal/negative weights are `+12/+4/-10`, registered boost rules apply
in declared order, missing non-exempt context is `-4`, confidence is high at
score `>=40`, medium at `>=24`, and low below `24`. Equal top shape scores and
low confidence require clarification. The skill scorer is
`which-skill-overlap-v1`: best-for overlap `+5`, not-for overlap `-10`,
description/name overlap excluding best-for hits `+2`, exact tier `+8`, cross-
cutting tier `+3`, and exact job `+6` per hit/rule as currently defined; its
numeric selection threshold is `5`. Scorer inputs, stopword array, weights,
registry, and implementation raw-byte hashes are bundle-indexed; changing any
requires a new ID and compatibility entry.

Within `which-skill-overlap-v1`, `quick=true` exactly when normalized tokens
intersect the checked-in v1 quick-hint array, except that simultaneous
intersection with the checked-in skill-development subject and action arrays
overrides tier/job to `cross-cutting/plan` before the quick short-circuit. The
checked-in job/tier/obligation hint maps and their iteration order are also
scorer inputs; no synonym or model inference is permitted under this ID.

`WhichShapeResultV1` has exactly `schema_version`, `router_id`,
`normalizer_id`, `task_sha256`, `profile_sha256`, `status`, `candidates`, and
`error`. Status is `ok|clarification|required_context|error`; error is null or
an enum code. Candidates contain exactly `shape_id`, signed 32-bit integer
`score`, `confidence: high|medium|low`, and 0–16 enum rationale codes; there are
0–256 candidates sorted by descending score then UTF-8 shape id, preserving
equal scores. `WhichSkillResultV1` has exactly `schema_version`, `router_id`,
`normalizer_id`, `scorer_id`, `threshold`, `task_sha256`, `profile_sha256`,
`quick`, `status`, `candidates`, `excluded`, and `error`. Status is
`ok|proceed_directly|error`; candidates contain exactly canonical/public name,
signed 32-bit score, applicability, per-root ordered binding ids/hashes, and
0–16 rationale codes; excluded rows contain the same names plus 1–16 enum
exclusion codes. Each list is 0–256 rows, sorted by descending score then UTF-8
canonical/public name without discarding ties. IDs use the 64-byte grammar
defined below and digests are lowercase SHA-256. The schemas set recursive
`additionalProperties: false`; full conversational rendering is outside these
dispatcher-input records.

A versioned dispatcher validates those router results and terminates according
to this total table; no unlisted combination is accepted:

| Input condition, in precedence order | Outcome |
|---|---|
| Malformed task/router/profile/catalog/binding data, unknown schema field, failed router, explicit unknown/incompatible name, or zero compatible candidates because required applicability/binding constraints excluded them | `error` |
| User answers a prior clarification with one valid canonical name or alias | `selected` with `selection_basis=user_confirmed` and the prior clarification id |
| Explicit valid canonical public name or alias supplied by the user | `selected` with `selection_basis=user_explicit` |
| Shape `clarification|required_context`, shape top-score tie, shape score below 24, or a step requiring simultaneous different procedures | `clarification_required` |
| Valid quick classification, or compatible ranked candidates exist but every score is below 5 | `proceed_directly` |
| One compatible skill is the sole highest scorer at or above 5, including when other lower candidates also exceed 5 | `selected` with `selection_basis=unique_winner` |
| Two or more compatible skills tie for highest score at or above 5 | `clarification_required` |

`selected` contains exactly one canonical procedure. Directory, registry,
discovery, installation, and input enumeration order are never tie-breakers.
For `clarification_required`, the parent asks one discriminating question
without loading candidate bodies. `proceed_directly` loads no procedure.
`error` is never converted to `proceed_directly` or ordinary parent fallback.

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
Temporary activation is supported on a surface only when its pinned adapter
has a verified terminal callback or wrapper that owns the entire invocation.
The lowercase UUIDv4 invocation id correlates journal states
`created → exposed → running → terminal → cleaned`; the callback accepts the
same id plus one terminal result status, removes the projection under the
lifecycle lock, verifies native discovery no longer exposes it, and only then
marks `cleaned`. Before agent discovery on every startup, the wrapper removes
all non-cleaned temporary records and projections and records crash cleanup.
A surface unable to run that pre-discovery cleanup and terminal callback must
declare `temporary_activation: unsupported`; it may still support persistent
activation but cannot emulate temporary activation with best-effort cleanup.
Router-selected worker execution reads directly from the store and never
changes ambient activation. Unknown, incompatible, collided, cyclic, stale,
or changed-target aliases fail before mutation. After activation, the user
invokes the exact unchanged surface form in the table; this two-step path is
the router-only interpretation of AC-3.2's invocation-compatibility promise.
`full-discovery` exposes the complete selected canonical portfolio plus every
declared public alias, while `router-only` exposes the two routers plus the
persistent/temporary named set.

The manifest `mode` enum is exactly `router-only|full-discovery`. There is no
`named`, `temporary`, or hybrid mode: persistent and temporary public names are
activation records orthogonal to mode. In `router-only` they add to the two
routers; in `full-discovery` a record already present through the full set is
deduplicated by exact public name without changing its canonical target.

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

Initial parent execution may use only the four reasons above. A worker terminal
failure binds a schema-valid `DispatchResultV1` whose status is `failed` or
`cancelled`, the prior `dispatch_id`, `workflow_pack_ordinal`,
`attempt_ordinal: 1`, consumed time/input/output tokens, and
`side_effect_disposition` (`none`, `rolled_back`, `committed_known`, or
`unknown`). Status `failed` requires exactly one of `spawn_failed`,
`capacity_exhausted`, `timeout`, `budget_exhausted`, or `worker_failed`; status
`cancelled` requires `failure_kind: cancelled`. `unknown` prohibits retry or
fallback. `committed_known` permits only a parent continuation with a content-
addressed side-effect ledger and user-confirmed `resume_without_repeating`
plan. `none` or `rolled_back` permits either a confirmed fresh-worker retry or
a confirmed selected-only parent continuation.

Both continuations hash the terminal result and exact retry/resume plan, use a
new `dispatch_id`, the same `workflow_id` and `workflow_pack_ordinal`,
`attempt_ordinal: 2`, `prior_dispatch_id`, and only the remaining cumulative
deadline/token budget. A worker retry has `execution_lane: fresh-worker`,
`fallback_reason: null`, and
`continuation_reason: user_confirmed_worker_retry`. A parent continuation has
`execution_lane: selected-only-parent`,
`fallback_reason: user_confirmed_after_worker_failure`, and
`continuation_reason: user_confirmed_parent_continuation`. Reusing a dispatch
id, resetting a budget, omitting the side-effect disposition, creating a third
attempt for the pack, or starting a second concurrent lane fails closed.

As part of IM-14 phase 1, before dispatcher code consumes them, exact checked-
in draft-2020-12 JSON Schemas `dispatch-pack-v1.schema.json` and
`dispatch-result-v1.schema.json` must set
`additionalProperties: false` recursively, require every field, and encode the
following closed contracts. Both documents use the RFC-8785 canonicalization
and digest domains above. Unknown/missing fields, duplicate keys, noncanonical
JSON, or a schema/digest mismatch fail before execution or result handoff.

`DispatchPackV1` is at most 131,072 canonical bytes. `workflow_id`,
`dispatch_id`, `prior_dispatch_id`, `invocation_id`, and clarification ids are
lowercase UUIDv4 strings; absent optional relationships are JSON `null`.
`workflow_pack_ordinal` is an integer from 1 through 16, and
`attempt_ordinal` is `1|2`. `execution_lane` is
`fresh-worker|selected-only-parent`; `continuation_reason` is exactly one of
`initial_selection`, `confirmed_sequence_step`,
`user_confirmed_worker_retry`, or `user_confirmed_parent_continuation`;
`fallback_reason` is null, one of the four initial parent reasons, or
`user_confirmed_after_worker_failure`, with the combinations constrained as
above.
Canonical/public skill and binding IDs match
`[a-z0-9][a-z0-9-]{0,63}`. Hashes are 64 lowercase hex characters. There are
1–32 normalized absolute project roots, each at most 4,096 UTF-8 bytes; at most
16 ordered bindings per root; task arguments are one string of at most 65,536
UTF-8 bytes; and at most 64 dependency records have a relative POSIX path of at
most 1,024 bytes, raw-byte hash, size, and media type. The selected procedure
is delivered explicitly as one UTF-8 `procedure.body` of at most 65,536 bytes
plus its raw/rendered hashes. Selected binding bodies are delivered inline in
declared order, each at most 32,768 bytes and still subject to the whole-pack
limit. Supporting scripts/assets are not ambient instructions: dependencies
are read-only content-addressed files under the verified catalog store and are
accepted only when path, size, and raw hash match the bundle index. No
frontmatter, body, binding, example, or knowledge from another skill may
appear. The two bootstrap headers and platform/system/host instructions that a
surface injects outside the pack are enumerated separately in evidence.
“Fresh” means zero inherited conversation turns, not absence of those declared
platform instructions.

`DispatchResultV1` is at most 65,536 canonical bytes and repeats the exact
`workflow_id`, `dispatch_id`, `prior_dispatch_id`, `workflow_pack_ordinal`,
`attempt_ordinal`, `execution_lane`, `continuation_reason`, and
`fallback_reason` from its pack. It has one of `success`, `needs_input`,
`needs_authority`, `failed`, or `cancelled`. Summary is at most
8,192 UTF-8 bytes; error code/message are at most 128/2,048 bytes; token and
timing counters are nonnegative integers; and there are at most 16 artifact
records. An artifact record has exactly `uri`, `name`, `media_type`, `size`,
and `sha256`: URI grammar is
`artifact://sha256/<64-lowercase-hex>`, name is a single safe POSIX segment of
at most 255 bytes, each regular-file artifact is at most 16 MiB, and aggregate
artifact bytes are at most 64 MiB. Before handoff, the result wrapper uses
`lstat`, rejects symlink/hard-link/non-regular/escaped objects, resolves the
object beneath the invocation artifact root, verifies size/raw hash/URI, and
opens without following links. Large bodies remain out-of-band. Oversize packs
fail before launch; invalid or oversize results become a minimal schema-valid
`failed` result and are never truncated or trusted.

The default project-wide execution policy permits one active worker or parent
execution lane across all dispatcher workflows, enforced by one dispatch lock.
Delegation depth is one and each dispatch has one attempt. A user-confirmed
ordinary serial procedure sequence has at most 16 packs: each selected
procedure receives a new `dispatch_id`, the next `workflow_pack_ordinal`,
`attempt_ordinal: 1`, and `continuation_reason: confirmed_sequence_step` (the
first uses `initial_selection`). This is an ordinary sequence step, not a
retry or fallback. Each workflow pack may have at most one second dispatch,
and only through the typed user-confirmed worker-terminal-failure path above;
that dispatch keeps the pack ordinal and uses `attempt_ordinal: 2`. The
1,200-second deadline starts on the local monotonic clock when the
dispatcher first accepts task input, before either router runs, never pauses,
and is not reset by clarification, retry, fallback, or restart. The workflow
budget is cumulative across worker and parent dispatches: at most 32,768 total
reported model tokens where total means input plus output, including system,
tool, failed, and cancelled attempts, and at most 8,192 output tokens. A retry
receives only the unspent time/token balance. The same trusted wrapper enforces
the lock, deadline, and counters in worker and parent lanes; missing or
unenforceable parent/worker accounting fails closed. No detached work is
allowed. A worker cannot activate skills, redispatch routers, or spawn a child.
Multi-skill loops return to the dispatcher and create a new bounded pack under
the same workflow budget for each serial selection; they never reuse a pack
ordinal or consume the failure-continuation attempt merely by advancing the
confirmed sequence.

### Lifecycle, migration, offline scope, and privacy

Lifecycle state is the tuple `(bundle_version, catalog_hash, mode,
activation_records, surface_set, manifest_generation)`. The manifest owns and
hashes catalog-store objects, bootstrap projections, activation/full-discovery projections,
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

In IM-14 phase 1, before installer/dispatcher/lifecycle code consumes them, the
repository checks in exact, schema-closed `aliases-v1.json`,
`legacy-layouts-v1.json`, and
`compatibility-v1.json`. The alias table lists every public alias, canonical
target, surface spelling, introduced version, and retirement version; an empty
table is explicit and no alias may be inferred from directories or prose. The
closed alias row is exactly `{public_name, canonical_target, surface_spellings,
introduced_release, retirement_release}`. `public_name`, `canonical_target`,
and each surface spelling use the lowercase hyphenated public-name grammar;
`surface_spellings` has exactly `claude-code`, `codex`, `augment`, `cursor`,
and `gemini`, and every value must equal `public_name`; no row can create
surface-specific alias divergence. `introduced_release` is a positive integer;
and `retirement_release` is null
or an integer greater than or equal to it. Surface adapters add their declared
namespace or literal-instruction syntax around that spelling.

When the production alias table is empty, alias activation is not fabricated:
each portfolio/surface snapshot records exactly
`{available: false, reason: no_alias_declared, activation_records: []}` for
both named-alias and cumulative canonical-plus-alias states. This is an honest
absence, not support evidence. Alias-mechanism conformance is still mandatory
and uses one fixture-only row—`plan-feature-v1` targeting `plan-feature`, all
five spellings `plan-feature-v1`, introduced release 1, retirement null. That
row is injected only into the contract test, is never written to
`aliases-v1.json`, and cannot enter a release, bundle, catalog, projection, or
runtime discovery set. A production alias guarantee begins only after an
explicit accepted table row exists.

The
legacy inventory lists every supported layout/manifest id, exact version or
closed version range, path set, known release-root/tree hashes, ownership
markers, and migration action. An unlisted layout/version/hash is unknown, not
the nearest known version.

The initial compatibility table has closed values: release-root, bundle-index,
installed-manifest, alias, legacy-layout, dispatcher-policy,
`DispatchPackV1`, and `DispatchResultV1` schemas are exactly version 1;
catalog inventory, capability registry schema/contract, and the accepted WP2
host-profile schema are exactly 1; router IDs are exactly
`which-shape-lexical-v1` and `which-skill-overlap-v1`; Claude Code is exactly
`2.1.211`, Codex exactly `0.144.1`, Augment exactly `imported-rules-v1`, Cursor
exactly `project-rules-v1`, and Gemini exactly `0.45.0`. Every range has both
lower and upper bounds even when equal. Widening any bound or changing an ID is
a versioned compatibility-table change with fixtures, never runtime inference.
The table cannot predeclare a future host-profile schema that the accepted WP2
reader neither emits nor accepts.

Migration recognizes only entries in that legacy inventory. Preview classifies
every path as known byte-identical toolkit content, modified known content, or
host/unknown content. Only the first class may be adopted or retired
automatically; either other class stops with a diff. A router-only migration
cannot succeed while legacy toolkit headers remain ambient. Unsupported
versions fail closed and never select full discovery. Downgrade uses an
explicitly supplied compatible local bundle and the same validation; changed
alias targets or stale activations stop before mutation.

Install, verify, local-bundle update/downgrade, rollback, uninstall, activate,
deactivate, mode transition, catalog lookup, and deterministic routing perform
no network access, package-manager action, model call, or download. Selected
procedure execution is outside that installer-offline claim and must separately
declare any network/tool requirement.

Persistent manifests, telemetry, and acceptance evidence contain only task/
result hashes and lengths, schema versions, canonical/public names, bindings,
lane, status, budgets, and artifact hashes—not raw prompts, conversation,
source snippets, procedure bodies, credentials, or result bodies. Raw task or
result staging is created under process umask `077`: invocation directories and
retained-artifact directories are mode `0700`, every pack/result/journal/raw
file is mode `0600`, and symlinks/hard links are prohibited. Raw pack,
procedure/binding copies, task input, stdout/stderr, intermediate result, and
unretained artifact files are deleted after handoff on every terminal status—
`success`, `needs_input`, `needs_authority`, `failed`, and `cancelled`—and by
startup recovery before activation recovery or new dispatch. Cleanup failure
keeps the workflow failed and blocks another dispatch.

The recovery journal is schema-closed, mode `0600`, and contains only ids,
state enums, relative staging paths, hashes, lengths, budgets, and cleanup
status; it may never contain raw inputs, bodies, output, credentials, or
artifact content. Explicit user-requested retention transactionally promotes a
verified artifact out of raw staging into a separate host-local `0700` root
with `0600` files and records owner, digest, expiry/deletion policy, and user
confirmation. Journal cleanup never deletes a promoted artifact but does
delete every raw source copy. Telemetry never transmits retained content.
Acceptance includes a canary secret that must be absent from manifests,
journals, logs, evidence, stdout, errors, and post-terminal raw staging.

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
