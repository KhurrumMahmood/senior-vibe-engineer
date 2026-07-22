# Canonical Patterns

Project-specific patterns and lint rules that govern recurring code surfaces.
This file is the project's positive law: the shapes that should be used and the
shapes that lints block on entry. Host projects extend this catalogue as they
add their own patterns and `/prevent-regression` lands new diff-scoped rules.

The catalogue is organized by surface so you can scan to your area, not by
priority — every entry is load-bearing when its surface is touched.

## Backref convention — `Decided in: NNNN`

When a pattern entry codifies a choice that was recorded as an Architectural
Decision Record under `ai-docs/decisions/`, the entry should carry a
`Decided in: NNNN` line pointing at the ADR id. This turns the pattern
catalogue from a flat list into a graph — readers can follow the link to
recover the rejected alternatives, the consequences, and the supersession
chain (if any).

Add the backref as the LAST line of the entry, prefixed with two hyphens for
visual separation:

```
- **Pattern name** — short rule statement.
  -- Decided in: 0001
```

When `/decide` writes an ADR with `related_pattern: <anchor>` in frontmatter,
the skill recommends adding the matching backref here — the human applies it
(auto-edits to this file are not allowed). The `scripts/decisions.py
link-check` command verifies that every `related_pattern` in an ADR has a
matching `Decided in:` here, and flags missing pairs.

## Precedent convention — `Precedent: <id>`

Use `.claude/docs/precedents.yml` for updateable implementation case law:
recurring mechanisms with canonical examples, guards, exceptions, and a
supersession path. ADRs preserve historical decisions; precedents describe the
current law-as-applied. When a precedent changes, add a new `.vN` entry, set
the old entry's `superseded_by`, and either migrate old applications or narrow
the old precedent to an explicit legacy/branched surface.

Pattern entries can point at an active precedent with a final line:

```
  -- Precedent: <precedent-id>.v1
```

Run `python3 scripts/precedents.py check` after changing the registry,
canonical examples, guard tests, or a supersession chain.

## Lint rules (diff-scoped)

These run on every staged-files pre-commit and CI diff. Names match the
identifier that appears in failure output and the `# noqa: <name>: <reason>`
allow-list marker. See `linting.md` for the install/escape-valve mechanics and
`scripts/lint/run.py` for the canonical rule scope definitions.

- **`silent-catch` / `scripts/lint/silent_catch.py`** — never write
  `except Exception: pass` / `return None` / `continue` in service or view
  layers (default scope: `app/services/`, `app/views/`, `src/services/`,
  `src/views/`) without logging or re-raising. Log the failure via
  `logger.warning(..., exc_info=True)` (or equivalent) before returning, or
  add `# noqa: silent-catch: <reason>` when the outer transaction genuinely
  owns the error path. The allow-list reason is required (non-empty). See
  `tests/lint/silent_catch_{bad,good}.py` for the canonical bad/good
  examples and `.claude/skills/prevent-regression/` for how to add the next
  rule.

- **`stringly-status` / `scripts/lint/no_stringly_typed_status.py`** — any
  `status` / `phase` / `state` field on a model class must be a typed enum
  (e.g. Django `models.TextChoices`, Python `enum.StrEnum`, or equivalent),
  and every comparison (`obj.status == "foo"`) must reference the enum
  member (`obj.status == JobStatus.FOO`). Typos in bare strings produce
  silent no-op comparisons that look correct in tests but fail in
  production. Allow-list via `# noqa: stringly-status: <reason>` (reason
  required). See `tests/lint/no_stringly_typed_status_{bad,good}.py` for
  examples and `architectural-smells.md` smell 2.
  -- Decided in: 0001

- **`query-mutation` / `scripts/lint/no_query_mutation.py`** — methods
  named `get_*`, `fetch_*`, `load_*`, `list_*`, `find_*`, `check_*` must
  not call `.save()`, `.delete()`, `.update()`, `.update_or_create()`,
  `.create()`, `.bulk_create()`, `.bulk_update()`, or `.get_or_create()` on
  persisted objects. Exceptions: stdlib-mirroring wrappers named exactly
  `get_or_create` / `update_or_create`, and read-path methods marked with
  `# hidden-mutation: <reason>` documenting why the read-named method
  intentionally writes (reason required). See
  `tests/lint/no_query_mutation_{bad,good}.py` for examples and
  `architectural-smells.md` smell 3.

- **`fat-view` / `scripts/lint/no_fat_view.py`** — module-level view
  functions stay ≤80 non-blank LOC; View-class HTTP methods
  (`get`/`post`/`put`/…) stay ≤120 non-blank LOC. Oversized views almost
  always own business logic that belongs in a service. Allow-list via
  `# noqa: fat-view: <reason>` (reason required); budgets tunable via
  `--fn-budget` / `--method-budget`. See
  `tests/lint/no_fat_view_{bad,good}.py` for examples and
  `architectural-smells.md` smell 4 (layer violation).

- **`safe-dispatch` / `scripts/lint/no_bare_delay.py`** — Celery task
  dispatches in task / view / service layers must route through a
  `safe_dispatch(...)` helper. Bare `<task>.delay(...)` and
  `<task>.apply_async(...)` are flagged — they throw 500s on broker
  failure instead of controlled 503s with domain cleanup. Scope excludes
  the helper module itself and package `__init__.py` re-export shims.
  Allow-list via `# noqa: safe-dispatch: <reason>` (reason required) for
  `apply_async` sites that genuinely need routing options (`countdown`,
  `eta`, `queue`) that the wrapper does not expose. See
  `tests/lint/no_bare_delay_{bad,good}.py` for examples.

- **`comment-drift` / `scripts/lint/no_comment_drift.py`** — bad
  comments must not enter the live code surface. This blocks stale
  terminology, detached section banners, obvious narration comments,
  noisy template section comments, and brittle line-number doc references in
  Python, JavaScript/JSX, TypeScript/TSX, and HTML/template files. The
  repository entry point is a thin wrapper around the detector and guard
  bundled with `/find-comment-drift`. It deliberately does **not** block
  thin-public-docstring or
  `jsdoc_candidate` findings; those stay advisory in `/find-comment-drift`
  so the skill can guide broader taste passes without making every commit
  a prose rewrite. Allow-list via `# noqa: comment-drift: <reason>` /
  `// noqa: comment-drift: <reason>` /
  `{# noqa: comment-drift: <reason> #}` only when a comment is genuinely
  explanatory but the lightweight detector cannot see why.

- **`codegen-emits-new-paths` /
  `scripts/lint/codegen_emits_new_paths.py`** — string literals that get
  exec'd or eval'd at runtime (generated Python source stored in the
  database, in compiled artifacts, or in cached pipeline output) must
  not contain stale module paths. The motivating shape: a code generator
  emits `from old.package import X` strings that look fine at write time
  but raise `ModuleNotFoundError` on the next exec when the
  shim/legacy-alias is removed. Host projects override the include/exclude
  scopes in `scripts/lint/run.py` to point at their own codegen output
  surfaces. Allow-list via `# noqa: codegen-emits-new-paths: <reason>`
  (reason required, narrow scope: legacy fixture round-trips only).

Host projects extend this catalogue by:

1. Adding a new rule script under `scripts/lint/`.
2. Appending a `RuleSpec` entry to `scripts/lint/run.py`'s `RULES` tuple
   (or a host-project overlay file that extends it at import time).
3. Mirroring the rule into `.pre-commit-config.yaml` as a `repo: local` hook.
4. Documenting the rule's scope, motivation, and allow-list shape here.
5. Adding bad/good fixtures under `tests/lint/`.

See `.claude/skills/prevent-regression/` for the full lifecycle (cluster
evidence → fixture → lint → catalogue entry).

## Structural rules without lints

Some patterns are too contextual for a mechanical check but are nonetheless
load-bearing. They live here as documentation; a future
`/prevent-regression` instance may promote them to a lint if drift recurs.

- **Job identity is an explicit foreign key** — never inferred from
  `(status, timestamp, nullness)` tuples. If you catch yourself writing
  `.filter(status=X, created_at__gt=Y).first()` to find "the active job,"
  stop and add a FK on the owning row instead. Tuple-inferred identity
  breaks under concurrent jobs and hides in test fixtures. See
  `architectural-smells.md` smell 2 (tuple-identity sub-shape).

- **Parallel writers route through a shared producer** — when two code
  paths build the same output shape (same model rows, same dict, same
  export columns) on shared inputs, route construction through one
  canonical producer. If you catch yourself spreading the same
  construction at a second site, stop and extract — or carry a
  `keep_separate_document_why` sibling-pointer docstring if the
  interface-depth gate (`.claude/skills/_common/interface-depth.md`)
  rejects extraction. Per-shape AST lints land via `/prevent-regression`
  after a recurring instance justifies one. See
  `architectural-smells.md` smell 5 (format-equivalence gap).
  -- Decided in: 0004

- **Views and tasks are thin HTTP/dispatch wrappers** — parse request
  / load model / call service / return response. Business logic
  (domain loops, model interaction, multi-resource transactions,
  external-service calls) lives in a service module. See
  `architectural-smells.md` smell 4 (layer violation) and the
  `fat-view` lint above.

- **Status fields use typed enums** — every `status`, `phase`, `state`
  attribute on a model class is a `TextChoices` / `StrEnum` / equivalent.
  Comparisons reference the enum member, not the bare string. Enforced
  by the `stringly-status` lint.
  -- Decided in: 0001

- **Query methods are side-effect free** — anything named `get_*`,
  `fetch_*`, `load_*`, `list_*`, `find_*`, `check_*` does not mutate.
  Enforced by the `query-mutation` lint.

- **Frontend primitives — three call sites across two templates** — the
  threshold for extracting a reusable UI primitive (Cotton component,
  React component, partial, etc.). Below it, duplication isn't yet
  load-bearing. At or above it, hand-rolled UI shells become an
  architectural smell (frontend primitive bypass). See
  `architectural-smells.md` smell 7 (frontend primitive bypass).

## How patterns get added

The lifecycle for new entries:

1. A `/find-*` SUSPECT skill surfaces a recurring shape.
2. An EXPLAIN skill (`/extract-enum`, `/extract-state-type`,
   `/introduce-fk`, `/extract-workflow-registry`, etc.) proposes the
   positive form.
3. `/refactor-subsystem` or `/fix-workflow` executes the migration.
4. `/prevent-regression` promotes the shape to a diff-scoped lint and
   adds a Canonical Patterns entry pointing at the lint plus the
   architectural-smells anchor.

That sequence is what keeps the catalogue from accumulating dead
guidance — every entry traces back to a recurring real-world cluster
and a guarded execution surface.

## Related docs

- `architectural-smells.md` — the negative form of every entry here:
  what the smell looks like, what it costs, and which skills detect /
  fix it.
- `linting.md` — install, escape-valves, full-repo scans, rule-set
  roadmap.
- `precedents.yml` — implementation case law for recurring mechanisms
  that warrant explicit example/guard/supersession tracking.
- `ai-docs/decisions/` — the ADR registry that pattern entries cite via
  `Decided in: NNNN`.
- `skill-catalog.md` — the loop that produces new patterns: map →
  suspect → explain → refactor → guard.
