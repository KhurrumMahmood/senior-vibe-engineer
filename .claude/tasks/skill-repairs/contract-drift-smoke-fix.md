# Contract Drift Smoke Fix

## Original Traceback

Path prefixes are rendered repo-relative here to satisfy the report path constraint.

```text
Traceback (most recent call last):
  File ".claude/skills/find-contract-drift/scripts/smoke.py", line 62, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File ".claude/skills/find-contract-drift/scripts/smoke.py", line 40, in main
    good = _run(SKILL_ROOT / "fixtures" / "good")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File ".claude/skills/find-contract-drift/scripts/smoke.py", line 18, in _run
    subprocess.run(
  File "<python-stdlib>/subprocess.py", line 571, in run
    raise CalledProcessError(retcode, process.args,
subprocess.CalledProcessError: Command '['.venv/bin/python', '.claude/skills/find-contract-drift/scripts/detect.py', '--project-root', '.claude/skills/find-contract-drift/fixtures/good', '--output', '<tmp>/detections.jsonl']' returned non-zero exit status 1.
```

The subprocess failure was caused by:

```text
TypeError: detect() takes 0 positional arguments but 4 were given
```

## Contract Owner

The wrong side was `.claude/skills/find-contract-drift/scripts/detect.py`.

Evidence:

- `.claude/skills/find-frontend-contract-drift/SKILL.md` invokes the frontend detector as a CLI with `detect.py --output ...`; its script-owned `main()` loads scope and calls `detect(...)` with keyword arguments.
- `.claude/skills/find-frontend-contract-drift/scripts/detect.py` declares `detect(*, project_root, scope, boot_threshold, template_root=None, js_root=None)`, making the function intentionally keyword-only.
- `.claude/skills/find-contract-drift/SKILL.md` documents the public pipeline as `scripts/run.py <paths...>`, while `scripts/run.py` calls the local contract detector.
- `.claude/skills/find-contract-drift/scripts/smoke.py` executes the local `scripts/detect.py` CLI with `--project-root` and `--output`; that CLI was fine until its adapter called the frontend detector using the stale positional signature.
- `tests/test_run_skill_smokes.py` validates that smoke scripts are run as subprocesses through the smoke gate; it does not define a detector function signature.
- Other caller search found no other in-scope frontend detector import calls.

## Diff Summary

- Updated `.claude/skills/find-contract-drift/scripts/detect.py` to load the frontend detector's scope through the frontend module.
- Replaced the stale positional call `module.detect(project_root, template_root, js_root, 3)` with the frontend detector's keyword-only contract: `project_root`, `scope`, `boot_threshold`, `template_root`, and `js_root`.

## Verification

```text
$ .venv/bin/python .claude/skills/find-contract-drift/scripts/smoke.py
find-contract-drift smoke OK
```

```text
$ .venv/bin/python -m pytest tests/test_run_skill_smokes.py -q
...........                                                              [100%]
11 passed in 1.72s
```

```text
$ .venv/bin/ruff check .claude/skills/find-contract-drift/scripts/detect.py
All checks passed!
```

## Disposition note (orchestrator)

The code change described above was real and faithful, but it was
accidentally absorbed into commit `ecac9cc` (the class-1 verdict-block
batch) because the orchestrator staged with a broad `git add
.claude/skills/` while multiple agent lanes shared the working tree.
Verified after the fact: `git show ecac9cc` contains the 9-line
detect.py hunk exactly as this report describes, and `git log -S`
confirms the stale positional call existed from the initial release
until that commit. The fix is live; only its commit attribution is
wrong. Lesson recorded in .claude/tasks/lessons.md.
