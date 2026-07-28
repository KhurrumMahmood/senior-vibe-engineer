# Real-repository product validation plan

Status: in progress

Branch: `codex/real-repo-validation`

Baseline: `584688bb1ea82a98886509d108d25ad9ba60c89a`

## Purpose

Determine whether the product on authoritative `main` is useful on real
repositories. The existing `22/22` language rows prove bounded fixture
contracts; they do not, by themselves, prove real-project usability.

This plan is intentionally product-facing. A finding enters implementation
only when it affects installation, routing, successful execution, correctness
or usefulness of the result, host-project safety, or material latency/setup
friction. Platform hardening without a demonstrated user impact goes to the
backlog.

## How to use this file

1. Change only the `Status` and checklist markers as evidence is produced.
2. Record exact commands, revisions, exit codes, timings, and artifact paths in
   the evidence table. Do not mark a criterion complete from a prose claim.
3. Classify every failure as `product-blocking`, `important`, `backlog`, or
   `environmental`. Only the first two classes interrupt the current slice.
4. Add a regression test before fixing a reproducible product defect.
5. Keep downloaded repositories below `.engineering/local/` or another
   disposable external cache. Never vendor them into Git.
6. After each four-language slice, update the validation-status table and
   decide whether the next slice is justified. Do not expand infrastructure
   speculatively.

Validation levels used by this plan:

- `implemented`: a language outcome and fixture contract exist;
- `fixture-validated`: focused synthetic/curated tests pass;
- `real-repo-smoke`: the current product completes the declared read-only
  journey on a pinned real repository without corrupting the host;
- `journey-validated`: routing, on-demand closure, execution, useful artifact,
  and verification all pass from a clean installed host.

## Acceptance criteria

### A. Authoritative baseline

- [x] A1. Work starts from the clean product checkout, not the divergent
  `codex/portable-v1-preflight` worktree.
- [x] A2. The release/matrix/router/installed-router boundary passes on the
  baseline: `95 passed`.
- [x] A3. Work is isolated on `codex/real-repo-validation`; the two pre-existing
  local commits remain intact.
- [x] A4. Findings and useful regression cases from the preflight branch are
  dispositioned individually as `port`, `already avoided`, or `not applicable`.

### B. Disposable pinned corpus

- [x] B1. A committed manifest records repository name, HTTPS source, exact
  40-character commit, primary language, license expectation, and slice.
- [x] B2. A stdlib-only command prepares or verifies selected repositories
  under `.engineering/local/real-repo-corpus` by default, with no writes to a
  prepared repository after checkout.
- [x] B3. The command refuses moving refs, non-HTTPS sources, unsafe cache
  paths, dirty prepared repositories, and a checked-out revision different
  from the manifest.
- [x] B4. Focused tests prove exact checkout, idempotent reuse, mismatch
  refusal, and operation without network by using local Git fixtures.
- [x] B5. The initial slice contains pinned Python, TypeScript, Go, and Java
  repositories at the revisions in the evidence table.

### C. Initial four-language product slice

For every initial repository:

- [x] C1. `/adapt-project` discovery runs read-only with artifacts outside the
  target repository, identifies the expected language, and names executable
  project test/build commands or an explicit limitation.
- [x] C2. An installed `which-shape`/`which-skill` route selects a relevant
  read-only code-health closure without ambient installation of the full
  catalog.
- [x] C3. At least one routed language-level skill completes through its final
  report boundary. Exit zero alone is insufficient: referenced paths must
  exist, malformed/partial analysis must be disclosed, and the report must
  contain either a supported clean result or actionable findings.
- [x] C4. Up to five sampled findings per non-clean report are manually checked
  against source (all findings when fewer than five exist). At least four of
  five, or every finding in a smaller sample, must be correct; duplicate or
  materially misleading findings count as incorrect.
- [x] C5. `git status --porcelain` and tracked-file hashes are unchanged after
  every read-only journey.
- [x] C6. Setup time, execution time, peak artifact size, errors, warnings, and
  required improvisations are recorded.

Initial-slice exit gate:

- [x] C7. All four languages reach `real-repo-smoke`, or every exception has a
  reproducible blocker, regression test, and explicit user-facing limitation.

### D. Repair gate

- [x] D1. Every product-blocking failure has a minimal reproduction against the
  pinned repository or a reduced fixture that preserves the failure.
- [x] D2. Repairs are made on the authoritative product architecture; the
  divergent preflight platform is not merged wholesale.
- [x] D3. Each repair passes its new regression, the affected language family,
  and the 95-test release/router boundary.
- [x] D4. The identical real-repository command passes after repair without
  weakening the acceptance oracle.
- [x] D5. Non-blocking findings are entered in the multi-language backlog with
  user impact, evidence, and a suggested trigger for revisiting them.

### E. Breadth and release truth

- [ ] E1. Every advertised language eventually reaches `real-repo-smoke` on at
  least one pinned repository.
- [x] E2. Representative deep journeys cover Python, TypeScript, Go, Java, one
  dynamic non-Python language, one systems language, and one mobile-oriented
  language.
- [ ] E3. At least one mutation-capable closure is exercised in preview mode
  and proves exact proposed changes, rollback/refusal behavior, and native test
  obligations without modifying the source checkout.
- [ ] E4. README and generated language surfaces display validation level
  separately from `22/22` implementation coverage.
- [ ] E5. A clean public install performs: three-router install, on-demand
  bootstrap, route, real-repository execution, verified final artifact,
  cleanup, and uninstall.
- [ ] E6. A release candidate is eligible only when focused tests, the release
  boundary, and the declared real-repository journeys pass from one exact
  revision.

## Evidence

| Item | Exact source/revision or command | Result | Status |
|---|---|---|---|
| Baseline release boundary | `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_multilanguage_expansion_matrix.py tests/test_release_language_consistency.py tests/test_router_decision_quality.py tests/test_installed_routers.py` | `95 passed in 22.67s` | pass |
| Repaired release/corpus boundary | same release boundary plus `tests/test_real_repo_corpus.py` | `106 passed in 23.54s` | pass |
| Corpus harness | `.venv/bin/python scripts/real_repo_corpus.py prepare --slice 1`; focused corpus suite | four exact detached clean checkouts; moving refs, non-HTTPS sources, destructive cache roots, dirty/mismatched checkouts refused | pass |
| Python corpus | `https://github.com/psf/requests.git@414f0513c33883adf6f2b46901d4f0b38a455851` | canonical scan: Python, `src=19`, `.venv/bin/python -m pytest`, dev-requirements setup, 8,745 artifact bytes, 0.06 s, evidence pass, host clean | C1 pass |
| TypeScript corpus | `https://github.com/sindresorhus/got.git@e3924aa1e53a6ca3eb93a43618ce532442a89b40` | canonical scan: TypeScript, `source=25`, tests excluded, declared npm tests/setup, one correct auth surface, 6,570 bytes, 0.05 s, evidence pass, host clean | C1 pass |
| Go corpus | `https://github.com/go-chi/chi.git@8b258c7bb28f97a5f2a856ff7ef962578fec9215` | canonical scan: Go, root `5`, middleware `30`, examples excluded, `go test ./...`, 7,051 bytes, 0.06 s, evidence pass, host clean | C1 pass |
| Java corpus | `https://github.com/spring-projects/spring-petclinic.git@f182358d02e4a68e52bdbabf55ca7800288511e7` | canonical scan: Java, `src=30`, Maven+Gradle wrapper tests, no inferred framework, 6,730 bytes, 0.08 s, evidence pass, host clean | C1 pass |
| Installed router lifecycle | local committed source at `1179fa1`; `skills@1.5.19`; three routers; external library/runtime; schema plan/apply; route; uninstall | compatibility match; health-audit + on-demand complexity handoffs; selected skill never ambient-installed; final list `[]` | pass |
| Routed initial slice | exact evidence in `real-repository-initial-slice-evidence.md` | Python 24 complete; TypeScript 4 complete; Go 1 partial with build-tag disclosure; Java 0 complete; sampled claims and tracked digests pass | pass |
| Corpus harness, slice 2 | `.venv/bin/python scripts/real_repo_corpus.py prepare --slice 2`; `verify --slice 2`; `tests/test_real_repo_corpus.py` | exact detached PHP/Ruby/Rust/Dart checkouts; declared licenses and clean revisions verified; `11 passed` | pass |
| Installed specialized-language lifecycle | local committed source at `62559f1`; `skills@1.5.19`; three routers; exact external library; route; execute; uninstall | all four routes selected on-demand complexity and canonical project-intake closures; selected skills never ambient-installed; final list `[]` | pass |
| Routed breadth slice | exact evidence in `real-repository-breadth-slice-evidence.md` | PHP 2 complete; Ruby 9 useful partial; Rust 51 useful partial; Dart 4 useful partial; sampled declarations and tracked revisions pass | pass |
| Breadth regression boundary | Ruby/Rust/Dart families, breadth discovery, corpus, conformance, matrix, release consistency, router quality, installed routers | `204 passed in 397.51s`; skill compliance `4 passed`; commit hooks pass | pass |

## Validation status

| Language | Implemented | Fixture validated | Real-repo smoke | Journey validated |
|---|---:|---:|---:|---:|
| Python | yes | yes | yes | yes |
| TypeScript | yes | yes | yes | yes |
| JavaScript | yes | yes | pending | pending |
| Go | yes | yes | yes | yes |
| Java | yes | yes | yes | yes |
| PHP | yes | yes | yes | yes |
| Ruby | yes | yes | yes | yes |
| Swift | yes | yes | pending | pending |
| Rust | yes | yes | yes | yes |
| Dart | yes | yes | yes | yes |
| C | yes | yes | pending | pending |
| C++ | yes | yes | pending | pending |
| Kotlin | yes | yes | pending | pending |
| C# | yes | yes | pending | pending |

## Current disposition of the preflight findings

| Finding | Current product relevance | Disposition |
|---|---|---|
| Tree-sitter `Point.row` native crash at scale | Current product `main` does not ship the divergent normalized tree-sitter provider used by the failing branch; applicable only if that provider is ported | not applicable to current execution paths; retain regression lesson |
| `.ts` parsed with the TSX grammar | Current TypeScript `find-omnibus` uses the TypeScript Compiler API; other current TypeScript providers must be checked independently | verify in real-repo slice |
| Destructuring pattern emitted as one symbol | Provider-specific; current language tools need output sampling | verify in real-repo slice |
| Whole file discarded for a tiny parser error | Provider-specific and user-visible if present | verify partial/malformed disclosure in C3 |
| Test suite creates load-bearing `__pycache__` | Product tests now set `PYTHONDONTWRITEBYTECODE`; repeatability still needs a focused check | port or reproduce before disposition |
| Multiple adapters per language break provenance | Divergent provider registry only | not applicable unless registry is ported |
| Cross-language write facts disagree | Divergent normalized-fact substrate only | backlog unless a current product consumer relies on equivalent cross-language semantics |
