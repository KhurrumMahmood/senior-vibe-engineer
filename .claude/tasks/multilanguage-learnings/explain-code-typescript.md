# explain-code TypeScript v1 learning handoff

Implementation revision: `0103a9e` (`feat: add TypeScript explain-code pilot`)

## 1. Invariant

`/explain-code` must leave a durable behavior document, not a symbol list.
For TypeScript v1, every named direct top-level export selected from a `.ts` or
`.tsx` target has a complete scout-backed contract in the final explanation;
unresolved export aliases and re-exports remain visible in the document and
`unexplained.txt`.

The Python AST path remains the reference oracle. The TypeScript v1 path does
not claim Python/Django modes, module resolution, React/Node behavior,
type-checker facts, or a framework contract.

## 2. Reference repair

The existing Python `inventory_symbols.py` depended on repository-level
`scripts/_lib/lang_adapter`. A copied installed skill therefore failed before
writing `targets.json` (`ModuleNotFoundError: _lib`). The Python implementation
is now stdlib-only again, and `python-oracle/expected-targets.json` freezes the
pre-existing public-symbol/ranking semantics. The first TypeScript pilot had
also dropped the Python directory exclusions for `migrations/` and
`tests_*.py`; the post-review directory oracle restored and locked both.

## 3. TypeScript model

- Syntax: named direct top-level `export` function/class/enum/interface/type/
  namespace/variable declarations in `.ts` and `.tsx`.
- Type system: no facts are inferred; type/interface names are inventory
  targets only.
- Module resolution: explicitly absent. `export { ... }`, `export *`, and
  default expressions are emitted as unresolved records.
- Runtime: the collector and renderer are stdlib Python scripts, runnable with
  isolated host Python; they do not run Node or a TypeScript compiler.
- Framework: none. Test, generated, declaration, vendor, build, and
  `node_modules` descendants are excluded relative to the requested target.

## 4. Tool decision

Selected: a family-local masked lexical collector plus a family-local renderer.
Masking comments, strings, and expression-position regex literals prevents
false `export` hits and brace-depth corruption while retaining line information
for stable ranking. The renderer deliberately consumes scout annotations
instead of synthesizing behavioral claims.

Rejected:

- TypeScript Compiler API: unnecessary for the accepted direct-export outcome;
  it would add an undeclared install dependency and invite an unearned resolver
  claim.
- A bare export regex: it would match comments/strings and has no honest
  unresolved-export channel.
- The repository language-adapter registry: one consumer and a copied-install
  failure are evidence against a shared adapter at this stage.

## 5. Fixture results

Red transcript before production edits:

```text
2 failed — copied inventory raised ModuleNotFoundError: No module named '_lib'
```

Post-review red transcript before the lexical repairs:

```text
3 failed — Python migrations/tests_ files re-entered the oracle; a regex
literal hid the following export while a multi-binding export lost `second`;
same-basename/same-symbol targets shared one symbol key and annotation path.
```

Green commands at `0103a9e`:

```bash
.venv/bin/ruff check \
  .claude/skills/explain-code/scripts tests/test_explain_code_typescript.py
.venv/bin/python -m pytest -q \
  tests/test_explain_code_typescript.py tests/test_skill_detector_reads.py \
  tests/test_skill_taxonomy.py tests/test_yaml_frontmatter.py
.venv/bin/python scripts/skill_meta.py lint --quiet
git diff --check
```

Result at the original revision: Ruff clean; 18 tests passed; frontmatter lint
clean; diff check clean. The post-review rerun commands and final counts are
recorded below in the machine-readable evidence.
`tests/test_explain_code_typescript.py` performs both the copied
`python -I -S` Python-oracle run and the copied `python -I -S` TypeScript
collector → scout annotations → renderer path outside the checkout. It asserts
the final Markdown, both sidecars, stable repeated `targets.json`, ignored
private/test/generated/vendor shapes, an honest alias/re-export region, and
source immutability. A separate target-under-`vendor/` test proves the ignore
rules are relative to the requested target, not an absolute ancestor.

D4 is not applicable: this is a read-only report skill with no proposed change
or guard. The report semantics are instead asserted at the final artifact
boundary.

The exact fresh D6 natural-task handoff was: “Explain the direct public exports
in src and produce the skill’s complete explanation artifact and sidecars.” No
expected diagnosis or answer was supplied. The parent holds the task prompt and
tool record; there is no transcript file to cite. The forward lane ran from only
the copied installed skill and raw fixture at
`/private/tmp/explain-code-forward.kvpvVc`. Both installed commands
exited 0 under `python3 -I -S`: inventory selected three direct exports from
eight total symbols and retained three unresolved export forms; rendering
wrote `reports/explanations/src.md`, three symbol annotations,
`src/unexplained.txt` (four entries), and `src/surprises.txt` (two entries).
The result explained `decide`, `renderLabel`, and `Badge`; kept alias, remote,
and star re-exports visibly unexplained; and recorded the missing `fallback`
source as a fourth unexplained region. Private/test/generated/vendor shapes
stayed excluded, direct-source hashes were unchanged, and only the reports
tree was created. The absent optional effectiveness logger was skipped rather
than fabricated.

The fresh artifact's first summary incorrectly said the lexical run “enforces
... typed TypeScript signatures.” No TypeScript compiler ran, so that was not
supported evidence. Adversarial review caught the overclaim; the final artifact
summary at the same evidence path now says signatures are source declarations
and explicitly says the run neither type-checks nor enforces them. Annotations,
sidecars, and the fresh lane's raw inventory evidence were not reinterpreted.

## 6. False-positive boundary

Legitimate private helpers and public symbols in test/generated/vendor trees do
not become annotation targets. Strings, comments, and regex literals containing
braces or `export` do not become targets or corrupt top-level depth. Simple
multi-binding exports inventory every identifier. Alias/re-export syntax is not
a false positive: it is retained as an explicit unresolved region. Known false
negatives are anonymous default exports and any module-resolved public surface.
Exported destructuring binding patterns remain explicitly unresolved instead
of silently disappearing.

## 7. What generalized

The stable `targets.json` shape, 15-symbol budget, scout annotation format,
renderer-owned document/sidecars, and no-source-mutation proof apply to both
the Python reference and TypeScript target paths.

## 8. What did not generalize

Python AST branch counts, `__all__`, methods, and docstrings are Python-only.
TypeScript export syntax, TSX, declarations, and re-export uncertainty are
variant-specific. Module resolution and caller discovery must not be extracted
from this lexical pilot.

## 9. Next-language translation

Rust needs `syn`/rust-analyzer facts for `pub` items and re-exports; Go needs
`go/parser` plus package/export fixtures; Java/Kotlin needs compiler or parser
support for public members and import aliases; C# needs Roslyn facts; Ruby needs
Ripper/Prism plus constant/module visibility fixtures. Each language needs a
direct-public positive, a private/test clean case, an export/re-export
uncertainty case, and a final rendered artifact before support can be claimed.

## 10. Reuse proposal

No abstraction is extracted. `inventory_symbols.py`'s comment/string/regex masking
and `render_explanation.py`'s annotation-to-sidecar renderer are potential
family-local references only. There is no actual second consumer, and no
shared parser, executor, or evaluator should be created yet.

## 11. User experience

The copied skill requires only Python already present in the host; the test
uses `python -I -S` and no network/package-manager step. The smallest later
improvement worth measuring is a router/catalog representation for a skill
with both a Python reference implementation and a narrowly supported
TypeScript variant. Until then, the frontmatter deliberately advertises the
earned TypeScript route and the serial integrator must regenerate the catalog.

## 12. Residual risks and next decision

The collector is lexical, so unusual multiline/type-heavy declaration spans and
anonymous defaults are intentionally incomplete. TypeScript v1 cannot resolve
an alias to determine whether it names a local symbol or a barrel dependency.
The fresh non-context D6 forward run passed. The serial integrator still needs
to regenerate the router catalog and review the resulting TypeScript-only
eligibility. Expand to module resolution only when a named `tsconfig`-backed
consumer needs it.
