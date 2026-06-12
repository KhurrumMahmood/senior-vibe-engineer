# Rule proposal: no-bare-int-request (POISONED-GOOD defect fixture)

## Source cluster
mini-host seed; anchor commit "Route product views through safe_int (anchor
fix)".

## Pattern
Bare `int(...)` of `request.POST.get(...)` / `request.GET.get(...)`. Path scope
`app/(services|views|pages|api)/**/*.py`. Full AST shape: see `pattern.md`.

## Artifacts
- lint guard: `scripts/lint/no_bare_int_request.py` (new — correct matcher),
  `tests/lint/no_bare_int_request_{bad,good}.py` (the **good fixture is
  poisoned** with a live anti-pattern), `.pre-commit-config.yaml`,
  `.github/workflows/ci.yml`, `scripts/lint/run.py`, `CLAUDE.md`.

## Verification
- `verify_rule.py`: BAD_RC=1 as expected, but GOOD_RC=1 (expected 0) because the
  "good" fixture contains an un-allow-listed `int(request.POST.get("page"))`.
  The differential gate fails — the proposal's evidence contradicts itself.
- Historical fire and whole-scope firing are both fine; the defect is purely in
  the fixture pair, which is exactly what C3 exists to catch.
