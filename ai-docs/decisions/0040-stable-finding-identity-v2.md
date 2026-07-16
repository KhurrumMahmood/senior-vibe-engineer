---
id: "0040"
namespace: core
title: "Finding identity is schema-versioned, language-namespaced, and anchored semantically"
status: accepted
date: 2026-07-16
deciders: [khurrum, codex]
assumes: ["manifest diffs need identity stable across line movement and producer upgrades", "a repository-relative path is part of finding identity, so a move is a new identity unless migration aliases it"]
revisit_when: ["a collision is observed or the manifest scale makes a 96-bit truncated digest inadequate", "semantic anchors cannot remain stable for a supported detector family", "cross-repository finding continuity becomes a product requirement"]
supersedes: []
superseded_by: null
applies_to: [.claude/tasks/sweep-prototype/, scripts/_lib/finding_identity.py]
embodied_by: ["script:scripts/_lib/finding_identity.py", "contract:tests/test_finding_identity.py", "pending:WP5 migrates the ADR 0036 prototype manifest and emits v1 legacy aliases"]
tags: [sweep, finding-id, schema, manifests, mixed-language]
related_smell: format-equivalence-gap
related_pattern: null
---

# Finding identity is schema-versioned, language-namespaced, and anchored semantically

## Context

ADR 0036's prototype hashes `rule | path | symbol`. That usefully excludes
line numbers, but it is ambiguous for anonymous/missing symbols, collides
across language/provider namespaces, has no explicit case policy, and cannot
explain what happens when paths move or the schema changes. Those omissions
become correctness defects once manifests are release evidence and mixed-host
ratchets compare findings over time.

## Decision

Finding identity schema v2 hashes a canonical JSON payload containing:

`schema version | provider | rule | subject language | normalized repository-relative path | semantic anchor | occurrence`

The public id is `f2_` plus 24 hexadecimal SHA-256 characters (96 bits). The
full canonical identity payload is retained in the manifest. A manifest writer
must reject duplicate ids with unequal payloads; a real collision is a hard
failure, never a merge.

The semantic anchor is detector-owned but must describe the stable syntactic or
semantic locus (for example `function:transition/property:status`). It is
required even when a symbol is absent. Multiple identical anchors use a
deterministic zero-based occurrence assigned after stable source-order sorting.
Line/column, severity, metrics, messages, and producer/tool version are outside
the hash and remain ordinary manifest fields.

Paths are POSIX repository-relative paths. Absolute inputs require an explicit
repository root and paths outside it fail. Case handling is an explicit host
profile property: case-sensitive hosts preserve case; case-insensitive hosts
case-fold before hashing. The implementation does not guess from the machine
running the scan.

A rename or move intentionally changes v2 identity because path is part of the
finding's scope. Migration-aware tools carry prior ids in `legacy_ids`, allowing
one release window of continuity. Producer upgrades do not change identity.
Any future identity change increments the schema version, documents a
migration, and can dual-emit old aliases; it never silently reinterprets v2.

## Alternatives considered

- **Keep `sha1(rule|path|symbol)[:12]`.** Rejected because empty symbols make
  distinct findings identical, mixed-language/provider collisions are
  possible, and schema/case semantics are implicit.
- **Hash line/column.** Rejected because unrelated edits would turn persisting
  findings into fixed+new churn.
- **Hash the complete message or AST text.** Rejected because wording,
  formatting, and volatile metrics are not identity.
- **Content-only identity that survives file moves.** Rejected for v2 because
  identical snippets create multiplicity ambiguity and a path move is a
  meaningful scope change. `legacy_ids` handles deliberate migrations.
- **Random UUIDs.** Rejected because independent rescans could not reproduce
  the same identity.

## Consequences

Line drift and tool upgrades preserve ids, anonymous findings remain distinct,
and mixed-language manifests do not collide accidentally. Identity migrations
are visible and auditable.

Every detector must produce a stable semantic anchor and deterministic
occurrence. WP5 must migrate prototype baselines rather than pretending v1 and
v2 ids are equal. Silent duplicate-id deduplication and filesystem-dependent
case guessing are disallowed.

## Verification

`tests/test_finding_identity.py` adversarially covers line/tool changes,
missing-symbol multiplicity, provider/language namespaces, case policy,
rename/move aliases, path escape, and absolute-path normalization. WP5 adds a
manifest-level collision test and a v1-to-v2 migration fixture before it
retires the prototype identity function.
