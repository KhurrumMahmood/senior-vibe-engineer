# Wave 3 Minor 1 — W3-2 Repair Report

Owned skill dirs only: `brainstorm-ideas`, `decide`, `engineer-init`,
`architecture-fit`, `gut-check`, `impact-feature`.

## brainstorm-ideas

Findings verified:

- TRUE — `/promote-idea-to-pattern` was referenced as an invocable
  handoff, but `.claude/skills/promote-idea-to-pattern/` does not exist.
- TRUE — `argument-hint` omitted `--external-research` while the body
  documented and handled that flag.
- PARTLY — activation-standard gap was minor, not structural: the skill
  already had a near-top success block and failure table, but its write
  gate did not explicitly require the helper's real stdout/stderr.

Edits made:

- Added `--external-research` to `argument-hint`.
- Replaced the nonexistent promotion-skill route with the real path:
  record adoption evidence via `/track-idea event`, then manually follow
  `.claude/docs/pattern-library.md` once the Tier 2 gate is met.
- Added a Stage 4 artifact-truth gate requiring the real helper summary
  (`wrote`, `skipped`, validation failures) to be quoted.
- Added `.claude/docs/pattern-library.md` to cross-references.

## decide

Findings verified:

- TRUE — the embedded ADR template predates the current
  `scripts/decisions.py init` scaffold: generated ADRs quote `id`, add
  `namespace: core`, and include `embodied_by: []`.
- PARTLY — command-surface drift was not the cited defect, but the
  registry commands depend on the PyYAML-backed frontmatter parser, so
  the skill is more executable as written when it uses `.venv/bin/python`.
- FALSE — no missing failure table or overall success block was found.

Edits made:

- Updated the ADR template to match the generated scaffold fields:
  `id: "<NNNN>"`, `namespace: core`, and `embodied_by: []`.
- Made `scripts/decisions.py init "${SLUG}"` the scaffold source of
  truth before editing the ADR body/frontmatter.
- Switched registry and effectiveness commands to `.venv/bin/python`.
- Made Stage 3 verification output part of the success gate.

## engineer-init

Findings verified:

- TRUE — the skill had a good staged pipeline and sideways table, but no
  near-top `How success is judged` block.
- FALSE — no script/resource drift exists; this is intentionally
  prompt-only because it bootstraps the runtime.

Edits made:

- Added a near-top success block naming the actual runtime gates:
  root markers, venv freshness, dependency install via
  `.venv/bin/python -m pip`, and Stage 5 checks for `ruff`,
  `decisions.py list`, and `skill_meta.py lint`.

## architecture-fit

Findings verified:

- TRUE — the Scope block's `python3 (stdlib-only)` claim was false.
  `scripts/decisions.py` and `scripts/plans.py` import
  `_lib.yaml_frontmatter`, which imports PyYAML.
- TRUE — the documented script flags themselves matched reality:
  `decisions.py audit --json`, `decisions.py list --json`, and
  `plans.py audit` are real.
- FALSE — no missing success block, sideways table, or handoff rule was
  found.

Edits made:

- Replaced the false interpreter/dependency claim with the real venv
  contract.
- Switched registry/audit commands to `.venv/bin/python`.
- Added an artifact-truth success gate for the `plans.py audit` output.
- Added a failure-path row for missing PyYAML/runtime initialization.

## gut-check

Findings verified:

- TRUE — the precedents-absent path contradicted itself: the success
  gate required reporting unavailable precedent matching, while Scope
  and the sideways table said to skip silently.
- FALSE — `.claude/docs/precedents.yml` is correctly optional; the
  defect was disclosure, not requiring the file to exist.

Edits made:

- Updated Scope and the sideways table to use ADR-only matching when
  `precedents.yml` is absent and to state in the report that precedent
  matching was unavailable for that run.

## impact-feature

Findings verified:

- TRUE — the Scope block's `python3 (stdlib-only)` claim was false.
  `scripts/plans.py` imports `_lib.yaml_frontmatter`, which imports
  PyYAML.
- TRUE — the sideways table documented a phantom
  `/impact-feature --subsystems <sub>` rerun form. The actual argument
  surface is `<plan-name>` only.
- PARTLY — activation-standard dispatch was mostly present through the
  scout output contract, but the scout prompt did not explicitly state
  how its output would be judged.

Edits made:

- Replaced the false interpreter/dependency claim with the real venv
  contract.
- Switched `plans.py audit` to `.venv/bin/python`.
- Replaced the phantom `--subsystems` rerun instruction with the real
  rerun form: `/impact-feature <plan-name>` and select the missing
  subsystem at Stage 1.
- Added an artifact-truth success gate for the `plans.py audit` output.
- Added a failure-path row for missing PyYAML/runtime initialization.
- Added a `How your output is judged` block to
  `impact-feature/agents/scout.md`.

## Resource Checks

Owned supplementary resources exist and are non-empty:

```text
$ test -s .claude/skills/decide/knowledge/rules.md && test -s .claude/skills/impact-feature/agents/scout.md && test -s .claude/skills/brainstorm-ideas/scripts/brainstorm.py && echo owned_resources_nonempty
owned_resources_nonempty
```

External reference targets used by the edited skills also exist and are
non-empty:

```text
$ test -s .claude/docs/idea-ledger.md && echo idea_ledger_exists_nonempty
idea_ledger_exists_nonempty

$ test -s .claude/docs/pattern-library.md && echo pattern_library_exists_nonempty
pattern_library_exists_nonempty

$ test -s ai-docs/decisions/0013-idea-tracking-system.md && echo adr_0013_exists_nonempty
adr_0013_exists_nonempty

$ test -s .claude/docs/architectural-smells.md && test -s .claude/docs/canonical-patterns.md && echo docs_exist_nonempty
docs_exist_nonempty
```

## Verification Output

Required skill metadata lint:

```text
$ .venv/bin/python scripts/skill_meta.py lint
OK — 76 skills, 76 declaring new contract
```

Required artifact-drift gate:

```text
$ .venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate brainstorm-ideas decide engineer-init architecture-fit gut-check impact-feature
# exit 0; no output
```

Command-surface smoke checks:

```text
$ .venv/bin/python .claude/skills/brainstorm-ideas/scripts/brainstorm.py --help
usage: brainstorm.py [-h] [--dry-run] [--json] [--project-root PROJECT_ROOT]
                     batch_file

Bulk intake writer

positional arguments:
  batch_file

options:
  -h, --help            show this help message and exit
  --dry-run             Validate and dedupe without writing
  --json                Emit JSON summary instead of human-readable text
  --project-root PROJECT_ROOT
                        Target project root owning .claude/ideas/log.jsonl
                        (default: git toplevel of cwd, else cwd)
```

```text
$ .venv/bin/python scripts/decisions.py init --help
usage: decisions.py init [-h] [--title TITLE] [--date DATE] slug

positional arguments:
  slug

options:
  -h, --help     show this help message and exit
  --title TITLE
  --date DATE
```

```text
$ .venv/bin/python scripts/plans.py audit --help
usage: plans.py audit [-h] [--json]

options:
  -h, --help  show this help message and exit
  --json
```

Matching pytest modules:

```text
$ .venv/bin/python -m pytest -q tests/test_decisions.py tests/test_plans.py tests/test_skill_meta_jobs.py
...............................................                          [100%]
47 passed in 0.11s
```

No direct pytest module exists for the prompt-only `engineer-init`,
`architecture-fit`, `gut-check`, or `impact-feature` skills; the matching
script-backed surfaces are covered by the command-smoke checks and the
`decisions.py` / `plans.py` / `skill_meta` tests above. No scripts were
changed in this lane.
