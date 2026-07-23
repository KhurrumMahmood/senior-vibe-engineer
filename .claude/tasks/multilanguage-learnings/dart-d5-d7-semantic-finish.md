# Dart D5/D7 semantic-lead finish packet

Status: isolated implementation candidate on exact base `dec49ac`; no router,
catalogue, matrix, coverage, active-plan, profile, installer, or shared skill
prose is changed here.

## Useful outcomes

- `find-semantic-duplication` consumes the accepted D4
  `call_hierarchy_queries` contract. It considers only authored production
  top-level, non-generic, synchronous free functions with explicit return type
  and one direct named-constructor return. A lead requires matching returned
  fields, constructor identity, complete member call facts, the same resolved
  first-party non-constructor callee identities, no member wrapper, lexical
  non-clone evidence, compatible bounded policy markers, and resolved
  first-party callers on distinct surfaces.
- The positive fixture yields only `buildStatement` / `summarizeInvoice`.
  Exact lexical clones and the extra `policyFee` callee are explicit
  rejections. Wrapper, method, extension, generic, dynamic, generated, test,
  example, and vendor shapes do not promote.
- Machine evidence writes a candidate with
  `machine_consolidation_shape: null` and `human_verdict: required`. Only a
  `candidate_sha256`-bound review can produce a final finding;
  `keep_separate_document_why` is a complete successful reviewed outcome.
- `unify-shadows` imports only `_dart/dart_accepted_evidence.py`. It launches
  no Dart process, LSP, analyzer, detector, Pub command, or network operation.
  It revalidates the acceptance, source/configuration snapshot, selected
  finding hash, copied human-review hash, scan lineage, capability-matrix hash,
  selected shape, and every member/caller citation, then writes exactly
  `proposal.md`, `evidence.json`, and `scope.json`.
- Missing, pending, partial, tampered, and stale evidence produces a visible
  three-artifact refusal. Directory replacement removes stale ready files;
  valid -> failure -> valid replay restores readiness without touching source.

## Copied closures and fixture

Manifests hash sorted `install-relative path + NUL + file SHA-256 + LF` rows.

| Closure | Files | Physical / nonblank LOC | Bytes | Manifest SHA-256 |
|---|---:|---:|---:|---|
| D5 detector + sibling `map-subsystem` provider | 2 | 2,543 / 2,384 | 101,574 | `485a0a09ce1a3da9a487e378db0aa29f4a88935724ad63ab42041a13d21b3f8e` |
| D7 proposer + accepted-evidence validator | 2 | 1,044 / 935 | 42,694 | `584019134775a5345fbc741eb3cd54ed8e19b2eea150c2db1c13e4d503e67c11` |

The positive fixture is 16 files / 7,193 bytes with manifest
`9da97ed7b5896afc61556f2a1cbbcbf2c459264d66690fbd309a2badd733b6a0`.
Copied runs use product Python `-I -S`, execute outside the repository and
audited host, and require no repository import or host repair.

## Economics

No new shared layer is introduced.

- D5 now has three real consumers of the existing 1,425-LOC D4 provider. A
  conservative `C = 3,639` charges all three adapters, sweep scout/triage, the
  D5 family test, and the entire combined finish test. Three copied providers
  would be `C + 3H = 7,914`; one shared provider is `C + H = 5,064`. Saved
  maintenance is 2,850 LOC, or **36.01%**.
- The accepted-evidence seam now has five real D6/D7 consumers. Starting from
  accepted `H = 786`, `C = 4,832`, `n = 4`, this batch conservatively adds the
  full 614-line proposer and 506-line combined test: `C = 5,952`, `n = 5`.
  Duplicated validation is `C + 5H = 9,882`; shared validation is
  `C + H = 6,738`. Saved maintenance is 3,144 LOC, or **31.82%**.

These calculations justify only the already-bounded Dart provider and
accepted-evidence seams. They do not justify a universal graph, parser,
proposal platform, or cross-language abstraction.

## Verification and limitations

Focused D5/D7, preserved D4/validator/proposal, and preserved Go/Java/Python/
TypeScript/Rust semantic/proposal tests pass. The Dart fixture passes fatal
analyze, check-only format, dependency-free direct test, and exact `42` smoke;
focused tests prove source hashes unchanged and the full refusal lifecycle.

The result is selected-configuration static review evidence only. It does not
prove behavioral equivalence, refactor safety, a canonical survivor, complete
runtime reachability, side effects, error ordering, external consumers,
reflection, dynamic dispatch, registries, isolates, native/JS interop,
generated/part/augmentation/conditional behavior, semver compatibility, or
Flutter/framework semantics. D7 proposes; it never edits source.

Root publication must serially replay both copied closures, then update the
two shared `SKILL.md` Dart command/replay sections, the two skill contracts,
`dart-language-coverage.json`, `multilanguage-skill-matrix.json`, the active
Dart plan/catalogue/router surfaces, and the reviewed revision/evidence rows.
Publish each row only after those central gates pass.
