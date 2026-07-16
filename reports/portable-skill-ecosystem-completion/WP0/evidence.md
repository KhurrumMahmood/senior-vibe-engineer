# WP0 implementation evidence

This record is the implementer's checkpoint for AC-0.1 through AC-0.5. It is
not the independent verdict. The verifier must rerun the commands from a clean
checkout and write a separate `verification.md` with a PASS/FAIL row for every
criterion.

## Revision and environment

- Baseline revision: `ad685e3f47fd6fb3debe4880735a5bf20eb79cae`
- Implementation revision: `9eecd1e2edb53413fa4f723eefa01b362af373fd`
- Workspace at implementation commit: clean (`git status --short` emitted no
  paths).
- Platform: Darwin 25.5.0, arm64.
- Python: 3.11.10.
- pytest: 9.0.3.
- Ruff: 0.6.9.
- Playwright Python package/CLI: 1.60.0.
- Browser prerequisite installed for this checkout with
  `.venv/bin/python -m playwright install chromium --only-shell`.

## Baseline and repairs

At the baseline, `.venv/bin/python -m pytest` collected 403 tests: 401 passed
and two failed. The renderer smoke could not launch because the Playwright
Chromium binary was absent. `test_exit_0_all_within_grace` depended on wall
clock time and had aged beyond its intended boundary.

The implementation:

- documents the optional dev requirements and deterministic Playwright browser
  installation in `README.md`;
- adds `triage_audit.py --now <ISO-8601>` and fixes the boundary test to inject
  its clock, with invalid-clock coverage;
- makes the artifact-drift gate scan skill evidence contracts for deleted
  concrete script references and supplies good/bad fixtures;
- corrects the stale `mature-existing-ideas` evidence contract;
- reconciles README/onboarding counts and portability claims, manifest labels,
  the skill catalog, and generated ecosystem state;
- adds explicit revisit triggers to eight deliberately proposed but aged ADRs,
  rather than suppressing the decision audit;
- maps every predecessor deliverable and success criterion into the master
  plan, marks the duplicate predecessor abandoned, and updates active inbound
  plan/ADR references.

The catalog reconciliation added the three missing catalog entries. No new
`shapes.yml` route was added: `find-incomplete-sweep` is already reachable by
the generic tactical health-audit shape, `find-perimeter-gaps` is an integration
step of adaptation/whole-codebase auditing rather than a new operating loop,
and `repair-skill` is a bounded response to a concrete skill defect rather than
a distinct task shape.

## Implementer command record

All commands below exited 0 at the implementation tree unless a baseline
failure is explicitly identified.

| Criterion | Command | Result |
|---|---|---|
| AC-0.1 | `.venv/bin/python -m pytest` | `404 passed in 13.22s`; browser tests ran, not skipped. |
| AC-0.1 | `.venv/bin/python -m pytest tests/test_render_status.py -q` | `4 passed`. |
| AC-0.2 | `.venv/bin/python -m pytest tests/test_triage_audit.py -q` | `23 passed`; the fixed-clock scenario passes `--now`, so removing/ignoring injection makes the dated fixture fail. |
| AC-0.3 | `.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate` | exit 0 on the live corpus. |
| AC-0.3 | `.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/smoke.py` | `OK - 7 bad fixture findings across 7 bands, good clean, gate honored`; includes `missing_contract_script_ref`. |
| AC-0.3/0.4 | `.venv/bin/python .claude/skills/check-ecosystem-consistency/scripts/check.py` | `no ecosystem consistency findings`. |
| AC-0.4 | `.venv/bin/python scripts/plans.py audit` | `OK — 5 plans, no drift`. |
| AC-0.4 | `.venv/bin/python scripts/decisions.py audit` | `OK — 29 decisions, no drift`. |
| AC-0.4 | `.venv/bin/python scripts/decisions.py link-check` | `OK — 29 decisions, all links resolve, 16 host-scoped`; pending embodiment notices are advisory. |
| AC-0.4 | `.venv/bin/python scripts/skill_meta.py lint` | `OK — 76 skills, 76 declaring new contract`. |
| AC-0.4 | `.venv/bin/python scripts/lint/run.py --self` | `silent-catch` and `query-mutation` checked 188 files; non-applicable host rules reported as skipped; exit 0. |
| AC-0.4 | `.venv/bin/ruff check scripts/triage_audit.py tests/test_triage_audit.py .claude/skills/find-skill-artifact-drift/scripts/detect.py .claude/skills/find-skill-artifact-drift/scripts/smoke.py` | `All checks passed!`. |
| AC-0.5 | inspection of the predecessor and the master plan's detailed inheritance ledger | W1–W6 deliverables and all six predecessor success criteria have exact decision/AC owners; unfinished ADR 0003 and 0026–0030 obligations have explicit ACs. Independent zero-unmapped verdict pending. |

The commit hook also passed Ruff, whitespace/YAML/merge checks, all seven
project AST lint hooks, decision audit/link checks, the no-host-reference gate,
and skill artifact drift.

## Predecessor disposition inspection

The active execution authority is now
`ai-docs/plans/portable-skill-ecosystem-completion.md`. The predecessor remains
available as historical provenance but is `abandoned` and links to the detailed
inheritance ledger. Active references in ADR 0034, ADR 0036, the consistency
session plan, and the status projection plan now point to the master plan.
References retained in the abandoned plan, append-only idea history, and task
records are historical evidence, not competing execution authority.

The independent verifier must compare the predecessor's complete W1–W6 bodies
and success-criteria list against the detailed ledger, not merely accept the
six heading-level rows.

## Implementation artifact hashes

These SHA-256 hashes identify the implementation artifacts at revision
`9eecd1e2edb53413fa4f723eefa01b362af373fd`:

```text
8edac78e94c093099c319d1bde60879ced6e11cffa6f4096042a569f85d65f63  .claude/ecosystem/last-state.json
41b253f1054bf78304e238d46fb87ce323298bf31fc29c5ca8250ff3616ee7f8  .claude/skills/find-skill-artifact-drift/fixtures/contracts/bad/drifty-skill.yaml
9c75798ab80864b04c2852faacddc4f16948b12e2968bd8855f92a904dfb1e9d  .claude/skills/find-skill-artifact-drift/fixtures/contracts/good/clean-skill.yaml
b4e465a3195ba370fdce9c432e281388cc121df95cbe25177885792dbaca9159  ai-docs/plans/portable-skill-ecosystem-completion.md
13d5c17bdde8e222d370b39339fe06576f7764a916b4a5e62b886119a923353f  ai-docs/plans/shareable-core-reorganization.md
e4d20622ddd94857d43e8e1122bbc6722b03926097a91e03ca0ba4046983b053  scripts/triage_audit.py
813aa933e28cd64652857def0b118ac6acfe6f0e9bdd1c5c8e294296da09fd41  tests/test_triage_audit.py
```

The evidence/tracker checkpoint that adds this file is intentionally a child
of the implementation revision and changes no WP0 runtime artifact. The fresh
verifier records the exact clean checkpoint revision and hashes this evidence
file in `verification.md`.
