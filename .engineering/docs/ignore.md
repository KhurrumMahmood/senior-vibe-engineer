# Repo-wide ignore — engineering-skills-2

The **system-level ignore** that applies to *every* scope-driven skill on this
repo — the companion to each skill's own `.engineering/docs/<skill>-scope.md`.
Any such skill's scan universe is the whole repo minus the builtin skips
(`.git`, `.venv`, `node_modules`, `.claude/worktrees`, `.engineering`, build
and cache dirs, generated migrations) minus the globs below minus that skill's
own `## Ignore`. All three layers only ever subtract; a skill's optional
`## Roots` is the one knob that adds back, by narrowing.

This is the repo-wide floor: things that are never *this toolkit's own source*,
no matter which skill is asking. It doubles as the canonical ignore-first
example an adopting project copies and edits — declare what to leave out, not
what to let in. (Per-skill files exist only to narrow further; most adopters
need just this one.)

engineering-skills-2 is the skills toolkit itself, not a product app. Its only
`urls.py` / view / model-shaped files live inside **fixtures** — synthetic
good/bad app trees that exercise the skills (`.claude/skills/*/fixtures`) and
the test suites (`.claude/tests/*/fixtures`, e.g. the idea-extraction
truth sets). They are test data, not toolkit source, so a scope-driven detector
that scanned them would mistake the fixtures for real code and emit false
positives across the board. Ignoring them repo-wide is what lets every skill
report the honest answer about the toolkit itself. `## Roots` is deliberately
omitted: a repo-wide *narrowing* is nonsensical, and the loader discards any
roots found here anyway.

Patterns are `fnmatch` globs over the repo-relative POSIX path, not gitignore
syntax: `*` matches across `/` (so `app/*.py` also matches `app/sub/x.py`),
`**` is not special, and a bare directory name matches that directory and
everything beneath it. Anchor a pattern by writing its leading path segments.

## Ignore

- `.claude/skills/*/fixtures` — skill test fixtures (sample app trees, not toolkit source)
- `.claude/tests/*/fixtures` — test-suite fixtures (synthetic truth sets, not toolkit source)
- `reports/` — generated skill-run reports
- `ai-reports/` — generated agent-run artifacts
