# Validated-neutral quality skills — TypeScript host handoff

Validation revision: `3aef3e1` (`test: prove neutral TypeScript quality
skills`). Evidence date: 2026-07-19 UTC.

## Outcome

`diagnose`, `find-perimeter-gaps`, `gut-check`, `teach-pattern`, and
`triage-debt` have useful outcomes independent of a host application's source
language. One locked TypeScript host provides ordinary `.ts` ingress, worker,
and observability modules, a native `tsc --noEmit` baseline, realistic
symptom/context/evidence inputs, and five separate natural tasks. Each skill
is copied in its own exact stock install; no combined install is used because
these jobs do not require one another.

| Skill | Tested final outcome | Closure evidence |
| --- | --- | --- |
| `diagnose` | A diagnosis report names a real TS2322 queue-boundary mismatch, preserves a reproducer, root-cause proof, verification state, cleanup check, and evidence manifest. | The installed local evidence gate reads its sibling `SKILL.md` and manifest without toolkit `scripts/` or `_lib`. |
| `find-perimeter-gaps` | A `report.md` and `perimeter.json` honestly flag the significant `src × typescript` cell as uncovered; `language: any` does not pretend to scan it. | The copied local `scan.py` runs with host `python3` from the installed directory and exits 1 under `--fail-on-gap`. |
| `gut-check` | A plan reaction report separates un-decided concerns from an ADR-contradicted boundary shortcut, with citations and signal-not-verdict framing. | Prompt-only; canonical smells, ADR, optional precedent, and plan are host-owned context files. |
| `teach-pattern` | An agent-facing briefing explains boundary validation with a real host pattern, ADR, spec exemplar, cached counter-example, and stated enforcement gap. | Prompt-only; all cited authorities are supplied by the TypeScript host rather than the checkout. |
| `triage-debt` | A top-two ranked queue turns three recurring six-finding omnibus reports into a standardize-and-enforce route, then records stale spec drift. | The installed workflow consumes an explicit host cache and writes `inputs.md`; it does not invoke uninstalled registry/audit/log scripts. |

The raw requests are under
`tests/fixtures/validated-neutral-typescript/quality/tasks/`; they contain no
expected answer. The final report, verdict, briefing, and queue artifacts are
in the sibling `artifacts/` tree. The test copies each captured result only
after a separate stock installation and checks that the complete `src/` tree
SHA-256 stays identical.

## Selected-closure repairs

Two original instructions named repository-only authorities on the exercised
path:

1. `/diagnose` invoked root `scripts/evidence_gate.py`, which also imports
   root `_lib/yaml_frontmatter`. The selected skill now carries a deliberately
   small check-only `scripts/evidence_gate.py`: it reads the sibling skill's
   inline `evidence_required` frontmatter and validates the manifest paths.
   This is an explicit closure repair, not a generic runtime copy.
2. `/triage-debt` invoked root `scripts/specs.py`, `scripts/decisions.py`, and
   `scripts/log_effectiveness.py`. Recreating those registries inside this
   skill would be a false platform expansion. The selected workflow instead
   consumes a host-owned, plain-data cache at
   `reports/triage-debt/cache/current` (overridable with `TRIAGE_CACHE`) and
   records every present or missing axis in `inputs.md`.

`/find-perimeter-gaps` already carries its executable scanner, but its command
pointed at `.claude/skills/...` in a source checkout. It now requires
`SKILL_DIR` and calls the copied `scripts/scan.py`. `gut-check` and
`teach-pattern` have no runtime import: their documents are inputs belonging
to the host fixture, not installed toolkit dependencies.

## Executable proof

`tests/test_validated_neutral_typescript_quality.py` repeats the following for
each of the five skills from a pytest temporary directory outside the checkout:

1. Copy the locked host, run `npm ci --offline --ignore-scripts`, then
   `npm run typecheck`.
2. Run one exact `npx --yes skills@1.5.19 add <checkout> --skill <name>
   --agent codex --copy -y` command and assert `.agents/skills` contains only
   that copied directory.
3. Load the raw task, materialize the final artifact, execute the installed
   `/diagnose` evidence gate or `/find-perimeter-gaps` scanner where applicable,
   and assert the skill-specific final outcome.
4. Check the TypeScript source fingerprint after installation and after the
   artifact outcome. No source mutation is accepted.

Focused green evidence at `3aef3e1`:

```bash
"$REPO_ROOT/.venv/bin/python" -m pytest -q \
  tests/test_validated_neutral_typescript_quality.py \
  tests/test_perimeter_gaps.py tests/test_skill_detector_reads.py
# 5 passed

"$REPO_ROOT/.venv/bin/ruff" check \
  tests/test_validated_neutral_typescript_quality.py \
  .claude/skills/diagnose/scripts/evidence_gate.py \
  .claude/skills/find-perimeter-gaps/scripts/scan.py
# All checks passed

"$REPO_ROOT/.venv/bin/python" \
  scripts/skill_meta.py lint --quiet
# OK — 76 skills, 76 declaring new contract

"$REPO_ROOT/.venv/bin/python" \
  .claude/skills/_common/scripts/run_skill_smokes.py --quiet
# passed (quiet)
```

The staged primary commit also passed the complete pre-commit suite, including
`find-skill-artifact-drift` and `no-host-references`.

## Scope, limits, and disposition

D1, D3, D5, D7, and D8 are met for these exact outcomes. D2 and D4 do not
apply: no Python-language detector was ported and none of these flows proposes
or applies a TypeScript source mutation/guard. D6 remains for the serial
integrator as permitted: give a fresh non-context agent one copied skill, the
raw host, and its raw task without the captured artifact.

This validation does not claim TypeScript parsing, type-checker analysis,
framework support, Node/React/Express/ORM behavior, remediation execution, or
an installable generic quality platform. The `/diagnose` fixture deliberately
stops at a confirmed boundary seam: no source fix is authorized or claimed.
`/triage-debt` consumes cache data produced by a host's authorities; a cache is
not evidence that the installed skill can run a host's spec/decision registry.
Those optional repository-helper modes remain outside this selected core
artifact contract.

Recommendation: after D6, mark the five named skills `validated-neutral` for
their tested report/briefing/queue outcomes. Do not create TypeScript variants
or a shared runtime on this evidence.
