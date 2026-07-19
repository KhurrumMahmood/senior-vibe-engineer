# adapt-project TypeScript v1 learning handoff

Implementation revisions: `e63a032` (`feat(adapt-project): add
self-contained TypeScript discovery`) and `023010c`
(`fix(adapt-project): default artifacts to host root`), plus `5f7dd5a`
(`fix(adapt-project): preserve Python stack heuristic`). The learning packet
is intentionally separate from implementation. `7337b1a` strengthens the
closure regression to use the pinned stock Codex installer. `085b2b9` repairs
the fresh D6 shell-expansion defect and executes the installed documented
commands verbatim in regression coverage.

## 1. Invariant

`/adapt-project` reports objective source-root facts and cautions without
promoting observed code into doctrine. Python source-root counts retain their
reference `>200` large-root caution. TypeScript v1 adds the identical outcome
for first-party `.ts` and `.tsx` source roots: the final adapter classifies the
root as TypeScript, records the total and extension breakdown, and the final
report carries the same large-root caution.

Excluded: Node/React/Vite/Next/Express framework inference from
`package.json`; TypeScript module resolution; type-checking as part of
discovery; framework- or ORM-specific conclusions; package-manager/trust
infrastructure; and any claim that a frequent host shape is healthy.

## 2. Reference repair

The reference `scripts/project_adapt.py` already emitted a `ts_files` count,
but its large-root caution read only `python_files`; it also relied on
repository imports and PyYAML, so a copied `adapt-project` directory could not
perform the documented final outcome. The lane did not change the shared
script. Instead, it froze the Python count/caution boundary in a dedicated
final-artifact test and added a stdlib-only, family-local installed command.

Python positive: 201 first-party `.py` files fires the existing caution.
Python negative: 200 does not fire. Python must-not-fire: 250 `.py` files
under `src/node_modules/` count as zero, preserving the reference common-skip
behavior. Python files alone still do not establish the stack language without
the reference's `manage.py`/`pyproject.toml`/`requirements*.txt` marker.

## 3. TypeScript model

- Syntax: `.ts` and `.tsx` filename facts only; no parsing beyond suffix and
  source-path classification.
- Type system: none.
- Module resolution: none.
- Runtime: Python 3 stdlib, run as `python3 -I -S`; no Node, TypeScript
  package, PyYAML, toolkit venv, repository `scripts/`, `_common`, or sibling
  skill is required by the installed discovery path.
- Framework: none. `package.json` contributes only package-manager markers
  and declared commands; its React/Vite keywords deliberately leave
  `frameworks: []`.
- TypeScript exclusions: `node_modules`, `dist`, `build`, `generated`,
  `vendor`, `test`, `tests`, and `__tests__` descendants; `*.d.ts`,
  `*.test.*`, and `*.spec.*` files.

## 4. Tool decision

Selected: a family-local stdlib `scripts/discover.py` plus
`scripts/check_evidence.py`. `adapter.yml` deliberately contains
JSON-compatible YAML, avoiding a copied-install PyYAML requirement.

Rejected: changing `scripts/project_adapt.py` (reserved shared surface), a
shared language adapter/fact platform, a Node/Compiler API dependency (suffix
and relative-path facts prove the accepted outcome), and framework inference
from dependency names. No abstraction was extracted because there is no second
consumer of this exact installed adapter closure.

## 5. Fixture and artifact evidence

The locked fixture is
`tests/fixtures/adapt-project-typescript/fixture.json`, materialized by its
checked-in `seed_host.py`. It pins 201 alternating `.ts`/`.tsx` source files,
seven excluded trees, `package-lock.json` with TypeScript 5.9.3, a native
typecheck, and a native Node test. The fixture has React/Vite *keywords* to
prove that package metadata does not make a framework fact.

`tests/test_adapt_project_typescript.py` asserts final `adapter.json`,
`adapter.yml`, `report.md`, and `evidence.json`, not a helper-only count. Its
positive TypeScript result is exactly 201 files (101 `.ts`, 100 `.tsx`) and
the large-root caution; 200 and exclusion-only roots remain clean. The test
uses `npx --yes skills@1.5.19 add <checkout> --skill adapt-project --agent
codex --copy -y` to install only the selected skill to
`.agents/skills/adapt-project`, runs both commands through `python -I -S` from
outside the checkout, and proves that no host adapter write occurs under
`--no-host-write`.

Green commands at `e63a032`:

```bash
"$REPO_ROOT/.venv/bin/python" -m pytest -q \
  tests/test_adapt_project_typescript.py tests/test_project_adapt.py \
  tests/test_skill_taxonomy.py tests/test_run_skill_smokes.py
"$REPO_ROOT/.venv/bin/python" \
  scripts/skill_meta.py lint --quiet
"$REPO_ROOT/.venv/bin/python" \
  .claude/skills/_common/scripts/run_skill_smokes.py --quiet
"$REPO_ROOT/.venv/bin/ruff" check \
  .claude/skills/adapt-project/scripts tests/test_adapt_project_typescript.py \
  tests/fixtures/adapt-project-typescript/seed_host.py
"$REPO_ROOT/.venv/bin/python" -m pre_commit run --files \
  .claude/skills/adapt-project/SKILL.md \
  .claude/skills/adapt-project/scripts/discover.py \
  .claude/skills/adapt-project/scripts/check_evidence.py \
  tests/test_adapt_project_typescript.py \
  tests/fixtures/adapt-project-typescript/fixture.json \
  tests/fixtures/adapt-project-typescript/package-lock.json \
  tests/fixtures/adapt-project-typescript/seed_host.py
git diff --check
```

Those checks produced 30 passed, metadata `OK — 76 skills, 76 declaring new
contract`, a green import-floor/smoke gate, and green lint/pre-commit/diff.
The full decode-safety conformance test was also run; it still fails on three
pre-existing `find-duplication` reads, but no longer lists either
`adapt-project` script.

Manual copied closure artifact:

```bash
cd /private/tmp/adapt-project-typescript-forward.qABrrP
python3 -I -S host/.agents/skills/adapt-project/scripts/discover.py \
  --project-root host --artifact-root artifacts --no-host-write \
  --timestamp 20260719-121500
python3 -I -S host/.agents/skills/adapt-project/scripts/check_evidence.py \
  --scan-dir artifacts/reports/adapt-project/scan-20260719-121500
```

This wrote and verified:

- `/private/tmp/adapt-project-typescript-forward.qABrrP/artifacts/reports/adapt-project/scan-20260719-121500/adapter.yml`
- `/private/tmp/adapt-project-typescript-forward.qABrrP/artifacts/reports/adapt-project/scan-20260719-121500/adapter.json`
- `/private/tmp/adapt-project-typescript-forward.qABrrP/artifacts/reports/adapt-project/scan-20260719-121500/report.md`
- `/private/tmp/adapt-project-typescript-forward.qABrrP/artifacts/reports/adapt-project/scan-20260719-121500/evidence.json`

The artifact says `typescript`, no framework, 201 source files, and the
large-root caution; it does not write `.engineering/project/adapter.yml`.
The copied-install regression also proves that an omitted `--artifact-root`
writes under the requested host's `reports/`, never the installed skill
directory.

## 6. False-positive boundary

React/Vite strings in `package.json` remain package metadata, not framework
facts. Test, declaration, generated, vendor, build, distribution, and
dependency-tree TypeScript files remain outside first-party source-root counts.
The only intentional false negative is source outside the established root
candidate set; discovery must not invent a source root from arbitrary
directories. A Python `vendor/` tree is intentionally not newly excluded: the
reference Python counter did not exclude it, and TypeScript support must be
additive rather than silently changing Python facts.

## 7. What generalized

The adapter/report/evidence artifact shape, the `>200` caution threshold,
read-only dogfood rule, source-root summary, standardization caveats, and
positive/negative/must-not-fire fixture method apply to both language paths.

## 8. What did not generalize

Python's reference skip semantics remain authoritative for Python files.
TypeScript's source/test/declaration/build exclusion policy is a TypeScript v1
fact. Node framework identity, package install, TS compiler semantics,
framework conventions, and profile/manifest activation remain outside this
language-level packet.

## 9. Fresh-forward packet (D6)

D6 **passed** at
`/private/tmp/adapt-project-typescript-forward.qABrrP/forward-evidence/journey-evidence.md`.
A fresh non-context agent used only the raw host and installed
`.agents/skills/adapt-project` closure, then produced the final adapter/report
for the natural task.

The first one-line shell form,
`ADAPT_PROJECT_SKILL="..." python3 ... "$ADAPT_PROJECT_SKILL/scripts/discover.py"`,
failed honestly with exit `2`: shell expansion happens before the temporary
environment assignment, so Python received `/scripts/discover.py`. The agent
then used a prior assignment line; discovery and the evidence gate both exited
`0`. It produced the exact final artifacts under:

- `/private/tmp/adapt-project-typescript-forward.qABrrP/forward-evidence/skill-artifacts/reports/adapt-project/scan-20260719-101037/adapter.yml`
- `/private/tmp/adapt-project-typescript-forward.qABrrP/forward-evidence/skill-artifacts/reports/adapt-project/scan-20260719-101037/adapter.json`
- `/private/tmp/adapt-project-typescript-forward.qABrrP/forward-evidence/skill-artifacts/reports/adapt-project/scan-20260719-101037/report.md`
- `/private/tmp/adapt-project-typescript-forward.qABrrP/forward-evidence/skill-artifacts/reports/adapt-project/scan-20260719-101037/evidence.json`

The final output reports 201 eligible TypeScript files (101 `.ts`, 100
`.tsx`), zero frameworks, and useful large-root/no-local-guardrail cautions.
The source fingerprint before and after is the same
`25845e911e4a575829a028ee10115019811bb1f3ec03770e1cd5a85605cda0a6`; no
`.engineering/project/adapter.yml` was written.

Repair `085b2b9` keeps `ADAPT_PROJECT_SKILL` on a preceding assignment line,
documents why the one-line temporary assignment is unsafe, and extracts both
installed pipeline blocks from `SKILL.md` after a pinned stock Codex install.
The regression concatenates and runs them verbatim with `/bin/sh`; it passes
only when discovery writes final artifacts and the evidence command prints
`adapt-project evidence OK`.

## 10. Next-language translation

Rust needs a Cargo-root/source-root classifier and locked `cargo test` fixture
with `target/`, generated bindings, vendored crates, and integration-test
exclusions. Go needs module/package root facts with `go test`, `vendor/`,
generated, and `_test.go` fixture boundaries. Java/Kotlin needs Gradle/Maven
source-set classification and `build/`/generated/test roots. C# needs project
source-set facts and `bin/`/`obj/`/test boundaries. Ruby needs Bundler/Rake
source-root facts and `vendor/`, generated, and test boundaries. None may
claim support based on extension analogy; each needs a final adapter/report,
positive/negative/must-not-fire counts, native command, copied closure, and a
fresh-forward outcome.

## 11. Reuse decision and user experience

Keep the discovery implementation family-local. Its deletion would leave this
skill without a stock installed outcome, while a new shared adapter would add
an unproven interface. Durable tests call the public command and inspect final
artifacts; there is no test-only seam. No actual second consumer exists.

Observed install is one normal stock copy of the selected skill under
`.agents/skills/adapt-project`; execution needs host Python only and completed
in under one second for the 201-file fixture. The biggest user friction was
the old documentation pointing to repository-global scripts that are absent
from a copied skill, followed by the D6 shell-expansion hazard in a temporary
one-line `ADAPT_PROJECT_SKILL` assignment. The installed command now requires
the variable assignment on its own preceding line and is replayed verbatim in
the copied closure test. The smallest later improvement worth measuring is a
serial, evidence-backed decision about whether other adapter-family skills
need the same self-contained closure; do not extract a shared runtime before
there is a second accepted consumer.

## 12. Residual risks and next decision

The shared source-tree `scripts/project_adapt.py` still has its historical
Python-only caution and remains intentionally untouched; serial integration
must decide whether it should delegate to or be replaced by this accepted
family-local closure without changing the frozen ownership boundary. Source
root candidates are intentionally limited and can miss unconventional
monorepo layouts. `adapter.yml` is JSON-compatible YAML rather than
human-styled YAML. The review portion of D8 remains pending serial-integrator
acceptance.

Recommendation: accept D1–D7 evidence, review this packet for D8, then keep
TypeScript discovery family-local unless a concrete second selected skill
needs the identical contract.
