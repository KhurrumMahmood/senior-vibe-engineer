# Pattern: no-bare-int-request (skill-comply OVER-BROAD defect fixture)

> Defect fixture. The prose below describes the CORRECT intent; the shipped rule
> script drifts to fire on any `int(...get(...))`. C3/C4 pass; the scorer's C8
> (bounded incidental firing) is what catches the over-breadth.

## Rule intent
Flag a bare `int(...)` whose argument is a `request.POST.get(...)` /
`request.GET.get(...)` lookup — raw coercion of user-supplied request data
without the canonical `safe_int(...)` helper.

## Classification
Custom AST rule. Ruff has no equivalent code; `safe_int` is a project-local
convention.

## Path scope
`app/(services|views|pages|api)/**/*.py`. Excludes `tests/test_*.py`.

## AST shape (intended)
Builtin `int(...)` wrapping `<x>.POST.get(...)` / `<x>.GET.get(...)`.

## False-positive boundaries (must NOT fire)
- `safe_int(request.GET.get(...))` — already canonical.
- `int(product_id)` — non-request argument.
- `int(request.session.get(...))`, `int(config.get(...))` — `.get` on a
  non-POST/GET receiver (server-side state / plain mappings, not user input).
- Allow-listed `# noqa: no-bare-int-request: <reason>`.

## Allow-list
`# noqa: no-bare-int-request: <reason>` on any line of the matched span; reason
must be non-empty.
