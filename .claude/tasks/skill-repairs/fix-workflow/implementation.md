# Implementation notes — /fix-workflow repair (Stage 4)

Date: 2026-06-12. Implemented per `change-spec.md` C1–C11, anchored
by scout §2 quotes. All eleven C-items applied; no spec deviation of
substance. Role note: implemented by the campaign orchestrator
inline rather than a fresh sub-agent (machine-local budget rule:
fewer agent lanes after observed mid-task lane deaths); independence
is recovered at Stage 5 by routing verification to the Codex lane.

## Files touched

- `.claude/skills/fix-workflow/SKILL.md` (C1–C3, C5–C11)
- `.claude/skills/fix-workflow/knowledge/verification.md` (NEW — C1,
  content verbatim from the spec)
- `.claude/skills/fix-workflow/knowledge/fix-shapes.md` (C1, C4, C5)
- `.claude/skills/fix-workflow/knowledge/learnings.md` (C1)

## Judgment calls

1. **C1 lead-in kept as "three knowledge files."** With
   `verification.md` restored the count is true again (the fourth
   bullet is the shared `_common` reference, not a knowledge file).
   Spec allowed either phrasing; chose the no-edit option.
2. **C3 coherence line.** Added `Entry format:` before the Step-5
   template block — the spec's replacement sentence left the
   markdown template without an introduction. Connective tissue
   only; no new obligation.
3. **C4 grep-roots fallback** merged into the existing "Run BOTH
   checks" sentence instead of a standalone sentence before the
   block, to keep the numbered-step voice. Same content as spec.
4. **C4 NO-EDIT honored:** learnings.md R13 `tests_custom_site` and
   cluster provenance examples untouched — illustrative provenance
   (learnings.md:8), not commands.
5. **C11 renumber:** Step 7 "Next cluster" became item 3 (spec
   explicitly allowed this list renumber; Steps/R-rules/§ untouched).
6. **C2 `layer:` loading bullet** placed directly after the
   `delete:`/`fix:` bullet (before the long `semantic:` bullet) for
   list scannability; spec said "after line 58" — same position.

## Verification run

- `.venv/bin/python scripts/skill_meta.py lint` → `OK — 74 skills,
  74 declaring new contract`.
- `grep -rn '`knowledge/`' .claude/skills/fix-workflow/` → 0 hits
  (all eight bare refs re-pointed).
- `grep -rn 'reports/duplication/learnings' .claude/skills/fix-workflow/`
  → 0 hits (declared-verdict item 4).
- Skill-local validate command: **none found** (grepped SKILL.md and
  knowledge/ for `--validate`/test invocations; the skill ships no
  scripts) — recorded explicitly per Stage 4 contract.

No commits made (campaign constraint).
