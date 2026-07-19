# TypeScript `audit-decisions` learning handoff

Implementation revision: `a30ea88` (`Add portable TypeScript decision audit
support`), based on `8fa69f3`, 2026-07-19 UTC.

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
# 15 passed

.venv/bin/python -m pytest -q \
  tests/test_audit_decisions_typescript.py tests/test_decisions.py \
  tests/test_yaml_frontmatter.py
# 53 passed

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
| D3 TypeScript outcome | Locked TS/TSX positive, negative, must-not-fire fixture reaches `drift.md` and `raw-drift.json`. | pass |
| D4 change/guard | Not applicable: advisory/read-only audit, no code change or blocking guard. | n/a |
| D5 installed closure | Copied and real stock `skills@1.5.19` selected-skill tests run `python3 -I -S` outside checkout. | pass |
| D6 fresh forward | Fresh nested dispatch returned `agent thread limit reached`; exact clean packet remains ready below. | pending |
| D7 regression/conformance | Focused regressions, Ruff, py_compile, metadata, smoke, artifact drift, and conformance passed. | pass |
| D8 learning handoff | This MD/JSON pair contains evidence, exclusions, and translation prerequisites. | ready for review |

## D6 prepared packet

The clean raw host is
`/private/tmp/audit-decisions-forward.LOk2mx/host`; it contains the fixture and
only `.agents/skills/audit-decisions`, installed with:

```text
DO_NOT_TRACK=1 npx --offline --yes skills@1.5.19 add \
  /private/tmp/engineering-skills-ts-audit-decisions \
  --skill audit-decisions --agent codex --copy -y
```

The non-context natural task is: “Audit this project’s decision registry and
inline decision references. Produce the skill’s final report artifacts and
summarize which drift needs engineering attention. Do not edit source files.”
The eventual forward lane must use only that installed directory and host
`python3 -I -S`, without reading the source checkout, tests, learning packet,
or expected result.

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
attribution, uncommon JSX/type grammar may under-report a real comment, and
the stdlib frontmatter compatibility parser supports the registry's scalar and
list fields rather than arbitrary YAML. It fails visibly rather than silently
inventing an audit result. Keep this family lexical and read-only until D6
replays cleanly and a concrete future language requires a different parser.
