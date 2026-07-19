# move-path TypeScript v1 learning report

Installed forward-tested revision: `a4e73fe`, 2026-07-19 UTC. The repair
revision that incorporates the resulting findings is reported at handoff.

## Outcome and invariant

The accepted v1 invariant is a deterministic move of standalone `.ts` or
`.tsx` paths while rewriting only identity-resolved Markdown, HTML, config,
backtick, and exact-text references. JSON plans are the stdlib-only installed
format. `.yml`/`.yaml` plans remain an optional PyYAML compatibility mode.

This is deliberately not an import-safe module move. TypeScript and TSX source
imports remain byte-for-byte unchanged. When a local static import's target or
referrer is changed by a move, the report records it under
`code_imports.ignored` and **Ignored TypeScript Imports**. Python imports,
TypeScript aliases, project references, package exports, barrels, dynamic
imports, and framework routing remain deferred.

## Reference repair and tool decision

The existing Python/reference oracle already covered virtual-after-tree
Markdown rewriting, HTML, backticks, exact text, residue scans, apply/check,
and YAML plans. Two reference-path defects required repair. First, the loader
required PyYAML even for JSON input, which broke copied-skill closure. Second,
an in-root JSON plan included by `**/*.json` could rewrite its own `from`
field during apply, corrupting the operation's authority input and making the
post-apply check meaningless. JSON is now stdlib-only, YAML is explicitly
optional, and the exact resolved plan file is always excluded from reference
rewrites.

The chosen tool is the existing family-local Python filesystem/path resolver
plus a narrow static-import risk scan. No TypeScript compiler, parser,
ts-morph, tree-sitter, resolver platform, or network dependency was added:
the accepted result never rewrites imports. The non-exhaustive import scan
recognizes common single-line and multiline static `import`/`export ... from`
forms well enough to expose a move-target risk. It never proposes a replacement
specifier: extension, leading `./`, package spelling, and compiler-mode choices
remain unknown without TypeScript module resolution.

## Fixture and execution evidence

- Existing Python/current oracle: `tests/test_move_path.py` preserves eleven
  current move-path tests (Markdown, config, residue, apply/check, and YAML
  compatibility).
- TypeScript positive: a JSON-plan dry run moves `src/old.ts` to `lib/new.ts`
  plus `src/Card.tsx` to `lib/Card.tsx`, and produces Markdown, HTML, JSON
  config, and backtick rewrites through the final JSON/Markdown report.
- Must-not-rewrite: `src/consumer.ts` imports `./old`; its source remains
  unchanged and the report records `src/old.ts` -> `lib/new.ts` as ignored
  import risk. A moved source file importing an unmoved sibling is also
  recorded because its relative referrer changed. An external URL and ordinary
  prose remain unchanged.
- Negative: a `.yml` plan without PyYAML fails with an explicit optional-mode
  message; `rewrite.code_imports: update` fails rather than pretending import
  rewriting is available.
- Authority-input guard: an in-root `move-plan.json` matched by `**/*.json`
  stays byte-identical through dry-run and apply; final check validates the
  original move, and a second dry-run parses it and reports the expected
  `missing_source` state instead of consuming a corrupted plan.
- Import risk boundary: same-directory and moved-referrer cases expose target
  identity but keep `expected_specifier: null` with remediation unknown; a
  standard multiline `import { ... } from "./old"` is reported.
- Copied install: the test copies only `move-path/`, invokes both executable
  scripts with `python -I -S` from an outside cwd, and uses a JSON plan. It
  passed without repository helpers, site packages, or network access.
- Metadata/conformance: `scripts/skill_meta.py lint --quiet` reported
  `OK — 76 skills, 76 declaring new contract`; the move-path smoke also passed.

Commands observed:

```text
.venv/bin/python \
  -m pytest tests/test_move_path.py -q -k 'not standalone_typescript_fixture_typechecks_after_an_import_safe_move'
# 17 passed, 1 deselected

.venv/bin/ruff check \
  .claude/skills/move-path/scripts/move_path.py tests/test_move_path.py
# All checks passed!

.venv/bin/python \
  scripts/skill_meta.py lint --quiet
# OK — 76 skills, 76 declaring new contract

.venv/bin/python \
  .claude/skills/move-path/scripts/smoke.py
# ok
```

## Native typecheck blocker

The import-safe standalone fixture applies a move from `src/old.ts` to
`lib/new.ts`, retains an unrelated local type-only import, and then invokes
`tsc --noEmit --project tsconfig.json`. This host has no `tsc` on `PATH`.
The test therefore fails explicitly instead of installing TypeScript or
claiming native typecheck evidence:

```text
Failed: tsc --noEmit is required for the TypeScript native-typecheck acceptance evidence
```

As a result, the full targeted test command is honestly incomplete here:
`17 passed, 1 failed`. Re-run it in a host with an already-installed TypeScript
compiler before accepting D4/D7.

## Fresh installed forward evidence

The fresh installed run at `/tmp/es-forward-move.3U1DIN` exercised committed
revision `a4e73fe` through the copied skill under system `python3`, outside the
source checkout. It moved `src/legacy.ts` to `src/workflow.ts`, updated
`docs/guide.md` and `config.json`, left the source import in
`src/consumer.ts` byte-for-byte as `./legacy`, and recorded the ignored import
risk in both final reports. The host had no `tsc`, so no native typecheck was
claimed or installed.

That run also supplied the repair evidence: its report invented
`expected_specifier: "workflow.ts"`. The repaired schema now preserves the
resolved before/after target only, sets `expected_specifier` to `null`, and
labels remediation unknown without TypeScript module resolution. The forward
plan was under the normally excluded `.engineering/local/` tree, so the new
in-root plan regression separately covers the self-rewrite failure.

## Boundaries, reuse, and translation

The successful shared concepts are virtual-after-tree path identity, plan
schema, report shape, explicit risk reporting, and copied-install replay.
`audit_path_residue.py` is an actual second family-local consumer of
`move_path.load_plan`, `plan_patterns`, and the move identity helpers; the
copied-install test exercises both. Keep that reuse within `move-path` rather
than extracting a global adapter: no other family has demonstrated this exact
path/text contract.

The TypeScript-specific pieces do not generalize: extension probing is only
risk reporting, not compiler resolution; aliases, package conditions, barrels,
and project references need native compiler facts. Python import rewriting and
framework behavior also remain out of scope.

- Rust: require `cargo check`, `mod`/`use` fixtures, and macro/path fixtures;
  macros and crate features are semantic gaps.
- Go: require `go test` or `go list`, package import fixtures, and module
  replacement fixtures; module/workspace identity is a semantic gap.
- Java/Kotlin: require compiler or language-server resolution, package/import
  fixtures, and multi-module fixtures; overloads and package visibility remain
  gaps.
- C#: require Roslyn or `dotnet build`, namespace/using fixtures, and project
  reference fixtures; partial types and assembly boundaries remain gaps.
- Ruby: require a parser or language server plus `require_relative` and
  autoload fixtures; runtime load paths and metaprogramming remain gaps.

## UX, residual risks, and integrator proposals

The installed happy path is one copied skill directory, a JSON plan, and the
host Python 3.11+ interpreter. The smallest later UX improvement is an
installer/router-visible JSON plan template that names the ignored-import
report before users apply a move.

Residual risk: static import records intentionally under-detect unusual import
syntax, aliases, package imports, dynamic imports, and TypeScript
configuration. They are warnings, not a safe move authorization. Fresh
installed forward evidence now exists; native typecheck remains pending until
an environment provides `tsc`.

Serial integrator proposals, intentionally not implemented in this isolated
lane:

1. Reconcile the router/catalog language claim with `move-path` frontmatter
   only after reviewing this learning packet and the other batch evidence.
2. Add an environment with preinstalled `tsc` to run the committed native
   typecheck acceptance test; do not add a network install step.
3. Decide whether a future `tsconfig`-aware resolver is justified before any
   import-rewrite mode is exposed.
