# Pattern: no-bare-int-request

> **skill-comply under-broad fixture.** Everything below is what the
> (defective) author believes: the receiver is always the literal name
> `request`. The matcher encodes that belief, so `self.request.POST.get`
> and aliased receivers are silently missed — the C9 recall defect.

## Rule intent
Flag a bare `int(...)` call whose argument is a `request.POST.get(...)` or
`request.GET.get(...)` lookup — raw coercion of user-supplied request data
without the canonical `safe_int(...)` helper.

## Classification
Custom AST rule. Ruff is silent on this shape: there is no ruff code for
"builtin `int()` wrapping a request `.get()` lookup". `safe_int` is a
project-local convention, so only a domain-specific rule can enforce it.

## Path scope
`app/views/**/*.py`, `app/pages/**/*.py`, `app/api/**/*.py`, `app/services/**/*.py`
(the request-handling surfaces). Excludes `tests/test_*.py`.

## File suffixes
`.py` only.

## AST shape
`ast.walk` looks for an `ast.Call` where:
- `node.func` is `ast.Name(id="int")` — the builtin int, NOT `safe_int` (which
  is `ast.Name(id="safe_int")`) and NOT an attribute call like `x.int(...)`;
- `node.args[0]` is an `ast.Call` whose `func` is `ast.Attribute(attr="get")`
  on an `ast.Attribute(attr in {"POST", "GET"})`.

## False-positive boundaries (must NOT fire)
- `safe_int(request.GET.get(...))` — already canonical (`func.id == "safe_int"`).
- `int(product_id)` — non-request argument.
- `int(request.headers.get(...))` — `.get` on a non-POST/GET attribute.
- A bare-int call carrying `# noqa: no-bare-int-request: <reason>` on its span.

## Allow-list
`# noqa: no-bare-int-request: <reason>` on any line of the matched span; reason
regex `\S` (non-empty).
