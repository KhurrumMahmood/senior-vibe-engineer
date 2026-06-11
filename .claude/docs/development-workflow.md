# Development Workflow

Implementation discipline, conventions, and patterns for normal and risky
work. The always-loaded `CLAUDE.md` carries terse pointers; this file holds
the full prose. Read before starting ambiguous, multi-file, or architectural
work — small obvious fixes do not need to load this.

## Workflow Discipline

- **Plan when it pays.** For ambiguous, risky, multi-file, or architectural
  work, write a short plan before editing. For simple, obvious fixes, proceed
  directly and keep the user updated.
- **Persist only durable plans.** Write plans to `.claude/tasks/<slug>.md`
  only for work that spans sessions or has many steps; otherwise keep the
  plan in the conversation.
- **Re-plan on evidence.** Update the plan when new information changes
  scope, invalidates an assumption, or verification exposes another failure.
- **Prefer the smallest responsible fix.** Fix the root cause without
  broadening the change beyond the touched behavior.
- **Check interface depth before extracting.** Before adding an abstraction,
  helper, service, module split, or adapter, apply
  `.claude/skills/_common/interface-depth.md`. Avoid speculative seams;
  create adapters or extension points only when real variation exists or the
  near-term second use is known.
- **Verify before done.** Do not call work complete until the changed
  behavior has been checked. Run the narrowest meaningful tests for the
  touched surface, expanding when the blast radius is shared or uncertain.
  If something cannot be verified, state exactly what was not run and why.
- **Prove the output boundary for data workflows.** For extraction,
  discovery, export, AI, and other data-pipeline changes, a passing candidate
  scorer or adapter harness is not enough. Prove at least one representative
  input artifact reaches the final executable/output boundary: cached input
  enters the pipeline, runtime code or an accepted artifact is produced,
  that output is executed or applied through the real boundary, and final
  values/expected abstains match the oracle.
- **Capture durable lessons.** Four surfaces, pick the right one (no
  overlap):
  - `.claude/tasks/lessons.md` — diary of repeated, project-specific, or
    non-obvious corrections. Append-only; "rule + why + how to apply."
  - `.claude/docs/known-issues.md` — current-state operational gotchas
    (third-party quirks, anti-bot patterns, cache behaviors, format
    mismatches). Updated in place when the underlying state changes.
  - `.claude/docs/precedents.yml` — updateable implementation case law for
    recurring mechanisms with exemplars, guards, exceptions, and
    supersession. Use it when a best-practice shape has real applications
    that must migrate together if the shape changes, but the choice is not
    ADR-weight.
  - `ai-docs/decisions/` — ADRs only when the choice constrains future
    work or excludes an alternative ("from now on…"). See
    `ai-docs/decisions/README.md` for the threshold (target 2-5/quarter).
  Do not put project-specific learnings in reusable `SKILL.md` files.

## Bug Fix Protocol

When the user reports a bug, reproduce it first with a test, log, traceback,
or minimal diagnostic. Fix the root cause, then prove the failure no longer
occurs. Ask the user only when expected behavior is ambiguous or environment
/ access blocks progress.

## Implementation Discipline

Before, during, and after implementing a change:

1. **Write a test first.** Before touching production code, write (or
   sketch) a test that captures the intended behavior. This forces you to
   trace the real code paths and exposes gaps in the plan early.
2. **Search for all affected code paths.** Don't trust a plan as
   exhaustive. Grep for every place the changed model/field/function is
   created, read, or defaulted. Example: if adding a default value, search
   for every place the owning row is constructed — not just where it's
   updated.
3. **Follow existing defensive patterns.** Before writing new
   parsing/validation code, read the surrounding code for try/except,
   clamping, or fallback patterns and match them.
4. **Post-implementation gut check.** After all tests pass, ask: "Does my
   change actually achieve the stated goal for every user-facing path?"
   Grep once more to confirm no creation/update/read path was missed.
5. **End-to-end core proof.** When the change affects extraction,
   discovery, exports, AI workflows, or generated runtime code, add or run a
   test that follows the whole core behavior — from cached input through
   the final executable boundary, with expected output values asserted. UI
   checks are additional when the UI is touched, but they do not replace
   this proof.

## Comments, Docstrings, and JSDoc

Comments are part of the code contract. Use them to explain intent,
ownership, caveats, compatibility, non-obvious history, or why a surprising
shape is deliberate. Do not use them to narrate the next line.

- Keep comments adjacent to the symbol or block they describe. Avoid detached
  banner comments when a function/class/module name already provides the
  structure.
- Modules/classes that own route, view, service, or workflow behavior
  should have concise docstrings naming that ownership or contract.
- JavaScript should use real JSDoc for public-ish functions: exported/global
  helpers, `initialize*`/`handle*` workflows, async functions, shared helpers,
  or anything with non-obvious parameters, return values, or side effects.
  Local caveats can stay as short `//` comments.
- Template comments should explain conditional rendering, shared modal
  or payload ownership, or template gotchas. Delete comments that duplicate
  visible headings or obvious HTML structure.
- Stale terms in comments/docstrings are bugs. Update them with the code, and
  keep compatibility notes explicit when old names still matter.
- `/find-comment-drift` is the advisory audit for comment/JSDoc cleanup;
  `comment-drift` is the diff-scoped lint for bad comment shapes on the live
  code surface.

## Service Layer Conventions

Services live in `app/services/` (or `src/services/`, etc.). Patterns to
follow:

- **Static methods on a class** — no instance state, no `__init__`. Pure
  functions with dependency injection via arguments.
- **Lazy imports** inside methods (`from app.models import Foo`) to avoid
  circular import issues.
- **Return types** — plain dicts for simple results; `@dataclass` for
  results with success/error semantics.
- **Docstrings** note which views/functions the service method was
  extracted from, for traceability.
- **Directory packages over flat files for god-classes** — when a service
  or model file grows past ~2000 LOC and the SRP sentence test shows 3+
  "and"s, split by domain cluster into sibling modules and preserve the
  import surface via `__init__.py`. If an old service is fully replaced,
  delete the legacy import shim instead of keeping a confusing fallback.
  For ORM models, every split must keep the `app_label` / table mapping
  stable so migrations remain schema-neutral.

## View Pattern

Views should be thin HTTP wrappers:

1. Parse request (get IDs, decode JSON body)
2. Load the model (`get_object_or_404` or equivalent)
3. Call service method
4. Return response

When a helper function in a view module is used by other callers (tasks,
other views), keep a thin delegate that calls the service — don't break
existing call sites. Don't extract view logic that is deeply HTTP-coupled
(proxy setup, gzip decompression, IP location checking). Only extract
reusable business logic.

## Testing Patterns

- **Capability tests** (user workflow outcomes) over granular unit tests.
- **End-to-end data tests** for extraction/discovery/export logic must
  assert final outputs, not only intermediate plans. For extraction, that
  means expected field values and expected abstains after the compiled
  runtime runs against sample input.
- **Mock async dispatch**: never launch real async jobs in tests.
- **Page-level tests** (Playwright or equivalent) for UI rendering and
  navigation, against a running dev server.
- **Live integration suites** are marked `live`/`slow` and skipped by
  default. Run them explicitly with `--run-live` or an env flag.
- **Shared test config** (e.g., `testing/conftest.py`) registers markers
  and enforces live-test gating.

See `testing.md` for the verification policy (which suite to run for a
given change shape) and the host project's coverage map.
