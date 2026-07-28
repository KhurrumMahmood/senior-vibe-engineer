# Stage 4 independent verification — `adapt-project` real-repository slice

Date: 2026-07-28

## Verdict: PASS

The bounded repair satisfies A1–A7 on the documented installed/canonical
producer, `.claude/skills/adapt-project/scripts/discover.py`. The current diff
does not modify `scripts/project_adapt.py`; that legacy helper was not used as
product evidence.

## Acceptance evidence

| Criterion | Independent result |
|---|---|
| A1 | PASS — The TypeScript reduced-host final-artifact test runs the canonical skill-local CLI, reports `source/` with one authored TypeScript file, omits `test/`, and has the Node setup path. The fresh Got scan independently confirms its declared Node test commands remain present. |
| A2 | PASS — The canonical TypeScript-family suite verifies `.venv/bin/python -m pytest` plus `requirements-dev.txt` setup for a valid structured `[tool.pytest.ini_options]` table, and verifies that a dependency-only reference and malformed TOML produce no pytest command. The fresh Requests scan matches the required closure. |
| A3 | PASS — The canonical Go test inventories a direct-child `middleware/` package and excludes `_examples/`; the full canonical Java family still accepts `src/main/java/example/...`. The fresh Chi scan reports root `5`, `middleware=30`, no `_examples`. |
| A4 | PASS — The affected TypeScript, Go, and Java final-artifact suites passed, including the copied-install/closure checks. |
| A5 | PASS — A new documented `-I -S` read-only scan and evidence-gate run on every pinned host exited 0; all four hosts remained Git-clean. The independent oracle verified the exact language, root count, and command expectations below. |
| A6 | PASS — This fresh review inspected the complete requested repair record, current diff, installed producer, canonical tests, and independently reran the focused and real-host boundaries. |
| A7 | PASS — The canonical regression test and fresh Got report retain `source/core/utils/strip-url-auth.ts` as the sole sensitive path and contain no migration-guide documentation match. |

## Fresh real-host results

| Host | Observed facts |
|---|---|
| Requests | `python`; `src=19`; test `.venv/bin/python -m pytest`; setup creates `.venv` then installs `requirements-dev.txt`; `src/requests/auth.py` is the observed sensitive path. |
| Got | `typescript`; `source=25`; no `test` source root; test commands `npm run test` and `npm run test:coverage`; setup `npm install`; only `source/core/utils/strip-url-auth.ts` is sensitive. |
| Chi | `go`; root `5`; `middleware=30`; no `_examples`; test `go test ./...`. |
| Spring PetClinic | `java`; `src=30`; tests `./mvnw test`, `./gradlew test`; frameworks is `[]`. |

## Commands and results

```bash
<repo>/.venv/bin/python -m ruff check \
  .claude/skills/adapt-project/scripts/discover.py \
  tests/test_adapt_project_typescript.py \
  tests/test_adapt_project_go_g1.py \
  tests/test_adapt_project_java_j2a.py \
  scripts/real_repo_corpus.py tests/test_real_repo_corpus.py
# exit 0 — All checks passed!

<repo>/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_adapt_project_typescript.py \
  tests/test_adapt_project_go_g1.py \
  tests/test_adapt_project_java_j2a.py \
  tests/test_real_repo_corpus.py
# exit 0 — 42 passed in 33.61s

<repo>/.venv/bin/python scripts/real_repo_corpus.py verify --slice 1
# exit 0 — Requests@414f051, Got@e3924aa, Chi@8b258c7, and
# Spring PetClinic@f182358d all verified clean at their manifest revisions.
```

For each host, I then ran the documented canonical boundary with
`<repo>/.venv/bin/python -I -S .claude/skills/adapt-project/scripts/discover.py`,
an external artifact root, fixed timestamp `stage4-20260728`, and
`--no-host-write`; then ran the canonical `check_evidence.py` against that
exact scan. All eight commands exited 0. A separate in-memory oracle asserted
the required A5/A7 values, adapter YAML/JSON semantic equality, terminal
status/analysis values, and report content; it exited 0.

## Findings

None. No implementation files were modified and no over-broad change or
regression was demonstrated within this repair's stated scope.
