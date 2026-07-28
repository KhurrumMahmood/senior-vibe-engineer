# Change specification — `adapt-project` real-repository slice

Status: verified; all A1–A7 criteria passed

## Grounded problem

The documented, copied `adapt-project/scripts/discover.py` completed on all
four pinned repositories, but its results were materially incomplete for
three common repository shapes:

- Got's conventional `source/` directory was absent, so observed TypeScript
  was mislabeled as JavaScript;
- Requests declared pytest configuration but received no test command; and
- Chi's domain-named `middleware/` package was absent while `_examples/`
  must remain excluded.

Spring PetClinic already produced a correct Java adapter through the canonical
entrypoint and is a no-regression host. The earlier empty Go/Java artifacts
were produced by the stale repository-level `scripts/project_adapt.py`, not by
the installed skill named in `SKILL.md`.

## Selected repair

1. Treat `source/` as a candidate root while preserving the existing
   JavaScript-family authored-source exclusions.
2. Inventory direct-child Go directories containing authored Go files, while
   retaining the established test/example/generated/vendor exclusions.
   Java package directories named `example` must not inherit Go's top-level
   example-directory exclusion.
3. Recognize pytest only from a valid structured `[tool.pytest.ini_options]`
   table or root `pytest.ini`, compose Python test commands with the venv setup
   interpreter, and prefer a declared `requirements-dev.txt` during setup.
4. Keep the skill contract and intent/provenance contract aligned with those
   accepted behaviors.
5. Suppress documentation-only lexical risk matches and require sensitive
   terms to occupy path-token boundaries; keep real authored-code matches.

## Explicitly not selected

- Do not grow `scripts/project_adapt.py` into a second multi-language product.
  Consolidating or retiring that stale discover surface is tracked separately.
- Do not infer Spring, React, Vite, or other frameworks from dependency text.
- Do not implement a universal dispatcher, result schema, transaction layer,
  or cross-language semantic platform in this slice.
- Do not accept every adversarial suggestion automatically. The semantic
  evidence gate, uniform specialized-language dispatch, report completeness,
  sensitive-path calibration, and legacy-helper retirement have separate
  triggers because they exceed the three demonstrated omissions.

## Acceptance criteria

- [x] A1. The TypeScript reduced fixture reports `source/` with one authored
  `.ts` file, excludes `test/`, and emits the declared Node setup/test commands.
- [x] A2. Valid structured pytest configuration emits a venv-composed test and
  setup closure; a dependency-only mention or malformed TOML emits no pytest
  command.
- [x] A3. The Go reduced fixture reports a domain-named package, excludes
  `_examples/`, and does not regress Java packages named `example`.
- [x] A4. The full affected TypeScript, Go, and Java families pass, including
  copied-install/final-artifact checks.
- [x] A5. The identical canonical read-only command on Requests, Got, Chi, and
  Spring PetClinic produces the expected language, root, command, and authored
  counts; `check_evidence.py` passes and every host remains Git-clean.
- [x] A6. A fresh independent verifier reviews the final diff and repeats the
  focused and real-host boundaries.
- [x] A7. Got's human report retains `source/core/utils/strip-url-auth.ts` and
  does not label its migration-guide documentation as a sensitive code surface.

## Exact expected real-host facts

| Host | Required facts |
|---|---|
| Requests | `python`; `src` has 19 authored Python files; test is `.venv/bin/python -m pytest`; setup installs `requirements-dev.txt` |
| Got | `typescript`; `source` has 25 authored TypeScript files; `test` is absent as a source root; Node test scripts remain visible |
| Chi | `go`; root has 5 authored Go files; `middleware` has 30; `_examples` is absent; test is `go test ./...` |
| Spring PetClinic | `java`; `src` has 30 authored Java files; Maven/Gradle wrapper tests remain visible; framework inference stays empty |
