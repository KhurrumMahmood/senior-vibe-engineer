# Rule proposal: no-bare-int-request (WRONG-NAME defect fixture)

## Source cluster
mini-host seed; anchor commit "Route product views through safe_int (anchor
fix)".

## Pattern
Bare `int(...)` of `request.POST.get(...)` / `request.GET.get(...)`. Path scope
`app/(services|views|pages|api)/**/*.py`. Full AST shape: see `pattern.md`.

## Artifacts
- lint guard: `scripts/lint/no_bare_int_request.py` (new — correct matcher, but
  the emitted **tag is drifted** from the wired name),
  `tests/lint/no_bare_int_request_{bad,good}.py`, `.pre-commit-config.yaml`,
  `.github/workflows/ci.yml`, `scripts/lint/run.py`, `CLAUDE.md`.

## Verification
- `verify_rule.py`: BAD_RC=1, GOOD_RC=0 — passes, because the differential gate
  keys off exit codes, not the emitted tag.
- Historical: the scorer counts `no-bare-int-request` violation lines on
  `<anchor>^:app/views/products.py`. The rule emits `no-bare-int-req`, so the
  count is 0 and C4 fails — the same scorecard signature as a matcher that
  misses the bug entirely. The two are distinguishable only by the C2 cosmetic
  output-format line. (See STAGE2.md on the tag-coupling fragility.)
