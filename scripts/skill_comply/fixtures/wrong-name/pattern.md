# Pattern: no-bare-int-request (skill-comply WRONG-NAME defect fixture)

> Defect fixture. The matcher is the CORRECT POST/GET-scoped rule, but the rule
> script emits a tag (`no-bare-int-req`) that has drifted from the wired/manifest
> name (`no-bare-int-request`). C3 passes (exit-code based); C4 fails because the
> scorer counts historical-fire hits by the wired tag and sees zero.

## Rule intent
Flag a bare `int(...)` whose argument is a `request.POST.get(...)` /
`request.GET.get(...)` lookup — raw coercion of user input without `safe_int(...)`.

## Classification
Custom AST rule. Ruff has no equivalent; `safe_int` is project-local.

## Path scope
`app/(services|views|pages|api)/**/*.py`. Excludes `tests/test_*.py`.

## AST shape
Builtin `int(...)` wrapping `<x>.POST.get(...)` / `<x>.GET.get(...)`.

## False-positive boundaries (must NOT fire)
- `safe_int(request.GET.get(...))`, `int(product_id)`,
  `int(request.headers.get(...))`.

## Allow-list
`# noqa: <wired-tag>: <reason>` — note that under tag drift the allow-list keyed
to the wired name is itself not recognized, which is part of why tag drift is a
real defect, not a cosmetic one.
