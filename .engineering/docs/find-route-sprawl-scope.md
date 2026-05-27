# find-route-sprawl scope — engineering-skills-2

Per-skill scan/ignore scope for `/find-route-sprawl` on this repo. The
contract is **ignore-first**: the scan universe is the whole repo minus the
builtin skips (`.git`, `.venv`, `node_modules`, `.claude/worktrees`, build
and cache dirs, …) minus the `## Ignore` globs below. Declaring `## Roots`
is an optional narrowing — deliberately omitted here, because the principle
is "say what to leave out, not what to let in."

engineering-skills-2 is the skills toolkit itself, not a Django web app. Its
only `urls.py` files live inside skill **fixtures** (sample good/bad app
trees used to test other skills) — they are not this repo's routes. Ignoring
the fixture trees is what makes `/find-route-sprawl` report the honest answer
(no production urlconf) instead of mistaking the fixtures for routes. This
descriptor doubles as the canonical ignore-first example an adopting project
copies and edits.

## Ignore

- `.claude/skills/*/fixtures` — skill test fixtures (sample app trees, not source)
- `reports/` — generated skill-run reports
- `ai-reports/` — generated agent-run artifacts
