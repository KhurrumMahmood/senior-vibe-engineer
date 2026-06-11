# Linting

Ruff + pre-commit + CI are configured (see `pyproject.toml`,
`.pre-commit-config.yaml`, `.github/workflows/ci.yml`). Enforcement is
**diff-scoped** — pre-commit lints only staged files, and CI lints only
files changed vs `origin/main`. Existing violations in untouched files do
not block commits or merges.

## Install (once per clone)

```bash
.venv/bin/pre-commit install
```

The local AST hooks under `repo: local` use `language: python`, so
pre-commit creates an isolated hook venv on first run. No system
`python3` alias is required, which keeps the hooks portable across
Linux, macOS, and Windows. If a hook misbehaves after upgrading
pre-commit or changing the hook config, rebuild the hook venv with
`.venv/bin/pre-commit clean && .venv/bin/pre-commit install --install-hooks`.

Note: CI runs `python3 scripts/lint/run.py` directly (see
`.github/workflows/ci.yml`), not via pre-commit, so the local
pre-commit path and the CI path are independent. A green local
pre-commit does not, on its own, validate that CI will pass.

## Targeted check while editing

```bash
.venv/bin/ruff check <path>         # or a single file
.venv/bin/ruff check --fix <path>   # auto-fix safe issues
```

## Full-repo scan (on explicit request only — noisy)

```bash
.venv/bin/pre-commit run --all-files
```

## Escape valve for emergencies

Use sparingly — CI still runs:

```bash
SKIP=ruff git commit -m '...'
```

## Rule set

The active ruff rule set is intentionally narrow (`F`, `E`, `B`, `BLE`) so
the first commit doesn't surface hundreds of violations.

The project also runs custom AST/regex-based lints under `scripts/lint/`.
Each is diff-scoped, named, and uses a `# noqa: <name>: <reason>` (or
`{# noqa: <name>: <reason> #}` / `// noqa: <name>: <reason>`) allow-list.
The full catalogue lives in `canonical-patterns.md` under "Lint rules
(diff-scoped)" and is the single source of truth — every active rule is
listed there with scope, motivation, and allow-list shape. The runtime
contract (RuleSpec scopes, included/excluded paths, suffixes) lives in
`scripts/lint/run.py`; `.pre-commit-config.yaml` mirrors it. To see the
current set without leaving the shell:

```bash
.venv/bin/python scripts/lint/run.py --rule all --all  # runs everything
grep -E '^\s+name=' scripts/lint/run.py                # lists rule names
```

Widening the ruff rule set and adding new project-specific AST checks
happens via `/prevent-regression` (the GUARD job in the maintenance
workflow — see `skill-catalog.md`).

Some lints have an advisory sibling skill that catches a broader set of
shapes. For example, `comment-drift` is the commit-time slice of
`/find-comment-drift`: the lint blocks only clearly bad comments, while
the skill remains the fuller advisory report for JSDoc/docstring
cleanup. When a lint and its skill share doctrine, update both surfaces
together; the lint should import the skill's detector so the two
surfaces share the same heuristics.
