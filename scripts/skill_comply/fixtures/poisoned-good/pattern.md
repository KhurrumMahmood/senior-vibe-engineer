# Pattern: no-bare-int-request (skill-comply POISONED-GOOD defect fixture)

> Defect fixture. The rule script is the CORRECT POST/GET-scoped matcher, but the
> shipped "good" fixture hides a live anti-pattern. The skill's own differential
> verifier (C3) catches the self-contradiction — GOOD_RC must be 0 and it is 1.

## Rule intent
Flag a bare `int(...)` whose argument is a `request.POST.get(...)` /
`request.GET.get(...)` lookup — raw coercion of user-supplied request data
without `safe_int(...)`.

## Classification
Custom AST rule. Ruff has no equivalent; `safe_int` is project-local.

## Path scope
`app/(services|views|pages|api)/**/*.py`. Excludes `tests/test_*.py`.

## AST shape
Builtin `int(...)` wrapping `<x>.POST.get(...)` / `<x>.GET.get(...)`.

## False-positive boundaries (must NOT fire)
- `safe_int(request.GET.get(...))`, `int(product_id)`,
  `int(request.headers.get(...))`, allow-listed `# noqa: ... <reason>`.

## Allow-list
`# noqa: no-bare-int-request: <reason>` on any line of the matched span.
