# Rule proposal: no-bare-int-request (OVER-BROAD defect fixture)

## Source cluster
mini-host seed; anchor commit "Route product views through safe_int (anchor
fix)" — the commit that fixed `app/views/products.py`.

## Pattern
Bare `int(...)` whose argument is `request.POST.get(...)` / `request.GET.get(...)`.
Path scope `app/(services|views|pages|api)/**/*.py`. Full AST shape and
false-positive boundaries: see `pattern.md`. (This is the *intended* pattern;
the shipped rule is over-broad.)

## Artifacts
- lint guard: `scripts/lint/no_bare_int_request.py` (new — **OVER-BROAD**: fires
  on any `int(...get(...))`), `tests/lint/no_bare_int_request_{bad,good}.py`,
  `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `scripts/lint/run.py`,
  `CLAUDE.md`.

## Verification
- `verify_rule.py`: BAD_RC=1, GOOD_RC=0 — the over-broad rule passes the
  differential gate because its self-consistent fixtures never exercise the
  innocent-code firing.
- Historical: fires on `<anchor>^:app/views/products.py`, clean on HEAD.
- KNOWN OVER-FIRE: also flags `app/services/cart.py`
  (`int(request.session.get(...))`, `int(config.get(...))`). Those are not the
  target anti-pattern. Caught only by whole-scope C8, not by the fixture pair.
