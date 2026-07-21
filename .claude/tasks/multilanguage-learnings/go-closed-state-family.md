# Go closed-state family learning packet

Status: implementation and focused preservation evidence complete; capability
promotion awaits fresh product review and a committed closeout revision.

## Useful outcome

The first Go G3 slice now reaches one complete maintenance loop from copied
skill closures:

1. `find-implicit-state` uses `go list`, export data, `go/parser`, and
   `go/types` to resolve direct string comparisons and assignments to an exact
   package, carrier type, and struct field.
2. `extract-enum` consumes only the structured detector evidence and emits a
   review-only named-string/typed-constant proposal without editing source.
3. `prevent-regression` stages an exact package/carrier/field guard, fixtures,
   and host-wiring guidance after the human accepts that the domain is finite.

The detector requires repeated evidence to nominate a field, while the accepted
guard rejects one new bare literal. Those are deliberately different
thresholds: discovery is conservative; enforcement protects a reviewed
invariant.

## Go-specific lesson

Go cannot prove that a `string` field has a closed domain, and a named string
type still permits comparisons with untyped string constants. Therefore:

- `go/types` proves receiver/field identity, not domain exhaustiveness;
- repeated literals make a `review_candidate`, never an automatic refactor;
- an existing named string type is an authority to reuse, not an enum-extraction
  target;
- the idiomatic proposal is a named string type plus typed `const` values,
  preserving serialized strings; and
- `gofmt`, `go vet` for the analyzer, and the host's `go test ./...` are native
  acceptance oracles.

## Reuse decision

This family produced the first justified reuse of identical Go semantic facts.
The canonical analyzer remains owned by `find-implicit-state`. The guard
generator copies that exact helper into the staged guard from the declared
sibling closure; it does not duplicate a second parser or import repository
runtime. A `prevent-regression` closure without `find-implicit-state` exits 2
with the missing dependency instead of weakening to field-name regexes.

Do not extract a universal Go analysis platform. Reconsider a smaller shared
package-loading primitive only when another independent family needs the same
export-data/type-check contract and selected-skill packaging can carry it
honestly.

## Locked evidence and limits

`tests/test_find_implicit_state_go.py` proves the final detector JSONL,
proposal Markdown/JSON, staged guard and verifier, copied closures, exact
historical hits, generated/test/vendor/typed/low-evidence exclusions,
malformed source, missing/old Go, source fingerprints, and native `go test`.
Carrier suffixes such as `Request` or `Payload` produce possible boundary
candidates only; a reviewer must confirm actual third-party ownership.

The v1 syntax surface is intentionally direct: selector comparisons (`==`,
`!=`, including reversed literals) and plain assignments. It does not claim
aliases, dataflow, struct-literal initialization, switches, reflection,
generated protocols, build matrices, cgo, or framework semantics. Those are
future candidates only when a real host demonstrates user value.

## Transfer to later languages

- Separate semantic identity from business-domain closure; compilers often
  prove the former but not the latter.
- Let proposals consume detector artifacts rather than rescan source.
- Let guards reuse the accepted semantic identity but tighten the occurrence
  threshold after human approval.
- Capture the language's idiomatic representation and native tools as part of
  support evidence. This packet seeds backlog item ML-023 for broader
  language-idiom profiles.
