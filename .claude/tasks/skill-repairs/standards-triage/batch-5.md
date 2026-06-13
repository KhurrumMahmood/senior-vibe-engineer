# Standards triage — batch 5 (recovered from Codex output; sandbox blocked the original write)

[codex] Command completed: /bin/zsh -lc 'ls .claude/skills/_common/dispatch_scout.sh .claude/skills/_common/dispatch_sco... (exit 0)
[codex] Running command: /bin/zsh -lc "find . -path '*project_core_vs_scratch_code.md' -o -path '*/find-incomplete-swe...
[codex] Command completed: /bin/zsh -lc "find . -path '*project_core_vs_scratch_code.md' -o -path '*/find-incomplete-swe... (exit 0)
[codex] Running command: /bin/zsh -lc "find .claude/skills -maxdepth 1 -type d -name '*pattern*' -print | sort"
[codex] Command completed: /bin/zsh -lc "find .claude/skills -maxdepth 1 -type d -name '*pattern*' -print | sort" (exit 0)
[codex] Running command: /bin/zsh -lc 'rg -n "find-doc-link-rot|DOC|FLOOR|RENAME|universal" .claude/skills/which-clean...
[codex] Command completed: /bin/zsh -lc 'rg -n "find-doc-link-rot|DOC|FLOOR|RENAME|universal" .claude/skills/which-clean... (exit 0)
[codex] Assistant message captured: A few referenced downstream skill names are not present in the catalogue, but I’m distinguish...
[codex] Running command: /bin/zsh -lc "nl -ba .claude/skills/which-cleanup/scripts/select_scanners.py | sed -n '50,120p'"
[codex] Command completed: /bin/zsh -lc "nl -ba .claude/skills/which-cleanup/scripts/select_scanners.py | sed -n '50,120p'" (exit 0)
[codex] Running command: /bin/zsh -lc "test -d .claude/skills/find-doc-link-rot; printf '%s\\n' "'$?'
[codex] Command completed: /bin/zsh -lc "test -d .claude/skills/find-doc-link-rot; printf '%s\\n' "'$?' (exit 0)
[codex] Running command: /bin/zsh -lc "nl -ba .claude/skills/which-cleanup/scripts/select_scanners.py | sed -n '1,49p'"
[codex] Command completed: /bin/zsh -lc "nl -ba .claude/skills/which-cleanup/scripts/select_scanners.py | sed -n '1,49p'" (exit 0)
[codex] Running command: /bin/zsh -lc "test -d .claude/skills/promote-idea-to-pattern; printf '%s\\n' "'$?'
[codex] Command completed: /bin/zsh -lc "test -d .claude/skills/promote-idea-to-pattern; printf '%s\\n' "'$?' (exit 0)
[codex] Assistant message captured: I’ve confirmed a couple of stale references: one missing downstream promotion skill name in i...
[codex] Running command: /bin/zsh -lc "rg -n \"status: STUB|lifecycle|def cmd_init|add_parser\\(\\\"init\\\"|motivatin...
[codex] Command completed: /bin/zsh -lc "rg -n \"status: STUB|lifecycle|def cmd_init|add_parser\\(\\\"init\\\"|motivatin... (exit 0)
[codex] Running command: /bin/zsh -lc "nl -ba scripts/specs.py | sed -n '1,260p'"
[codex] Command completed: /bin/zsh -lc "nl -ba scripts/specs.py | sed -n '1,260p'" (exit 0)
[codex] Running command: /bin/zsh -lc "nl -ba scripts/plans.py | sed -n '1,300p'"
[codex] Command completed: /bin/zsh -lc "nl -ba scripts/plans.py | sed -n '1,300p'" (exit 0)
[codex] Assistant message captured: The spec/plans CLIs confirm the “lifecycle proposed, status draft after filling” model. I’ll ...
[codex] Running command: /bin/zsh -lc "nl -ba scripts/specs.py | sed -n '1810,2025p'"
[codex] Running command: /bin/zsh -lc "nl -ba scripts/specs.py | sed -n '2100,2140p'"
[codex] Command completed: /bin/zsh -lc "nl -ba scripts/specs.py | sed -n '2100,2140p'" (exit 0)
[codex] Command completed: /bin/zsh -lc "nl -ba scripts/specs.py | sed -n '1810,2025p'" (exit 0)
[codex] Running command: /bin/zsh -lc "nl -ba scripts/plans.py | sed -n '300,405p'"
[codex] Command completed: /bin/zsh -lc "nl -ba scripts/plans.py | sed -n '300,405p'" (exit 0)
[codex] Running command: /bin/zsh -lc "nl -ba .claude/skills/_common/dispatch_scout.sh | sed -n '1,220p'"
[codex] Command completed: /bin/zsh -lc "nl -ba .claude/skills/_common/dispatch_scout.sh | sed -n '1,220p'" (exit 0)
[codex] Running command: /bin/zsh -lc "nl -ba .claude/skills/_common/dispatch_scout_cheap.sh | sed -n '1,220p'"
[codex] Command completed: /bin/zsh -lc "nl -ba .claude/skills/_common/dispatch_scout_cheap.sh | sed -n '1,220p'" (exit 0)
[codex] Running command: /bin/zsh -lc "test -f .claude/skills/find-concept-divergence/scripts/scan.py && nl -ba .claud...
[codex] Command completed: /bin/zsh -lc "test -f .claude/skills/find-concept-divergence/scripts/scan.py && nl -ba .claud... (exit 0)
[codex] Running command: /bin/zsh -lc '.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py --help'
[codex] Command completed: /bin/zsh -lc '.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py --help' (exit 0)
[codex] Assistant message captured: I also checked the indirect `find-concept-divergence` scan that `rename-concept` delegates to...
[codex] Running command: /bin/zsh -lc 'for p in .claude/docs/canonical-patterns.md .claude/docs/architectural-smells.m...
[codex] Command completed: /bin/zsh -lc 'for p in .claude/docs/canonical-patterns.md .claude/docs/architectural-smells.m... (exit 0)
[codex] Running command: /bin/zsh -lc 'find .claude/skills/plan-feature/knowledge -maxdepth 1 -type f -print | sort'
[codex] Running command: /bin/zsh -lc 'find .claude/skills/unify-shadows/knowledge -maxdepth 1 -type f -print | sort'
[codex] Command completed: /bin/zsh -lc 'find .claude/skills/unify-shadows/knowledge -maxdepth 1 -type f -print | sort' (exit 0)
[codex] Command completed: /bin/zsh -lc 'find .claude/skills/plan-feature/knowledge -maxdepth 1 -type f -print | sort' (exit 0)
[codex] Assistant message captured: All directly named docs/scripts I checked exist, except the intentionally absent downstream s...
[codex] Running command: /bin/zsh -lc 'test -d .claude/tasks/skill-repairs/standards-triage && find .claude/tasks/skil...
[codex] Command completed: /bin/zsh -lc 'test -d .claude/tasks/skill-repairs/standards-triage && find .claude/tasks/skil... (exit 0)
[codex] Running command: /bin/zsh -lc "test -d .claude/tasks/skill-repairs/standards-triage; printf '%s\\n' "'$?'
[codex] Command completed: /bin/zsh -lc "test -d .claude/tasks/skill-repairs/standards-triage; printf '%s\\n' "'$?' (exit 0)
[codex] Assistant message captured: I’ve finished the read/contract pass and have the verdicts. I’m going to write only the reque...
[codex] Assistant message captured: I completed the read-only triage, but the sandbox blocked the requested write to `.claude/tas...
[codex] Turn completed.
I completed the read-only triage, but the sandbox blocked the requested write to `.claude/tasks/skill-repairs/standards-triage/batch-5.md` (`apply_patch` was rejected because filesystem writes are disabled and approvals are unavailable). No skill files were edited and no commit was made.

```markdown
# Batch 5 Frame-Review Triage

## Verdict Table

| skill | verdict | one-line reason |
|---|---|---|
| plan-feature | MINOR | Script contracts line up; only `--force` retry guidance is not represented in the skill's argument surface. |
| plan-spec | OK | `plans.py promote`, `specs.py init`, and verification commands match the documented workflow. |
| project-interview | OK | `project_adapt.py interview` writes the profile artifacts and `evidence.json` that `evidence_gate.py check` expects. |
| propose-boundary | MINOR | Helper CLI matches usage, but documented inspection schema omits the helper's `subsystem` target kind and overstates `call_edges`. |
| propose-folder-reorganization | MINOR | Helper CLI matches usage, but threshold prose has a `<2` vs `<3` drift. |
| query-patterns | MINOR | De-baked `--project-root` usage matches; no-match guidance references a missing downstream promotion skill and has one stale exit-code sentence. |
| rename-concept | OK | `assess.py` and delegated `find-concept-divergence` flags match the documented assess-only contract. |
| teach-pattern | MINOR | Mostly executable, but one read-scope path uses the stale `reports/<find-*>` form contradicted later by the skill. |
| track-idea | MINOR | Current `track.py` forms match; downstream promotion guidance references a missing skill. |
| triage-debt | NEEDS-REPAIR | `--top N` parsing is unexecutable as written and can corrupt the rendered queue/log. |
| unify-shadows | NEEDS-REPAIR | Stage 3 depends on shape templates in an empty `knowledge/` directory, forcing invention at the write site. |
| which-cleanup | MINOR | Current scripts match the de-baked `--project-root` convention; prose still names a disabled/missing doc-link scanner. |
| which-skill | OK | `match.py` output and exit-code contract match the documented recommendation flow. |

## NEEDS-REPAIR

### triage-debt

F1. `.claude/skills/triage-debt/SKILL.md:4` documents `argument-hint: "[--top N]  (default top=5; raise to see more)"`, but `.claude/skills/triage-debt/SKILL.md:108` sets `TOP_N="${1:-5}"`.
With `/triage-debt --top 10`, `TOP_N` becomes `--top`, not `10`.
That value is consumed in `.claude/skills/triage-debt/SKILL.md:251` (`## Top <TOP_N>`) and `.claude/skills/triage-debt/SKILL.md:286` (`"top_n": ${TOP_N}`), so a real run can render/log invalid output.

### unify-shadows

F1. `.claude/skills/unify-shadows/SKILL.md:188` says `see `knowledge/` for the exact`, and `.claude/skills/unify-shadows/SKILL.md:207` requires a shape-specific body (`keep_separate_document_why | share_utilities`).
The referenced `knowledge/` directory contains no files.
A fresh executor cannot get the promised exact per-shape body templates from the repo and must either stall or invent the most load-bearing part of the proposal.

## MINOR

- plan-feature: Add `--force` to the documented argument surface or remove the retry advice; `.claude/skills/plan-feature/SKILL.md:4` only lists `<feature-name> [--subsystems <a,b,c>]`, while `.claude/skills/plan-feature/SKILL.md:121` says an existing spec should recommend `--force`.
- propose-boundary: Include `subsystem` in the proposal target-kind path or normalize it before render; `.claude/skills/propose-boundary/SKILL.md:118` says subsystem docs are accepted, `.claude/skills/propose-boundary/scripts/propose.py:90` returns `"subsystem"`, but `.claude/skills/propose-boundary/SKILL.md:204` only lists `file | directory | skill_directory`. Also align `call_edges`: `.claude/skills/propose-boundary/SKILL.md:166` says `{caller, callee, count}`, while `.claude/skills/propose-boundary/scripts/propose.py:659` emits file/caller/callee rows.
- propose-folder-reorganization: Change the early stop threshold to match ADR/helper behavior; `.claude/skills/propose-folder-reorganization/SKILL.md:133` says `fewer than 2 sibling files`, but `.claude/skills/propose-folder-reorganization/SKILL.md:314` and `.claude/skills/propose-folder-reorganization/scripts/inspect.py:395` use the `<3` cluster threshold.
- query-patterns: Replace missing `/promote-idea-to-pattern` handoffs (`.claude/skills/query-patterns/SKILL.md:39`, `.claude/skills/query-patterns/SKILL.md:156`, `.claude/skills/query-patterns/SKILL.md:198`) with current manual/Tier-2 guidance, and fix the stale empty-library exit sentence: `.claude/skills/query-patterns/SKILL.md:97` says `exit 0`, while `.claude/skills/query-patterns/scripts/query.py:263` returns 1 when there are no results.
- teach-pattern: Normalize the read-scope path to the smell-directory convention; `.claude/skills/teach-pattern/SKILL.md:89` says `reports/<find-*>/latest/`, while `.claude/skills/teach-pattern/SKILL.md:176` says on-disk dirs omit the `find-` prefix.
- track-idea: Replace missing `/promote-idea-to-pattern` handoffs with current manual/Tier-2 guidance; references appear at `.claude/skills/track-idea/SKILL.md:39`, `.claude/skills/track-idea/SKILL.md:230`, and `.claude/skills/track-idea/SKILL.md:237`.
- which-cleanup: Remove stale doc-link scanner prose; `.claude/skills/which-cleanup/SKILL.md:92` says the floor includes `find-doc-link-rot` on doc changes, while `.claude/skills/which-cleanup/scripts/select_scanners.py:56` sets `DOC_SHAPE_FLOOR: list[str] = []`.
```
