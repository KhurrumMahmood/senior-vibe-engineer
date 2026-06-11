# Scans Frontmatter Sweep

## Summary

Added explicit `scans:` frontmatter fields to 12 SUSPECT skills in both engineering-skills and host-a projects. Per ADR 0032, `scans:` lists the languages a detector's scan surface actually covers, enabling the perimeter audit to detect coverage gaps. The static/javascript gap (motivating incident from ADR 0032) is now closed.

## Skills Updated (with Evidence)

### language: any + Multi-language Detection

1. **find-async-lifecycle-drift** → `scans: [python, javascript]`
   - Evidence: `.claude/skills/find-async-lifecycle-drift/scripts/detect.py` line 19: `SUFFIXES = (".py", ".js")`

2. **find-comment-drift** → `scans: [python, javascript, templates]`
   - Evidence: `.claude/skills/find-comment-drift/scripts/detect.py` line 27: `SUFFIXES = (".py", ".js", ".html")`

3. **find-contract-drift** → `scans: [python, javascript, templates]`
   - Evidence: `.claude/skills/find-contract-drift/scripts/detect.py` line 28: `SUFFIXES = (".py", ".js", ".html")`

4. **find-dead-route-surface** → `scans: [python, javascript, templates]`
   - Evidence: `.claude/skills/find-dead-route-surface/scripts/detect.py` line 19: `SUFFIXES = (".py", ".js", ".html")`

5. **find-workflow-state-gaps** → `scans: [javascript, templates]`
   - Evidence: `.claude/skills/find-workflow-state-gaps/scripts/detect.py` line 19: `SUFFIXES = (".js", ".html")`

6. **find-test-obligation-drift** → `scans: [python, javascript, templates]`
   - Evidence: `.claude/skills/find-test-obligation-drift/scripts/detect.py` uses `endswith(".py")`, `endswith(".js")`, `endswith(".html")` checks across lines 100-150

### language: python + Cross-language Detection

7. **find-workflow-duplication** → `scans: [python, javascript, templates, markdown]`
   - Evidence: `scripts/detect.py` (lines 33-36) checks `templates/`, `static/js/`, `.js`, and `docs/` file paths; description line 3 states "backend, templates, JS, and docs"

8. **find-frontend-contract-drift** → `scans: [javascript, templates]`
   - Evidence: `scripts/detect.py` lines 562-563: `_scope.iter_paths(project_root, scope, extensions={".html"})` and `extensions={".js"}`

9. **find-frontend-duplication** → `scans: [javascript, templates]`
   - Evidence: `scripts/frontend_class_chain_scanner.py` line 95: `for path in base.rglob("*.html")` and `scripts/frontend_helper_scanner.py` line 75: `for path in sorted(js_dir.rglob("*.js"))`

### language: python + Markdown/Mixed Detection

10. **find-skill-artifact-drift** → `scans: [python, markdown]`
    - Evidence: Scans SKILL.md files (markdown) and Python scripts in `_common/` for skill integrity

11. **find-rule-surface-drift** → `scans: [markdown]`
    - Evidence: `scripts/detect.py` lines 201, 251: `for doc in sorted(docs_root.glob("*.md"))` — scans `.md` files only

12. **find-stale-artifacts** → `scans: [markdown]`
    - Evidence: `scripts/detect.py` lines 158, 253: `for plan in sorted(plans_root.glob("*.md"))` and `for entry in sorted(reports_root.glob("*.md"))` — scans `.md` files only

## Skills Deliberately Not Modified

- **find-omnibus**: Already correctly handles scans via language-adapter architecture (ADR 0032)
- **find-perimeter-gaps**: Meta-skill that reads scans declarations; no need for self-reference
- All `language: python` skills without cross-language detection (find-complexity-hotspots, find-query-mutation, find-implicit-state, find-layer-violation, find-transaction-overreach) — their `language:` frontmatter correctly covers them; adding `scans: [python]` would be redundant

## Test Results

- `tests/test_perimeter_gaps.py` and `tests/test_skill_taxonomy.py`: **6 passed** (0.05s)
- Perimeter gaps audit on host-a:
  - Before: 8 uncovered gaps (including **static/javascript** 38534 LOC, 74 files — the motivating incident)
  - After: **2 gaps** (only static/css and testing/sql, both expected — no CSS/SQL detectors exist)
  - static/javascript now covered by 9 detectors (find-async-lifecycle-drift, find-comment-drift, find-contract-drift, find-dead-route-surface, find-frontend-contract-drift, find-frontend-duplication, find-test-obligation-drift, find-workflow-duplication, find-workflow-state-gaps)

## Locations Modified

1. Engineering-skills: `~/Projects/engineering-skills/.claude/skills/`
   - find-async-lifecycle-drift/SKILL.md
   - find-comment-drift/SKILL.md
   - find-contract-drift/SKILL.md
   - find-dead-route-surface/SKILL.md
   - find-workflow-state-gaps/SKILL.md
   - find-test-obligation-drift/SKILL.md
   - find-workflow-duplication/SKILL.md
   - find-frontend-contract-drift/SKILL.md
   - find-frontend-duplication/SKILL.md
   - find-skill-artifact-drift/SKILL.md
   - find-rule-surface-drift/SKILL.md
   - find-stale-artifacts/SKILL.md

2. host-a (copied skills): `<host-a-checkout>/.claude/skills/`
   - Same 12 skills, updated in parallel to maintain consistency
