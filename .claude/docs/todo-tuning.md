# `/find-orphaned-ideas --todo` tuning

> This file is optional. When absent, `/find-orphaned-ideas --todo`
> uses its built-in defaults (`min_words=4`, no path skip, no age
> bound). Copy this file into your host project and uncomment the
> patterns relevant to your repo.

Optional host config for `/find-orphaned-ideas --todo`. When present,
the patterns below extend or override the skill's defaults.

Trigger: read this when authoring or calibrating
`/find-orphaned-ideas --todo` for your host project.

## Path skip

Glob patterns matched against the file path relative to repo root.
A path matching any of these is excluded from the scan. Use this for
vendor code, agent scratch, build artifacts that the walker doesn't
already prune via its directory blocklist (`.git`, `.venv`,
`node_modules`, `__pycache__`, `dist`, `build`, etc.).

Format: each bullet's leading backtick-delimited token is the glob
pattern. Anything after `—` is documentation.

Common patterns to consider (copy and uncomment as needed for your
host project):

<!--
- `.claude/worktrees/**` — Claude Code agent worktrees (full repo
  copies; scanning produces duplicate findings).
- `static/admin/js/vendor/**` — Django admin's vendored jQuery / Select2.
- `**/migrations/**` — Django migrations are generated code.
- `vendor/**` — Go / PHP vendored dependencies (turn off if you ship
  source under `vendor/`).
- `**/__generated__/**` — codegen output.
- `**/*.min.js` — minified JS bundles.
-->

## Min words

Override the default `min_words=4` threshold. Higher values surface
fewer, more substantive TODOs; lower values surface more noise.

The first integer-only line under this heading wins; comment lines
(starting with `#`) are skipped.

<!-- 4 -->
