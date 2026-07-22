# Go closed-state guard contract

After a human accepts the Go proposal's finite-domain invariant, stage an
exact package/carrier/field guard from its `targets.json`. The generator needs
the `find-implicit-state` closure beside this skill so it can copy the same
`go/types` analyzer into the staged, self-contained guard; it exits 2 rather
than silently falling back to a lexical field-name check.

```bash
OUT="reports/prevent-regression/go-state"
python3 .claude/skills/prevent-regression/scripts/generate_go_state_guard.py \
  --targets reports/extract-enum/go-state/targets.json \
  --project-root "$(pwd)" --output-root "$OUT"

python3 .claude/skills/prevent-regression/scripts/verify_go_state_guard.py \
  --rule "$OUT/scripts/lint/no_stringly_state.py" \
  --project-root "$(pwd)" \
  --bad "$OUT/tests/lint/no_stringly_state_bad.go" \
  --good "$OUT/tests/lint/no_stringly_state_good.go"
```

The staged guard rejects a single new bare comparison or assignment on the
accepted field, even though nomination originally required repeated evidence.
It uses Go 1.22+ and exact `go/types` identity, stages bad/good fixtures plus a
host-wiring recipe, and does not install itself. Verification must report
`BAD_RC=1, GOOD_RC=0`.
