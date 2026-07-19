# Validated-neutral planning skills — TypeScript host handoff

Validation revision: `08953b9` (`test(validated-neutral): prove TypeScript
planning artifacts`). Evidence date: 2026-07-19 UTC.

## Outcome

The first planning batch is genuinely host-language neutral. The skills do not
interpret Python, TypeScript, or framework semantics; they make a planning
judgment and produce a durable project artifact. A locked TypeScript host with
three small `.ts` modules, `tsconfig.json`, and a TypeScript 5.9.3 lockfile
replays five distinct natural tasks with unchanged `src/` bytes:

| Skill | Invariant and captured final outcome |
| --- | --- |
| `scope-feature` | Confirmed System-tier bounds become a `scoped` plan with concrete in/out/non-goal lines and observable criteria. |
| `architecture-fit` | An impacted plan becomes `architected`; decision/pattern/smell fit and a genuine P0 fork are visible rather than guessed. |
| `decide` | One material, cross-cutting choice becomes a proposed ADR with alternatives and verification, without touching source. |
| `design-it-twice` | Three divergent designs become one comparative analysis with agreements, differences, a named trade, and a `/decide` handoff. |
| `plan-spec` | A P0-clean architected plan becomes a bidirectionally linked draft spec whose goals, architecture, implementation, and exception come from the plan. |

The raw tasks are in
`tests/fixtures/validated-neutral-typescript/planning/tasks/`; the captured
durable results are in the sibling `artifacts/` tree. They are deliberately
not TypeScript variants of the skills: TypeScript only supplies a realistic
host source tree and code-root names.

## Closure audit and exclusions

All five selected directories are prose-only. The exact stock copy installed
only their `SKILL.md` files and the two local knowledge files that exist:

```bash
npx --yes skills@1.5.19 add <checkout> \
  --skill architecture-fit --skill decide --skill design-it-twice \
  --skill plan-spec --skill scope-feature --agent codex --copy -y
```

The combined install is legitimate: these are the System-tier chain, and
`architecture-fit` explicitly hands material forks to both
`design-it-twice` and `decide`; `plan-spec` is its terminal successor. The
test asserts that `.agents/skills` contains exactly those five copied
directories, none resolves into the checkout, and `decide/knowledge/rules.md`
plus `scope-feature/knowledge/structure-redesign-lessons.md` survive copying.

The SKILL instructions reference project-owned planning scripts and project
docs (`scripts/plans.py`, `scripts/decisions.py`, `scripts/specs.py`,
`ai-docs/`, and `.claude/docs/`). Those are host project facilities, not
executables imported by the selected prompt-only skill. Per the prompt-only
validation rule, the batch uses copied SKILL/knowledge closure plus an
executable final-artifact oracle instead of inventing a launcher or copying a
toolkit runtime into every skill. No selected directory imports root
`scripts/`, `_common`, a toolkit venv, or another skill at execution time.

`scope-feature` has an intentionally conditional structure-redesign branch:
its local lesson mentions a shared structural-design reference. The locked
task is not a project-topology redesign, so that branch is not needed for this
neutral outcome and was not copied or generalized. It remains a separate
closure question if a future batch claims stock-installed structural-redesign
support. The batch also excludes framework inference, compiler/type facts,
Node/React/Express/ORM choices, and every implementation or source mutation.

## Executable artifact proof

`tests/test_validated_neutral_typescript_planning.py` performs the following
from a pytest temporary directory outside the checkout:

1. Copies the raw locked host, runs `npm ci --offline --ignore-scripts`, and
   runs `npm run typecheck`.
2. Performs the exact pinned stock combined install above from the temporary
   host.
3. Reads each distinct natural task (which contains no expected answer),
   materializes its captured final artifact, validates the skill-specific
   artifact contract, and checks the complete `src/` tree SHA-256 fingerprint
   after every result.

The artifact contracts are narrow and final-output oriented: `scoped`,
`architected`, `proposed`, comparative analysis with three real design files,
and `promoted`/`draft` plan-spec linkage. The test never asserts a parser
helper or an artificial `.ts` suffix branch. Each replay leaves the original
three TypeScript source files byte-identical.

Green evidence at `08953b9`:

```bash
"$REPO_ROOT/.venv/bin/python" -m pytest -q \
  tests/test_validated_neutral_typescript_planning.py \
  tests/test_plans.py tests/test_decisions.py tests/test_specs.py
# 75 passed

"$REPO_ROOT/.venv/bin/ruff" check \
  tests/test_validated_neutral_typescript_planning.py
# All checks passed

"$REPO_ROOT/.venv/bin/python" \
  scripts/skill_meta.py lint --quiet
# OK — 76 skills, 76 declaring new contract

"$REPO_ROOT/.venv/bin/python" \
  .claude/skills/_common/scripts/run_skill_smokes.py --quiet
# 55 eligible; 21 prose-only; 11 explicit smokes and 44 import-floor checks pass
```

The staged files also passed the full pre-commit hook set and `git diff
--check`.

## Disposition and remaining work

`architecture-fit`, `decide`, `design-it-twice`, `plan-spec`, and
`scope-feature` are ready for the tracker’s `validated-neutral` disposition:
their tested outcome is independent of the host application language, with no
TypeScript scan claim or TypeScript implementation added.

D1 scope honesty, D3 final TypeScript-host artifacts, D5 stock copied
closure, D7 regression/conformance, and D8 learning handoff pass. D2 and D4
are inapplicable: no Python detector/reference invariant or proposed source
change/guard exists. D6 remains intentionally open for the serial integrator:
a fresh non-context agent should receive one installed skill, the raw locked
host, and one task file without a captured result, then independently produce
and inspect the corresponding artifact.

No skill repair, router/catalog/tracker change, or shared runtime was needed.
The smallest later improvement is an integrator-owned D6 replay, followed only
if needed by a focused review of the optional structural-redesign knowledge
closure; do not broaden this neutral planning packet into framework support.
