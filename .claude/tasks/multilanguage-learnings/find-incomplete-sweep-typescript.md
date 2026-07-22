# TypeScript `find-incomplete-sweep` v1 learning handoff

Implementation revision: `8fa9371` (`Add TypeScript incomplete sweep
detection`) in isolated worktree `codex/typescript-incomplete-sweep`.

## Invariant and narrow TypeScript model

The language-independent invariant is an incomplete multi-site sweep: one
live sibling still has the old option shape while a strong majority of the
same resolved callable's siblings carry the newer shape. Detection remains
advisory: the compiler can establish a candidate and its evidence, but a human
must still decide `forgotten`, `deliberate`, `optional`, or `not-applicable`.

TypeScript/TSX v1 is deliberately limited to calls whose TypeScript Compiler
API resolved signature points to a **project function declaration**. It groups
those calls by that declaration, not lexical callee spelling; therefore direct
imports and aliases share a group while distinct overload signature
declarations do not. It collects option/property presence from object literal
arguments and resolves a local `const` object-literal `...spread`. A
destructured parameter default down-ranks an omission unless every present site
uses the same comparable non-default value, in which case the candidate is
promoted as a changed-result-shape risk. The original git-blame trajectory gate
is preserved: present sites must be newer than the straggler.

Method signatures (including framework/external APIs), runtime dispatch,
dynamic callees, unresolved spreads, JSX/React conventions, routes, and ORM
semantics are deferred rather than guessed. A static unresolved module,
dynamic callee, or unresolved spread makes the manifest `partial`; missing or
invalid prerequisites fail with exit 2.

## Final output oracle

Before accepting TypeScript detection, the lane added the language-neutral
`scripts/triage.py` writer. It validates exact packet accounting and the fixed
verdict vocabulary before it renders forgotten-first `triaged.md`; it rejects
missing, duplicate, unknown, invalid, multiline-rationale, and completionless
forgotten records. The TypeScript fixture drives the complete output boundary:

```text
Compiler candidate → manifest.json/findings.md → scout_packets.json
→ explicit scout_verdicts.json → triaged.md → /fix-workflow cluster:SW-01
```

`scout.py` reads compiler-resolved present-site locations from the TypeScript
manifest; it does not reimplement the detector. Both Scout and Step C retain
the detector's project-root report containment and reject symlinked output
files. The legacy Python `--out` behavior remains unchanged.

## Fixture and proof

`tests/fixtures/find-incomplete-sweep-typescript/host` pins TypeScript 5.9.3
and contains:

- a positive `buildRequest` sweep with a direct import, an import alias, two
  resolved local object spreads, three newer `region: "us"` sites, and one old
  omitted `region` site;
- a complete four-site control and a default-equal `stableRequest` negative
  that is down-ranked, not gated in;
- two overload call shapes that must not group together;
- a framework method-signature group that is explicitly deferred, never a
  candidate;
- direct generated/vendor/spec/declared-excluded targets, external and
  internal directory symlinks, report symlink escape, and Scout/triage
  symlink-output attempts;
- invalid TypeScript, missing tsconfig, missing host compiler, and an injected
  unresolved module that yields a `partial` manifest.

The focused oracle asserts exactly one gated-in candidate:
`buildRequest` / `region`, 3 of 4 resolved sites, at `src/calls.ts:10`, with
`"us"` overriding the declared `"global"` default. The test initializes Git
history so the three present call lines are in a later sweep commit. It also
asserts all source hashes remain unchanged.

## Verification at `8fa9371`

```text
.venv/bin/python -m ruff check \
  .claude/skills/find-incomplete-sweep/scripts/scan.py \
  .claude/skills/find-incomplete-sweep/scripts/scout.py \
  .claude/skills/find-incomplete-sweep/scripts/triage.py \
  tests/test_find_incomplete_sweep_typescript.py
# All checks passed

node --check .claude/skills/find-incomplete-sweep/scripts/detect_typescript_sweep.mjs
.venv/bin/python -m py_compile .claude/skills/find-incomplete-sweep/scripts/{scan.py,scout.py,triage.py}
# passed

.venv/bin/python -m pytest -q \
  tests/test_find_incomplete_sweep_typescript.py \
  tests/scripts/test_project_root_debaking.py
# 15 passed

.venv/bin/python .claude/skills/find-incomplete-sweep/scripts/test_scan.py
# 14 passed (Python oracle retained)

.venv/bin/python scripts/skill_meta.py lint
# OK — 76 skills, 76 declaring new contract

git diff --check
# clean
```

Every locked host starts with `npm ci --offline --ignore-scripts`, `npm run
typecheck`, and `npm test`; the copied and real stock `skills@1.5.19`
selected-skill executions rerun those native checks after scanning.

## D1–D8 status

| Gate | Status | Evidence |
|---|---|---|
| D1 scope honesty | pass | `SKILL.md` declares `language: any`, `scans: [python, typescript]`, exact resolved-call/property invariant, and all framework/dynamic defers. |
| D2 Python oracle | pass | Existing Python 14-test regression path remains green, including default promotion/down-rank and placeholder behavior. |
| D3 TypeScript outcome | pass | Locked TS 5.9.3 fixture reaches manifest → packet → verdict → `triaged.md`, with positive, complete, default, alias/spread, overload, framework, partial, and containment boundaries. |
| D4 change/guard | n/a | This is a read-only advisory detector; it proposes no automatic source mutation or blocking guard. |
| D5 installed closure | pass | Copied skill and exact stock selected-skill install run detector, Scout, and fixed writer outside the checkout; no repository `_common`, `scripts/_lib`, toolkit venv, sibling skill, or post-install network runtime. |
| D6 fresh forward | pass | A fresh no-context agent used only the installed skill and raw host. It resolved two raw divergences, correctly promoted none without blame trajectory, wrote packet/verdict/triage artifacts, passed native checks, and preserved source hashes. |
| D7 regression/conformance | pass | Focused 15-test set, Python 14-test oracle, metadata lint, Ruff, Node syntax, pycompile, fixture native checks, pre-commit, and diff check passed. |
| D8 learning handoff | pass | This MD/JSON pair records tool choice, exact outcome, closure, boundaries, and accepted D6 evidence. |

## Generalization and non-generalization

What generalized: the candidate→packet→explicit verdict→triage handoff, fixed
vocabulary, git trajectory idea, default-value promotion rule, project-local
exclusion/containment discipline, host-pinned Compiler API loading, native
fixture proof, and selected-skill closure procedure.

What did not generalize: Python AST collection and Django lookup filters;
framework API identity; arbitrary object/property dataflow; dynamic runtime
reachability; method/constructor semantics; React/JSX, ORM, or route
conventions; and a shared TypeScript parser/fact platform. One accepted
consumer is not justification for an ecosystem service.

## Tool decision, reuse, and future translation

The family-local Node launcher uses the host's TypeScript Compiler API via the
named tsconfig. It rejects lexical grouping because lexical names would merge
aliases, overloads, and unrelated methods; it rejects ts-morph/tree-sitter
because they add a dependency without supplying more of this accepted result.
It also rejects a shared resolver because no second accepted consumer needs
this exact call/property/default/trajectory contract.

A later semantic family may copy the *procedure*—host-local compiler loading,
project-relative exclusions, explicit partial state, final-artifact tests, and
stock selected-skill closure—but should implement its own facts. Do not extract
this launcher until a second accepted consumer proves the same requirements.

For Rust, Go, Java/Kotlin, C#, and Ruby, a future claim needs a locked host
fixture with language-native resolution of a declaration/call identity,
option/property/default semantics, ignored framework/dynamic boundary, Git
trajectory, exact final triage, native verification, and installed closure.
Analogy from TypeScript is not evidence.

## UX, residual risk, and next decision

The actual TypeScript command is one detector invocation then one Scout
invocation. It intentionally stops for human verdicts; `triage.py` tells the
user exactly when packet accounting is incomplete. The smallest later UX work
would be a helper that scaffolds an empty `scout_verdicts.json` with packet IDs
without inventing the verdicts.

Residual risks are deliberate: nested/non-const/aliased spreads, methods and
constructors, callbacks, generic conditional APIs, multi-project/reference
resolution, runtime framework semantics, and blame-unavailable histories do
not become candidates. The fresh installed D6 replay passed. The recommended
next step is to retain this boundary; do not broaden to
a shared TypeScript semantic platform or framework contract.
