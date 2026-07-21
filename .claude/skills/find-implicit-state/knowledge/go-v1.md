# Go implicit-state review contract

Use this branch for Go 1.22+ modules. It resolves selector fields with
`go/types` and promotes only a built-in `string` field named `state`, `status`,
or `phase` that has at least three direct comparison/assignment operations and
at least two distinct literals. That is review evidence, not proof that the
domain is closed. Named string types are classified as existing typed
authorities; convention-named possible vendor carrier types, tests, generated source, unrelated string
fields, and low-evidence fields remain explicit exclusions.

```bash
TARGET="${TARGET:-.}"
python3 .claude/skills/find-implicit-state/scripts/detect_go_state.py \
  --target "$TARGET" --project-root "$(pwd)" \
  --output reports/implicit-state/go.jsonl
```

The copied closure discovers Go from `PATH`, requires Go 1.22+, uses only the
host toolchain and standard library, and never downloads a parser. Syntax,
package, import-export, cgo, or tool failures exit 2 without publishing an
artifact. Inactive build-constrained source remains explicit `partial`
evidence and cannot authorize a proposal. Hand only `first_party_state_operation` records from a complete run to the Go branch of
`/extract-enum`; do not treat `insufficient_closed_state_evidence` as a clean
or actionable result.

The supported syntax is intentionally direct selector `==`/`!=` comparisons,
including reversed literals, and plain assignments. Do not claim alias,
dataflow, struct-literal, switch, reflection, build-matrix, cgo, generated
protocol, or framework coverage.

`Vendor*` and `*Payload|Request|Response|Event|Message|Wire` carrier names are
only boundary candidates. Type-name convention does not prove third-party
ownership; the proposal must ask the reviewer to confirm each boundary.
