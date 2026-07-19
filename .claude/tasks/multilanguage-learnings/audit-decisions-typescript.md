# TypeScript `audit-decisions` learning handoff

Implementation revision: `30f780a` (`Contain audit decision report outputs`),
following the Compiler API migration `aab14c8`, generic-JSX repair `259de78`,
the original additive implementation `a30ea88`, first adversarial repair
`fbeca4e`, and base `8fa69f3`, 2026-07-19 UTC.

## Invariant and scope

The audit must retain every valid `decision:NNNN` reference as evidence in its
final drift artifacts and surface an orphan only when its ADR id does not exist.
TypeScript v1 recognizes the token only inside line (`//`), block (`/* */`),
or JSDoc (`/** */`) comments, including real comments in template
interpolations and TSX expressions. It does not inspect identifiers, imports,
types, runtime behavior, or framework semantics.

The final `raw-drift.json` now retains `references[]` with path, line,
language, comment form, ADR id, and resolution status; `drift.md` repeats the
resolved inventory. This makes valid TypeScript/TSX references observable even
though they correctly produce no drift row.

## Reference repair and tool decision

The prior skill was instruction-only: its code-reference stage used a grep that
could not distinguish TypeScript comments from literals, and its registry stage
called a repository-level executable that a stock selected-skill copy does not
contain. Neither outcome was an installed audit.

`scripts/audit.py` is a family-local, Python-stdlib runner. It preserves the
registry audit/link-check compatibility artifacts, scans Python comments with
`tokenize`, retains Markdown/HTML's existing `# decision:NNNN` form, and invokes
the bundled Node helper for TS/TSX. That helper resolves the host's pinned
`typescript` package from `--project-root/package.json`, rejects parse errors,
and uses Compiler API literal/JSX ranges so its small comment pass only sees
real code trivia. Node.js and the project-local dependency are therefore
explicit prerequisites; the audit still does no package installation, network
access, `tsconfig` loading, semantic resolution, repository-helper import, or
sibling-skill import.

The runner, parser launcher, exclusion policy, and report-output boundary stay
family-local. The Compiler API owns TypeScript/TSX syntax boundaries; there is
no shared parser or fact platform because no second consumer has this exact
final-artifact and selected-install contract.

## Adversarial lexer repair (historical)

Independent review at `fdad6b6` found three P1 attribution failures. JSX
fragments (`<>...</>`) were not recognized, so comment-shaped JSX text in
nested elements was scanned as code. The JSX/generic disambiguation rejected
an otherwise valid tag when a quoted attribute contained a comma. Finally,
`typeof` was absent from the expression-prefix contexts that permit a regex
literal, so `/* ... */` inside a regex character class was mistaken for a real
block comment.

The former repaired scanner recognized JSX fragment delimiters, inspected
commas and `extends` only outside quoted attributes and JSX attribute expressions, and
keeps valid TSX generic arrows (`<T,>` and `<T extends ...>`) out of the JSX
path. It also recognizes JavaScript/TypeScript expression-prefix keywords such
as `typeof`, `void`, and `instanceof` when deciding whether `/` starts a regex;
member access such as `.typeof` is not treated as a keyword context.

The locked one-line fragment replay retains the real
`{/* decision:0001 */}` expression comment while suppressing JSX-text ids
`9441` and `9442`. A quoted-comma attribute suppresses JSX-text id `9443`, and
regex literals after `typeof`, `void`, and `instanceof` suppress ids
`9444`–`9446`. Real comments inside both supported TSX generic-arrow shapes
remain visible. These adversarial cases remain fixture evidence, but `aab14c8`
replaced the lexer with the Compiler API helper rather than extending lexical
states further.

A second adversarial review then found that generic JSX type arguments were
recognized as JSX but the tag scanner stopped at the generic argument's `>`.
For `<Select<number> />; /* decision:0002 */`, that left the outer `/>`
unconsumed and caused the scanner to treat all following code as JSX text.
The former repair tracked nested angle depth in both JSX recognition and actual
tag scanning, while treating `=>` inside a function type as an arrow rather
than a generic close. The exact self-closing replay and its nearby probes now
guard the Compiler API-backed outcome: nested/multiple/function type arguments,
member component names, quoted `>`/comma attributes, and non-self-closing
generic elements must retain following real comments while child text remains
ignored.

## Fixture and installed evidence

`tests/fixtures/audit-decisions-typescript/host` locks an accepted registry,
Python/Markdown/HTML references, TypeScript line/block/JSDoc references, TSX
expression comments, template-interpolation comments, literal/regex/JSX-text
must-not-fire values, and generated/vendor/dependency/build/test paths.

The dedicated final-artifact suite was initially red because
`scripts/audit.py` did not exist:

```text
.venv/bin/python -m pytest -q tests/test_audit_decisions_typescript.py
# 14 failed: cannot open .../audit-decisions/scripts/audit.py
```

After implementation:

```text
.venv/bin/python -m pytest -q tests/test_audit_decisions_typescript.py
# 17 passed

.venv/bin/python -m pytest -q \
  tests/test_audit_decisions_typescript.py tests/test_decisions.py \
  tests/test_yaml_frontmatter.py
# 55 passed

.venv/bin/ruff check .claude/skills/audit-decisions/scripts/audit.py \
  tests/test_audit_decisions_typescript.py
# All checks passed

.venv/bin/python scripts/skill_meta.py lint
# OK — 76 skills, 76 declaring new contract

.venv/bin/python .claude/skills/_common/scripts/run_skill_smokes.py \
  --skills-dir .claude/skills --timeout 20 --quiet
# 54 eligible, 11 explicit smokes + 43 import-floor checks: all passed

.venv/bin/python scripts/skill_comply/validate.py
# OVERALL: PASS
```

The absolute repository venv interpreter was used from the isolated worktree
because that worktree intentionally had no `.venv`. Post-repair `py_compile`,
the `find-skill-artifact-drift --gate audit-decisions` check, and commit hooks
also passed.

The actual current-repository replay also proved portable registry parity:
`registry-audit.json` has the same eight diagnostics as the existing registry
audit, and `link-check.txt` byte-matches its link-check output. It returned
the expected drift exit status because the repository contains old proposed
decisions, not because the runner failed.

The dedicated suite invokes the pinned stock installer
`skills@1.5.19` with only `--skill audit-decisions`, confirms that only the
selected directory appears under `.agents/skills`, and runs the installed
runner from an unrelated working directory with `python3 -I -S`.

## Exclusion-transfer lesson

Ignore policy belongs to the project root, not the caller's selected target.
The locked regression directly targets both directory and file forms under
`generated`, `vendor`, `node_modules`, `build`, and `tests`; every invocation
must produce an empty reference/drift result. Walking only from a narrowed
target and deciding eligibility relative to that target would let a direct
`--target vendor/file.ts` bypass the policy.

This is transferable to every language adapter: source ownership/exclusion is
a property of the host path, not of invocation convenience.

## Report-output containment repair

The report directory is a separate trust boundary from source-target selection.
Resolve both `--project-root` and `--output-dir`, then require the resolved
output path to be relative to the resolved project root before calling `mkdir`
or writing an artifact. That rejects an absolute external path, `..` escape,
an existing output-directory symlink, and a symlinked ancestor that points
outside; it still permits ordinary root-relative and absolute-contained report
paths.

The regression checks exit `2` and assert that the external directory remains
empty for every rejected path form. Positive relative and absolute-contained
paths must produce exactly `drift.md`, `raw-drift.json`,
`registry-audit.json`, and `link-check.txt`. The resulting invariant is
reports-only: the audit never turns an output-path spelling into a write beyond
the host project.

## D1–D8 status

| Gate | Evidence | Status |
|---|---|---|
| D1 scope honesty | Installed skill freezes comment forms, report-output containment, and literal/semantic non-goals. | pass |
| D2 Python oracle | Locked Python/Markdown/HTML positive and literal-clean cases reach final artifacts; source registry compatibility replay passes. | pass |
| D3 TypeScript outcome | Compiler API-backed TS/TSX positives plus literal/JSX and parser-error boundaries reach `drift.md` and `raw-drift.json`. | pass |
| D4 change/guard | Not applicable: advisory/read-only audit, no code change or blocking guard. | n/a |
| D5 installed closure | Copied and real stock `skills@1.5.19` selected-skill tests run `python3 -I -S` outside checkout. | pass |
| D6 fresh forward | A fresh non-context lane used only the stock-installed skill and raw host, produced all four final artifacts, identified the single real orphan, and preserved source bytes. | pass |
| D7 regression/conformance | 26 focused audit tests, 38 decisions/frontmatter tests, Ruff, Node syntax, pycompile, metadata, and commit hooks passed. | pass |
| D8 learning handoff | This MD/JSON pair records parser ownership and the output-containment repair. | pass |

## D6 installed forward journey

A fresh non-context lane received only the clean stock-installed host at
`/private/tmp/audit-decisions-forward.LOk2mx/host` and this natural task:
“Audit this project’s decision registry and inline decision references.
Produce the skill’s final report artifacts and summarize which drift needs
engineering attention. Do not edit source files.” It read the installed
instructions and ran only:

```text
python3 -I -S .agents/skills/audit-decisions/scripts/audit.py \
  --project-root "$PWD" \
  --output-dir "$PWD/reports/audit-decisions/forward-full-project"
```

Exit `1` was the documented completed-with-drift result. The independent
interpretation identified exactly one actionable finding: P0
`code-ref-orphan` at `src/decision_refs.ts:20` for nonexistent
`decision:9999`. It correctly reported the three-ADR registry and link checks
healthy, with no broken supersession, missing applies-to paths, aged proposals,
or unreferenced decisions. It recommended authoring ADR 9999 only if the
comment represents a real decision, otherwise removing or replacing the stale
reference, then re-running the audit.

All required artifacts are preserved under
`/private/tmp/audit-decisions-forward.LOk2mx/host/reports/audit-decisions/forward-full-project/`:

| Artifact | SHA-256 |
|---|---|
| `drift.md` | `2ed13724742dc3edda35967b0f9a5a893378dcf848149082ffac16ddad43705c` |
| `raw-drift.json` | `453bae8322011f888180ad1986edcbb15b0a033f98350b79b99f362094222adf` |
| `registry-audit.json` | `69c5b7ce62cfd2397002e625137e8d01f13fba56ab73842bde79e6a4ca9df2f0` |
| `link-check.txt` | `e684789cbf0e14973ecd88b9bc961543fd1b060445544fabc0ce4394655e281f` |

The pre/post aggregate source manifest was identical at
`c06a54d9b4edec541f49238ff5ec54494a2220364bb940cb055c20f2b00332f0`;
the installed skill was also unchanged. Complete transcripts, independent
interpretation, hashes, and friction notes are preserved under
`/private/tmp/audit-decisions-forward.LOk2mx/forward-evidence/`.

The installed instructions for that historical host were sufficient with no
TypeScript toolchain, package install, virtual environment, network, or
`tsconfig`. The current Compiler API path instead requires the host's locked
`typescript` package and Node.js, while retaining the no-install/no-network
contract. The runner printed the primary artifact path despite exit `1`, and
all four outputs landed predictably together. The only minor clarity friction
was the phrase
“TS/TSX comment references: 7 total” above an inventory containing ten total
cross-language references; it is a correct TypeScript subtotal, but explicitly
labeling it “TypeScript subtotal” would reduce ambiguity in a later UX pass.
This D6 host exercised `a30ea88` before the adversarial fixtures were added;
its portability and source-integrity evidence remains valid, while current
selected-install closure is covered by the post-repair 17-test suite.

## False-positive boundary, reuse, and next languages

Strings, template text, regex literals, JSX text nodes, unrelated numbers,
generated/vendor/dependency/build/test paths, `.d.ts`, `.test`, `.spec`, and
minified source do not create references. A comment inside an actual template
interpolation or TSX expression does count.

Python tokenization, the TypeScript Compiler API helper, and the registry
frontmatter subset are intentionally not a shared parser abstraction. The only
reusable knowledge is the final-artifact fixture pattern, project-root-relative
exclusion regression, and resolved report-output containment check. A future
shared component needs a third accepted consumer with the exact comment
attribution, exclusion, failure, output-boundary, and selected-closure
contract.

- Rust needs a comment tokenizer aware of raw strings and macro bodies, plus
  line/block/doc-comment, raw-string/regex-like, generated/test fixture cases.
- Go needs `//`/`/* */` comments, raw/interpreted string handling, generated
  and `_test.go` direct-target cases.
- Java/Kotlin need Javadoc/KDoc plus string/text-block and generated/test
  boundaries; a parser is only required if syntax beyond lexical comments is
  claimed.
- C# needs XML-doc/line/block comments, verbatim/raw string boundaries, and
  `obj`/`bin`/test fixture paths.
- Ruby needs comment and heredoc handling, generated/vendor/spec boundaries,
  and a lexical or native parser decision before supporting heredoc edges.

Residual risks are deliberate: an unavailable or parse-failing TypeScript
Compiler API aborts the audit rather than inventing a partial inventory, and
the stdlib frontmatter compatibility parser supports the registry's scalar and
list fields rather than arbitrary YAML. It fails visibly rather than silently
inventing an audit result. The family should remain parser-backed, read-only,
and local until a concrete future language requires a different native parser.
