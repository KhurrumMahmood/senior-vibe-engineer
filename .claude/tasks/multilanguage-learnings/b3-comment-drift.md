# B3 TypeScript comment-drift pilot learning report

Revision: working tree on `codex/productization-restart`, 2026-07-19 UTC

## Outcome

`find-comment-drift` now scans `.ts` and `.tsx` through the same advisory
detector used for Python, JavaScript/JSX, and HTML/template files. Its bundled
guard owns the blocking subset, while the repository lint is only a thin
wrapper. A copied skill runs outside the toolkit checkout with isolated
stdlib-only Python.

The portable invariant is deliberately lexical: comments that narrate code,
detached banners, stale terms, brittle line references, and thin or missing
documentation candidates can be surfaced without a language type checker.
The detector does not establish API visibility, module identity, or semantic
correctness.

## Reference repair

- Detector and reporter imported repository `_common` modules, so an installed
  selected skill could not run. Their small filesystem/report closure now
  lives in `scripts/support.py`.
- The blocking lint duplicated orchestration outside the skill. The reusable
  implementation now lives in `scripts/guard.py`; the root lint dynamically
  loads it.
- The original JavaScript callable regex did not cover typed arrow return
  annotations. It now recognizes the fixture's typed async arrow.
- The first self-contained file walker incorrectly rejected every fixture
  below a hidden ancestor such as `.claude`. The scanner now evaluates hidden
  and generated directories relative to the requested scan root.
- The direct guard was green while the normal pre-commit `types_or` filter and
  lint runner `--all` collector still excluded TS/TSX. The hook now accepts
  `jsx`, `ts`, and `tsx` tags, and the runner collects those suffixes from
  normal `app/` and `src/` host roots. A copied-host end-to-end regression
  proves the final invocation path, not only the guard entry point.
- The contract described unrelated contradicted-count and TODO/FIXME behavior.
  It now names the bands the detector actually implements.

## TypeScript model and tool decision

The pilot needs only source text, suffix recognition, comments, nearby
function-like syntax, and typed parameter cleanup. It therefore keeps the
existing stdlib lexical detector and adds `.ts/.tsx` rather than introducing
the TypeScript Compiler API, tree-sitter, ts-morph, or a shared fact platform.
This is sufficient for review leads and insufficient for proving an exported
API or resolving aliases. That limitation is explicit in `SKILL.md`.

No Node dependency, network access, project `tsconfig`, repository helper, or
toolkit venv is required. The host prerequisite is Python 3.11+.

## Fixture and verification evidence

- Must fire: `fixtures/bad/bad.ts` and `bad.tsx` exercise narration, an
  exported typed async function, a typed async arrow with thin JSDoc, and a
  brittle `.ts` line reference.
- Must stay clean: `fixtures/good/good.ts` has useful typed JSDoc;
  `good/good.tsx` is an ordinary JSX-returning component and is not treated as
  a documentation candidate merely because it is TSX.
- `tests/test_comment_drift_typescript.py` proves detector behavior,
  detector/guard agreement, reasoned TypeScript allow-listing, and copied-skill
  execution under `python -I -S` outside the source checkout.
- `.claude/skills/find-comment-drift/scripts/smoke.py` preserves the existing
  Python/JavaScript/HTML oracle while including TS/TSX fixtures.
- A fresh non-context agent received only a copied skill and raw host fixture.
  It independently produced `detections.jsonl`, `report.md`, `findings.json`,
  and `latest` under
  `/tmp/es-b3-forward.yiYjNe/host/reports/find-comment-drift/`, reported the
  four useful `setup.ts` leads, and correctly identified `UserCard.tsx` as the
  clean component boundary. It reported no workflow-closure problem.

Commands and observed evidence:

```
../engineering-skills/.venv/bin/python \
  -m pytest -q tests/test_comment_drift_typescript.py
# 6 passed

../engineering-skills/.venv/bin/python \
  .claude/skills/find-comment-drift/scripts/smoke.py
# OK - 23 bad fixture findings, good fixtures clean
```

## False-positive and false-negative boundary

Ordinary components stay clean unless their name/shape independently matches
the existing public-ish handler/initializer heuristic. A reasoned
`// noqa: comment-drift: <reason>` suppresses the blocking guard, not the
advisory detector. The lexical scanner can miss re-exports, aliased callable
bindings, multiline signatures outside its regex, and public functions whose
names do not match the candidate heuristic. It can over-rank a locally named
handler that is not actually public. These are acceptable only because JSDoc
candidates remain advisory.

## What generalized—and what did not

Generalized successfully: file discovery, report schema, advisory-versus-
blocking split, reasoned allow-listing, copied-skill closure, and the lexical
comment bands. Python class docstrings remain Python-specific. TypeScript
export/type/module semantics did not generalize and were not approximated.
HTML/template rules remain textual rather than framework-aware.

No shared TypeScript abstraction should be extracted from this pilot. The
actual second consumer is absent; the useful reusable pattern is the test
shape: reference oracle, TS positive/negative/must-not-fire fixtures, final
artifact/guard agreement, and copied-install replay.

## Translation prerequisites

- Rust: extend suffix/comment recognition and fixture exported functions;
  rustdoc/visibility semantics require `rustdoc` or rust-analyzer before making
  public-API claims.
- Go: extend suffix/comment recognition and exported-name fixtures; `go/doc`
  or `go/packages` is required for package/API identity.
- Java/Kotlin: extend suffix/comment recognition and Javadoc/KDoc fixtures;
  compiler or language-server facts are required for visibility/overloads.
- C#: extend suffix/comment recognition and XML-doc fixtures; Roslyn is needed
  for symbol visibility and partial types.
- Ruby: extend suffix/comment recognition and YARD fixtures; a parser or
  language server is needed for metaprogrammed/public API claims.

## User experience and next decision

The useful installed path is one copied directory and one `python3` command.
The principal confusion was not TypeScript syntax; it was hidden source-tree
coupling and disagreement about which layer owned enforcement. Keep future
pilots family-local, prove the final installed command early, and introduce a
semantic TypeScript tool only for a skill whose accepted outcome genuinely
requires it.

B3 is complete. The final adversarial review first exposed missing pre-commit
and `--all` TypeScript dispatch, then returned PASS after the end-to-end repair.
The full repository suite produced 415 passes and one intentional skip; its one
failure is an unrelated pre-existing calendar-sensitive triage-audit test whose
fixed June 2026 fixture is compared by the CLI to real current time.
