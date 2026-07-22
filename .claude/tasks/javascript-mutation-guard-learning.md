# Checked JavaScript mutation and guard learning

## Outcome

The `move-path` family now has an explicit `update-javascript` mode for
reviewed `.js`, `.jsx`, `.mjs`, and `.cjs` moves. It rewrites only
Compiler-API-confirmed literal module specifiers, records each exact span
change, requires native host checks before and after mutation, and restores
the original files and moves if the post-apply check fails. The adjacent
`prevent-regression` family can stage a closed-state JavaScript guard only
from a complete detector manifest and real first-party findings.

## Tool choice and boundary

The implementation deliberately uses a small family-local Node helper with
the host's pinned TypeScript Compiler API. It requires an explicit
`jsconfig`/`tsconfig` with `allowJs` and `checkJs`; it does not add a Python
JavaScript lexer, a resolver, a shared language platform, aliases, package
resolution, extension inference, or framework rules. The bounded mover accepts
only explicit relative JavaScript filenames in static import/export, literal
`import()`, and literal `require()` forms. Dynamic/nonliteral imports are
reported and block a moved referrer.

This is intentionally a narrow tradeoff: roughly 300 net lines across the
mover integration and local compiler helper buy executable syntax/type/config
proof without pretending to solve general JavaScript module resolution.

## Verification evidence

The focused cohort copies both skill directories to a temporary installed
location, then proves a real mixed TypeScript/JavaScript host through the
final boundaries:

- exact ESM, JSX, dynamic-import, and CommonJS rewrites after five moves;
- `node --check`, host typecheck, and host tests after mutation;
- rollback with byte-identical source hashes when the post-move config no
  longer covers the moved files;
- missing configuration (`unsupported`), malformed source (`failed`), a
  symlink source (`unsupported`), and dynamic imports (`partial` plus a
  blocking record);
- detector-backed staged guard generation and independent bad/good fixtures
  for `.js`, `.jsx`, `.mjs`, and `.cjs`.

## Transferable and non-transferable parts

Transferable: virtual-after-tree planning, explicit status bands, exact
change records, native-tool validation before and after mutation, source
snapshot rollback, copied-closure tests, and evidence-gated staged guards.

JavaScript-specific: UTF-16 Compiler API spans, ESM/CJS/JSX syntax, the
`allowJs`/`checkJs` configuration gate, and JSDoc closed-union evidence. A Go
or another language cohort should keep the transaction/status/evidence shape
but use that language's host-native parser and checker rather than adapting
this helper.

## Residual risks and next trigger

The mode intentionally refuses unresolved module forms instead of guessing.
If a host needs aliases, package exports, extensionless imports, or framework
module conventions, that is a separate resolver-aware adapter with its own
fixture and rollback acceptance proof. Do not widen this family-local helper
incrementally without first naming that new boundary and proving it through a
copied installation.
