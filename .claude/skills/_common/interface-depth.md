# Interface Depth Rubric

Use this shared rubric when a skill proposes or executes an extraction,
module split, helper consolidation, adapter, or new public service method.
It is project-agnostic; project-specific examples and exceptions belong
in each skill's `knowledge/` directory.

## Terms

- **Module** - anything with an interface and an implementation: a
  function, class, package, or workflow slice.
- **Interface** - everything a caller must know to use the module
  correctly: signature, invariants, ordering, error modes, config, and
  performance expectations.
- **Implementation** - the code behind the interface.
- **Depth** - leverage at the interface. A deep module hides meaningful
  behavior behind a smaller interface; a shallow module makes callers
  learn nearly as much as the implementation.
- **Seam** - where behavior can vary without editing the caller.
- **Adapter** - a concrete implementation that satisfies a seam.
- **Locality** - change, bugs, verification, and knowledge concentrate
  in one place instead of spreading across callers.

## Four Checks

Record these checks in any proposal that creates or reshapes a public
module, service method, helper, or adapter:

1. **Deletion test** - if this module disappeared, would complexity
   reappear across multiple callers/tests, or would it mostly vanish?
   If it mostly vanishes, the module is pass-through ceremony.
2. **Caller knowledge test** - what facts do callers no longer need to
   know after this change? Good answers name invariants, retries,
   failure shape, resource ownership, or ordering constraints.
3. **Test-surface test** - can durable tests exercise behavior through
   the module interface? If tests must reach private helpers, the
   interface is probably the wrong shape.
4. **Adapter reality test** - one adapter is a hypothetical seam; two
   adapters are a real seam. Introduce a port/adapter only when real
   variation exists, usually production plus a test stand-in or two
   production implementations.

## Dependency Categories

Use the dependency category to decide how much interface ceremony is
justified:

| Category | Examples | Design default |
|---|---|---|
| In-process | Pure computation, local state | Merge/deepen directly; no adapter. |
| Local-substitutable | DB via test DB, filesystem with temp dir | Test through the module interface using the local stand-in. |
| Remote but owned | Internal HTTP/gRPC/queue service | Define a port only if logic remains local and transport varies. |
| True external | Third-party API, paid model/provider, remote upstream vendor | Inject a narrow dependency and test with a fake/mock adapter. |

## Design-It-Twice Trigger

For a high-blast-radius interface (3+ callers, cross-layer dependency,
external I/O, or an adapter/port), compare at least two interface
shapes before implementation:

- Minimal interface: 1-3 entry points, maximum leverage per call.
- Common-case interface: make the hottest caller trivial.
- Flexible interface: supports known variation without leaking internals.
- Ports/adapters interface: only when the adapter reality test passes.

Pick one and record the reason. Do not implement a menu of all options.

## Proposal Snippet

Use this compact section in reports/proposals:

```markdown
## Interface depth check

- **Deletion test:** <what complexity would spread if removed>
- **Caller knowledge removed:** <invariants/error modes/resource policy hidden>
- **Test surface:** <durable tests hit this public interface>
- **Adapter count:** <none | one deliberate fake | two+ real adapters>
- **Decision:** <deep enough | keep local | redesign before extracting>
```

## Anti-Patterns

- A helper whose parameters mirror the caller's local variables but
  hides no policy or invariant.
- A service method that just renames one ORM call.
- A public seam created only so tests can mock an internal collaborator.
- A port with one production adapter and no realistic test stand-in.
- Splitting facets of one workflow into sibling modules that constantly
  import each other's private helpers.
