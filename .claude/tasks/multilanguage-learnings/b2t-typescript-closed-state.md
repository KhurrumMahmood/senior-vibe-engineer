# B2T — TypeScript closed-state learning handoff

## 1. Invariant

A first-party closed state carrier has one exported runtime value authority.
First-party callers assign and compare that authority rather than bare strings.
External vendor wire literals stay at a named, reasoned boundary.

## 2. Reference repair

No new Python defect was found. The B2P reference replay remains green at this
revision: 8 targeted Python tests passed.

## 3. TypeScript model

The supported host owns TypeScript 5.9.3 and tsconfig.json. The detector uses
the project-local Compiler API to resolve the state receiver type. It treats a
string-literal union or enum as closed; it classifies, rather than migrates,
typed authorities, vendor payloads, tests/fixtures, unrelated status prose,
and open-ended string expressions. The reviewed replacement is an exported
as-const value object plus a derived union. No ORM or framework semantics are
claimed.

## 4. Tool decision

The family-local Node launcher resolves TypeScript through the host
package.json. It rejects a missing package or tsconfig with exit 2. The
Compiler API was necessary to distinguish a JobState receiver from an
open-ended string without a lexical guess. Rejected: ts-morph, tree-sitter,
ast-grep, a repository fact platform, and a shared adapter. The staged guard
copies its own source and needs only Node, the host tsconfig, and the host
TypeScript package.

## 5. Fixture results

Committed before/after hosts each pin TypeScript 5.9.3 in package.json and a
lockfile. The outcome test runs npm ci --offline --ignore-scripts, npm run
typecheck, and npm test for each host; it then runs copied detector, extractor,
generator, generated guard, and verifier outside the toolkit checkout.

Red transcript captured before production scripts existed:

    $ .venv/bin/python -m pytest -q tests/test_b2t_typescript_closed_state.py
    F
    Error: Cannot find module .../find-implicit-state/scripts/detect_typescript_state.mjs
    1 failed

Green evidence:

    $ .venv/bin/python -m pytest -q tests/test_b2t_typescript_closed_state.py
    2 passed

The test proves eight first-party pre-fix operations, detector
classification of every required false-positive boundary, proposal caller and
vendor inventories, after-fixture typecheck/native tests, nine TS/TSX guard
hits, clean fixed fixtures, reasoned vendor noqa, and 0/1/2 CLI paths.

Adversarial repair began with regression fixtures and failed before production
changes with `assert 4 == 8` first-party operations. The repaired detector and
staged guard cover a direct local alias, `??=`, every target in a chained
assignment, and a first-party `Job` operation in `vendor.ts`. Invalid detector
syntax exits 2. A forged noqa on that first-party receiver remains actionable;
the only suppressed literal has semantic receiver type `VendorJobPayload` and
a non-empty reason.

Repair validation:

    10 passed — combined B2T/B2P targeted outcome suite
    5 passed — skill meta/compliance tests
    OVERALL: PASS — scripts/skill_comply/validate.py
    PASS — ruff, five Node syntax checks, JSON parse, and git diff check

Fresh non-context forward lane PASS: a separate agent received only copied
find-implicit-state and extract-enum directories, the raw before host, and a
natural closed-state proposal request. It did not read after/tests/plan/
learnings/git. At /private/tmp/b2t-forward.lb5LzK it ran npm ci, detector, and
collector with rc 0; findings.jsonl has 9 records and 3 actionable Job.state
operations. review.md, proposal.md, and targets.json correctly retain the
vendor/test/open-text/unrelated-status boundaries; the agent verified that the
host source diff, excluding node_modules and .test-dist, was unchanged.

Forward commands, each rc 0:

    cd /private/tmp/b2t-forward.lb5LzK/host && npm ci --ignore-scripts
    cd /private/tmp/b2t-forward.lb5LzK && node installed/find-implicit-state/scripts/detect_typescript_state.mjs --target /private/tmp/b2t-forward.lb5LzK/host --project-root /private/tmp/b2t-forward.lb5LzK/host --tsconfig /private/tmp/b2t-forward.lb5LzK/host/tsconfig.json --output /private/tmp/b2t-forward.lb5LzK/artifacts/reports/implicit-state/scan-typescript-20260719-001/findings.jsonl
    cd /private/tmp/b2t-forward.lb5LzK && node installed/extract-enum/scripts/collect_typescript_state.mjs --findings /private/tmp/b2t-forward.lb5LzK/artifacts/reports/implicit-state/scan-typescript-20260719-001/findings.jsonl --project-root /private/tmp/b2t-forward.lb5LzK/host --output /private/tmp/b2t-forward.lb5LzK/artifacts/reports/extract-enum/typescript-state/targets.json --proposal /private/tmp/b2t-forward.lb5LzK/artifacts/reports/extract-enum/typescript-state/proposal.md

## 6. False-positive boundary

The detector emits but does not migrate typed authority declarations, vendor
payload comparisons, test/fixture operations, status-heading text, and
open-ended string comparison. The guard fires only when a state-ish property
has a semantically closed receiver. A non-empty vendor noqa suppresses the
matched boundary line only when the receiver's semantic type is explicitly
named `Vendor*Payload|Request|Response|Event|Message|Wire`; filenames, source
text, and forged comments do not provide vendor attribution.

## 7. What generalized

The invariant, JSONL detector-to-proposal handoff, before/after fixture shape,
copied-install replay, and red/green guard evidence parallel B2P.

## 8. What did not generalize

Django models.TextChoices, Python AST attribution, migrations, the Python root
lint wrapper, and a generic rule scaffold do not transfer. TypeScript needs
the host Compiler API and explicit module/tsconfig resolution.

## 9. Next-language translation

- Rust: require rust-analyzer or rustc facts, typed enum fixtures, bare
  string operation fixtures, and serde wire-boundary coverage.
- Go: require go/packages or gopls, named string constants, typed receiver
  fixtures, JSON-tag boundary coverage, and interface-resolution evidence.
- Java/Kotlin: require compiler/language-server facts, enum or sealed-state
  fixtures, DTO wire boundaries, overload/nullability coverage.
- C#: require Roslyn, enum or readonly value-type fixtures, typed properties,
  JSON converter boundaries, and partial-type coverage.
- Ruby: require a Ruby parser or language server, value-object/symbol
  fixtures, literal operations, external API boundaries, and dynamic receiver
  limits.

## 10. Reuse proposal

Keep the Compiler API launcher and staged guard local to this family. The only
candidate for later reuse is the outcome-first fixture and copied-install
procedure; there is no actual second consumer, so no code abstraction is
justified.

## 11. User experience

Pinned stock installation was replayed from a disposable host outside the
checkout and installed exactly the selected three directories under its local
`.agents/skills`:

    DO_NOT_TRACK=1 npx --yes skills@1.5.19 add /private/tmp/engineering-skills-ts-b2t --skill find-implicit-state --skill extract-enum --skill prevent-regression --agent codex --copy -y

The installed detector, collector, generator, and verifier then completed the
before/after host path. A host must already
provide Node, package.json, tsconfig.json, and TypeScript. The lockfile plus
npm ci --offline replay makes the fixture deterministic when the pinned npm
tarball is cached. The smallest later improvement to measure is a concise
host-prerequisite probe printed by the installed skill handoff.

## 12. Residual risks and next decision

The current guard intentionally protects only closed literal-union/enum
property receivers and one-hop local `const` aliases initialized directly
from such a property. Alias propagation, dynamic/computed access, arbitrary serializers,
and framework ORM fields remain out of scope. Do not extract a shared
TypeScript analysis layer until another accepted family proves the identical
contract.
