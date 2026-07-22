# JavaScript language-expansion transfer guide

Status: accepted — JavaScript P2 complete

This guide compresses the cohort learning packets into instructions for the
next language pilot. The raw evidence remains in
`javascript-{syntax,lexical,semantic,proposal,mutation-guard}-learning.md`.

## What transferred from TypeScript

1. **Port outcomes by fact level, not skills alphabetically.** Lexical,
   syntax, semantic/project, proposal, and mutation/guard families share test
   and failure shapes without pretending they share one AST.
2. **Extend the accepted family-local engine first.** Existing TypeScript
   runners usually accepted JavaScript through explicit script kinds,
   checked-project configuration, and language-aware rendering. No shared
   execution platform was needed.
3. **Count support only at the final boundary.** A parser hit did not count.
   Each skill had to emit its established report/proposal, apply its declared
   mutation, or execute its generated guard.
4. **Keep copied closure executable.** The selected skill directory plus the
   host's own native tools had to work outside the repository. Literal command
   blocks were tested under both `.agents/skills` and `.claude/skills` layouts.
5. **Make partial coverage first-class.** Missing tools/config, syntax errors,
   config-excluded relevant files, unresolved edges, and unexpected mutation
   never became clean results.
6. **Preserve native verification.** Checked-JavaScript projects ran their
   pinned host compiler and tests; read-only skills hashed source and mutation
   skills proved exact diffs.

## What JavaScript required explicitly

- Inventory `.js`, `.jsx`, `.mjs`, and `.cjs` independently; TypeScript
  traversal does not imply JavaScript support.
- Choose script kind per suffix. `node --check` does not establish JSX or
  project-semantic support.
- Require named `allowJs` + `checkJs` configuration for semantic/project
  claims. Distinguish JSDoc authority from compiler inference and untyped
  strings.
- Preserve ESM extension spelling and treat only literal CommonJS
  `require(...)` as a static edge. Dynamic imports/require and package/alias
  conventions need explicit resolution or an unresolved outcome.
- Do not infer Node, React, or another framework from JavaScript, JSX,
  dependencies, or paths alone.
- Treat a documented command as an API: initialize its skill root inside the
  command rather than relying on a previous shell block.

## Process learning

### What improved throughput

- Freeze the 22-skill inventory and split it into disjoint fact-level cohorts.
- Give each lane exclusive skill/test/learning ownership; keep routers,
  matrices, and shared harnesses serial.
- Reuse the TypeScript final-artifact fixture and add only JavaScript-specific
  positive, must-not-fire, partial, and native-check cases.
- Run product-aligned review against installation, support honesty, final
  outcome, source safety, and likely user harm. Do not promote unrelated
  hardening into the plan.

### What nearly became a rabbit hole

The first `move-path` attempt grew a bespoke JavaScript lexer/resolver to more
than 500 new Python lines. It was stopped and preserved on an unmerged branch.
The replacement uses a small host-compiler span helper plus the existing move
engine, with a line-budget checkpoint before integration.

For future mutation ports:

1. decide the exact supported import/reference forms before coding;
2. prefer the target's native parser/compiler for source spans;
3. reuse the existing mutation, report, and rollback path;
4. checkpoint when new parsing/resolution code approaches 200 lines; and
5. choose an explicit limited disposition when the smallest safe path still
   demands a new language platform.

## Shared-tooling decision

No new runtime platform is justified by this pass. Repeated project-local
TypeScript loading remains family-local because extracting it would either
create hidden selected-skill dependencies or copy the same helper into every
closure. The common value is currently in contracts and tests:

- four-suffix source inventory;
- outcome vocabulary;
- copied-closure harness shape;
- source fingerprinting; and
- final-artifact/native-check acceptance.

Reconsider a runtime helper only when one real repair must change at least two
accepted consumers and the shared API is smaller than both implementations.

## Brief for the next language pilot

Start with three outcomes, not blanket coverage:

1. one read-only detector using the language's native parser/compiler;
2. one resolved proposal using the native project/package model; and
3. one bounded mutation or guard with exact diff and native verification.

The agent brief must name the native tool/version, source/package inventory,
generated/vendor/test exclusions, positive and must-not-fire fixtures,
partial/unsupported behavior, final artifact, copied closure, native command,
source-integrity rule, and what learning to return. Expansion is earned only
if at least two families transfer without skill-specific platform work.

## Closeout data

- The final matrix has 22 `javascript-supported` language-level skills and no
  pending or limited row.
- The accepted `move-path` branch adds a 138-line family-local Compiler API
  span helper and reuses the existing Python virtual-tree, replacement,
  report, apply, and rollback machinery. The rejected branch's custom lexer
  exceeded 500 new Python lines and remains unmerged.
- The JavaScript guard reuses `prevent-regression`'s staged
  generator/template/verifier contract and proves independent bad/good
  behavior across all four suffixes.

The three mixed-host journeys passed from clean three-router installations
with task skills loaded only from the on-demand library. Two first attempts
proved why direct outcome tests are insufficient: missing project context
overrode an explicit boundary proposal, and generic `old`/`new` path names
overrode an explicit file move. The repaired routers now preserve bounded
operation intent, and the exact natural prompts are regression tests.

The final product-aligned review passed after two bounded repairs: boundary
proposal routing now requires actual boundary intent, and checked-JavaScript
proposal evidence resolves literal CommonJS exports while downgrading dynamic
forms to partial. Candidate cutoff visibility is intentionally deferred as
ML-008; the broader router corpus is ML-007.
