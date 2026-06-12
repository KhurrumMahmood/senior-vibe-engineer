# Pattern: no-bare-int-request (DEFECTIVE)

## Rule intent
Flag a bare `int(...)` call on user-supplied request data without the canonical
`safe_int(...)` helper.

## Classification
Custom AST rule (ruff is silent on this domain shape).

## Path scope
`app/(services|views|pages|api)/**/*.py`, excluding `tests/test_*.py`.

## File suffixes
`.py` only.

## AST shape (as implemented — DEFECTIVE)
`ast.Call` where `func` is `ast.Name(id="int")` and `args[0]` is an
`ast.Subscript` on `request.POST` / `request.GET`.

> Coverage defect: the real anti-pattern uses the `.get(...)` *method* form,
> not subscripting. This matcher therefore never fires on the actual bug. The
> fixture pair below is self-consistent with the (wrong) matcher, so the
> skill's own `verify_rule.py` still passes — only the historical-fire check
> against the pre-anchor blob surfaces the gap.

## Allow-list
`# noqa: no-bare-int-request: <reason>` (reason required).
