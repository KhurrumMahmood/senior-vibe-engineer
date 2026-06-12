# Rule proposal: no-bare-int-request (DEFECTIVE)

## Source cluster
mini-host seed; anchor commit "Route product views through safe_int (anchor
fix)".

## Pattern
Bare `int(...)` on user-supplied request data; should route through
`safe_int(...)`. Path scope `app/(services|views|pages|api)/**/*.py`. (As
implemented the matcher only covers the subscript form — see `pattern.md`.)

## Artifacts
- lint guard: `scripts/lint/no_bare_int_request.py` (new),
  `tests/lint/no_bare_int_request_{bad,good}.py` (new),
  `.pre-commit-config.yaml` (modified — `local` hook entry),
  `.github/workflows/ci.yml` (modified — diff-scoped step),
  `scripts/lint/run.py` (modified — one `RuleSpec`),
  `CLAUDE.md` (modified — Canonical Patterns entry)

## Verification
- `verify_rule.py`: BAD_RC=1, GOOD_RC=0 (passes — the fixtures are
  self-consistent with the matcher).
- Historical regression: rule fires on `git show <anchor>^:app/views/products.py`.
- Clean on current HEAD: `app/views/products.py`.

## Follow-on findings
`app/views/checkout.py` still parses `int(request.POST.get("quantity"))`.
