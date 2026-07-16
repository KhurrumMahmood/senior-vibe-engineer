---
name: extract-enum
description: Turn a stringly-typed closed vocabulary into a wire-compatible enum proposal. Consumes an extract-enum candidate or an explicit `<file>::<field>` target and emits a read-only proposal with members, caller classifications, compatibility risks, and a stop decision. Use when repeated string states should become one named type without changing persisted or external values.
argument-hint: "<implicit-state:ID or FILE::FIELD>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A confirmed stringly-state field whose values form a closed vocabulary.
  The run must preserve wire identity, classify every caller, and produce a
  reviewable proposal before any implementation begins.
not_for: |
  Detection (use /find-implicit-state). Relationship inference (use
  /introduce-fk). Refactor execution (use /fix-workflow or
  /refactor-subsystem). Open-ended user or third-party values that do not form
  a closed vocabulary.
language: any
framework: any
---

# /extract-enum

<!-- spec:portable-skill-layer-distribution::IM-8 -->

Turn one stringly-typed closed vocabulary into an implementation-ready enum
proposal. Preserve every persisted, serialized, and externally exchanged wire
value. Produce evidence and a proposal; never edit production code.

## How success is judged

- Binding evidence names the canonical profile root, ordered overlays, source
  hashes, rendered hash, and profile hash. Ambiguous, incompatible, or absent
  required overlays stop before collection.
- `targets.json` identifies exactly one carrier, its current keyword/options
  contract, every literal and count, case variants, comparisons, assignments,
  and caller files.
- `semantic.json` and the selected binding's proposal artifact reach its final
  output boundary. Every identifier, target path, literal, count, site,
  classification, member order, wire value, risk, and stop condition is
  preserved.
- Candidate-form routing accepts only `extract_enum_candidate`; every other
  category exits before scanning and produces no output.
- The run writes only under `reports/extract-enum/<target-slug>/` and defers
  implementation to a refactoring skill after human review.

Grade only the artifacts and re-runnable commands, never a conversational
claim. Write toward these gates from Stage 0.

## Core invariant

1. **Closed vocabulary first.** Include only states owned by the carrier.
   Values owned by an external bridge remain boundary mappings, not members.
2. **Wire identity is immutable in the proposal.** Member names may improve;
   persisted and exchanged values may not silently change.
3. **Variants are evidence.** A spelling/case variant is a compatibility risk,
   not noise to normalize away.
4. **One target per run.** Record another field as a follow-on finding and
   invoke the skill again.
5. **Proposal only.** Do not edit the carrier, callers, schema, data, tests, or
   guard rules in this skill.

## Inputs

### Candidate form

Accept `implicit-state:<id>` or a raw `implicit-state-NNNN` identifier. Strip
the optional prefix and resolve it from the latest implicit-state findings
artifact. Read `recommendation_hint` or final `bucket`; proceed only when it is
exactly `extract_enum_candidate`.

If the findings artifact is missing, stop and request `/find-implicit-state`.
Do not replace the missing artifact with a fresh scan.

### Explicit form

Accept `<file>::<field>` or `<file>::<field>::<carrier>`. Present the parsed
file, field, carrier, and deterministic target slug. Wait for an approval whose
first non-whitespace token is `approved`, `approve`, `go`, `lgtm`, `proceed`,
or `yes`.

## Pipeline

### Stage 0 — Select the root and overlays

Use the canonical host profile. Select independently for the target root in
this precedence order: core, language, framework, domain, host. Never select
from the aggregate multi-root stack, registry order, or directory order.

Require the runtime's binding evidence before proceeding. Stop on a malformed
profile/registry, a same-precedence ambiguity without one explicit root-local
choice, an incompatible explicit choice, a required zero-match, or a source
path outside this canonical skill root.

### Stage 1 — Collect the target

Load the selected language overlay and execute its candidate-form or
explicit-form collector command exactly as written. Paste the command, exit
status, and stderr summary into the run record. A zero-literal result stops;
it does not become an empty proposal.

### Stage 2 — Classify the vocabulary

Read `targets.json`. Classify every site as one of:

- confirmed state comparison;
- assignment;
- case/legacy risk;
- third-party bridge; or
- dynamic/unresolved.

Derive members only from the carrier's declared vocabulary when one exists.
Member names are symbolic; wire values retain exact spelling and order. If the
declared vocabulary and collected literals differ, retain both sets and add a
reconciliation risk.

Use `agents/enum-profiler.md` only when deterministic evidence cannot classify
a site. Tell the scout its output is judged solely by the profile artifact it
writes, with every target site represented. If the scout fails twice, record
`profile_incomplete` and keep the stop decision closed.

### Stage 3 — Render and verify the final proposal

Load the selected framework or language output overlay and execute its final
render command. The command must write `semantic.json` plus the overlay's
declared proposal artifact (`proposal.md` or an executable enum module).

For a replay oracle, pass separate actual and expected temporary directory
roots and compare semantics after only these normalizations: typed path fields
under those roots, timestamps/scan IDs, Markdown whitespace, and table ordering
explicitly declared irrelevant. Preserve every relative path suffix. Do not normalize identifiers,
targets, literals, counts, sites, classifications, keyword/options data,
member names/order, wire values, risks, or stop decisions.

Paste the comparator exit status and normalization report. A semantic mismatch
is a failed run even if the Markdown looks plausible.

### Stage 4 — Handoff

Summarize the target, literal and variant counts, caller files, unresolved
sites, risks, binding evidence path, and proposal path in at most ten lines.
Request human review. Hand an approved proposal to `/fix-workflow` for a narrow
change or `/refactor-subsystem` for a multi-file migration. Do not begin that
work here.

## Replay

Use the framework fixture with one carrier field, a declared three-value
vocabulary, two valid comparisons, one case variant, one bridge literal, and
one assignment. Also run the plain-language fixture through its executable
enum renderer. The replay passes
only when the semantic comparator exits zero and records no normalization
beyond the four allowed categories. Separately replay a non-extraction
candidate and require exit 2, empty stdout, exact routing stderr, and no output
artifact.

## Non-goals

- Detecting candidates or inferring relationships.
- Editing implementation, data, schema, tests, or lints.
- Inventing members for external or dynamic values.
- Processing more than one target.
- Treating a rendered document as proof without semantic output.

## When things go sideways

| Symptom | Action |
|---|---|
| Canonical profile or binding evidence is absent | Stop; do not infer from installed tools or the aggregate stack |
| Two overlays match one precedence | Require exactly one explicit choice for that root |
| Candidate category is not `extract_enum_candidate` | Abort before scanning and report the owning route |
| Collector returns zero literals | Stop and suggest `/find-dormant` for the carrier |
| Declared values and collected values differ | Preserve both sets, add a reconciliation risk, keep execution blocked |
| A site is dynamic or cannot be classified | Record it explicitly; do not create a member from it |
| Semantic comparator changes a literal, site, wire value, risk, or stop condition | Fail the replay; AR-8 does not allow that normalization |
| A required command cannot run | Record the exact command and reason; never simulate output |
