# Rule proposal: no-bare-int-request

## Source cluster
mini-host seed; anchor commit "Route product views through safe_int (anchor
fix)" — the commit that fixed `app/views/products.py` to stop parsing request
data with a bare `int(...)`.

## Pattern
Bare `int(...)` whose argument is `request.POST.get(...)` / `request.GET.get(...)`.
Path scope `app/(services|views|pages|api)/**/*.py`. Rationale: a missing key
makes `.get(...)` return `None` and `int(None)` raise `TypeError`; junk input
raises `ValueError`. The canonical `safe_int(...)` swallows both with a default,
so user input must route through it. Full AST shape and false-positive
boundaries: see `pattern.md`.

## Artifacts
- lint guard: `scripts/lint/no_bare_int_request.py` (new),
  `tests/lint/no_bare_int_request_{bad,good}.py` (new),
  `.pre-commit-config.yaml` (modified — `local` hook entry),
  `.github/workflows/ci.yml` (modified — diff-scoped step),
  `scripts/lint/run.py` (modified — one `RuleSpec`),
  `CLAUDE.md` (modified — Canonical Patterns entry)

## Verification
(Under-broad fixture note: every claim below is true — the defect is what
is NOT claimed. The rule never fires on `self.request.POST.get(...)` or
aliased receivers, so the sibling instances in `app/views/reports.py` go
unguarded. Self-chosen fixtures cannot see that; only C9 can.)
- `verify_rule.py`: BAD_RC=1 with 4 hits (one per matcher variant), GOOD_RC=0.
- Historical regression: rule fires on `git show <anchor>^:app/views/products.py`
  (2 hits, lines 9 and 10).
- Clean on current HEAD: `app/views/products.py` (0 hits after the safe_int fix).

## Follow-on findings
`app/views/checkout.py` still parses `int(request.POST.get("quantity"))` — the
anchor cluster did not fix it. This is a new `/fix-workflow` candidate, not
Phase 1 work for this guard.
