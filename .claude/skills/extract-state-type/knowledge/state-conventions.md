# /extract-state-type state conventions

This file is scout context for `agents/state-profiler.md`. The orchestrator
loads `knowledge/proposal-template.md` when writing the final proposal; the
scout loads this file while deciding whether the target shape should become a
`@dataclass`, `TypedDict`, or no type at all.

## Shape decision rule

| Current state behavior | Proposed shape |
|---|---|
| Mutated in place across helper calls inside one process | `@dataclass` |
| Constructed once, serialized, cached, logged, or returned as a boundary payload | `TypedDict` |
| Mutated internally and returned as a legacy dict | `@dataclass` plus `to_dict()` compatibility method |
| Arbitrary runtime string keys, such as user ids or site ids | Do not typeify; document the key convention instead |

Prefer `@dataclass` whenever mutation continues after construction. Prefer
`TypedDict` only when the object is a read-only boundary shape.

## Location convention

The proposal should place the new type in the smallest module that is already
owned by the target subsystem. For a single large service module, propose a
nearby `state.py` only when the target already has or clearly earns a package;
otherwise define the type next to the carrier and let `/fix-workflow` decide
whether a package extraction is warranted.

## Proposal guardrails

- Every mutable default uses `field(default_factory=...)`.
- Every caller that reads the legacy dict return is named in the caller table.
- Dynamic-key shapes stop with a "do not typeify" proposal; they are not forced
  into a lossy `dict[str, Any]` wrapper.
