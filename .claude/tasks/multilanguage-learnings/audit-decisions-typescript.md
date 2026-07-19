# TypeScript `audit-decisions` learning handoff

Implementation revision: `fbeca4e` (`Repair TypeScript JSX and regex
boundaries`), following the original additive implementation `a30ea88` and
based on `8fa69f3`, 2026-07-19 UTC.

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
`tokenize`, retains Markdown/HTML's existing `# decision:NNNN` form, and uses a
small TypeScript/TSX lexical comment scanner. The scanner skips quoted strings,
template text, regex literals, and TSX text; it recursively scans actual
template/JSX expression code. No TypeScript compiler, package manager,
network access, `tsconfig`, shared parser, shared fact platform, repository
helper, or sibling skill is necessary for comment attribution.

The scanner and every exclusion are deliberately family-local. A compiler API
would add host prerequisites without improving this lexical invariant.

## Adversarial lexer repair

Independent review at `fdad6b6` found three P1 attribution failures. JSX
fragments (`<>...</>`) were not recognized, so comment-shaped JSX text in
nested elements was scanned as code. The JSX/generic disambiguation rejected
an otherwise valid tag when a quoted attribute contained a comma. Finally,
`typeof` was absent from the expression-prefix contexts that permit a regex
literal, so `/* ... */` inside a regex character class was mistaken for a real
block comment.

The repaired scanner recognizes JSX fragment delimiters, inspects commas and
`extends` only outside quoted attributes and JSX attribute expressions, and
keeps valid TSX generic arrows (`<T,>` and `<T extends ...>`) out of the JSX
path. It also recognizes JavaScript/TypeScript expression-prefix keywords such
as `typeof`, `void`, and `instanceof` when deciding whether `/` starts a regex;
member access such as `.typeof` is not treated as a keyword context.

The locked one-line fragment replay retains the real
`{/* decision:0001 */}` expression comment while suppressing JSX-text ids
`9441` and `9442`. A quoted-comma attribute suppresses JSX-text id `9443`, and
regex literals after `typeof`, `void`, and `instanceof` suppress ids
`9444`–`9446`. Real comments inside both supported TSX generic-arrow shapes
remain visible. This closes the adversarial blockers without a compiler,
shared parser, or broader source support.

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
# 16 passed

.venv/bin/python -m pytest -q \
  tests/test_audit_decisions_typescript.py tests/test_decisions.py \
  tests/test_yaml_frontmatter.py
# 54 passed

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

## D1–D8 status

| Gate | Evidence | Status |
|---|---|---|
| D1 scope honesty | Installed skill freezes comment forms and literal/semantic non-goals. | pass |
| D2 Python oracle | Locked Python/Markdown/HTML positive and literal-clean cases reach final artifacts; source registry compatibility replay passes. | pass |
| D3 TypeScript outcome | Locked TS/TSX positives plus fragment, quoted-attribute, generic-angle, regex-keyword, and must-not-fire fixtures reach `drift.md` and `raw-drift.json`. | pass |
| D4 change/guard | Not applicable: advisory/read-only audit, no code change or blocking guard. | n/a |
| D5 installed closure | Copied and real stock `skills@1.5.19` selected-skill tests run `python3 -I -S` outside checkout. | pass |
| D6 fresh forward | A fresh non-context lane used only the stock-installed skill and raw host, produced all four final artifacts, identified the single real orphan, and preserved source bytes. | pass |
| D7 regression/conformance | Post-adversarial focused regressions (16/54), Ruff, py_compile, metadata, artifact drift, commit hooks, and conformance passed. | pass |
| D8 learning handoff | This MD/JSON pair records both the initial installed proof and the later adversarial repair. | ready for re-review |

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

The installed instructions were sufficient with no TypeScript toolchain,
package install, virtual environment, network, or `tsconfig`. The runner
printed the primary artifact path despite exit `1`, and all four outputs landed
predictably together. The only minor clarity friction was the phrase
“TS/TSX comment references: 7 total” above an inventory containing ten total
cross-language references; it is a correct TypeScript subtotal, but explicitly
labeling it “TypeScript subtotal” would reduce ambiguity in a later UX pass.
This D6 host exercised `a30ea88` before the adversarial fixtures were added;
its portability and source-integrity evidence remains valid, while current
selected-install closure is covered by the post-repair 16-test suite.

## False-positive boundary, reuse, and next languages

Strings, template text, regex literals, JSX text nodes, unrelated numbers,
generated/vendor/dependency/build/test paths, `.d.ts`, `.test`, `.spec`, and
minified source do not create references. A comment inside an actual template
interpolation or TSX expression does count.

Python tokenization, TypeScript lexical states, and the registry frontmatter
subset are intentionally not a shared parser abstraction. The only reusable
knowledge is the final-artifact fixture pattern and project-root-relative
exclusion regression. A future shared component needs a third accepted
consumer with the exact comment-attribution, exclusion, failure, and selected
closure contract.

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

Residual risks are deliberate: malformed TypeScript can defeat lexical
attribution, uncommon valid JSX/type grammar not represented by the locked
fragment/attribute/generic cases may under-report a real comment, and
the stdlib frontmatter compatibility parser supports the registry's scalar and
list fields rather than arbitrary YAML. It fails visibly rather than silently
inventing an audit result. D6 confirms that this family should remain lexical,
read-only, and family-local until a concrete future language requires a
different parser.
