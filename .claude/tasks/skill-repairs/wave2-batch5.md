# Wave 2 batch 5 repair report - W2-4

Scope owned: `triage-debt`, `unify-shadows`, `project-interview`,
`query-patterns` skill directories plus this report. No commit made.

## triage-debt

### Findings verified

- **TRUE - `--top N` parse bug.** `SKILL.md` documented
  `/triage-debt [--top N]`, but Stage 0 used `TOP_N="${1:-5}"`. With the
  documented `--top 10` shape, `TOP_N` became `--top`, and Stage 5 would
  render invalid JSON for `log_effectiveness.py --buckets`.
- **PARTLY - standard elements already present but incomplete.** The skill
  already had `How success is judged` and a sideways table, but artifact
  truth, executable-as-written parser behavior, venv command contracts,
  and replay evidence were incomplete.

### Reproduction before fix

Command:

```bash
set -- --top 10
TOP_N="${1:-5}"
printf 'TOP_N=%s\n' "${TOP_N}"
printf '{"top_n": %s}\n' "${TOP_N}" > /tmp/triage-debt-top-before.json
.venv/bin/python -m json.tool /tmp/triage-debt-top-before.json
```

Output:

```text
TOP_N=--top
Expecting value: line 1 column 11 (char 10)
```

### Edits made

- Replaced the single-argument default with a real parser for `--top N`
  and `--top=N`, including exit-2 errors for missing, non-numeric, or
  zero values.
- Switched repo script invocations from bare `python3` to
  `.venv/bin/python`.
- Added artifact-truth requirements for pasted Stage 1 and Stage 5 command
  output.
- Added a self-contained replay case for the parser/JSON boundary.

### Passing run after fix

```text
TOP_N=10
{
    "top_n": 10
}
```

## unify-shadows

### Findings verified

- **TRUE - empty load-bearing `knowledge/` reference.** The skill required
  exact per-shape proposal body templates from `knowledge/`, but the
  directory had zero files. Stage 3 forced the executor to invent the most
  load-bearing part of the proposal.
- **PARTLY - standard elements present but thin.** The skill already had a
  success block, failure table, and sub-agent path, but the dispatch did
  not declare exactly how scout output would be judged, the knowledge
  reference had no readable target, Stage 4 logged a string-valued bucket,
  and there was no replay case.

### Edits made

- Added `knowledge/proposal-templates.md` with concrete bodies for
  `keep_separate_document_why`, `share_utilities`, `complete_migration`,
  and `merge_at_workflow`.
- Updated Stage 3 to read only the matching section of
  `knowledge/proposal-templates.md`, and to abort if it is missing or
  empty.
- Added declared-verdict dispatch language for scout profiles and added a
  `How output is judged` gate to `agents/shadow-profiler.md`.
- Switched command examples to `.venv/bin/python`.
- Changed Stage 4 effectiveness buckets to numeric `shape_<shape>: 1`.
- Added artifact-truth and replay-case requirements.

### Knowledge reference check

```text
.claude/skills/unify-shadows/knowledge/proposal-templates.md
    2996 .claude/skills/unify-shadows/knowledge/proposal-templates.md
```

### Collector smoke

```text
wrote /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/tmp.sWPLi7ADn5/reports/unify-shadows/SC-1/targets.json: SC-1 (share_utilities, 2 members)
{
    "finding_id": "SC-1",
    "title": "Sample shadows",
    "shape": "share_utilities",
    "capability_matrix": null,
    "notes": "Extract shared request-shaping code only.",
    "members": [
        {
            "file": "core/services/foo.py",
            "lineno": 10,
            "symbol": "Foo.run",
            "caller_count": 2,
            "member_key": "foo__run"
        },
        {
            "file": "core/services/bar.py",
            "lineno": 20,
            "symbol": "Bar.run",
            "caller_count": 3,
            "member_key": "bar__run"
        }
    ]
}
```

## project-interview

### Findings verified

- **TRUE - missing activation-standard elements.** The skill had no
  near-top `How success is judged` block and no honest failure-path table.
- **TRUE - artifact-root contract break.** The helper writes to
  `${ARTIFACT_ROOT}/reports/project-interview/scan-<TS>/`, but the
  documented evidence gate checked repo-local `reports/project-interview/latest`.
  The documented `--no-host-write --artifact-root <outside>` form therefore
  checked the wrong tree.
- **PARTLY - batch-5 OK claim.** The helper itself does write
  `profile.yml`, `profile.md`, `open-questions.md`, and `evidence.json`;
  the SKILL prose around where to check them was the broken part.

### Edits made

- Added `How success is judged` with draft/apply/no-host-write gates and
  mandatory pasted evidence-gate output.
- Added Stage 0 setup for `PROJECT_ROOT` and `ARTIFACT_ROOT`.
- Set `SCAN_DIR="${ARTIFACT_ROOT}/reports/project-interview/latest"` and
  reused it for reads and evidence gate.
- Added a sideways table for helper exit failures, missing artifacts,
  evidence-token failures, unavailable users, and apply-write failures.
- Added a replay case for the dogfood artifact-root path.
- Removed non-load-bearing inspiration prose.

### Artifact-root smoke

```text
/private/var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/tmp.6sCTbofeNq/reports/project-interview/scan-project-interview-smoke
Evidence gate for /project-interview on /private/var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/tmp.6sCTbofeNq/reports/project-interview/scan-project-interview-smoke:
  [ok] profile -> profile.yml
  [ok] profile_summary -> profile.md
  [ok] open_questions -> open-questions.md

OK: 3/3 required evidence shapes present.
```

## query-patterns

### Findings verified

- **TRUE - missing downstream promotion skill.** The referenced
  `/promote-idea-to-pattern` skill does not exist; current pattern-related
  skill dirs are `query-patterns` and `teach-pattern`.
- **TRUE - stale empty-library exit contract.** `SKILL.md` said the
  empty-library path exits 0, while `scripts/query.py` returns 1 when
  there are zero results. The script docstring also declares exit 1 for
  zero patterns or all-zero scores.
- **PARTLY - standard elements incomplete.** The skill had a sideways table
  and exit-code vocabulary, but lacked a near-top success block,
  artifact-truth gate, valid no-match handoff, venv command contract, and
  replay case.

### Edits made

- Replaced every missing promotion-skill handoff with `/track-idea intake`
  plus manual Tier 2 promotion into `.claude/patterns/` per
  `.claude/docs/pattern-library.md`.
- Updated the empty-library contract to exit 1 as a valid no-match result.
- Updated the script's rendered no-pattern guidance to match the SKILL.
- Switched command examples to `.venv/bin/python`.
- Added `How success is judged`, no-match artifact gates, matcher-exit
  failure handling, and replay cases.
- Removed non-load-bearing future-evolution prose.

### Matcher smoke - empty library

```text
Query: workflow registry guard
Library size: 0 patterns

No patterns recorded yet. Capture the problem with `/track-idea intake`
and promote manually into `.claude/patterns/` once it satisfies
the Tier 2 gate in `.claude/docs/pattern-library.md`.
rc=1
```

### Matcher smoke - current repo

```text
Query: workflow registry guard
Library size: 0 patterns

No patterns recorded yet. Capture the problem with `/track-idea intake`
and promote manually into `.claude/patterns/` once it satisfies
the Tier 2 gate in `.claude/docs/pattern-library.md`.
rc=1
```

## Cross-skill standard pass

| Element | Result |
|---|---|
| Declared verdict | All four now have a near-top `How success is judged` block. |
| Artifact-truth gates | All four require pasted command output or evidence-gate output instead of claims. |
| Decision-point mandates | Parser, no-match, artifact-root, template, and scout-profile decisions sit at the stages where they are consumed. |
| Executable-as-written contracts | Fixed `--top`, corrected query exit code, aligned project-interview scan dir with artifact root, and switched repo script examples to `.venv/bin/python`. |
| Declared-verdict dispatch | `unify-shadows` scout dispatch now names exactly how profiles are judged; the other three do not dispatch sub-agents. |
| Load-bearing or deleted | Added the missing load-bearing template file and removed non-load-bearing project-interview/query-patterns prose. |
| Honest failure paths | All four have sideways/failure guidance for predictable failures. |
| Replay case | All four now include a replay case appropriate to their shape. |

## Final verification

### Skill metadata lint

```text
OK — 74 skills, 74 declaring new contract
```

### Targeted pytest selector

Command:

```bash
.venv/bin/python -m pytest -k 'triage_debt or unify_shadows or project_interview or query_patterns' -q
```

Output:

```text

369 deselected in 0.09s
```

Pytest exited 5 because there were no matching tests for that selector.

### Content constraints

- `rg` found no forbidden token or machine-user absolute path in the four
  owned skill dirs.
- `rg` found no remaining `promote-idea-to-pattern` reference in the four
  owned skill dirs.
