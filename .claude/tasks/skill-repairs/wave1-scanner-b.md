# Wave 1 Scanner B Repair Report

Scope: `find-skill-intent-drift`, `find-semantic-duplication`,
`find-orphaned-ideas`, `find-incomplete-sweep`.

Files touched stayed inside the four owned skill directories plus this report.
No git commit was made.

## find-skill-intent-drift

Findings verified:

- F1 TRUE — SKILL.md claimed the skill never edits skills or contracts, while
  the pipeline said `_index.yaml` is regenerated.
- F2 TRUE — `scripts/scan.py` writes `<contracts-dir>/_index.yaml` by default
  when `--no-index` is absent.
- F3 TRUE — `scripts/scan.py` accepts `host-attested`, while SKILL.md omitted
  it from the dogfood-kind enum prose.

Edits made:

- Added a near-top `How success is judged` block requiring pasted stdout,
  separate drift-band counts, honest index-write/no-write reporting, and no
  skill/per-contract edits.
- Resolved the read-only contradiction by declaring `_index.yaml` regeneration
  as the default side effect and `--no-index` as the no-write audit path. I
  chose this because the existing skill text already describes `_index.yaml`
  as the durable roll-up consumed with the contracts.
- Added `host-attested` to the dogfood-kind prose.
- Added dispatch/verdict contract, failure table, and replay case for
  `scripts/test_scan.py`.

## find-semantic-duplication

Findings verified:

- F1 TRUE — the Confirm brief required `reports/duplication/latest/triage.md`,
  and that file is absent in this checkout:

```text
$ if [ -e reports/duplication/latest/triage.md ]; then printf 'present\n'; else printf 'absent\n'; fi
absent
```

- F2 TRUE — `knowledge/false-positives.md` named dead artifact
  `confirmed_pairs.json`; the current pipeline uses `scout/`, `ranked.json`,
  and `triage.md`.
- F3 TRUE — SKILL.md made cross-domain comparison conditional, while
  `knowledge/learnings.md` said to always run it.

Edits made:

- Made the sibling duplication report conditional in `agents/confirm.md`.
  If absent, Confirm records `sibling duplication report absent` and continues
  with direct token-overlap evidence.
- Replaced `confirmed_pairs.json` with current artifacts in
  `knowledge/false-positives.md`.
- Reconciled cross-domain guidance in `knowledge/learnings.md`: run it when
  focus spans domains and prompt size is bounded; otherwise record the skip.
- Added scout dispatch artifact contracts, artifact-truth gates, conditional
  sibling-report failure handling, and replay guidance in SKILL.md.
- Verified referenced knowledge/scout files are present and non-empty:

```text
$ wc -c .claude/skills/find-semantic-duplication/knowledge/false-positives.md .claude/skills/find-semantic-duplication/knowledge/learnings.md
    5633 .claude/skills/find-semantic-duplication/knowledge/false-positives.md
    6155 .claude/skills/find-semantic-duplication/knowledge/learnings.md
   11788 total

$ wc -c .claude/skills/find-semantic-duplication/agents/summarize.md .claude/skills/find-semantic-duplication/agents/compare.md .claude/skills/find-semantic-duplication/agents/confirm.md .claude/skills/find-incomplete-sweep/reference/scout-rubric.md
    4495 .claude/skills/find-semantic-duplication/agents/summarize.md
    5331 .claude/skills/find-semantic-duplication/agents/compare.md
    9856 .claude/skills/find-semantic-duplication/agents/confirm.md
    5197 .claude/skills/find-incomplete-sweep/reference/scout-rubric.md
   24879 total
```

## find-orphaned-ideas

Findings verified:

- F1 TRUE — the success gate demanded seven separated modes, but `--all` only
  runs `stale` and `harvest` in `scripts/find.py`.
- F2 TRUE — SKILL.md said stale-plans only flags `proposed`; the script accepts
  `draft`, `proposed`, `scoped`, `impacted`, and `architected`.
- F3 TRUE — the effectiveness-log command used undefined shell values such as
  `$TOTAL` and per-bucket counters.

Edits made:

- Reframed success around every requested mode, and made `--all` explicitly the
  two-mode lightweight default, not a seven-mode audit.
- Updated stale-plan prose and script output/help/docstring to say
  non-terminal plans without active ledger tracking.
- Replaced undefined effectiveness-log variables with a JSON-derived command
  that defines `TOTAL` and `BUCKETS` before logging.
- Added no-subagent verdict contract and replay guidance for changed modes.
- Smoke-ran the changed stale-plans mode against a tiny fixture:

```text
$ /tmp/es-repo-1781314996/.venv/bin/python /tmp/es-repo-1781314996/.claude/skills/find-orphaned-ideas/scripts/find.py --stale-plans --stale-plans-days 0 --project-root /tmp/orphaned-ideas-fixture-1781314996 --json
{
  "attention_gap": {
    "areas": [],
    "drift": [],
    "status": "not_requested"
  },
  "dead_prototype": [],
  "harvest": [],
  "now": "2026-06-13T01:43:33Z",
  "plan_dropouts": {
    "items": [],
    "path": null
  },
  "stale": [],
  "stale_days": 14,
  "stale_plans": [
    {
      "days_silent": 2354,
      "last_modified": "2020-01-01T08:00:00+00:00",
      "path": "ai-docs/plans/demo-plan.md",
      "slug": "demo-plan",
      "status": "scoped"
    }
  ],
  "stale_plans_days": 0,
  "todo": []
}
```

Default `--all` smoke:

```text
$ /tmp/es-repo-1781314996/.venv/bin/python /tmp/es-repo-1781314996/.claude/skills/find-orphaned-ideas/scripts/find.py --all --project-root /tmp/orphaned-ideas-fixture-1781314996 --json
{
  "attention_gap": {
    "areas": [],
    "drift": [],
    "status": "not_requested"
  },
  "dead_prototype": [],
  "harvest": [],
  "now": "2026-06-13T01:43:39Z",
  "plan_dropouts": {
    "items": [],
    "path": null
  },
  "stale": [],
  "stale_days": 14,
  "stale_plans": [],
  "stale_plans_days": 30,
  "todo": []
}
```

## find-incomplete-sweep

Findings verified:

- F1 TRUE — SKILL.md promised relative paths anchor on `--project-root`, but
  `run_placeholder_band` did not pass the resolved project root.
- F2 TRUE — `placeholder.py` resolved raw paths from the process cwd.
- F3 TRUE — the scout flow named `scout_packets.json` and `triaged.md` but did
  not name per-judge verdict artifacts or the merge contract.

Edits made:

- Passed resolved `project_root` from `scan.py` into the placeholder band.
- Updated `placeholder.py` so path walking, reference checks, implemented
  sibling checks, report labels, and manifests all honor the supplied project
  root.
- Fixed placeholder rendering to call `scan.rel` with a project root.
- Added a regression test for running placeholder detection from a different
  cwd than the target project root.
- Added `scout_verdicts.json` as the required per-packet verdict merge
  artifact and documented the merge into `triaged.md`.
- Added failure table and replay case.

Cross-cwd smoke required by the retry:

```text
$ /tmp/es-repo-1781314996/.venv/bin/python /tmp/es-repo-1781314996/.claude/skills/find-incomplete-sweep/scripts/scan.py --band placeholder --paths app --project-root /tmp/incomplete-sweep-fixture-1781314996 --out /tmp/incomplete-sweep-out-1781314996
wrote /tmp/incomplete-sweep-out-1781314996/placeholder_findings.md  (1 gated-in / 1 raw)

$ sed -n '1,12p' /tmp/incomplete-sweep-out-1781314996/placeholder_findings.md
# find-incomplete-sweep — findings (band: placeholder-residue)

- paths: `app`
- files scanned: 2
- max-age-days (recency gate): 120.0
- raw placeholder bodies: 1
- **gated IN (recent + reference-asymmetry): 1**
- gated out (stale / no asymmetry / no blame): 0

## Gated IN — recent referenced stubs (likely forgotten work)

### `Forgotten.run` — not_implemented
```

## Verification

Intent-drift fixture suite:

```text
$ .venv/bin/python .claude/skills/find-skill-intent-drift/scripts/test_scan.py
test_fm1_body_only_change_is_not_stale (__main__.IntentAwareStaleTests.test_fm1_body_only_change_is_not_stale) ... ok
test_fm2_frontmatter_intent_change_is_stale (__main__.IntentAwareStaleTests.test_fm2_frontmatter_intent_change_is_stale) ... ok
test_fm3_path_only_frontmatter_change_is_not_stale (__main__.IntentAwareStaleTests.test_fm3_path_only_frontmatter_change_is_not_stale) ... ok
test_fm4_operational_key_only_change_is_not_stale (__main__.IntentAwareStaleTests.test_fm4_operational_key_only_change_is_not_stale) ... ok
test_fm5_skillmd_absent_at_contract_commit_is_stale (__main__.IntentAwareStaleTests.test_fm5_skillmd_absent_at_contract_commit_is_stale) ... ok
test_fm6_uncommitted_contract_is_baseline (__main__.IntentAwareStaleTests.test_fm6_uncommitted_contract_is_baseline) ... ok
test_n1_intent_fingerprint_drops_operational_and_collapses_paths (__main__.NormalizationPrimitiveTests.test_n1_intent_fingerprint_drops_operational_and_collapses_paths) ... ok
test_n2_frontmatter_block_slicing (__main__.NormalizationPrimitiveTests.test_n2_frontmatter_block_slicing) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.640s

OK
```

Incomplete-sweep fixture suite:

```text
$ .venv/bin/python .claude/skills/find-incomplete-sweep/scripts/test_scan.py
test_dc1_default_field_recognized (__main__.DataclassDefaultFilterTests.test_dc1_default_field_recognized) ... ok
test_dc3_field_factory_vs_bare_field (__main__.DataclassDefaultFilterTests.test_dc3_field_factory_vs_bare_field) ... ok
test_dc4_function_param_defaults (__main__.DataclassDefaultFilterTests.test_dc4_function_param_defaults) ... ok
test_dc5_frozen_and_dotted_dataclass (__main__.DataclassDefaultFilterTests.test_dc5_frozen_and_dotted_dataclass) ... ok
test_filter_downranks_default_kwarg_straggler (__main__.DataclassDefaultFilterTests.test_filter_downranks_default_kwarg_straggler) ... ok
test_value_awareness_keeps_default_equal_value_downranked (__main__.DataclassDefaultFilterTests.test_value_awareness_keeps_default_equal_value_downranked) ... ok
test_value_awareness_no_promote_when_default_is_non_literal (__main__.DataclassDefaultFilterTests.test_value_awareness_no_promote_when_default_is_non_literal) ... ok
test_value_awareness_promotes_consistent_nondefault_override (__main__.DataclassDefaultFilterTests.test_value_awareness_promotes_consistent_nondefault_override) ... ok
test_ph1_notimplemented_concrete (__main__.PlaceholderBandTests.test_ph1_notimplemented_concrete) ... ok
test_ph2_abstract_excluded (__main__.PlaceholderBandTests.test_ph2_abstract_excluded) ... ok
test_ph3_pass_and_ellipsis (__main__.PlaceholderBandTests.test_ph3_pass_and_ellipsis) ... ok
test_ph4_todo_return_vs_plain_return (__main__.PlaceholderBandTests.test_ph4_todo_return_vs_plain_return) ... ok
test_ph5_recency_reference_gate (__main__.PlaceholderBandTests.test_ph5_recency_reference_gate) ... ok
test_ph6_project_root_anchors_paths_from_other_cwd (__main__.PlaceholderBandTests.test_ph6_project_root_anchors_paths_from_other_cwd) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.139s

OK
```

Skill metadata lint:

```text
$ .venv/bin/python scripts/skill_meta.py lint
OK — 74 skills, 74 declaring new contract
```

Requested pytest selector:

```text
$ .venv/bin/python -m pytest -k 'intent_drift or semantic or orphaned or incomplete_sweep' -q
.....                                                                    [100%]
5 passed, 364 deselected in 0.18s
```

Changed Python script lint:

```text
$ .venv/bin/ruff check .claude/skills/find-incomplete-sweep/scripts/scan.py .claude/skills/find-incomplete-sweep/scripts/placeholder.py .claude/skills/find-incomplete-sweep/scripts/test_scan.py .claude/skills/find-orphaned-ideas/scripts/find.py
All checks passed!
```

Diff whitespace check:

```text
$ git diff --check -- .claude/skills/find-skill-intent-drift .claude/skills/find-semantic-duplication .claude/skills/find-orphaned-ideas .claude/skills/find-incomplete-sweep
```

No output; exit 0.

Final scoped status:

```text
$ git status --short -- .claude/skills/find-skill-intent-drift .claude/skills/find-semantic-duplication .claude/skills/find-orphaned-ideas .claude/skills/find-incomplete-sweep .claude/tasks/skill-repairs/wave1-scanner-b.md
 M .claude/skills/find-incomplete-sweep/SKILL.md
 M .claude/skills/find-incomplete-sweep/scripts/placeholder.py
 M .claude/skills/find-incomplete-sweep/scripts/scan.py
 M .claude/skills/find-incomplete-sweep/scripts/test_scan.py
 M .claude/skills/find-orphaned-ideas/SKILL.md
 M .claude/skills/find-orphaned-ideas/scripts/find.py
 M .claude/skills/find-semantic-duplication/SKILL.md
 M .claude/skills/find-semantic-duplication/agents/confirm.md
 M .claude/skills/find-semantic-duplication/knowledge/false-positives.md
 M .claude/skills/find-semantic-duplication/knowledge/learnings.md
 M .claude/skills/find-skill-intent-drift/SKILL.md
?? .claude/tasks/skill-repairs/wave1-scanner-b.md
```
