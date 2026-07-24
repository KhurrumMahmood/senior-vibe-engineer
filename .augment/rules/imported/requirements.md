---
type: "always_apply"
---

# Engineering Skills Ecosystem Requirements

## Functional Requirements

### Skill ecosystem core

- The maintenance loop is `map -> suspect -> explain -> refactor ->
  guard`. Each step has a small set of canonical skills; the catalogue
  lives in `.claude/docs/skill-catalog.md`.
- Skills are read primarily by AI agents, not humans. The frontmatter
  of every `SKILL.md` is a decision contract (`tier`, `job`,
  `best_for`, `not_for`, `language`, `framework`) -- `not_for` is the
  highest-leverage anti-misapplication field.
- `/which-skill` recommends or rules out a skill from a free-text task
  description by reading its generated metadata-only catalog, without loading
  every skill body into ambient context.
- `/which-shape` recommends the operating loop before tactical skill choice;
  review its `shapes.json` when a new skill changes a durable loop.
- `/which-cleanup` recommends bounded post-change checks using explicit Git or
  path scope; it does not execute those checks automatically.
- Default discovery contains exactly those three routers. Other skills and
  supporting tools stay in the external project-scoped library unless the user
  explicitly requests a validated optional install.
- `/diagnose` is the concrete-symptom lane beside the maintenance
  loop: reproduce, identify root cause, verify the fix, and name
  the prevention follow-up before broad cleanup.
- `/plan-skill` is the intake gate for broad new or materially
  revised skills. New skills need adversarial requirements, a
  trigger contract, evidence requirements, and at least one dogfood
  case before cataloging.
- `/check-ecosystem-consistency` is the post-change audit for the skill
  ecosystem. It compares against `.claude/ecosystem/last-state.json` and
  flags stale counts, missing catalog coverage, and shape-router review
  obligations.

### Host-state migrations

- Stock agent-skill installation and ordinary Git update distributed toolkit
  code. `scripts/host_migrations.py` is a separate, bounded lifecycle for
  toolkit-owned host state; it must not fetch code or become a package manager.
- Inspect with read-only `status` and `plan`. Run `apply` or `restore` only as
  an explicit mutation after reviewing the exact operations.
- Migrations may change only declared toolkit-owned `.engineering/` paths or
  validated managed blocks. Ambiguous legacy files, unmarked instructions, and
  project source require a human disposition and are never overwritten.
- A newer host-state schema is read-only to an older toolkit. Applied migration
  IDs live in the committed manifest; byte-level recovery data stays under the
  ignored `.engineering/local/` zone.

### Planning ladder

- **Quick** tier: one-line / one-file. No skill required.
- **Feature** tier: 1-3 day scope, one workflow. Use `/plan-feature`.
- **System** tier: multi-week or new-subsystem. Use the chain
  `/scope-feature` -> `/impact-feature` -> `/architecture-fit` ->
  `/plan-spec`. Each judgment pause is load-bearing; do not collapse
  them.
- **Maintenance** tier: the find/fix loop above.

### Decisions and precedents

- Material choices (architectural fork, choice that excludes
  alternatives, choice that constrains future work) get an ADR via
  `/decide`. ADRs live under `ai-docs/decisions/`. Target 2-5 entries
  per quarter.
- Recurring mechanisms that need consistent application get a
  precedent entry in `.claude/docs/precedents.yml` with canonical
  examples, guards, exceptions, and a supersession chain.
- When a precedent changes, add a new `.vN` entry, set the old entry's
  `superseded_by`, and either migrate the referenced cases or narrow
  the old precedent to an explicit branched surface.

### Lints (diff-scoped)

Active lints in `scripts/lint/`, mirrored into
`.pre-commit-config.yaml`, documented in `.claude/docs/canonical-patterns.md`:

- `silent-catch` -- no `except Exception: pass` in service/view
  layers without logging.
- `stringly-status` -- model `status` / `phase` / `state` fields must
  be typed enums.
- `query-mutation` -- read-named methods (`get_*`, `fetch_*`, etc.)
  must not mutate.
- `fat-view` -- module-level views <=80 LOC; View-class HTTP methods
  <=120 LOC.
- `safe-dispatch` -- Celery dispatches in task/view/service layers
  must route through a `safe_dispatch(...)` helper.
- `comment-drift` -- stale terminology, detached banners, brittle
  doc references blocked at the live code surface.
- `codegen-emits-new-paths` -- runtime-exec'd string literals must
  not contain stale module paths.

Host projects extend by adding a new `RuleSpec` to `scripts/lint/run.py`.

### Structural rules without lints

These live in `.claude/docs/canonical-patterns.md` as documentation;
`/prevent-regression` may promote them to lints when drift recurs:

- Job identity is an explicit foreign key, never tuple-inferred from
  `(status, timestamp, nullness)`.
- Parallel writers route through a shared producer.
- Views and tasks are thin HTTP / dispatch wrappers.
- Frontend primitives extract at >=3 call sites across >=2 templates.

### Cross-tool governance

- Durable agent rules start in `.claude/docs/` and are mirrored into
  tool adapters: `AGENTS.md` (Codex), `CLAUDE.md` (Claude),
  `.augment/rules/imported/` (Augment).
- A rule becomes a test / lint / hook / permission when it protects
  correctness, production writes, provider routing, or benchmark
  validity. Prompt context is advisory; durable boundaries need
  enforcement.

### Reporting and effectiveness

- Every skill writes artifacts under `reports/<skill-name>/scan-<TS>/`
  with a `latest` symlink.
- Final stage appends one line to `reports/_meta/effectiveness.jsonl`
  via `scripts/log_effectiveness.py`.
- `scripts/skill_effectiveness.py` aggregates the jsonl into
  `reports/_meta/dashboard.md`.

## Technical Conventions

- **Python runtime**: Run
  `python3 .claude/skills/which-skill/scripts/setup_runtime.py --project-root .`
  once per clone. It health-probes Python >=3.11, creates/rebuilds `.venv`,
  installs pinned requirements, verifies dependencies, and wires Git hooks.
  Use the reported `.venv/bin/python` path explicitly in delegated work.
- **Services**: Static methods, no instance state, lazy imports.
- **Views**: Thin HTTP wrappers calling services.
- **Comments**: Explain intent, ownership, contract, caveat,
  compatibility, or non-obvious history. Avoid narration, detached
  banners, stale terminology. `/find-comment-drift` is the advisory
  audit; `comment-drift` is the diff-scoped bad-comment lint.
- **Testing**: Tiered verification policy in `.claude/docs/testing.md`;
  match test scope to the change.
- **Frontmatter**: Validate with
  `.venv/bin/python scripts/skill_meta.py lint`.
- **Templates**: Never auto-format templates that embed agent syntax —
  any engine with embedded tags (Django `{% %}`, Jinja, Liquid, etc.) —
  because formatters break the tag parser.
- **Symbolic names, never raw line numbers** in comments, docstrings,
  or report prose.

## Detailed Documentation

See `.claude/docs/` for comprehensive reference:

- `canonical-patterns.md` -- positive law and lint catalogue
- `architectural-smells.md` -- negative form of every pattern
- `development-workflow.md` -- test-first / call-path / service / view
  prose
- `senior-engineer-posture.md` -- problem-class framing
- `skill-catalog.md` -- maintenance-loop skill list
- `linting.md` -- install, escape-valves, full scans
- `testing.md` -- coverage map, tiered verification
- `folder-organization.md` -- intra-folder placement
- `cross-tool-agent-governance.md` -- editing agent rules,
  cross-tool sync
- `quality-coordination-kernel.md` -- kernel architecture, ROI
- `precedents.yml` -- implementation case law
</content>
</invoke>
