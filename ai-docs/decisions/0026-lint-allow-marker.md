---
id: "0026"
namespace: core
title: Project lints use a dedicated, reason-mandatory `# lint-allow:` marker
status: proposed
date: 2026-06-09
provenance: "Promoted from a private host adaptation where this pattern is accepted and enforced; offered to core as a calibrated default."
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [host:scripts/lint/, .claude/docs/linting.md]
tags: [lint, suppression, convention]
related_smell: null
related_pattern: null
---

# Project lints use a dedicated, reason-mandatory `# lint-allow:` marker

## Context

A project that ships its own custom lints (AST checks, template checks,
project-specific rules) alongside a third-party linter needs a way to suppress an
individual finding. The tempting shortcut is to reuse the linter's native
suppression namespace — e.g. an inline `# noqa: <code>: <reason>` comment for a
Python linter, or the equivalent `// eslint-disable-line` / `// nolint` /
`# pylint: disable` form in other ecosystems. Borrowing that namespace for
project-owned codes causes recurring papercuts:

1. **The linter tries to validate foreign codes.** Most linters lex the token
   immediately after their suppression keyword as one of *their* rule codes.
   Project codes (typically lowercase-hyphenated, e.g. `my-project-rule`) do not
   match the linter's code grammar (often uppercase-plus-digits, e.g. `ABC123`),
   so the linter emits a cosmetic diagnostic such as `Invalid directive: expected
   a comma-separated list of codes`. This warning is often *finding-gated*: it
   fires only when the linter also has a genuine finding on the same line, which
   makes it intermittent and confusing — a line that linted clean yesterday warns
   today because an unrelated native rule started firing beside the project marker.
2. **Configuration cannot reliably register foreign codes.** Settings intended to
   teach a linter about "external" codes generally govern *unused-directive*
   detection, not the lex-time directive validation that emits the warning, so
   they do not silence it.
3. **It blocks the native unused-suppression check.** Sharing the namespace
   prevents later enabling the linter's "unused suppression" rule, because that
   rule would try to validate the project's custom codes as native codes and flag
   every project marker as unknown or unused.

The root issue is namespace collision: two independent tools cannot share one
suppression grammar when only one of them owns the code vocabulary.

## Decision

Project lints get their own allow-list marker, disjoint from any third-party
linter's native namespace:

```
# lint-allow: <code>: <reason>
```

1. **Reason is mandatory.** Each lint's marker regex matches only when a
   non-whitespace character follows the final colon. A bare `# lint-allow: <code>:`
   with no rationale does **not** bypass. The canonical pattern is
   `…lint-allow:\s*<code>:\s*\S`. This makes every deliberate suppression carry a
   documented reason and keeps them greppable.
2. **Language-aware comment prefix.** The marker rides whatever comment syntax the
   host file uses; each lint matches the `lint-allow: <code>:` substring regardless
   of the surrounding delimiter — `#` (Python/shell), `//` (JS/TS), `<!-- … -->`
   (HTML), `{# … #}` (a templating language).
3. **The third-party linter's native namespace is reserved exclusively for its own
   codes.** Project codes never appear after the native suppression keyword; native
   codes never appear after `lint-allow:`. Each tool owns its grammar.
4. **Two-marker form when a line trips both.** Some lines legitimately trip a native
   rule *and* a project lint — e.g. a broad catch-all handler the native linter
   flags *and* a project "no silent catch" lint also flags. Suppress both with two
   independent, co-located markers on one line — the native suppression first, the
   project marker second:

   ```python
   except Exception:  # noqa: ABC123  # lint-allow: <project-code>: <reason>
   ```

   (`# noqa: ABC123` is a generic stand-in for whatever native suppression the
   linter uses.) The markers are orthogonal: each lint looks only for its own
   marker, so a co-located native suppression neither helps nor hinders the project
   lint, and vice versa.

Adoption is a single hard cutover: each lint's marker regex and error strings move
to `lint-allow:` in lockstep with rewriting every existing project marker in the
codebase and in test fixtures/assertions. Any combined markers split into the
two-marker form. Pure native suppressions are left untouched.

## Alternatives considered

- **Register project codes via the linter's "external codes" configuration.**
  Rejected: that setting typically affects only unused-directive detection, not the
  directive lexer that emits the cosmetic warning, so the warning persists.
- **Keep using the native namespace and suppress the warning another way** (per-file
  ignore, global config). Rejected: the warning is finding-gated and scattered, so
  there is no clean global suppression; and it leaves project lints permanently
  coupled to the linter's namespace, still blocking the native unused-suppression rule.
- **One combined marker honored by both the linter and project lints.** Rejected: a
  third-party linter will not honor a foreign token. Two disjoint namespaces is the
  only arrangement that lets each tool own its own grammar.
- **No dedicated marker; rely on the native suppression for everything.** Rejected:
  project lints could not distinguish a deliberate, reasoned suppression from an
  unrelated native one, and could not enforce the mandatory-reason requirement.

## Consequences

- **Easier:** the cosmetic native directive warning is eliminated repo-wide.
- **Easier:** project lints are decoupled from the linter's namespace — adding or
  renaming a project lint can never reintroduce a native lex warning.
- **Easier:** unblocks enabling the linter's unused-suppression rule later, because
  its namespace will then contain only genuine native codes.
- **Easier:** every deliberate suppression is reason-mandatory and greppable —
  `grep` for `lint-allow:` enumerates all project suppressions with rationales, and
  the trailing-`\S` requirement prevents empty-reason escape hatches.
- **Explicit cost:** the two-marker form is now the canonical way to suppress a line
  that trips both a native rule and a project lint — slightly more verbose, but each
  marker's ownership is unambiguous and independently greppable.
- **Behavior-preserving:** a guard test should pin that a stale native-namespace
  suppression carrying a *project* code no longer bypasses, so the cutover cannot
  leave a silent escape hatch.

## Verification

- Lint unit tests are green with migrated fixtures, including cases asserting a bare
  `# lint-allow: <code>:` (no reason) does **not** bypass while
  `# lint-allow: <code>: <reason>` does.
- A negative guard test pins that a legacy native-namespace marker carrying a project
  code is ignored, and only `# lint-allow:` is honored.
- Representative files exercising each comment syntax confirm the marker suppresses
  correctly under its lint regardless of delimiter.
- The full lint gate runs clean, with no cosmetic directive warnings from the
  third-party linter.
- A repo-wide sweep confirms no project code remains in the native suppression
  namespace, except intentional documented exclusions (fixtures, or the negative
  test that must retain a legacy marker to prove it is ignored).
