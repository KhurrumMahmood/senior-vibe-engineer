# Go concept-rename assessment v1

Load this guide only when the host contains Go source.

## What the gate proves

`assess.py` runs two distinct authorities:

1. the installed `find-concept-divergence` companion inventories eligible Go
   source and checks the retired term/prose bands; and
2. `scripts/go_identifier_evidence.go` uses Go 1.22+ `go list`, `go/parser`,
   and `go/types` to resolve matching identifiers.

Only exported package-scope declarations in the host establish the deprecated
or canonical concept symbol. References to those objects are classified as
`old_concept_symbol` or `new_concept_symbol`. Same-named locals, struct fields,
import aliases, unexported declarations, and external symbols remain separate
classifications and cannot certify the rename.

A Go rename cannot be complete unless the lexical bands are clean, semantic
evidence is `resolved`, no old authority/reference or unresolved matching
identifier remains, at least one canonical exported declaration exists, all
selected source is covered, and resolution diagnostics are empty. Missing or
old Go, inactive build-constrained source, malformed packages, and tool failure
stay unsupported/partial/inconclusive rather than clean.

## Invocation

Run the standard `scripts/assess.py` command from `SKILL.md` with the router's
exact guide, companion, and bundled-tool paths. No Go-specific flag is needed;
the assessment discovers the safe first-party `.go` surface from the companion
inventory and invokes the skill-local resolver. Run `go test ./...` before and
after to demonstrate that the read-only assessment preserved the host.

This branch does not rewrite identifiers, paths, comments, strings, generated
code, or build-tag variants, and it does not claim an automated rename is safe.
