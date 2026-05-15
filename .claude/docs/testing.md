# Testing Reference

How to scope tests and which suite to run for a given change shape. Host
projects extend the coverage map below with their own modules; the framework
itself stays generic.

## Verification policy (tiered)

Match test scope to the change. Don't run the full ladder for tiny work, but
don't skip verification on shared-surface changes either.

| Change shape | Run |
|---|---|
| Pure docs / comments | Nothing automated |
| Tiny local fix (one file, narrow blast radius) | Touched tests only — name them in your reply |
| Normal backend change | Always-suite (the host project's fast no-server smoke set) |
| Shared service / cross-cutting helper / settings | Targeted backend suite (host-defined module list) |
| UI / template change | Playwright or equivalent against running server |
| Live integration / live LLM / live network | Live suite (`--run-live`, env flag, or equivalent) |
| Endpoint touched | Manual JSON / page render check, no JS console errors |

If a verification step cannot be run, **state which one and why** — don't
claim done.

## Coverage map (host-project responsibility)

The host project's `docs/testing.md` (or this file, if you'd rather inline it)
lists every test module that the verification policy maps to, including:

- Always-suite modules — fast, no server, no Celery, no network.
- Targeted backend modules — module-level coverage of services, exports,
  discovery, extraction, custom-site logic, settings.
- Playwright / UI modules — page-level rendering and navigation checks
  against a running server.
- Live integration suites — opt-in via `--run-live` or an env flag.

Each entry should name the file, the surfaces it covers, and any
pre-conditions (server, Celery, network credentials, fixtures).

## Test infrastructure

Common scaffolding that every host project will need:

- **Shared pytest config** in `testing/conftest.py` registering markers and
  enforcing live-test gating.
- **HTTP response cache** for reproducible runs against external services.
- **Committed fixtures** for the workflows you don't want to re-derive from
  live state (extraction, discovery, image mapping, exports).
- **Live smoke targets** that are opt-in and clearly gated.

## Testing patterns

Reusable patterns the host project should keep consistent:

- **Capability tests** (user workflow outcomes) over granular unit tests.
- **End-to-end output proof** for data-pipeline work: cached input →
  pipeline → final executable boundary. A passing candidate scorer or
  adapter harness is not enough.
- **Mock async dispatch** instead of launching real jobs in tests.
- **Page-level tests** for UI rendering and navigation.
- **Live integration suites** marked and skipped by default.
- **Test-first protocol** — write the test before touching production code
  to expose gaps in the plan early.

See `.claude/docs/development-workflow.md` for the full implementation
discipline (test-first, post-implementation gut check, end-to-end core proof).
